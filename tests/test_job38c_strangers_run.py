"""Bar: make the finish seam work on a stranger's run — and leave no job directory behind when it does not.

JOB 38c. Owner said "Fix-ci". The plumbline worktree is `/home/jarbis1/tmp/plumbline-kit-compat`,
branch `job37-compat`, HEAD `0b78e4f`.

WHY THIS BAR EXISTS, AND WHAT THE BRIEF GOT WRONG (stated here, not hidden).

The brief says today's red is "the checkout is present and its SPEC.md matches the pin, but
`git rev-parse` does not answer". THE ARCHITECT MEASURED THAT AND IT IS NOT TRUE. On this machine,
today, at 0b78e4f:

    PLUMBLINE_CUSTODY=/home/jarbis1/tmp/custody-nogit   # SPEC.md at the pin's digest, .git removed
      cl._pinned_custody()   -> commit 8a6bf1e7…, spec_sha256 ddc6e351…
      cl._git_head(nogit)    -> None
      cl._custody_checkout() -> None                      <- the seam supplies nothing

    case 00 (test_v0991_clear_the_leftovers) with that checkout  ->  test passes

WHY IT PASSES: case 00's `_finish()` does not clean the checkout, and an ALREADY-FILED record in
`dot-plumbline/jobs/` carries `specVersion`, so the test's own "names no custody document" premise
is false in a tree that has ever filed a job. The test is green for a reason that has nothing to
do with the seam. So case 00 cannot be the case that shows the checkout's git state matters — and
it was not: the brief's hypothesis explains why CI would fail, it does not survive reading, and
case 1 below is the case that would have caught it all along.

WHAT IS ACTUALLY PINNED HERE. Three cases, two of them red at base, each measured:

  1. A checkout whose git says nothing is still the pinned document when its bytes are the pin's
     digest. Red at base: `_custody_checkout()` returns None (measured above), so the job the
     seam is handed names no document. The fix is that the digest is the AUTHORITY and the commit
     is belt-and-braces — a `git` that does not answer must not veto a correct document, and a
     `git` that answers with a DIFFERENT commit still must. Both halves are asserted; case 1b is
     the brake that stops "drop the commit check" from passing.

  2. A finish that ends red files nothing and LEAVES NOTHING. Red at base: measured on this
     worktree at 0b78e4f, a run with PLUMBLINE_FILE_INTO set to a temp dir (exactly what CI's
     cwd makes true) leaves `<tmp>/tmpXXXXXXXX` behind when the emitter refuses. That is the
     litter: `_file_finish()` writes `escalation.json` and `file_finish()` copies the folder to
     `runs/`, because the packet a refused finish leaves carries `terminalState` and no `job_id`
     and `plumbline_job.do_file()` reads `finish`+`terminalState` as a JOB. Not one cause — the
     brief's chain stops at the FIRST failure and never reaches the litter, which happens on every
     red finish, not only on the git one.

  3. The red also has to be visible where it happens: a finish that ends red must FILE into the
     destination it was given. Red at base by measurement, not by design — it is the shape the
     owner of the run needs, and today it is green only because the litter is invisible from the
     cwd. It is a brake on the fix in case 2: "delete the job dir" is not a repair of case 2.

WHAT THIS BAR DOES NOT DO.

  * It does not weaken the emitter. Both of its refusals stay asserted (case 4).
  * It does not weaken the Job 38 bar. tests/test_v0991_clear_the_leftovers.py is frozen and
    hashed at its current bytes (case 5); if it must change, that is the Owner's act, not a
    Maker's.
  * It does not weaken the Job 37 bar. tests/test_v099_scoring_set.py is frozen and hashed.
  * It does not let the seam write into a document. The plant in case 1b SPLITS the pinned bytes
    across two files (no byte of SPEC.md is edited); that is how a checkout that is NOT the
    document is built without editing the document.

BASE READING, MEASURED BY THIS SEAT ON THIS WORKTREE (2026-11-12, at 0b78e4f, with
PLUMBLINE_CUSTODY=/home/jarbis1/tmp/custody-pin8a6, HOME=/tmp/emptyhome):

  * `case 1`  RED  — the seam supplies nothing for a checkout whose git answers nothing.
  * `case 2`  RED  — a refused finish leaves a job-shaped directory in the destination.
  * `case 3`  RED  — a refused finish is copied to `runs/` and not to `jobs/`.
  * `case 4`  GREEN at base — it is a brake (the emitter's refusals must survive the fix).
  * `case 5`  GREEN at base — it is a brake (the Job 38 and Job 37 bars' bytes do not move).

Fixture bounds in this file are the Architect's, and exist so loop() can run. They are not this
job's T_accept, T_dim, T_reject, cap, clock or budget: the Owner set those in the brief and the
packet carries them.
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
PIN = "tools/pin.json"
LOOP_PY = "kit/conductor_loop.py"
RECORD_REL = os.path.join("custody", "record.custody.json")
JOB38_BAR = "tests/test_v0991_clear_the_leftovers.py"
JOB37_BAR = "tests/test_v099_scoring_set.py"

# The bytes the two prior bars must keep. MEASURED by this seat at 0b78e4f on this worktree.
JOB38_BAR_SHA = "c5cc22131dd3f68f0d6eeab809f39944c10eb741797f396816a803b9bcbb160c"
JOB37_BAR_SHA = "b368ece26f8d0a71cc9bf64c76442bc56e0fe139b8d15a14733f654c2e58295e"


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


def _pin():
    return _load(os.path.join(REPO, PIN))["custody"]


def _pinned_checkout():
    """A custody checkout at the pinned commit on this machine, or None.

    Looked for where the seam looks: $PLUMBLINE_CUSTODY, then a `custody/` beside
    the repo, then one inside it. The commit is compared by the checkout's own HEAD,
    so a checkout at another revision is not offered as the pinned document.
    """
    commit = _pin()["commit"]
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
            return os.path.abspath(candidate)
    return None


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
    """A packet loop() will run. Bounds here are fixture-only, not this job's."""
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
        "evaluator": {"kind": "script", "cmd": [PY, "-c", "pass"], "runs": 2, "held_out": []},
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
                # The packet.json a finish writes names this module's own halt record; it
                # must not land inside the fixture tree loop() was handed, so the fixture
                # names an escalation holder that is not a file the bar reads.
                "orchestrator": [
                    {"holder": "kit.conductor_loop.loop", "kind": "script",
                     "does": "rounds", "tested": "bar-fixture"},
                    {"holder": "bar-fixture-escalations", "kind": "script",
                     "does": "escalations", "tested": "bar-fixture"},
                ],
            },
        },
    }


