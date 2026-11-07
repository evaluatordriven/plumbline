"""Bar for the escalation holder. Red until kit/escalate.py exists.

This file is the bar. It is frozen. Do not edit it to make it pass.

The script is not in this tree. Importing it is the red. A later failure that
is an assertion in this file, rather than that import, is the wrong red.

Agreed core, Owner brief 2026-11-06. Nothing else is in this bar.

- The holder is a script in public kit/. loop() does not call the Architect.
  The script runs after loop() returns.
- The Architect writes the analysis. A broken or incomplete Architect run
  delivers nothing. The script does not invent an escalation.
- Deliver the Architect's text with its sha256. A send receipt is not a
  read-back. Do not label a delivery verified.
- A retry does not re-run rounds and does not send twice.
- decide records the Owner's reply and does not touch terminal_state.
- proposed_packet, when present, is validated and is not ratified.
- A public module does not name an address or a profile. The address stays
  in the plug. Steve's address is not recorded. The check is structural.
- Do not add a minimum option count or clock arithmetic and call it I12.
  That rule is withdrawn. The analysis text below has neither. Rejecting it
  for a missing count or missing figures fails this bar.

Labels the Architect chose. They are names for the seam, not resolutions
of the open questions below.

- Module kit.escalate, file kit/escalate.py. Chosen so it does not collide
  with gate.plumbline_escalate. The branch name is not the import name.
- deliver(record_dir, *, architect, transport) -> dict
  architect is a callable. A finished run returns a dict with non-blank
  text. proposed_packet is optional; null and a missing key are the same,
  not present. Anything else, or a raise, is a broken or incomplete run.
  transport is a callable. It receives the Architect's text. It owns the
  address. Neither argument has a default.
  On a send, the return has delivered is True and sha256 is
  hashlib.sha256(text.encode("utf-8")).hexdigest(). The same sha256 is in
  some file under record_dir. The transport's first positional argument,
  or its text keyword, is the Architect's text unchanged.
  On no send, transport is not called. The call may raise, or return a
  dict whose delivered is False.
- decide(record_dir, reply) -> object
  The second positional is the Owner's reply. After the call the reply's
  exact text is in some file under record_dir. terminal_state in
  summary.json and escalation.json is unchanged.
- Validated means Draft 2020-12 against schemas/job-packet.schema.json in
  this repo. The corpus checker is not this bar. A missing corpus must not
  be the red. Checked this turn: the unratified fixture below is valid, the
  ratified readings fixture below is valid, and {"ratified": false} alone
  is invalid (first error: 'entry' is a required property).
- Once transport has been called, a later deliver does not call it again,
  including when the first call raised. A broken Architect run does not
  count as a send: a later finished run may send once.

Not in this bar. Not decided. Do not encode an answer.

- Memo questions 1-7. Q1's option count and clock arithmetic are withdrawn,
  not replaced with a different count. Q3's does value is not decided.
  Q4's file name (escalation.filled.json or an in-place fill) is not
  decided. Q5's decision.json, C40 fields, escalation_id, and the state
  names prepared, sent, answered are not decided. Q6's exit on accepted,
  on rejected, and on a missing escalation.json is not decided. Q7,
  _held_out, is a separate change.
- This bar does not require an intent file, a CLI flag, or a chain that
  re-runs rounds. It requires the observables above.
- The holder entries in the fixture are the shape loop() already writes.
  They are not a ruling on who the escalations holder is.
- T_accept, T_dim, T_reject, cap, clock, and budget are not set for this
  job. They are not used. This file writes no packet.
"""
import hashlib
import importlib
import inspect
import json
import os
import re
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import kit.escalate as escalate

