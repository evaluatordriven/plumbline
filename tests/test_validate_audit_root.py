#!/usr/bin/env python3
"""Bar for JOB 31: tests/validate_audit.py resolves its audit root from the repo it is run in.

THE DEFECT, quoted from the base (commit 6793e53ddc5071aa252be10f2c0fc18c5a5b0b35):

    tests/validate_audit.py:46
        DEVSPACE = Path(os.environ.get("PLUMBLINE_AUDIT_ROOT") or REPO.parent).expanduser()
    tests/validate_audit.py:113
        homes = [p for p in sorted(DEVSPACE.glob("*/dot-plumbline/audits")) if p.is_dir()]

With PLUMBLINE_AUDIT_ROOT unset, the search root is REPO.parent, and the suite globs
<parent>/*/dot-plumbline/audits. A checkout that ships no dot-plumbline/audits/ of its own,
sitting beside one that does, therefore reads the NEIGHBOUR's census and prints it as this
tree's. Measured by the Architect on 2026-11-09 in a git archive of the base: beside a
schema-valid neighbour it exits 0 and prints

    neighbour                1 record(s)
    --- neighbour/2026-12-01-fixture.json ---
      checked 1 record(s) from 1 home(s)
    ALL AUDIT RECORDS CONSISTENT

That is the mis-measure, and it is NOT an exit code. A base run and a correct run both exit
0 and both print a clean summary. Every assertion below is on WHICH RECORD IS NAMED — the
`--- <home>/<file> ---` section headers and the `checked N record(s) from M home(s)` coverage
line — never on the exit code alone.

THE SPINE IS THE COMPARATIVE FORM (2026-11-09, third authoring of this bar)
    The tree this bar lives in is now a clone with history, so `git archive BASE` in it
    succeeds and yields a fixed subject. The bar therefore measures TWO subjects in one
    room and asserts the DIFFERENCE between them:

      subject-base  a git archive of BASE (fixed bytes; the unfixed suite)  -> MUST name the neighbour
      subject-work  a copy of the tree this bar lives in (the suite as it is now) -> MUST NOT name it

    The base naming the neighbour is the ONE RED this bar is built on: it proves both that
    the defect is real and that the neighbour fixture is nameable. The work tree not naming
    it is the fix. The bar is red at the base (subject-work == subject-base there, so it
    names the neighbour) and green after the fix (subject-work differs). This is the form
    the loop can actually use, because the work tree now carries the history `git archive`
    needs.

    An earlier authoring built the subject only from the work tree, because a loop work
    tree had no .git and `git archive BASE` exited 128 there. That shape had to be red on a
    tree that was already fixed, or green on one that was not — it could not be an
    instrument. It is gone.

THE SUBJECT DOES NOT MOVE (option C, ratified by the Owner)
    PLUMBLINE_AUDIT_ROOT unset, in a checkout that ships no dot-plumbline/audits/ and sits
    beside one that does:
      - exit 0;
      - nothing from the neighbour is named as checked — not in the discovered homes, not
        in `checked N record(s) from M home(s)`;
      - the suite is not silenced into reading nothing everywhere: a clean parent with its
        own record still checks it, and an explicit PLUMBLINE_AUDIT_ROOT pointing at an
        empty directory still exits 0.

THE CORPUS DECISION — REFUSE WHEN A CORPUS IS SUPPLIED BY AMBIENT ENVIRONMENT
    Measured by the Architect on 2026-11-09: with EDI_CORPUS set in the environment to
    /home/jarbis1/Jarbis-PARA/5_Devspace/edi, the base prints `corpus source: EDI_CORPUS`,
    reads <that>@schemas/evaluator-record.schema.json and runs corpus.audit-equality — the
    run is not corpus-free. With a bogus EDI_CORPUS it exits 2. So the result of the same
    tree changes with an inherited variable, and that is not an instrument.

    The pin's vendored copy (schemas/vendor/e-di@<pin8>/) CANNOT be passed explicitly: it
    holds evaluator-record.schema.json and fixtures/ but no schemas/job-packet.schema.json,
    and tools/edi_corpus.py::_check refuses it as "not an E-DI corpus" (measured: exit 2).
    So the only honest choice left is the other one: THE BAR REFUSES AN AMBIENT CORPUS.

    Concretely, every subject run here is built from a clean environment with EDI_CORPUS and
    PLUMBLINE_REQUIRE_CORPUS REMOVED. Each run is therefore corpus-free by construction and
    prints `SKIP[corpus] corpus.audit-equality`. The hostile test (5) plants a bogus
    EDI_CORPUS and a bogus PLUMBLINE_AUDIT_ROOT in the ambient environment and shows the
    bar's run does not read them — and shows the SAME planted environment, run against the
    BASE, DOES name the decoy and read the corpus. That is what makes the hostile case able
    to fail: it fails against a suite that reads the ambient value (the base), and passes
    only for a suite that is run corpus-free.

FIXTURE NAMING. Generation is routed by filename date (validate_audit.py:61-66); only a name
on or after 2026-09-29 validates against the live schema. The fixture here is named
2026-12-01-fixture.json so it is schema-valid under the live generation and a "not named"
is about the root, never about a schema error.

Run:  python3 tests/test_validate_audit_root.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PY = sys.executable
REPO = Path(__file__).resolve().parent.parent
SUITE = "tests/validate_audit.py"
FIXTURE_NAME = "2026-12-01-fixture.json"

# The fixed base. Never the work tree's own HEAD: the subject must be the UNFIXED suite for
# the comparative red to mean anything. Pointing this at HEAD would be green by construction.
BASE = "6793e53ddc5071aa252be10f2c0fc18c5a5b0b35"

# Variables that make a run depend on the caller's environment rather than on the tree.
AMBIENT = ("PLUMBLINE_AUDIT_ROOT", "EDI_CORPUS", "PLUMBLINE_REQUIRE_CORPUS")

# A record schema-valid under the live (9999-12-31) generation the fixture name routes to.
FIXTURE_RECORD = {
    "passes": [{"pass_id": "p1", "kind": "scored", "status": "filed", "artifact": "pass-1.json"}],
    "dimensions": [{
        "name": "bar",
        "score": 1,
        "scale": "binary 0/1",
        "anchor_note": "1 = the check passes",
        "observation": "the reading this fixture stands for",
        "observation_channel": "python3 tests/validate_audit.py",
        "ground_truth_access": "blind_to_gt",
    }],
    "pass_rule": {"accept": 1, "dimension_floor": 1, "reject": 0, "cap": 2},
    "violations": [],
    "verdict": "accept",
    "ground_truth_ref": "fixture",
    "ground_truth_version": "0",
    "ground_truth_hardness": "DOCUMENT",
    "mandate_ref": {"doc": "fixture.md", "version": "0"},
    "instrument_in_force": {"version": "0", "rubric_sha256": "0" * 64, "code_sha256": "0" * 64},
    "evaluator_identity": "fixture-evaluator",
    "channel_blind": True,
    "ratified": True,
    "instance_extensions": [
        {"name": "artifact_ref", "label": "instance-specific", "value": "fixture"},
        {"name": "method_note", "label": "instance-specific", "value": "fixture"},
        {"name": "verdict_derivation", "label": "instance-specific", "value": "fixture"},
    ],
}


# ----------------------------------------------------------------------------- subject builders

def _ensure_base() -> None:
    """Make BASE resolvable in this checkout, or say why it is not.

    CI checks out SHALLOW (actions/checkout default depth 1), so a bar that archives a fixed
    ancestor commit fails there on absent history rather than on the property it measures.
    Measured 2026-11-09: the bar was kept out of the tree for exactly that reason. Fetching the
    one commit it needs makes the bar portable without weakening a single assertion.

    No silent skip: if the fetch fails, the archive below raises with the git stderr.
    """
    probe = subprocess.run(
        ["git", "cat-file", "-e", BASE + "^{commit}"], cwd=str(REPO), capture_output=True,
    )
    if probe.returncode == 0:
        return
    subprocess.run(
        ["git", "fetch", "--depth", "1", "origin", BASE],
        cwd=str(REPO), capture_output=True,
    )


def _archive_subject(dest: Path) -> Path:
    """`git archive BASE` in this tree, extracted into dest. One fixed subject.

    Raises RuntimeError naming BASE and the git stderr if the archive cannot be made — the
    bar refuses to measure rather than silently substituting the work tree.
    """
    dest.mkdir(parents=True)
    _ensure_base()
    arch = subprocess.run(
        ["git", "archive", BASE], cwd=str(REPO), capture_output=True,
    )
    if arch.returncode != 0:
        raise RuntimeError(
            "`git archive %s` failed in %s (rc=%d): %s" % (
                BASE, REPO, arch.returncode, arch.stderr.decode(errors="replace")[:400],
            )
        )
    tar = subprocess.run(["tar", "-x", "-C", str(dest)], input=arch.stdout, capture_output=True)
    if tar.returncode != 0:
        raise RuntimeError("tar extraction of the base archive failed (rc=%d): %s"
                           % (tar.returncode, tar.stderr.decode(errors="replace")[:400]))
    return dest


def _work_subject(dest: Path) -> Path:
    """A copy of the tree this bar lives in — the suite as it is now, no .git, no bar.

    Nothing is archived, checked out or reverted. The suite goes in as it is.
    """
    shutil.copytree(
        REPO, dest, symlinks=True,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc",
                                      "test_validate_audit_root.py"),
    )
    return dest


def _place_record(audits_dir: Path, name: str = FIXTURE_NAME, rec: dict | None = None) -> Path:
    audits_dir.mkdir(parents=True, exist_ok=True)
    path = audits_dir / name
    path.write_text(json.dumps(rec or FIXTURE_RECORD), encoding="utf-8")
    return path


# ----------------------------------------------------------------------------- run helpers

def _clean_env() -> dict:
    """The environment for a subject run: the caller's, minus every variable that leaks."""
    return {k: v for k, v in os.environ.items() if k not in AMBIENT}


