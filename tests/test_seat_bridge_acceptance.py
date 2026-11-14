"""Frozen acceptance bar for kit/seat_bridge.py (job 2026-11-13-kit-bridge).

Written by the E-DI Architect before any candidate exists. The Maker copies this file byte for
byte to tests/test_seat_bridge_acceptance.py and never edits it (bar.md K1, G1). Red at BASE
943f41c: kit/seat_bridge.py does not exist there.

The interface it pins is bar.md section 3. The seats are played by fakes in this file: a fake
Maker bot and a fake Evaluator bot that answer the bridge's request files the way the real bots
are told to (atomic rename). No network, no model, no bot, no paid call.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import kit.conductor_loop as cl  # noqa: E402
from kit.conductor_run import run  # noqa: E402

# The commit this bar was written at; kit/preflight.py L30-32 checks it against the worktree HEAD.
BASE_COMMIT = "943f41cb9900b8e4234b328d5b6365450c74736b"
BRIDGE = os.path.join(REPO, "kit", "seat_bridge.py")
PY = sys.executable
POLL = ["--poll", "0.05"]
WAIT = 15.0


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _put(path, obj):
    """Write JSON the way a seat is told to: a .part file, then an atomic rename."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part = path + ".part"
    with open(part, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    os.replace(part, path)


def _wait_for(path, proc=None, seconds=WAIT):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if os.path.isfile(path):
            return True
        if proc is not None and proc.poll() is not None:
            return os.path.isfile(path)
        time.sleep(0.02)
    return False


def _tree(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            with open(path, "rb") as fh:
                out[os.path.relpath(path, root)] = _sha(fh.read())
    return out


def _env(**extra):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra)
    return env


def _stop(proc):
    """Kill if still running, then reap. Safe to call more than once and after communicate():
    with stdin=DEVNULL and stderr=STDOUT, communicate() reads stdout directly and closes it, so a
    second communicate() would read a closed pipe (pre-freeze review B1)."""
    if proc.poll() is None:
        proc.kill()
    if proc.stdout is not None and not proc.stdout.closed:
        proc.communicate()
    else:
        proc.wait()


def _bare_env(**extra):
    """_env() without the loop's inputs, plus exactly the ones given (bar.md section 3, step 1 of each command)."""
    env = _env()
    for name in ("PLUMBLINE_FINDINGS", "PLUMBLINE_TURN", "PLUMBLINE_COST"):
        env.pop(name, None)
    env.update(extra)
    return env


def _bad_input_exit(test, argv, cwd, env):
    """Start a bridge command on a bad input; it must exit by itself, non-zero, within WAIT."""
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    test.addCleanup(_stop, proc)
    try:
        proc.communicate(timeout=WAIT)
    except subprocess.TimeoutExpired:
        test.fail("the command did not exit on a bad input within %.0f s" % WAIT)
    test.assertNotEqual(proc.returncode, 0, "a bad input exited 0")


def _clear(root):
    for name in os.listdir(root):
        path = os.path.join(root, name)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


def _reading(score, verdict, bridge):
    return {
        "dimensions": [{"name": "q", "score": score, "observation": "seen"}],
        "violations": [],
        "verdict": verdict,
        "controls": {"should_pass": "passed", "should_fail": "failed"},
        "bridge": bridge,
    }


class MakerCommandTests(unittest.TestCase):
    def setUp(self):
        self._dirs = [tempfile.TemporaryDirectory() for _ in range(2)]
        self.rec, self.work = (os.path.realpath(d.name) for d in self._dirs)
        for d in self._dirs:
            self.addCleanup(d.cleanup)
        with open(os.path.join(self.work, "w.txt"), "w") as fh:
            fh.write("no\n")
        self.exit_file = os.path.join(self.rec, "aider-exit.json")
        self.dispatch = os.path.join(self.rec, "aider-dispatch.json")

    def _start(self, number=1, findings=None):
        findings = findings or {"round": number, "cap": 2, "best": None, "defects": [], "solutions": []}
        self.findings_path = os.path.join(self.rec, "findings-%02d.json" % number)
        with open(self.findings_path, "w") as fh:
            json.dump(findings, fh)
        self.findings = findings
        self.cost = os.path.join(self.rec, "cost-%02d-maker.json" % number)
        proc = subprocess.Popen(
            [PY, BRIDGE, "maker", *POLL], cwd=self.work,
            env=_env(PLUMBLINE_FINDINGS=self.findings_path, PLUMBLINE_COST=self.cost),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self.addCleanup(_stop, proc)
        return proc

    def _dispatched(self, proc, number):
        end = time.monotonic() + WAIT
        while time.monotonic() < end:
            if os.path.isfile(self.dispatch):
                try:
                    body = json.load(open(self.dispatch))
                except ValueError:
                    body = None
                if isinstance(body, dict) and body.get("round") == number:
                    return body
            if proc.poll() is not None:
                break
            time.sleep(0.02)
        self.fail("no aider-dispatch.json for round %d (exit %r)" % (number, proc.poll()))

    def test_a01_request_dispatch_block_then_exit_and_cost(self):
        before = _tree(self.work)
        proc = self._start(1)
        body = self._dispatched(proc, 1)
        request = os.path.join(self.rec, "bridge", "maker-request-01.json")
        self.assertEqual(body["request"], request)
        raw = open(request, "rb").read()
        self.assertEqual(body["request_sha256"], _sha(raw))
        self.assertEqual(body["exit_file"], self.exit_file)
        req = json.loads(raw.decode("utf-8"))
        self.assertEqual(req["kind"], "maker_request")
        self.assertEqual(req["round"], 1)
        self.assertEqual(req["findings"], self.findings)
        self.assertEqual(req["findings_sha256"], _sha(open(self.findings_path, "rb").read()))
        self.assertEqual(req["exit_file"], self.exit_file)
        self.assertEqual(req["cwd"], self.work)
        self.assertTrue(str(req.get("written_at") or "").strip())
        time.sleep(0.6)
        self.assertIsNone(proc.poll(), "maker returned before the Maker's exit record existed")
        self.assertFalse(os.path.exists(self.cost), "a cost file was written before the seat declared one")
        _put(self.exit_file, {"round": 1, "request_sha256": body["request_sha256"], "exit": 0, "cost_usd": 0})
        self.assertEqual(proc.wait(WAIT), 0)
        self.assertEqual(json.load(open(self.cost))["amount"], 0)
        self.assertEqual(_tree(self.work), before, "the bridge wrote inside cwd")
        log = os.path.join(self.rec, "bridge", "log.jsonl")
        lines = [json.loads(line) for line in open(log) if line.strip()]
        self.assertTrue(lines)
        for line in lines:
            self.assertTrue(line.get("at") and line.get("event"))

    def test_a02_nonzero_exit_record_and_declared_cost_pass_through(self):
        proc = self._start(1)
        body = self._dispatched(proc, 1)
        _put(self.exit_file, {"round": 1, "request_sha256": body["request_sha256"], "exit": 1, "cost_usd": 0.25})
        self.assertNotEqual(proc.wait(WAIT), 0)
        self.assertEqual(json.load(open(self.cost))["amount"], 0.25)

    def test_a03_stale_exit_record_is_kept_and_never_ends_the_turn(self):
        stale = json.dumps({"round": 1, "request_sha256": "0" * 64, "exit": 0, "cost_usd": 0}).encode()
        with open(self.exit_file, "wb") as fh:
            fh.write(stale)
        proc = self._start(2)
        body = self._dispatched(proc, 2)
        self.assertFalse(os.path.exists(self.exit_file), "the stale exit record was left in place")
        kept = [p for p in _tree(os.path.join(self.rec, "bridge")).values() if p == _sha(stale)]
        self.assertTrue(kept, "the stale exit record's bytes were not kept under bridge/")
        time.sleep(0.6)
        self.assertIsNone(proc.poll(), "the turn ended on a stale exit record")
        _put(self.exit_file, {"round": 2, "request_sha256": body["request_sha256"], "exit": 0, "cost_usd": 0})
        self.assertEqual(proc.wait(WAIT), 0)

    def test_a04_mismatched_exit_record_never_ends_the_turn_as_success(self):
        for wrong in ({"round": 1, "request_sha256": "f" * 64, "exit": 0, "cost_usd": 0},
                      {"round": 9, "request_sha256": None, "exit": 0, "cost_usd": 0}):
            with self.subTest(wrong=wrong):
                _clear(self.rec)
                proc = self._start(1)
                body = self._dispatched(proc, 1)
                if wrong["request_sha256"] is None:
                    wrong = dict(wrong, request_sha256=body["request_sha256"])
                _put(self.exit_file, wrong)
                time.sleep(1.5)
                self.assertNotEqual(proc.poll(), 0, "a mismatched exit record ended the turn with 0")
                _stop(proc)

    def test_a05_missing_or_malformed_cost_writes_no_cost_file(self):
        for cost in (None, -1, "0", True):
            with self.subTest(cost=cost):
                _clear(self.rec)
                proc = self._start(1)
                body = self._dispatched(proc, 1)
                record = {"round": 1, "request_sha256": body["request_sha256"], "exit": 0}
                if cost is not None:
                    record["cost_usd"] = cost
                _put(self.exit_file, record)
                self.assertEqual(proc.wait(WAIT), 0)
                self.assertFalse(os.path.exists(self.cost), "a cost the seat did not declare was written")

    def test_a06_silent_maker_is_a_timeout_through_run(self):
        os.makedirs(os.path.join(self.work, "tests"))
        with open(os.path.join(self.work, "tests", "bar.py"), "w") as fh:
            fh.write("import sys\nsys.exit(1)\n")
        findings = os.path.join(self.rec, "findings-01.json")
        with open(findings, "w") as fh:
            json.dump({"round": 1, "cap": 1, "best": None, "defects": [], "solutions": []}, fh)
        started = time.monotonic()
        result = run(
            [PY, "tests/bar.py"], ["tests/bar.py"], ["w.txt"], [PY, BRIDGE, "maker", *POLL],
            cwd=self.work, timeout_s=3,
            maker_env={"PLUMBLINE_FINDINGS": findings,
                       "PLUMBLINE_COST": os.path.join(self.rec, "cost-01-maker.json")},
            await_exit_file=self.exit_file, await_dispatch_file=self.dispatch,
        )
        self.assertEqual(result["reason"], "timeout", result)
        self.assertLess(time.monotonic() - started, 30)


    def test_a11_bad_input_exits_nonzero_before_any_dispatch(self):
        # bar.md section 3, maker step 1: a missing or unreadable input, or an N that disagrees with the
        # cost-NN-maker.json name, exits non-zero before writing a dispatch file.
        self.assertTrue(os.path.isfile(BRIDGE), "kit/seat_bridge.py is absent")
        findings = os.path.join(self.rec, "findings-01.json")
        good = json.dumps({"round": 1, "cap": 2, "best": None, "defects": [], "solutions": []})
        cost1 = os.path.join(self.rec, "cost-01-maker.json")
        cost2 = os.path.join(self.rec, "cost-02-maker.json")
        for case, text, env in (
                ("PLUMBLINE_FINDINGS unset", good, {"PLUMBLINE_COST": cost1}),
                ("PLUMBLINE_COST unset", good, {"PLUMBLINE_FINDINGS": findings}),
                ("findings file missing", None, {"PLUMBLINE_FINDINGS": findings, "PLUMBLINE_COST": cost1}),
                ("findings not JSON", '{"round": 1,', {"PLUMBLINE_FINDINGS": findings, "PLUMBLINE_COST": cost1}),
                ("round 1 but cost-02-maker.json", good, {"PLUMBLINE_FINDINGS": findings, "PLUMBLINE_COST": cost2})):
            with self.subTest(case=case):
                _clear(self.rec)
                if text is not None:
                    with open(findings, "w") as fh:
                        fh.write(text)
                _bad_input_exit(self, [PY, BRIDGE, "maker", *POLL], self.work, _bare_env(**env))
                self.assertFalse(os.path.exists(self.dispatch), "a dispatch file was written for a bad input")


class EvaluatorCommandTests(unittest.TestCase):
    def setUp(self):
        self._dirs = [tempfile.TemporaryDirectory() for _ in range(2)]
        self.rec, self.work = (os.path.realpath(d.name) for d in self._dirs)
        for d in self._dirs:
            self.addCleanup(d.cleanup)
        with open(os.path.join(self.work, "w.txt"), "w") as fh:
            fh.write("yes\n")

    def _start(self, number=1, index=1):
        self.turn = {"round": number, "artifact": os.path.join(self.rec, "round-%02d" % number, "editable"),
                     "artifact_sha256": "a" * 64, "gate": {"passed": True}}
        self.turn_text = json.dumps(self.turn)
        self.cost = os.path.join(self.rec, "cost-%02d-eval-%d.json" % (number, index))
        self.request = os.path.join(self.rec, "bridge", "eval-request-%02d-%d.json" % (number, index))
        proc = subprocess.Popen(
            [PY, BRIDGE, "evaluator", *POLL], cwd=self.work,
            env=_env(PLUMBLINE_TURN=self.turn_text, PLUMBLINE_COST=self.cost),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self.addCleanup(_stop, proc)
        self.assertTrue(_wait_for(self.request, proc), "no eval request (exit %r)" % proc.poll())
        time.sleep(0.05)
        return proc

    def _req(self):
        raw = open(self.request, "rb").read()
        return json.loads(raw.decode("utf-8")), _sha(raw)

    def test_a07_request_block_then_print_the_reading_verbatim(self):
        before = _tree(self.work)
        proc = self._start(1, 1)
        req, req_sha = self._req()
        self.assertEqual(req["kind"], "eval_request")
        self.assertEqual(req["round"], 1)
        self.assertEqual(req["run"], 1)
        self.assertEqual(req["turn"], self.turn)
        self.assertEqual(req["turn_sha256"], _sha(self.turn_text.encode("utf-8")))
        reading_file = os.path.join(self.rec, "bridge", "eval-reading-01-1.json")
        self.assertEqual(req["reading_file"], reading_file)
        self.assertTrue(str(req.get("written_at") or "").strip())
        time.sleep(0.6)
        self.assertIsNone(proc.poll(), "evaluator returned before the reading existed")
        _put(reading_file, _reading(1, "accept", {"round": 1, "run": 1, "request_sha256": req_sha, "cost_usd": 0}))
        out, _ = proc.communicate(timeout=WAIT)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(out, open(reading_file, "rb").read(), "combined output is not the reading's bytes")
        self.assertEqual(json.load(open(self.cost))["amount"], 0)
        self.assertEqual(_tree(self.work), before, "the bridge wrote inside cwd")

    def test_a08_mismatched_reading_is_never_printed_as_success(self):
        for field, value in (("run", 0), ("round", 2), ("request_sha256", "e" * 64)):
            with self.subTest(field=field):
                _clear(self.rec)
                proc = self._start(1, 1)
                req, req_sha = self._req()
                bridge = {"round": 1, "run": 1, "request_sha256": req_sha, "cost_usd": 0}
                bridge[field] = value
                _put(req["reading_file"], _reading(1, "accept", bridge))
                time.sleep(1.5)
                self.assertNotEqual(proc.poll(), 0, "a reading for another request was printed with exit 0")
                _stop(proc)

    def test_a09_partial_reading_is_waited_on(self):
        proc = self._start(1, 0)
        req, req_sha = self._req()
        with open(req["reading_file"], "w") as fh:
            fh.write('{"dimensions": [')
        time.sleep(0.6)
        self.assertIsNone(proc.poll(), "a partial reading ended the run")
        full = _reading(1, "accept", {"round": 1, "run": 0, "request_sha256": req_sha, "cost_usd": 0})
        with open(req["reading_file"], "w") as fh:
            json.dump(full, fh)
        out, _ = proc.communicate(timeout=WAIT)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(out.decode("utf-8")), full)

    def test_a10_missing_cost_prints_but_writes_no_cost_file(self):
        proc = self._start(1, 1)
        req, req_sha = self._req()
        _put(req["reading_file"], _reading(1, "accept", {"round": 1, "run": 1, "request_sha256": req_sha}))
        proc.communicate(timeout=WAIT)
        self.assertEqual(proc.returncode, 0)
        self.assertFalse(os.path.exists(self.cost), "a cost the seat did not declare was written")


    def test_a12_bad_input_exits_nonzero(self):
        # bar.md section 3, evaluator step 1: a disagreement (N against the cost-NN-eval-I.json name) or an
        # unreadable input exits non-zero.
        self.assertTrue(os.path.isfile(BRIDGE), "kit/seat_bridge.py is absent")
        turn = json.dumps({"round": 1, "artifact": os.path.join(self.rec, "round-01", "editable"),
                           "artifact_sha256": "a" * 64, "gate": {"passed": True}})
        cost1 = os.path.join(self.rec, "cost-01-eval-1.json")
        cost2 = os.path.join(self.rec, "cost-02-eval-1.json")
        for case, env in (
                ("PLUMBLINE_TURN unset", {"PLUMBLINE_COST": cost1}),
                ("PLUMBLINE_COST unset", {"PLUMBLINE_TURN": turn}),
                ("turn not JSON", {"PLUMBLINE_TURN": '{"round": 1,', "PLUMBLINE_COST": cost1}),
                ("round 1 but cost-02-eval-1.json", {"PLUMBLINE_TURN": turn, "PLUMBLINE_COST": cost2})):
            with self.subTest(case=case):
                _clear(self.rec)
                _bad_input_exit(self, [PY, BRIDGE, "evaluator", *POLL], self.work, _bare_env(**env))

    def test_a13_evaluator_appends_its_log(self):
        # bar.md section 3, both commands: one JSON line per event, at least at and event, in R/bridge/log.jsonl.
        proc = self._start(1, 1)
        req, req_sha = self._req()
        _put(req["reading_file"], _reading(1, "accept", {"round": 1, "run": 1, "request_sha256": req_sha, "cost_usd": 0}))
        proc.communicate(timeout=WAIT)
        self.assertEqual(proc.returncode, 0)
        log = os.path.join(self.rec, "bridge", "log.jsonl")
        self.assertTrue(os.path.isfile(log), "no bridge/log.jsonl after an evaluator run")
        lines = [json.loads(line) for line in open(log) if line.strip()]
        self.assertTrue(lines)
        for line in lines:
            self.assertIsInstance(line, dict)
            self.assertTrue(line.get("at") and line.get("event"))


class FakeSeats(threading.Thread):
    """Answers the bridge's files as the E-DI Maker and E-DI Evaluator bots are told to."""

    def __init__(self, rec, work_file, readings, maker_cost=0, maker_silent=False):
        super().__init__(daemon=True)
        self.rec, self.work_file, self.readings = rec, work_file, readings
        self.maker_cost, self.maker_silent = maker_cost, maker_silent
        self.halt = threading.Event()
        self.maker_rounds, self.eval_done = [], set()

    def run(self):
        dispatch = os.path.join(self.rec, "aider-dispatch.json")
        bridge = os.path.join(self.rec, "bridge")
        while not self.halt.is_set():
            try:
                body = json.load(open(dispatch)) if os.path.isfile(dispatch) else None
            except ValueError:
                body = None
            if isinstance(body, dict) and body.get("round") not in self.maker_rounds and not self.maker_silent:
                number = body["round"]
                self.maker_rounds.append(number)
                with open(self.work_file, "w") as fh:
                    fh.write("yes\n%d\n" % number)
                record = {"round": number, "request_sha256": body["request_sha256"], "exit": 0}
                if self.maker_cost is not None:
                    record["cost_usd"] = self.maker_cost
                _put(body["exit_file"], record)
            if os.path.isdir(bridge):
                for name in sorted(os.listdir(bridge)):
                    if not (name.startswith("eval-request-") and name.endswith(".json")) or name in self.eval_done:
                        continue
                    raw = open(os.path.join(bridge, name), "rb").read()
                    req = json.loads(raw.decode("utf-8"))
                    score, verdict = self.readings[(req["round"], req["run"])]
                    _put(req["reading_file"], _reading(score, verdict, {
                        "round": req["round"], "run": req["run"], "request_sha256": _sha(raw), "cost_usd": 0}))
                    self.eval_done.add(name)
            time.sleep(0.02)


class LoopHoldsRoundsTests(unittest.TestCase):
    """loop() holds the rounds with the bridge as maker.cmd and evaluator.cmd (bar.md K1, D6.1)."""

    def setUp(self):
        patcher = mock.patch.object(cl, "emit_custody_for_finish", lambda record_dir, summary: 0, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self._dirs = [tempfile.TemporaryDirectory() for _ in range(2)]
        self.tmp, self.rec = (os.path.realpath(d.name) for d in self._dirs)
        for d in self._dirs:
            self.addCleanup(d.cleanup)
        os.makedirs(os.path.join(self.tmp, "tests"))
        os.makedirs(os.path.join(self.tmp, "src"))
        with open(os.path.join(self.tmp, "tests", "t.py"), "w") as fh:
            fh.write("pin\n")
        self.work_file = os.path.join(self.tmp, "src", "w.txt")
        with open(self.work_file, "w") as fh:
            fh.write("no\n")

    def _packet(self, cap=2, amount=1.0):
        suite = [PY, "-c", "import sys; t=open(%r).read(); sys.exit(0 if t.startswith('yes') else 1)" % self.work_file]
        return {
            "ratified": True, "mode": "scored", "human_seat": "Owner",
            "artifact": {"test_cmd": suite, "frozen": [os.path.join(self.tmp, "tests", "t.py")],
                         "editable": ["src"], "ignore": [".git", "__pycache__"]},
            "maker": {"cmd": [PY, BRIDGE, "maker", *POLL], "handoff": "rule12"},
            "evaluator": {"kind": "model", "cmd": [PY, BRIDGE, "evaluator", *POLL], "runs": 2, "held_out": []},
            "bounds": {"T_accept": 1, "T_dim": 1, "T_reject": 0, "cap": cap, "cap_counts": "generations",
                       "budget": {"amount": amount, "unit": "USD", "lt": False, "time_hours_lt": 1}},
            "escalation": {"route": ["Architect", "Owner"], "classes": [], "holders": {
                "architect": "E-DI Architect (agent)",
                "orchestrator": [
                    {"holder": "kit.conductor_loop.loop", "kind": "script", "does": "rounds", "tested": "acceptance"},
                    {"holder": "escalation-agent", "kind": "model", "does": "escalations", "tested": "acceptance"},
                ]}},
        }

    def _loop(self, readings, timeout_s=60, **seat):
        seats = FakeSeats(self.rec, self.work_file, readings, **seat)
        seats.start()
        try:
            summary = cl.loop(self._packet(), record_dir=self.rec, cwd=self.tmp, timeout_s=timeout_s)
        finally:
            seats.halt.set()
            seats.join(5)
        return summary, seats

    def test_l01_accepted_on_round_2_with_budget_measured(self):
        summary, seats = self._loop({(1, 0): (0.5, "regenerate"), (1, 1): (0.5, "regenerate"),
                                     (2, 0): (1, "accept"), (2, 1): (1, "accept")})
        self.assertEqual(summary["stop"], "accepted", summary)
        self.assertEqual(summary["terminal_state"], "accepted")
        self.assertEqual(summary["accepted_round"], 2)
        self.assertEqual(summary["cost"], 0)
        self.assertEqual(seats.maker_rounds, [1, 2])
        bridge = os.path.join(self.rec, "bridge")
        for name in ("maker-request-01.json", "maker-request-02.json", "eval-request-01-0.json",
                     "eval-request-01-1.json", "eval-request-02-0.json", "eval-request-02-1.json"):
            self.assertTrue(os.path.isfile(os.path.join(bridge, name)), name)
        for name in ("cost-01-maker.json", "cost-02-maker.json", "cost-02-eval-0.json", "cost-02-eval-1.json"):
            self.assertEqual(json.load(open(os.path.join(self.rec, name)))["amount"], 0, name)
        second = json.load(open(os.path.join(bridge, "maker-request-02.json")))
        self.assertEqual(second["findings"]["round"], 2)
        self.assertIsNotNone(second["findings"]["best"], "round 2 was not handed the best artifact")

    def test_l02_planted_stop_evaluator_split(self):
        summary, _ = self._loop({(1, 0): (1, "accept"), (1, 1): (0.5, "regenerate")})
        self.assertEqual(summary["stop"], "evaluator split", summary)

    def test_l03_planted_stop_silent_maker_times_out(self):
        summary, _ = self._loop({}, timeout_s=3, maker_silent=True)
        self.assertEqual(summary["stop"], "timeout", summary)

    def test_l04_planted_stop_undeclared_maker_cost_is_budget_unmeasured(self):
        summary, _ = self._loop({(1, 0): (1, "accept"), (1, 1): (1, "accept")}, maker_cost=None)
        self.assertEqual(summary["stop"], "budget unmeasured", summary)

    def test_l05_planted_stop_cap_reached(self):
        summary, _ = self._loop({(n, i): (0.5, "regenerate") for n in (1, 2) for i in (0, 1)})
        self.assertEqual(summary["stop"], "cap reached", summary)
        self.assertEqual(summary["rounds"], 2)


if __name__ == "__main__":
    unittest.main()
