"""Bar for wall-clock stamps on loop(). Red until kit.conductor_loop records them.

This file is the bar. It is frozen. Do not edit it to make it pass.
The Owner, 2026-11-05, revised the escalation clock. A normal
escalation.json carries started_at only. ended_at belongs on the
summary. Do not put ended_at back on that file.

Clock seam, chosen by the Architect: the module binds
`from datetime import datetime, timezone`. Tests replace
kit.conductor_loop.datetime.now. loop() gains no parameter. Patching
keeps the signature unchanged.

Stamp form, chosen by the Architect: timezone-aware ISO 8601 at second
precision with a numeric offset, matching
datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds").
A trailing Z is not an explicit offset. Fractional seconds are not
second precision.

Where the stamps go, chosen by the Architect:
- started_at is taken once, at loop() entry, before _load. It is the
  first datetime.now call.
- summary.json carries started_at and ended_at. ended_at is the wall
  time when the summary is built. A refusal does not write a summary.
- each written round record carries started_at and ended_at. They fall
  inside the job window and are in order across rounds.
- a non-refusal escalation.json carries started_at only, the same
  string as the summary. ended_at belongs on the summary. No ended_at
  and no refused_at on that file. Owner, 2026-11-05. The earlier
  self-contained reading is withdrawn.
- a packet-refused escalation.json carries started_at and refused_at.
  refused_at is a later clock call, not a copy of started_at. No
  ended_at.
- if _load raises, loop() still writes that refusal record, then
  re-raises. No summary. The fixture for that path is held out.
- the offset is the local zone's offset, not a hardcoded +00:00. The
  zone fixture is held out.
- a stop that fires during a round still writes that round's stamps
  inside the job window, in order. The mid-round fixture is held out.
- nothing reads these fields to choose a stop, a state, an outcome, or
  a round count. The deadline and the CLOCK stop stay monotonic.
- the stamps record the clock. They are not clamped. S2 (started_at <=
  ended_at) is scored on a clock that does not move backward. A
  backward jump must not change the stop; it is not required to keep
  the inequality. Loosened in writing: clamping would hide the jump,
  and nothing gates on these fields.
- rounds_sha256 is the sha256 of the written round files, new fields
  included. packet_sha256 stays the hash of the packet bytes.

Do not open evaluator.held_out paths. They are not part of this suite.
"""
import hashlib
import json
import os
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from unittest import mock

from kit.conductor_loop import loop

PY = sys.executable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAMP = __import__("re").compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"
)

SUMMARY_KEYS = {
    "terminal_state", "outcome", "stop", "rounds", "cap", "accepted_round",
    "best_round", "cost", "separation_gaps", "rounds_sha256", "packet_sha256",
    "commit", "escalation", "started_at", "ended_at",
}
ROUND_KEYS = {
    "round", "run", "findings_sha256", "held_out", "evaluator", "reading",
    "pass_rule", "verdict_mismatch", "best_round", "cost", "stop",
    "started_at", "ended_at",
}
ESCALATION_KEYS = {
    "terminal_state", "outcome", "stop", "by", "escalation_kind", "route",
    "human_seat", "holders", "best", "tried", "question", "diagnosis",
    "why_unobservable", "options", "recommendation", "proposed_packet",
    "decision", "packet_sha256", "started_at",
}
REFUSAL_KEYS = {
    "terminal_state", "outcome", "stop", "escalation_kind", "route",
    "human_seat", "holders", "problems", "question", "diagnosis",
    "why_unobservable", "options", "recommendation", "proposed_packet",
    "decision", "started_at", "refused_at",
}
GAP_GATE = (
    "The gate rerun is a script Evaluator reading held in the same module as "
    "Orchestrator dispatch (DOCTRINE D3.holder, rule 5)."
)
GAP_ARCH = (
    "Architect proposed packet not recorded after seeing drafts "
    "(D3.Architect vs Contracts §4.2); Owner ratification required"
)


