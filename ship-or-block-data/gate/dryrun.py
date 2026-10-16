"""Estimate prompt size / cost WITHOUT calling any model.

Builds the exact prompt the judge would send for every practice case and reports
character and rough token counts, so we can size the budget before spending.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "starter"))

from load import load_corpus, load_cases
import retrieval
import judge

max_total = int(sys.argv[1]) if len(sys.argv) > 1 else 70
k_bm25 = int(sys.argv[2]) if len(sys.argv) > 2 else 48
cases_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "..", "practice.jsonl")

acts, provisions = load_corpus(os.path.join(HERE, "..", "corpus"))
index = retrieval.Index(provisions)
cases = load_cases(cases_path)

chars = []
for c in cases:
    ids, resolved = retrieval.candidates(c, provisions, index, k_bm25=k_bm25, max_total=max_total)
    p = judge.build_prompt(c, ids, resolved, acts)
    chars.append(len(p) + len(judge.SYSTEM))

n = len(chars)
tot = sum(chars)
# ~4 chars per token is the usual rough rule
in_tok = tot / 4
print(f"cases: {n}")
print(f"avg prompt chars: {tot/n:.0f}   max: {max(chars)}")
print(f"est input tokens total: {in_tok:,.0f}   avg/case: {in_tok/n:,.0f}")
# cost at a few price points ($/1M input tokens); output assumed ~40 tokens/case
for name, pin, pout in [("gemini-2.5-flash", 0.30, 2.50),
                        ("gemini-2.5-flash-lite", 0.10, 0.40),
                        ("gpt-4.1-mini", 0.40, 1.60)]:
    out_tok = n * 60
    cost = in_tok / 1e6 * pin + out_tok / 1e6 * pout
    print(f"  {name:24s} ~${cost:.3f} for {n} cases  (~${cost/n*1000:.3f}/1k cases)")
