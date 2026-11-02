#!/usr/bin/env python3
"""Unit tests for extract_files.py against synthetic replies. Stdlib only; no network.
  python3 test_extract_files.py      (exit 0 = all pass)"""
import hashlib, os, subprocess, sys, tempfile, unittest
from pathlib import Path

X = Path(__file__).resolve().parent / "extract_files.py"
F = lambda p: f"<<<PLUMBLINE-FILE path={p}>>>\n".encode()
E = lambda p: f"<<<PLUMBLINE-END path={p}>>>\n".encode()
D = lambda n: f"<<<PLUMBLINE-DONE files={n}>>>\n".encode()


def run(reply: bytes, pre: dict | None = None, extra=()):
    d = Path(tempfile.mkdtemp())
    root = d / "co"; root.mkdir()
    for p, b in (pre or {}).items():
        (root / p).parent.mkdir(parents=True, exist_ok=True); (root / p).write_bytes(b)
    (d / "reply.txt").write_bytes(reply)
    r = subprocess.run([sys.executable, str(X), str(d / "reply.txt"), str(root), "--list", str(d / "list.txt"), *extra],
                       capture_output=True)
    return r, root, d


def tree(root: Path) -> dict:
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class T(unittest.TestCase):
    def ok(self, reply, pre=None):
        r, root, d = run(reply, pre); self.assertEqual(r.returncode, 0, r.stderr.decode()); return root, d

    def refused(self, reply, pre=None, why=""):
        r, root, _ = run(reply, pre)
        self.assertEqual(r.returncode, 1, r.stdout.decode() + r.stderr.decode())
        self.assertIn(b"nothing written", r.stderr); self.assertIn(why.encode(), r.stderr)
        self.assertEqual(tree(root), pre or {})          # all-or-nothing

    def test_exact_bytes_no_normalization(self):
        body = "def f():\r\n\treturn 'é'  \n\n   \nx = 1\n".encode()   # CRLF, tab, trailing spaces, non-ASCII, blank lines
        root, d = self.ok(F("kit/emit_custody.py") + body + E("kit/emit_custody.py") + D(1) + b"NOTES: hi\n",
                          {"kit/emit_custody.py": b"old\n"})
        self.assertEqual((root / "kit/emit_custody.py").read_bytes(), body)
        self.assertEqual((d / "list.txt").read_text(), "kit/emit_custody.py\n")

    def test_multiple_files_and_new_fixture(self):
        a, b = b"a\n", b"{\"k\": 1}\n"
        root, _ = self.ok(b"\n" + F("kit/custody_history.py") + a + E("kit/custody_history.py") +
                          F("tests/fixtures/custody/new-job/inputs/x.json") + b + E("tests/fixtures/custody/new-job/inputs/x.json")
                          + D(2))
        self.assertEqual(tree(root), {"kit/custody_history.py": a, "tests/fixtures/custody/new-job/inputs/x.json": b})

    def test_empty_file_and_done_without_newline(self):
        root, _ = self.ok(F("docs/custody-emission.md") + E("docs/custody-emission.md") + b"<<<PLUMBLINE-DONE files=1>>>")
        self.assertEqual((root / "docs/custody-emission.md").read_bytes(), b"")

    def test_contents_with_fences_and_lookalikes(self):
        body = b"```diff\n--- a\n+++ b\n```\n <<<PLUMBLINE-END path=x>>>\n<<PLUMBLINE-FILE\n"
        root, _ = self.ok(F("docs/custody-emission.md") + body + E("docs/custody-emission.md") + D(1))
        self.assertEqual((root / "docs/custody-emission.md").read_bytes(), body)

    def test_truncated_no_end(self):
        self.refused(F("kit/emit_custody.py") + b"x = 1\ny = ", {"kit/emit_custody.py": b"old\n"}, "no END line")

    def test_truncated_no_done(self):
        self.refused(F("kit/emit_custody.py") + b"x\n" + E("kit/emit_custody.py"), None, "no <<<PLUMBLINE-DONE")

    def test_done_count_mismatch(self):
        self.refused(F("kit/emit_custody.py") + b"x\n" + E("kit/emit_custody.py") + D(2), None, "DONE says files=2")

    def test_end_path_mismatch(self):
        self.refused(F("kit/emit_custody.py") + b"x\n" + E("kit/custody_ledger.py") + D(1), None, "does not match")

    def test_missing_final_newline_runs_into_end(self):
        self.refused(F("kit/emit_custody.py") + b"x" + E("kit/emit_custody.py") + D(1), None, "not at the start of a line")

    def test_nested_file_marker(self):
        self.refused(F("kit/emit_custody.py") + b"x\n" + F("kit/custody_ledger.py") + b"y\n" + E("kit/custody_ledger.py")
                     + D(1), None, "expected <<<PLUMBLINE-END")

    def test_malformed_markers(self):
        for bad in (b"<<<PLUMBLINE-FILE path=kit/emit_custody.py>>>\r\n", b"<<<PLUMBLINE-FILE path=kit/emit_custody.py >>>\n",
                    b"<<<PLUMBLINE-FILE kit/emit_custody.py>>>\n", b"<<<PLUMBLINE-file path=kit/emit_custody.py>>>\n"):
            self.refused(bad + b"x\n" + E("kit/emit_custody.py") + D(1), None, "")

    def test_prose_or_fence_outside_blocks(self):
        self.refused(b"Here are the files:\n" + F("kit/emit_custody.py") + b"x\n" + E("kit/emit_custody.py") + D(1), None,
                     "outside a file block")
        self.refused(b"```\n" + F("kit/emit_custody.py") + b"x\n" + E("kit/emit_custody.py") + b"```\n" + D(1), None,
                     "outside a file block")
        self.refused(F("kit/emit_custody.py") + b"x\n" + E("kit/emit_custody.py") + D(1) + b"thanks\n", None,
                     "not a NOTES: line")
        self.refused(F("kit/emit_custody.py") + b"x\n" + E("kit/emit_custody.py") + D(1) + b"NOTES: n\n" * 21, None,
                     "more than 20")

    def test_disallowed_and_bad_paths(self):
        for p in ("kit/check.py", "dot-plumbline/x", "tests/fixtures/other/x", "tests/fixtures/custody/",
                  "/etc/passwd", "kit/../kit/emit_custody.py", "tests/fixtures/custody/./x", "tests//fixtures/custody/x",
                  "kit\\emit_custody.py", "Kit/emit_custody.py"):
            self.refused(F(p) + b"x\n" + E(p) + D(1), {"kit/emit_custody.py": b"old\n"}, "")

    def test_duplicate_path(self):
        b = F("kit/emit_custody.py") + b"x\n" + E("kit/emit_custody.py")
        self.refused(b + b + D(2), None, "twice")

    def test_no_files(self):
        self.refused(D(0), None, "no files")

    def test_symlink_target(self):
        r, root, d = run(b"")
        (root / "tests/fixtures/custody").mkdir(parents=True)
        os.symlink("/tmp", root / "tests/fixtures/custody/ln")
        p = "tests/fixtures/custody/ln/x"
        (d / "reply.txt").write_bytes(F(p) + b"x\n" + E(p) + D(1))
        r = subprocess.run([sys.executable, str(X), str(d / "reply.txt"), str(root)], capture_output=True)
        self.assertEqual(r.returncode, 1); self.assertIn(b"symlink", r.stderr)

    def test_check_mode_writes_nothing(self):
        r, root, _ = run(F("kit/emit_custody.py") + b"x\n" + E("kit/emit_custody.py") + D(1), None, ["--check"])
        self.assertEqual(r.returncode, 0); self.assertEqual(tree(root), {})
        self.assertIn(hashlib.sha256(b"x\n").hexdigest().encode(), r.stdout)

    def test_usage(self):
        r = subprocess.run([sys.executable, str(X), "only-one"], capture_output=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