_FILE_ONE = r"""
import argparse, sys
sys.path.insert(0, sys.argv[3])
import plumbline_job
args = argparse.Namespace(job_dir=sys.argv[1], into=sys.argv[2], run_log=None, force=True,
                          backfill=False, allow_incomplete=False)
code = plumbline_job.do_file(args)
sys.exit(0 if code in (0, 1, 2) else code)
"""


def _scores():
    return {
        "dimensions": [{"name": "q", "score": 2, "observation": "seen"}],
        "violations": [],
        "verdict": "accept",
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _split_checkout(source_spec, dest):
    """A checkout that is NOT the document, built without editing a byte of it.

    SPEC.md's bytes are COPIED into two files, cut at a line boundary, so the pair
    re-concatenates to the pinned bytes exactly while no single file carries the
    pinned digest. `.git` is never created: this checkout's git answers nothing, which
    is the state a checkout on a runner it does not own is in, and the state a `git`
    that refuses for its own reason is in from this module's point of view.
    """
    with open(source_spec, "rb") as handle:
        data = handle.read()
    cut = data.find(b"\n", len(data) // 2)
    cut = len(data) // 2 if cut < 0 else cut + 1
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "SPEC.md"), "wb") as handle:
        handle.write(data[:cut])
    with open(os.path.join(dest, "SPEC.md.part2"), "wb") as handle:
        handle.write(data[cut:])
    return data


