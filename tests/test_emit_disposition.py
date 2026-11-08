#!/usr/bin/env python3
"""Bar: the custody emitter must read packet.disposition_state on a loop finish.

The defect, measured. `kit/emit_custody.py` routes finish-shaped jobs (`packet` carries
a `finish` object or the job wrote `round-NN.json` records) through `build_finish()`.
`build()` reads `packet["disposition_state"]` and cross-checks the live `dispose` event
in `inputs/custody-events.jsonl`. `build_finish()` hard-codes the disposition to
`{state: null, by: null, at: null}` and never reads the packet's value.

These tests are the bar. Do not edit them to make them pass. A correct fix lives in
`kit/emit_custody.py` (almost certainly `build_finish()`), not in these tests and not in
any hand-edited record.

What these fixtures cannot show: a non-finish job (`build()` without `build_finish()`)
is not exercised here. The bar asserts through `build()` on finish-shaped fixtures, so
`build_finish()` is the path under test. The tests also cannot prove that `--allow-hand-times`
interacts cleanly with a loop-finish disposition; the disposition time must come from the
ledger event, not from a hand-entered time, and the fixtures keep the ledger event clean.
"""
from __future__ import annotations
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "kit"))
import emit_custody as EC  # noqa: E402
import custody_history as H  # noqa: E402

PY = sys.executable
STARTED_AT = "2026-11-06T18:20:40Z"
PRODUCED_AT = "2026-11-06T18:30:21Z"
DISPOSITION_AT = "2026-11-08T19:30:15Z"
APPROVER = "Steve Moitozo II"
REAL_FINISH_JOB = Path("/home/jarbis1/tmp/plumbline-escalate-record")


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _packet(disposition_state: str = "given") -> dict:
    return {
        "job_id": "test-disposition",
        "terminal_state": "accepted",
        "outcome": "accepted",
        "stop": "accepted",
        "disposition_state": disposition_state,
        "started_at": STARTED_AT,
        "ended_at": PRODUCED_AT,
    }


def _finish_block(disposition_state: str = "given") -> dict:
    return {
        "terminal_state": "accepted",
        "outcome": "accepted",
        "stop": "accepted",
        "started_at": STARTED_AT,
        "ended_at": PRODUCED_AT,
    }


def _round_record() -> dict:
    return {
        "ended_at": PRODUCED_AT,
        "pass_rule": None,
        "stop": "accepted",
        "reading": {
            "verdict": "accept",
            "dimensions": [{"name": "q", "score": 1.0, "observation": "seen"}],
            "violations": [],
        },
        "evaluator": [],
    }


def _ledger(event_state: str | None = None) -> str:
    if event_state is None:
        return ""
    line = {
        "event": "dispose",
        "by": APPROVER,
        "at": DISPOSITION_AT,
        "state": event_state,
        "writer": "kit/custody_ledger.py@cb22c1a89266",
    }
    return json.dumps(line) + "\n"


def _build_job(tmp: Path, disposition_state: str = "given", ledger_state: str | None = "given") -> Path:
    """A loop-finish job: packet, one round record, one editable file, and a ledger event."""
    packet = _packet(disposition_state)
    packet["finish"] = _finish_block(disposition_state)
    _write(tmp / "packet.json", json.dumps(packet, indent=2))
    _write(tmp / "round-01.json", json.dumps(_round_record(), indent=2))
    _write(tmp / "round-01" / "editable" / "src.txt", "artifact\n")
    _write(tmp / EC.LEDGER_REL, _ledger(ledger_state))
    return tmp


def _disposition(record: dict) -> dict:
    return record["predicate"]["disposition"]


def _patch_revision():
    """The emitter's git-dirty check is not under test here."""
    return mock.patch.object(
        EC.H, "revision",
        return_value={
            "commit": "1234567890abcdef1234567890abcdef12345678",
            "tree": "abcdef1234567890abcdef1234567890abcdef12",
            "dirty": False,
            "stated": None,
        },
    )


