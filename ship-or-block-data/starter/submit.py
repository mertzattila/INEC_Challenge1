"""Write and check submission.csv.

    from submit import write_submission
    write_submission({"T001": ("SHIP", ""), "T002": ("BLOCK", "SSA §7")}, "submission.csv")

    python submit.py submission.csv test.jsonl     # checks the file before you email it
"""
import csv
import json
import re
import sys

EVIDENCE = re.compile(r"^[A-Z]{2,5} §\d+$")


def write_submission(decisions, path="submission.csv"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "decision", "evidence"])
        for case_id, (decision, evidence) in sorted(decisions.items()):
            w.writerow([case_id, decision, evidence if decision == "BLOCK" else ""])


def read_submission(path):
    """Return {case_id: (decision, evidence)}; the first row for a case wins."""
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = (row.get("case_id") or "").strip()
            if cid and cid not in out:
                out[cid] = ((row.get("decision") or "").strip().upper(), (row.get("evidence") or "").strip())
    return out


def check(path, cases_path):
    ids = [json.loads(l)["case_id"] for l in open(cases_path, encoding="utf-8") if l.strip()]
    sub = read_submission(path)
    problems = []
    for cid in ids:
        if cid not in sub:
            problems.append(f"{cid}: missing (counts as BLOCK without evidence)")
            continue
        decision, evidence = sub[cid]
        if decision not in ("SHIP", "BLOCK"):
            problems.append(f"{cid}: decision {decision!r} is not SHIP or BLOCK")
        if decision == "BLOCK" and evidence and not EVIDENCE.match(evidence):
            problems.append(f"{cid}: evidence {evidence!r} should look like 'SSA §7'")
    extra = set(sub) - set(ids)
    if extra:
        problems.append(f"{len(extra)} rows with unknown case_id, e.g. {sorted(extra)[:3]}")
    return problems


if __name__ == "__main__":
    probs = check(sys.argv[1], sys.argv[2])
    print("\n".join(probs[:50]) if probs else "OK: every case has a valid row.")
    if len(probs) > 50:
        print(f"... and {len(probs) - 50} more")
