#!/usr/bin/env python3
"""Job 2026-10-28-custody-times-ledger-spend, iteration 2 guide redo (Orchestrator-written, 2026-10-29; pinned in
handoffs/iter2/MANIFEST-guide-redo.sha256). Fixes a handoff defect: build_maker_messages.py --part guide never shows
the current guide, so FEEDBACK-guide.md's "The file shown above is YOUR iteration-1 guide" was not true for guide a1.
This helper inserts the iteration-1 guide, byte for byte, into the guide request built by build_maker_messages.py.
Stdlib + git only; no network; no model; never reads the held-out controls or the key.

  add_iter1_guide.py IN_BASE_MESSAGES.json REPO OUT_MESSAGES.json

REPO is any git checkout that holds commit ITER1 (e.g. $R). The guide is read with `git show ITER1:FG` and must hash
to ITER1_GUIDE_SHA256. OUT = IN with one block inserted into the LAST user turn, immediately before the builder's
closing line "Return your files now, following the OUTPUT CONTRACT exactly.": a fixed heading (below), then the
guide in the builder's own fence. Then run add_feedback.py on OUT with FEEDBACK-guide.md, so the feedback follows.
Refuses (exit 2) if IN is not a part-guide request, if the closing line is not where the builder puts it, if IN
already shows the guide file, if the guide bytes differ from the pin, or if OUT exists.
"""
import hashlib, json, subprocess, sys
from pathlib import Path

ITER1 = "1cb410badbff504ca480b199ae4fe4f37caed893"
FG = "docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md"
ITER1_GUIDE_SHA256 = "7b8214a9ae5f579c232365623ae702e19cf77fb66f70a10e6ed4b2abf884e645"
CLOSE = "Return your files now, following the OUTPUT CONTRACT exactly.\n"
HEAD = ("## FILE " + FG + " (YOUR iteration-1 guide, as committed at " + ITER1[:12] + "; sha256 " +
        ITER1_GUIDE_SHA256 + ")\n\n"
        "This request REVISES this file; it does not start a new one. Return the complete file, starting from the text "
        "below: keep every section, rule, story and line that the iteration-2 feedback at the end does not name, and "
        "change only what it names. The two drafts above remain the only sources for any story you add.\n\n")


def fence(text: str) -> str:  # identical to build_maker_messages.py fence()
    f = "````" if "```" in text else "```"
    return f"{f}\n{text}{'' if text.endswith(chr(10)) else chr(10)}{f}\n"


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: add_iter1_guide.py IN_BASE_MESSAGES.json REPO OUT_MESSAGES.json", file=sys.stderr); return 2
    src, repo, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    if out.exists():
        print(f"REFUSED: {out} exists", file=sys.stderr); return 2
    msgs = json.loads(src.read_text(encoding="utf-8"))
    if not msgs or msgs[-1].get("role") != "user" or not isinstance(msgs[-1].get("content"), str):
        print("REFUSED: last turn is not a plain-text user turn", file=sys.stderr); return 2
    c = msgs[-1]["content"]
    if not c.startswith("# Part `guide`"):
        print("REFUSED: not a part-guide request", file=sys.stderr); return 2
    if "## FILE " + FG in c:
        print("REFUSED: the request already shows the guide file", file=sys.stderr); return 2
    if not c.endswith("\n" + CLOSE) or c.count(CLOSE) != 1:
        print("REFUSED: the builder's closing line is not where expected", file=sys.stderr); return 2
    r = subprocess.run(["git", "-C", repo, "show", f"{ITER1}:{FG}"], capture_output=True)
    if r.returncode != 0:
        print(f"REFUSED: git show {ITER1[:12]}:{FG} failed in {repo}", file=sys.stderr); return 2
    if hashlib.sha256(r.stdout).hexdigest() != ITER1_GUIDE_SHA256:
        print("REFUSED: iteration-1 guide bytes differ from the pin", file=sys.stderr); return 2
    guide = r.stdout.decode("utf-8")
    block = HEAD + fence(guide)
    msgs[-1] = {**msgs[-1], "content": c[: -len(CLOSE)] + block + "\n" + CLOSE}
    out.write_text(json.dumps(msgs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"add_iter1_guide: {out} sha256 {hashlib.sha256(out.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
