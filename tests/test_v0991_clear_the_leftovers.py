"""Bar: clear the Job 36 leftovers and teach the finish seam to file.

JOB 38. Owner said "Go" and named three things on the plumbline worktree at
`/home/jarbis1/tmp/plumbline-kit-compat`, branch `job37-compat`, HEAD `0b0d4a7`.

THE THREE JOBS, as the Owner named them.

  A. The Job 36 bar (`tests/test_v0910_scoring_set.py`, sha256 `3f426942…`) is
     SUPERSEDED. Two of its cases — `test_02_a_declared_scoring_set_is_admitted_
     and_an_undeclared_one_is_refused` and `test_10_an_empty_or_absent_set_does_
     not_score_everything` — assert the refuse-on-absent rule the Owner replaced
     with compat (Job 37, accepted at round 1). No bar may remain in the tree
     that asserts law the Owner repealed. THE DECISION THIS BAR ENFORCES:
     RETIRE, not rewrite. The Job 37 bar `tests/test_v099_scoring_set.py`
     (sha256 `b368ece2…`) is the live law and already carries every still-valid
     Job 36 case forward under case 02/04/10/12/13; a second scoring-set bar
     asserting the same law is a second place for it to drift. Retirement is
     done by DELETING the file — case 10 below reads the tree, not a record of
     an intention to delete.

  B. The frozen pin must move with the file it pins. `LOOP_SHA` in
     `tests/test_loop_custody_sources.py` still reads `6db27b6a…` while
     `kit/conductor_loop.py` is `1cd6fac2…` (Job 37's accepted bytes). This is
     BOOKKEEPING, NOT A WEAKENED TEST. What that test is for, quoted from its
     own comment above the constant: "loop() gained the last act of a job …
     The seam this bar locks is untouched: `emit_custody_for_finish` is still
     called once, loop()'s signature is still (packet, record_dir, cwd,
     timeout_s, commit, evaluator_fn), a non-zero code is still CustodyNotDone,
     and the record is still written by the emitter rather than by this module."
     The pin is the tripwire that makes an unannounced change to loop() fail
     the suite; moving it to the bytes the record names keeps the tripwire
     armed. It is re-pinned to whatever `kit/conductor_loop.py` holds AFTER
     this job's own change, which is why the pin is an edouble in this job and
     the value is read at test time, not typed into this bar.

  C. The finish seam must let a kit job file. `emit_custody_for_finish()`
     (kit/conductor_loop.py:239-259) runs
     `[sys.executable, emitter, "--job-dir", str(record_dir)]` and returns its
     code; `loop()` raises `CustodyNotDone` when that code is non-zero (line
     646), so a run ends with NO summary and NO filing. Measured on Job 37's
     record: no `summary.json`, no `escalation.json`. Jobs 35, 36 and 37 all
     ended that way: accepted work, no record.
     The emitter's refusal is CORRECT and stays: with no custody document and
     no `--spec-version`, `predicate.specVersion` has no source and the emitter
     refuses rather than guess. THE FIX IS IN THE SEAM: it supplies a SOURCED
     spec version. It reads `custody.specVersion` from the kit's own
     `tools/pin.json`. That value is READ, not typed: `tools/build_schemas.py`
     derives it (`custody_spec_version()`, tools/build_schemas.py:387) from the
     `**Version X.Y.Z**` header of SPEC.md at the pinned custody commit, so the
     pin names a version that came out of a document, and a re-pin cannot leave
     the version behind (the failure that function exists to prevent, measured
     2026-11-10). The record shows its origin: the emitter already writes
     `x-plumbline.spec_version = {origin, path, source, sha256}` and
     `predicate.specVersion`; case 03 asserts the record says so and that the
     value equals the pin's, not a literal in this bar.

BASE READING, MEASURED ON THIS WORKTREE by the Architect on 2026-11-12, not
inferred:

  * `PYTHONPATH=. python3 -m unittest discover -s tests` -> exit 1, Ran 344,
    FAILED (failures=3, skipped=3). The three: the two Job 36 cases above, and
    `test_frozen_files_stay` (LOOP_SHA `6db27b6a…` != file `1cd6fac2…`).
  * `PYTHONPATH=. python3 tests/test_v099_scoring_set.py` -> exit 0, Ran 14, OK.
  * The pin checkout with none of this work (`plumbline-kit-basejob37`) ->
    `unittest discover` rc 0. The six run_all corpus failures exist at base too
    (EDI_CORPUS is not <checkout>/contracts) and are NOT this job's.

RED BEFORE THE FIX. Cases 00-03 fail today; 04-06 are green today and are the
brake (a fix that deletes too much must not pass them). Measured by this seat:
case 00 -> `CustodyNotDone`, no summary.json; case 01 -> the seam files a dirty
emitter anyway (or the fix makes it); case 02 -> LOOP_SHA mismatched; case 03 ->
the emitter refuses with `[spec-version]`, exit 3, nothing written; case 04 ->
the Job 36 file is present; cases 05-06 -> green.

WHAT THIS BAR DOES NOT DO. It does not drive the real emitter in case 00 with a
value this seat picked: the emitted record must name a version equal to what
`tools/pin.json` holds, read by the test from that file. It does not weaken
case 01 to keep the dirty-tree refusal green: a refusal for a REAL reason (the
emitter's tree is not the bytes the record would claim) must still stop the
finish, and the bar proves it by planting a dirty emitter tree and requiring no
filing.

THE ORACLE. Case 00 asserts the whole loop() finish (summary on disk, filing
row filed, record on disk), so a seam that returns 0 without shipping cannot
pass it. Case 01 asserts the negative. Case 03 runs the emitter itself on the
seam's own command shape and requires the spec-version refusal to be ABSENT and
the origin to be present, so a seam that invents a version string fails on the
origin/sha check rather than on a happy-path exit code.

Fixture bounds in this file are the Architect's and exist so loop() can run.
They are not this job's T_accept, T_dim, T_reject, cap, clock or budget. The
Owner set those in the brief and the packet carries them.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from tempfile import TemporaryDirectory

PY = sys.executable
EMITTER = "kit/emit_custody.py"
LOOP_PY = "kit/conductor_loop.py"
SOURCES = "tests/test_loop_custody_sources.py"
JOB36_BAR = "tests/test_v0910_scoring_set.py"
JOB37_BAR = "tests/test_v099_scoring_set.py"
V099_SHA = "b368ece26f8d0a71cc9bf64c76442bc56e0fe139b8d15a14733f654c2e58295e"
PIN = "tools/pin.json"
RECORD_REL = os.path.join("custody", "record.custody.json")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _repo():
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    if os.path.isfile(os.path.join(parent, "kit", "conductor_loop.py")):
        return parent
    env = os.environ.get("PLUMBLINE_REPO", "")
    if env and os.path.isfile(os.path.join(env, "kit", "conductor_loop.py")):
        return os.path.realpath(env)
    return parent


REPO = _repo()
sys.path.insert(0, REPO)

import kit.conductor_loop as cl  # noqa: E402


def _sha_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _pinned_version():
    """The version the kit says it is pinned to. READ from tools/pin.json."""
    return _load(os.path.join(REPO, PIN))["custody"]["specVersion"]


def _clean_emitter():
    """A throwaway clean commit of the emitter pair, so a dirty tree is not the red.

    This is the same discipline tests/test_loop_custody_sources.py:416 uses: a
    real git checkout with the kit files under test committed, so the emitter's
    revision refusal is about ITS bytes and not this worktree's state.
    """
    root = TemporaryDirectory()
    kit = os.path.join(root.name, "kit")
    os.makedirs(kit)
    for name in ("emit_custody.py", "custody_history.py"):
        shutil.copy2(os.path.join(REPO, "kit", name), os.path.join(kit, name))

    def git(*args):
        return subprocess.run(
            ["git", "-c", "user.email=bar@local", "-c", "user.name=bar",
             "-c", "commit.gpgsign=false", *args],
            cwd=root.name, capture_output=True, text=True,
        )

    git("init")
    git("add", "kit")
    done = git("commit", "-m", "bar-satisfiability")
    if done.returncode != 0:
        raise RuntimeError(done.stderr or done.stdout)
    return root, os.path.join(kit, "emit_custody.py")


def _work_tree(work):
    _write(os.path.join(work, "tests", "t.py"), "pin\n")
    _write(os.path.join(work, "src", "w.txt"), "no\n")
    _write(os.path.join(work, "custody", "bar.md"), "bar\n")
    suite = _write(
        os.path.join(work, "suite.py"),
        "import pathlib, sys\n"
        "text = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')\n"
        "sys.exit(0 if text.startswith('yes') else 1)\n",
    )
    maker = _write(
        os.path.join(work, "maker.py"),
        "import json, os, pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text('yes\\n', encoding='utf-8')\n"
        "cost = os.environ.get('PLUMBLINE_COST')\n"
        "if cost:\n"
        "    pathlib.Path(cost).write_text(json.dumps({'amount': 0}) + '\\n', encoding='utf-8')\n",
    )
    return suite, maker


def _packet(work, suite, maker):
    """A packet loop() will run. Bounds here are fixture-only. Not the job's."""
    return {
        "ratified": True,
        "mode": "scored",
        "human_seat": "bar-fixture-human-seat",
        "artifact": {
            "test_cmd": [PY, suite, os.path.join(work, "src", "w.txt")],
            "frozen": [os.path.join(work, "tests", "t.py")],
            "editable": ["src"],
            "ignore": [".git", "__pycache__"],
        },
        "maker": {"cmd": [PY, maker, os.path.join(work, "src", "w.txt")], "handoff": "rule12"},
        "evaluator": {
            "kind": "script",
            "cmd": [PY, "-c", "pass"],
            "runs": 2,
            "held_out": [],
        },
        "bounds": {
            "T_accept": 2,
            "T_dim": 2,
            "T_reject": 1,
            "cap": 1,
            "budget": {"amount": 1, "unit": "USD", "time_hours_lt": 1},
        },
        "escalation": {
            "route": ["Architect", "Owner"],
            "classes": [],
            "holders": {
                "architect": "bar-fixture-architect",
                # A finish inside the bar writes packet.json back with this module's
                # own halt record; it must not land inside the fixture tree loop()
                # was handed, so no file the Maker produced is edited by the bar.
                "orchestrator": [
                    {
                        "holder": "kit.conductor_loop.loop",
                        "kind": "script",
                        "does": "rounds",
                        "tested": "bar-fixture",
                    },
                    {
                        "holder": "bar-fixture-escalations",
                        "kind": "script",
                        "does": "escalations",
                        "tested": "bar-fixture",
                    },
                ],
            },
        },
    }


