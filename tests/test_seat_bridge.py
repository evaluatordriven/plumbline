"""The Maker's own tests for kit/seat_bridge.py: choices bar.md section 3 leaves open (see docs/SEAT-BRIDGE.md).

Each test starts the bridge as loop() would, plays the seat by writing files, and reaps the process.
No network, no model, no bot.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE = os.path.join(REPO, "kit", "seat_bridge.py")
PY = sys.executable
WAIT = 15.0


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read(path):
    with open(path, "rb") as fh:
        return fh.read()


def _put(path, text):
    part = path + ".part"
    with open(part, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(part, path)


def _until(path, proc):
    end = time.monotonic() + WAIT
    while time.monotonic() < end:
        if os.path.isfile(path):
            return True
        if proc.poll() is not None:
            break
        time.sleep(0.02)
    return os.path.isfile(path)


class BridgeChoiceTests(unittest.TestCase):
    def setUp(self):
        dirs = [tempfile.TemporaryDirectory() for _ in range(2)]
        for d in dirs:
            self.addCleanup(d.cleanup)
        self.rec, self.work = (os.path.realpath(d.name) for d in dirs)

    def _start(self, command, env, poll="0.02"):
        full = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for name in ("PLUMBLINE_FINDINGS", "PLUMBLINE_TURN", "PLUMBLINE_COST"):
            full.pop(name, None)
        full.update(env)
        proc = subprocess.Popen([PY, BRIDGE, command, "--poll", poll], cwd=self.work, env=full,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self._reap, proc)
        return proc

    @staticmethod
    def _reap(proc):
        if proc.poll() is None:
            proc.kill()
        proc.communicate()

    def _maker(self, number=1):
        findings = os.path.join(self.rec, "findings-%02d.json" % number)
        with open(findings, "w") as fh:
            json.dump({"round": number, "cap": 2, "best": None, "defects": [], "solutions": []}, fh)
        self.cost = os.path.join(self.rec, "cost-%02d-maker.json" % number)
        proc = self._start("maker", {"PLUMBLINE_FINDINGS": findings, "PLUMBLINE_COST": self.cost})
        request = os.path.join(self.rec, "bridge", "maker-request-%02d.json" % number)
        self.assertTrue(_until(request, proc), "no maker request")
        time.sleep(0.1)  # the second file of the turn follows the request
        raw = _read(request)
        return proc, json.loads(raw.decode("utf-8")), _sha(raw)

    def test_maker_waits_on_an_exit_record_that_does_not_parse_yet(self):
        proc, req, sha = self._maker()
        with open(req["exit_file"], "w") as fh:
            fh.write('{"round": 1, "exit"')
        time.sleep(0.5)
        self.assertIsNone(proc.poll(), "a partial exit record ended the turn")
        _put(req["exit_file"], json.dumps({"round": 1, "request_sha256": sha, "exit": 0, "cost_usd": 0}))
        self.assertEqual(proc.wait(WAIT), 0)

    def test_written_at_has_an_offset_and_every_step_is_logged(self):
        proc, req, sha = self._maker()
        self.assertRegex(req["written_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
        _put(req["exit_file"], json.dumps({"round": 1, "request_sha256": sha, "exit": 0, "cost_usd": 0}))
        self.assertEqual(proc.wait(WAIT), 0)
        with open(os.path.join(self.rec, "bridge", "log.jsonl")) as fh:
            events = [json.loads(line)["event"] for line in fh if line.strip()]
        for name in ("maker_start", "request_written", "exit_record_accepted", "cost_written", "maker_done"):
            self.assertIn(name, events)

    def test_a_non_finite_cost_writes_no_cost_file(self):
        proc, req, sha = self._maker()
        _put(req["exit_file"], '{"round": 1, "request_sha256": "%s", "exit": 0, "cost_usd": Infinity}' % sha)
        self.assertEqual(proc.wait(WAIT), 0)
        self.assertFalse(os.path.exists(self.cost))

    def test_two_stale_exit_records_are_both_kept(self):
        for text in ('{"old": 1}', '{"old": 2}'):
            with open(os.path.join(self.rec, "aider-exit.json"), "w") as fh:
                fh.write(text)
            proc, req, sha = self._maker(2)
            _put(req["exit_file"], json.dumps({"round": 2, "request_sha256": sha, "exit": 0}))
            self.assertEqual(proc.wait(WAIT), 0)
            os.remove(req["exit_file"])
        kept = sorted(n for n in os.listdir(os.path.join(self.rec, "bridge")) if n.startswith("aider-exit-stale-"))
        self.assertEqual(kept, ["aider-exit-stale-02-1.json", "aider-exit-stale-02.json"])

    def test_poll_must_be_a_positive_number(self):
        for poll in ("0", "-1", "nan", "x"):
            with self.subTest(poll=poll):
                proc = self._start("maker", {}, poll=poll)
                proc.communicate(timeout=WAIT)
                self.assertNotEqual(proc.returncode, 0)

    def test_evaluator_refuses_before_writing_a_request(self):
        good = os.path.join(self.rec, "cost-01-eval-0.json")
        for case, env in (
                ("no integer round", {"PLUMBLINE_TURN": '{"round": "1"}', "PLUMBLINE_COST": good}),
                ("cost name does not parse", {"PLUMBLINE_TURN": '{"round": 1}',
                                              "PLUMBLINE_COST": os.path.join(self.rec, "cost-01-eval-x.json")})):
            with self.subTest(case=case):
                proc = self._start("evaluator", env)
                out, err = proc.communicate(timeout=WAIT)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(out, b"")
                self.assertEqual(len(err.decode().strip().splitlines()), 1, err)
                self.assertFalse(os.path.exists(os.path.join(self.rec, "bridge")))

    def test_evaluator_prints_only_the_reading(self):
        turn = json.dumps({"round": 1, "artifact": "a", "artifact_sha256": "b" * 64, "gate": {}})
        cost = os.path.join(self.rec, "cost-01-eval-0.json")
        proc = self._start("evaluator", {"PLUMBLINE_TURN": turn, "PLUMBLINE_COST": cost})
        request = os.path.join(self.rec, "bridge", "eval-request-01-0.json")
        self.assertTrue(_until(request, proc))
        raw = _read(request)
        req = json.loads(raw.decode("utf-8"))
        self.assertTrue(re.search(r"[+-]\d\d:\d\d$", req["written_at"]))
        reading = json.dumps({"verdict": "accept", "bridge": {"round": 1, "run": 0, "request_sha256": _sha(raw),
                                                               "cost_usd": 0.5}})
        _put(req["reading_file"], reading)
        out, err = proc.communicate(timeout=WAIT)
        self.assertEqual((proc.returncode, out, err), (0, reading.encode("utf-8"), b""))
        with open(cost) as fh:
            self.assertEqual(json.load(fh)["amount"], 0.5)


if __name__ == "__main__":
    unittest.main()
