"""Rev3 bar. These fail on rev2: a planted cache, a deleted freeze, a rerun timeout."""
import os
import sys
import unittest
from tempfile import TemporaryDirectory

from kit.conductor_run import DEFAULT_TIMEOUT_S, run
from kit.conductor_software import is_pass

PY = sys.executable


def _write(root, name, text):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class Rev3Tests(unittest.TestCase):
    def test_pycache_plant_is_not_a_pass(self):
        with TemporaryDirectory() as tmp:
            _write(tmp, "src/x.txt", "a")
            helper = _write(tmp, "helper.py", "def ok():\n    return False\n")
            test = _write(tmp, "test_x.py", "import helper, sys\nsys.exit(0 if helper.ok() else 1)\n")
            maker = _write(tmp, "maker.py", (
                "import os, py_compile, importlib.util\n"
                "st = os.stat('helper.py'); orig = open('helper.py','rb').read()\n"
                "evil = b'def ok():\\n    return True \\n'\n"
                "open('helper.py','wb').write(evil); os.utime('helper.py', ns=(st.st_atime_ns, st.st_mtime_ns))\n"
                "py_compile.compile('helper.py', cfile=importlib.util.cache_from_source('helper.py'))\n"
                "open('helper.py','wb').write(orig); os.utime('helper.py', ns=(st.st_atime_ns, st.st_mtime_ns))\n"
                "open('src/x.txt','w').write('b')\n"
            ))
            result = run([PY, test], [test, helper], ["src"], [PY, maker], cwd=tmp)
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "edit outside editable")
        self.assertIs(result["hashes_unchanged"], True)

    def test_deleted_frozen_file_returns_a_record(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt", "pin\n")
            result = run(
                [PY, "-c", "raise SystemExit(1)"],
                [frozen],
                [],
                [PY, "-c", "import os; os.remove(%r)" % frozen],
                cwd=tmp,
            )
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "edit outside editable")
        self.assertIs(result["hashes_unchanged"], False)

    def test_frozen_path_missing_at_start_raises(self):
        with TemporaryDirectory() as tmp:
            ran = os.path.join(tmp, "ran")
            with self.assertRaises(ValueError):
                run(
                    [PY, "-c", "raise SystemExit(1)"],
                    ["missing.txt"],
                    [],
                    [PY, "-c", "open(%r,'w').close()" % ran],
                    cwd=tmp,
                )
            self.assertFalse(os.path.exists(ran))

    def test_rerun_timeout_reason_is_timeout(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt", "pin\n")
            work = _write(tmp, "w.txt", "no")
            suite = [PY, "-c",
                     "import sys,time; ok=open(%r).read()=='yes'; "
                     "time.sleep(30 if ok else 0); sys.exit(0 if ok else 1)" % work]
            result = run(
                suite, [frozen], [work],
                [PY, "-c", "open(%r,'w').write('yes')" % work],
                cwd=tmp, timeout_s=1,
            )
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "timeout")
        self.assertEqual(result["rerun"]["exit"], "timeout")

    def test_default_timeout_is_600(self):
        self.assertEqual(DEFAULT_TIMEOUT_S, 600)

    def test_pytest_cache_without_ignore_is_not_a_pass(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt", "pin\n")
            _write(tmp, "src/w.txt", "no")
            maker = [PY, "-c",
                     "import os; open('src/w.txt','w').write('yes'); "
                     "os.makedirs('.pytest_cache', exist_ok=True); open('.pytest_cache/v','w').write('1')"]
            suite = [PY, "-c", "import sys; sys.exit(0 if open('src/w.txt').read()=='yes' else 1)"]
            result = run(suite, [frozen], ["src"], maker, cwd=tmp)
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "edit outside editable")

    def test_pytest_cache_ignored_is_a_pass_and_listed(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt", "pin\n")
            _write(tmp, "src/w.txt", "no")
            maker = [PY, "-c",
                     "import os; open('src/w.txt','w').write('yes'); "
                     "os.makedirs('.pytest_cache', exist_ok=True); open('.pytest_cache/v','w').write('1')"]
            suite = [PY, "-c", "import sys; sys.exit(0 if open('src/w.txt').read()=='yes' else 1)"]
            result = run(suite, [frozen], ["src"], maker, cwd=tmp, ignore=[".pytest_cache"])
        self.assertIs(result["passed"], True)
        self.assertEqual(result["reason"], "ok")
        self.assertEqual(result["ignored"]["paths"], [".pytest_cache/v"])

    def test_write_into_git_is_not_a_pass(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt", "pin\n")
            os.makedirs(os.path.join(tmp, ".git"))
            _write(tmp, "src/w.txt", "no")
            maker = [PY, "-c", "open('.git/planted','w').write('x'); open('src/w.txt','w').write('yes')"]
            suite = [PY, "-c", "import sys; sys.exit(0 if open('src/w.txt').read()=='yes' else 1)"]
            result = run(suite, [frozen], ["src"], maker, cwd=tmp)
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "edit outside editable")

    def test_ignoring_pycache_is_recorded(self):
        with TemporaryDirectory() as tmp:
            _write(tmp, "src/x.txt", "a")
            helper = _write(tmp, "helper.py", "def ok():\n    return False\n")
            test = _write(tmp, "test_x.py", "import helper, sys\nsys.exit(0 if helper.ok() else 1)\n")
            maker = _write(tmp, "maker.py", (
                "import os, py_compile, importlib.util\n"
                "st = os.stat('helper.py'); orig = open('helper.py','rb').read()\n"
                "evil = b'def ok():\\n    return True \\n'\n"
                "open('helper.py','wb').write(evil); os.utime('helper.py', ns=(st.st_atime_ns, st.st_mtime_ns))\n"
                "py_compile.compile('helper.py', cfile=importlib.util.cache_from_source('helper.py'))\n"
                "open('helper.py','wb').write(orig); os.utime('helper.py', ns=(st.st_atime_ns, st.st_mtime_ns))\n"
                "open('src/x.txt','w').write('b')\n"
            ))
            result = run(
                [PY, test], [test, helper], ["src"], [PY, maker],
                cwd=tmp, ignore=["__pycache__"],
            )
        self.assertIs(result["passed"], True)
        self.assertEqual(result["reason"], "ok")
        self.assertTrue(any("__pycache__" in path for path in result["ignored"]["paths"]))

    def test_ignored_shape_on_refused_timeout_and_pass(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt", "pin\n")
            refused = run(
                [PY, "-c", "raise SystemExit(0)"],
                [frozen], [], [PY, "-c", "pass"], cwd=tmp, ignore=[".git"],
            )
            timed = run(
                [PY, "-c", "import time; time.sleep(30)"],
                [frozen], [], [PY, "-c", "pass"], cwd=tmp, timeout_s=1, ignore=[".git"],
            )
            work = _write(tmp, "w.txt", "no")
            passed = run(
                [PY, "-c", "import sys; sys.exit(0 if open(%r).read()=='yes' else 1)" % work],
                [frozen], [work], [PY, "-c", "open(%r,'w').write('yes')" % work],
                cwd=tmp, ignore=[".git"],
            )
        for record in (refused, timed, passed):
            self.assertEqual(set(record["ignored"]), {"rules", "paths"})
            self.assertEqual(record["ignored"]["rules"], [".git"])
            self.assertIsInstance(record["ignored"]["paths"], list)
        self.assertEqual(refused["ignored"]["paths"], [])
        self.assertEqual(timed["ignored"]["paths"], [])

    def test_is_pass_positional_call_raises(self):
        with self.assertRaises(TypeError):
            is_pass(True, True, 0)
        self.assertIs(is_pass(hashes_unchanged=True, rerun_exit=0), True)


if __name__ == "__main__":
    unittest.main()
