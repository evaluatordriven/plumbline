"""Bar: seat-move notices reach the conductor's Bot Chat via a Plumbline-private mailbox.

Source:
  /home/jarbis1/plumbline-hermes-seat-architecture.md section 15, lines 618-624.
  The artifact under test is the repo-resident seat-move module
  (kit/seat_move_notice.py) plus the repo-resident deployment hinge
  (deployment/plumbline-conductor/seat-move-notice.py) and deployment record
  (deployment/plumbline-conductor/README.md).  The profile launcher script at
  ~/.hermes/profiles/plumbline-conductor/bin/run-loop is produced by the
  deployment step and is NOT tested directly; see M7/M8.

Why a Plumbline-private mailbox, not the engine's
=================================================
The Hermes engine already ships two durable handoffs — `cron/bot_chat_delivery.py`
(lines 59 `defer`, 82 `drain`, 93 `_drain`) and `tools/bot_live_delivery.py`
(lines 54 `find_canonical_live_owner`, 167 `deliver_to_live_owner`) — and a
conductor-profile plugin hook would run inside the process that owns the session.
None of the three can satisfy Section 15 for the CLI-backed conductor Bot Chat
that the existing wrappers run, while keeping the "session must not be written by
a process that does not own it" rule and the fail-closed rule.

`cron/bot_chat_delivery.py` drains via the scheduler, and its drain loop contains
an explicit guard at lines 116-122: if a canonical Bot Chat owner exists but is
not a *live* consumer, the receipt is skipped and left queued.  `tools/bot_live_delivery.py`
`find_canonical_live_owner` (lines 54-61) considers a consumer live only when its
lease metadata advertises `bot_live_delivery_consumer=True` and a `live_session_id`;
that metadata is set by `tui_gateway/session_lifecycle.py::_lease_metadata`
(lines 63-66) only for sessions claimed through the gateway/TUI.  A plain CLI
`hermes chat` Bot Chat therefore appears as a canonical owner but never as a live
consumer, which makes the scheduler drain silently stall.  `_deliver_to_bot_chat`
in `cron/scheduler_delivery.py` encodes the same choice at lines 837-848: when a
canonical owner exists but no live owner is present, it enqueues a deferred receipt
rather than writing the session.

`tools/bot_live_delivery.py::deliver_to_live_owner` would be the right path if the
conductor Bot Chat were gateway/TUI-hosted, because the live owner could then claim
and write the notice in-process.  That is a hosting change, not a drop-in
replacement, and Section 15 is written against the existing Bot Chat (`Bot Chat`,
session `20261106_173554_a10444`) that the wrapper opens as a CLI session.

An in-process plugin hook runs inside the owner process and takes no lease, but
Hermes provides no cross-process hook fire from the side process that detects the
seat move.  The side process still needs a handoff surface.  The only engine
surface for that handoff is the live-owner mailbox, which is gated on the
gateway/TUI lease metadata the CLI session does not carry.

So the engine's deferred mailbox is a *cron-output* mailbox drained by the
scheduler for the benefit of later live consumers; Plumbline needs a
*conductor-side* mailbox drained by the conductor's own turn.  That is what this
bar tests: a private JSON mailbox under the conductor profile's runtime directory,
written by the side process and drained by the conductor's own turn, with no
Hermes session lease, no `hermes chat` subprocess, and no dependence on the
engine's Bot Chat delivery paths.

Scale:
  Binary per dimension: 1 = the check PASSes, 0 = it does not.

Threshold:
  T_accept = 1, T_dim = 1, T_reject = 0.  Every dimension must PASS.
  Any FAIL before implementation exists is the red bar.

Dimensions:
  M1. kit/seat_move_notice.py exists and exports callable ``send_notice`` and
      ``drain_notices``.
  M2. ``send_notice`` writes a durable JSON notice into the Plumbline mailbox
      directory for the named conductor profile; it does not invoke ``hermes``,
      any subprocess, or any network/platform API.
  M3. The notice content names the direction (to_seat/from_seat), the seat,
      the job_id, and carries a stable notice id and a queued-at timestamp.
  M4. ``send_notice`` is safe to call from a side process: it touches only the
      mailbox directory, requires no TTY, claims no Hermes session, and returns
      the notice id once the file is durable on disk.
  M5. Fail-closed: an unknown direction raises ``ValueError``; a write that
      cannot be persisted raises; ``PLUMBLINE_SEAT_NOTICE=0`` still disables
      delivery without writing a mailbox file.
  M6. ``drain_notices`` returns every queued notice in FIFO order from the same
      mailbox directory and removes consumed files, so the same notice is
      never delivered twice.  A read/write error raises rather than silently
      dropping notices.
  M7. The repo carries deployment/plumbline-conductor/seat-move-notice.py,
      a script that imports ``kit.seat_move_notice`` and calls
      ``send_notice`` for both to_seat and from_seat, without swallowing
      exceptions.
  M8. The repo carries deployment/plumbline-conductor/README.md that records:
      the Plumbline mailbox path; the side-process enqueue hook points for
      dispatch and handback; and the conductor-own-turn drain hook that moves
      the notice into the Bot Chat.
  M9. The implementation of ``send_notice`` does not depend on the engine's
      Bot Chat delivery paths: it never imports or invokes
      ``cron.bot_chat_delivery``, ``tools.bot_live_delivery``,
      ``find_canonical_owner``, ``find_canonical_live_owner``,
      ``deliver_to_live_owner``, or any active-session lease machinery, and the
      deployment script does not either.

What this bar does NOT prove:
  It does not prove that the live Bot Chat UI renders the notice or that the
  Owner-facing conduit reacts to it; it proves only that the Plumbline mailbox
  exists, that notices are durably enqueued by the side process without touching
  the session, that the conductor's own turn can drain them, that the deployment
  step documents both hooks, and that the implementation does not silently fall
  back to an engine path that would stall or break the ownership rule.
"""
from __future__ import annotations