def _write(root, name, text):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _holders():
    return {
        "architect": "plumbline-architect",
        "orchestrator": [
            {"holder": "kit.conductor_loop.loop", "kind": "script", "does": "rounds", "tested": "rec#abc"},
            {"holder": "escalation-agent", "kind": "model", "does": "escalations", "tested": "rec#def"},
        ],
    }


def _packet(tmp, maker, suite, **over):
    packet = {
        "ratified": True,
        "mode": "scored",
        "human_seat": "Owner",
        "artifact": {
            "test_cmd": suite,
            "frozen": [os.path.join(tmp, "tests", "t.py")],
            "editable": ["src"],
            "ignore": [".git", "__pycache__"],
        },
        "maker": {"cmd": maker, "handoff": "rule12"},
        "evaluator": {
            "kind": "script",
            "cmd": [PY, "-c", "raise SystemExit(0)"],
            "runs": 2,
            "held_out": [],
        },
        "bounds": {
            "T_accept": 1,
            "T_dim": 1,
            "T_reject": 0,
            "cap": 3,
            "cap_counts": "generations",
            "budget": {"amount": 0, "unit": "USD", "time_hours_lt": 2},
        },
        "escalation": {
            "route": ["Architect", "Owner"],
            "classes": [],
            "holders": _holders(),
        },
    }
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(packet.get(key), dict):
            packet[key].update(value)
        else:
            packet[key] = value
    return packet


