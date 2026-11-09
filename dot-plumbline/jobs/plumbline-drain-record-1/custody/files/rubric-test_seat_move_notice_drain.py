"""Bar: seat-move notices are drained at conductor turn start and consumed only on success.

Source:
  /home/jarbis1/plumbline-hermes-seat-architecture.md section 15, lines 618-624.
  Follow-up to tests/test_seat_move_notice.py (job 5).  Job 5 proved durable
  enqueue and FIFO drain from a side process; it did not prove that a real
  conductor Bot Chat turn sees the notice, or that the notice survives a failed
  turn.  This bar is that missing hop.

Mechanism choice and why
========================
The Owner offered two candidates.  (a) is a conductor-profile ``pre_llm_call``
plugin hook.  That hook can inject context (``agent/turn_context.py:682-736``
shows the host collecting ``{"context": "..."}`` returned by ``pre_llm_call``
and appending it to the user message).  But it is the wrong choice here for
three reasons:

1. Turn boundary.  The canonical ``pre_llm_call`` payload
   (``hermes_cli/hooks.py:116-120``) gives ``session_id`` but no ``turn_id``.
   ``pre_llm_call`` fires once per LLM call, not once per user turn; a turn
   that calls the LLM, runs tools, and calls the LLM again will fire the hook
   twice.  With no stable turn identifier passed by the host, a plugin cannot
   safely stage notices once per turn, and a naive hook would either drain
   twice (duplicate announcement) or consume on the first call (leaving no
   recovery if the turn later fails).

2. Consume-after-success.  ``post_llm_call`` also fires per LLM call
   (``hermes_cli/hooks.py:120``), not once per successful turn.  There is no
   host hook that signals "the whole turn completed successfully".  A plugin
   could track state in memory, but memory state is lost on crash.

3. Testability.  Proving the plugin hook fires at the right LLM-call boundary
   requires either a live Hermes turn or a host-mocked harness that reproduces
   the exact dispatch.  That makes the bar expensive and slow.

I therefore choose mechanism (b): a step in the conductor's turn launcher
BEFORE the turn logic runs.  The launcher defines the turn boundary: it
stages waiting notices from the Plumbline mailbox into an in-flight
 directory, passes the formatted text into the turn, and only deletes the
in-flight files if the turn completes without raising.  If the turn crashes,
the in-flight files remain on disk; the next launcher run recovers them back
to the mailbox before staging again.  The "consume only after success" mark is
the absence of the in-flight directory; while it exists, the notice is still
queued for retry.

This design keeps the durable handoff inside ``kit/seat_move_notice``'s private
mailbox; it never writes the conductor's Hermes session from outside; and it
requires no engine hook.

What mechanism (b) must prevent
---------------------------------
- The launcher must not remove notices from the mailbox before the turn
  succeeds.  If it drained and then crashed, notices would be lost.
- The launcher must not pass notices into a turn that never runs.  The safe
  form stages, runs the turn, and consumes only on clean completion.  If the
  turn never runs, staged files stay and are recovered next turn.

Scale and threshold
===================
Binary per dimension: 1 = the check PASSes, 0 = it does not.
T_accept = 1, T_dim = 1, T_reject = 0.  Every dimension must PASS.
Any FAIL before implementation exists is the red bar.

Dimensions
==========
D1. ``kit/seat_move_drain.py`` exists and exports a callable
    ``prepare_turn`` that takes a conductor profile home, recovers any
    in-flight notices from prior failed turns to the mailbox, drains the
    mailbox into an in-flight directory, and returns both the notice payloads
    and a formatted context string suitable for the Bot Chat.
D2. A failed turn leaves the notice queued.  If ``prepare_turn`` is called but
    ``consume_turn`` (or the equivalent success marker) is not called before a
    later ``prepare_turn``, the notice is announced in the later turn exactly
    once and is then consumed.
D3. An empty mailbox yields an empty context string and costs nothing: no
    files are written to the in-flight directory and the mailbox stays empty.
D4. Two notices are drained in FIFO order, announced together, and consumed
    on successful completion.
D5. A notice queued under a different profile's mailbox is not drained by the
    conductor turn; only the conductor profile's own mailbox is read.
D6. Fail-closed: a corrupt mailbox file causes ``prepare_turn`` to raise rather
    than silently dropping the notice or announcing garbage.
D7. The deployment record documents the consume-after-success mechanism and
    the live Bot Chat verification path, so the Owner knows how to confirm the
    notice is rendered in session ``20261106_173554_a10444`` title "Bot Chat".

What fixtures can and cannot show
=================================
D1-D6 can be exercised against a temporary profile home and an in-memory or
filesystem mailbox without any live Hermes session.  The tests below do exactly
that.

D7 is the live acceptance step the Owner performs: enqueue one real notice
into ``~/.hermes/profiles/plumbline-conductor/runtime/plumbline-seat-notices/``,
start a real conductor Bot Chat turn, and observe the notice text in an
assistant message in ``~/.hermes/profiles/plumbline-conductor/state.db`` session
``20261106_173554_a10444``.  The fixture tests cannot write to the session, so
they verify instead that the deployment record names this verification step
and the expected session coordinates.  The live check itself is left to the
Owner's acceptance run.
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import shutil
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

DEPLOY_DIR = os.path.join(REPO, "deployment", "plumbline-conductor")
DEPLOY_RECORD = os.path.join(DEPLOY_DIR, "seat-move-turn.md")
DEPLOY_SCRIPT = os.path.join(DEPLOY_DIR, "seat-move-turn.py")


def _mailbox_dir(profile_home: pathlib.Path) -> pathlib.Path:
    return profile_home / "runtime" / "plumbline-seat-notices"


def _inflight_dir(profile_home: pathlib.Path) -> pathlib.Path:
    return _mailbox_dir(profile_home) / "inflight"


class TestSeatMoveNoticeDrain(unittest.TestCase):

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="seatdrain-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile_home = self.tmp / "plumbline-conductor"
        self.env = {"PLUMBLINE_SEAT_NOTICE": "1"}

    def _mod(self):
        return importlib.import_module("kit.seat_move_drain")

    def _send(self, *, direction: str, seat: str, job_id: str, profile_home: pathlib.Path | None = None):
        smn = importlib.import_module("kit.seat_move_notice")
        return smn.send_notice(
            direction=direction,
            seat=seat,
            job_id=job_id,
            profile_home=str(profile_home or self.profile_home),
            env=self.env,
        )

    def test_d1_prepare_turn_returns_context(self):
        """D1: a queued notice appears in the next turn's context."""
        mod = self._mod()
        notice_id = self._send(direction="to_seat", seat="plumbline-eval", job_id="job-6-d1")
        self.assertIsNotNone(notice_id)

        notices, context = mod.prepare_turn(profile_home=str(self.profile_home), env=self.env)
        self.assertEqual(len(notices), 1, "exactly one notice must be staged")
        self.assertEqual(notices[0]["notice_id"], notice_id)
        self.assertEqual(notices[0]["direction"], "to_seat")
        self.assertEqual(notices[0]["seat"], "plumbline-eval")
        self.assertIn(notice_id, context, "the returned context must contain the notice id")
        self.assertIn("plumbline-eval", context, "the returned context must contain the seat name")
        # After staging, the mailbox is empty but the notice is recoverable.
        self.assertFalse(list(_mailbox_dir(self.profile_home).glob("*.json")))
        self.assertTrue(list(_inflight_dir(self.profile_home).glob("*.json")))

    def test_d2_failed_turn_leaves_notice_queued_no_duplicate(self):
        """D2: a failed turn leaves the notice queued; retry announces exactly once.

        Simulates failure by staging the notice and never calling the success
        marker, then calling prepare_turn again as the retry.  The retry must
        recover the in-flight notice before draining, so the same notice is
        announced once in the retry and once consumed.
        """
        mod = self._mod()
        notice_id = self._send(direction="from_seat", seat="plumbline-maker", job_id="job-6-d2")

        notices1, context1 = mod.prepare_turn(profile_home=str(self.profile_home), env=self.env)
        self.assertEqual(len(notices1), 1)
        self.assertEqual(notices1[0]["notice_id"], notice_id)

        # Turn fails: consume_turn is NOT called.  Staged files must remain.
        staged1 = list(_inflight_dir(self.profile_home).glob("*.json"))
        self.assertEqual(len(staged1), 1, "in-flight notice must survive a failed turn")

        # Retry turn starts.  It recovers the in-flight notice into the mailbox,
        # drains it, and stages under the new turn.
        notices2, context2 = mod.prepare_turn(profile_home=str(self.profile_home), env=self.env)
        self.assertEqual(len(notices2), 1, "retry must announce exactly one notice")
        self.assertEqual(notices2[0]["notice_id"], notice_id)
        self.assertEqual(context1.count(notice_id), 1, "first turn must announce the notice once")
        self.assertEqual(context2.count(notice_id), 1, "retry must announce the recovered notice once")

        # Now the retry succeeds.
        mod.consume_turn(profile_home=str(self.profile_home), env=self.env)
        self.assertFalse(list(_mailbox_dir(self.profile_home).glob("*.json")))
        self.assertFalse(list(_inflight_dir(self.profile_home).glob("*.json")))

    def test_d3_empty_mailbox_changes_nothing(self):
        """D3: an empty mailbox yields empty context and costs nothing."""
        mod = self._mod()
        notices, context = mod.prepare_turn(profile_home=str(self.profile_home), env=self.env)
        self.assertEqual(notices, [])
        self.assertEqual(context, "")
        self.assertFalse(list(_mailbox_dir(self.profile_home).glob("*.json")))
        self.assertFalse(list(_inflight_dir(self.profile_home).glob("*.json")))

    def test_d4_multiple_notices_fifo(self):
        """D4: two notices drain FIFO, are announced together, and consumed on success."""
        mod = self._mod()
        ids = [
            self._send(direction="to_seat", seat="plumbline-eval", job_id="job-6-d4-first"),
            self._send(direction="from_seat", seat="plumbline-maker", job_id="job-6-d4-second"),
        ]
        self.assertEqual(len(ids), 2)
        # Tiny timing gap to ensure FIFO order is intentional, not accident.
        time.sleep(0.01)

        notices, context = mod.prepare_turn(profile_home=str(self.profile_home), env=self.env)
        self.assertEqual(len(notices), 2)
        for idx, nid in enumerate(ids):
            self.assertEqual(notices[idx]["notice_id"], nid)
            self.assertIn(nid, context)

        mod.consume_turn(profile_home=str(self.profile_home), env=self.env)
        self.assertFalse(list(_mailbox_dir(self.profile_home).glob("*.json")))
        self.assertFalse(list(_inflight_dir(self.profile_home).glob("*.json")))

    def test_d5_different_profile_not_drained(self):
        """D5: a notice queued for a different profile is left untouched."""
        mod = self._mod()
        other_home = self.tmp / "plumbline-eval"
        self._send(
            direction="to_seat",
            seat="plumbline-conductor",
            job_id="job-6-d5-other",
            profile_home=other_home,
        )

        # Conductor turn starts with empty conductor mailbox.
        notices, context = mod.prepare_turn(profile_home=str(self.profile_home), env=self.env)
        self.assertEqual(notices, [])
        self.assertEqual(context, "")

        # The other profile's notice is still in its mailbox.
        other_files = list(_mailbox_dir(other_home).glob("*.json"))
        self.assertEqual(len(other_files), 1, "other profile's notice must not be drained")

    def test_d6_corrupt_mailbox_raises(self):
        """D6: a corrupt mailbox file causes prepare_turn to raise, not drop."""
        mod = self._mod()
        mailbox = _mailbox_dir(self.profile_home)
        mailbox.mkdir(parents=True, exist_ok=True)
        corrupt = mailbox / "00000000000000000001-bad.json"
        corrupt.write_text("not valid json", encoding="utf-8")

        with self.assertRaises((json.JSONDecodeError, OSError)):
            mod.prepare_turn(profile_home=str(self.profile_home), env=self.env)

        # The corrupt file must still be present so a human can inspect it.
        self.assertTrue(corrupt.exists())

    def test_d7_deployment_record_documents_live_verification(self):
        """D7: the deployment record documents consume-after-success and the Bot Chat check.

        This fixture cannot prove the live Bot Chat renders the notice, so the
        test checks that the record carried by the repo names the mechanism and
        the exact session coordinates the Owner will verify.
        """
        self.assertTrue(
            os.path.isfile(DEPLOY_RECORD),
            f"deployment record missing: {DEPLOY_RECORD}",
        )
        src = pathlib.Path(DEPLOY_RECORD).read_text(encoding="utf-8")
        self.assertIn("inflight", src.lower(), "must record the in-flight / staged directory")
        self.assertIn("consume", src.lower(), "must record the consume-after-success step")
        self.assertIn("20261106_173554_a10444", src, "must record the Bot Chat session id")
        self.assertIn("state.db", src, "must record the SQLite state database path")


if __name__ == "__main__":
    unittest.main()
