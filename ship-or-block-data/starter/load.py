"""Load the Nordvale corpus and the case files into plain Python structures."""
import json
from pathlib import Path


def _jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_corpus(corpus_dir="corpus"):
    """Return (acts, provisions).

    acts:       {"FDA": "Fees and Duties Act", ...}
    provisions: {"FDA §14": [version 1 dict, version 2 dict, ...], ...}
                Each version dict has provision_id, act_id, act_title, section,
                heading, version, in_force_from, in_force_to, text.
                Versions are sorted by version number. Which version applies on
                a given day is for you to work out.
    """
    corpus_dir = Path(corpus_dir)
    acts = {a["act_id"]: a["title"] for a in json.loads((corpus_dir / "acts.json").read_text(encoding="utf-8"))}
    provisions = {}
    for row in _jsonl(corpus_dir / "provisions.jsonl"):
        provisions.setdefault(row["provision_id"], []).append(row)
    for versions in provisions.values():
        versions.sort(key=lambda r: r["version"])
    return acts, provisions


def load_cases(path):
    """Return the cases in a practice.jsonl or test.jsonl file as a list of dicts."""
    return _jsonl(path)
