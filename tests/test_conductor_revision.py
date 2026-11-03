"""Bar for the maintainer's confirmed defects D1-D8.

The current modules fail these. A pass here is not a pass of the old suite.
"""
import os
import sys
import unittest
from tempfile import TemporaryDirectory

from kit.conductor_run import run
from kit.conductor_software import refuse_editable

PY = sys.executable


def _pin(tmp, name="frozen.txt", text="pin\n"):
    path = os.path.join(tmp, name)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class RevisionTests(unittest.TestCase):
    def test_relative_freeze_uses_cwd(self):
        with TemporaryDirectory() as tmp:
            _pin(tmp)
            result = run(
                [PY, "-c", "raise SystemExit(1)"],
                ["frozen.txt"],
                [],
                [PY, "-c", "pass"],
                cwd=tmp,
            )
        self.assertIsInstance(result, dict)
        self.assertIn("passed", result)

    def test_edit_outside_editable(self):
        with TemporaryDirectory() as tmp:
            test = os.path.join(tmp, "test_x.py")
            with open(test, "w", encoding="utf-8") as fh:
                fh.write("import helper\nassert helper.ok()\n")
            with open(os.path.join(tmp, "helper.py"), "w", encoding="utf-8") as fh:
                fh.write("def ok():\n    return False\n")
            os.makedirs(os.path.join(tmp, "src"))
            maker = [PY, "-c", "open('helper.py','w').write('def ok():\\n    return True\\n')"]
            result = run([PY, test], [test], ["src/other.py"], maker, cwd=tmp)
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "edit outside editable")

    def test_new_file_outside_editable(self):
        with TemporaryDirectory() as tmp:
            test = os.path.join(tmp, "test_x.py")
            with open(test, "w", encoding="utf-8") as fh:
                fh.write("import os, sys\nsys.exit(0 if os.path.exists('shim.py') else 1)\n")
            _pin(tmp)
            maker = [PY, "-c", "open('shim.py','w').write('')"]
            result = run([PY, test], [test], [], maker, cwd=tmp)
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "edit outside editable")

    def test_new_file_inside_editable_dir_is_allowed(self):
        with TemporaryDirectory() as tmp:
            test = os.path.join(tmp, "test_x.py")
            with open(test, "w", encoding="utf-8") as fh:
                fh.write(
                    "import os, sys\n"
                    "sys.exit(0 if os.path.exists('src/shim.py') else 1)\n"
                )
            os.makedirs(os.path.join(tmp, "src"))
            _pin(tmp)
            maker = [PY, "-c", "open('src/shim.py','w').write('')"]
            result = run([PY, test], ["frozen.txt"], ["src"], maker, cwd=tmp)
        self.assertNotEqual(result["reason"], "edit outside editable")
        self.assertIs(result["passed"], True)

    def test_overlap_refused(self):
        with TemporaryDirectory() as tmp:
            frozen = _pin(tmp, "tests/t.py")
            tests_dir = os.path.join(tmp, "tests")
            link = os.path.join(tmp, "alias.py")
            os.symlink(frozen, link)
            cases = [
                ([frozen], [frozen]),
                ([tests_dir], [frozen]),
                ([frozen], [tests_dir]),
                ([os.path.abspath(frozen)], [os.path.join("tests", "t.py")]),
                ([os.path.join(tmp, "tests", "..", "tests", "t.py")], [frozen]),
                ([os.path.join(tmp, ".", "tests", "t.py")], [frozen]),
                ([link], [frozen]),
            ]
            old = os.getcwd()
            os.chdir(tmp)
            try:
                for editable, frozen_paths in cases:
                    self.assertIs(
                        refuse_editable(editable, frozen_paths),
                        True,
                        msg=repr((editable, frozen_paths)),
                    )
            finally:
                os.chdir(old)

    def test_maker_nonzero_is_not_a_pass(self):
        with TemporaryDirectory() as tmp:
            frozen = _pin(tmp)
            work = _pin(tmp, "work.txt", "no")
            suite = [
                PY, "-c",
                "import sys; sys.exit(0 if open(%r).read()=='yes' else 1)" % work,
            ]
            maker = [PY, "-c", "open(%r,'w').write('yes'); raise SystemExit(3)" % work]
            result = run(suite, [frozen], [work], maker, cwd=tmp)
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "maker failed")
        self.assertEqual(result["maker"]["exit"], 3)

    def test_rerun_digest_recorded(self):
        with TemporaryDirectory() as tmp:
            frozen = _pin(tmp)
            work = _pin(tmp, "work.txt", "no")
            suite = [
                PY, "-c",
                "import sys; sys.exit(0 if open(%r).read()=='yes' else 1)" % work,
            ]
            maker = [PY, "-c", "open(%r,'w').write('yes')" % work]
            result = run(suite, [frozen], [work], maker, cwd=tmp)
            self.assertIn("rerun", result)
            self.assertEqual(result["rerun"]["exit"], 0)
            digest = result["rerun"]["output_sha256"]
            self.assertTrue(digest == "not recorded" or len(digest) == 64)
            green = run(
                [PY, "-c", "raise SystemExit(0)"],
                [frozen], [], [PY, "-c", "pass"], cwd=tmp,
            )
        self.assertEqual(green["rerun"]["output_sha256"], "not recorded")
        self.assertEqual(green["maker"]["output_sha256"], "not recorded")

    def test_timeout_is_named(self):
        with TemporaryDirectory() as tmp:
            frozen = _pin(tmp)
            result = run(
                [PY, "-c", "raise SystemExit(1)"],
                [frozen],
                [],
                [PY, "-c", "import time; time.sleep(30)"],
                cwd=tmp,
                timeout_s=1,
            )
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "timeout")
        self.assertEqual(result["maker"]["exit"], "timeout")

    def test_noop_maker_is_not_a_pass(self):
        with TemporaryDirectory() as tmp:
            frozen = _pin(tmp)
            seen = os.path.join(tmp, "seen")
            suite = [
                PY, "-c",
                "import os,sys; p=%r; e=os.path.exists(p); open(p,'w').close(); sys.exit(0 if e else 1)" % seen,
            ]
            result = run(suite, [frozen], [], [PY, "-c", "pass"], cwd=tmp)
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "no artifact")

    def test_applied_edit_with_moved_freeze(self):
        with TemporaryDirectory() as tmp:
            frozen = _pin(tmp)
            suite = [
                PY, "-c",
                "import sys; sys.exit(0 if 'rewritten' in open(%r).read() else 1)" % frozen,
            ]
            maker = [
                PY, "-c",
                "print('Applied edit'); open(%r,'w').write('rewritten\\n')" % frozen,
            ]
            result = run(suite, [frozen], [], maker, cwd=tmp)
        self.assertIs(result["passed"], False)
        self.assertIs(result["hashes_unchanged"], False)

    def test_record_keys_on_every_path(self):
        keys = {
            "dispatched", "reason", "passed", "commit",
            "red", "maker", "rerun", "hashes_unchanged",
        }
        with TemporaryDirectory() as tmp:
            frozen = _pin(tmp)
            refused = run(
                [PY, "-c", "raise SystemExit(0)"],
                [frozen], [], [PY, "-c", "pass"], cwd=tmp,
            )
        self.assertTrue(keys <= set(refused))
        for arm in ("red", "maker", "rerun"):
            self.assertIn("exit", refused[arm])
            self.assertIn("output_sha256", refused[arm])


if __name__ == "__main__":
    unittest.main()
