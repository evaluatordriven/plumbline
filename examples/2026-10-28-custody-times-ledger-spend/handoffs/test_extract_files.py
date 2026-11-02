#!/usr/bin/env python3
"""Unit tests for extract_files.py (job 2026-10-28-custody-times-ledger-spend; job 1's tests with paths moved to part 'docs', plus part tests) against synthetic replies. Stdlib only; no network.
  python3 test_extract_files.py      (exit 0 = all pass)"""
import hashlib, os, subprocess, sys, tempfile, unittest
from pathlib import Path

X = Path(__file__).resolve().parent / "extract_files.py"
F = lambda p: f"<<<PLUMBLINE-FILE path={p}>>>\n".encode()
E = lambda p: f"<<<PLUMBLINE-END path={p}>>>\n".encode()
D = lambda n: f"<<<PLUMBLINE-DONE files={n}>>>\n".encode()


def run(reply: bytes, pre: dict | None = None, extra=(), part="docs"):
    d = Path(tempfile.mkdtemp())
    root = d / "co"; root.mkdir()
    for p, b in (pre or {}).items():
        (root / p).parent.mkdir(parents=True, exist_ok=True); (root / p).write_bytes(b)
    (d / "reply.txt").write_bytes(reply)
    r = subprocess.run([sys.executable, str(X), str(d / "reply.txt"), str(root), "--part", part, "--list", str(d / "list.txt"), *extra],
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
        root, d = self.ok(F("kit/README.md") + body + E("kit/README.md") + D(1) + b"NOTES: hi\n",
                          {"kit/README.md": b"old\n"})
        self.assertEqual((root / "kit/README.md").read_bytes(), body)
        self.assertEqual((d / "list.txt").read_text(), "kit/README.md\n")

    def test_multiple_files_and_new_fixture(self):
        a, b = b"a\n", b"{\"k\": 1}\n"
        root, _ = self.ok(b"\n" + F("docs/custody-emission.md") + a + E("docs/custody-emission.md") +
                          F("kit/README.md") + b + E("kit/README.md")
                          + D(2))
        self.assertEqual(tree(root), {"docs/custody-emission.md": a, "kit/README.md": b})

    def test_empty_file_and_done_without_newline(self):
        root, _ = self.ok(F("docs/custody-emission.md") + E("docs/custody-emission.md") + b"<<<PLUMBLINE-DONE files=1>>>")
        self.assertEqual((root / "docs/custody-emission.md").read_bytes(), b"")

    def test_contents_with_fences_and_lookalikes(self):
        body = b"```diff\n--- a\n+++ b\n```\n <<<PLUMBLINE-END path=x>>>\n<<PLUMBLINE-FILE\n"
        root, _ = self.ok(F("docs/custody-emission.md") + body + E("docs/custody-emission.md") + D(1))
        self.assertEqual((root / "docs/custody-emission.md").read_bytes(), body)

    def test_truncated_no_end(self):
        self.refused(F("kit/README.md") + b"x = 1\ny = ", {"kit/README.md": b"old\n"}, "no END line")

    def test_truncated_no_done(self):
        self.refused(F("kit/README.md") + b"x\n" + E("kit/README.md"), None, "no <<<PLUMBLINE-DONE")

    def test_done_count_mismatch(self):
        self.refused(F("kit/README.md") + b"x\n" + E("kit/README.md") + D(2), None, "DONE says files=2")

    def test_end_path_mismatch(self):
        self.refused(F("kit/README.md") + b"x\n" + E("kit/custody_ledger.py") + D(1), None, "does not match")

    def test_missing_final_newline_runs_into_end(self):
        self.refused(F("kit/README.md") + b"x" + E("kit/README.md") + D(1), None, "not at the start of a line")

    def test_nested_file_marker(self):
        self.refused(F("kit/README.md") + b"x\n" + F("kit/custody_ledger.py") + b"y\n" + E("kit/custody_ledger.py")
                     + D(1), None, "expected <<<PLUMBLINE-END")

    def test_malformed_markers(self):
        for bad in (b"<<<PLUMBLINE-FILE path=kit/README.md>>>\r\n", b"<<<PLUMBLINE-FILE path=kit/README.md >>>\n",
                    b"<<<PLUMBLINE-FILE kit/README.md>>>\n", b"<<<PLUMBLINE-file path=kit/README.md>>>\n"):
            self.refused(bad + b"x\n" + E("kit/README.md") + D(1), None, "")

    def test_prose_or_fence_outside_blocks(self):
        self.refused(b"Here are the files:\n" + F("kit/README.md") + b"x\n" + E("kit/README.md") + D(1), None,
                     "outside a file block")
        self.refused(b"```\n" + F("kit/README.md") + b"x\n" + E("kit/README.md") + b"```\n" + D(1), None,
                     "outside a file block")
        self.refused(F("kit/README.md") + b"x\n" + E("kit/README.md") + D(1) + b"thanks\n", None,
                     "not a NOTES: line")
        self.refused(F("kit/README.md") + b"x\n" + E("kit/README.md") + D(1) + b"NOTES: n\n" * 21, None,
                     "more than 20")

    def test_disallowed_and_bad_paths(self):
        for p in ("kit/emit_custody.py", "tools/pin.json", "dot-plumbline/x", "docs/other.md", "tests/fixtures/custody/x",
                  "/etc/passwd", "docs/../kit/README.md", "./kit/README.md", "docs//custody-emission.md",
                  "docs\\custody-emission.md", "kit/readme.md", "kit/README.md "):
            self.refused(F(p) + b"x\n" + E(p) + D(1), {"kit/README.md": b"old\n"}, "")

    def test_duplicate_path(self):
        b = F("kit/README.md") + b"x\n" + E("kit/README.md")
        self.refused(b + b + D(2), None, "twice")

    def test_no_files(self):
        self.refused(D(0), None, "no files")

    def test_symlink_target(self):
        r, root, d = run(b"")
        (d / "elsewhere").mkdir()
        os.symlink(d / "elsewhere", root / "docs")
        p = "docs/custody-emission.md"
        (d / "reply.txt").write_bytes(F(p) + b"x\n" + E(p) + D(1))
        r = subprocess.run([sys.executable, str(X), str(d / "reply.txt"), str(root), "--part", "docs"], capture_output=True)
        self.assertEqual(r.returncode, 1); self.assertIn(b"symlink", r.stderr)

    def test_check_mode_writes_nothing(self):
        r, root, _ = run(F("kit/README.md") + b"x\n" + E("kit/README.md") + D(1), None, ["--check"])
        self.assertEqual(r.returncode, 0); self.assertEqual(tree(root), {})
        self.assertIn(hashlib.sha256(b"x\n").hexdigest().encode(), r.stdout)

    def test_usage(self):
        r = subprocess.run([sys.executable, str(X), "only-one"], capture_output=True)
        self.assertEqual(r.returncode, 2)

    # --- job 2026-10-28-custody-times-ledger-spend: parts ---
    def test_part_required_and_known(self):
        d = Path(tempfile.mkdtemp()); (d / "co").mkdir(); (d / "r.txt").write_bytes(D(0))
        for extra in ([], ["--part", "nope"]):
            r = subprocess.run([sys.executable, str(X), str(d / "r.txt"), str(d / "co"), *extra], capture_output=True)
            self.assertEqual(r.returncode, 2)

    def test_guide_only_in_its_own_part(self):
        g = "docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md"
        r, root, _ = run(F(g) + b"# guide\n" + E(g) + D(1), part="guide")
        self.assertEqual(r.returncode, 0, r.stderr.decode()); self.assertEqual(tree(root), {g: b"# guide\n"})
        for part in ("ledger", "emitter", "verifier", "edi", "docs"):
            r, root, _ = run(F(g) + b"x\n" + E(g) + D(1), part=part)
            self.assertEqual(r.returncode, 1, part); self.assertEqual(tree(root), {})
        r, root, _ = run(F(g) + b"x\n" + E(g) + F("kit/README.md") + b"y\n" + E("kit/README.md") + D(2), part="guide")
        self.assertEqual(r.returncode, 1); self.assertIn(b"not allowed in part guide", r.stderr); self.assertEqual(tree(root), {})

    def test_part_paths(self):
        ok = {"ledger": ["kit/custody_ledger.py", "kit/custody_history.py", "tests/test_custody_ledger_cmds.py"],
              "edi": ["tools/edi/or_call.py", "tools/edi/sub/x.py", "tests/test_edi_or_call.py"],
              "verifier": ["kit/plumbline_verify.py", "schemas/x-plumbline/x-plumbline-v1.schema.json",
                           "kit/plumbline_job.py", "tests/test_plumbline_verify.py"],
              "emitter": ["kit/emit_custody.py", "tests/validate_schemas.py"]}
        bad = {"ledger": ["kit/emit_custody.py", "tests/sub/test_custody_ledger.py", "tools/edi/x.py"],
               "edi": ["tools/pin.json", "tools/build_schemas.py", "tests/test_custody_ledger.py"],
               "verifier": ["schemas/x-plumbline/other.json", "kit/custody_ledger.py"],
               "emitter": ["dot-plumbline/jobs/x/y.json", "schemas/custody/x.json"]}
        for part, ps in ok.items():
            for p in ps:
                r, root, _ = run(F(p) + b"x\n" + E(p) + D(1), extra=["--check"], part=part)
                self.assertEqual(r.returncode, 0, (part, p, r.stderr))
        for part, ps in bad.items():
            for p in ps:
                r, root, _ = run(F(p) + b"x\n" + E(p) + D(1), part=part)
                self.assertEqual(r.returncode, 1, (part, p)); self.assertEqual(tree(root), {})

    def test_fixture_new_folders_only(self):
        d = Path(tempfile.mkdtemp()); co = d / "co"; co.mkdir()
        g = lambda *a: subprocess.run(["git", "-C", str(co), *a], check=True, capture_output=True, text=True).stdout
        g("init", "-q"); (co / "tests/fixtures/custody/old").mkdir(parents=True)
        (co / "tests/fixtures/custody/old/a.json").write_text("{}\n")
        g("add", "-A"); g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "b")
        base = g("rev-parse", "HEAD").strip()
        x2 = d / "extract_files.py"
        x2.write_text(X.read_text().replace('BASE = "3df1ce52eddfe18705e380c4b6e99cf617cfa24b"', f'BASE = "{base}"'))
        def go(p):
            (d / "r.txt").write_bytes(F(p) + b"x\n" + E(p) + D(1))
            return subprocess.run([sys.executable, str(x2), str(d / "r.txt"), str(co), "--part", "emitter"], capture_output=True)
        r = go("tests/fixtures/custody/old/a.json"); self.assertEqual(r.returncode, 1); self.assertIn(b"base fixture", r.stderr)
        self.assertEqual((co / "tests/fixtures/custody/old/a.json").read_text(), "{}\n")
        r = go("tests/fixtures/custody/new-case/a.json"); self.assertEqual(r.returncode, 0, r.stderr)
        # fails closed where the base commit is absent
        r, root, _ = run(F("tests/fixtures/custody/n/a.json") + b"x\n" + E("tests/fixtures/custody/n/a.json") + D(1), part="emitter")
        self.assertEqual(r.returncode, 1); self.assertIn(b"cannot check fixture paths", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
