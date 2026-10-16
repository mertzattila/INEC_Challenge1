"""Deterministic retrieval for Ship or Block.

For each case we build a small, high-signal candidate set of provisions that could
change the answer, so the LLM never has to see the whole 20k-line corpus.

The candidate set is the union of:
  1. the provisions the answer cites (version in force on asked_on),
  2. provisions in force that textually reference a cited act/section
     ("Notwithstanding FDA §14 ...", "in place of ...", overrides),
  3. defined-term chains: "X means ..." provisions whose term appears in the
     question/answer/cited text, plus the schedule/category provisions those
     definitions point at,
  4. the best lexical (BM25) matches between the question+answer and every
     provision in force on asked_on.

Everything here is free: no model calls.
"""
import math
import re
from collections import Counter, defaultdict

# A provision reference like "FDA §14" or "SSA §7(1)".
REF_RE = re.compile(r"\b([A-Z]{2,5})\s*§\s*(\d+)")
# A quoted defined term: 'renal filtration patient'  (straight or curly quotes).
TERM_RE = re.compile(r"[\u2018'\"\u201c]([a-z][a-z \-]{2,60})[\u2019'\"\u201d]")
WORD_RE = re.compile(r"[a-z][a-z\-]+")

STOP = set(
    "the a an and or of to in on for by with at from as is are be shall may must "
    "that this it its he she his her you your i am not no any all each per which who "
    "what how much many does do done has have had will would can could de la le".split()
)

# How many definition "bridges" to chase per case.
TERM_BRIDGE_TOP = 8

# Small legal paraphrase map: everyday words in the questions mapped to the
# formal vocabulary the definitions use. Bridges the lexical gap that pure BM25
# cannot cross (e.g. a question says "dialysis", the law says "haemodialysis").
SYNONYMS = {
    "dialysis": ["haemodialysis", "hemodialysis", "renal", "filtration", "blood"],
    "kidney": ["renal", "haemodialysis"],
    "pool": ["bath", "aquatic", "swimmers", "swimming", "leisure", "gymnasium"],
    "swimming": ["bath", "aquatic", "leisure", "swimmers"],
    "pass": ["subscription", "ticket", "permit"],
    "monthly": ["subscription", "days"],
    "referee": ["adjudicator", "official", "officiating", "controller"],
    "umpire": ["adjudicator", "official"],
    "specialist": ["consultation", "secondary", "physician", "branch"],
    "doctor": ["physician", "consultation"],
    "appointment": ["consultation", "attendance"],
    "student": ["pupil", "enrolled", "full-time"],
    "pensioner": ["pension", "retired", "basic"],
    "disabled": ["disability", "impairment"],
    "bike": ["bicycle"],
    "ebike": ["bicycle", "electric"],
    "car": ["vehicle", "motor"],
    "night": ["shifts", "evening"],
    "injury": ["injured", "injuries", "hurt"],
    "injured": ["injury", "injuries"],
    "moved": ["registration", "resident", "arrived"],
    "newcomer": ["registration", "resident"],
    "fee": ["amount", "charge", "payable", "levy", "duty"],
    "discount": ["abatement", "reduction", "reduced", "rebate"],
    "reduction": ["abatement", "reduced", "rebate"],
    "library": ["card", "borrower"],
    "toll": ["passage", "road"],
    "medicine": ["dispensed", "medicament", "pharmaceutical"],
    "medication": ["dispensed", "medicine"],
}


def section_id(ref):
    """'SSA §7(1)' -> 'SSA §7'. Normalises whitespace around the section mark."""
    m = REF_RE.search(ref or "")
    return f"{m.group(1)} §{m.group(2)}" if m else (ref or "").strip()


def in_force(versions, day):
    """Return the version(s) of a provision in force on `day`.

    A version is in force when in_force_from <= day < in_force_to (or no end).
    There should be at most one; we return a list to be safe.
    """
    out = []
    for v in versions:
        frm = v.get("in_force_from")
        to = v.get("in_force_to")
        if frm and frm <= day and (to is None or day < to):
            out.append(v)
    return out


def _tokens(text):
    return [w for w in WORD_RE.findall((text or "").lower()) if w not in STOP and len(w) > 2]


