#!/usr/bin/env python3
"""Vendor the corpus's schemas and its WHOLE fixture battery at the pinned commit, and write VENDOR.json.

    tools/vendor_corpus.py [--corpus PATH]          # write schemas/vendor/e-di@<pin8>/ from the corpus at the pin

WHY THIS EXISTS. The vendored copy used to be made by a shell loop over a named list of files, recorded as text
in VENDOR.json. A named list misses fixtures the corpus adds later; the alignment check then fails, naming the
missing files, and someone has to work out why. This copies the two schemas plus every `fixtures/*.json` the
corpus holds AT THE PINNED COMMIT (read with `git show`, never from the working tree), so the copy is the
corpus's bytes by construction. It removes any other `e-di@*` vendored copy. It never re-pins: run
`tools/build_schemas.py --repin` first; this reads tools/pin.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import edi_corpus  # noqa: E402

SCHEMAS = ("job-packet.schema.json", "evaluator-record.schema.json")


def git(top: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(top), *args], capture_output=True, text=True, check=True).stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="")
    a = ap.parse_args()
    pin = json.loads((REPO / "tools" / "pin.json").read_text(encoding="utf-8"))
    corpus, _ = edi_corpus.resolve_or_exit(a.corpus or None, ("schemas/job-packet.schema.json",))
    corpus = corpus.path if hasattr(corpus, "path") else Path(corpus)
    top = Path(git(corpus, "rev-parse", "--show-toplevel").strip()).resolve()
    prefix = corpus.resolve().relative_to(top).as_posix()
    prefix = "" if prefix == "." else prefix + "/"
    commit = pin["commit"]
    listed = git(top, "ls-tree", "--name-only", f"{commit}:{prefix}schemas/fixtures").split()
    names = [f"{n}" for n in SCHEMAS] + [f"fixtures/{f}" for f in sorted(listed) if f.endswith(".json")]
    dest = REPO / "schemas" / "vendor" / f"e-di@{commit[:8]}"
    for old in (REPO / "schemas" / "vendor").glob("e-di@*"):
        if old != dest:
            shutil.rmtree(old)
    files = {}
    for n in names:
        data = subprocess.run(["git", "-C", str(top), "show", f"{commit}:{prefix}schemas/{n}"],
                              capture_output=True, check=True).stdout
        out = dest / n
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        files[n] = {"original_path": f"schemas/{n}", "sha256": hashlib.sha256(data).hexdigest()}
    vendor = {
        "source_repo": pin.get("corpus", ""),
        "commit": commit,
        "copied_by": f"tools/vendor_corpus.py: the two schemas and every fixtures/*.json at {commit[:8]}, read with git show",
        "files": files,
    }
    (dest / "VENDOR.json").write_text(json.dumps(vendor, indent=2) + "\n", encoding="utf-8")
    print(f"vendored {len(files)} files ({len(files) - len(SCHEMAS)} fixtures) to {dest.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
