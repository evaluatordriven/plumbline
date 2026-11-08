"""Bar: no CL1 approval or disposition time in the packet that is not stamped by the ledger.

Owner ruling, binding this job:
  "no approval time without the act that stamps it."

A CL1 custody record needs:
  - bar.approvals[].at — the moment the Buyer or Specialist approved the bar.
  - disposition.at    — the moment the Owner/human seat disposed of the record.

Both times come from a live custody_ledger.py event:
  - `custody_ledger.py approve --role buyer|specialist` writes `at` when the approval happens.
  - `custody_ledger.py dispose --by "..."` writes `at` when the disposition happens.

The packet is written BEFORE those acts.  Therefore the packet may describe an approval
(role, by, optional barDigest) and a disposition (by, state), but it must not carry a
literal `at`.  A typed `at` is a hand time, and the only source that can time it is the
ledger that has not happened yet.

Where the check lives:
  - kit/emit_packet.py, in the CL1 source gate.  This is the last place a typed time can
    be stopped before it becomes part of the job's terms.
  - custody_ledger.py already stamps `at` when it runs; it is the act, not a second checker.
  - kit/emit_custody.py (via custody_history.py) already refuses hand times downstream;
    this gate is the upstream backstop.

Rubric:
  Dimension:  untimeable time fields in a CL1 packet (bar.approvals[].at and disposition.at)
  Scale:      count of such fields present in the packet
  Threshold:  0 — any typed time refuses the packet

Failing cases:
  - A CL1 packet whose bar.approvals[0].at is a literal RFC 3339 UTC string.
  - A CL1 packet whose disposition.at is a literal RFC 3339 UTC string.

Passing cases:
  - A CL1 approval with role and by but no at (the ledger will stamp it later).
  - A CL1 disposition with by and state but no at (the ledger will stamp it later).
  - A baseline packet is not held to this bar, even if it carries literal times.

The ledger-stamped fixture is represented by an approval or disposition that leaves the
`at` field absent from the packet; the real time arrives from inputs/custody-events.jsonl.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

from kit.emit_packet import cl1_source_gaps  # noqa: E402


def _min_valid_cl1() -> dict:
    """A CL1 packet whose approvals and disposition leave the time for the ledger."""
    return {
        "job_id": "cl1-time-source",
        "job_name": "Valid CL1 packet (time left to ledger)",
        "entry": "A",
        "instrument_profile": "full",
        "mode": "scored",
        "ratified": True,
        "artifact": {"repo": "x", "paths": []},
        "buyer": "Fixture Buyer",
        "specialist": "Fixture Specialist",
        "human_seat": "Fixture Owner",
        "maker": {"name": "Fixture Maker"},
        "evaluator": {"name": "Fixture Evaluator", "kind": "model"},
        "standard_ref": {"doc": "x", "version": "v1"},
        "mandate_ref": {"doc": "EDI-MANDATE.md", "version": "a48a4645"},
        "bounds": {
            "T_accept": 1,
            "T_dim": 1,
            "T_reject": 0,
            "cap": 3,
            "budget": {"amount": 10, "unit": "USD"},
        },
        "k": 3,
        "x": 10,
        "ground_truth": [{"source": "x", "version": "v1", "hardness": "INVARIANT"}],
        "escalation": {"route": "Owner"},
        "constitution_ref": "dot-plumbline/constitution.json",
        "constitution_version": "0.1.0",
        "proposed": {
            "level_claimed_for_own_record": "CL1",
            "drafted_by": "Fixture Architect",
        },
        "bar": {
            "approvals": [
                {"role": "buyer", "by": "Fixture Buyer", "barDigest": "a" * 64},
                {"role": "specialist", "by": "Fixture Specialist", "barDigest": "a" * 64},
            ]
        },
        "controls": [
            {"id": "K1", "batch": "b1", "evaluator": "eval-a", "expected": "conforms"},
            {"id": "K2", "batch": "b1", "evaluator": "eval-a", "expected": "does_not_conform"},
        ],
        "disposition": {"state": "not_yet_given", "by": "Fixture Owner"},
    }


class TestPacketCL1TimeSource(unittest.TestCase):
    """CL1 packets must leave approval and disposition times to the ledger."""

    def _reasons(self, packet: dict) -> str:
        return " ".join(cl1_source_gaps(packet)).lower()

    def test_cl1_typed_approval_at_is_refused(self):
        """A hand-typed bar.approvals[].at has no ledger act behind it."""
        packet = _min_valid_cl1()
        packet["bar"]["approvals"][0]["at"] = "2026-11-08T02:00:00Z"
        reasons = self._reasons(packet)
        self.assertIn("bar.approvals[0].at", reasons)
        self.assertIn("stamped", reasons.lower())

    def test_cl1_typed_disposition_at_is_refused(self):
        """A hand-typed disposition.at has no dispose act behind it."""
        packet = _min_valid_cl1()
        packet["disposition"]["at"] = "2026-11-08T02:00:00Z"
        reasons = self._reasons(packet)
        self.assertIn("disposition.at", reasons)

    def test_cl1_approval_without_at_passes(self):
        """The ledger-stamped shape: time absent in the packet, to be stamped by approve."""
        packet = _min_valid_cl1()
        reasons = self._reasons(packet)
        self.assertNotIn("bar.approvals[0].at", reasons)
        self.assertNotIn("bar.approvals[1].at", reasons)

    def test_cl1_disposition_without_at_passes(self):
        """The ledger-stamped shape: time absent in the packet, to be stamped by dispose."""
        packet = _min_valid_cl1()
        reasons = self._reasons(packet)
        self.assertNotIn("disposition.at", reasons)

    def test_baseline_level_ignores_typed_times(self):
        """A baseline claim is not CL1, so this gate does not apply."""
        packet = _min_valid_cl1()
        packet["proposed"]["level_claimed_for_own_record"] = "baseline"
        packet["bar"]["approvals"][0]["at"] = "2026-11-08T02:00:00Z"
        packet["disposition"]["at"] = "2026-11-08T02:00:00Z"
        gaps = cl1_source_gaps(packet)
        self.assertEqual(gaps, [])

    def test_custody_ledger_approve_stamps_its_own_time(self):
        """The ledger-stamped fixture: approve ignores any typed at and writes the tool clock.

        This proves the source-of-truth path the packet must defer to.
        """
        with tempfile.TemporaryDirectory() as td:
            job = Path(td)
            (job / "inputs").mkdir(parents=True, exist_ok=True)
            bar = job / "custody" / "bar.md"
            bar.parent.mkdir(parents=True, exist_ok=True)
            bar.write_text("# bar\n", encoding="utf-8")
            custody = {
                "custody_inputs": "plumbline/custody-inputs/v1",
                "orchestrator": {"name": "Fixture Orchestrator", "kind": "agent"},
                "bar": {"file": "custody/bar.md"},
            }
            (job / "inputs" / "custody.json").write_text(json.dumps(custody, indent=2), encoding="utf-8")

            before_freeze = subprocess.run(
                [sys.executable, str(REPO / "kit" / "custody_ledger.py"), "approve",
                 "--job-dir", str(job), "--role", "buyer", "--by", "Fixture Buyer"],
                capture_output=True, text=True,
            )
            self.assertEqual(before_freeze.returncode, 2, "approve before freeze must be refused")

            freeze = subprocess.run(
                [sys.executable, str(REPO / "kit" / "custody_ledger.py"), "freeze",
                 "--job-dir", str(job), "--bar", "custody/bar.md"],
                capture_output=True, text=True,
            )
            self.assertEqual(freeze.returncode, 0, freeze.stderr)

            approve = subprocess.run(
                [sys.executable, str(REPO / "kit" / "custody_ledger.py"), "approve",
                 "--job-dir", str(job), "--role", "buyer", "--by", "Fixture Buyer"],
                capture_output=True, text=True,
            )
            self.assertEqual(approve.returncode, 0, approve.stderr)
            events = (job / "inputs" / "custody-events.jsonl").read_text(encoding="utf-8").strip().splitlines()
            approve_event = next((json.loads(e) for e in events if json.loads(e).get("event") == "approve"), {})
            self.assertIn("at", approve_event)
            self.assertRegex(approve_event["at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


if __name__ == "__main__":
    unittest.main()