class DispositionOnFinishTests(unittest.TestCase):
    def _now(self) -> datetime:
        return datetime(2026, 11, 9, 0, 0, 0, tzinfo=timezone.utc)

    def _record(self, job: Path) -> tuple[dict, EC.Gaps, H.Refusals]:
        ref = H.Refusals()
        inputs = job / "inputs" / "custody.json"
        with _patch_revision():
            record, gaps, _ = EC.build(job, inputs, ref=ref, now=self._now())
        return record, gaps, ref

    def test_packet_given_plus_ledger_given_makes_record_given(self):
        with TemporaryDirectory() as td:
            job = _build_job(Path(td), "given", "given")
            record, gaps, ref = self._record(job)
        disp = _disposition(record)
        self.assertFalse(ref, "a matching ledger event must not be refused")
        self.assertEqual(disp["state"], "given")
        self.assertEqual(disp["by"], APPROVER)
        self.assertEqual(disp["at"], DISPOSITION_AT)

    def test_packet_declined_plus_ledger_declined_makes_record_declined(self):
        with TemporaryDirectory() as td:
            job = _build_job(Path(td), "declined", "declined")
            record, gaps, ref = self._record(job)
        disp = _disposition(record)
        self.assertFalse(ref, "a matching ledger event must not be refused")
        self.assertEqual(disp["state"], "declined")

    def test_packet_not_yet_given_stays_not_yet_given_and_has_no_time(self):
        with TemporaryDirectory() as td:
            job = _build_job(Path(td), "not_yet_given", None)
            # remove any ledger line that may have been written by the helper
            job.joinpath(EC.LEDGER_REL).write_text("")
            record, gaps, ref = self._record(job)
        disp = _disposition(record)
        self.assertFalse(ref, "no ledger event means no contradiction to refuse")
        self.assertEqual(disp["state"], "not_yet_given")
        self.assertIsNone(disp["by"])
        self.assertIsNone(disp["at"])
        # The emitter must not invent a time for a disposition that was never given.
        self.assertNotEqual(disp["at"], H.iso(self._now()))

    def test_packet_given_but_ledger_declined_is_refused(self):
        with TemporaryDirectory() as td:
            job = _build_job(Path(td), "given", "declined")
            record, gaps, ref = self._record(job)
        self.assertTrue(ref, "the packet and ledger must agree on disposition.state")
        message = " ".join(kind + ": " + msg for kind, msg in ref.rows)
        self.assertIn("disposition", message.lower())

    def test_packet_declined_but_ledger_given_is_refused(self):
        with TemporaryDirectory() as td:
            job = _build_job(Path(td), "declined", "given")
            record, gaps, ref = self._record(job)
        self.assertTrue(ref, "the packet and ledger must agree on disposition.state")

    def test_real_pr_record_re_emitted_carries_owner_given(self):
        self.assertTrue(
            (REAL_FINISH_JOB / "packet.json").is_file(),
            f"fixture not found: {REAL_FINISH_JOB / 'packet.json'}",
        )
        self.assertTrue(
            (REAL_FINISH_JOB / EC.LEDGER_REL).is_file(),
            f"fixture not found: {REAL_FINISH_JOB / EC.LEDGER_REL}",
        )
        inputs = REAL_FINISH_JOB / "inputs" / "custody.json"
        ref = H.Refusals()
        with _patch_revision():
            record, gaps, _ = EC.build(REAL_FINISH_JOB, inputs, ref=ref, now=self._now())
        disp = _disposition(record)
        self.assertFalse(ref, "the PR record must re-emit without refusal")
        self.assertEqual(disp["state"], "given")
        self.assertEqual(disp["by"], APPROVER)
        self.assertEqual(disp["at"], DISPOSITION_AT)


if __name__ == "__main__":
    unittest.main()