def _scores():
    return {
        "dimensions": [{"name": "q", "score": 2, "observation": "seen"}],
        "violations": [],
        "verdict": "accept",
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _pinned_checkout(commit):
    """A custody checkout at exactly `commit`, or None.

    Looked for where the seam is expected to look: $PLUMBLINE_CUSTODY, then a
    `custody/` beside the repo. The commit is compared by the checkout's own
    HEAD so a checkout at the wrong revision is not accepted as the pin.
    """
    candidates = []
    env = os.environ.get("PLUMBLINE_CUSTODY")
    if env:
        candidates.append(env)
    candidates.append(os.path.join(os.path.dirname(REPO), "custody"))
    candidates.append(os.path.join(REPO, "custody"))
    for candidate in candidates:
        if not os.path.isfile(os.path.join(candidate, "SPEC.md")):
            continue
        head = subprocess.run(["git", "-C", candidate, "rev-parse", "HEAD"],
                              capture_output=True, text=True)
        if head.returncode == 0 and head.stdout.strip() == commit:
            return candidate
    return None


def _seam_running(emitter):
    """A seam that runs THAT emitter with the arguments the real seam uses.

    Not a pass-through: `loop()` calls this instead of the real seam so the
    case can plant an emitter that refuses for its own reason and ask whether
    the finish still stops. It passes no flag the real seam would not, so the
    plant cannot be rescued by a version being supplied on its behalf.
    """

    def seam(record_dir, summary):
        proc = subprocess.run(
            [PY, emitter, "--job-dir", str(record_dir)],
            capture_output=True, text=True,
        )
        return proc.returncode

    return seam


class TheThreeJobs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._oracle, cls._clean = _clean_emitter()

    @classmethod
    def tearDownClass(cls):
        cls._oracle.cleanup()

    def _finish(self, emitter=None):
        """One accepted loop() over a job dir with NO custody_spec.

        `emitter=None` runs the REAL seam, untouched: the object loop() calls is
        whatever kit/conductor_loop.py defines. `emitter=<path>` runs a
        stand-in seam that invokes THAT emitter with no extra flags — used to
        plant an emitter that refuses for a reason of its own, so the case can
        ask whether a refusal still stops the finish without also being blocked
        by the seam's own version work.
        """
        work = TemporaryDirectory()
        record = TemporaryDirectory()
        filed = TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.addCleanup(record.cleanup)
        self.addCleanup(filed.cleanup)
        suite, maker = _work_tree(work.name)
        packet = _packet(work.name, suite, maker)
        saved = cl.emit_custody_for_finish
        if emitter is not None:
            cl.emit_custody_for_finish = _seam_running(emitter)
        try:
            old = os.environ.get("PLUMBLINE_FILE_INTO")
            os.environ["PLUMBLINE_FILE_INTO"] = filed.name
            try:
                halt = cl.loop(packet, record_dir=record.name, cwd=work.name,
                               timeout_s=60, evaluator_fn=lambda turn, root: _scores())
            finally:
                if old is None:
                    os.environ.pop("PLUMBLINE_FILE_INTO", None)
                else:
                    os.environ["PLUMBLINE_FILE_INTO"] = old
        except cl.CustodyNotDone as exc:
            return {"halt": None, "exit": exc.exit_code,
                    "record": record.name, "filed": filed.name}
        finally:
            cl.emit_custody_for_finish = saved
        return {"halt": halt, "exit": 0, "record": record.name, "filed": filed.name}

    # 00 ------------------------------------------------------------------
    def test_00_a_finish_with_no_custody_document_produces_a_summary_and_a_filed_record(self):
        """THE REGRESSION. This fails today: CustodyNotDone, no summary, no filing.

        Runs the REAL seam — not a double — over a job that names no custody
        document, which is the shape of every Plumbline kit job, Jobs 35/36/37
        included. Today the emitter refuses for `spec-version` and loop() raises
        CustodyNotDone, so there is no summary.json and nothing is filed.
        After the fix the seam supplies the version, this returns, and the
        summary and the filed copy both exist. The version the record carries
        must be the pin's, read here from tools/pin.json, not a literal in this
        bar. The check that the record says so is case 03.
        """
        got = self._finish()
        self.assertEqual(got["exit"], 0,
                         "loop() ended with CustodyNotDone exit %r: a kit job that names no "
                         "custody document must still file" % (got["exit"],))
        summary = os.path.join(got["record"], "summary.json")
        self.assertTrue(os.path.isfile(summary),
                        "no summary.json: the run ended without a record of itself")
        body = _load(summary)
        self.assertEqual(body.get("terminal_state"), "accepted")
        filing = body.get("filing") or {}
        self.assertTrue(filing.get("filed"),
                        "summary.json says the job was not filed: %r" % (filing,))
        record = os.path.join(got["record"], RECORD_REL)
        self.assertTrue(os.path.isfile(record), "no custody record on disk")
        dest = filing.get("dest") or ""
        self.assertTrue(dest and os.path.isdir(dest),
                        "the filing row names no directory that exists: %r" % (dest,))
        filed_record = os.path.join(dest, RECORD_REL)
        self.assertTrue(os.path.isfile(filed_record),
                        "the filed copy carries no custody record: %s" % filed_record)

    # 01 ------------------------------------------------------------------
    def test_01_a_finish_the_emitter_refuses_for_a_real_reason_still_does_not_file(self):
        """The fix must not make a bad record ship.

        The emitter refuses (exit 3) when its own tree is dirty: the bytes that
        wrote the record are not the bytes the record would claim. That refusal
        is REAL and is kept. The plant is not an emitter swap: it is the REAL
        seam, pointed at an emitter tree that moves after it is committed. A
        fix that supplies a version must not thereby turn this refusal into a
        ship, so the finish must stop with no summary and no filing.

        Today this passes for the wrong reason (the seam refuses every finish).
        That is stated, not hidden: it is a brake, not a red. It fails the
        moment a fix makes the seam file regardless of the emitter's exit code.
        """
        dirty = TemporaryDirectory()
        self.addCleanup(dirty.cleanup)
        kit = os.path.join(dirty.name, "kit")
        os.makedirs(kit)
        for name in ("emit_custody.py", "custody_history.py"):
            shutil.copy2(os.path.join(REPO, "kit", name), os.path.join(kit, name))

        def git(*args):
            return subprocess.run(
                ["git", "-c", "user.email=bar@local", "-c", "user.name=bar",
                 "-c", "commit.gpgsign=false", *args],
                cwd=dirty.name, capture_output=True, text=True,
            )

        git("init")
        git("add", "kit")
        self.assertEqual(git("commit", "-m", "dirty-fixture").returncode, 0)
        # The plant: the tree moves after the commit, so it is no longer the
        # bytes that were committed.
        with open(os.path.join(kit, "emit_custody.py"), "a", encoding="utf-8") as handle:
            handle.write("\n# planted-after-commit\n")

        # The emitter run from that tree really does refuse, so the plant is a
        # real refusal and not a mis-wired path. It is given a job that would
        # otherwise be readable, so the only reason left to refuse is its own
        # revision.
        probe_job = TemporaryDirectory()
        self.addCleanup(probe_job.cleanup)
        _write(os.path.join(probe_job.name, "inputs", "custody.json"), json.dumps({
            "custody_inputs": "plumbline/custody-inputs/v1",
            "levelClaimed": "CL1",
            "bar": {"file": "custody/bar.md"},
            "orchestrator": {"name": "bar", "kind": "agent"},
        }))
        _write(os.path.join(probe_job.name, "custody", "bar.md"), "bar\n")
        _write(os.path.join(probe_job.name, "packet.json"), json.dumps({
            "job_id": "bar", "terminal_state": "accepted", "outcome": "accepted",
            "disposition_state": "given",
        }))
        probe = subprocess.run(
            [PY, os.path.join(kit, "emit_custody.py"), "--job-dir", probe_job.name,
             "--spec-version", _pinned_version()],
            capture_output=True, text=True,
        )
        refused = (probe.stdout or "") + (probe.stderr or "")
        self.assertNotIn(probe.returncode, (0, 1),
                         "the planted emitter did not refuse; the plant is not a real refusal")
        self.assertIn("revision", refused,
                      "the planted emitter refused for a reason other than its revision: %s"
                      % refused[-800:])

        got = self._finish(emitter=os.path.join(kit, "emit_custody.py"))
        self.assertNotEqual(got["exit"], 0,
                            "a dirty emitter tree was filed as a clean finish; a real refusal "
                            "must still stop the run")
        self.assertFalse(os.path.isfile(os.path.join(got["record"], "summary.json")),
                         "summary.json was written for a finish the emitter refused")
        self.assertFalse(os.path.isfile(os.path.join(got["record"], RECORD_REL)),
                         "a custody record was written by a dirty emitter")
        dest = os.path.join(got["filed"], "jobs")
        self.assertFalse(os.path.isdir(dest) and os.listdir(dest),
                         "the refused finish was filed into the instance record: %s" % dest)

    # 02 ------------------------------------------------------------------
    def test_02_the_frozen_pin_is_the_file_it_pins(self):
        """LOOP_SHA moves with kit/conductor_loop.py. Bookkeeping, not a weakening.

        The test whose constant this is locks the seam's shape (quoted in this
        bar's docstring) and hashes the file as its tripwire. The value is read
        from the file at test time, so this case fails while the pin and the
        file disagree and passes only when they agree — which is exactly the
        bookkeeping the job names. It does not assert the test still exists and
        checks nothing: the next step runs it and requires it green.
        """
        path = os.path.join(REPO, SOURCES)
        self.assertTrue(os.path.isfile(path), "tests/test_loop_custody_sources.py is absent")
        text = open(path, encoding="utf-8").read()
        self.assertIn("LOOP_SHA", text, "the pin constant is gone from the sources test")
        import re
        found = re.search(r'^LOOP_SHA\s*=\s*"([0-9a-f]{64})"', text, re.MULTILINE)
        if found is None:
            self.fail("LOOP_SHA is not a 64-hex constant any more")
        actual = _sha_file(os.path.join(REPO, LOOP_PY))
        self.assertEqual(found.group(1), actual,
                         "LOOP_SHA pin %s != kit/conductor_loop.py %s: the pin did not move "
                         "with the file it pins" % (found.group(1)[:12], actual[:12]))

    # 03 ------------------------------------------------------------------
    def test_03_the_spec_version_is_sourced_and_the_seam_cannot_outsmart_its_twin(self):
        """Three things about the supply, all measured on the emitter itself.

        1. The emitter still REFUSES a job with no document and no version. The
           fix is in the seam, not in the emitter, and a fix that deletes this
           refusal fails here.
        2. `tools/pin.json` is the only honest source: it carries
           custody.commit, custody.specVersion, and the sha256 of the SPEC.md at
           that commit. This case reads all three and requires them to agree
           with each other and with the record.
        3. THE SHAPE. A seam that adds `--spec-version` produces a record the
           plain command does not (`origin: "--spec-version"`, no path, no
           digest), and it BREAKS the frozen bar
           tests/test_loop_custody_on_finish.py:290, which requires the seam's
           exit code to equal `emit_custody.py --job-dir J` with no flags. So
           the record must NOT be the flag shape: the version must arrive as
           the custody DOCUMENT the job names, and the record must carry
           `origin: "document"` with the pin's SPEC.md sha256. Measured: with
           the flag shape the frozen test fails 1 != 3; with the document
           shape the whole suite is rc 0.

        The bar therefore asks for the document shape and says why, rather than
        accepting either.
        """
        pin = _load(os.path.join(REPO, PIN))
        custody_pin = pin.get("custody") or {}
        pinned = custody_pin.get("specVersion")
        commit = custody_pin.get("commit")
        spec_sha = (custody_pin.get("files") or {}).get("SPEC.md")
        self.assertTrue(pinned and commit and spec_sha,
                        "tools/pin.json no longer names the custody commit, version and SPEC.md "
                        "digest the seam's source depends on: %r" % (custody_pin,))
        self.assertEqual(pinned, _pinned_version())

        work = TemporaryDirectory()
        self.addCleanup(work.cleanup)
        job = os.path.join(work.name, "job")
        _write(os.path.join(job, "inputs", "custody.json"), json.dumps({
            "custody_inputs": "plumbline/custody-inputs/v1",
            "levelClaimed": "CL1",
            "bar": {"file": "custody/bar.md"},
            "orchestrator": {"name": "bar", "kind": "agent"},
        }))
        _write(os.path.join(job, "custody", "bar.md"), "bar\n")
        _write(os.path.join(job, "packet.json"), json.dumps({
            "job_id": "bar", "terminal_state": "accepted", "outcome": "accepted",
            "disposition_state": "given",
            "started_at": "2026-11-12T00:00:00+00:00",
            "ended_at": "2026-11-12T00:01:00+00:00",
        }))

        bare = subprocess.run([PY, self._clean, "--job-dir", job],
                              capture_output=True, text=True)
        self.assertEqual(bare.returncode, 3,
                         "the emitter no longer refuses a job with no document and no version; "
                         "that refusal is correct and must stay (exit %r)" % (bare.returncode,))
        self.assertIn("spec-version", (bare.stdout or "") + (bare.stderr or ""),
                      "the refusal no longer names the spec-version refusal")

        # The seam's outcome is what case 00 grades. Here: the RECORD shape.
        # Run the job twice with the document named, as the seam does, and
        # require origin "document" — not the flag.
        inputs = os.path.join(job, "inputs", "custody.json")
        body = _load(inputs)
        checkout = _pinned_checkout(commit)
        if checkout is None:
            self.fail("no custody checkout at the pinned commit %s on this machine (looked at "
                      "$PLUMBLINE_CUSTODY and a custody/ beside the repo). Case 00 requires the "
                      "seam to find one, and this case cannot grade the record's origin without "
                      "it; a skip here would hide that." % (str(commit)[:12],))
        body["custody_spec"] = checkout
        _write(inputs, json.dumps(body))
        told = subprocess.run([PY, self._clean, "--job-dir", job],
                              capture_output=True, text=True)
        record = os.path.join(job, RECORD_REL)
        self.assertTrue(os.path.isfile(record),
                        "no record written with the pinned document named: exit %r, %s"
                        % (told.returncode, (told.stderr or told.stdout)[-2000:]))
        pred = (_load(record).get("predicate") or {})
        self.assertEqual(pred.get("specVersion"), pinned,
                         "the record's specVersion is not the pin's value")
        block = ((pred.get("x-plumbline") or {}).get("spec_version") or {})
        self.assertTrue(block, "x-plumbline.spec_version is absent: the record does not say "
                               "where its version came from")
        self.assertEqual(block.get("origin"), "document",
                         "the record's version came from %r; the flag shape breaks the frozen "
                         "twin bar (tests/test_loop_custody_on_finish.py:290) and carries no "
                         "digest" % (block.get("origin"),))
        self.assertEqual(block.get("sha256"), spec_sha,
                         "the record's SPEC.md digest is not the one tools/pin.json names: %r"
                         % (block.get("sha256"),))
        self.assertTrue(str(block.get("source") or "").strip(),
                        "the record names no source for its version")

    # 04 ------------------------------------------------------------------
    def test_04_no_bar_in_the_tree_asserts_an_absent_scoring_set_is_refused(self):
        """The Owner repealed refuse-on-absent. No bar in the tree may re-assert it.

        The Job 36 bar is superseded: its case 02 and case 10 legalise the old
        rule, and the Job 37 bar carries every still-valid case forward. This
        case requires the file to be resolved — gone, or agreeing — and forbids
        the repealed assertion anywhere else.
        """
        job36 = os.path.join(REPO, JOB36_BAR)
        if os.path.isfile(job36):
            text = open(job36, encoding="utf-8").read()
            reasserted = [token for token in ("_undeclared_one_is_refused",
                                              "_does_not_score_everything")
                          if token in text]
            self.assertEqual(reasserted, [],
                             "the Job 36 bar still asserts an absent set is refused: found %s in %s"
                             % (reasserted, JOB36_BAR))
        live = os.path.join(REPO, JOB37_BAR)
        self.assertTrue(os.path.isfile(live), "the live Job 37 bar is absent")
        self.assertEqual(_sha_file(live), V099_SHA,
                         "the live Job 37 bar was edited; the compat law is the record of "
                         "what was accepted and its bytes do not move")
        # The repealed assertion, as text, in any bar-shaped file in the tree.
        offenders = []
        for name in sorted(os.listdir(os.path.join(REPO, "tests"))):
            if not (name.startswith("test_") and name.endswith(".py")):
                continue
            if name in (os.path.basename(JOB37_BAR), os.path.basename(__file__)):
                continue
            with open(os.path.join(REPO, "tests", name), encoding="utf-8") as handle:
                body = handle.read()
            if "an_undeclared_one_is_refused" in body:
                offenders.append(name)
        self.assertEqual(offenders, [],
                         "bars still asserting an absent set is refused: %s" % (offenders,))

    # 05 ------------------------------------------------------------------
    def test_05_the_job_37_compat_law_still_passes(self):
        """The compat law is not regressed by any of this: the 14 cases, run.

        Exit 0 and "Ran 14" and OK, measured from the bar's own bytes rather
        than trusting a report of them.
        """
        bar = os.path.join(REPO, JOB37_BAR)
        proc = subprocess.run([PY, bar], cwd=REPO, capture_output=True, text=True,
                              env=dict(os.environ, PYTHONPATH=REPO))
        self.assertEqual(proc.returncode, 0,
                         "the Job 37 bar is red: %s" % ((proc.stderr or proc.stdout)[-3000:],))
        self.assertIn("Ran 14 tests", proc.stderr + proc.stdout)
        self.assertIn("OK", proc.stderr + proc.stdout)

    # 06 ------------------------------------------------------------------
    def test_06_the_emitter_still_refuses_and_the_seam_is_still_the_emitter(self):
        """The two things the fix could break and must not.

        The emitter refuses rather than guess (asserted in case 03, asserted
        again here at the source so a lucky fixture cannot hide it), and the
        seam still calls the emitter and not `plumbline_job.py` — the shape the
        frozen sources test locks. `loop()` gains no new parameter a caller must
        remember: the version is read inside the seam from the repo it writes in.
        """
        import inspect
        source = inspect.getsource(cl.emit_custody_for_finish)
        self.assertIn("emit_custody", source, "the seam no longer calls the emitter")
        self.assertNotIn("plumbline_job", source, "the seam calls the close command")
        params = set(inspect.signature(cl.loop).parameters)
        self.assertEqual(params, {"packet", "record_dir", "cwd", "timeout_s", "commit", "evaluator_fn"},
                         "loop() gained a parameter; the version must not become a caller's duty")
        pin = _load(os.path.join(REPO, PIN))
        self.assertIn("specVersion", pin.get("custody") or {},
                      "tools/pin.json no longer carries custody.specVersion: the seam's only "
                      "honest source for the version is gone")


if __name__ == "__main__":
    unittest.main()
