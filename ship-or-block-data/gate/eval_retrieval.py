"""Offline check (no LLM): does retrieval surface the ground-truth evidence?

For every practice BLOCK case, the gate can only succeed if at least one of the
case's evidence provisions is in the candidate set. This measures retrieval recall,
the ceiling on the gate's score, for free.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "starter"))

from load import load_corpus, load_cases
import retrieval
from retrieval import section_id

acts, provisions = load_corpus(os.path.join(HERE, "..", "corpus"))
index = retrieval.Index(provisions)
cases = load_cases(os.path.join(HERE, "..", "practice.jsonl"))

max_total = int(sys.argv[1]) if len(sys.argv) > 1 else 40
k_bm25 = int(sys.argv[2]) if len(sys.argv) > 2 else 24

hit = miss = 0
misses = []
sizes = []
for c in cases:
    if c["label"] != "BLOCK":
        continue
    ids, _ = retrieval.candidates(c, provisions, index, k_bm25=k_bm25, max_total=max_total)
    sizes.append(len(ids))
    cand = {section_id(i) for i in ids}
    gold = {section_id(e) for e in c["evidence"]}
    if cand & gold:
        hit += 1
    else:
        miss += 1
        misses.append((c["case_id"], sorted(gold), len(ids)))

total = hit + miss
print(f"evidence recall on practice BLOCKs: {hit}/{total} = {hit/total:.1%}")
print(f"avg candidate set size: {sum(sizes)/len(sizes):.1f}")
if misses:
    print("\nMISSED (gold evidence not retrieved):")
    for cid, gold, n in misses:
        print(f"  {cid}: wanted one of {gold}  (showed {n} candidates)")
