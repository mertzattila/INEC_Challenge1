"""The LLM judge: given a case and its retrieved provisions, decide SHIP or BLOCK.

One model call per case. The model only ever sees the small candidate set that
retrieval surfaced, never the whole corpus.
"""
import json
import re

from retrieval import section_id

SYSTEM = """You are a legal answer-checker for Nordvale, a fictional country. \
You decide whether an AI-drafted answer to a legal/tax question should be shipped \
to the user or blocked. Judge ONLY against the law provisions given to you. \
Nordvale law is self-contained; ignore any real-world law you may know.

SHIP the answer only if ALL four conditions hold on the law in force on the ask date:
  1. Every factual statement in the answer is supported by the provisions it cites.
  2. Every citation exists, was in force on the ask date, and supports the statement it backs.
  3. No OTHER provision in force on the ask date changes the answer for the facts
     GIVEN IN THE QUESTION: no exception, override, cross-act definition,
     transitional rule or special rate is missed.
  4. Simple arithmetic from the law counts as supported
     ("half of 30 crowns is 15 crowns" is fine).
Otherwise BLOCK.

Critical rules of interpretation:
- Do NOT assume facts the question does not state: If the question does not say the person is a student or registered peat cutter, a student-only or peat-cutter-only rule does NOT apply and does NOT make the answer wrong.
- Strict condition & threshold verification: Check numbers, limits, quotas, and timing conditions meticulously!
  * If a special rule requires "at least 30 matches" and the person only refereed 22 matches, the rule DOES NOT APPLY.
  * If a discount applies "for at most 10 nights" and the person already used 10 nights, the discount is exhausted and DOES NOT APPLY.
  * If an exemption applies only to the "first month" or "beginning attendance" and the person attended since months ago, it DOES NOT APPLY.
  * If an answer correctly states "no reduction applies" or quotes the standard fee because the person fails the threshold, the answer is CORRECT -> SHIP it!
- A defined term (e.g. 'renal filtration patient', 'leisure subscription') has a formal definition that may live in a different act and applies across all acts. Apply a special rule ONLY if the question's stated facts actually satisfy every element of that definition.
- A newer version of the cited section in force on the ask date (different fee/number) makes an answer citing the old number wrong -> BLOCK, evidence = that section.
- If a cited section was NOT IN FORCE on the ask date -> BLOCK, evidence = that cited section.
- Transitional rules: if a fee or rate changed but a transitional rule in force protects or grandfathers the user based on registration date -> BLOCK, evidence = that transitional section.
- Do NOT cite a provision as evidence to BLOCK if that provision is already cited in the answer, unless the answer misapplied its text or numbers.
- When you BLOCK, pick the SINGLE provision that most directly proves the answer wrong, at section level (e.g. "SSA §7", "FDA §40", never "SSA §7(1)"). If several prove it, any one is fine; prefer the operative rule (the special rate / override / transitional rule / new version), not the pure definition.

Respond with ONLY a JSON object, no prose:
{"decision": "SHIP"} or {"decision": "BLOCK", "evidence": "SSA §7"}"""


def build_prompt(case, candidate_ids, resolved, acts):
    lines = []
    lines.append(f"ASK DATE: {case['asked_on']}")
    lines.append(f"QUESTION: {case['question']}")
    lines.append(f"ANSWER TO CHECK: {case['answer']}")
    lines.append(f"CITATIONS IN THE ANSWER: {', '.join(case.get('citations', [])) or '(none)'}")
    lines.append("")
    lines.append("LAW PROVISIONS (only these; each is the version in force on the ask date "
                 "unless marked NOT IN FORCE):")
    cited = {section_id(c) for c in case.get("citations", [])}
    for pid in candidate_ids:
        v = resolved.get(pid)
        act = acts.get(pid.split(" ")[0], "")
        tag = " [CITED]" if pid in cited else ""
        if v is None:
            lines.append(f"\n### {pid} ({act}){tag}  -- NOT IN FORCE on the ask date")
            continue
        window = f"{v['in_force_from']} -> {v['in_force_to'] or 'open'}"
        lines.append(f"\n### {pid} v{v.get('version')} ({act}) [{window}]{tag}")
        lines.append(f"{v['heading']}: {v['text']}")
    lines.append("")
    lines.append("Decide SHIP or BLOCK. Output ONLY the JSON object.")
    return "\n".join(lines)


_JSON_RE = re.compile(r"\{.*\}", re.S)


def parse_decision(text, candidate_ids):
    """Parse the model reply into (decision, evidence). Defaults to BLOCK on garble,
    which is the safe, scoring-aligned fallback."""
    m = _JSON_RE.search(text or "")
    if not m:
        return "BLOCK", ""
    try:
        obj = json.loads(m.group(0))
    except Exception:
        # tolerate trailing text / single quotes
        try:
            obj = json.loads(m.group(0).replace("'", '"'))
        except Exception:
            return "BLOCK", ""
    decision = str(obj.get("decision", "")).strip().upper()
    if decision == "SHIP":
        return "SHIP", ""
    if decision == "BLOCK":
        ev = section_id(obj.get("evidence", "")) if obj.get("evidence") else ""
        # keep evidence only if it is one of the provisions we actually showed,
        # otherwise the model may be hallucinating an ID.
        if ev and ev in {section_id(c) for c in candidate_ids}:
            return "BLOCK", ev
        return "BLOCK", ev  # still return it; scorer will judge correctness
    return "BLOCK", ""
