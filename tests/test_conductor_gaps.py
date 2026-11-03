"""Five behaviours rev2 gets right but no test pins down."""
import hashlib
import os
import sys
import time
import unittest
from tempfile import TemporaryDirectory

from kit.conductor_run import run
from kit.conductor_software import refuse_editable, resolve

PY = sys.executable


def _write(root, name, text):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class GapTests(unittest.TestCase):
    def test_rerun_and_red_digests_are_of_the_real_bytes(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt", "pin\n")
            work = _write(tmp, "w.txt", "no")
            suite = [PY, "-c",
                     "import sys; ok=open(%r).read()=='yes'; "
                     "sys.stdout.write('GREEN' if ok else 'RED'); sys.exit(0 if ok else 1)" % work]
            result = run(suite, [frozen], [work], [PY, "-c", "open(%r,'w').write('yes')" % work], cwd=tmp)
        self.assertEqual(result["red"]["output_sha256"], hashlib.sha256(b"RED").hexdigest())
        self.assertEqual(result["rerun"]["output_sha256"], hashlib.sha256(b"GREEN").hexdigest())

    def test_red_run_timeout_is_named_and_the_maker_never_runs(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt", "pin\n")
            ran = os.path.join(tmp, "maker-ran")
            result = run([PY, "-c", "import time; time.sleep(30)"], [frozen], [],
                         [PY, "-c", "open(%r,'w').close()" % ran], cwd=tmp, timeout_s=1)
            self.assertFalse(os.path.exists(ran))
        self.assertIs(result["dispatched"], False)
        self.assertEqual(result["reason"], "timeout")
        self.assertEqual(result["red"]["exit"], "timeout")
        self.assertIsNone(result["maker"]["exit"])

    def test_timeout_kills_the_makers_children(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt", "pin\n")
            marker = os.path.join(tmp, "late")
            _write(tmp, "grand.py", "import time\ntime.sleep(2)\nopen(%r,'w').write('x')\n" % marker)
            _write(tmp, "maker.py",
                   "import subprocess,sys,time\nsubprocess.Popen([sys.executable,'grand.py'])\ntime.sleep(30)\n")
            result = run([PY, "-c", "raise SystemExit(1)"], [frozen], [], [PY, "maker.py"], cwd=tmp, timeout_s=1)
            time.sleep(2.5)
            self.assertFalse(os.path.exists(marker), "a child of the timed-out Maker kept running")
        self.assertEqual(result["reason"], "timeout")

    def test_containment_is_by_path_component_not_string_prefix(self):
        with TemporaryDirectory() as tmp:
            tests = os.path.join(tmp, "tests")
            tests2 = os.path.join(tmp, "tests2", "x.py")
            self.assertIs(refuse_editable([tests2], [tests]), False)
            self.assertIs(refuse_editable([tests], [tests2]), False)
            self.assertIs(refuse_editable([os.path.join(tests, "t.py")], [tests]), True)

    def test_relative_symlink_alias_is_resolved_against_cwd(self):
        with TemporaryDirectory() as tmp:
            _write(tmp, "tests/t.py", "pin\n")
            os.symlink(os.path.join("tests", "t.py"), os.path.join(tmp, "alias.py"))
            self.assertEqual(resolve("alias.py", tmp), resolve("tests/t.py", tmp))
            ran = os.path.join(tmp, "maker-ran")
            result = run([PY, "-c", "raise SystemExit(1)"], ["tests/t.py"], ["alias.py"],
                         [PY, "-c", "open(%r,'w').close()" % ran], cwd=tmp)
            self.assertFalse(os.path.exists(ran))
        self.assertIs(result["dispatched"], False)
        self.assertEqual(result["reason"], "frozen test is editable")


if __name__ == "__main__":
    unittest.main()