ANALYSIS = "ARCHITECT-ANALYSIS-7c1e"
REPLY = "OWNER-REPLY-7c1e"
SCHEMA = ROOT / "schemas" / "job-packet.schema.json"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PROFILES = (
    "plumbline-architect",
    "plumbline-conductor",
    "plumbline-eval",
    "plumbline-maker",
    "plumbline-deploy",
    "plumbline-audit",
)
# Copied from tests/validate_schemas.py. Not this job's packet.
UNRATIFIED = {
    "entry": "A",
    "instrument_profile": "full",
    "job_name": "unratified job",
    "artifact": "artifact/iter-0",
    "buyer": "Owner",
    "evaluator": "z-ai/glm-5.3-flash",
    "maker": "some-engine",
    "mode": "readings",
    "ratified": False,
    "stage": "elicitation",
    "proposed": {"rationale": "thresholds and dimension set proposed, unratified"},
}
# Copied from tests/validate_schemas.py reading(). Schema-valid and ratified.
RATIFIED = {
    "entry": "B",
    "instrument_profile": "full",
    "job_name": "retrofit census",
    "artifact": "repo@abc123",
    "buyer": "Owner",
    "maker": "unrecoverable",
    "evaluator": "z-ai/glm-5.3-flash",
    "mode": "readings",
    "ratified": True,
    "stage": "architecture",
    "human_seat": "Owner via Telegram topic",
    "standard_ref": "the artifact's own docs and tests, frozen 2026-09-29",
    "reads_before_freeze": ["rubric frozen 2026-09-29T10:00Z; git log read after"],
}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def _needs_owner_record(root):
    """A stop loop() already writes. Not a holder ruling. Not a packet."""
    _write(os.path.join(root, "summary.json"), {
        "terminal_state": "needs_owner",
        "outcome": "needs_owner",
        "stop": "cap reached",
        "rounds": 1,
    })
    _write(os.path.join(root, "escalation.json"), {
        "terminal_state": "needs_owner",
        "outcome": "needs_owner",
        "stop": "cap reached",
        "escalation_kind": "other",
        "route": ["Architect", "Owner"],
        "human_seat": "Owner",
        "holders": {
            "architect": "architect-seat",
            "orchestrator": [
                {
                    "holder": "kit.conductor_loop.loop",
                    "kind": "script",
                    "does": "rounds",
                    "tested": "fixture",
                },
                {
                    "holder": "escalation-holder",
                    "kind": "model",
                    "does": "escalations",
                    "tested": "fixture",
                },
            ],
        },
        "problems": [],
        "question": None,
        "diagnosis": None,
        "why_unobservable": None,
        "options": None,
        "recommendation": None,
        "proposed_packet": None,
        "decision": None,
        "best": None,
        "tried": [],
        "by": "loop()",
        "started_at": "2026-11-06T00:00:00+00:00",
        "ended_at": "2026-11-06T00:00:01+00:00",
    })


def _terminal(root, name):
    with open(os.path.join(root, name), encoding="utf-8") as fh:
        return json.load(fh)["terminal_state"]


def _snapshot(root):
    found = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                found[path] = fh.read()
    return found


def _changed(root, before):
    after = _snapshot(root)
    return {path: data for path, data in after.items() if before.get(path) != data}


def _has_verified(obj):
    if isinstance(obj, dict):
        if "verified" in obj:
            return True
        return any(_has_verified(value) for value in obj.values())
    if isinstance(obj, list):
        return any(_has_verified(value) for value in obj)
    return obj == "verified"


def _sent_text(transport):
    _args, kwargs = transport.call_args
    if transport.call_args.args:
        return transport.call_args.args[0]
    return kwargs.get("text")


