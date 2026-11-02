import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_RUN = ROOT / "tools" / "edi" / "fixture_run.py"


def chmod_tree(root: Path, file_mode: int = 0o644, dir_mode: int = 0o755) -> None:
    for base, dirs, files in os.walk(root):
        for d in dirs:
            os.chmod(Path(base) / d, dir_mode)
        for f in files:
            os.chmod(Path(base) / f, file_mode)
    os.chmod(root, dir_mode)


class TestFixtureRun(unittest.TestCase):
    def test_read_only_source_copies_writable_and_reproducible(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "src"
            (src / "sub").mkdir(parents=True)
            (src / "a.txt").write_text("alpha\n", encoding="utf-8")
            (src / "sub" / "b.bin").write_bytes(b"\x00\x01")
            os.chmod(src / "a.txt", 0o444)
            os.chmod(src / "sub" / "b.bin", 0o400)
            os.chmod(src / "sub", 0o555)
            os.chmod(src, 0o555)
            try:
                work1 = td / "work1"
                sum1 = td / "sum1.json"
                r = subprocess.run([
                    sys.executable, str(FIXTURE_RUN),
                    "--src", str(src), "--work", str(work1), "--summary", str(sum1),
                ], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                for p in work1.rglob("*"):
                    if p.is_file():
                        self.assertTrue(os.access(p, os.W_OK), f"{p} is not writable")
                self.assertEqual((work1 / "a.txt").read_bytes(), b"alpha\n")
                s1 = json.loads(sum1.read_text(encoding="utf-8"))
                self.assertIn("started_at", s1)
                self.assertIn("finished_at", s1)
                self.assertTrue(s1["writer"].startswith("tools/edi/fixture_run.py@"))
                self.assertEqual({f["path"] for f in s1["files"]}, {"a.txt", "sub/b.bin"})
                for f in s1["files"]:
                    self.assertIsInstance(f["mode"], str)
                    self.assertTrue(int(f["mode"].replace("0o", ""), 8) & 0o200)

                work2 = td / "work2"
                sum2 = td / "sum2.json"
                r = subprocess.run([
                    sys.executable, str(FIXTURE_RUN),
                    "--src", str(src), "--work", str(work2), "--summary", str(sum2),
                ], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                s2 = json.loads(sum2.read_text(encoding="utf-8"))
                self.assertEqual(s1["files"], s2["files"])
            finally:
                chmod_tree(src)


if __name__ == "__main__":
    unittest.main()