class Index:
    """A BM25 lexical index over the current (as-of-day) text of every provision.

    We index each provision once using its latest version's text; the per-day
    in-force check is applied at query time so results never cite a dead version.
    """

    def __init__(self, provisions):
        self.provisions = provisions  # {pid: [version dicts]}
        self.tf = {}                  # pid -> {term: count}
        self.postings = defaultdict(list)  # term -> [(pid, tf), ...]
        self.df = defaultdict(int)
        self.len = {}
        for pid, versions in provisions.items():
            latest = max(versions, key=lambda v: v.get("version", 0))
            toks = _tokens(latest["heading"] + " " + latest["text"])
            counts = Counter(toks)
            self.tf[pid] = counts
            self.len[pid] = len(toks) or 1
            for t, c in counts.items():
                self.df[t] += 1
                self.postings[t].append((pid, c))
        self.N = len(self.tf) or 1
        self.avglen = (sum(self.len.values()) / self.N) if self.tf else 1.0
        # term -> provisions whose text defines it ("... means ...")
        self.term_defs = self._build_term_defs()
        # cross-reference graph for walking overrides/definitions
        self.refers_to, self.referenced_by = _build_ref_graph(provisions)
        # provisions that look like operative special rules (not pure definitions)
        self.override_markers = self._build_override_markers()
        # defined-term bridge: match plain-language questions to formal terms,
        # then reach the operative rules that use those terms.
        self._build_term_bridge()

    def _build_term_bridge(self):
        """For every defined term, record its definition provisions, a token bag
        of the definition body, and the provisions that USE the term."""
        self.term_def_tokens = {}   # term -> Counter of tokens from its definition body
        self.term_users = defaultdict(set)  # term -> pids whose text uses the term
        all_terms = list(self.term_defs)
        latest_low = {}
        for pid, versions in self.provisions.items():
            latest = max(versions, key=lambda v: v.get("version", 0))
            latest_low[pid] = latest["text"].lower()
        # which provisions use each term. Fast substring check (terms are multi-word
        # phrases, so false positives are rare); good enough to seed candidates.
        for term in all_terms:
            for pid, low in latest_low.items():
                if term in low:
                    self.term_users[term].add(pid)
        # definition body token bags
        for term, def_pids in self.term_defs.items():
            bag = Counter()
            for pid in def_pids:
                for v in self.provisions[pid]:
                    bag.update(_tokens(v["text"]))
            self.term_def_tokens[term] = bag

    def match_terms(self, query_tokens, top=6):
        """Return the defined terms whose definition body best matches the query,
        scored by shared informative tokens (idf-weighted)."""
        q = set(t for t in query_tokens if t in self.df)
        scored = []
        for term, bag in self.term_def_tokens.items():
            overlap = q & set(bag)
            if not overlap:
                continue
            s = sum(math.log(1 + self.N / (1 + self.df[t])) for t in overlap)
            scored.append((s, term))
        scored.sort(reverse=True)
        return [term for _, term in scored[:top]]

    def _build_override_markers(self):
        """pids whose latest text carries an override/special-rate signal."""
        signals = ("notwithstanding", "in place of", "instead of",
                   "despite", "the amount payable is", "pays half",
                   "no fee is charged", "is exempt", "reduced", "half of",
                   "this section does not apply", "does not benefit")
        out = set()
        for pid, versions in self.provisions.items():
            latest = max(versions, key=lambda v: v.get("version", 0))
            low = latest["text"].lower()
            if any(s in low for s in signals):
                out.add(pid)
        return out

    def _build_term_defs(self):
        defs = defaultdict(set)
        for pid, versions in self.provisions.items():
            for v in versions:
                for m in re.finditer(r"[\u2018'\"\u201c]([a-z][a-z \-]{2,60})[\u2019'\"\u201d]\s+means\b",
                                     v["text"].lower()):
                    defs[m.group(1).strip()].add(pid)
        return defs

    def bm25(self, query_tokens, k=25, k1=1.5, b=0.75):
        qcounts = Counter(t for t in query_tokens if t in self.df)
        scores = defaultdict(float)
        for t, tf_q in qcounts.items():
            idf = math.log(1 + (self.N - self.df[t] + 0.5) / (self.df[t] + 0.5))
            qweight = 1 + 0.3 * (tf_q - 1)
            for pid, tf in self.postings[t]:
                dl = self.len[pid]
                denom = tf + k1 * (1 - b + b * dl / self.avglen)
                scores[pid] += idf * (tf * (k1 + 1) / denom) * qweight
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [pid for pid, _ in ranked[:k]]


def _build_ref_graph(provisions):
    """Map every section -> set of provisions that reference it in their text.

    Lets us walk the override/definition graph in both directions cheaply.
    """
    refers_to = defaultdict(set)   # pid -> sections it mentions
    referenced_by = defaultdict(set)  # section -> pids that mention it
    for pid, versions in provisions.items():
        for v in versions:
            for m in REF_RE.finditer(v["text"]):
                ref = f"{m.group(1)} §{m.group(2)}"
                refers_to[pid].add(ref)
                referenced_by[ref].add(pid)
    return refers_to, referenced_by