class EscalateBar(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.record = self._tmp.name
        _needs_owner_record(self.record)

    def _guard_loop(self):
        import kit.conductor_loop as cl

        original = cl.loop
        calls = []

        def sentinel(*_args, **_kwargs):
            calls.append(1)
            raise AssertionError("loop() was called")

        cl.loop = sentinel
        saved = []
        for name in dir(escalate):
            if getattr(escalate, name, None) is original:
                saved.append((name, original))
                setattr(escalate, name, sentinel)
        self.addCleanup(self._restore_loop, cl, original, saved)
        return calls

    def _restore_loop(self, cl, original, saved):
        cl.loop = original
        for name, value in saved:
            setattr(escalate, name, value)

    def _assert_not_verified(self, result, changed):
        if result is not None:
            self.assertFalse(_has_verified(result), result)
        for path, data in changed.items():
            text = data.decode("utf-8", errors="replace")
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                self.assertIsNone(
                    re.search(r"\bverified\b", text),
                    path,
                )
            else:
                self.assertFalse(_has_verified(parsed), path)

    def _call_deliver(self, architect, transport):
        calls = self._guard_loop()
        before = _snapshot(self.record)
        try:
            result = escalate.deliver(
                self.record, architect=architect, transport=transport,
            )
        except AssertionError:
            raise
        except Exception:
            result = None
        self.assertEqual(calls, [], "loop() was called")
        return result, _changed(self.record, before)

    def test_module_is_public_kit_escalate(self):
        self.assertTrue(SCHEMA.is_file(), SCHEMA)
        module_file = escalate.__file__
        if not isinstance(module_file, str):
            self.fail("kit.escalate.__file__ is not a file path")
        path = Path(module_file).resolve()
        self.assertEqual(path, (ROOT / "kit" / "escalate.py").resolve())
        self.assertTrue(str(path).startswith(str(ROOT.resolve())))
        source = path.read_text(encoding="utf-8")
        found = EMAIL.search(source)
        self.assertIsNone(found, found.group(0) if found else "")
        for name in PROFILES:
            self.assertNotIn(name, source)
        deliver = inspect.signature(escalate.deliver)
        for name in ("architect", "transport"):
            self.assertIn(name, deliver.parameters)
            self.assertIs(
                deliver.parameters[name].default, inspect.Parameter.empty,
            )
        with self.assertRaises(TypeError):
            escalate.deliver(self.record)

    def test_loop_does_not_call_the_architect(self):
        source = (ROOT / "kit" / "conductor_loop.py").read_text(encoding="utf-8")
        self.assertNotIn("kit.escalate", source)
        self.assertNotIn("import escalate", source)

    def test_broken_or_incomplete_architect_delivers_nothing(self):
        def _raise():
            raise RuntimeError("architect failed")

        cases = [
            _raise,
            lambda: None,
            lambda: ANALYSIS,
            lambda: {},
            lambda: {"text": ""},
            lambda: {"text": "   "},
            lambda: {"text": None},
        ]
        for architect in cases:
            with self.subTest(architect=getattr(architect, "__name__", architect)):
                transport = mock.Mock()
                result, changed = self._call_deliver(architect, transport)
                self.assertEqual(transport.call_count, 0)
                if isinstance(result, dict):
                    self.assertIs(result.get("delivered"), False)
                self._assert_not_verified(result, changed)
                joined = b"\n".join(changed.values())
                self.assertNotIn(ANALYSIS.encode("utf-8"), joined)

    def test_delivers_architect_text_with_sha256_and_not_verified(self):
        architect = mock.Mock(return_value={"text": ANALYSIS})
        transport = mock.Mock(return_value={
            "receipt": "send-1",
            "status": "verified",
        })
        calls = self._guard_loop()
        before = _snapshot(self.record)
        result = escalate.deliver(
            self.record, architect=architect, transport=transport,
        )
        changed = _changed(self.record, before)
        self.assertEqual(calls, [])
        self.assertEqual(architect.call_count, 1)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(_sent_text(transport), ANALYSIS)
        self.assertIsInstance(result, dict)
        self.assertIs(result.get("delivered"), True)
        digest = _sha(ANALYSIS)
        self.assertEqual(result.get("sha256"), digest)
        self.assertNotIn("verified", result)
        self._assert_not_verified(result, changed)
        blob = b"\n".join(changed.values())
        self.assertIn(digest.encode("ascii"), blob)

    def test_retry_does_not_send_twice_or_rerun_rounds(self):
        architect = mock.Mock(return_value={"text": ANALYSIS})
        transport = mock.Mock(return_value={"receipt": "send-1", "status": "verified"})
        calls = self._guard_loop()
        escalate.deliver(self.record, architect=architect, transport=transport)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(_sent_text(transport), ANALYSIS)
        importlib.reload(escalate)
        second_architect = mock.Mock(return_value={"text": "OTHER-TEXT"})
        second = mock.Mock(return_value={"receipt": "send-2"})
        try:
            escalate.deliver(
                self.record, architect=second_architect, transport=second,
            )
        except AssertionError:
            raise
        except Exception:
            pass
        self.assertEqual(second.call_count, 0)
        self.assertEqual(calls, [])

    def test_transport_failure_is_not_sent_twice(self):
        architect = mock.Mock(return_value={"text": ANALYSIS})
        transport = mock.Mock(side_effect=RuntimeError("transport down"))
        calls = self._guard_loop()
        try:
            escalate.deliver(
                self.record, architect=architect, transport=transport,
            )
        except AssertionError:
            raise
        except Exception:
            pass
        self.assertEqual(transport.call_count, 1)
        importlib.reload(escalate)
        second = mock.Mock(return_value={"receipt": "send-2"})
        try:
            escalate.deliver(
                self.record, architect=architect, transport=second,
            )
        except AssertionError:
            raise
        except Exception:
            pass
        self.assertEqual(second.call_count, 0)
        self.assertEqual(calls, [])

    def test_broken_run_does_not_consume_the_send(self):
        def _raise():
            raise RuntimeError("architect failed")

        transport = mock.Mock()
        self._call_deliver(_raise, transport)
        self.assertEqual(transport.call_count, 0)
        architect = mock.Mock(return_value={"text": ANALYSIS})
        transport2 = mock.Mock(return_value={"receipt": "send-1"})
        calls = self._guard_loop()
        result = escalate.deliver(
            self.record, architect=architect, transport=transport2,
        )
        self.assertEqual(calls, [])
        self.assertEqual(transport2.call_count, 1)
        self.assertEqual(_sent_text(transport2), ANALYSIS)
        self.assertIs(result.get("delivered"), True)

    def test_decide_records_the_reply_and_does_not_touch_terminal_state(self):
        before_summary = _terminal(self.record, "summary.json")
        before_escalation = _terminal(self.record, "escalation.json")
        calls = self._guard_loop()
        escalate.decide(self.record, REPLY)
        self.assertEqual(calls, [])
        self.assertEqual(_terminal(self.record, "summary.json"), before_summary)
        self.assertEqual(_terminal(self.record, "escalation.json"), before_escalation)
        found = False
        for dirpath, _dirs, files in os.walk(self.record):
            for name in files:
                with open(os.path.join(dirpath, name), encoding="utf-8") as fh:
                    if REPLY in fh.read():
                        found = True
        self.assertTrue(found, "Owner reply was not recorded")

    def test_proposed_packet_ratified_is_not_delivered(self):
        architect = mock.Mock(return_value={
            "text": ANALYSIS,
            "proposed_packet": RATIFIED,
        })
        transport = mock.Mock()
        result, _changed_files = self._call_deliver(architect, transport)
        self.assertEqual(transport.call_count, 0)
        if isinstance(result, dict):
            self.assertIs(result.get("delivered"), False)

    def test_proposed_packet_invalid_is_not_delivered(self):
        architect = mock.Mock(return_value={
            "text": ANALYSIS,
            "proposed_packet": {"ratified": False},
        })
        transport = mock.Mock()
        result, _changed_files = self._call_deliver(architect, transport)
        self.assertEqual(transport.call_count, 0)
        if isinstance(result, dict):
            self.assertIs(result.get("delivered"), False)

    def test_proposed_packet_unratified_is_delivered_and_not_run(self):
        architect = mock.Mock(return_value={
            "text": ANALYSIS,
            "proposed_packet": UNRATIFIED,
        })
        transport = mock.Mock(return_value={"receipt": "send-1"})
        calls = self._guard_loop()
        result = escalate.deliver(
            self.record, architect=architect, transport=transport,
        )
        self.assertEqual(calls, [])
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(_sent_text(transport), ANALYSIS)
        self.assertIs(result.get("delivered"), True)
        self.assertEqual(result.get("sha256"), _sha(ANALYSIS))

    def test_null_proposed_packet_is_not_present(self):
        architect = mock.Mock(return_value={
            "text": ANALYSIS,
            "proposed_packet": None,
        })
        transport = mock.Mock(return_value={"receipt": "send-1"})
        calls = self._guard_loop()
        before = _snapshot(self.record)
        result = escalate.deliver(
            self.record, architect=architect, transport=transport,
        )
        changed = _changed(self.record, before)
        self.assertEqual(calls, [])
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(_sent_text(transport), ANALYSIS)
        self.assertIsInstance(result, dict)
        self.assertIs(result.get("delivered"), True)
        self._assert_not_verified(result, changed)


if __name__ == "__main__":
    unittest.main()
