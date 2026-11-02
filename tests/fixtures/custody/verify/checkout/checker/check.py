#!/usr/bin/env python3
"""A stand-in for the pinned custody checker: it checks the subject digests and nothing else.

The real checker (checker/check.py in the custody checkout) is pinned by tools/pin.json; this file stands in for
it in the verifier's own tests, so they need no network and no checkout. Command line, flags and exit codes are
the real checker's: `check.py RECORD --files DIR --evidence DIR [--bar FILE]`, 0 OK, 1 FAILED, 2 not checkable.
"""
import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("record")
    ap.add_argument("--files", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--bar")
    a = ap.parse_args(argv)
    try:
        rec = json.loads(Path(a.record).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 2
    if not isinstance(rec, dict):
        return 2
    files = Path(a.files)
    for s in rec.get("subject") or []:
        p = files / str(s.get("name") or "")
        if not p.is_file():
            return 1
        want = (s.get("digest") or {}).get("sha256")
        if sha256(p.read_bytes()).hexdigest() != want:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
