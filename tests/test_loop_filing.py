#!/usr/bin/env python3
"""A finished loop() closes and files the job itself.

THE DEFECT THIS MEASURES. `dot-plumbline/jobs/` held two jobs on 2026-11-09 while roughly twenty-five had run,
because filing was a sentence in a commit message (`988c8ac`) and every dispatch wrote to `/tmp`. Four of the
twelve folders that were eventually backfilled could not say in themselves whether a record was even possible.
The seat that decides the terminal state is the seat that closes the job; running `close` afterwards is the same
defect one level down.

WHAT IS ASSERTED
- an accepted finish writes `custody/status.json` into the job folder, naming the record's sha256 and the state;
- with `PLUMBLINE_FILE_INTO` set, the folder lands under `<into>/jobs/<name>` and `summary.filing.filed` is true;
- with it unset, the status is still written and `summary.filing` says no destination was configured — never a
  silent skip;
- a finish with no record states `missing` and is refused by the filer rather than filed as complete.

The fixture packet is borrowed from the frozen custody bar so this test measures the filing, not loop()'s bounds.
"""
import json
import os
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from kit.conductor_loop import file_finish, loop  # noqa: E402
import kit.conductor_loop as cl  # noqa: E402
from test_loop_custody_on_finish import _job, _maker, _packet, _scores, _suite  # noqa: E402


def _emit(record_dir, summary):
    """Stand in for the emitter: write the record the real one would, and say clean."""
    os.makedirs(os.path.join(record_dir, "custody"), exist_ok=True)
    with open(os.path.join(record_dir, "custody", "record.custody.json"), "w") as fh:
        json.dump({"_type": "plumbline-test-record"}, fh)
    return 0


def _finish(tmp, into=None):
    """Run one accepted loop() and return (summary, record_dir).

    The emitter is mocked: this file measures the filing step, and the record's own bar is elsewhere in this
    suite. Everything after the emitter — the status file, the copy, the summary row — runs for real.
    """
    job = _job(tmp)
    packet = _packet(tmp, _maker(job), _suite(job))
    packet["bounds"].update({"cap": 1})
    record = TemporaryDirectory()   # loop() refuses a record_dir inside cwd
    _FINISH_DIRS.append(record)
    record_dir = record.name
    env = {"PLUMBLINE_FILE_INTO": into} if into else {}
    with mock.patch.object(cl, "emit_custody_for_finish", side_effect=_emit):
        with mock.patch.dict(os.environ, env, clear=False):
            if not into:
                os.environ.pop("PLUMBLINE_FILE_INTO", None)
            return loop(packet, record_dir=record_dir, cwd=tmp,
                        evaluator_fn=lambda record, cwd: _scores(1, verdict="accept")), record_dir


_FINISH_DIRS = []


class FinishFilesItself(unittest.TestCase):
    def test_a_finish_lands_in_the_instance_record_by_itself(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as repo:
            summary, record_dir = _finish(tmp, into=repo)
            filing = summary.get("filing") or {}
            self.assertTrue(filing.get("filed"), "loop() returned without filing the job: %r" % (filing,))
            # Owner A (2026-11-12): id-less finish -> runs/finish-<started_at>, not jobs/<scratch>.
            dest = str(filing.get("dest") or "")
            self.assertTrue(dest and os.path.isdir(dest), "no filed folder at %s (filing=%r)" % (dest, filing))
            self.assertTrue(
                os.path.abspath(dest).startswith(os.path.abspath(os.path.join(repo, "runs")) + os.sep),
                "id-less finish must land under runs/, got %r" % (dest,),
            )
            self.assertFalse(
                os.path.abspath(dest).startswith(os.path.abspath(os.path.join(repo, "jobs")) + os.sep),
                "id-less finish must not land under jobs/, got %r" % (dest,),
            )
            self.assertTrue(os.path.basename(dest).startswith("finish-"),
                            "Owner A: dest basename is finish-<started_at>, got %r" % (os.path.basename(dest),))
            self.assertTrue(os.path.isfile(os.path.join(dest, "custody", "status.json")),
                            "the filed folder states no custody status")
            status = json.load(open(os.path.join(dest, "custody", "status.json")))
            self.assertEqual(status["state"], "custody")
            self.assertEqual(status["terminal_state"], "accepted")
            self.assertEqual(len(status["record_sha256"]), 64)
            self.assertTrue(os.path.isfile(os.path.join(repo, "run-log.json")),
                            "filing wrote no run-log row")
            # The copy must be able to say how it was filed. Measured 2026-11-09: the folder was copied before
            # the row was written, so the filed summary carried `filing: null` while the live one carried it.
            filed_summary = json.load(open(os.path.join(dest, "summary.json")))
            self.assertTrue((filed_summary.get("filing") or {}).get("filed"),
                            "the filed copy cannot say how it was filed: %r" % (filed_summary.get("filing"),))

    def test_with_no_destination_the_status_is_still_written_and_says_why(self):
        with TemporaryDirectory() as tmp:
            summary, record_dir = _finish(tmp, into=None)
            filing = summary.get("filing") or {}
            self.assertFalse(filing.get("filed"), "filed without a configured destination: %r" % (filing,))
            self.assertIn("PLUMBLINE_FILE_INTO", filing.get("detail", ""))
            self.assertTrue(os.path.isfile(os.path.join(record_dir, "custody", "status.json")),
                            "the job folder says nothing about its own custody status")

    def test_a_finish_with_no_record_says_missing_and_is_not_filed_as_complete(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as repo:
            job = os.path.join(tmp, "2026-11-09-no-record")
            os.makedirs(job)
            json.dump({"job_id": "2026-11-09-no-record", "ratified": True, "terminal_state": "accepted"},
                      open(os.path.join(job, "packet.json"), "w"))
            with mock.patch.dict(os.environ, {"PLUMBLINE_FILE_INTO": repo}, clear=False):
                row = file_finish(job, {"terminal_state": "accepted"})
            self.assertEqual(row["state"], "missing")
            self.assertFalse(row["filed"], "a closed job with no record was filed as complete: %r" % (row,))
            self.assertIn("custody", row["detail"].lower())
            self.assertTrue(os.path.isfile(os.path.join(job, "custody", "status.json")))


class LoopWiring(unittest.TestCase):
    def test_loop_calls_the_filing_step_and_carries_its_row(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as repo:
            with mock.patch.object(cl, "file_finish", return_value={"state": "custody", "filed": True}) as called:
                summary, record_dir = _finish(tmp, into=repo)
            self.assertEqual(called.call_count, 1, "loop()'s finish path never called file_finish")
            self.assertEqual((called.call_args[0][0]), record_dir)
            self.assertIn("filing", summary, "the summary carries no filing row")
            self.assertTrue(json.load(open(os.path.join(record_dir, "summary.json")))["filing"]["filed"])


if __name__ == "__main__":
    unittest.main()
