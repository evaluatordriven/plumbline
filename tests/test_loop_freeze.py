"""Bar: loop() freezes the custody bar before it dispatches the Maker.

Owner slice, binding this job: loop() freezes the bar in the ledger at the
start, after it reads the packet and before it dispatches the Maker. The
freeze is a live event. It is not a time typed into inputs/custody.json.

kit/emit_custody.py, kit/custody_history.py and schemas/ are not editable.
This bar does not require the emitter to exit 0. A CustodyNotDone from the
finish seam, after a live freeze, is not a failure of this file.

Labels this seat chose:
- The job directory is record_dir. That is the directory loop() already
  passes to kit/emit_custody.py --job-dir. The ledger is
  record_dir/inputs/custody-events.jsonl and record_dir/inputs/custody.json.
  record_dir must be empty of files when loop() is entered, so the bar is
  not planted there.
- The bar is <cwd>/custody/bar.md. That name is the ledger tool's own
  default. The bytes are the fixture below, not a job bound.
- A live freeze is one line from kit/custody_ledger.py freeze, writer
  kit/custody_ledger.py@<sha12> of this tree's kit/custody_ledger.py, never
  "hand". bar_file is relative to record_dir, and the file it names hashes
  to bar_sha256, which is the planted bar's sha256. How loop() points the
  tool at that file is the Maker's. The event has to name those bytes.
- The Maker harness log is the stub's, at
  record_dir/custody/evidence/harness-maker.log. startedAt is that first
  call's sent_at, which is how kit/custody_history.py defines it. No
  network and no model call. The stub's first action records the ledger
  bytes it already saw, so a same-second stamp cannot pretend the freeze
  preceded dispatch.
- A caller with no custody inputs and no convention bar: loop() proceeds
  without freezing anything. Nothing is frozen and nothing is written for the
  bar. The Maker command runs and the finish seam runs normally. Owner
  instruction 2026-11-08, binding this job.
- A custody-bearing job (inputs/custody.json present) that names no bar and
  has no convention bar still fails closed, because the presence of custody
  inputs removes the skip path.
- A planted bar that cannot be read, or a freeze command that the ledger
  tool refuses, still fails closed before the Maker command runs.
  loop() must raise and must not invoke kit/emit_custody.py.

Fixture bounds below are not this job's bounds. This seat chose them so
loop() can be entered. They are not another bar's bounds.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

PY = sys.executable
BAR_REL = "custody/bar.md"
BAR_BYTES = b"loop-freeze bar\n"
LEDGER_REL = "inputs/custody-events.jsonl"
HARNESS_REL = "custody/evidence/harness-maker.log"
SAW_REL = "maker-saw.json"
LEDGER_PY = "kit/custody_ledger.py"


def _repo():
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    if os.path.isfile(os.path.join(parent, "kit", "conductor_loop.py")):
        return parent
    env = os.environ.get("PLUMBLINE_REPO", "")
    if env and os.path.isfile(os.path.join(env, "kit", "conductor_loop.py")):
        return os.path.realpath(env)
    return parent


REPO = _repo()
sys.path.insert(0, REPO)

from kit.conductor_loop import loop  # noqa: E402
import kit.conductor_loop as cl  # noqa: E402
import kit.custody_history as H  # noqa: E402


def _sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _writer_stamp():
    digest = _sha_file(os.path.join(REPO, LEDGER_PY))[:12]
    return "kit/custody_ledger.py@%s" % digest


def _packet(work, maker):
    """A packet loop() will enter. Bounds here are fixture-only. Not the job's."""
    return {
        "ratified": True,
        "mode": "scored",
        "human_seat": "fixture-human-seat",
        "artifact": {
            "test_cmd": [PY, "-c", "import sys; t=open(sys.argv[1]).read(); sys.exit(0 if t.startswith('yes') else 1)", os.path.join(work, "src", "w.txt")],
            "frozen": [os.path.join(work, "tests", "t.py")],
            "editable": ["src"],
            "ignore": [".git", "__pycache__"],
        },
        "maker": {"cmd": maker, "handoff": "rule12"},
        "evaluator": {
            "kind": "script",
            "cmd": [PY, "-c", "raise SystemExit('fixture evaluator_fn is the seat')"],
            "runs": 2,
            "held_out": [],
        },
        "bounds": {
            "T_accept": 2,
            "T_dim": 2,
            "T_reject": 1,
            "cap": 1,
            "budget": {"amount": 0, "unit": "USD", "time_hours_lt": 1},
        },
        "escalation": {
            "route": ["Architect", "Owner"],
            "classes": [],
            "holders": {
                "architect": "plumbline-architect",
                "orchestrator": [
                    {
                        "holder": "kit.conductor_loop.loop",
                        "kind": "script",
                        "does": "rounds",
                        "tested": "fixture-not-a-job",
                    },
                    {
                        "holder": "fixture-escalations",
                        "kind": "script",
                        "does": "escalations",
                        "tested": "fixture-not-a-job",
                    },
                ],
            },
        },
    }


