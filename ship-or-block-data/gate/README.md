# Ship or Block — the gate

A gate that checks AI-drafted legal answers against Nordvale law and decides
**SHIP** (the answer is right) or **BLOCK** (it's wrong, here's the provision that
proves it). Built on top of the starter plumbing in `../starter`.

## The idea

The corpus is ~16k provisions / 21k section-versions — far too big for any model
context. The wrong answers are rarely wrong on their face: the trap is a hidden
rule in **another act** (an override, a special rate, or a formal definition that
changes who a rule applies to). So the gate is two layers:

1. **Retrieval (free, no model).** For each case we build a small candidate set of
   provisions that could change the answer:
   - the cited sections, resolved to the version **in force on `asked_on`**;
   - every provision that textually references a cited section ("Notwithstanding
     FDA §14 …") — the direct overrides;
   - **BM25** lexical matches between the question+answer and the whole corpus;
   - a **defined-term bridge**: the question describes facts in plain language
     ("dialysis three times a week"); the law uses formal terms ("renal filtration
     patient … haemodialysis …"). We expand the query with legal synonyms, match it
     to the best definition bodies, and pull in both the definition and the
     operative rules that *use* that term;
   - a 2-hop walk of the cross-reference graph so override → defined term → schedule
     chains come along together.

   On the practice set this surfaces the ground-truth evidence provision for
   **~82%** of the wrong answers (measured by `eval_retrieval.py`).

2. **Judge (one model call per case).** The model sees only the retrieved
   provisions and applies the four official SHIP conditions. It returns JSON:
   `{"decision":"SHIP"}` or `{"decision":"BLOCK","evidence":"SSA §7"}`. Anything
   unparseable defaults to BLOCK (the safe, scoring-aligned fallback).

## Files

| File | Role |
|---|---|
| `retrieval.py` | candidate selection: in-force resolution, BM25, reference graph, defined-term bridge |
| `judge.py` | the judge system prompt, prompt builder, and reply parser |
| `run.py` | ties it together, runs cases in parallel, writes `submission.csv` |
| `eval_retrieval.py` | offline: does retrieval contain the gold evidence? (no model) |
| `dryrun.py` | offline: prompt sizes and a cost estimate before spending (no model) |
| `selftest.py` | offline: full wiring check with a fake model (no model) |

## Run it

```bash
export OPENROUTER_API_KEY=sk-or-...          # from the team email

# 0. check retrieval + sizing for free
python eval_retrieval.py                      # evidence recall on practice
python dryrun.py                              # token/cost estimate

# 1. develop on the practice set (scores against the real labels)
python run.py --cases ../practice.jsonl --out practice_submission.csv --score

# 2. once happy, run the test set (this is what you submit)
python run.py --cases ../test.jsonl --out submission.csv
python ../starter/submit.py submission.csv ../test.jsonl   # validate the file
python ../starter/budget.py                                # what's left
```

### Useful knobs

- `--model` any OpenRouter id (default `google/gemini-2.5-flash`). Try
  `google/gemini-2.5-flash-lite` to cut cost ~3×, or a stronger model if the
  budget allows and the practice score justifies it.
- `--max-total` provisions shown to the model (default 70). Higher = better recall,
  more cost.
- `--k-bm25` lexical candidates added (default 48).
- `--workers` parallel calls (default 8).
- `--limit N` judge only the first N cases while iterating.

## Cost

At the defaults, ~10.6k input tokens/case. A full 500-case test run is roughly
**$1–2** on `gemini-2.5-flash` and **~$0.55** on `gemini-2.5-flash-lite`. Every call
is logged to `calls.jsonl`; `python ../starter/budget.py` shows the key balance.

## What it misses

Retrieval ceiling is ~82% on practice: a handful of wrong answers hinge on a
multi-hop definition chain whose operative rule shares no vocabulary with the
question (e.g. an entirely paraphrased concept). Those get BLOCKed anyway (avoiding
the −3 of a wrong SHIP) but may be scored as "blocked without the right evidence"
(0 instead of +1). Widening the synonym map or adding an embedding retriever would
lift this further.