def _run(subject: Path, override=None):
    """Run the suite in `subject`.

    PLUMBLINE_AUDIT_ROOT and the corpus variables are REMOVED from the environment (the bar
    refuses an ambient corpus); `override` sets the root explicitly.
    """
    env = _clean_env()
    if override is not None:
        env["PLUMBLINE_AUDIT_ROOT"] = str(override)
    proc = subprocess.run(
        [PY, SUITE], cwd=str(subject), env=env, capture_output=True, text=True, timeout=900,
    )
    return proc.returncode, proc.stdout + proc.stderr


def _named_records(output: str) -> list:
    """The records the run says it checked: the `--- <home>/<file> ---` section headers."""
    return sorted(re.findall(r"^--- ([A-Za-z0-9_.@-]+)/([A-Za-z0-9_.-]+) ---$", output, re.M))


def _named_homes(output: str) -> list:
    """The homes the run says it discovered records in: the `<home> N record(s)` census lines."""
    return re.findall(r"^\s+(\S+)\s+\d+ record\(s\)$", output, re.M)


def _checked(output: str):
    """The `checked N record(s) from M home(s)` coverage line, or None."""
    m = re.search(r"checked (\d+) record\(s\) from (\d+) home\(s\)", output)
    return (int(m.group(1)), int(m.group(2))) if m else None


