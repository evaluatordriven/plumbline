"""A control's cited evidence, re-hashed.

The custody checker cannot do this: a control's evidence citation lives under `x-plumbline`, and SPEC §4 says
`x-` keys are not read by any requirement. So the only layer that can hold an emitter to what it cited is
this one. Measured 2026-11-10: corrupting every control's cited digest in a published record changed no
requirement at all - `OK`, `CL1` - because nothing on either side re-hashed it.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kit"))
import plumbline_verify as V  # noqa: E402


def _record(name: str, digest: str) -> dict:
    return {"predicate": {"controls": [
        {"id": "K1", "batch": "B1", "evaluator": "E1", "case": {"sha256": "a" * 64},
         "expected": "conforms", "outcome": "conforms",
         "x-plumbline": {"evidence": {"name": name, "sha256": digest}}}]}}


class ControlEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.job = self.tmp / "job"
        self.ev = self.job / "custody" / "evidence"
        self.ev.mkdir(parents=True)
        self.file = self.ev / "s1--summary.json"
        self.file.write_text(json.dumps({"verdict": "CONFORMS"}), encoding="utf-8")
        self.good = hashlib.sha256(self.file.read_bytes()).hexdigest()

    def test_a_matching_digest_passes(self):
        self.assertEqual(V.check_control_evidence(_record("custody/evidence/s1--summary.json", self.good),
                                                self.job, self.ev), [])

    def test_a_wrong_digest_is_a_failure(self):
        bad = "b" * 64
        f = V.check_control_evidence(_record("custody/evidence/s1--summary.json", bad), self.job, self.ev)
        self.assertEqual(len(f), 1, f)
        self.assertEqual(f[0]["field"], "controls[0].evidence")
        self.assertIn(bad, f[0]["message"])

    def test_a_missing_file_is_a_failure_not_a_skip(self):
        f = V.check_control_evidence(_record("custody/evidence/gone.json", "c" * 64), self.job, self.ev)
        self.assertEqual(len(f), 1, f)
        self.assertIn("not in the job", f[0]["message"])

    def test_no_citation_is_not_a_failure(self):
        rec = {"predicate": {"controls": [{"id": "K1", "batch": "B1", "evaluator": "E1",
                                           "case": {"sha256": "a" * 64},
                                           "expected": "conforms", "outcome": "conforms"}]}}
        self.assertEqual(V.check_control_evidence(rec, self.job, self.ev), [])


if __name__ == "__main__":
    unittest.main()
