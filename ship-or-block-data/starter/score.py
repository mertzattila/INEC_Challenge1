"""Score a submission on the practice set, exactly like the final scoring.

    python score.py practice_submission.csv practice.jsonl
"""
import argparse
import json

from scoring import score
from submit import read_submission

p = argparse.ArgumentParser()
p.add_argument("submission")
p.add_argument("practice", nargs="?", default="practice.jsonl")
p.add_argument("--spent", type=float, default=None)
a = p.parse_args()

truth = [json.loads(l) for l in open(a.practice, encoding="utf-8") if l.strip()]
r = score(truth, read_submission(a.submission), a.spent)
print(f"score {r['score']} of max {r['max']}")
print(f"  shipped: {r['ship_right']} right, {r['ship_wrong']} wrong")
print(f"  blocked wrong answers: {r['block_proved']} with right evidence, {r['block_unproved']} without")
print(f"  blocked right answers: {r['block_right_answer']}")
