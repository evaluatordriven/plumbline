#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z — S1 instrument, job 2026-10-27-custody-emitter-gaps (author: Chief of Staff (Orchestrator) drafter).
"""Run one emitter revision on one held-out fixture and keep every artifact the N checks read.

  subject.py --rev <checkout of the emitter revision> --fixture <fixture dir> --checkpy <pinned check.py> --out <dir>

Writes <out>/job (a copy of the fixture the emitter ran on), <out>/emit.json {exit, stdout, stderr,
record_written, revision}, and when a record was written: <out>/record.custody.json, <out>/check.json (pinned
check.py on it) and <out>/bundle.zip (<rev>/tools/pack_stranger_bundle.py). Nothing else is read or written.
"""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys
from pathlib import Path

CHECKPY_SHA = "aaeb7e0532c950ee1736207b0a91ff9d810533fccecdb2c7708312408e5bcd18"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev", required=True); ap.add_argument("--fixture", required=True)
    ap.add_argument("--checkpy", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rev, out = Path(a.rev).resolve(), Path(a.out).resolve()
    if hashlib.sha256(Path(a.checkpy).read_bytes()).hexdigest() != CHECKPY_SHA:
        print("check.py is not the pinned one", file=sys.stderr); return 2
    if out.exists():
        shutil.rmtree(out)
    job = out / "job"
    shutil.copytree(a.fixture, job)
    revision = subprocess.run(["git", "-C", str(rev), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    p = subprocess.run([sys.executable, str(rev / "kit/emit_custody.py"), "--job-dir", str(job)], cwd=rev,
                       capture_output=True, text=True)
    rec = job / "custody" / "record.custody.json"
    emit = {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "record_written": rec.is_file(),
            "revision": revision}
    (out / "emit.json").write_text(json.dumps(emit, indent=1) + "\n")
    if rec.is_file():
        shutil.copy(rec, out / "record.custody.json")
        ci = json.loads((job / "inputs/custody.json").read_text())
        bar = (ci.get("bar") or {}).get("file")
        c = subprocess.run([sys.executable, a.checkpy, str(rec), "--files", str(job / ci.get("files_dir", "custody/files")),
                            "--evidence", str(job / ci.get("evidence_dir", "custody/evidence"))]
                           + (["--bar", str(job / bar)] if bar else []), capture_output=True, text=True)
        (out / "check.json").write_text(c.stdout if c.stdout.strip() else json.dumps({"verdict": None, "stderr": c.stderr}))
        b = subprocess.run([sys.executable, str(rev / "tools/pack_stranger_bundle.py"), "--job-dir", str(job),
                            "--out", str(out / "bundle.zip")], cwd=rev, capture_output=True, text=True)
        (out / "pack.json").write_text(json.dumps({"exit": b.returncode, "stdout": b.stdout, "stderr": b.stderr}, indent=1))
    print(json.dumps({"fixture": Path(a.fixture).name, "exit": p.returncode, "record": rec.is_file()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