def candidates(case, provisions, index, k_bm25=40, max_total=60):
    """Return (ordered list of candidate provision_ids, {pid: in-force version}).

    Strategy: start from the cited sections and the strongest lexical matches,
    then walk the cross-reference graph in both directions for two hops so that
    override -> definition -> schedule chains come along, and finally pull in the
    definitions of any formal term whose plain-language description matches the
    question. Order reflects confidence (cited, overrides, graph, lexical).
    """
    day = case["asked_on"]
    cited_sections = {section_id(c) for c in case.get("citations", [])}

    ordered = []
    seen = set()
    source = {}  # pid -> how it got in (for ranking)

    def add(pid, src=None):
        if pid and pid in provisions and pid not in seen:
            seen.add(pid)
            ordered.append(pid)
            source[pid] = src
            return True
        return False

    # 1. cited provisions
    for s in cited_sections:
        add(s)

    # 2. direct overrides: anything that references a cited section
    for s in cited_sections:
        for pid in sorted(index.referenced_by.get(s, ())):
            add(pid)

    # 3. lexical matches on the question + answer. This is what surfaces the
    #    special-rate act whose definition matches the plain-language facts
    #    ("dialysis three times a week" -> 'renal filtration patient').
    q_tokens = _tokens(case.get("question", "") + " " + case.get("answer", ""))
    lexical = index.bm25(q_tokens, k=k_bm25)
    for pid in lexical:
        add(pid)

    # 4a. defined-term chains: a term literally present in the question/answer/cited text
    hay = (case.get("question", "") + " " + case.get("answer", "")).lower()
    for s in cited_sections:
        for v in in_force(provisions.get(s, []), day):
            hay += " " + v["text"].lower()
    for term, def_pids in index.term_defs.items():
        if term in hay:
            for pid in def_pids:
                add(pid)
            for pid in index.term_users.get(term, ()):
                add(pid)

    # 4b. defined-term BRIDGE: the hard cross-act cases. The question describes
    #     facts in plain language ("dialysis three times a week") that match a
    #     formal definition ("renal filtration patient ... haemodialysis ...").
    #     Expand the query with legal synonyms, find the best-matching definitions,
    #     and pull in both the definition and the operative rules that use the term.
    expanded = list(q_tokens)
    for w in list(q_tokens):
        expanded.extend(SYNONYMS.get(w, ()))
    for term in index.match_terms(expanded, top=TERM_BRIDGE_TOP):
        for pid in index.term_defs.get(term, ()):
            add(pid, "bridge")
        for pid in index.term_users.get(term, ()):
            add(pid, "bridge")

    # 5. graph walk: for two hops, pull in whatever the current candidates
    #    reference and whatever references them. Definitions/overrides/schedules
    #    form short chains (operative rule -> defined term -> category table).
    frontier = list(ordered)
    for _hop in range(2):
        nxt = []
        for pid in frontier:
            for ref in index.refers_to.get(pid, ()):      # downward: what it points at
                if add(ref):
                    nxt.append(ref)
            for src in index.referenced_by.get(pid, ()):  # upward: what points at it
                if add(src):
                    nxt.append(src)
        frontier = nxt
        if len(ordered) >= max_total * 2:
            break

    # Rank: keep cited + overrides + top lexical first, then prefer provisions
    # that carry an override signal, then the rest, trimming to max_total.
    lex12 = set(lexical[:12])
    priority = {}
    for i, pid in enumerate(ordered):
        if pid in cited_sections:
            p = 100
        elif pid in lex12:
            p = 90 - lexical.index(pid)
        elif source.get(pid) == "bridge" and pid in index.override_markers:
            p = 78  # operative special rule found via a definition bridge
        elif source.get(pid) == "bridge":
            p = 70
        elif pid in index.override_markers:
            p = 50
        elif pid in lexical:
            p = 40 - min(lexical.index(pid), 30)
        else:
            p = 20
        priority[pid] = (p, -i)  # higher first, then insertion order
    ordered.sort(key=lambda pid: priority[pid], reverse=True)

    # resolve each candidate to the version in force on asked_on
    resolved = {}
    kept = []
    for pid in ordered:
        vs = in_force(provisions.get(pid, []), day)
        if vs:
            resolved[pid] = vs[0]
            kept.append(pid)
        elif pid in cited_sections:
            # cited but not in force: keep so the judge can flag a dead citation.
            kept.append(pid)
            resolved[pid] = None
        if len(kept) >= max_total:
            break
    return kept, resolved
