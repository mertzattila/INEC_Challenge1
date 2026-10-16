"""Offline end-to-end test of the pipeline with a FAKE model (no credit spent).

Proves retrieval -> prompt -> parse -> submission -> scoring all wire up, and
that a trivial 'always BLOCK with the first candidate' policy produces a valid,
scorable submission. This is plumbing validation only, not a quality measure.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "starter"))

import retrieval
import judge
from load import load_corpus, load_cases
from submit import write_submission
from scoring import score

acts, provisions = load_corpus(os.path.join(HERE, "..", "corpus"))
index = retrieval.Index(provisions)
cases = load_cases(os.path.join(HERE, "..", "practice.jsonl"))

decisions = {}
empty_candidates = 0
for c in cases:
    ids, resolved = retrieval.candidates(c, provisions, index, k_bm25=48, max_total=70)
    prompt = judge.build_prompt(c, ids, resolved, acts)
    assert isinstance(prompt, str) and len(prompt) > 50
    if not ids:
        empty_candidates += 1
    # fake model reply: BLOCK citing the top candidate
    fake = '{"decision": "BLOCK", "evidence": "%s"}' % (ids[0] if ids else "")
    decision, evidence = judge.parse_decision(fake, ids)
    decisions[c["case_id"]] = (decision, evidence)

out = os.path.join(HERE, "selftest_submission.csv")
write_submission(decisions, out)
truth = [c for c in cases if "label" in c]
r = score(truth, decisions)
print("PIPELINE OK")
print(f"  cases with zero candidates: {empty_candidates}")
print(f"  all-BLOCK baseline score: {r['score']} of {r['max']}")
print(f"  (blocked wrong: {r['block_proved']} proved / {r['block_unproved']} unproved; "
      f"false blocks of right answers: {r['block_right_answer']})")
os.remove(out)
