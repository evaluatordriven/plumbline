#!/usr/bin/env python3
"""Job 2026-10-28-custody-times-ledger-spend, iteration 2 (NEW in iteration 2; Orchestrator-written; pin its sha256
in handoffs/iter2/MANIFEST.sha256 before use). Add the Evaluator-derived, control-free feedback for ONE PART to the
messages that build_maker_messages.py wrote, mechanically. Stdlib only; no network; no model.

  add_feedback.py IN_MESSAGES.json FEEDBACK.md OUT_MESSAGES.json

OUT = IN with FEEDBACK.md appended verbatim to the LAST user turn, after the fixed separator below (roles keep
alternating). The operator adds no words of its own. Refuses (exit 2) if IN's last turn is not a user turn, if
FEEDBACK.md is empty, or if OUT already exists.
"""
import json, sys
from pathlib import Path

SEP = ("\n\n==== ITERATION 2: WHAT THE EVALUATOR FOUND IN YOUR ITERATION-1 FILES FOR THIS PART ====\n"
       "The starting files above already contain your iteration-1 work. Keep everything that is not named below; "
       "fix what is named; follow the OUTPUT CONTRACT above exactly.\n\n")

def main() -> int:
    if len(sys.argv) != 4:
        print("usage: add_feedback.py IN_MESSAGES.json FEEDBACK.md OUT_MESSAGES.json", file=sys.stderr); return 2
    src, fb, out = (Path(x) for x in sys.argv[1:4])
    if out.exists():
        print(f"REFUSED: {out} exists", file=sys.stderr); return 2
    msgs = json.loads(src.read_text(encoding="utf-8"))
    text = fb.read_text(encoding="utf-8")
    if not text.strip():
        print("REFUSED: empty feedback", file=sys.stderr); return 2
    if not msgs or msgs[-1].get("role") != "user" or not isinstance(msgs[-1].get("content"), str):
        print("REFUSED: last turn is not a plain-text user turn", file=sys.stderr); return 2
    msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + SEP + text}
    out.write_text(json.dumps(msgs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    sys.exit(main())
