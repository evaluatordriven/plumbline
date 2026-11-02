#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — S1 instrument, job 2026-10-28-custody-times-ledger-spend (author: Chief of Staff (Orchestrator) drafter). Copied unchanged in logic from job 2026-10-28-doctrine-reader-pointer.
"""S1 check P5(e) (bar.md, amendment 2). Prints one JSON object {check: "P5e", verdict PASS|FAIL, why[], ...};
exit 0 PASS, 1 FAIL, 2 usage.

  p5check.py --job J [--record R]

J is a job folder whose inputs/custody-events.jsonl holds the ledger (kit/custody_ledger.py). The frozen set is
the directory of the freeze event's `bar_file`. PASS iff all of:
  1. exactly one freeze event;
  2. each frozen file carries a header `FROZEN-BUILD <YYYY-MM-DDTHH:MM:SSZ>` in its first 3 lines: the bar file,
     `bounds`, `controls/README.md`, and every file under `freeze/harness/` and `freeze/instrument/` of the frozen
     set (except `freeze/harness/fixtures/`, recorded API replies); at least one harness/instrument file exists;
  3. every header's build time <= the freeze event's `at` (whole seconds UTC);
  4. sha256(bar file) == the freeze event's `bar_sha256`;
  5. with --record: the record's `predicate.bar.digest.sha256` == that same digest.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

HDR = re.compile(r"FROZEN-BUILD (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)")


def t(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def header_time(p: Path):
    try:
        head = p.read_text(encoding="utf-8", errors="replace").splitlines()[:3]
    except OSError:
        return None
    for line in head:
        m = HDR.search(line)
        if m:
            return m.group(1)
    return None


def check(job: Path, record: Path | None) -> dict:
    why, ev = [], job / "inputs" / "custody-events.jsonl"
    out = {"check": "P5e", "job": str(job), "ledger": str(ev)}
    if not ev.is_file():
        return {**out, "verdict": "FAIL", "why": [f"no ledger at {ev}"]}
    rows = []
    for n, line in enumerate(ev.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except ValueError:
                why.append(f"ledger line {n} is not JSON")
    fz = [r for r in rows if r.get("event") == "freeze"]
    if len(fz) != 1:
        return {**out, "verdict": "FAIL", "why": why + [f"{len(fz)} freeze events in the ledger; exactly one required"]}
    fz = fz[0]; at = t(fz.get("at"))
    out["freeze"] = {k: fz.get(k) for k in ("at", "bar_file", "bar_sha256")}
    if at is None:
        why.append(f"freeze event time {fz.get('at')!r} is not YYYY-MM-DDTHH:MM:SSZ")
    bar = job / str(fz.get("bar_file") or "")
    if not bar.is_file():
        return {**out, "verdict": "FAIL", "why": why + [f"freeze event's bar_file {fz.get('bar_file')!r} not in the job"]}
    fset = bar.parent
    files = [bar, fset / "bounds", fset / "controls" / "README.md"]
    code = sorted(p for d in ("freeze/harness", "freeze/instrument") for p in (fset / d).rglob("*")
                  if p.is_file() and "fixtures" not in p.relative_to(fset / d).parts and "__pycache__" not in p.parts)
    if not code:
        why.append("no harness/instrument files under freeze/ in the frozen set")
    headers = []
    for p in files + code:
        rel = str(p.relative_to(job)) if p.is_relative_to(job) else str(p)
        if not p.is_file():
            why.append(f"{rel}: missing"); continue
        h = header_time(p); headers.append({"file": rel, "build": h})
        if h is None:
            why.append(f"{rel}: no `FROZEN-BUILD <time>` header in the first 3 lines")
        elif at is not None and t(h) > at:
            why.append(f"{rel}: build time {h} is later than the ledger freeze at {fz.get('at')}")
    out["headers"] = headers
    d = hashlib.sha256(bar.read_bytes()).hexdigest(); out["bar_sha256"] = d
    if fz.get("bar_sha256") != d:
        why.append(f"sha256({fz.get('bar_file')}) = {d} but the ledger freeze event records {fz.get('bar_sha256')!r}")
    if record is not None:
        try:
            rd = json.loads(record.read_text(encoding="utf-8"))["predicate"]["bar"]["digest"]["sha256"]
        except (OSError, ValueError, KeyError, TypeError):
            rd = None
        out["record_bar_sha256"] = rd
        if rd != d:
            why.append(f"record bar digest {rd!r} != sha256 of the frozen bar {d}")
    return {**out, "verdict": "FAIL" if why else "PASS", "why": why}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--job", required=True); ap.add_argument("--record")
    a = ap.parse_args(argv)
    r = check(Path(a.job).resolve(), Path(a.record).resolve() if a.record else None)
    print(json.dumps(r, indent=1))
    return 0 if r["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