class ValidateAuditRootTest(unittest.TestCase):
    """One room per test: a temp parent holding subject-base/ and subject-work/."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="job31-bar-")
        self.tmp = Path(self._tmp.name)
        self.parent = self.tmp / "parent"
        self.parent.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _subjects(self):
        """The one fixed base subject and the work subject, built in this test's parent."""
        base = _archive_subject(self.parent / "subject-base")
        work = _work_subject(self.parent / "subject-work")
        return base, work

    # ------------------------------------------------------------------ guards (kept in their own right)

    def test_0a_the_suite_is_present_in_both_subjects(self):
        """Provenance guard: without the suite nothing below means anything; refuse by name."""
        base, work = self._subjects()
        for name, tree in (("subject-base", base), ("subject-work", work)):
            self.assertTrue(
                (tree / SUITE).is_file(),
                "%s does not contain %s; the bar cannot measure a suite that is not there"
                % (name, SUITE),
            )

    def test_0b_the_subjects_ship_no_audits_of_their_own(self):
        """The option-C case requires a checkout with NO dot-plumbline/audits/ of its own."""
        base, work = self._subjects()
        for name, tree in (("subject-base", base), ("subject-work", work)):
            self.assertFalse(
                (tree / "dot-plumbline" / "audits").is_dir(),
                "%s ships a dot-plumbline/audits/; checks 1-2 measure a checkout with none, "
                "so the neighbour case they describe does not arise in %s" % (name, name),
            )

    def test_0c_the_neighbour_fixture_is_a_census_a_suite_can_read(self):
        """Guard: the neighbour record IS named when the root is pointed at the parent that holds it.

        Turns a later 'not named' from a possible silence into a measured absence: if the
        fixture cannot be named even under an explicit root, a suite that reads nothing
        everywhere would pass checks 1-2 by accident.
        """
        base, work = self._subjects()
        _place_record(self.parent / "neighbour" / "dot-plumbline" / "audits")

        code, out = _run(work, override=self.parent)

        self.assertIn(
            ("neighbour", FIXTURE_NAME), _named_records(out),
            "the neighbour fixture must be nameable when the root is pointed at the directory "
            "that holds it; otherwise a later 'not named' proves only that the fixture was "
            "never visible. named=%r\n%s" % (_named_records(out), out),
        )
        self.assertEqual(code, 0, "a schema-valid fixture under an explicit root must exit 0; "
                                  "exited %d.\n%s" % (code, out))

    # ------------------------------------------------------------------ the spine (comparative)

    def test_1_the_base_names_the_neighbour_and_the_work_tree_does_not(self):
        """THE SPINE. One room, two subjects, one assertion on the difference.

        subject-base (fixed bytes of BASE) MUST name the neighbour's record as checked — this
        is the one red, and it proves the defect is real and the fixture nameable.
        subject-work (the tree this bar lives in) MUST NOT name it — this is the fix.
        """
        base, work = self._subjects()
        _place_record(self.parent / "neighbour" / "dot-plumbline" / "audits")

        base_code, base_out = _run(base, override=None)
        work_code, work_out = _run(work, override=None)

        # (a) the red: the base reads the neighbour as this tree's.
        self.assertIn(
            ("neighbour", FIXTURE_NAME), _named_records(base_out),
            "the base (git archive %s) must name the neighbour's record as checked; if it does "
            "not, the room is not exercising the defect and the red below is vacuous. "
            "named=%r rc=%d\n%s" % (BASE, _named_records(base_out), base_code, base_out),
        )

        # (b) the fix: the work tree does not.
        self.assertNotIn(
            ("neighbour", FIXTURE_NAME), _named_records(work_out),
            "the work tree's suite named the neighbour's record as checked by a checkout that "
            "does not contain it; it read a sibling tree as this one. named=%r rc=%d\n%s"
            % (_named_records(work_out), work_code, work_out),
        )
        self.assertNotIn(
            "neighbour", _named_homes(work_out),
            "the work tree's suite reported the neighbour's census as this tree's. homes=%r\n%s"
            % (_named_homes(work_out), work_out),
        )
        checked = _checked(work_out)
        if checked is not None:
            self.assertEqual(
                checked, (0, 0),
                "a checkout with no records of its own must report checking none; reported "
                "%d record(s) from %d home(s).\n%s" % (checked[0], checked[1], work_out),
            )

    def test_2_the_c_case_exits_zero_and_states_it_read_nothing(self):
        """The C case on the work tree: no override, exit 0, and it says it read nothing.

        The exit code alone is green at the base; the naming half is check 1. Both are here
        so the Owner's ruling is written down as the Owner wrote it.
        """
        _, work = self._subjects()
        _place_record(self.parent / "neighbour" / "dot-plumbline" / "audits")

        code, out = _run(work, override=None)

        self.assertNotIn(
            ("neighbour", FIXTURE_NAME), _named_records(out),
            "the C case: with no override the neighbour's record must not be named as "
            "checked.\n%s" % out,
        )
        self.assertEqual(
            code, 0,
            "the C case: a checkout with no audits of its own and no override must exit 0 "
            "as an explicit empty root does; exited %d.\n%s" % (code, out),
        )

    # ------------------------------------------------------------------ guards that the fix is not silence

    def test_3_the_override_still_works_on_the_work_tree(self):
        """PLUMBLINE_AUDIT_ROOT=<empty dir> is honoured on the work tree: exit 0, nothing named."""
        _, work = self._subjects()
        _place_record(self.parent / "neighbour" / "dot-plumbline" / "audits")
        empty = self.tmp / "empty-root"
        empty.mkdir()

        code, out = _run(work, override=empty)

        self.assertEqual(code, 0, "an explicit empty root must exit 0; exited %d.\n%s" % (code, out))
        self.assertEqual(
            _named_records(out), [],
            "an explicit empty root must name no record as checked and must not fall through "
            "to the neighbour; named=%r\n%s" % (_named_records(out), out),
        )

    def test_4_a_clean_parent_with_its_own_record_is_still_checked(self):
        """Guard: the work tree has not been silenced into reading nothing everywhere.

        A checkout carrying its own dot-plumbline/audits/ with one record, in a parent with no
        other checkout, must still check that record.
        """
        _, work = self._subjects()
        _place_record(work / "dot-plumbline" / "audits")

        code, out = _run(work, override=None)

        self.assertIn(
            ("subject-work", FIXTURE_NAME), _named_records(out),
            "a checkout carrying its own record must still check it; named=%r\n%s"
            % (_named_records(out), out),
        )
        self.assertIn(
            "subject-work", _named_homes(out),
            "the checkout's own census must be listed; homes=%r\n%s" % (_named_homes(out), out),
        )
        checked = _checked(out)
        self.assertIsNotNone(
            checked, "the run must state coverage; no 'checked N record(s)' line.\n%s" % out)
        self.assertEqual(
            checked, (1, 1),
            "the checkout's own one record must be the one checked; stated %r.\n%s" % (checked, out))
        self.assertEqual(code, 0, "checking its own valid record must exit 0; exited %d.\n%s"
                                  % (code, out))

    # ------------------------------------------------------------------ the corpus defect, as a test

    def test_5_a_corpus_or_root_supplied_by_the_environment_is_not_silently_read(self):
        """REFUSE-ON-AMBIENT, proven non-vacuous.

        The bar refuses a corpus supplied by ambient environment: it runs every subject with
        EDI_CORPUS / PLUMBLINE_REQUIRE_CORPUS removed, so each run is corpus-free by
        construction. This test proves three things:

          (a) the bar's own run of the work tree, with no ambient corpus and no ambient root,
              prints SKIP[corpus] and does not name a home planted anywhere by the caller —
              it is corpus-free and root-clean;
          (b) the SAME junk planted in the ambient environment, run against the BASE without
              the bar's scrub, DOES name the decoy home and read the ambient corpus — so the
              hostile case can fail, and it fails for a suite that reads the ambient value.
              A case that cannot fail is not a case;
          (c) a bogus EDI_CORPUS is refused by name (exit 2, the value quoted), not read.
        """
        base, work = self._subjects()
        _place_record(self.parent / "neighbour" / "dot-plumbline" / "audits")

        decoy_root = self.tmp / "decoy-audits"
        _place_record(decoy_root / "decoy-home" / "dot-plumbline" / "audits",
                      name="2026-12-01-decoy.json")
        bogus_corpus = str(self.tmp / "no-such-corpus")

        # (a) the bar's ordinary run is corpus-free and does not see a caller-planted root.
        _, work_out = _run(work, override=None)
        self.assertNotIn(
            "decoy-home", work_out,
            "the work tree's run named a home that exists only under a caller's planted root; "
            "the bar's clean environment is not reaching the subject.\n%s" % work_out,
        )
        self.assertNotIn(
            "corpus source:", work_out,
            "the work tree's run read a corpus; the bar must run corpus-free.\n%s" % work_out,
        )
        self.assertIn(
            "SKIP[corpus]", work_out,
            "a corpus-free run must say so with SKIP[corpus]; its absence means the corpus "
            "gate was not exercised.\n%s" % work_out,
        )

        # (b) non-vacuity: the same planted environment, without the bar's scrub, IS read.
        env = _clean_env()
        real = os.environ.get("EDI_CORPUS")
        if real:
            env["EDI_CORPUS"] = real
        env["PLUMBLINE_AUDIT_ROOT"] = str(decoy_root)
        proc = subprocess.run([PY, SUITE], cwd=str(base), env=env,
                              capture_output=True, text=True, timeout=900)
        base_planted = proc.stdout + proc.stderr
        self.assertIn(
            "decoy-home", base_planted,
            "the base, run with a PLUMBLINE_AUDIT_ROOT planted in the environment, must name "
            "the decoy home; if it does not, check (a) proves only that the decoy was never "
            "visible. This is the non-vacuity of the hostile case.\n%s" % base_planted,
        )
        if real:
            self.assertIn(
                "corpus source:", base_planted,
                "the base, run with the ambient EDI_CORPUS left in place, must read it; if it "
                "does not, the corpus half of the hostile case is vacuous.\n%s" % base_planted,
            )

        # (c) a bogus corpus is refused by name, never read.
        env = _clean_env()
        env["EDI_CORPUS"] = bogus_corpus
        proc = subprocess.run([PY, SUITE], cwd=str(work), env=env,
                              capture_output=True, text=True, timeout=900)
        refused = proc.stdout + proc.stderr
        self.assertEqual(
            proc.returncode, 2,
            "a set EDI_CORPUS that is not a corpus must be a usage error (exit 2); exited %d.\n%s"
            % (proc.returncode, refused),
        )
        self.assertIn(
            bogus_corpus, refused,
            "the refusal must name the offending value, not fall through silently.\n%s" % refused,
        )


if __name__ == "__main__":
    unittest.main()