def _scores():
    return {
        "dimensions": [{"name": "q", "score": 2, "observation": "seen"}],
        "violations": [],
        "verdict": "accept",
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _events(path):
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                out.append(json.loads(line))
    return out


def _freezes(events):
    return [ev for ev in events if isinstance(ev, dict) and ev.get("event") == "freeze"]


def _prepare(work):
    _write(work, "tests/t.py", "pin\n")
    _write(work, "src/w.txt", "no\n")


def _plant_bar(work):
    path = os.path.join(work, BAR_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(BAR_BYTES)
    return path


def _maker(work, record_dir):
    """Stub maker. First action snapshots the ledger, then writes one harness call.

    sent_at is the process clock at that moment, fractional seconds, UTC Z.
    It is a measurement, not a time computed from the freeze stamp.
    """
    script = os.path.join(work, "maker.py")
    os.makedirs(work, exist_ok=True)
    with open(script, "w", encoding="utf-8") as handle:
        handle.write(
            "import json, os, sys\n"
            "from datetime import datetime, timezone\n"
            "from pathlib import Path\n"
            "record = Path(sys.argv[1])\n"
            "work_file = sys.argv[2]\n"
            "events = record / %r\n"
            "seen = events.read_text(encoding='utf-8') if events.is_file() else ''\n"
            "(record / %r).write_text(json.dumps({'events': seen}), encoding='utf-8')\n"
            "now = datetime.now(timezone.utc).strftime('%%Y-%%m-%%dT%%H:%%M:%%S.%%fZ')\n"
            "log = record / %r\n"
            "log.parent.mkdir(parents=True, exist_ok=True)\n"
            "log.write_text(json.dumps({\n"
            "    'call': 'maker-1',\n"
            "    'sent_at': now,\n"
            "    'received_at': now,\n"
            "    'request': {'url': 'http://127.0.0.1/fixture-not-a-network-call'},\n"
            "    'response': {},\n"
            "}) + '\\n', encoding='utf-8')\n"
            "Path(work_file).write_text('yes\\n', encoding='utf-8')\n"
            % (LEDGER_REL, SAW_REL, HARNESS_REL)
        )
    return [PY, script, record_dir, os.path.join(work, "src", "w.txt")]


def _sentinel_maker(record_dir):
    sentinel = os.path.join(record_dir, "maker-ran")
    return [PY, "-c", "open(%r, 'w').write('ran\\n')" % sentinel], sentinel


def _proceeding_maker(record_dir, work):
    """A maker that runs, writes a sentinel, and also produces the artifact."""
    sentinel = os.path.join(record_dir, "maker-ran")
    w_path = os.path.join(work, "src", "w.txt")
    return [PY, "-c", "open(%r, 'w').write('ran\\n'); open(%r, 'w').write('yes\\n')" % (sentinel, w_path)], sentinel


STANDARD_MOVED = {
    "locator": "standard_moved",
    "dimension": "loop()/freeze_bar behaviour when no bar is present",
    "test": "tests/test_loop_freeze.py::LoopFreezeTests::test_unwritable_freeze_fails_closed",
    "old_assertion": (
        "exc is not None and not os.path.exists(sentinel) and no emit_custody.py call "
        "and no custody/record.custody.json"
    ),
    "new_assertion": (
        "not isinstance(exc, RuntimeError) and os.path.exists(sentinel) and no freeze event in "
        "inputs/custody-events.jsonl and no bar file copied into the job directory"
    ),
    "ruling": (
        "Owner instruction 2026-11-08: a caller with no custody inputs and no bar "
        "proceeds; nothing is frozen; nothing is written."
    ),
    "moved_at": "2026-11-08",
}


def _call_loop(packet, record, work):
    try:
        loop(
            packet,
            record_dir=record,
            cwd=work,
            evaluator_fn=lambda turn, cwd: _scores(),
        )
    except Exception as exc:
        return exc
    return None


class LoopFreezeTests(unittest.TestCase):
    def test_freeze_event_precedes_the_maker(self):
        bar_sha = _sha_bytes(BAR_BYTES)
        with TemporaryDirectory() as work, TemporaryDirectory() as record:
            _prepare(work)
            _plant_bar(work)
            exc = _call_loop(_packet(work, _maker(work, record)), record, work)
            events_path = os.path.join(record, LEDGER_REL)
            freezes = _freezes(_events(events_path))
            with self.subTest("freeze event"):
                self.assertTrue(
                    freezes,
                    "no freeze event in %s; loop() never froze the bar (%s)"
                    % (LEDGER_REL, type(exc).__name__ if exc else "returned"),
                )
                self.assertEqual(len(freezes), 1, "a bar is frozen once; got %d freeze events" % len(freezes))
            ev = freezes[0] if freezes else None

            def event():
                self.assertIsNotNone(ev, "no freeze event; loop() never froze the bar")
                assert ev is not None
                return ev

            with self.subTest("writer"):
                got = event()
                self.assertEqual(got.get("writer"), _writer_stamp())
                self.assertNotEqual(got.get("writer"), "hand")
                self.assertFalse(str(got.get("writer", "")).startswith("hand"))
            with self.subTest("bar file and sha256"):
                got = event()
                self.assertEqual(got.get("bar_sha256"), bar_sha)
                rel = got.get("bar_file")
                self.assertIsInstance(rel, str)
                self.assertTrue(rel)
                assert isinstance(rel, str)
                self.assertFalse(os.path.isabs(rel))
                named = os.path.join(record, rel)
                self.assertTrue(os.path.isfile(named), "freeze names %r but that file is not in the job directory" % rel)
                self.assertEqual(_sha_file(named), bar_sha)
                self.assertEqual(open(named, "rb").read(), BAR_BYTES)
            with self.subTest("at strictly earlier than maker startedAt"):
                got = event()
                saw_path = os.path.join(record, SAW_REL)
                self.assertTrue(os.path.isfile(saw_path), "stub did not record the ledger it saw at start")
                seen = json.loads(open(saw_path, encoding="utf-8").read()).get("events") or ""
                seen_freezes = _freezes(
                    [json.loads(line) for line in seen.splitlines() if line.strip()]
                )
                self.assertTrue(
                    seen_freezes,
                    "no freeze event; the ledger did not already hold one when the Maker started",
                )
                self.assertEqual(seen_freezes[0].get("at"), got.get("at"))
                self.assertEqual(seen_freezes[0].get("bar_sha256"), bar_sha)
                log = os.path.join(record, HARNESS_REL)
                calls = H.read_log(Path(log))
                self.assertTrue(calls, "stub harness log has no call")
                started = calls[0].sent
                frozen_at = H.parse_ts(got.get("at"))
                self.assertIsNotNone(
                    frozen_at,
                    "freeze at %r is not the ledger tool's UTC stamp" % (got.get("at"),),
                )
                self.assertIsNotNone(started, "harness call has no sent_at; startedAt was not measured")
                assert frozen_at is not None and started is not None
                self.assertLess(
                    frozen_at,
                    started,
                    "freeze at %s is not strictly earlier than maker startedAt %s"
                    % (got.get("at"), calls[0].raw.get("sent_at")),
                )

    def test_no_custody_inputs_and_no_bar_proceeds_without_freeze(self):
        """Owner instruction 2026-11-08: a caller with no custody inputs and no
        bar proceeds; nothing is frozen; nothing is written for the bar."""
        with TemporaryDirectory() as work, TemporaryDirectory() as record:
            _prepare(work)
            self.assertFalse(os.path.isfile(os.path.join(work, BAR_REL)))
            self.assertFalse(os.path.isfile(os.path.join(record, "inputs", "custody.json")))
            maker, sentinel = _proceeding_maker(record, work)
            exc = _call_loop(_packet(work, maker), record, work)
            # If loop raised at the freeze seam it would be RuntimeError;
            # proceeding past freeze_bar is what this clause tests.
            self.assertNotIsInstance(
                exc,
                RuntimeError,
                "loop() raised %s at the freeze seam for a caller with no custody inputs and no bar; it should proceed"
                % (type(exc).__name__ if exc else None,),
            )
            self.assertTrue(
                os.path.isfile(sentinel),
                "maker did not run; loop() failed closed instead of proceeding",
            )
            events_path = os.path.join(record, LEDGER_REL)
            freezes = _freezes(_events(events_path))
            self.assertEqual(
                freezes,
                [],
                "freeze event was written when no custody inputs were prepared; nothing should be frozen",
            )
            self.assertFalse(
                os.path.isfile(os.path.join(record, BAR_REL)),
                "bar file was copied into the job directory when no custody inputs were prepared; nothing should be written",
            )


if __name__ == "__main__":
    unittest.main()
