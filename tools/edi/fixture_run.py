#!/usr/bin/env python3
"""tools/edi/fixture_run.py: run a fixture tree from a writable copy.

    fixture_run.py --src DIR --work DIR --summary FILE

Copies src into work, making every copied file owner-writable and every copied
directory owner-writable and searchable, whatever the source modes were.  The
summary is {started_at, finished_at, writer, files: [{path, sha256, mode}]}
with paths relative to work and mode as an octal string.  Two runs from the same
contents differ only in started_at and finished_at.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

HARNESS_NAME = "tools/edi/fixture_run.py"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def writer() -> str:
    sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    return f"{HARNESS_NAME}@{sha}"


def _force_rmtree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if not path.exists():
        return
    for root, dirs, files in os.walk(path):
        for d in dirs:
            os.chmod(Path(root) / d, 0o700)
        for f in files:
            os.chmod(Path(root) / f, 0o600)
    os.chmod(path, 0o700)
    shutil.rmtree(path)


def copy_writable(src: Path, work: Path) -> None:
    _force_rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        wroot = work / rel
        wroot.mkdir(parents=True, exist_ok=True)
        os.chmod(wroot, (stat.S_IMODE(os.stat(wroot).st_mode) & 0o777) | 0o700)
        for name in files:
            s = Path(root) / name
            d = wroot / name
            shutil.copyfile(s, d)
            os.chmod(d, (stat.S_IMODE(os.stat(d).st_mode) & 0o777) | 0o600)
    for root, dirs, files in os.walk(work):
        os.chmod(root, (stat.S_IMODE(os.stat(root).st_mode) & 0o777) | 0o700)
        for name in files:
            p = Path(root) / name
            os.chmod(p, (stat.S_IMODE(os.stat(p).st_mode) & 0o777) | 0o600)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Copy a fixture tree into a writable work tree.")
    ap.add_argument("--src", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--summary", required=True)
    a = ap.parse_args(argv)
    src, work, summary = Path(a.src), Path(a.work), Path(a.summary)
    if not src.is_dir():
        print(f"fixture_run: --src {src} is not a directory", file=sys.stderr)
        return 2
    started = now()
    try:
        copy_writable(src, work)
        files = []
        for root, dirs, names in os.walk(work):
            for name in names:
                p = Path(root) / name
                rel = p.relative_to(work).as_posix()
                files.append({
                    "path": rel,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    "mode": oct(stat.S_IMODE(p.stat().st_mode) & 0o777),
                })
        files.sort(key=lambda x: x["path"])
        finished = now()
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text(json.dumps({
            "started_at": started,
            "finished_at": finished,
            "writer": writer(),
            "files": files,
        }, indent=2) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"fixture_run: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
