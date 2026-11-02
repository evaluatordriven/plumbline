#!/usr/bin/env python3
"""Job 2026-10-28-custody-times-ledger-spend (copied from job 2026-10-28-doctrine-reader-pointer; header and the
wrapper's "same base" wording only). Build the next logged Maker call of ONE PART after a failed extract/test,
mechanically. Stdlib only; no network. The operator resets the Maker checkout to the part's starting commit first.

  followup_messages.py PREV_MESSAGES.json PREV_REPLY.txt FAILURE.txt OUT_MESSAGES.json
OUT = PREV messages + the Maker's previous reply (verbatim, as the assistant turn) + one user turn carrying
FAILURE.txt verbatim. The operator adds no words of its own beyond the fixed wrapper below.
"""
import json, sys
from pathlib import Path

WRAP = ("Your files were not accepted. The operator ran the step named below and it failed; its verbatim output "
        "follows. Nothing you returned was kept. Return the COMPLETE set of files again (every file you change, "
        "each in full, for this part, against the same starting files), following the OUTPUT CONTRACT exactly.\n\n```\n{failure}```\n")

def main() -> int:
    prev, reply, failure, out = sys.argv[1:5]
    msgs = json.loads(Path(prev).read_text(encoding="utf-8"))
    f = Path(failure).read_text(encoding="utf-8")
    msgs += [{"role": "assistant", "content": Path(reply).read_text(encoding="utf-8")},
             {"role": "user", "content": WRAP.format(failure=f if f.endswith("\n") else f + "\n")}]
    Path(out).write_text(json.dumps(msgs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    sys.exit(main())