import ast
import importlib
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock as mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

DEPLOY_DIR = os.path.join(REPO, "deployment", "plumbline-conductor")
DEPLOY_SCRIPT = os.path.join(DEPLOY_DIR, "seat-move-notice.py")
DEPLOY_README = os.path.join(DEPLOY_DIR, "README.md")

_MODULE_PATH = pathlib.Path(REPO, "kit", "seat_move_notice.py")

# Engine entry points that are explicitly not used by the private-mailbox design.
# See the bar rationale for why each one is unavailable or wrong for the CLI-backed
# conductor Bot Chat.
_ENGINE_BOT_CHAT_PATHS = (
    "cron.bot_chat_delivery",
    "tools.bot_live_delivery",
    "find_canonical_owner",
    "find_canonical_live_owner",
    "deliver_to_live_owner",
    "try_acquire_active_session",
    "active_sessions",
)


def _mailbox_dir(profile_home: "str | pathlib.Path") -> pathlib.Path:
    return pathlib.Path(profile_home) / "runtime" / "plumbline-seat-notices"


class TestSeatMoveNoticeMailbox(unittest.TestCase):

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="seatnotice-"))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.profile_home = self.tmp
        self.env = {"PLUMBLINE_SEAT_NOTICE": "1"}

    def _module(self):
        return importlib.import_module("kit.seat_move_notice")

    def _mailbox(self) -> pathlib.Path:
        return _mailbox_dir(self.profile_home)

    def test_m1_exports_send_and_drain(self):
        """M1: the module exports send_notice and drain_notices."""
        mod = self._module()
        self.assertTrue(hasattr(mod, "send_notice") and callable(mod.send_notice))
        self.assertTrue(hasattr(mod, "drain_notices") and callable(mod.drain_notices))

    def test_m2_writes_mailbox_no_subprocess(self):
        """M2: send_notice writes a JSON file in the mailbox, not a hermes/subprocess call."""
        mod = self._module()
        with mock.patch("subprocess.run") as mock_run, mock.patch("subprocess.Popen") as mock_popen:
            notice_id = mod.send_notice(
                direction="to_seat",
                seat="plumbline-eval",
                job_id="job-1",
                profile_home=str(self.profile_home),
                env=self.env,
            )
        mock_run.assert_not_called()
        mock_popen.assert_not_called()

        files = list(self._mailbox().glob("*.json"))
        self.assertEqual(len(files), 1, "exactly one notice file must be written")
        with files[0].open(encoding="utf-8") as fh:
            payload = json.load(fh)
        self.assertEqual(payload.get("notice_id"), notice_id)
        self.assertEqual(payload.get("direction"), "to_seat")
        self.assertEqual(payload.get("seat"), "plumbline-eval")
        self.assertEqual(payload.get("job_id"), "job-1")

    def test_m3_notice_content(self):
        """M3: notice names direction, seat, job_id, plus id and queued_at."""
        mod = self._module()
        before = time.time()
        mod.send_notice(
            direction="from_seat",
            seat="plumbline-maker",
            job_id="job-2",
            profile_home=str(self.profile_home),
            env=self.env,
        )
        after = time.time()
        files = sorted(self._mailbox().glob("*.json"))
        self.assertEqual(len(files), 1)
        payload = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertIn(payload["direction"], ("to_seat", "from_seat"))
        self.assertIsInstance(payload.get("seat"), str)
        self.assertIsInstance(payload.get("job_id"), str)
        self.assertIsInstance(payload.get("notice_id"), str)
        self.assertTrue(payload["notice_id"])
        queued = payload.get("queued_at")
        self.assertIsInstance(queued, str)
        # ISO 8601-ish timestamp within the call window.
        self.assertTrue(before <= float(payload.get("queued_at_epoch", before)) <= after)

    def test_m4_side_process_safe(self):
        """M4: send_notice touches only the mailbox; no session, no TTY, no hermes ownership."""
        mod = self._module()
        # Run in an environment that has no real HOME/HERMES_HOME access unless
        # the implementation explicitly reads it.  The call must not prompt,
        # block, or require an active Hermes session.
        minimal_env = {"PLUMBLINE_SEAT_NOTICE": "1"}
        mod.send_notice(
            direction="to_seat",
            seat="plumbline-eval",
            job_id="job-3",
            profile_home=str(self.profile_home),
            env=minimal_env,
        )
        self.assertTrue(list(self._mailbox().glob("*.json")))

    def test_m5_fail_closed_bad_direction(self):
        """M5 fail-closed: unknown directions raise ValueError."""
        mod = self._module()
        with self.assertRaises(ValueError):
            mod.send_notice(
                direction="sideways",
                seat="plumbline-eval",
                job_id="job-bad",
                profile_home=str(self.profile_home),
                env=self.env,
            )

    def test_m5_fail_closed_write_error(self):
        """M5 fail-closed: a mailbox that cannot be written raises rather than silently dropping."""
        mod = self._module()
        # Make the runtime directory exist as a file so the mailbox dir cannot be created.
        runtime = self.profile_home / "runtime"
        runtime.write_text("not a directory", encoding="utf-8")
        with self.assertRaises((OSError, RuntimeError)):
            mod.send_notice(
                direction="to_seat",
                seat="plumbline-eval",
                job_id="job-write-fail",
                profile_home=str(self.profile_home),
                env=self.env,
            )

    def test_m5_disabled(self):
        """M5: PLUMBLINE_SEAT_NOTICE=0 skips writing without raising."""
        mod = self._module()
        env = dict(self.env)
        env["PLUMBLINE_SEAT_NOTICE"] = "0"
        result = mod.send_notice(
            direction="to_seat",
            seat="plumbline-eval",
            job_id="job-disabled",
            profile_home=str(self.profile_home),
            env=env,
        )
        self.assertFalse(list(self._mailbox().glob("*.json")))
        self.assertIsNone(result)

    def test_m6_drain_notices_fifo_and_cleanup(self):
        """M6: drain_notices returns queued notices in order and removes consumed files."""
        mod = self._module()
        ids = []
        for idx, direction in enumerate(("to_seat", "from_seat", "to_seat")):
            notice_id = mod.send_notice(
                direction=direction,
                seat=f"seat-{idx}",
                job_id=f"job-{idx}",
                profile_home=str(self.profile_home),
                env=self.env,
            )
            ids.append(notice_id)

        drained = mod.drain_notices(profile_home=str(self.profile_home))
        self.assertEqual(len(drained), 3)
        for idx, item in enumerate(drained):
            self.assertEqual(item["direction"], ("to_seat", "from_seat", "to_seat")[idx])
            self.assertEqual(item["seat"], f"seat-{idx}")
            self.assertEqual(item["job_id"], f"job-{idx}")
            self.assertEqual(item["notice_id"], ids[idx])

        # After draining, the mailbox is empty.
        self.assertFalse(list(self._mailbox().glob("*.json")))
        # A second drain returns nothing.
        self.assertEqual(mod.drain_notices(profile_home=str(self.profile_home)), [])

    def test_m6_drain_fails_closed(self):
        """M6: a mailbox that cannot be read raises instead of silently dropping notices."""
        mod = self._module()
        runtime = self.profile_home / "runtime"
        runtime.write_text("not a directory", encoding="utf-8")
        with self.assertRaises((OSError, RuntimeError)):
            mod.drain_notices(profile_home=str(self.profile_home))

    def test_m7_deployment_script_wires_module(self):
        """M7: repo-resident deployment script calls send_notice for both directions."""
        self.assertTrue(
            os.path.isfile(DEPLOY_SCRIPT),
            f"deployment script missing: {DEPLOY_SCRIPT}",
        )
        src = pathlib.Path(DEPLOY_SCRIPT).read_text(encoding="utf-8")
        self.assertIn("kit.seat_move_notice", src, "must import the repo module")

        tree = ast.parse(src)
        send_notice_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "send_notice"
        ]
        self.assertTrue(send_notice_calls, "must call send_notice")
        directions = set()
        for call in send_notice_calls:
            for kw in call.keywords:
                if kw.arg == "direction" and isinstance(kw.value, ast.Constant):
                    directions.add(kw.value.value)
        self.assertIn("to_seat", directions, "must announce work moving to a seat")
        self.assertIn("from_seat", directions, "must announce a seat handing work back")

        # Fail-closed: the wrapper must not silence a failure from send_notice.
        except_handlers = [
            node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)
        ]
        for handler in except_handlers:
            if handler.type is None or (
                isinstance(handler.type, ast.Name) and handler.type.id == "Exception"
            ):
                self.fail(
                    "deployment script must not use a bare or Exception catch "
                    "around the notice call"
                )

    def test_m8_deployment_record_states_mailbox_and_hooks(self):
        """M8: deployment README records the mailbox path and both enqueue/drain hooks."""
        self.assertTrue(
            os.path.isfile(DEPLOY_README),
            f"deployment record missing: {DEPLOY_README}",
        )
        src = pathlib.Path(DEPLOY_README).read_text(encoding="utf-8")
        # The record must state the actual channel, not the superseded hermes chat path.
        self.assertIn("plumbline-seat-notices", src, "must record the mailbox directory path")
        self.assertIn("to_seat", src, "must record the dispatch enqueue hook")
        self.assertIn("from_seat", src, "must record the handback enqueue hook")
        self.assertIn("drain", src.lower(), "must record the conductor-own-turn drain hook")
        # The README must point at the repo-resident script.
        self.assertIn("deployment/plumbline-conductor/seat-move-notice.py", src)

    def test_m9_private_mailbox_not_engine_mailbox(self):
        """M9: the implementation does not ride Hermes Bot Chat delivery machinery.

        The engine's paths are excluded by design:
          * cron/bot_chat_delivery.py::_drain lines 116-122 skips a profile when a
            canonical owner exists but no live consumer is present.
          * tools/bot_live_delivery.py::find_canonical_live_owner lines 54-61 only
            treats gateway/TUI leases with bot_live_delivery_consumer=True as live.
          * tui_gateway/session_lifecycle.py::_lease_metadata lines 63-66 show
            that metadata is set only for gateway/TUI claimed sessions.
          * cron/scheduler_delivery.py::_deliver_to_bot_chat lines 837-848 defers
            to cron.bot_chat_delivery when the canonical owner is not live.
        A side process that called those paths would either silently queue behind
        the scheduler or require a hosting change to gateway/TUI, neither of which
        satisfies the existing CLI-backed conductor Bot Chat.
        """
        self.assertTrue(
            _MODULE_PATH.is_file(),
            f"module missing: {_MODULE_PATH}",
        )
        mod_src = _MODULE_PATH.read_text(encoding="utf-8")
        deploy_src = pathlib.Path(DEPLOY_SCRIPT).read_text(encoding="utf-8")
        for token in _ENGINE_BOT_CHAT_PATHS:
            self.assertNotIn(
                token,
                mod_src,
                f"kit/seat_move_notice.py must not use {token!r} -- "
                "the engine path cannot deliver into a CLI-owned Bot Chat",
            )
            self.assertNotIn(
                token,
                deploy_src,
                f"deployment/plumbline-conductor/seat-move-notice.py must not use {token!r}",
            )


if __name__ == "__main__":
    unittest.main()
