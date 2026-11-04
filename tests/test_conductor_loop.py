"""Bar for the multi-round loop driver. Red until kit.conductor_loop exists."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from tempfile import TemporaryDirectory

from kit.conductor_loop import loop
from kit.conductor_run import run

PY = sys.executable


def _write(root, name, text):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _holders(architect="E-DI Architect (agent)"):
    return {
        "architect": architect,
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
            "budget": {"amount": 0, "unit": "USD", "lt": False, "time_hours_lt": 2},
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


def _scores(pairs, verdict="regenerate", violations=None, controls=None):
    return {
        "dimensions": [
            {"name": name, "score": score, "observation": "seen"}
            for name, score in pairs
        ],
        "violations": violations or [],
        "verdict": verdict,
        "controls": controls or {"should_pass": "passed", "should_fail": "failed"},
    }


def _suite(work):
    return [PY, "-c", "import sys; t=open(%r).read(); sys.exit(0 if t.startswith('yes') else 1)" % work]


def _job(tmp):
    _write(tmp, "tests/t.py", "pin\n")
    _write(tmp, "src/w.txt", "no\n")
    return os.path.join(tmp, "src", "w.txt")


class PacketRefusalTests(unittest.TestCase):
    def test_each_bad_packet_is_refused_before_a_command(self):
        cases = [
            ("ratified", {"ratified": False}),
            ("readings", {"mode": "readings"}),
            ("frozen", {"artifact": {"frozen": []}}),
            ("cap", {"bounds": {"cap": 0}}),
            ("T_reject", {"bounds": {"T_reject": None}}),
            ("time_hours_lt", {"bounds": {"budget": {"time_hours_lt": 0}}}),
            ("runs", {"evaluator": {"runs": 1}}),
            ("handoff", {"maker": {"handoff": "other"}}),
            ("route", {"escalation": {"route": "Owner"}}),
        ]
        for needle, over in cases:
            with self.subTest(needle=needle):
                with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
                    work = _job(tmp)
                    ran = os.path.join(tmp, "ran")
                    maker = [PY, "-c", "open(%r,'w').close()" % ran]
                    packet = _packet(tmp, maker, _suite(work))
                    for key, value in over.items():
                        if isinstance(value, dict) and isinstance(packet.get(key), dict):
                            packet[key].update(value)
                        else:
                            packet[key] = value
                    with self.assertRaises(ValueError) as caught:
                        loop(packet, record_dir=rec, cwd=tmp)
                    self.assertIn(needle, str(caught.exception))
                    self.assertFalse(os.path.exists(ran))
                    body = json.load(open(os.path.join(rec, "escalation.json")))
                    self.assertEqual(body["stop"], "packet refused")
                    self.assertTrue(any(needle in line for line in body["problems"]))

    def test_three_problems_are_three_lines(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, [PY, "-c", "pass"], _suite(work), ratified=False)
            packet["mode"] = "readings"
            packet["bounds"]["cap"] = 0
            with self.assertRaises(ValueError) as caught:
                loop(packet, record_dir=rec, cwd=tmp)
            problems = json.load(open(os.path.join(rec, "escalation.json")))["problems"]
            self.assertGreaterEqual(len(problems), 3)
            self.assertGreaterEqual(str(caught.exception).count(";"), 2)

    def test_holder_and_record_dir_refusals(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, [PY, "-c", "pass"], _suite(work))
            packet["escalation"]["holders"]["orchestrator"][1]["tested"] = "  "
            with self.assertRaises(ValueError) as caught:
                loop(packet, record_dir=rec, cwd=tmp)
            self.assertIn("tested", str(caught.exception))
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, [PY, "-c", "pass"], _suite(work))
            packet["escalation"]["holders"]["orchestrator"] = [
                {"holder": "only-agent", "kind": "model", "does": "escalations", "tested": "rec#x"}
            ]
            with self.assertRaises(ValueError) as caught:
                loop(packet, record_dir=rec, cwd=tmp)
            self.assertIn("script", str(caught.exception))
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(
                tmp, [PY, "-c", "pass"], _suite(work),
            )
            packet["escalation"]["holders"] = _holders("  e-di architect (agent)  ")
            packet["escalation"]["holders"]["orchestrator"][1]["holder"] = "E-DI Architect (agent)"
            with self.assertRaises(ValueError) as caught:
                loop(packet, record_dir=rec, cwd=tmp)
            self.assertIn("architect", str(caught.exception).lower())
        with TemporaryDirectory() as tmp:
            work = _job(tmp)
            inside = os.path.join(tmp, "records")
            os.makedirs(inside)
            with self.assertRaises(ValueError) as caught:
                loop(_packet(tmp, [PY, "-c", "pass"], _suite(work)), record_dir=inside, cwd=tmp)
            self.assertIn("record_dir", str(caught.exception))
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            _write(rec, "already.txt", "x")
            with self.assertRaises(ValueError) as caught:
                loop(_packet(tmp, [PY, "-c", "pass"], _suite(work)), record_dir=rec, cwd=tmp)
            self.assertIn("record_dir", str(caught.exception))


class LoopTests(unittest.TestCase):
    def _low(self, calls, score=0.5, violations=None, verdict="regenerate"):
        def fn(record, cwd):
            calls.append(record["round"])
            return _scores([("q", score)], verdict=verdict, violations=violations)
        return fn

    def test_cap_writes_the_escalation_record(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            calls = []
            maker = [PY, "-c", "open(%r,'w').write('yes\\n'+__import__('time').time().__str__())" % work]
            packet = _packet(tmp, maker, _suite(work))
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=self._low(calls))
            self.assertEqual(summary["terminal_state"], "needs_owner")
            self.assertEqual(summary["stop"], "cap reached")
            self.assertEqual(len(summary["rounds_sha256"]), 3)
            self.assertEqual(len(calls), 6)
            body = json.load(open(os.path.join(rec, "escalation.json")))
            self.assertEqual(body["escalation_kind"], "cap_reached")
            self.assertEqual(body["route"], ["Architect", "Owner"])
            self.assertEqual(body["human_seat"], "Owner")
            self.assertEqual(body["holders"], packet["escalation"]["holders"])
            self.assertTrue(body["best"]["editable"])
            self.assertEqual(len(body["tried"]), 3)
            for row in body["tried"]:
                self.assertEqual(row["record_sha256"], _sha(row["record"]))
            for key in ("question", "diagnosis", "why_unobservable", "options", "recommendation", "proposed_packet", "decision"):
                self.assertIsNone(body[key])
            self.assertFalse(os.path.exists(os.path.join(rec, "round-04.json")))

    def test_accepted_on_round_2_and_rejected_on_round_1(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            calls = []
            def fn(record, cwd):
                calls.append(record["round"])
                score = 0.5 if record["round"] == 1 else 1
                return _scores([("q", score)], verdict="reject")
            maker = [PY, "-c", "open(%r,'w').write('yes\\n'+__import__('time').time().__str__())" % work]
            summary = loop(_packet(tmp, maker, _suite(work)), record_dir=rec, cwd=tmp, evaluator_fn=fn)
            self.assertEqual(summary["terminal_state"], "accepted")
            self.assertEqual(summary["accepted_round"], 2)
            self.assertTrue(json.load(open(os.path.join(rec, "round-02.json")))["verdict_mismatch"])
            self.assertFalse(os.path.exists(os.path.join(rec, "round-03.json")))
            self.assertFalse(os.path.exists(os.path.join(rec, "escalation.json")))
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, [PY, "-c", "open(%r,'w').write('yes\\n')" % work], _suite(work))
            packet["bounds"]["T_reject"] = 0.4
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=self._low([], score=0.1, verdict="reject"))
            self.assertEqual(summary["terminal_state"], "rejected")
            self.assertEqual(summary["outcome"], "rejected")
            body = json.load(open(os.path.join(rec, "escalation.json")))
            self.assertEqual(body["escalation_kind"], "below_floor")

    def test_findings_reach_round_2_and_a_red_rerun_skips_the_judge(self):
        token = "TOKEN-round1-only"
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            got = os.path.join(tmp, "src", "got.txt")
            maker = [PY, "-c",
                     "import os; open(%r,'w').write('yes\\n'+__import__('time').time().__str__());"
                     "open(%r,'w').write(open(os.environ['PLUMBLINE_FINDINGS']).read())" % (work, got)]
            calls = []
            def fn(record, cwd):
                calls.append(1)
                return _scores([("q", 0.5)], violations=[{
                    "id": "V1", "class": "artifact_missed_standard", "dimension": "q",
                    "observation": token, "remedy": "fix it",
                }])
            packet = _packet(tmp, maker, _suite(work))
            packet["bounds"]["cap"] = 2
            loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=fn)
            self.assertIn(token, open(got).read())
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            calls = []
            maker = [PY, "-c", "open(%r,'w').write('still-no\\n'+__import__('time').time().__str__())" % work]
            packet = _packet(tmp, maker, _suite(work))
            packet["bounds"]["cap"] = 2
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=self._low(calls))
            self.assertEqual(calls, [])
            self.assertTrue(os.path.exists(os.path.join(rec, "round-02.json")))
            self.assertEqual(json.load(open(os.path.join(rec, "round-01.json")))["reading"]["from"], "gate")
            self.assertEqual(summary["rounds"], 2)

    def test_best_artifact_and_no_reset(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            extra = os.path.join(tmp, "src", "extra.txt")
            saw = os.path.join(tmp, "src", "saw.txt")
            maker = [PY, "-c",
                     "import json,os,time; f=json.load(open(os.environ['PLUMBLINE_FINDINGS']));"
                     "open(%r,'w').write('yes\\n'+str(time.time()));"
                     "open(%r,'w').write('yes' if os.path.exists(%r) else 'no');"
                     "open(%r,'w').write('from-'+str(f['round'])) if f['round']>=2 else None"
                     % (work, saw, extra, extra)]
            def fn(record, cwd):
                if record["round"] == 1:
                    return _scores([("a", 0.6), ("b", 0.6)])
                if record["round"] == 2:
                    return _scores([("a", 0.9), ("b", 0.3)])
                return _scores([("a", 0.6), ("b", 0.6)])
            summary = loop(_packet(tmp, maker, _suite(work)), record_dir=rec, cwd=tmp, evaluator_fn=fn)
            self.assertEqual(summary["best_round"], 1)
            self.assertEqual(json.load(open(os.path.join(rec, "round-03.json")))["best_round"], 1)
            self.assertEqual(open(saw).read(), "no")
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            marker = os.path.join(tmp, "src", "from2.txt")
            saw = os.path.join(tmp, "src", "saw2.txt")
            maker = [PY, "-c",
                     "import json,os,time; f=json.load(open(os.environ['PLUMBLINE_FINDINGS']));"
                     "open(%r,'w').write('yes\\n'+str(time.time()));"
                     "open(%r,'w').write('yes' if os.path.exists(%r) else 'no');"
                     "open(%r,'w').write('2') if f['round']==2 else None"
                     % (work, saw, marker, marker)]
            def fn(record, cwd):
                if record["round"] == 1:
                    return _scores([("a", 0.5), ("b", 0.5)])
                return _scores([("a", 0.7), ("b", 0.5)])
            summary = loop(_packet(tmp, maker, _suite(work)), record_dir=rec, cwd=tmp, evaluator_fn=fn)
            self.assertEqual(summary["best_round"], 2)
            self.assertEqual(open(saw).read(), "yes")

    def test_green_base_is_refused_only_on_round_1(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            _write(tmp, "src/w.txt", "yes\n")
            summary = loop(
                _packet(tmp, [PY, "-c", "open(%r,'w').write('ran')" % os.path.join(tmp, "ran")], _suite(work)),
                record_dir=rec, cwd=tmp, evaluator_fn=self._low([]),
            )
            self.assertEqual(summary["stop"], "not dispatched")
            self.assertFalse(os.path.exists(os.path.join(tmp, "ran")))
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            calls = []
            maker = [PY, "-c", "open(%r,'w').write('yes\\n'+__import__('time').time().__str__())" % work]
            packet = _packet(tmp, maker, _suite(work))
            packet["bounds"]["cap"] = 2
            loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=self._low(calls))
            second = json.load(open(os.path.join(rec, "round-02.json")))
            self.assertTrue(second["run"]["dispatched"])
            self.assertNotEqual(second["run"]["reason"], "no RED")

    def test_held_out_and_escalation_class(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as held, TemporaryDirectory() as rec:
            secret = _write(held, "case-a.txt", "SECRET-LINE\n")
            work = _job(tmp)
            maker = [PY, "-c", "import os; open(%r,'w').write('yes\\n'); open('src/got.txt','w').write(open(os.environ['PLUMBLINE_FINDINGS']).read())" % work]
            def fn(record, cwd):
                return _scores([("q", 0.5)], violations=[{
                    "id": "V1", "class": "artifact_missed_standard", "observation": "x",
                    "remedy": "see SECRET-LINE",
                }])
            packet = _packet(tmp, maker, _suite(work))
            packet["evaluator"]["held_out"] = [secret]
            packet["bounds"]["cap"] = 2
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=fn)
            self.assertEqual(summary["stop"], "held-out leak")
            self.assertFalse(os.path.exists(os.path.join(rec, "findings-02.json")))
            for name in os.listdir(rec):
                if name.startswith("findings"):
                    self.assertNotIn("SECRET-LINE", open(os.path.join(rec, name)).read())
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            maker = [PY, "-c", "open(%r,'w').write('yes\\n')" % work]
            def fn(record, cwd):
                return _scores([("q", 1)], verdict="accept", violations=[{
                    "id": "V9", "class": "frame_at_fault", "observation": "frame",
                }])
            packet = _packet(tmp, maker, _suite(work))
            packet["escalation"]["classes"] = ["frame_at_fault"]
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=fn)
            self.assertEqual(summary["stop"], "escalation class")
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            maker = [PY, "-c", "open(%r,'w').write('yes\\n')" % work]
            def fn(record, cwd):
                return _scores([("q", 1)], verdict="accept", violations=[{
                    "id": "V9", "class": "frame_at_fault", "observation": "frame",
                }])
            summary = loop(_packet(tmp, maker, _suite(work)), record_dir=rec, cwd=tmp, evaluator_fn=fn)
            self.assertEqual(summary["terminal_state"], "accepted")

    def test_proposed_packet_is_not_run(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, [PY, "-c", "open(%r,'w').write('yes\\n')" % work], _suite(work))
            packet["bounds"]["cap"] = 1
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=self._low([]))
            self.assertGreaterEqual(len(summary["separation_gaps"]), 2)
            body = json.load(open(os.path.join(rec, "escalation.json")))
            body["proposed_packet"] = {"path": os.path.join(tmp, "next.json"), "sha256": "abc"}
            json.dump(body, open(os.path.join(rec, "escalation.json"), "w"))
            self.assertFalse(os.path.exists(os.path.join(rec, "round-02.json")))
            nxt = dict(packet)
            nxt["ratified"] = False
            with TemporaryDirectory() as rec2:
                with self.assertRaises(ValueError) as caught:
                    loop(nxt, record_dir=rec2, cwd=tmp)
                self.assertIn("ratified", str(caught.exception))
            with self.assertRaises(ValueError) as caught:
                loop(packet, record_dir=rec, cwd=tmp)
            self.assertIn("record_dir", str(caught.exception))

    def test_tamper_stops_before_the_evaluator(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            frozen = os.path.join(tmp, "tests", "t.py")
            calls = []
            maker = [PY, "-c",
                     "import json,os; f=json.load(open(os.environ['PLUMBLINE_FINDINGS']));"
                     "open(%r,'w').write('yes\\n');"
                     "open(%r,'w').write('tamper') if f['round']>=2 else None" % (work, frozen)]
            packet = _packet(tmp, maker, _suite(work))
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=self._low(calls, score=0.5))
            self.assertEqual(summary["stop"], "tampered")
            self.assertEqual(summary["rounds"], 2)
            self.assertEqual(calls, [1, 1])
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            calls = []
            maker = [PY, "-c",
                     "import json,os; f=json.load(open(os.environ['PLUMBLINE_FINDINGS']));"
                     "open(%r,'w').write('yes\\n');"
                     "open('sneak.txt','w').write('x') if f['round']>=2 else None" % work]
            summary = loop(_packet(tmp, maker, _suite(work)), record_dir=rec, cwd=tmp, evaluator_fn=self._low(calls))
            self.assertEqual(summary["stop"], "tampered")
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            def fn(record, cwd):
                open(os.path.join(cwd, "from-eval.txt"), "w").write("x")
                return _scores([("q", 0.5)])
            summary = loop(
                _packet(tmp, [PY, "-c", "open(%r,'w').write('yes\\n')" % work], _suite(work)),
                record_dir=rec, cwd=tmp, evaluator_fn=fn,
            )
            self.assertEqual(summary["stop"], "tampered")
            body = json.load(open(os.path.join(rec, "escalation.json")))
            self.assertEqual(body["by"], "evaluator")

    def test_evaluator_problems_do_not_raise(self):
        def run_case(evaluator, cmd=None):
            with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
                work = _job(tmp)
                packet = _packet(tmp, [PY, "-c", "open(%r,'w').write('yes\\n')" % work], _suite(work))
                if cmd:
                    packet["evaluator"]["cmd"] = cmd
                    summary = loop(packet, record_dir=rec, cwd=tmp, timeout_s=1)
                else:
                    summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=evaluator, timeout_s=1)
                self.assertEqual(summary["terminal_state"], "needs_owner")
                self.assertEqual(summary["outcome"], "no_observation")
                self.assertTrue(os.path.exists(os.path.join(rec, "round-01.json")))
                self.assertTrue(os.path.exists(os.path.join(rec, "escalation.json")))
                return summary["stop"]
        self.assertEqual(run_case(None, [PY, "-c", "raise SystemExit(2)"]), "evaluator failed")
        self.assertEqual(run_case(None, [PY, "-c", "import time; time.sleep(30)"]), "evaluator failed")
        self.assertEqual(run_case(None, [PY, "-c", "print('nope')"]), "evaluator failed")
        self.assertEqual(run_case(lambda record, cwd: (_ for _ in ()).throw(RuntimeError("no"))), "evaluator failed")
        self.assertEqual(
            run_case(lambda record, cwd: _scores([("q", 1)], verdict="accept") | {"dimensions": [{"name": "q", "score": 1, "observation": ""}]}),
            "no observation",
        )
        self.assertEqual(
            run_case(lambda record, cwd: _scores([("q", 1)], controls={"should_pass": "failed", "should_fail": "failed"})),
            "instrument failed",
        )
        state = {"n": 0}
        def split(record, cwd):
            state["n"] += 1
            return _scores([("q", 0.2 if state["n"] == 1 else 0.9)])
        self.assertEqual(run_case(split), "evaluator split")

    def test_maker_and_bounds(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            summary = loop(
                _packet(tmp, [PY, "-c", "raise SystemExit(3)"], _suite(work)),
                record_dir=rec, cwd=tmp, evaluator_fn=self._low([]),
            )
            self.assertEqual(summary["stop"], "maker failed")
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            summary = loop(
                _packet(tmp, [PY, "-c", "import time; time.sleep(30)"], _suite(work)),
                record_dir=rec, cwd=tmp, timeout_s=1, evaluator_fn=self._low([]),
            )
            self.assertEqual(summary["stop"], "timeout")
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            summary = loop(
                _packet(tmp, [PY, "-c", "pass"], _suite(work)),
                record_dir=rec, cwd=tmp, evaluator_fn=self._low([]),
            )
            self.assertEqual(summary["stop"], "no artifact")
            self.assertEqual(summary["outcome"], "no_artifact")
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, [PY, "-c", "import time; time.sleep(30)"], _suite(work))
            packet["bounds"]["budget"]["time_hours_lt"] = 0.0004
            summary = loop(packet, record_dir=rec, cwd=tmp, timeout_s=600, evaluator_fn=self._low([]))
            self.assertEqual(summary["stop"], "clock")
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            maker = [PY, "-c",
                     "import json,os; open(%r,'w').write('yes\\n');"
                     "json.dump({'amount': 1.0}, open(os.environ['PLUMBLINE_COST'],'w'))" % work]
            packet = _packet(tmp, maker, _suite(work))
            packet["bounds"]["budget"]["amount"] = 1
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=self._low([]))
            self.assertEqual(summary["stop"], "budget")
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, [PY, "-c", "open(%r,'w').write('yes\\n')" % work], _suite(work))
            packet["bounds"]["budget"]["amount"] = 1
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=self._low([]))
            self.assertEqual(summary["stop"], "budget unmeasured")


class GatePinTests(unittest.TestCase):
    def test_require_red_default_matches_the_published_gate(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt", "pin\n")
            refused = run([PY, "-c", "raise SystemExit(0)"], [frozen], [], [PY, "-c", "pass"], cwd=tmp)
            self.assertFalse(refused["dispatched"])
            self.assertEqual(refused["reason"], "no RED")
            allowed = run(
                [PY, "-c", "raise SystemExit(0)"], [frozen], ["src"],
                [PY, "-c", "import os; os.makedirs('src', exist_ok=True); open('src/a','w').write('1')"],
                cwd=tmp, require_red=False,
            )
            self.assertTrue(allowed["dispatched"])
            self.assertNotEqual(allowed["reason"], "no RED")

    def test_maker_env_does_not_reach_the_suite(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt", "pin\n")
            suite = [PY, "-c", "import os,sys; sys.exit(0 if os.environ.get('PLUMBLINE_SECRET') else 1)"]
            maker = [PY, "-c", "import os; os.makedirs('src', exist_ok=True); open('src/seen','w').write(os.environ.get('PLUMBLINE_SECRET',''))"]
            result = run(
                suite, [frozen], ["src"], maker, cwd=tmp,
                maker_env={"PLUMBLINE_SECRET": "only-maker"},
            )
            self.assertNotEqual(result["red"]["exit"], 0)
            self.assertEqual(open(os.path.join(tmp, "src", "seen")).read(), "only-maker")


def _sha(path):
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


if __name__ == "__main__":
    unittest.main()
