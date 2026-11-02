#!/usr/bin/env python3
"""Run every Plumbline suite once and say, in one place, what ran, what failed and what was skipped.

    python3 tests/run_all.py                    # a stranger's run: no corpus, the corpus checks SKIP by name
    EDI_CORPUS=<e-di checkout> python3 tests/run_all.py      # the opt-in run: the corpus checks run too
    PLUMBLINE_REQUIRE_CORPUS=1 python3 tests/run_all.py      # every would-be SKIP is a FAIL

WHAT IT RUNS (cwd = the repository root, the interpreter running this file, the caller's environment):
  1. tools/build_schemas.py --check           owns corpus.build-check
  2. tools/build_schemas.py --custody --check
  3. tests/validate_schemas.py                 owns corpus.battery-equality and corpus.pin-on-disk
  4. tests/validate_audit.py                   owns corpus.audit-equality
  5. tests/validate_pin_prose.py
  6. tests/validate_constitution.py
  7. -m unittest discover -s tests -p 'test_*.py'
  and kit/cases/run_cases.py                   owns corpus.run-cases (counted only as that id)

WHAT IT PRINTS (stdout, whole lines):
  corpus source: <rule>                        only when a corpus resolves
  suite <name>: rc=<n> pass|FAIL               one per suite, with the suite's own output tail when it failed
  SKIP[corpus] <id>: <reason>                  one line per corpus-dependent id, exactly as its owner printed it:
  RAN[corpus] <id>: pass|fail                    SKIP (no corpus, not required), RAN (a corpus resolved) or
  FAIL[corpus] <id>: <reason>                    FAIL (PLUMBLINE_REQUIRE_CORPUS=1 and no corpus)
  PLUMBLINE-TALLY pass=<n> fail=<n> skip=<n> skipped=<ids|->   always the last line; 12 items: 7 suites by rc,
                                                                and the 5 ids
An id whose owner printed no line for it (the owner crashed, say) is reported as a failure, never as a skip.

EXIT: 0 exactly when fail=0. A PLUMBLINE_REQUIRE_CORPUS value other than unset, "", 0 or 1, or an EDI_CORPUS that is
set but is not a corpus, is a usage error: nothing runs, the message names it, the tally counts all 12 as failed,
exit 2. The corpus rules are tools/edi_corpus.py's (D-E); this runner resolves only --/EDI_CORPUS, as the suites do.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import edi_corpus  # noqa: E402

PY = sys.executable
SUITES = [
    ("build_schemas --check", [PY, "tools/build_schemas.py", "--check"]),
    ("build_schemas --custody --check", [PY, "tools/build_schemas.py", "--custody", "--check"]),
    ("validate_schemas", [PY, "tests/validate_schemas.py"]),
    ("validate_audit", [PY, "tests/validate_audit.py"]),
    ("validate_pin_prose", [PY, "tests/validate_pin_prose.py"]),
    ("validate_constitution", [PY, "tests/validate_constitution.py"]),
    ("unittest", [PY, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
]
RUN_CASES = ("run_cases", [PY, "kit/cases/run_cases.py"])
OWNER = {
    "corpus.audit-equality": "validate_audit",
    "corpus.battery-equality": "validate_schemas",
    "corpus.build-check": "build_schemas --check",
    "corpus.pin-on-disk": "validate_schemas",
    "corpus.run-cases": "run_cases",
}
assert set(OWNER) == set(edi_corpus.IDS)
LINE = re.compile(r"^(SKIP|RAN|FAIL)\[corpus\] (\S+): (.*)$")
TAIL = 40


def tally(passed: int, failed: int, skipped: list[str]) -> str:
    return (f"PLUMBLINE-TALLY pass={passed} fail={failed} skip={len(skipped)} "
            f"skipped={','.join(sorted(skipped)) or '-'}")


def run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, timeout=3600)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as e:
        return 124, (e.stdout or "") if isinstance(e.stdout, str) else "", f"timed out after {e.timeout}s"
    except OSError as e:
        return 127, "", f"could not start: {e}"


def main() -> int:
    try:
        edi_corpus.require_corpus()
        corpus = edi_corpus.resolve(None, ("schemas/job-packet.schema.json", "tools/validate_job_packet.py"),
                                    hermes=False)
    except edi_corpus.CorpusUsageError as e:
        print(f"USAGE ERROR: {e}")
        print("nothing was run: a usage error is not a skip")
        print(tally(0, len(SUITES) + len(OWNER), []))
        return 2
    if corpus:
        corpus.announce()

    outputs: dict[str, str] = {}
    passed = failed = 0
    for name, cmd in SUITES + [RUN_CASES]:
        rc, out, err = run(cmd)
        outputs[name] = out
        if name == RUN_CASES[0]:
            if rc != 0:
                print(f"note: run_cases exited {rc}; it is counted as corpus.run-cases")
            continue
        ok = rc == 0
        passed, failed = passed + ok, failed + (not ok)
        print(f"suite {name}: rc={rc} {'pass' if ok else 'FAIL'}")
        if not ok:
            # the tail a reader needs: what failed, not the rows that passed or the id lines reported below
            body = [ln for ln in (out + err).splitlines()
                    if ln.strip() and not LINE.match(ln) and not ln.startswith(("[PASS] ", "[ok] "))]
            for ln in body[-TAIL:]:
                print(f"    | {ln}")

    skipped: list[str] = []
    for cid in sorted(OWNER):
        found = [m for m in (LINE.match(ln) for ln in outputs[OWNER[cid]].splitlines()) if m and m.group(2) == cid]
        if len(found) == 1:
            kind, rest = found[0].group(1), found[0].group(3)
            print(found[0].group(0))
            if kind == "SKIP":
                skipped.append(cid)
            elif kind == "RAN" and rest == "pass":
                passed += 1
            else:
                failed += 1
        else:
            print(f"FAIL[corpus] {cid}: {OWNER[cid]} printed {len(found)} result lines for this id, not 1 — a check "
                  f"with no single result is a failure, never a skip")
            failed += 1
    print(tally(passed, failed, skipped))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
