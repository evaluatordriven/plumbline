"""The corpus opt-in rules (D-E), held as unit tests of tools/edi_corpus.py.

No corpus is needed and nothing is skipped: each test builds a throwaway directory that looks like a corpus
(it has schemas/job-packet.schema.json) or deliberately does not.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import edi_corpus  # noqa: E402

CLEAN = {k: v for k, v in os.environ.items()
         if k not in (edi_corpus.REQUIRE_VAR, edi_corpus.CORPUS_VAR, "HERMES_HOME")}


class _Env(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.corpus = self.tmp / "corpus"
        (self.corpus / "schemas").mkdir(parents=True)
        (self.corpus / "schemas" / "job-packet.schema.json").write_text("{}\n")
        env = dict(CLEAN, HOME=str(self.home))
        self._patch = mock.patch.dict(os.environ, env, clear=True)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def resolve_quiet(self, *a, **k):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            got = edi_corpus.resolve(*a, **k)
        return got, out.getvalue()


class RequireCorpus(_Env):
    def test_only_1_turns_it_on(self):
        os.environ[edi_corpus.REQUIRE_VAR] = "1"
        self.assertTrue(edi_corpus.require_corpus())

    def test_unset_empty_and_0_leave_it_off(self):
        self.assertFalse(edi_corpus.require_corpus())
        for v in ("", "0"):
            os.environ[edi_corpus.REQUIRE_VAR] = v
            self.assertFalse(edi_corpus.require_corpus(), v)

    def test_any_other_value_is_a_usage_error_naming_the_variable(self):
        for v in ("true", "yes", "on", "2", " 1", "1 ", "TRUE", "01"):
            os.environ[edi_corpus.REQUIRE_VAR] = v
            with self.assertRaises(edi_corpus.CorpusUsageError, msg=v) as cm:
                edi_corpus.require_corpus()
            self.assertIn(edi_corpus.REQUIRE_VAR, str(cm.exception))


class Resolution(_Env):
    def test_nothing_set_resolves_to_none(self):
        self.assertIsNone(self.resolve_quiet()[0])

    def test_empty_edi_corpus_counts_as_unset(self):
        os.environ[edi_corpus.CORPUS_VAR] = ""
        self.assertIsNone(self.resolve_quiet()[0])

    def test_edi_corpus_resolves_with_its_source(self):
        os.environ[edi_corpus.CORPUS_VAR] = str(self.corpus)
        got, _ = self.resolve_quiet()
        self.assertEqual((got.path, got.source), (self.corpus.resolve(), "EDI_CORPUS"))

    def test_explicit_wins_over_edi_corpus(self):
        os.environ[edi_corpus.CORPUS_VAR] = str(self.tmp / "nowhere")
        got, _ = self.resolve_quiet(str(self.corpus))
        self.assertEqual(got.source, "--corpus")

    def test_bad_edi_corpus_is_an_error_naming_the_path(self):
        for bad in (self.tmp / "nowhere", self.home):        # missing, and a directory that is not a corpus
            os.environ[edi_corpus.CORPUS_VAR] = str(bad)
            with self.assertRaises(edi_corpus.CorpusUsageError) as cm:
                self.resolve_quiet()
            self.assertIn(str(bad), str(cm.exception))

    def test_bad_edi_corpus_never_falls_through_to_hermes(self):
        hh = self.tmp / "hermes"
        hh.mkdir()
        (hh / "config.yaml").write_text(f"plugins:\n  edi-loop:\n    corpus: {self.corpus}\n")
        os.environ["HERMES_HOME"] = str(hh)
        os.environ[edi_corpus.CORPUS_VAR] = str(self.tmp / "nowhere")
        with self.assertRaises(edi_corpus.CorpusUsageError):
            self.resolve_quiet()

    def test_need_lists_what_the_caller_reads(self):
        os.environ[edi_corpus.CORPUS_VAR] = str(self.corpus)
        with self.assertRaises(edi_corpus.CorpusUsageError) as cm:
            self.resolve_quiet(need=("tools/validate_job_packet.py",))
        self.assertIn("tools/validate_job_packet.py", str(cm.exception))

    def test_unreadable_hermes_config_is_reported_with_its_path(self):
        hh = self.tmp / "hermes"
        hh.mkdir()
        cfg = hh / "config.yaml"
        cfg.write_text("plugins: [unclosed\n  edi-loop: {corpus\n")
        os.environ["HERMES_HOME"] = str(hh)
        got, out = self.resolve_quiet()
        self.assertIsNone(got)
        self.assertIn(str(cfg), out)
        self.assertIn("was not read", out)

    def test_hermes_is_not_consulted_when_the_caller_opts_out(self):
        hh = self.tmp / "hermes"
        hh.mkdir()
        (hh / "config.yaml").write_text("plugins: [unclosed\n")
        os.environ["HERMES_HOME"] = str(hh)
        got, out = self.resolve_quiet(hermes=False)
        self.assertEqual((got, out), (None, ""))


class LineForms(_Env):
    def lines(self, fn, *a):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ret = fn(*a)
        return ret, out.getvalue()

    def test_skip_fail_ran_and_source_lines(self):
        self.assertEqual(self.lines(edi_corpus.not_run, "corpus.run-cases", False, "why"),
                         (False, "SKIP[corpus] corpus.run-cases: why\n"))
        ret, out = self.lines(edi_corpus.not_run, "corpus.run-cases", True, "why")
        self.assertTrue(ret)
        self.assertTrue(out.startswith("FAIL[corpus] corpus.run-cases: "))
        self.assertIn(edi_corpus.REQUIRE_VAR, out)
        self.assertEqual(self.lines(edi_corpus.ran, "corpus.build-check", True)[1],
                         "RAN[corpus] corpus.build-check: pass\n")
        self.assertEqual(self.lines(edi_corpus.ran, "corpus.build-check", False)[1],
                         "RAN[corpus] corpus.build-check: fail\n")
        c = edi_corpus.Corpus(self.corpus, "EDI_CORPUS", str(self.corpus))
        self.assertEqual(self.lines(c.announce)[1], "corpus source: EDI_CORPUS\n")

    def test_the_five_ids(self):
        self.assertEqual(sorted(edi_corpus.IDS), ["corpus.audit-equality", "corpus.battery-equality",
                                                  "corpus.build-check", "corpus.pin-on-disk",
                                                  "corpus.run-cases"])


if __name__ == "__main__":
    unittest.main()
