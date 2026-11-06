"""Commit-4 bar. Red on commit 3 until restore and the problems label land."""
import json
import os
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest import mock

import kit.conductor_loop as cl
from kit.conductor_loop import loop

PY = sys.executable


def _write(root, name, text):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _holders():
    return {
        "architect": "E-DI Architect (agent)",
        "orchestrator": [
            {"holder": "kit.conductor_loop.loop", "kind": "script", "does": "rounds", "tested": "rec#abc"},
            {"holder": "escalation-agent", "kind": "model", "does": "escalations", "tested": "rec#def"},
        ],
    }


def _packet(tmp, maker, suite):
    return {
        "ratified": True,
        "mode": "scored",
        "human_seat": "Owner",
        "artifact": {
            "test_cmd": suite,
            "frozen": [os.path.join(tmp, "tests", "t.py")],
            "editable": ["keep.txt"],
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
            "T_accept": 0.9,
            "T_dim": 0.5,
            "T_reject": 0.2,
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


def _scores(score):
    return {
        "dimensions": [{"name": "q", "score": score, "observation": "seen"}],
        "violations": [],
        "verdict": "regenerate",
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _fn():
    def fn(turn, cwd):
        return _scores(0.6 if turn["round"] == 1 else 0.4)
    return fn


def _suite(work):
    return [PY, "-c", "import sys; t=open(%r).read(); sys.exit(0 if t.startswith('yes') else 1)" % work]


def _script(side, text):
    path = os.path.join(side, "maker.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return [PY, path]


def _pin(tmp):
    _write(tmp, "tests/t.py", "pin\n")
    _write(tmp, "keep.txt", "no\n")


class Commit4Tests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            cl, "emit_custody_for_finish",
            lambda record_dir, summary: 0, create=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_restore_removes_the_file_the_best_round_lacked(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec, TemporaryDirectory() as side:
            _pin(tmp)
            _write(tmp, "notes.txt", "stay\n")
            seen = os.path.join(side, "seen")
            npath = os.path.join(side, "n")
            maker = _script(side, (
                "import os\n"
                "npath = %r\n"
                "seen = %r\n"
                "n = int(open(npath).read()) if os.path.exists(npath) else 0\n"
                "n += 1\n"
                "open(npath, 'w').write(str(n))\n"
                "if n == 1:\n"
                "    open('keep.txt', 'w').write('yes\\n')\n"
                "elif n == 2:\n"
                "    open('extra.txt', 'w').write('later\\n')\n"
                "else:\n"
                "    open(seen, 'w').write('yes' if os.path.exists('extra.txt') else 'no')\n"
            ) % (npath, seen))
            packet = _packet(tmp, maker, _suite(os.path.join(tmp, "keep.txt")))
            packet["artifact"]["editable"] = ["keep.txt", "extra.txt"]
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=_fn())
            self.assertEqual(summary["best_round"], 1)
            self.assertEqual(_read(seen), "no")
            self.assertFalse(os.path.exists(os.path.join(tmp, "extra.txt")))
            self.assertFalse(os.path.exists(os.path.join(rec, "round-03", "editable", "extra.txt")))
            self.assertTrue(os.path.exists(os.path.join(rec, "round-02", "editable", "extra.txt")))
            self.assertEqual(_read(os.path.join(tmp, "notes.txt")), "stay\n")

    def test_restore_removes_a_directory_entry_the_best_round_lacked(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec, TemporaryDirectory() as side:
            _pin(tmp)
            _write(tmp, "other.txt", "stay\n")
            seen = os.path.join(side, "seen")
            npath = os.path.join(side, "n")
            maker = _script(side, (
                "import os\n"
                "npath = %r\n"
                "seen = %r\n"
                "n = int(open(npath).read()) if os.path.exists(npath) else 0\n"
                "n += 1\n"
                "open(npath, 'w').write(str(n))\n"
                "if n == 1:\n"
                "    open('keep.txt', 'w').write('yes\\n')\n"
                "elif n == 2:\n"
                "    os.makedirs('src', exist_ok=True)\n"
                "    open('src/extra.txt', 'w').write('later\\n')\n"
                "else:\n"
                "    open(seen, 'w').write('yes' if os.path.lexists('src') else 'no')\n"
            ) % (npath, seen))
            packet = _packet(tmp, maker, _suite(os.path.join(tmp, "keep.txt")))
            packet["artifact"]["editable"] = ["keep.txt", "src"]
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=_fn())
            self.assertEqual(summary["best_round"], 1)
            self.assertEqual(_read(seen), "no")
            self.assertFalse(os.path.lexists(os.path.join(tmp, "src")))
            self.assertFalse(os.path.lexists(os.path.join(rec, "round-03", "editable", "src")))
            self.assertTrue(os.path.exists(os.path.join(rec, "round-02", "editable", "src", "extra.txt")))
            self.assertEqual(_read(os.path.join(tmp, "other.txt")), "stay\n")

    def test_restore_unlinks_a_symlink_and_leaves_the_outside_target(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec, TemporaryDirectory() as side:
            _pin(tmp)
            target = os.path.join(side, "target.txt")
            _write(side, "target.txt", "safe\n")
            seen = os.path.join(side, "seen")
            npath = os.path.join(side, "n")
            maker = _script(side, (
                "import os\n"
                "npath = %r\n"
                "seen = %r\n"
                "target = %r\n"
                "n = int(open(npath).read()) if os.path.exists(npath) else 0\n"
                "n += 1\n"
                "open(npath, 'w').write(str(n))\n"
                "if n == 1:\n"
                "    open('keep.txt', 'w').write('yes\\n')\n"
                "elif n == 2:\n"
                "    os.symlink(target, 'link.txt')\n"
                "else:\n"
                "    open(seen, 'w').write('yes' if os.path.lexists('link.txt') else 'no')\n"
            ) % (npath, seen, target))
            packet = _packet(tmp, maker, _suite(os.path.join(tmp, "keep.txt")))
            packet["artifact"]["editable"] = ["keep.txt", "link.txt"]
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=_fn())
            self.assertEqual(summary["best_round"], 1)
            self.assertEqual(_read(seen), "no")
            self.assertFalse(os.path.lexists(os.path.join(tmp, "link.txt")))
            self.assertFalse(os.path.lexists(os.path.join(rec, "round-03", "editable", "link.txt")))
            self.assertEqual(_read(target), "safe\n")

    def test_rounds_holder_without_tested_names_that_entry(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            _pin(tmp)
            packet = _packet(tmp, [PY, "-c", "pass"], _suite(os.path.join(tmp, "keep.txt")))
            packet["escalation"]["holders"]["orchestrator"][0]["tested"] = ""
            with self.assertRaises(ValueError) as caught:
                loop(packet, record_dir=rec, cwd=tmp)
            message = str(caught.exception)
            self.assertIn("holders.orchestrator[0] (rounds) has no tested", message)
            self.assertNotIn("escalations holder has no tested", message)
            with open(os.path.join(rec, "escalation.json"), encoding="utf-8") as fh:
                problems = json.load(fh)["problems"]
            self.assertIn("holders.orchestrator[0] (rounds) has no tested", problems)


if __name__ == "__main__":
    unittest.main()
