#!/usr/bin/env python3
"""Job 2026-10-28-custody-times-ledger-spend, iteration 2 guide redo, step 3 of 3 (Orchestrator-written 2026-10-29;
pinned in handoffs/iter2/MANIFEST-guide-redo-2.sha256). Appends FEEDBACK-guide-rules.md (two rules the Owner added,
Owner decision 2026-10-29 07:50 EDT) to the LAST user turn, after FEEDBACK-guide.md, under its own separator (it is
not Evaluator feedback, so add_feedback.py's separator would mislabel it). Stdlib only; no network; no model.

  add_owner_rules.py IN_MESSAGES.json RULES.md OUT_MESSAGES.json

IN must be add_feedback.py's output for the guide part built on add_iter1_guide.py's output: the last user turn must
show the iteration-1 guide file block and end with FEEDBACK-guide.md exactly (its sha256 is pinned below), and must
not already contain this separator. Refuses (exit 2) otherwise, if RULES.md is empty, or if OUT exists.
"""
import hashlib, json, sys
from pathlib import Path

FEEDBACK_GUIDE_SHA256 = "ec1efd28da8e4e20a4612e5c3c91132676578a6da44f6ab92a56e3432d79f334"
FG_BLOCK = "## FILE docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md (YOUR iteration-1 guide, as committed at 1cb410badbff;"
SEP = ("\n\n==== ITERATION 2: TWO RULES THE OWNER ADDED FOR THIS GUIDE (in addition to the evaluator's item above; "
       "keep everything else) ====\n\n")


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: add_owner_rules.py IN_MESSAGES.json RULES.md OUT_MESSAGES.json", file=sys.stderr); return 2
    src, rules_p, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    if out.exists():
        print(f"REFUSED: {out} exists", file=sys.stderr); return 2
    rules = rules_p.read_text(encoding="utf-8")
    if not rules.strip():
        print("REFUSED: empty rules file", file=sys.stderr); return 2
    msgs = json.loads(src.read_text(encoding="utf-8"))
    if not msgs or msgs[-1].get("role") != "user" or not isinstance(msgs[-1].get("content"), str):
        print("REFUSED: last turn is not a plain-text user turn", file=sys.stderr); return 2
    c = msgs[-1]["content"]
    if FG_BLOCK not in c:
        print("REFUSED: the iteration-1 guide block is not in the request (run add_iter1_guide.py first)", file=sys.stderr); return 2
    if SEP.strip() in c:
        print("REFUSED: the owner rules are already appended", file=sys.stderr); return 2
    # FEEDBACK-guide.md must be the tail: find its pinned bytes at the end
    ok = False
    for n in range(1, min(len(c), 20000) + 1):
        if hashlib.sha256(c[-n:].encode("utf-8")).hexdigest() == FEEDBACK_GUIDE_SHA256:
            ok = True; break
    if not ok:
        print("REFUSED: the request does not end with FEEDBACK-guide.md (pinned sha256)", file=sys.stderr); return 2
    msgs[-1] = {**msgs[-1], "content": c + SEP + rules}
    out.write_text(json.dumps(msgs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"add_owner_rules: {out} sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
