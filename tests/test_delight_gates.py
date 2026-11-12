"""Delight gates: dual finish, hollow custody, preflight (2026-11-12 lessons)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from kit.delight import (
    attach_gates,
    hollow_reasons,
    instrument_gate,
    job_class_of,
    status_card_lines,
)
from kit.preflight import preflight


class DelightGatesTest(unittest.TestCase):
    def test_job_class_from_packet(self):
        self.assertEqual(job_class_of({"job_class": "docs_cut"}), "docs_cut")
        self.assertEqual(
            job_class_of({"x-plumbline": {"job_class": "full_release_record"}}),
            "full_release_record",
        )
        self.assertEqual(job_class_of({}), "unknown")

    def test_hollow_reasons_on_null_bar(self):
        rec = {
            "predicate": {
                "specVersion": "0.9.9",
                "bar": {"digest": None, "frozenAt": None, "author": None, "dimensions": []},
                "maker": {"name": None, "kind": None, "version": None},
                "instrument": {"rubric": None, "runner": None},
                "controls": [],
                "checks": [{"dimension": "00", "score": 1, "outcome": None}],
            }
        }
        reasons = hollow_reasons(rec)
        self.assertTrue(any("bar hollow" in r for r in reasons))
        self.assertTrue(any("maker hollow" in r for r in reasons))
        self.assertTrue(any("controls empty" in r for r in reasons))

    def test_attach_gates_instrument_only_hollow(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "custody"))
            rec = {
                "predicate": {
                    "specVersion": "0.9.9",
                    "bar": {},
                    "maker": {},
                    "instrument": {},
                    "controls": [],
                    "checks": [],
                }
            }
            path = os.path.join(td, "custody", "record.custody.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(rec, fh)
            halt = {
                "stop": "accepted",
                "terminal_state": "accepted",
                "outcome": "accepted",
                "packet_sha256": "abc",
                "cost": 0.1,
            }
            out = attach_gates(halt, td, {"job_class": "docs_cut"})
            self.assertEqual(out["instrument_gate"], "pass")
            self.assertEqual(out["custody_gate"], "hollow")
            self.assertEqual(out["finish_kind"], "instrument_only_hollow_custody")
            self.assertEqual(out["job_class"], "docs_cut")
            # doctrine terminal unchanged
            self.assertEqual(out["terminal_state"], "accepted")

    def test_instrument_gate_needs_owner(self):
        self.assertEqual(
            instrument_gate({"stop": "no artifact", "terminal_state": "needs_owner"}),
            "fail",
        )

    def test_status_card_no_tables(self):
        text = status_card_lines(
            job_id="j1",
            instrument_gate="pass",
            custody_gate="hollow",
            next_human="do not merge",
        )
        self.assertIn("instrument_gate: pass", text)
        self.assertIn("custody_gate: hollow", text)
        self.assertNotIn("|", text)

    def test_preflight_blocks_unratified(self):
        with tempfile.TemporaryDirectory() as td:
            r = preflight({"ratified": False, "job_class": "docs_cut"}, td)
            self.assertFalse(r["ok"])
            self.assertTrue(any("ratified" in b for b in r["blocking"]))

    def test_preflight_warns_full_release_budget(self):
        with tempfile.TemporaryDirectory() as td:
            # minimal SPEC so full_release does not block on missing SPEC
            with open(os.path.join(td, "SPEC.md"), "w", encoding="utf-8") as fh:
                fh.write("# x\n\n**Version 0.9.9 · candidate · 2026-11-12**\n")
            r = preflight(
                {
                    "ratified": True,
                    "job_class": "full_release_record",
                    "bounds": {"budget": {"amount": 0.3, "unit": "USD"}},
                },
                td,
                custody_tree=td,
            )
            self.assertTrue(r["ok"])
            self.assertTrue(any("floor" in w for w in r["warnings"]))


if __name__ == "__main__":
    unittest.main()
