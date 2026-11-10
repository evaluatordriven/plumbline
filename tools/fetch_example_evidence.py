#!/usr/bin/env python3
"""Fetch the example evidence that is too large to keep in the working tree.

    python3 tools/fetch_example_evidence.py            # into the paths the records name
    python3 tools/fetch_example_evidence.py --to /tmp/x # somewhere else
    python3 tools/fetch_example_evidence.py --check     # verify without writing

Each entry in `tools/evidence-archive.json` carries the sha256 the example record pins. A file that
downloads to a different digest is refused, not written: the point of moving these out of the tree is
that the record still verifies byte-for-byte once they are fetched back, and a fetch that silently
returns different bytes would make the record unverifiable while looking fine.

No third-party imports; this runs on a machine that has just cloned the repo.
"""
import argparse
import hashlib
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "tools" / "evidence-archive.json"


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", default=None, help="directory to fetch into instead of the recorded paths")
    ap.add_argument("--check", action="store_true", help="only report which files are present and correct")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = manifest["files"]
    failures = 0
    for e in entries:
        target = (pathlib.Path(args.to) / e["asset"]) if args.to else (ROOT / e["path"])
        if target.is_file():
            ok = digest(target) == e["sha256"]
            print("%-7s %s" % ("OK" if ok else "WRONG", e["path"]))
            failures += 0 if ok else 1
            continue
        if args.check:
            print("%-7s %s" % ("MISSING", e["path"]))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".part")
        try:
            with urllib.request.urlopen(e["url"], timeout=180) as r, open(tmp, "wb") as fh:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
        except Exception as exc:                                    # noqa: BLE001 - reported, not raised
            print("FAILED  %s: %s" % (e["path"], exc))
            tmp.unlink(missing_ok=True)
            failures += 1
            continue
        got = digest(tmp)
        if got != e["sha256"]:
            print("REFUSED %s: downloaded sha256 %s, the record pins %s" % (e["path"], got[:16], e["sha256"][:16]))
            tmp.unlink(missing_ok=True)
            failures += 1
            continue
        tmp.replace(target)
        print("FETCHED %s (%d bytes)" % (e["path"], e["bytes"]))
    print("evidence-archive: %d file(s), %d failure(s)" % (len(entries), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