def _scores(score, verdict="accept"):
    return {
        "dimensions": [{"name": "q", "score": score, "observation": "seen"}],
        "violations": [],
        "verdict": verdict,
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _suite(work):
    return [PY, "-c", "import sys; t=open(%r).read(); sys.exit(0 if t.startswith('yes') else 1)" % work]


def _job(tmp):
    _write(tmp, "tests/t.py", "pin\n")
    _write(tmp, "src/w.txt", "no\n")
    return os.path.join(tmp, "src", "w.txt")


def _maker(work, exit_code=0):
    return [PY, "-c", "open(%r,'w').write('yes\\n'+__import__('time').time().__str__()); raise SystemExit(%d)" % (work, exit_code)]


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _parse(value):
    if not isinstance(value, str) or STAMP.match(value) is None:
        raise AssertionError("not a second-precision offset stamp: %r" % (value,))
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.microsecond != 0:
        raise AssertionError("stamp has no explicit offset: %r" % (value,))
    return parsed


def _local_iso(stamp):
    return stamp.astimezone().isoformat(timespec="seconds")


class _SeqClock:
    """Non-decreasing. One second per call, starting at a fixed UTC instant."""

    def __init__(self):
        self.calls = []
        self.start = datetime(2026, 11, 5, 15, 0, 0, tzinfo=timezone.utc)

    def now(self, tz=None):
        stamp = self.start + timedelta(seconds=len(self.calls))
        self.calls.append(stamp)
        return stamp


class _JumpClock:
    """First call is the start. Later calls jump forward, then back."""

    def __init__(self):
        self.n = 0

    def now(self, tz=None):
        self.n += 1
        if self.n == 1:
            return datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        if self.n % 2 == 0:
            return datetime(2036, 6, 1, 12, 0, self.n, tzinfo=timezone.utc)
        return datetime(2020, 6, 1, 12, 0, self.n, tzinfo=timezone.utc)


def _bind(test, clock):
    import kit.conductor_loop as cl
    clock_cls = getattr(cl, "datetime", None)
    if clock_cls is None:
        test.fail("kit.conductor_loop.datetime is not bound; loop() has no wall clock")
    return mock.patch.object(clock_cls, "now", clock.now)


class StampTests(unittest.TestCase):
    def test_s1_s2_summary_stamps_and_s8_keys_on_accept(self):
        clock = _SeqClock()
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, _maker(work), _suite(work), bounds={"cap": 1})
            with _bind(self, clock):
                summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=lambda record, cwd: _scores(1))
            self.assertEqual(summary["stop"], "accepted")
            self.assertEqual(summary["terminal_state"], "accepted")
            self.assertEqual(set(summary), SUMMARY_KEYS)
            self.assertEqual(summary["separation_gaps"], [])
            self.assertIsNone(summary["escalation"])
            self.assertFalse(os.path.exists(os.path.join(rec, "escalation.json")))
            started = _parse(summary["started_at"])
            ended = _parse(summary["ended_at"])
            self.assertLessEqual(started, ended)
            self.assertEqual(summary["started_at"], _local_iso(clock.calls[0]))
            self.assertIn(_parse(summary["ended_at"]), [_parse(_local_iso(item)) for item in clock.calls])
            on_disk = json.load(open(os.path.join(rec, "summary.json")))
            self.assertEqual(on_disk["started_at"], summary["started_at"])
            self.assertEqual(on_disk["ended_at"], summary["ended_at"])
            raw = json.dumps(packet, sort_keys=True).encode("utf-8")
            self.assertEqual(summary["packet_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertNotIn(summary["started_at"], raw.decode("utf-8"))

    def test_s3_round_stamps_fall_inside_the_job_window_in_order(self):
        clock = _SeqClock()
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, _maker(work), _suite(work))
            packet["bounds"]["cap"] = 2

            def fn(record, cwd):
                score = 0.5 if record["round"] == 1 else 1
                verdict = "regenerate" if record["round"] == 1 else "accept"
                return _scores(score, verdict=verdict)

            with _bind(self, clock):
                summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=fn)
            self.assertEqual(summary["rounds"], 2)
            self.assertEqual(summary["stop"], "accepted")
            job_start = _parse(summary["started_at"])
            job_end = _parse(summary["ended_at"])
            self.assertLessEqual(job_start, job_end)
            previous = job_start
            for number in (1, 2):
                body = json.load(open(os.path.join(rec, "round-%02d.json" % number)))
                self.assertEqual(set(body), ROUND_KEYS)
                self.assertNotIn("refused_at", body)
                started = _parse(body["started_at"])
                ended = _parse(body["ended_at"])
                self.assertLessEqual(started, ended)
                self.assertLessEqual(job_start, started)
                self.assertLessEqual(ended, job_end)
                self.assertLessEqual(previous, started)
                previous = ended
            self.assertEqual(
                summary["rounds_sha256"],
                [_sha(os.path.join(rec, "round-%02d.json" % n)) for n in (1, 2)],
            )

    def test_s4_refusal_stamps_are_taken_before_load(self):
        clock = _SeqClock()
        import kit.conductor_loop as cl
        real_load = cl._load
        seen = {}

        def wrapping(packet):
            seen["calls_before_load"] = len(clock.calls)
            return real_load(packet)

        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, _maker(work), _suite(work))
            packet["ratified"] = False
            with _bind(self, clock), mock.patch.object(cl, "_load", wrapping):
                with self.assertRaises(ValueError):
                    loop(packet, record_dir=rec, cwd=tmp)
            self.assertGreaterEqual(seen.get("calls_before_load", 0), 1)
            self.assertFalse(os.path.exists(os.path.join(rec, "summary.json")))
            body = json.load(open(os.path.join(rec, "escalation.json")))
            self.assertEqual(set(body), REFUSAL_KEYS)
            self.assertEqual(body["stop"], "packet refused")
            self.assertNotIn("ended_at", body)
            self.assertEqual(body["started_at"], _local_iso(clock.calls[0]))
            refused = _parse(body["refused_at"])
            self.assertLessEqual(_parse(body["started_at"]), refused)
            later = [_local_iso(item) for item in clock.calls[seen["calls_before_load"]:] ]
            self.assertIn(body["refused_at"], later)

    def test_s5_cap_floor_and_other_escalations_carry_the_summary_stamps(self):
        cases = (
            ("cap reached", "cap_reached", {"cap": 1}, 0.5, "regenerate", 0),
            ("rejected", "below_floor", {"T_reject": 0.4, "cap": 1}, 0.1, "reject", 0),
            ("maker failed", "other", {"cap": 1}, None, "accept", 1),
        )
        for stop, kind, bounds, score, verdict, maker_exit in cases:
            with self.subTest(stop=stop):
                clock = _SeqClock()
                with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
                    work = _job(tmp)
                    packet = _packet(tmp, _maker(work, maker_exit), _suite(work))
                    packet["bounds"].update(bounds)
                    fn = None if score is None else (lambda record, cwd, s=score, v=verdict: _scores(s, verdict=v))
                    with _bind(self, clock):
                        summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=fn)
                    self.assertEqual(summary["stop"], stop)
                    self.assertEqual(set(summary), SUMMARY_KEYS)
                    body = json.load(open(os.path.join(rec, "escalation.json")))
                    self.assertEqual(set(body), ESCALATION_KEYS)
                    self.assertEqual(body["escalation_kind"], kind)
                    self.assertNotIn("refused_at", body)
                    self.assertNotIn("ended_at", body)
                    self.assertEqual(body["started_at"], summary["started_at"])
                    self.assertIn("ended_at", summary)
                    self.assertEqual(summary["started_at"], _local_iso(clock.calls[0]))
                    self.assertLessEqual(_parse(summary["started_at"]), _parse(summary["ended_at"]))
                    self.assertEqual(summary["separation_gaps"], [GAP_GATE, GAP_ARCH])

    def test_s5_clock_stop_with_no_rounds_still_stamps_the_summary(self):
        clock = _SeqClock()
        import kit.conductor_loop as cl
        calls = {"n": 0}

        def mono():
            calls["n"] += 1
            return 0.0 if calls["n"] == 1 else 1e9

        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, _maker(work), _suite(work))
            with _bind(self, clock), mock.patch.object(cl.time, "monotonic", mono):
                summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=lambda record, cwd: _scores(1))
            self.assertEqual(summary["stop"], "clock")
            self.assertEqual(summary["rounds"], 0)
            self.assertFalse(os.path.exists(os.path.join(rec, "round-01.json")))
            self.assertEqual(set(summary), SUMMARY_KEYS)
            body = json.load(open(os.path.join(rec, "escalation.json")))
            self.assertEqual(body["escalation_kind"], "other")
            self.assertEqual(body["started_at"], summary["started_at"])
            self.assertNotIn("ended_at", body)
            self.assertNotIn("refused_at", body)
            self.assertIn("ended_at", summary)
            self.assertLessEqual(_parse(summary["started_at"]), _parse(summary["ended_at"]))

    def test_s6_wall_clock_jump_does_not_change_stop_state_or_rounds(self):
        def once(clock):
            with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
                work = _job(tmp)
                packet = _packet(tmp, _maker(work), _suite(work), bounds={"cap": 1})
                with _bind(self, clock):
                    summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=lambda record, cwd: _scores(1))
                self.assertIn("started_at", summary)
                self.assertIn("ended_at", summary)
                return summary["stop"], summary["terminal_state"], summary["rounds"]

        steady = once(_SeqClock())
        jumped = once(_JumpClock())
        self.assertEqual(jumped, steady)
        self.assertEqual(steady, ("accepted", "accepted", 1))


class DocTests(unittest.TestCase):
    def test_s9_docstring_and_release_gate_row_name_what_is_recorded(self):
        import kit.conductor_loop as cl
        doc = cl.__doc__ or ""
        self.assertIn("started_at", doc)
        self.assertIn("ended_at", doc)
        row = ""
        with open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8") as fh:
            for line in fh:
                if "Release-gate building block" in line:
                    row = line
                    break
        self.assertNotEqual(row, "")
        self.assertIn("started_at", row)
        self.assertIn("ended_at", row)

    def test_s10_unreleased_added_names_the_stamps(self):
        with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as fh:
            text = fh.read()
        unreleased = text.split("## Unreleased", 1)[1].split("\n## ", 1)[0]
        added = unreleased.split("**Added**", 1)[1].split("**", 1)[0]
        self.assertIn("started_at", added)
        self.assertIn("ended_at", added)


if __name__ == "__main__":
    unittest.main()
