"""Rev4 bar: unreadable paths, a frozen path under an ignore rule, and the ignore matcher."""
import os
import sys
import unittest
from tempfile import TemporaryDirectory

from kit.conductor_run import run
from kit.conductor_software import matches_ignore

PY = sys.executable
FAIL = [PY, "-c", "raise SystemExit(1)"]
ROOT = hasattr(os, "geteuid") and os.geteuid() == 0


def _write(root, name, text="x\n"):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


@unittest.skipIf(ROOT, "root can read a mode-000 file")
class UnreadablePathTests(unittest.TestCase):
    def test_chmod_000_frozen_file_gives_a_record(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt")
            result = run(
                FAIL, [frozen], [],
                [PY, "-c", "import os; os.chmod(%r, 0)" % frozen],
                cwd=tmp,
            )
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "edit outside editable")
        self.assertIs(result["hashes_unchanged"], False)

    def test_frozen_file_replaced_by_a_directory_gives_a_record(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt")
            result = run(
                FAIL, [frozen], [],
                [PY, "-c", "import os; os.remove(%r); os.mkdir(%r)" % (frozen, frozen)],
                cwd=tmp,
            )
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "edit outside editable")
        self.assertIs(result["hashes_unchanged"], False)

    def test_unreadable_new_file_outside_editable_gives_a_record(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt")
            result = run(
                FAIL, [frozen], [],
                [PY, "-c", "import os; open('x','w').write('1'); os.chmod('x', 0)"],
                cwd=tmp,
            )
        self.assertIs(result["passed"], False)
        self.assertEqual(result["reason"], "edit outside editable")


class UpFrontRefusalTests(unittest.TestCase):
    def test_directory_freeze_path_raises_before_anything_runs(self):
        with TemporaryDirectory() as tmp:
            _write(tmp, "tests/t.py")
            ran = os.path.join(tmp, "maker-ran")
            with self.assertRaises(ValueError):
                run(
                    FAIL, ["tests"], [],
                    [PY, "-c", "open(%r,'w').close()" % ran],
                    cwd=tmp,
                )
            self.assertFalse(os.path.exists(ran))

    @unittest.skipIf(ROOT, "root can read a mode-000 file")
    def test_unreadable_frozen_path_at_start_raises(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "frozen.txt")
            os.chmod(frozen, 0)
            ran = os.path.join(tmp, "maker-ran")
            try:
                with self.assertRaises(ValueError):
                    run(
                        FAIL, [frozen], [],
                        [PY, "-c", "open(%r,'w').close()" % ran],
                        cwd=tmp,
                    )
                self.assertFalse(os.path.exists(ran))
            finally:
                os.chmod(frozen, 0o600)

    def test_ignore_rule_covering_a_frozen_path_raises(self):
        with TemporaryDirectory() as tmp:
            frozen = _write(tmp, "cache/frozen.txt")
            _write(tmp, "src/w.txt", "no")
            ran = os.path.join(tmp, "maker-ran")
            with self.assertRaises(ValueError):
                run(
                    [PY, "-c", "raise SystemExit(1)"], [frozen], ["src"],
                    [PY, "-c", "open(%r,'w').close()" % ran],
                    cwd=tmp, ignore=["cache"],
                )
            self.assertFalse(os.path.exists(ran))


class IgnoreRuleTests(unittest.TestCase):
    def test_bare_name_matches_at_any_depth(self):
        self.assertTrue(matches_ignore("a/b/cache/x", ["cache"]))

    def test_slash_rule_is_anchored_at_the_root(self):
        self.assertTrue(matches_ignore("build/out/x", ["build/out"]))
        self.assertFalse(matches_ignore("src/build/out/x", ["build/out"]))

    def test_whole_components_only(self):
        self.assertFalse(matches_ignore("build/output/x", ["build/out"]))

    def test_dot_slash_rule_is_normalised(self):
        self.assertTrue(matches_ignore("build/x", ["./build"]))


if __name__ == "__main__":
    unittest.main()
