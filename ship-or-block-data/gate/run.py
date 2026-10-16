"""Ship or Block: run the gate over a case file and write submission.csv.

Usage:
    export OPENROUTER_API_KEY=sk-or-...
    python run.py --cases ../practice.jsonl --out practice_submission.csv --score
    python run.py --cases ../test.jsonl     --out submission.csv

Pipeline per case:
    retrieval.candidates(...)  ->  judge.build_prompt(...)  ->  one chat() call
                               ->  judge.parse_decision(...)

The model only ever sees the retrieved candidate provisions, so cost stays low
and we can judge against a 20k-provision corpus that never fits in context.
"""
import argparse
import json
import os
import sys

# make the starter plumbing (load/llm/budget) and the gate package importable
HERE = os.path.dirname(os.path.abspath(__file__))
STARTER = os.path.join(HERE, "..", "starter")
sys.path.insert(0, HERE)
sys.path.insert(0, STARTER)

from load import load_corpus, load_cases          # noqa: E402  (starter)
from llm import chat, run_parallel, total_cost     # noqa: E402  (starter)
from submit import write_submission                # noqa: E402  (starter)

import retrieval                                    # noqa: E402  (gate)
import judge                                        # noqa: E402  (gate)

DEFAULT_MODEL = "google/gemini-2.5-flash"


def decide_one(case, provisions, index, acts, model, max_total, k_bm25,
               max_tokens, verbose=False):
    ids, resolved = retrieval.candidates(
        case, provisions, index, k_bm25=k_bm25, max_total=max_total)
    prompt = judge.build_prompt(case, ids, resolved, acts)
    reply = chat(prompt, model=model, system=judge.SYSTEM,
                 max_tokens=max_tokens, temperature=0.0)
    decision, evidence = judge.parse_decision(reply.text, ids)
    if verbose:
        print(f"{case['case_id']}: {decision} {evidence}  "
              f"(candidates={len(ids)}, ${reply.cost:.5f})")
    return case["case_id"], decision, evidence, reply.cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True, help="practice.jsonl or test.jsonl")
    ap.add_argument("--corpus", default=os.path.join(HERE, "..", "corpus"))
    ap.add_argument("--out", default="submission.csv")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-total", type=int, default=70, help="max provisions shown to the model")
    ap.add_argument("--k-bm25", type=int, default=48, help="lexical candidates to add")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--limit", type=int, default=0, help="debug: only first N cases")
    ap.add_argument("--score", action="store_true", help="score against practice labels after running")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print("loading corpus ...", flush=True)
    acts, provisions = load_corpus(args.corpus)
    print(f"  {len(provisions)} provisions, {len(acts)} acts", flush=True)
    print("building lexical index ...", flush=True)
    index = retrieval.Index(provisions)

    cases = load_cases(args.cases)
    if args.limit:
        cases = cases[:args.limit]
    print(f"judging {len(cases)} cases with {args.model} ...", flush=True)

    def fn(case):
        return decide_one(case, provisions, index, acts, args.model,
                          args.max_total, args.k_bm25, args.max_tokens, args.verbose)

    results = run_parallel(fn, cases, workers=args.workers)

    decisions = {}
    failures = 0
    for r in results:
        if isinstance(r, Exception):
            failures += 1
            continue
        cid, decision, evidence, _ = r
        decisions[cid] = (decision, evidence)
    # any case that errored out -> safe default BLOCK without evidence
    for c in cases:
        decisions.setdefault(c["case_id"], ("BLOCK", ""))

    write_submission(decisions, args.out)
    spent = total_cost()
    print(f"\nwrote {args.out}  ({len(decisions)} rows)")
    print(f"model failures (defaulted to BLOCK): {failures}")
    print(f"spent this run: ${spent:.4f}   (~${spent / max(len(cases),1):.5f} per case)")

    if args.score:
        from scoring import score
        truth = [c for c in cases if "label" in c]
        if truth:
            r = score(truth, decisions)
            print("\n--- practice score ---")
            print(f"score {r['score']} of max {r['max']}")
            print(f"  shipped: {r['ship_right']} right, {r['ship_wrong']} wrong")
            print(f"  blocked wrong answers: {r['block_proved']} proved, {r['block_unproved']} unproved")
            print(f"  blocked right answers (false blocks): {r['block_right_answer']}")
        else:
            print("\n(no labels in this file; skipping score)")


if __name__ == "__main__":
    main()
