"""Bar: a packet that claims a CL1 custody record must carry its sources.

Architect ruling, binding this job:

A packet is a job's terms.  A CL1 custody record needs:
  - bar.approvals from the Buyer and Specialist (each names who approved),
  - controls from the Evaluator (at least one expecting conforms and one expecting does_not_conform),
  - disposition.by from the Owner/human seat (the person named as the source of the disposition act).

When level_claimed_for_own_record is "CL1", these facts must be present in the packet at open.
If they are absent, the packet emitter must refuse and the owner of the defect is the packet template,
not the run that later tries to source them.

Seat that writes each field:
  - bar.approvals: Orchestrator, from the Owner/Buyer/Specialist approve events.
  - controls:       Orchestrator, from the Specialist's bar and the Evaluator's batch plan.
  - disposition.by: Orchestrator, from the packet's human_seat / named owner disposition source.

A packet whose level claim is baseline (no CL1 claim) is not held to this bar.

disposition.by: the custody/v1 predicate requires it (state, by, at, acknowledgesUnobserved).
For a CL1 record its absence is never correct, even when disposition_state is "not_yet_given";
in that case the record carries state "not_yet_given" with by naming the approver.  An accepted
job with no disposition act is therefore recorded as accepted with state="not_yet_given", not as
a missing field.

The red bar here is the missing implementation of cl1_source_gaps() (or an equivalent
packet-level CL1 gate) in kit/emit_packet.py.  The existing emit_packet.refusals() does not
read these three CL1 source requirements, and the existing schema does not require them.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))

# Red bar: the function that gates CL1 source shape does not exist yet.
from kit.emit_packet import cl1_source_gaps  # noqa: E402

EXAMPLE_PACKET = REPO / "examples" / "2026-10-27-custody-emitter-gaps" / "packet.json"


def _load_example() -> dict:
    if not EXAMPLE_PACKET.is_file():
        raise FileNotFoundError(f"example packet missing: {EXAMPLE_PACKET}")
    return json.loads(EXAMPLE_PACKET.read_text())


def _min_valid_cl1() -> dict:
    """A packet carrying the three CL1 source fields correctly."""
    return {
        "job_id": "cl1-valid",
        "job_name": "Valid CL1 packet",
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
                {"role": "buyer", "by": "Fixture Buyer"},
                {"role": "specialist", "by": "Fixture Specialist"},
            ]
        },
        "controls": [
            {"id": "K1", "batch": "b1", "evaluator": "eval-a", "expected": "conforms"},
            {"id": "K2", "batch": "b1", "evaluator": "eval-a", "expected": "does_not_conform"},
        ],
        "disposition": {"state": "not_yet_given", "by": "Fixture Owner"},
    }


class TestPacketCL1Sources(unittest.TestCase):
    """CL1 packets must source controls, approvals, and disposition.by."""

    def test_example_packet_missing_all_three(self):
        """The 2026-10-27 custody-emitter-gaps packet claimed CL1 and sourced none of the three."""
        packet = _load_example()
        self.assertEqual(
            packet.get("proposed", {}).get("level_claimed_for_own_record"),
            "CL1",
            "precondition: this fixture must claim CL1",
        )
        gaps = cl1_source_gaps(packet)
        reasons = " ".join(gaps).lower()
        self.assertIn("bar.approvals", reasons)
        self.assertIn("controls", reasons)
        self.assertIn("disposition.by", reasons)

    def test_cl1_requires_buyer_and_specialist_approvals(self):
        packet = _min_valid_cl1()
        packet["bar"]["approvals"] = [{"role": "specialist", "by": "Fixture Specialist"}]
        gaps = cl1_source_gaps(packet)
        reasons = " ".join(gaps).lower()
        self.assertIn("buyer", reasons)

    def test_cl1_controls_need_conforms_and_does_not_conform(self):
        packet = _min_valid_cl1()
        packet["controls"] = [
            {"id": "K1", "batch": "b1", "evaluator": "eval-a", "expected": "conforms"},
        ]
        gaps = cl1_source_gaps(packet)
        reasons = " ".join(gaps).lower()
        self.assertIn("does_not_conform", reasons)

    def test_cl1_requires_disposition_by(self):
        packet = _min_valid_cl1()
        packet["disposition"] = {"state": "not_yet_given"}
        gaps = cl1_source_gaps(packet)
        reasons = " ".join(gaps).lower()
        self.assertIn("disposition.by", reasons)

    def test_baseline_level_does_not_require_cl1_sources(self):
        packet = _min_valid_cl1()
        packet["proposed"]["level_claimed_for_own_record"] = "baseline"
        packet.pop("bar", None)
        packet.pop("controls", None)
        packet.pop("disposition", None)
        gaps = cl1_source_gaps(packet)
        self.assertEqual(gaps, [])

    def test_valid_cl1_packet_has_no_gaps(self):
        packet = _min_valid_cl1()
        gaps = cl1_source_gaps(packet)
        self.assertEqual(gaps, [])


if __name__ == "__main__":
    unittest.main()
