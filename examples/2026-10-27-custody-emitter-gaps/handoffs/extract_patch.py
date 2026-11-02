#!/usr/bin/env python3
"""Copy the Maker's patch out of a reply, byte for byte. Stdlib only; no network.

  extract_patch.py REPLY.txt OUT.patch
Takes the lines strictly between the first line that is exactly ```diff and the next line that is exactly ```.
Nothing is edited, trimmed or reordered. Exit 0 written; 1 no such block (OUT not written).
"""
import sys
from pathlib import Path

def main() -> int:
    lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines(keepends=True)
    try:
        i = next(k for k, ln in enumerate(lines) if ln.rstrip("\r\n") == "```diff")
        j = next(k for k in range(i + 1, len(lines)) if lines[k].rstrip("\r\n") == "```")
    except StopIteration:
        print("extract_patch: no ```diff ... ``` block in the reply", file=sys.stderr); return 1
    Path(sys.argv[2]).write_text("".join(lines[i + 1:j]), encoding="utf-8")
    print(f"extract_patch: lines {i + 2}-{j} of {sys.argv[1]} -> {sys.argv[2]}"); return 0

if __name__ == "__main__":
    sys.exit(main())
