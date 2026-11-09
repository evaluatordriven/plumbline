"""Bar for Job 11: acceptance must not delete a work-tree file.

After ``loop()`` accepts a job, the work tree must still contain every file it
contained before acceptance, with the same bytes.  Nothing on the acceptance path
may remove or move a path outside the record directory.

The fixture deliberately creates ``src/w.txt`` in a round that is not the best
round, so restoring the best round's snapshot later clears the editable
``src`` directory and deletes the file.  A green bar proves acceptance did not
remove it; it does not prove the acceptance path is safe for every job shape.
"""
import json
import os
import sys
import tempfile
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


def _holders():
    return {
        "architect": "E-DI Architect (agent)",
        "orchestrator": [
            {"holder": "kit.conductor_loop.loop", "kind": "script", "does": "rounds", "tested": "rec#abc"},
            {"holder": "escalation-agent", "kind": "model", "does": "escalations", "tested": "rec#def"},
        ],
    }


def _packet(tmp, maker, suite, editable):
    return {
        "ratified": True,
        "mode": "scored",
        "human_seat": "Owner",
        "constitution_ref": "test",
        "constitution_version": "v0",
        "artifact": {
            "test_cmd": suite,
            "frozen": [os.path.join(tmp, "tests", "t.py")],
            "editable": editable,
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
        "ground_truth": [{"source": "x", "version": "v", "hardness": "DOCUMENT"}],
        "mandate_ref": {"doc": "x", "version": "v"},
        "standard_ref": "x",
    }


def _scores(score, verdict="regenerate"):
    return {
        "dimensions": [{"name": "q", "score": score, "observation": "seen"}],
        "violations": [],
        "verdict": verdict,
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _work_file_set(root):
    """Every regular-file path under root, made relative and /-separated."""
    found = set()
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            found.add(rel)
    return found


class AcceptanceNoDeleteTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            cl, "emit_custody_for_finish",
            lambda record_dir, summary: 0, create=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, tmp, rec, editable):
        """Run the three-round scenario and return (summary, pre_files)."""
        _write(tmp, "tests/t.py", "pin\n")
        _write(tmp, "keep.txt", "no\n")
        keep = os.path.join(tmp, "keep.txt")
        # A file that exists BEFORE the run starts, inside an editable directory. The Maker never writes it; it is
        # not the product of any round. This is the data-loss case: it must still be here after acceptance.
        _write(tmp, "src/w.txt", "stay\n")

        def eval_fn(turn, cwd):
            r = turn["round"]
            if r == 1:
                return _scores(0.5)
            if r == 2:
                return _scores(0.4)
            return _scores(1, verdict="accept")

        # Round 1: only keep.txt changes (best_score becomes 0.5).
        # Round 2: keep.txt changes and src/ (with w.txt) is created (score 0.4).
        # Round 3: restore from round 1 clears src/, then keep.txt is changed again.
        maker_script = """
import json, os, time
round = json.load(open(os.environ['PLUMBLINE_FINDINGS']))['round']
open('keep.txt', 'w').write('yes\\n' + str(time.time()))
if round == 2:
    os.makedirs('src', exist_ok=True)
    open('src/a.txt', 'w').write('r2\\n')
"""
        maker = [PY, "-c", maker_script]
        suite = [PY, "-c", "import sys; t=open(%r).read(); sys.exit(0 if t.startswith('yes') else 1)" % keep]
        packet = _packet(tmp, maker, suite, editable)
        pre_files = _work_file_set(tmp)
        summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=eval_fn)
        return summary, pre_files

    def test_survival_untracked_file_in_editable_directory(self):
        # SURVIVAL
        # src/w.txt EXISTED BEFORE the run started and the Maker never wrote it. It must survive acceptance at
        # round 3, which restores from round 1 -- a round in which the snapshot has no entry for it.
        # The distinction this pins: restore may remove what THIS RUN created; it may never remove what was
        # there before the run began.
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            summary, _ = self._run(tmp, rec, ["keep.txt", "src"])
            self.assertEqual(summary["terminal_state"], "accepted")
            w = os.path.join(tmp, "src", "w.txt")
            self.assertTrue(
                os.path.exists(w),
                "loop() accepted but src/w.txt no longer exists",
            )
            self.assertEqual(
                open(w, "rb").read(),
                b"stay\n",
                "loop() accepted but src/w.txt bytes changed",
            )

    def test_containment_work_tree_unchanged_record_dir_grew(self):
        # CONTAINMENT
        # The whole acceptance path must not add or remove work-tree files.
        # (The Maker is allowed to edit bytes; the file set of the work tree
        # must be the same before and after the run.)
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            summary, pre_files = self._run(tmp, rec, ["keep.txt", "src"])
            self.assertEqual(summary["terminal_state"], "accepted")
            post_files = _work_file_set(tmp)
            self.assertEqual(
                post_files, pre_files,
                "acceptance added or removed work-tree files outside the record directory",
            )
            self.assertTrue(
                any(name.startswith("round-") for name in os.listdir(rec)),
                "record directory did not grow any round record",
            )

    def test_restore_still_removes_a_later_added_editable_file(self):
        # OPTIONAL CONTROL
        # A fix must not win by never restoring.  When an editable file was
        # added in a worse round and the best snapshot lacked it, restore
        # should still remove that file.
        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            _write(tmp, "tests/t.py", "pin\n")
            _write(tmp, "keep.txt", "no\n")
            keep = os.path.join(tmp, "keep.txt")

            def eval_fn(turn, cwd):
                r = turn["round"]
                if r == 1:
                    return _scores(0.5)
                if r == 2:
                    return _scores(0.4)
                return _scores(1, verdict="accept")

            maker_script = """
import json, os, time
round = json.load(open(os.environ['PLUMBLINE_FINDINGS']))['round']
open('keep.txt', 'w').write('yes\\n' + str(time.time()))
if round == 2:
    open('extra.txt', 'w').write('later\\n')
"""
            maker = [PY, "-c", maker_script]
            suite = [PY, "-c", "import sys; t=open(%r).read(); sys.exit(0 if t.startswith('yes') else 1)" % keep]
            packet = _packet(tmp, maker, suite, ["keep.txt", "extra.txt"])
            summary = loop(packet, record_dir=rec, cwd=tmp, evaluator_fn=eval_fn)
            self.assertEqual(summary["terminal_state"], "accepted")
            self.assertFalse(
                os.path.exists(os.path.join(tmp, "extra.txt")),
                "restore stopped removing later-added editable files",
            )


if __name__ == "__main__":
    unittest.main()
