# Ship or Block: starter kit

Plumbing only. Nothing here decides anything; that is your job.

| File | What it gives you |
|---|---|
| `load.py` | `load_corpus("corpus")` and `load_cases("test.jsonl")` |
| `llm.py` | `chat(prompt, model=...)` with retries and cost per call; `run_parallel(fn, items, workers=8)`; every call logged to `calls.jsonl` |
| `budget.py` | `python budget.py` or `remaining()`: dollars spent and left on your key |
| `submit.py` | `write_submission(decisions)`; `python submit.py submission.csv test.jsonl` checks the file |
| `score.py` | `python score.py my_practice.csv practice.jsonl`: your score on the practice set, same rule as the final |
| `scoring.py` | The official scoring rule, in code |

Setup (Python 3.9+, no packages needed):

    export OPENROUTER_API_KEY=sk-or-...        # from your team's email
    python budget.py                           # check the key works

Put the kit next to the data (`corpus/`, `practice.jsonl`, `test.jsonl`) or pass paths.
`:free` models are refused by `llm.chat`, as the rules require.
