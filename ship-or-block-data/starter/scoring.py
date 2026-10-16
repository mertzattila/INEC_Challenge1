"""The official scoring rule. score.py uses it on the practice set; Azta uses the same code on the test set.

Per case:            answer correct   answer wrong
  SHIP                    +1              -3
  BLOCK, right evidence   -1              +1
  BLOCK, other            -1               0
Model spending does not affect the score. Missing or invalid rows count as BLOCK without evidence.
Evidence is one provision ID at section level ("SSA §7"); a subsection like "SSA §7(1)" is cut to the section.
"""
import re

SHIP_RIGHT, SHIP_WRONG, BLOCK_RIGHT_ANSWER, BLOCK_PROVED = 1, -3, -1, 1


def norm_evidence(ev):
    ev = re.sub(r"\s+", " ", (ev or "").strip())
    ev = re.sub(r"\s*§\s*", " §", ev)
    return re.sub(r"(§\d+)\(.*$", r"\1", ev)


def score(truth, decisions, spent=0.0):  # spent is ignored, kept for compatibility
    """truth: list of cases with label and evidence; decisions: {case_id: (decision, evidence)}."""
    pts = 0
    counts = {"ship_right": 0, "ship_wrong": 0, "block_proved": 0, "block_unproved": 0, "block_right_answer": 0}
    for case in truth:
        decision, evidence = decisions.get(case["case_id"], ("BLOCK", ""))
        wrong = case["label"] == "BLOCK"
        if decision == "SHIP":
            pts += SHIP_WRONG if wrong else SHIP_RIGHT
            counts["ship_wrong" if wrong else "ship_right"] += 1
        elif not wrong:
            pts += BLOCK_RIGHT_ANSWER
            counts["block_right_answer"] += 1
        elif norm_evidence(evidence) in {norm_evidence(e) for e in case["evidence"]}:
            pts += BLOCK_PROVED
            counts["block_proved"] += 1
        else:
            counts["block_unproved"] += 1
    return {"score": pts, "points": pts, "cost_penalty": 0,
            "max": len(truth), **counts}
