#!/usr/bin/env python3
"""kit/emit_record.py resolves its corpus with tools/edi_corpus.py, and before it writes anything (option A).

Every case runs the emitter as a subprocess in a scrubbed environment (no EDI_CORPUS, HERMES_HOME or
PLUMBLINE_REQUIRE_CORPUS from the caller; HOME pointed at an empty directory), on the kit's own pinned run
(kit/cases/run_cases.py's EMITTER_RUN, dumped with indent=2) beside a stand-in artifact. "Resolved" cases use a
stand-in corpus built here: the resolver's base need (schemas/job-packet.schema.json) plus a
tools/validate_evaluator_record.py that accepts its argument, so no E-DI checkout is needed and the tests run
in a stranger's clone. What they hold is the emitter's corpus handling, not the corpus's validator.

    python3 -m unittest -v tests.test_emit_record
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EMIT = REPO / "kit" / "emit_record.py"
sys.path.insert(0, str(REPO / "kit" / "cases"))
from run_cases import EMITTER_RUN  # noqa: E402

RUN = json.dumps(EMITTER_RUN, indent=2) + "\n"
SCRUB = ("EDI_CORPUS", "HERMES_HOME", "PLUMBLINE_REQUIRE_CORPUS")
VALIDATOR = ('import sys, pathlib\n'
             'assert pathlib.Path(sys.argv[-1]).is_file()\n'
             'print("OK (schema-verified)")\n')


class EmitRecordCorpusTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self.work = self.root / "work"; self.work.mkdir()
        (self.work / "iteration-1-artifact.md").write_text("# stand-in artifact\n")
        self.run_file = self.root / "run.json"; self.run_file.write_text(RUN)
        self.home = self.root / "home"; self.home.mkdir()
        self.corpus = self.root / "corpus"
        (self.corpus / "schemas").mkdir(parents=True)
        (self.corpus / "schemas" / "job-packet.schema.json").write_text("{}\n")
        (self.corpus / "tools").mkdir()
        (self.corpus / "tools" / "validate_evaluator_record.py").write_text(VALIDATOR)
        self.missing = self.root / "no-such-corpus"

    def tearDown(self):
        self._td.cleanup()

    def emit(self, *flags: str, **env: str) -> tuple[int, str]:
        e = {k: v for k, v in os.environ.items() if k not in SCRUB}
        e["HOME"] = str(self.home)
        e["PYTHONDONTWRITEBYTECODE"] = "1"
        e.update(env)
        r = subprocess.run([sys.executable, "-B", str(EMIT), "--run", str(self.run_file),
                            "--out-dir", str(self.work), *flags],
                           capture_output=True, text=True, env=e, cwd=str(self.root))
        return r.returncode, r.stdout + r.stderr

    def written(self) -> list[str]:
        """Everything the emitter left in the job dir, beyond the stand-in artifact."""
        return sorted(str(p.relative_to(self.work)) for p in self.work.rglob("*")
                      if p.is_file() and p.name != "iteration-1-artifact.md")

    def assertNothingWritten(self, out: str):
        self.assertEqual(self.written(), [], out)
        self.assertFalse((self.work / "passes").exists(), out)

    # ---- no corpus: exit 1, nothing written ----
    def test_no_corpus_writes_nothing(self):
        for env in ({}, {"PLUMBLINE_REQUIRE_CORPUS": "1"}, {"PLUMBLINE_REQUIRE_CORPUS": "0"},
                    {"PLUMBLINE_REQUIRE_CORPUS": ""}, {"EDI_CORPUS": ""}):
            with self.subTest(env=env):
                code, out = self.emit(**env)
                self.assertEqual(code, 1, out)
                self.assertNothingWritten(out)
                self.assertNotIn("corpus source:", out)
                self.assertIn("Nothing was written", out)

    def test_unreadable_hermes_config_is_named_and_treated_as_no_corpus(self):
        hh = self.root / "hermes"; hh.mkdir()
        cfg = hh / "config.yaml"
        cfg.write_text(f"plugins:\n  edi-loop:\n    corpus: {self.corpus}\n")
        try:
            import yaml  # noqa: F401
            self.skipTest("PyYAML is importable here, so the config is readable and the corpus resolves")
        except ImportError:
            pass
        code, out = self.emit(HERMES_HOME=str(hh))
        self.assertEqual(code, 1, out)
        self.assertIn(str(cfg), out)
        self.assertNotIn("corpus source:", out)
        self.assertNothingWritten(out)

    # ---- a set value that is not a corpus: exit 2, named, no fallthrough ----
    def test_bad_corpus_flag_is_a_usage_error(self):
        code, out = self.emit("--corpus", str(self.missing))
        self.assertEqual(code, 2, out)
        self.assertIn(str(self.missing), out)
        self.assertNothingWritten(out)

    def test_bad_corpus_flag_does_not_fall_through_to_env(self):
        code, out = self.emit("--corpus", str(self.missing), EDI_CORPUS=str(self.corpus))
        self.assertEqual(code, 2, out)
        self.assertIn(str(self.missing), out)
        self.assertNotIn("corpus source:", out)
        self.assertNothingWritten(out)

    def test_bad_env_corpus_is_a_usage_error_naming_the_variable(self):
        code, out = self.emit(EDI_CORPUS=str(self.missing))
        self.assertEqual(code, 2, out)
        self.assertIn("EDI_CORPUS", out)
        self.assertIn(str(self.missing), out)
        self.assertNothingWritten(out)

    def test_bad_require_value_is_a_usage_error_even_with_a_corpus(self):
        for val in ("yes", " 1"):
            with self.subTest(val=val):
                code, out = self.emit("--corpus", str(self.corpus), PLUMBLINE_REQUIRE_CORPUS=val)
                self.assertEqual(code, 2, out)
                self.assertIn("PLUMBLINE_REQUIRE_CORPUS", out)
                self.assertNothingWritten(out)

    # ---- a corpus resolves: its source is announced, the record and its pass are written and validated ----
    def test_corpus_flag_resolves_and_writes(self):
        code, out = self.emit("--corpus", str(self.corpus))
        self.assertEqual(code, 0, out)
        self.assertIn("corpus source: --corpus", out)
        self.assertIn("OK (schema-verified)", out)
        self.assertEqual(len(self.written()), 2, self.written())

    def test_env_corpus_resolves_and_writes(self):
        code, out = self.emit(EDI_CORPUS=str(self.corpus))
        self.assertEqual(code, 0, out)
        self.assertIn("corpus source: EDI_CORPUS", out)
        self.assertIn("OK (schema-verified)", out)
        self.assertEqual(len(self.written()), 2, self.written())

    def test_print_only_needs_no_corpus_and_writes_nothing(self):
        code, out = self.emit("--print-only")
        self.assertEqual(code, 0, out)
        self.assertNothingWritten(out)


if __name__ == "__main__":
    unittest.main()
