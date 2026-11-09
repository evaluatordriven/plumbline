#!/usr/bin/env python3
"""A run file the emitter cannot read is refused BY NAME — never a traceback.

WHY THIS EXISTS. Measured 2026-11-09, trying to close a filed job: its `round-01.json` carries
`pass_rule: "accepted"`, the older run shape. `refusals()` did `(run.get("pass_rule") or {}).get(...)`,
which raised `AttributeError: 'str' object has no attribute 'get'` — a traceback where a refusal belongs. The
close wrapper reported "the record emitter refused", but the reason was a crash, and four filed jobs share that
shape. The property is narrow and worth its own test: a malformed run is a fact about the input, and the input
must be named.
"""
from __future__ import annotations
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EMIT = REPO / "kit" / "emit_record.py"
# A job the repo actually filed, used only for its packet: the test needs terms, not a verdict.
PACKET_SOURCE = REPO / "dot-plumbline" / "jobs" / "plumbline-job1-record-1" / "packet.json"


class PassRuleShape(unittest.TestCase):
    def test_a_string_pass_rule_is_refused_by_name_and_not_by_traceback(self):
        if not PACKET_SOURCE.is_file():
            self.skipTest(f"no packet to borrow at {PACKET_SOURCE}")
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp) / "job"
            job.mkdir()
            shutil.copy(PACKET_SOURCE, job / "packet.json")
            (job / "round-01.json").write_text(json.dumps({
                "round": 1,
                "verdict": "accept",
                "pass_rule": "accepted",          # the older shape, and the whole point of the test
                "stop": "accepted",
                "dimensions": [{"name": "bar", "score": 1}],
                "passes": [],
                "cost": {"amount": 0.0, "source": "test"},
            }) + "\n")
            r = subprocess.run([sys.executable, str(EMIT), "--run", str(job / "round-01.json"),
                                "--out-dir", str(job), "--print-only"],
                               capture_output=True, text=True, timeout=120)
            both = (r.stdout or "") + (r.stderr or "")
            self.assertNotIn("Traceback", both, f"a malformed run must not crash the emitter:\n{both[-800:]}")
            self.assertNotEqual(r.returncode, 0, "a run the emitter cannot read must not emit a record")
            self.assertIn("pass_rule", both, f"the refusal must name the field: {both[-600:]}")


if __name__ == "__main__":
    unittest.main()
