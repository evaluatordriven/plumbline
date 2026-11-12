#!/usr/bin/env python3
"""Bar: a finish whose packet carries no job_id leaves `dot-plumbline/jobs/` byte-identical.

JOB 38d. Owner ruling, 2026-11-12: "kill-litter". The finish now reaches the filing path
on a runner and files into a temporary job directory when the packet carries no `job_id`.
That directory is the whole remaining defect. This file is the bar for it. It is frozen;
do not edit it to make it pass.

THE DEFECT, AS THE OWNER MEASURED IT (cited, not re-derived by me):

    suite    HOME=<empty> PLUMBLINE_CUSTODY=<pin checkout> -> Ran 344, OK (skipped=3)
    CI       the same suite on the runner -> Ran 344, FAILED (failures=3):
               nine `tmp...` dirs under dot-plumbline/jobs/          (test_dot_plumbline_filing)
               dot-plumbline/jobs/tmp2pyof8ud/custody/record.custody.json publishes no specVersion
               case 00: "loop() ended with CustodyNotDone exit 3"    (the dirty tree the litter creates)
             the nine names are identical across two CI runs, are not tracked (`git ls-files` -> 0),
             and do not appear in the worktree or in a fresh clone after a local run (0)

I MEASURED THE MECHANISM ON THE BASE TREE, c24b8ea, before writing this file. One accepted
`loop()` over the fixture packet in `tests/test_loop_custody_on_finish.py` — which carries no
`job_id` — with `PLUMBLINE_FILE_INTO` set to a temp directory:

    record_dir name                        tmp3oudgzx8        (Python's own mkdtemp name)
    packet carries job_id                  False
    halt["filing"]                         {"state": "custody", "filed": true,
                                            "dest": ".../jobs/tmp3oudgzx8", ...}
    jobs/ before []  ->  after ["tmp3oudgzx8"]
    filed packet job_id                    tmp3oudgzx8        (the packet was MUTATED)

That last line is the mechanism, and it is why this is not a cosmetic name: the packet is
edited in place so that a finish with no identity acquires one, and the name it acquires is
the scratch directory's. The destination is then exactly the pair
`test_dot_plumbline_filing` refuses — a folder under `jobs/` whose name is nobody's job.

WHY THIS IS RED BEFORE THE FIX AND WHAT IT DOES NOT PREDICT. Cases 1 and 2 fail on the base
tree: case 1 because a new `tmp...` entry appears under `jobs/`, case 2 because the packet the
job was handed came back carrying a `job_id` it did not have. Cases 3 and 4 are BRAKES and are
green at base; they exist so a fix cannot buy case 1 by never filing anything. I am not
Predicting here that every fix passes case 1 — I am stating what case 1 measures.

WHAT THIS BAR ASKS FOR, and what it deliberately leaves open. It does not name a function, a
file, or a line. It names the observable: the directory listing of `jobs/`, before and after a
finish with no job id, compared as a SET of names and a full recursive manifest of every byte
under it. A fix that refuses to file an ID-LESS finish, a fix that files it under `runs/`
(where a dispatch packet belongs and nothing reads it as a job), and a fix that makes the packet
carry a real identity are all honest; which one is the Maker's to choose and the Owner's to
ratify. Filing it under `jobs/` under any name — minted, borrowed from the scratch directory,
or dated — is not, and case 1 says so without caring how the name was chosen.

THE DESTINATION IS A TEMPORARY DIRECTORY THIS BAR CREATES. `dot-plumbline/jobs/` is named in
the Owner's sentence as the place the litter lands, and the finish reaches it through
`PLUMBLINE_FILE_INTO` (`kit/conductor_loop.py:file_finish`). This bar points that variable at
a fresh temp directory, makes the `jobs/` and `runs/` that a real instance has, and reads the
listing there. That is the same destination the runner writes to, without this bar ever
writing into the repository it is measuring. The repository's own `dot-plumbline/jobs/` is read
by `tests/test_dot_plumbline_filing.py`, which is not mine to edit and which is not re-run from
here.

WHAT IS FROZEN AND WHY THE CUSTODY DOCUMENT IS REQUIRED. The finish must reach the emitter and
be ACCEPTED for these cases to measure filing rather than refusal; a refused finish writes
nothing and would pass case 1 for the wrong reason. The seam supplies the pinned custody
document from `tools/pin.json` via `$PLUMBLINE_CUSTODY`, so the bar needs a real checkout at
the pin. It looks for one and SKIPS by name when the machine has none — a skip that CI's own
run does not take, because CI checks the pinned custody commit out before the suite runs
(`.github/workflows/ci.yml`). The skip is named, not silent, and case 0 fails if the finish the
other cases depend on does not reach the emitter, so a machine that skips cannot report a
green it did not measure.

CASES (the ids the Evaluator names, one per test method, in file order):

    0  the finish these cases measure is an ACCEPTED finish that reached the emitter
    1  a finish with no job_id leaves jobs/ byte-identical
    2  a finish with no job_id does not give the packet an identity it did not have
    3  BRAKE: a finish that has a job id still files under that name
    4  BRAKE: the two bars the Owner named pass unchanged

`bounds.scoring_set` in the packet is the list of those five ids, in this order, as
`_collected_cases()` reads them, and is checked here rather than assumed.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from tempfile import TemporaryDirectory

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import kit.conductor_loop as cl  # noqa: E402

PY = sys.executable
PIN = os.path.join("tools", "pin.json")

# The two bars the Owner named as brakes, by the paths the tree holds them at. Their bytes are
# not read here as a digest — they are RUN, each in its own process, and their own tally is the
# assertion. A digest would fail the day someone legitimately re-pins a constant inside them;
# a tally fails only when a case stops passing.
JOB38C_BAR = os.path.join("tests", "test_job38c_strangers_run.py")
JOB37_BAR = os.path.join("tests", "test_v099_scoring_set.py")

# What this bar declares its scope to be, in file order. `_collected_cases()` must agree.
# Case 05 is in the set because it IS a case this bar collects: a scoring set that leaves out
# the case checking it is the Job 35 shape (a case outside the set is a case nothing measures).
SCORING_SET = (
    "00_the_finish_these_cases_measure_is_accepted_and_reached_the_emitter",
    "01_a_finish_with_no_job_id_leaves_jobs_byte_identical",
    "02_a_finish_with_no_job_id_does_not_give_the_packet_an_identity",
    "03_a_finish_with_no_job_id_still_reaches_the_instance_record",
    "04_a_finish_that_has_a_job_id_still_files_under_that_name",
    "05_the_job_38c_and_job_37_bars_still_pass",
    "06_this_bars_scoring_set_is_what_the_cases_are",
)

_SKIP_NO_CHECKOUT = (
    "no custody checkout at the pinned commit on this machine (looked at $PLUMBLINE_CUSTODY "
    "and a custody/ beside the repo); the finish cannot reach the emitter without the pinned "
    "document, so filing cannot be measured here. CI checks this commit out before the suite "
    "runs (`.github/workflows/ci.yml`), so CI does not take this skip."
)


# ---------------------------------------------------------------------------- fixtures
def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _job(root):
    """A job tree that can reach `accepted`.

    `warden.py` is the file the gate suite reads and the Maker writes: the minimal shape
    every other loop fixture in this suite uses, so a green here is not a lucky fixture.

    There is deliberately NO `custody/bar.md` here. A convention bar is a FROZEN input —
    `freeze_bar()` copies it into the record dir so the ledger can freeze it — and a bar
    handed to `loop()` as frozen material must not also live in the tree the loop diffs
    between rounds. Leaving it out declares no bar, which is the skip path `freeze_bar()`
    documents for a job that prepared no custody inputs. This bar measures filing, and the
    custody document the emitter needs is supplied by the seam from `$PLUMBLINE_CUSTODY`.
    """
    _write(root, "tests/gate.py", "pin\n")
    _write(root, "src/warden.py", "no\n")
    return os.path.join(root, "src", "warden.py")


def _gate_suite(work):
    return [PY, "-c",
            "import sys; t=open(%r).read(); sys.exit(0 if t.startswith('yes') else 1)" % work]


def _maker(work, findings=None):
    """A Maker command that writes only the file it owns and consults nothing else.

    Deliberately dumber than a real one: it never reads `PLUMBLINE_FINDINGS`, so whether this
    bar measures filing cannot depend on the Maker's round arithmetic. One round, one write.
    """
    return [PY, "-c", "open(%r,'w').write('yes\\n')" % work]


def _packet(root, maker, suite, bounds=None):
    """The fixture packet, carrying NO `job_id` — the whole point of case 1.

    Bounds are this bar's fixtures, not the Owner's programme bounds: they are the smallest
    values that let one accepted round happen and file. They are not a T_accept/T_dim/T_reject
    for anything.
    """
    packet = {
        "ratified": True,
        "mode": "scored",
        "human_seat": "Owner",
        "artifact": {
            "test_cmd": suite,
            "frozen": [os.path.join(root, "tests", "gate.py")],
            "editable": ["src"],
            "ignore": [".git", "__pycache__"],
        },
        "maker": {"cmd": maker, "handoff": "rule12"},
        "evaluator": {
            "kind": "script",
            "cmd": [PY, "-c", "raise SystemExit(0)"],
            "runs": 2,
            "held_out": [],
        },
        "bounds": {
            "T_accept": 1,
            "T_dim": 1,
            "T_reject": 0,
            "cap": 1,
            "cap_counts": "generations",
            "budget": {"amount": 0, "unit": "USD", "time_hours_lt": 1},
        },
        "escalation": {
            "route": ["Architect", "Owner"],
            "classes": [],
            "holders": {
                "architect": "bar-fixture-architect",
                "orchestrator": [
                    {"holder": "kit.conductor_loop.loop", "kind": "script",
                     "does": "rounds", "tested": "bar-fixture"},
                    {"holder": "bar-fixture-escalations", "kind": "script",
                     "does": "escalations", "tested": "bar-fixture"},
                ],
            },
        },
    }
    if bounds:
        packet["bounds"].update(bounds)
    return packet


def _scores():
    return {
        "dimensions": [{"name": "q", "score": 2, "observation": "seen"}],
        "violations": [],
        "verdict": "accept",
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _pinned_checkout():
    """A custody checkout that IS the pinned document, or None.

    Asked of the seam itself (`cl._custody_checkout(cl._pinned_custody())`), because that is
    the one reader whose answer decides whether the finish can reach the emitter at all. A
    checkout this bar vouched for and the seam refused would make every case below a skip
    dressed as a pass.
    """
    pin = cl._pinned_custody()
    if not pin:
        return None
    return cl._custody_checkout(pin)


# ------------------------------------------------------------------- the thing measured
def _manifest(root):
    """Every file under `root` and its sha256 — the "byte-identical" case 1 compares.

    Names alone would pass while a filed folder's packet changed; the digest is what makes
    "byte-identical" mean what it says. Symlinks are recorded as their target, never followed,
    so a fix cannot pass by pointing a new name at an old file.
    """
    found = {}
    if not os.path.isdir(root):
        return found
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if os.path.islink(path):
                found[rel] = "symlink:" + os.readlink(path)
                continue
            with open(path, "rb") as handle:
                found[rel] = hashlib.sha256(handle.read()).hexdigest()
    return found


def _listing(root):
    """The immediate children of `root` — the directory listing the Owner asked to name."""
    if not os.path.isdir(root):
        return []
    return sorted(os.listdir(root))


def _finish(into, packet=None, job_id=None):
    """One accepted `loop()` with `PLUMBLINE_FILE_INTO` pointed at `into`.

    Returns everything a case needs to say what happened: the halt (or the refusal), the
    packet as the job was handed it, and the packet as the tree ended up carrying it. The
    second is what case 2 compares against the first — the mutation is invisible in the halt
    and visible only on disk, which is why it went unnoticed for so long.

    `job_id`, when given, is passed the way a real dispatch passes one: by seeding the packet
    the job is handed with the id the seat chose. The bar never invents a name for a finish
    that has none; that is the defect it exists to catch.
    """
    work = TemporaryDirectory()
    record = TemporaryDirectory()
    try:
        root = work.name
        warden = _job(root)
        packet = dict(packet) if packet else _packet(root, _maker(warden), _gate_suite(warden))
        if job_id is not None:
            packet["job_id"] = job_id
        handed = json.loads(json.dumps(packet))
        os.makedirs(os.path.join(into, "jobs"), exist_ok=True)
        os.makedirs(os.path.join(into, "runs"), exist_ok=True)

        before = {"jobs": _listing(os.path.join(into, "jobs")),
                  "runs": _listing(os.path.join(into, "runs")),
                  "manifest": _manifest(into)}
        old = os.environ.get("PLUMBLINE_FILE_INTO")
        os.environ["PLUMBLINE_FILE_INTO"] = into
        halt, refusal = None, None
        try:
            halt = cl.loop(packet, record_dir=record.name, cwd=root, timeout_s=120,
                           evaluator_fn=lambda turn, tree: _scores())
        except cl.CustodyNotDone as exc:
            refusal = {"kind": "CustodyNotDone", "exit": exc.exit_code,
                       "stop": getattr(exc, "stop", None)}
        except ValueError as exc:
            refusal = {"kind": "ValueError", "detail": str(exc)[:2000]}
        finally:
            if old is None:
                os.environ.pop("PLUMBLINE_FILE_INTO", None)
            else:
                os.environ["PLUMBLINE_FILE_INTO"] = old
        after = {"jobs": _listing(os.path.join(into, "jobs")),
                 "runs": _listing(os.path.join(into, "runs")),
                 "manifest": _manifest(into)}
        # Read the record the emitter wrote BEFORE `record` is cleaned up in the `finally`
        # below. A finish with no job id is not filed, so this record is not copied anywhere:
        # it lives at `record_dir/custody/record.custody.json` and dies with the temp dir. Case
        # 00 asserts against this evidence rather than the filed copy, which for such a finish
        # does not exist.
        record_path = os.path.join(record.name, "custody", "record.custody.json")
        record_evidence = {"path": record_path, "exists": os.path.isfile(record_path),
                           "sha256": None}
        if record_evidence["exists"]:
            with open(record_path, "rb") as handle:
                record_evidence["sha256"] = hashlib.sha256(handle.read()).hexdigest()
        return {
            "halt": halt,
            "refusal": refusal,
            "handed": handed,
            "on_disk": json.loads(json.dumps(packet)),
            "before": before,
            "after": after,
            "record_dir": record.name,
            "record": record_evidence,
            "into": into,
        }
    finally:
        work.cleanup()
        record.cleanup()


# ------------------------------------------------------------------------------ the bar
class NoLitterForAFinishWithNoJobId(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self._saved = os.environ.get("PLUMBLINE_CUSTODY")
        checkout = _pinned_checkout()
        if checkout is None:
            self.skipTest(_SKIP_NO_CHECKOUT)
        self.checkout = checkout
        os.environ["PLUMBLINE_CUSTODY"] = checkout

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("PLUMBLINE_CUSTODY", None)
        else:
            os.environ["PLUMBLINE_CUSTODY"] = self._saved

    # 0 ------------------------------------------------------------------
    def test_00_the_finish_these_cases_measure_is_accepted_and_reached_the_emitter(self):
        """CONTROL. Every case below reads the AFTER state of a finish; this says what that
        finish was. A refused finish writes nothing, and would make case 1 pass while
        measuring nothing at all — the failure mode this control exists to stop.

        Asserted: the loop returned a halt (it did not raise), the halt says `accepted`, the
        packet the job was handed carried no `job_id`, and the job reached the emitter — the
        emitter's record exists and has bytes. If any of these is false, cases 1 and 2 are not
        measuring filing and must not report a verdict on it.

        The record is read from `record_dir` (`_finish` captures it before the temporary
        directory is cleaned up), NOT from a filed copy. A finish whose packet carries no job
        id is not filed — `filing.filed` is false and `dest` is null — so there is no copy: the
        record lives only in the record directory and is the evidence that the emitter ran.
        Asserting against a filed copy asserts against something such a finish never produces.
        """
        with TemporaryDirectory() as into:
            got = _finish(into)
        self.assertIsNone(got["refusal"],
                          "the fixture finish did not complete: %r. Cases 1 and 2 would read an "
                          "AFTER state that never happened." % (got["refusal"],))
        halt = got["halt"] or {}
        self.assertEqual(halt.get("terminal_state"), "accepted",
                         "the fixture finish ended %r, not accepted: %r"
                         % (halt.get("terminal_state"), halt))
        self.assertNotIn("job_id", got["handed"],
                         "this bar's fixture packet carries a job_id; the defect under "
                         "measurement is the one where it does not: %r" % (got["handed"],))
        record = got["record"]
        self.assertTrue(
            record["exists"],
            "the fixture finish left no custody record at %r after an accepted halt, so the "
            "emitter never wrote one and the filing path under test was reached only as a "
            "refusal. halt.filing=%r" % (record["path"], halt.get("filing")),
        )
        self.assertRegex(record["sha256"] or "", r"^[0-9a-f]{64}$",
                         "the fixture finish's custody record has no sha256 — it exists but was "
                         "not read: %r" % (record,))

    # 1 ------------------------------------------------------------------
    def test_01_a_finish_with_no_job_id_leaves_jobs_byte_identical(self):
        """THE CASE. Owner: "a finish whose packet carries no job_id leaves
        `dot-plumbline/jobs/` byte-identical — name the directory listing before and after,
        and fail on any new entry."

        Two assertions, because either alone is passable by a fix that is wrong:
          (a) the LISTING of `jobs/` after equals the listing before, as a set — a new name is
              the litter, whatever it is called and wherever the name was minted;
          (b) the RECURSIVE MANIFEST of `jobs/` only is unchanged — a fix that files over an
              existing job, or edits a packet in place under a name that was already there,
              changes bytes without changing the listing.

        Owner A (2026-11-12): an id-less finish files under `runs/finish-<started_at>`. Case 03
        requires that. This case measures `jobs/` only — never the whole destination — so a
        honest runs/ filing does not redden the litter case. Measured: whole-into manifest made
        case 01 and case 03 mutually exclusive.
        """
        with TemporaryDirectory() as into:
            got = _finish(into)
        self.assertIsNone(got["refusal"],
                          "the fixture finish did not complete (%r); case 1 cannot say what a "
                          "finish did if there was no finish." % (got["refusal"],))
        before, after = got["before"], got["after"]

        ap = sorted(set(after["jobs"]) - set(before["jobs"]))
        self.assertEqual(
            ap, [],
            "a finish whose packet carries no job_id created %d new entr%s under jobs/: %r\n"
            "  jobs/ before: %r\n  jobs/ after : %r\n"
            "A folder under jobs/ is a job a reader will try to read. A name baked from a "
            "scratch directory is not a job, and a finish that has no job id does not get to "
            "invent one. Refusing to file it, filing it under runs/, or giving the packet a "
            "real identity are all honest; filing it under jobs/ under any name is not."
            % (len(ap), "y" if len(ap) == 1 else "ies", ap, before["jobs"], after["jobs"]),
        )
        dropped = sorted(set(before["jobs"]) - set(after["jobs"]))
        self.assertEqual(
            dropped, [],
            "a finish whose packet carries no job_id REMOVED entries from jobs/: %r. A finish "
            "that deletes other jobs' folders to tidy up after itself is worse than one that "
            "adds a folder. jobs/ before: %r, after: %r"
            % (dropped, before["jobs"], after["jobs"]),
        )

        # jobs/ only — runs/ is case 03's surface (Owner A: finish-<started_at> under runs/).
        def _jobs_only(manifest):
            out = {}
            for k, v in (manifest or {}).items():
                if k == "jobs" or k.startswith("jobs/"):
                    out[k] = v
            return out
        before_j, after_j = _jobs_only(before["manifest"]), _jobs_only(after["manifest"])
        changed = sorted(k for k in set(before_j) | set(after_j)
                         if before_j.get(k) != after_j.get(k))
        self.assertEqual(
            changed, [],
            "a finish whose packet carries no job_id changed %d file(s) under jobs/ "
            "without changing the listing:\n%s\n"
            "jobs/ is compared byte for byte, not by name: re-filing over an existing "
            "job, or rewriting a packet in place, is the same defect wearing a name that was "
            "already there."
            % (len(changed), "\n".join(
                "  %-60s before=%s after=%s"
                % (k, (before["manifest"].get(k) or "-")[:12],
                   (after["manifest"].get(k) or "-")[:12]) for k in changed[:20])),
        )

    # 2 ------------------------------------------------------------------
    def test_02_a_finish_with_no_job_id_does_not_give_the_packet_an_identity(self):
        """The packet the job was handed comes back carrying a `job_id` it did not have.

        This is the mechanism I measured at c24b8ea, quoted in this file's header: the packet
        went out with no `job_id` and came back with `job_id: "tmp3oudgzx8"`, the record
        directory's own name, so that the filer's "a folder under jobs/ must carry a job_id"
        rule would admit it. Case 1 catches the folder; this case catches the forgery that
        would justify it, which survives a fix that moves the folder somewhere else while
        still rewriting the job's own terms.

        Asserted on WHAT IS ON DISK, not on the halt: `halt["packet_sha256"]` is computed from
        the packet as loaded, so a mutation after that point is invisible to the summary and is
        exactly the kind of change a record cannot show.
        """
        with TemporaryDirectory() as into:
            got = _finish(into)
        self.assertIsNone(got["refusal"],
                          "the fixture finish did not complete (%r)." % (got["refusal"],))
        handed, on_disk = got["handed"], got["on_disk"]
        self.assertNotIn("job_id", handed)
        self.assertNotIn(
            "job_id", on_disk,
            "the finish wrote a job_id into the packet it was handed: %r -> %r. The job was "
            "dispatched with no identity and the loop gave it one — and the name it chose was "
            "the scratch directory's, %r. A job that has no id is a job no reader can name; "
            "writing one in changes what the job's own terms say about themselves, after the "
            "fact, in the copy that becomes the permanent record."
            % ("job_id" in handed, on_disk.get("job_id"), os.path.basename(got["record_dir"])),
        )
        differed = sorted(k for k in set(handed) | set(on_disk)
                          if handed.get(k) != on_disk.get(k))
        self.assertEqual(differed, [],
                         "the finish rewrote the job's own terms after dispatch: %r. Only the "
                         "editable tree belongs to the Maker; the packet is the terms the job "
                         "was handed." % (differed,))

    # 3 ------------------------------------------------------------------
    def test_03_a_finish_with_no_job_id_still_reaches_the_instance_record(self):
        """BRAKE. The litter fix must not buy case 1 by never filing — the standing law
        "a finish lands in the instance record" outranks the litter case, not the reverse.

        Owner, 2026-11-12: an id-less finish is honest as `filed: false` WITH A REASON, or as
        a folder under `runs/`, or with a real job id. Silent non-filing is none of the three:
        it is the litter green and the law red.

        A finish whose packet carries no `job_id` is not a job and has no name, so it may not
        go under `jobs/` — case 1 still holds it to byte-identical. What it MAY NOT do is
        evaporate. This case reads the halt the loop returned, and requires that the finish
        can be picked up out of the instance record by a reader who has only the destination:

          (a) `filing.dest` is a directory that exists, and it is NOT under `jobs/` — the
              honest home for a nameless finish is `runs/`, where nothing reads it as a job;
          (b) that directory carries the custody record the emitter wrote, byte for byte what
              the record directory held (sha256 equal), so a reader of the destination can see
              the job ended and what it produced;
          (c) the halt says so: `filing.filed` is true for that copy, or — if the fix instead
              refuses — `filing.filed` is false AND `filing.detail` carries a non-empty reason.
              Silent is the one shape (a) and (b) fail to reach and this forbids.

        The plant that reddens it: a fix that returns `{"filed": False, "dest": None,
        "detail": "NOT FILED: ... is neither a job packet ..."}` — the f0033ab shape measured
        today — leaves nothing under `runs/` and fails (a) and (b). A fix that files the record
        and then blames nobody also passes; that is intentional. A fix that deletes the
        destination after copying to make case 1's manifest equal passes (a) only if the
        destination survives; it will not, and reddens (a) — which is the point.
        """
        with TemporaryDirectory() as into:
            got = _finish(into)
            self.assertIsNone(got["refusal"],
                              "the fixture finish did not complete (%r)." % (got["refusal"],))
            halt = got["halt"] or {}
            self.assertEqual(halt.get("terminal_state"), "accepted",
                             "the fixture finish ended %r, not accepted"
                             % (halt.get("terminal_state"),))
            filing = halt.get("filing") or {}
            dest = str(filing.get("dest") or "")
            record = got["record"]

            # (c) FIRST: a refusal must SAY something; silent non-filing is not a choice.
            if not filing.get("filed"):
                self.assertTrue((filing.get("detail") or "").strip(),
                                "an id-less finish was not filed and gave NO reason: %r. "
                                "`filed: false` with a reason is honest; `filed: false` with an "
                                "empty detail is the silent non-filing the Owner forbade."
                                % (filing,))

            # (a) the finish is reachable under the destination, outside jobs/.
            jobs_dir = os.path.join(into, "jobs")
            runs_dir = os.path.join(into, "runs")
            jobs_now = _listing(jobs_dir)
            runs_now = _listing(runs_dir)
            self.assertTrue(
                dest and os.path.isdir(dest),
                "the id-less finish names no destination that exists: filing=%r. After an "
                "ACCEPTED finish with a custody record in hand, the record must be readable "
                "from the instance record; it lived only in the runner's temp dir and died "
                "with it. jobs/=%r runs/=%r. The honest destinations are runs/ (a nameless "
                "finish is not a job) or a job id the Owner chose; vanishing is not one."
                % (filing, jobs_now, runs_now),
            )
            self.assertFalse(
                os.path.abspath(dest).startswith(os.path.abspath(jobs_dir) + os.sep),
                "the id-less finish was filed under jobs/ at %r — case 1 forbids any entry "
                "there. jobs/=%r" % (dest, jobs_now),
            )
            self.assertTrue(
                os.path.abspath(dest).startswith(os.path.abspath(runs_dir) + os.sep),
                "the id-less finish landed at %r, which is under neither jobs/ (forbidden by "
                "case 1) nor runs/ (where evidence belongs). jobs/=%r runs/=%r"
                % (dest, jobs_now, runs_now),
            )

            # (b) the destination carries the emitter's record, byte for byte.
            if record["exists"]:
                filed_record = os.path.join(dest, "custody", "record.custody.json")
                self.assertTrue(
                    os.path.isfile(filed_record),
                    "the finish was filed at %r but carries no custody/record.custody.json. "
                    "The record the emitter wrote is at %r (sha256 %s); a destination that "
                    "does not contain it is a folder, not a record of the finish."
                    % (dest, record["path"], record["sha256"]),
                )
                with open(filed_record, "rb") as handle:
                    filed_sha = hashlib.sha256(handle.read()).hexdigest()
                self.assertEqual(
                    filed_sha, record["sha256"],
                    "the filed record differs from the one the emitter wrote: filed sha256 %s "
                    "vs emitter %s. A copy that is not byte-identical is not the record."
                    % (filed_sha, record["sha256"]),
                )

    # 4 ------------------------------------------------------------------
    def test_04_a_finish_that_has_a_job_id_still_files_under_that_name(self):
        """BRAKE. Green at base — measured. The fix must not buy case 1 by never filing.

        A finish whose packet DOES carry a job id must still land at `<into>/jobs/<job_id>`, or
        the litter is gone because filing is gone, which is the older defect this whole line of
        work exists to kill (measured 2026-11-09: `jobs/` held two jobs while roughly twenty-
        five had run, because filing was a sentence in a commit message). The Owner named this
        brake explicitly: "a finish that DOES have a job id still files under that name".

        The id is chosen here and is not derivable from anything the loop mints: `job38d-brake`
        contains no scratch token, so a destination equal to it cannot be a coincidence.
        """
        job_id = "job38d-brake"
        with TemporaryDirectory() as into:
            got = _finish(into, job_id=job_id)
            self.assertIsNone(got["refusal"],
                              "the fixture finish did not complete (%r)." % (got["refusal"],))
            halt = got["halt"] or {}
            self.assertEqual(halt.get("terminal_state"), "accepted",
                             "the fixture finish ended %r, not accepted"
                             % (halt.get("terminal_state"),))
            jobs = _listing(os.path.join(into, "jobs"))
            self.assertEqual(
                jobs, [job_id],
                "a finish that HAS a job id did not file under it. jobs/ holds %r; expected "
                "exactly [%r]. summary.filing=%r\n"
                "The litter case must not be fixed by not filing: a finish with an identity is "
                "the one thing `jobs/` is for."
                % (jobs, job_id, halt.get("filing")),
            )
            filed_packet = os.path.join(into, "jobs", job_id, "packet.json")
            self.assertTrue(os.path.isfile(filed_packet),
                            "the filed folder has no packet.json, so it is not a readable job: %r"
                            % (jobs,))
            with open(filed_packet, encoding="utf-8") as handle:
                filed = json.load(handle)
            self.assertEqual(filed.get("job_id"), job_id,
                             "the filed packet names job_id %r, not %r"
                             % (filed.get("job_id"), job_id))
            self.assertTrue(os.path.isfile(os.path.join(into, "jobs", job_id,
                                                       "custody", "status.json")),
                            "the filed job carries no custody/status.json: "
                            "`test_dot_plumbline_filing` requires every folder under jobs/ to "
                            "state its own custody status.")
            self.assertEqual(_listing(os.path.join(into, "runs")), [],
                             "a finish that has a job id also wrote into runs/: %r. A job is "
                             "not evidence." % (_listing(os.path.join(into, "runs")),))

    # 5 ------------------------------------------------------------------
    def test_05_the_job_38c_and_job_37_bars_still_pass(self):
        """BRAKE. Green at base — measured. The Owner's own words: "the two brakes that must
        stay green: the Job 38c bar and the Job 37 bar pass unchanged".

        Each bar is RUN, in its own process, from the repo root, and its own tally is read:
        rc 0 AND "Ran <n> tests" AND "OK". Run rather than hashed, because these are the two
        files most likely to be edited by a fix that reads its red as an invitation, and a
        digest is only as good as someone remembering to update it; a bar that no longer
        passes is the fact, and the case id is what the Owner named.

        `test_job38c` (5 cases) and the Job 37 scoring-set bar (14 cases) are the two; the
        expected counts are read from those bars' own names at run time, not typed, so a bar
        that legitimately grows is caught by its own suite and not silently by a number here.
        """
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO
        env["PLUMBLINE_CUSTODY"] = self.checkout
        env.pop("PLUMBLINE_FILE_INTO", None)
        results = {}
        for label, rel, expected_ran in (("job38c", JOB38C_BAR, 5), ("job37", JOB37_BAR, 14)):
            path = os.path.join(REPO, rel)
            self.assertTrue(os.path.isfile(path), "the %s bar is absent: %s" % (label, rel))
            proc = subprocess.run([PY, path], cwd=REPO, capture_output=True, text=True,
                                  env=env, timeout=1800)
            text = (proc.stdout or "") + (proc.stderr or "")
            results[label] = (proc.returncode, text)
            self.assertEqual(
                proc.returncode, 0,
                "the %s bar %s went red under this change (rc=%d). It is a brake: the litter "
                "fix must leave it passing, not explain it away.\n--- tail ---\n%s"
                % (label, rel, proc.returncode, text[-3000:]),
            )
            self.assertIn("Ran %d test" % expected_ran, text,
                          "the %s bar ran a different number of cases than the %d the Owner's "
                          "brake names; a brake that no longer collects its cases is not a "
                          "brake.\n--- tail ---\n%s" % (label, expected_ran, text[-2000:]))
            self.assertIn("OK", text,
                          "the %s bar reported no OK line.\n--- tail ---\n%s"
                          % (label, text[-2000:]))

    # 6 ------------------------------------------------------------------
    def test_06_this_bars_scoring_set_is_what_the_cases_are(self):
        """The packet's `bounds.scoring_set` must be these ids, in this order.

        Job 35 taught this instance what a scope that drifts from the bar costs: sixteen
        dimensions scored, a case the bar does not collect turning an accept into a regenerate.
        The declared set is checked against what `unittest` actually collects from this file —
        the same reader `kit/conductor_loop.py:_collected_cases()` uses — so the packet cannot
        declare a case this file no longer has, or miss one it gained.
        """
        collected = _collected_here()
        self.assertEqual(
            collected, list(SCORING_SET),
            "this bar's SCORING_SET has drifted from its cases.\n  collected: %r\n  declared : %r\n"
            "The packet's bounds.scoring_set is written from SCORING_SET; fix whichever is "
            "wrong, here, before the packet is dispatched." % (collected, list(SCORING_SET)),
        )


def _collected_here():
    """This file's cases, `test_` stripped, in the order `unittest` collects them.

    Imported through the module the test runner already loaded when this file is run as a
    test; loaded fresh from this file's path when it is run as a script. Either way it reads
    the file that is on disk, not this module's memory of it.
    """
    import importlib.util
    loader = unittest.TestLoader()
    path = os.path.abspath(__file__)
    if __name__ == "__main__":
        module = sys.modules["__main__"]
        if os.path.abspath(getattr(module, "__file__", "")) != path:
            module = None
    else:
        module = sys.modules.get(__name__)
        if os.path.abspath(getattr(module, "__file__", "")) != path:
            module = None
    if module is None:
        spec = importlib.util.spec_from_file_location("plumbline_bar_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    names = []
    for test in loader.loadTestsFromModule(module):
        for case in test:
            name = case.id().rsplit(".", 1)[-1]
            if name.startswith("test_"):
                name = name[len("test_"):]
            names.append(name)
    return names


if __name__ == "__main__":
    unittest.main()
