#!/usr/bin/env python3
"""A frozen verdict for every record we publish, and the exact command that produces it.

The point is not to re-run a check today. It is to make a checker change prove it moved no published
verdict: each row carries its command, its input commit and the verdict it must still produce, and this
script refuses when a row's result drifts. A row whose inputs are not published cannot be frozen, and says
so in `unfreezable` rather than being quietly counted as passing.

    python3 tools/check_verdicts.py [--custody DIR] [--json OUT]

Exit 0 every row matches, 1 a row drifted, 2 the table or the custody checkout could not be read.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "tools" / "verdicts.json"


def checkout(custody: str | None, commit: str) -> tuple[Path | None, str]:
    """A custody checkout at `commit`: the argument, $CUSTODY_DIR, or a shallow clone."""
    if custody:
        p = Path(custody).expanduser()
        return (p, "") if (p / "checker" / "check.py").is_file() else (None, f"{p} has no checker/check.py")
    env = os.environ.get("CUSTODY_DIR")
    if env:
        p = Path(env).expanduser()
        if (p / "checker" / "check.py").is_file():
            return p, ""
        return None, f"CUSTODY_DIR={p} has no checker/check.py"
    d = Path(tempfile.mkdtemp(prefix="custody-"))
    r = subprocess.run(["git", "clone", "--quiet", "--depth", "1",
                        "https://github.com/evaluatordriven/custody", str(d)], capture_output=True, text=True)
    if r.returncode != 0:
        return None, f"clone failed: {r.stderr.strip()[:200]}"
    # A shallow clone holds only the tip, so the row's commit is fetched by name rather than assumed present.
    r = subprocess.run(["git", "-C", str(d), "fetch", "--quiet", "--depth", "1", "origin", commit],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, f"fetch {commit} failed: {r.stderr.strip()[:200]}"
    r = subprocess.run(["git", "-C", str(d), "checkout", "--quiet", "FETCH_HEAD"], capture_output=True, text=True)
    if r.returncode != 0:
        return None, f"checkout {commit} failed: {r.stderr.strip()[:200]}"
    return d, ""


def run_row(row: dict, custody: Path) -> tuple[bool, str]:
    job = ROOT / row["job"]
    r = subprocess.run([sys.executable, str(custody / "checker" / "check.py"), row["record"],
                        "--files", row["files"], "--evidence", row["evidence"], "--bar", row["bar"]],
                       cwd=job, capture_output=True, text=True)
    try:
        got = json.loads(r.stdout)
    except json.JSONDecodeError:
        return False, f"checker printed no JSON (exit {r.returncode}): {r.stderr.strip()[:160]}"
    want = row["expect"]
    failed = sorted(k for k, v in got["requirements"].items() if v.get("status") == "FAILED")
    ok = (got["verdict"] == want["verdict"] and got["levelAchieved"] == want["levelAchieved"]
          and failed == sorted(want["failed"]))
    return ok, f"{got['verdict']}/{got['levelAchieved'] or '-'} failed={failed}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--custody")
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    if not TABLE.is_file():
        print(f"no table at {TABLE}")
        return 2
    here = TABLE.parent.parent
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    rows = table.get("rows") or []
    pin_path = ROOT / "tools" / "pin.json"
    pinned = (json.loads(pin_path.read_text(encoding="utf-8")).get("custody") or {}).get("commit") \
        if pin_path.is_file() else None
    if rows and pinned and table.get("custodyCommit") and pinned != table["custodyCommit"]:
        print(f"the table froze verdicts at custody {table['custodyCommit'][:8]} but the pin is {pinned[:8]}: "
              f"a re-pin must re-freeze the table, or the checker moved under it")
        return 2
    out, bad = [], 0
    checkout_dir, why = checkout(a.custody, table.get("custodyCommit", "main")) if rows else (None, "")
    if rows and checkout_dir is None:
        print(f"cannot resolve the custody checkout: {why}")
        return 2
    for row in rows:
        if not (here / row["job"] / row["record"]).is_file():
            print(f"MISSING  {row['job']} ({row['record']})")
            bad += 1
            continue
        ok, detail = run_row(row, checkout_dir)
        print(f"{'PASS' if ok else 'FAIL':8} {row['job']:44} {detail}")
        out.append({"job": row["job"], "command": row.get("command"), "custodyCommit": row.get("custodyCommit"),
                    "ok": ok, "detail": detail})
        bad += 0 if ok else 1
    for u in table.get("unfreezable") or []:
        print(f"UNFROZEN {u['record']:44} {u['why']}")
    if a.json:
        Path(a.json).write_text(json.dumps({"rows": out}, indent=1) + "\n", encoding="utf-8")
    print(f"VERDICTS {len(rows) - bad} of {len(rows)} match; {len(table.get('unfreezable') or [])} record(s) cannot be frozen")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
