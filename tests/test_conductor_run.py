"""A green suite must not dispatch the maker."""
import os
import sys
import unittest
from tempfile import TemporaryDirectory

from kit.conductor_run import run


class ConductorRunTests(unittest.TestCase):
    def test_green_suite_does_not_dispatch(self):
        with TemporaryDirectory() as tmp:
            frozen = os.path.join(tmp, "frozen.txt")
            with open(frozen, "w", encoding="utf-8") as fh:
                fh.write("pin\n")
            suite = [sys.executable, "-c", "raise SystemExit(0)"]
            sentinel = os.path.join(tmp, "sentinel.txt")
            maker = [
                sys.executable,
                "-c",
                "open(%r, 'w').write('made\\n')" % sentinel,
            ]
            result = run(
                test_cmd=suite,
                freeze_paths=[frozen],
                editable=[],
                maker_cmd=maker,
                cwd=tmp,
            )
            self.assertFalse(os.path.exists(sentinel))
            self.assertIs(result["dispatched"], False)
            self.assertEqual(result["reason"], "no RED")
            self.assertIs(result["passed"], False)

    def test_frozen_path_in_editable(self):
        with TemporaryDirectory() as tmp:
            frozen = os.path.join(tmp, "frozen.txt")
            with open(frozen, "w", encoding="utf-8") as fh:
                fh.write("pin\n")
            suite = [sys.executable, "-c", "raise SystemExit(1)"]
            sentinel = os.path.join(tmp, "sentinel.txt")
            maker = [
                sys.executable,
                "-c",
                "open(%r, 'w').write('made\\n')" % sentinel,
            ]
            result = run(
                test_cmd=suite,
                freeze_paths=[frozen],
                editable=[frozen],
                maker_cmd=maker,
                cwd=tmp,
            )
            self.assertFalse(os.path.exists(sentinel))
            self.assertIs(result["dispatched"], False)
            self.assertEqual(result["reason"], "frozen test is editable")
            self.assertIs(result["passed"], False)

    def test_unchanged_freeze_passes(self):
        with TemporaryDirectory() as tmp:
            frozen = os.path.join(tmp, "frozen.txt")
            work = os.path.join(tmp, "work.txt")
            with open(frozen, "wb") as fh:
                fh.write(b"pin\n")
            with open(work, "w", encoding="utf-8") as fh:
                fh.write("broken\n")
            before = open(frozen, "rb").read()
            suite = [
                sys.executable,
                "-c",
                "import pathlib,sys; sys.exit(0 if 'fixed' in pathlib.Path(%r).read_text() else 1)"
                % work,
            ]
            maker = [
                sys.executable,
                "-c",
                "open(%r, 'w').write('fixed\\n')" % work,
            ]
            result = run(
                test_cmd=suite,
                freeze_paths=[frozen],
                editable=[work],
                maker_cmd=maker,
                cwd=tmp,
            )
            self.assertIs(result["passed"], True)
            self.assertIs(result["dispatched"], True)
            with open(frozen, "rb") as fh:
                self.assertEqual(fh.read(), before)

    def test_moved_freeze_voids(self):
        with TemporaryDirectory() as tmp:
            frozen = os.path.join(tmp, "frozen.txt")
            with open(frozen, "w", encoding="utf-8") as fh:
                fh.write("pin\n")
            suite = [
                sys.executable,
                "-c",
                "import pathlib,sys; sys.exit(0 if 'rewritten' in pathlib.Path(%r).read_text() else 1)"
                % frozen,
            ]
            maker = [
                sys.executable,
                "-c",
                "open(%r, 'w').write('rewritten\\n')" % frozen,
            ]
            result = run(
                test_cmd=suite,
                freeze_paths=[frozen],
                editable=[],
                maker_cmd=maker,
                cwd=tmp,
            )
            self.assertIs(result["passed"], False)

    def test_applied_edit_is_not_a_pass(self):
        with TemporaryDirectory() as tmp:
            frozen = os.path.join(tmp, "frozen.txt")
            with open(frozen, "w", encoding="utf-8") as fh:
                fh.write("pin\n")
            suite = [sys.executable, "-c", "raise SystemExit(1)"]
            maker = [sys.executable, "-c", "print('Applied edit')"]
            result = run(
                test_cmd=suite,
                freeze_paths=[frozen],
                editable=[],
                maker_cmd=maker,
                cwd=tmp,
            )
            self.assertIs(result["passed"], False)

    def test_commit_field(self):
        with TemporaryDirectory() as tmp:
            frozen = os.path.join(tmp, "frozen.txt")
            with open(frozen, "w", encoding="utf-8") as fh:
                fh.write("pin\n")
            suite = [sys.executable, "-c", "raise SystemExit(0)"]
            maker = [sys.executable, "-c", "raise SystemExit(0)"]
            omitted = run(
                test_cmd=suite,
                freeze_paths=[frozen],
                editable=[],
                maker_cmd=maker,
                cwd=tmp,
            )
            none = run(
                test_cmd=suite,
                freeze_paths=[frozen],
                editable=[],
                maker_cmd=maker,
                cwd=tmp,
                commit=None,
            )
            named = run(
                test_cmd=suite,
                freeze_paths=[frozen],
                editable=[],
                maker_cmd=maker,
                cwd=tmp,
                commit="abc",
            )
            self.assertEqual(omitted["commit"], "not recorded")
            self.assertEqual(none["commit"], "not recorded")
            self.assertEqual(named["commit"], "abc")

    def test_empty_red_output(self):
        with TemporaryDirectory() as tmp:
            frozen = os.path.join(tmp, "frozen.txt")
            with open(frozen, "w", encoding="utf-8") as fh:
                fh.write("pin\n")
            suite = [sys.executable, "-c", "raise SystemExit(1)"]
            maker = [sys.executable, "-c", "raise SystemExit(0)"]
            result = run(
                test_cmd=suite,
                freeze_paths=[frozen],
                editable=[],
                maker_cmd=maker,
                cwd=tmp,
            )
            self.assertEqual(result["red"]["output_sha256"], "not recorded")


if __name__ == "__main__":
    unittest.main()
