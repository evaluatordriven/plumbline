import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "tools" / "edi" / "extract_files.py"

REPLY = (
    b"<<<PLUMBLINE-FILE path=a.txt>>>\n"
    b"alpha\n"
    b"<<<PLUMBLINE-END path=a.txt>>>\n"
    b"<<<PLUMBLINE-FILE path=sub/b.txt>>>\n"
    b"beta\n"
    b"<<<PLUMBLINE-END path=sub/b.txt>>>\n"
    b"<<<PLUMBLINE-DONE files=2>>>\n"
    b"NOTES: ok\n"
)


class TestExtractFiles(unittest.TestCase):
    def test_check_validates_and_write_is_byte_exact(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            reply = td / "reply.txt"
            reply.write_bytes(REPLY)
            target = td / "target"
            target.mkdir()
            r = subprocess.run([sys.executable, str(EXTRACT), str(reply), str(target), "--check"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(list(target.iterdir()), [])
            r = subprocess.run([sys.executable, str(EXTRACT), str(reply), str(target)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((target / "a.txt").read_bytes(), b"alpha\n")
            self.assertEqual((target / "sub" / "b.txt").read_bytes(), b"beta\n")

    def test_missing_end_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            reply = td / "reply.txt"
            reply.write_bytes(
                b"<<<PLUMBLINE-FILE path=a.txt>>>\n"
                b"alpha\n"
                b"<<<PLUMBLINE-DONE files=1>>>\n"
            )
            target = td / "target"
            target.mkdir()
            r = subprocess.run([sys.executable, str(EXTRACT), str(reply), str(target)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("no END", r.stderr)
            self.assertFalse((target / "a.txt").exists())

    def test_duplicate_path_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            reply = td / "reply.txt"
            reply.write_bytes(
                b"<<<PLUMBLINE-FILE path=a.txt>>>\n"
                b"one\n"
                b"<<<PLUMBLINE-END path=a.txt>>>\n"
                b"<<<PLUMBLINE-FILE path=a.txt>>>\n"
                b"two\n"
                b"<<<PLUMBLINE-END path=a.txt>>>\n"
                b"<<<PLUMBLINE-DONE files=2>>>\n"
            )
            target = td / "target"
            target.mkdir()
            r = subprocess.run([sys.executable, str(EXTRACT), str(reply), str(target)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            self.assertIn("returned twice", r.stderr)
            self.assertFalse((target / "a.txt").exists())


if __name__ == "__main__":
    unittest.main()