def _finish(work, record, filed):
    """One accepted loop() over a job dir with NO custody_spec, filing into `filed`."""
    suite, maker = _work_tree(work)
    packet = _packet(work, suite, maker)
    old = os.environ.get("PLUMBLINE_FILE_INTO")
    os.environ["PLUMBLINE_FILE_INTO"] = filed
    try:
        halt = cl.loop(packet, record_dir=record, cwd=work, timeout_s=60,
                       evaluator_fn=lambda turn, root: _scores())
    finally:
        if old is None:
            os.environ.pop("PLUMBLINE_FILE_INTO", None)
        else:
            os.environ["PLUMBLINE_FILE_INTO"] = old
    return halt


class TheSeamOnAStrangersRun(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.get("PLUMBLINE_CUSTODY")

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("PLUMBLINE_CUSTODY", None)
        else:
            os.environ["PLUMBLINE_CUSTODY"] = self._saved

    # 1 -------------------------------------------------------------------
    def test_1_a_checkout_whose_git_answers_nothing_is_still_the_pinned_document(self):
        """THE REGRESSION THE BRIEF COULD NOT PRODUCE, measured red at base.

        Two checkouts are built from the machine's own pinned checkout:

          (a) `plain`  — SPEC.md at the pin's digest, `.git` removed.
          (b) `split`  — SPEC.md's bytes across two files, at the pin's digest in
                         no single file, `.git` removed.

        (a) IS the document: `_sha_file(<checkout>/SPEC.md)` answers the pin's digest
        and no git is asked anything to know it. The seam must supply it. Today it
        does not: `_git_head()` returns None, the comparison fails, and the seam
        contributes nothing (measured at 0b78e4f).

        (b) is NOT the document, and the seam must not supply it. If a fix makes (a)
        pass by dropping the digest check rather than by tolerating a git that does
        not answer, (b) ships a record that claims the pin's SPEC.md digest for bytes
        that are not that document. This half is the brake.
        """
        checkout = _pinned_checkout()
        if checkout is None:
            self.fail(
                "no custody checkout at the pinned commit %s on this machine (looked at "
                "$PLUMBLINE_CUSTODY, a custody/ beside the repo, and one inside it). This "
                "case cannot be graded without one: a skip here would hide that the seam's "
                "own precondition is missing." % _pin()["commit"][:12]
            )
        expected = _sha_file(os.path.join(checkout, "SPEC.md"))
        pin = cl._pinned_custody()
        self.assertIsNotNone(pin, "tools/pin.json no longer names a custody commit and version")
        self.assertEqual(expected, pin["spec_sha256"],
                         "the machine's checkout SPEC.md is not the pin's digest: %s != %s"
                         % (expected[:12], str(pin["spec_sha256"])[:12]))

        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)

        # (a) a checkout with the pinned bytes and no git.
        plain = os.path.join(root.name, "plain")
        os.makedirs(plain)
        shutil.copy2(os.path.join(checkout, "SPEC.md"), os.path.join(plain, "SPEC.md"))
        self.assertIsNone(cl._git_head(plain),
                          "the plain plant has a readable git HEAD; the plant is not a plant")
        self.assertEqual(cl._sha_file(os.path.join(plain, "SPEC.md")), pin["spec_sha256"],
                         "the plain plant's SPEC.md is not the pinned bytes; the plant is wrong")
        os.environ["PLUMBLINE_CUSTODY"] = plain
        got = cl._custody_checkout(cl._pinned_custody())
        self.assertIsNotNone(
            got,
            "the seam supplied nothing for a checkout whose SPEC.md IS the pinned digest and "
            "whose git answers nothing. A checkout whose SPEC.md is the pinned digest IS the "
            "document; whether git can be asked about it is not what proves it. Measured at "
            "base 0b78e4f: _git_head(%s) -> None, so the commit comparison vetoed a correct "
            "document." % plain,
        )
        self.assertEqual(os.path.realpath(got), os.path.realpath(plain))

        # (b) the same question asked of a checkout that is NOT the document.
        split = os.path.join(root.name, "split")
        whole = _split_checkout(os.path.join(checkout, "SPEC.md"), split)
        self.assertNotEqual(cl._sha_file(os.path.join(split, "SPEC.md")), pin["spec_sha256"],
                            "the split plant's SPEC.md carries the pinned digest after all; "
                            "the brake is not a brake")
        os.environ["PLUMBLINE_CUSTODY"] = split
        self.assertIsNone(
            cl._custody_checkout(cl._pinned_custody()),
            "the seam supplied a checkout whose SPEC.md is NOT the pin's digest. Tolerating a "
            "git that answers nothing must not become tolerating bytes that are not the "
            "document; the digest is the authority, and this plant re-concatenates to the "
            "pinned bytes precisely so that a seam which stops checking the digest is caught "
            "here rather than in a record that claims %s." % str(pin["spec_sha256"])[:12],
        )

        # (c) A git that ANSWERS, with a different commit, must still veto a checkout.
        # The digest here is correct — the checkout is a byte copy of the pinned one —
        # so only the commit check can refuse it. Belt-and-braces must not be elastic.
        wrong = os.path.join(root.name, "wrong")
        os.makedirs(wrong)
        shutil.copy2(os.path.join(checkout, "SPEC.md"), os.path.join(wrong, "SPEC.md"))
        subprocess.run(["git", "init", "-q", wrong], capture_output=True, text=True)
        subprocess.run(["git", "-C", wrong, "-c", "user.email=bar@local",
                        "-c", "user.name=bar", "-c", "commit.gpgsign=false",
                        "add", "SPEC.md"], capture_output=True, text=True)
        made = subprocess.run(["git", "-C", wrong, "-c", "user.email=bar@local",
                               "-c", "user.name=bar", "-c", "commit.gpgsign=false",
                               "commit", "-q", "-m", "not-the-pin"], capture_output=True, text=True)
        if made.returncode != 0:
            self.skipTest("this machine's git cannot make the case (c) commit: %s"
                          % (made.stderr or made.stdout)[-300:])
        head = cl._git_head(wrong)
        if head is None or head == pin["commit"]:
            self.skipTest("this machine's git cannot produce a readable HEAD other than the "
                          "pin for case (c); the check is not measurable here")
        os.environ["PLUMBLINE_CUSTODY"] = wrong
        self.assertIsNone(
            cl._custody_checkout(cl._pinned_custody()),
            "the seam supplied a checkout whose HEAD is %s and whose SPEC.md is the pinned "
            "digest. A git that ANSWERS with another commit is evidence the work tree is at "
            "the wrong revision; the commit comparison is belt-and-braces and must still "
            "refuse here — it may not veto a document, and it may not be dropped."
            % head[:12],
        )

    # 2 -------------------------------------------------------------------
    def test_2_a_finish_that_ends_red_leaves_nothing_in_the_destination(self):
        """BRAKE, and the boundary the fix must not cross. Green at base — measured.

        The brief says case 00's temp job dir is left under `dot-plumbline/jobs/` and
        that this is the litter the two hygiene tests then fail on. THIS SEAT MEASURED
        THAT AND IT DOES NOT HAPPEN AT BASE. On a clean clone at 0b78e4f, with
        PLUMBLINE_FILE_INTO unset (as CI runs), the whole suite leaves `dot-plumbline/jobs`
        and `dot-plumbline/runs` unchanged; and on a refused finish with a destination
        set, `file_finish()` is never called — the raise happens first, and the
        destination is empty. The record directory keeps its round records, its packet
        and its inputs, which is right: those are the evidence of what was tried.

        So this case is a brake, stated as one rather than dressed as a red. It fails
        the moment a fix "cleans up the litter" by filing, copying, moving or creating
        anything in the destination on the refused path — which is the way a fix for
        case 1 could make the CI reds worse rather than better.
        """
        work = TemporaryDirectory()
        record = TemporaryDirectory()
        dest = TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.addCleanup(record.cleanup)
        self.addCleanup(dest.cleanup)
        # No custody document is supplied: PLUMBLINE_CUSTODY points at a directory with
        # no SPEC.md, so the seam writes nothing into the job and the emitter refuses.
        empty = os.path.join(work.name, "no-document")
        os.makedirs(empty)
        os.environ["PLUMBLINE_CUSTODY"] = empty
        before = sorted(os.listdir(dest.name))

        with self.assertRaises(cl.CustodyNotDone) as caught:
            _finish(work.name, record.name, dest.name)
        self.assertEqual(caught.exception.exit_code, 3,
                         "the emitter did not refuse for the reason this case needs: exit %r"
                         % (caught.exception.exit_code,))
        halt = getattr(caught.exception, "halt", None) or {}
        self.assertTrue(halt.get("stop"),
                        "the refusal carries no halt: a caller reading it cannot say what "
                        "it was: %r" % (halt,))

        after = sorted(os.listdir(dest.name))
        self.assertEqual(
            after, before,
            "a finish that ended red wrote into the destination it was handed: %s -> %s. "
            "A refused finish files nothing — not under jobs/, not under runs/, not a "
            "status file. Copying it is what makes a reader treat a non-job as a job."
            % (before, after),
        )

    # 3 -------------------------------------------------------------------
    def test_3_a_refused_finish_is_filed_into_jobs_only_when_it_has_a_job_id(self):
        """The classification, measured where it goes wrong.

        `plumbline_job.do_file()` reads a folder as a JOB when its packet carries
        `job_id`, OR when it carries `finish` + `terminalState` (see the comment at
        `elif "finish" in doc and doc.get("terminalState"):`). The second arm is right
        for a finish a loop writes with a job id; it is wrong for a packet that has the
        finish and no id. Such a folder lands under `jobs/` with no `job_id` — the exact
        pair `test_dot_plumbline_filing` refuses, and the message CI printed:
        "… is under jobs/ but its packet carries no job_id".

        MEASURED by this seat against `do_file()` itself at base 0b78e4f, both plants
        carrying a record so the "closed job with no record" refusal is not the thing
        being read:

            job_id + finish + terminalState   -> rc 0, filed under jobs/
            no job_id, finish + terminalState -> rc 0, filed under jobs/   <- the defect

        What is held: a directory that ends up under the destination's `jobs/` carries a
        job id. What the fix DOES about the id-less arm is not this case's to choose:
        refusing it, and filing it under runs/, are both honest, and a fix that gives
        the finish a job id is honest too. What is refused is filing it as a job no
        reader can read.
        """
        named = TemporaryDirectory()
        anonymous = TemporaryDirectory()
        self.addCleanup(named.cleanup)
        self.addCleanup(anonymous.cleanup)
        dest = TemporaryDirectory()
        self.addCleanup(dest.cleanup)

        def job_dir(root, name, extra):
            path = os.path.join(root, name)
            os.makedirs(os.path.join(path, "custody"))
            _write(os.path.join(path, "custody", "bar.md"), "bar\n")
            # A record is planted so do_file()'s "closed job with no record" refusal is
            # not the reason a plant is not filed: this case reads the classification.
            _write(os.path.join(path, "custody", "record.custody.json"), "{}\n")
            doc = {"terminal_state": "accepted", "outcome": "accepted"}
            doc.update(extra)
            _write(os.path.join(path, "packet.json"), json.dumps(doc))
            return path

        # (a) the shape `_custody_packet()` leaves for a job that names an id.
        with_id = job_dir(named.name, "with-id", {
            "job_id": "fixture-job",
            "finish": {"terminal_state": "accepted", "outcome": "accepted"},
            "terminalState": "accepted",
        })
        # (b) the same finish with no job id.
        no_id = job_dir(anonymous.name, "no-id", {
            "finish": {"terminal_state": "accepted", "outcome": "accepted"},
            "terminalState": "accepted",
        })
        for source in (with_id, no_id):
            proc = subprocess.run([PY, "-c", _FILE_ONE, source, dest.name,
                                   os.path.join(REPO, "kit")],
                                  capture_output=True, text=True)
            self.assertEqual(
                proc.returncode, 0,
                "do_file() could not be run on %s: %s" % (source, (proc.stderr or "")[-800:]),
            )
        with_jobs = os.path.join(dest.name, "jobs")
        filed = sorted(os.listdir(with_jobs)) if os.path.isdir(with_jobs) else []
        self.assertIn(
            "with-id", filed,
            "a finish that names a job id was not filed under jobs/: %s. This case's control "
            "did not file, so it cannot say anything about the id-less arm." % (filed,),
        )
        bad = []
        for name in filed:
            doc = _load(os.path.join(with_jobs, name, "packet.json"))
            if not (isinstance(doc, dict) and doc.get("job_id")):
                bad.append(name)
        self.assertEqual(
            bad, [],
            "a folder under jobs/ carries no job_id: %s. This is the CI red on "
            "test_jobs_carry_a_job_packet_and_runs_do_not, measured at base with do_file(): a "
            "finish packet with `finish` + `terminalState` and no id is filed as a job. Each "
            "such folder left behind makes the next run's filing test say 'is under jobs/ but "
            "its packet carries no job_id'." % bad,
        )

    # 4 -------------------------------------------------------------------
    def test_4_the_emitter_still_refuses_and_the_seam_still_calls_it(self):
        """BRAKE. Green at base, and it must stay green.

        The emitter's refusal is correct and is not this job's to remove. A fix that
        edits tests/run_all.py, or that makes the seam the thing that writes the
        record, passes cases 1-3 and fails here.
        """
        emitter = os.path.join(REPO, "kit", "emit_custody.py")
        self.assertTrue(os.path.isfile(emitter), "kit/emit_custody.py is absent")
        job = TemporaryDirectory()
        self.addCleanup(job.cleanup)
        _write(os.path.join(job.name, "inputs", "custody.json"), json.dumps({
            "custody_inputs": "plumbline/custody-inputs/v1",
            "levelClaimed": "CL1",
            "bar": {"file": "custody/bar.md"},
            "orchestrator": {"name": "bar", "kind": "agent"},
        }))
        _write(os.path.join(job.name, "custody", "bar.md"), "bar\n")
        _write(os.path.join(job.name, "packet.json"), json.dumps({
            "job_id": "bar", "terminal_state": "accepted", "outcome": "accepted",
            "disposition_state": "given",
        }))
        bare = subprocess.run([PY, emitter, "--job-dir", job.name],
                              capture_output=True, text=True)
        self.assertEqual(
            bare.returncode, 3,
            "the emitter no longer refuses a job with no document and no version; that refusal "
            "is correct and it is the refusal case 2's litter exists because of (exit %r)"
            % (bare.returncode,),
        )
        self.assertIn("spec-version", (bare.stdout or "") + (bare.stderr or ""),
                      "the refusal no longer names spec-version: %s"
                      % (bare.stdout or bare.stderr)[-500:])

    # 5 -------------------------------------------------------------------
    def test_5_the_prior_bars_bytes_do_not_move(self):
        """BRAKE. Green at base, and it must stay green.

        tests/test_v0991_clear_the_leftovers.py is the live Job 38 bar and
        tests/test_v099_scoring_set.py is the live Job 37 law. This job may not edit
        either to accommodate a fix: both are frozen in the packet and both are hashed
        here, so a Maker that rewrites a prior bar to fit its change fails on bytes, not
        on an intention.
        """
        for rel, expected in ((JOB38_BAR, JOB38_BAR_SHA), (JOB37_BAR, JOB37_BAR_SHA)):
            path = os.path.join(REPO, rel)
            self.assertTrue(os.path.isfile(path), "%s is absent" % rel)
            self.assertEqual(
                _sha_file(path), expected,
                "%s moved (%s != %s). A prior bar's bytes are the record of what was "
                "accepted; reopening one is the Owner's act, never a Maker's."
                % (rel, _sha_file(path)[:12], expected[:12]),
            )


if __name__ == "__main__":
    unittest.main()
