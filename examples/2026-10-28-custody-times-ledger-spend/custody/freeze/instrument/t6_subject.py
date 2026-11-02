#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — S1 T6 subject runner, job 2026-10-28-custody-times-ledger-spend.
"""Drop-in for the prior S1's subject.py (same CLI, same outputs), for T6:

  subject.py --rev <subject checkout> --fixture <fixture dir> --checkpy <pinned check.py> --out <dir>

1. emits a copy of the fixture with NO switch and keeps the hand-time lines it prints (the flagged set);
2. emits <out>/job WITH --allow-hand-times (the prior fixtures are hand-typed by design) and writes what the prior
   subject.py wrote: emit.json, record.custody.json, check.json, bundle.zip/pack.json;
3. runs the subject's kit/plumbline_verify.py on the record (--custody from env S1_CUSTODY).
emit.json gains: no_switch {exit, hand: [[field, file, line, source]]}, hand_times (the record's), verify {rc, kinds}.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys
from pathlib import Path

CHECKPY_SHA = "aaeb7e0532c950ee1736207b0a91ff9d810533fccecdb2c7708312408e5bcd18"
HAND = re.compile(r"^\s*\[hand-time\]\s+(\S+)\s+(\S+):(\d+)\s+\(([a-z-]+)\)", re.M)
VFAIL = re.compile(r"^FAIL\s+(\S+)\s+(\S+)\s+(\S+?):(\d+)\s*$", re.M)


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
    out.mkdir(parents=True)
    revision = subprocess.run(["git", "-C", str(rev), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    j0 = out / "job-noswitch"
    shutil.copytree(a.fixture, j0)
    p0 = subprocess.run([sys.executable, str(rev / "kit/emit_custody.py"), "--job-dir", str(j0)], cwd=rev,
                        capture_output=True, text=True)
    hand = sorted({(f, fl, int(ln), s) for f, fl, ln, s in HAND.findall(p0.stdout + "\n" + p0.stderr)})
    shutil.rmtree(j0)
    job = out / "job"
    shutil.copytree(a.fixture, job)
    p = subprocess.run([sys.executable, str(rev / "kit/emit_custody.py"), "--job-dir", str(job), "--allow-hand-times"],
                       cwd=rev, capture_output=True, text=True)
    rec = job / "custody" / "record.custody.json"
    emit = {"exit": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "record_written": rec.is_file(),
            "revision": revision, "no_switch": {"exit": p0.returncode, "hand": hand}}
    if rec.is_file():
        shutil.copy(rec, out / "record.custody.json")
        r = json.loads(rec.read_text())
        emit["hand_times"] = ((r.get("predicate") or {}).get("x-plumbline") or {}).get("hand_times")
        ci = json.loads((job / "inputs/custody.json").read_text())
        bar = (ci.get("bar") or {}).get("file")
        files, ev = job / ci.get("files_dir", "custody/files"), job / ci.get("evidence_dir", "custody/evidence")
        c = subprocess.run([sys.executable, a.checkpy, str(rec), "--files", str(files), "--evidence", str(ev)]
                           + (["--bar", str(job / bar)] if bar else []), capture_output=True, text=True)
        (out / "check.json").write_text(c.stdout if c.stdout.strip() else json.dumps({"verdict": None, "stderr": c.stderr}))
        b = subprocess.run([sys.executable, str(rev / "tools/pack_stranger_bundle.py"), "--job-dir", str(job),
                            "--out", str(out / "bundle.zip")], cwd=rev, capture_output=True, text=True)
        (out / "pack.json").write_text(json.dumps({"exit": b.returncode, "stdout": b.stdout, "stderr": b.stderr}, indent=1))
        vf = rev / "kit/plumbline_verify.py"
        if vf.is_file():
            v = subprocess.run([sys.executable, str(vf), "--record", str(rec), "--files", str(files), "--evidence", str(ev),
                                "--ledger", str(job / "inputs/custody-events.jsonl"), "--custody",
                                os.environ.get("S1_CUSTODY", ""), "--json", str(out / "verify.json")],
                               cwd=rev, capture_output=True, text=True)
            emit["verify"] = {"rc": v.returncode, "kinds": sorted({k for k, *_ in VFAIL.findall(v.stdout)}),
                              "out": (v.stdout + v.stderr)[-1500:]}
        else:
            emit["verify"] = {"rc": None, "kinds": [], "out": "no kit/plumbline_verify.py"}
    (out / "emit.json").write_text(json.dumps(emit, indent=1) + "\n")
    print(json.dumps({"fixture": Path(a.fixture).name, "exit": p.returncode, "record": rec.is_file()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
