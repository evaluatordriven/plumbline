"""Bar — the emitter resolves the custody spec version from the document it attests, or refuses.

CASE IDS / DIMENSION NAMES (route-eval derives them from this file, in this order, and refuses a
score whose names are not exactly this list in this order):

    1. version_is_read_from_the_custody_document
    2. no_document_no_override_refuses
    3. the_override_is_honoured
    4. the_override_does_not_collide_with_the_document
    5. every_published_verdict_is_byte_for_byte_unchanged
    6. the_bar_leaves_its_subject_clean
    7. the_claim_about_the_emitter_survives_the_emitter_changing
    8. the_claims_tool_selftest_runs_and_keeps_its_rule_set
    9. a_deleted_selftest_rule_is_caught

WHY THIS FILE EXISTS
--------------------
Measured at plumbline `8590496` (2026-11-10):

    kit/emit_custody.py:88     SPEC_VERSION = "0.9.8"            a literal. No resolution. No refusal.
    kit/emit_custody.py:594      "specVersion": SPEC_VERSION      the round path stamps it
    kit/emit_custody.py:1179     "specVersion": SPEC_VERSION      the inputs path stamps it

The custody document `custody/tools/count.py:153-161` requires a record named `custody-v<version>.json`
to carry `predicate.specVersion == <version>`. So a job that attests custody at any version other than
the literal emits a record the document refuses, and the emitter cannot notice: it never looks at a
document in order to say what version it is attesting.

One directory over, the re-pin learned this on 2026-11-10 (`tests/test_repin_spec_version.py`,
`tools/build_schemas.py:custody_spec_version`): *"The fix reads the version from the checkout's own
SPEC.md, and refuses the re-pin when it cannot."* This bar asks the emitter for the same property,
with two additions the re-pin did not need:

  R1  RESOLVE FROM THE DOCUMENT. The record's `specVersion` is the version the custody document the
      job attests declares. Not a literal in the emitter. Not the re-pin. The document is a custody
      checkout: `<dir>/SPEC.md` carrying `**Version X.Y.Z · ...**`. The job names that checkout one of
      two ways, both of which are the job attesting a document:
        (a) `inputs/custody.json` -> `custody_spec` = a path to the checkout (absolute, or relative to
            the job dir); the record names the SPEC.md it read under
            `predicate.x-plumbline.spec_version = {source, path, sha256, origin}`.
        (b) failing (a), `--spec-version X.Y.Z` on the command line: the override, and the record says
            `origin: "--spec-version"`.
  R2  REFUSE RATHER THAN GUESS. Neither the document nor an override -> exit 3, a refusal naming
      `spec-version`, and NO record written (an existing record is left as it was). A `custody_spec`
      that does not exist, is not a directory, has no SPEC.md, or whose SPEC.md declares no
      `**Version X.Y.Z**` is a REFUSAL, never a fall-back to the override, never a fall-back to the
      literal. When a checkout names its own commit (`git -C <dir> rev-parse HEAD` answers) the
      containing git work tree's HEAD must BE that commit: a SPEC.md read beside the wrong commit is
      not the document the job attests (this is `--expect-revision`'s rule, one level down).
  R3  THE OVERRIDE STAYS AVAILABLE. A job whose artifact is not a custody tree carries
      `--spec-version` and the record says so (`origin: "--spec-version"`), including for a version
      while no literal anywhere in the emitter says it.
  R4  NO PUBLISHED VERDICT MOVES. Every stored custody record in the tree keeps the `specVersion` it
      publishes today (0.9.6, all fourteen of them), and `tools/pin.json` keeps its `0.9.8`: the fix
      moves no reading a reader already holds, and it rewrites no history on disk.

WHAT THE FIX MAY DO WITH THE LITERAL — deliberately NOT legislated
------------------------------------------------------------------
An earlier draft of this bar asserted that `SPEC_VERSION = "0.9.8"` was gone from `kit/emit_custody.py`
as source text. That case was dropped: it legislated a spelling, not an observable, and it could be
satisfied by a rename while the defect stood, or broken by a correct fix that stores the value
differently. The property that matters is case 1: with the document saying 0.9.9 and every literal in
the emitter saying something else, the record says 0.9.9. Case 3 measures the mirror: with no document
and an override of 0.9.7, the record says 0.9.7 — a record can only say one thing, so whichever route
a fix leaves untaught reddens a case.

THE SUBJECT AND HOW A CASE REACHES IT
-------------------------------------
The subject is `kit/emit_custody.py` at `8590496`, run as a PROCESS (`--job-dir`, `--out`), never
imported: the exit code graded is the process's, not a patched function's. Each case copies the
committed job tree into a scratch root outside the job tree, edits only that copy, and runs the
emitter with that copy as its current directory. Two paths are exercised, because the emitter has two
and each stamps the literal separately (:594 and :1179):

  INPUTS  `tests/fixtures/custody/job-rejected`, a full custody-inputs job. Case 1 is the load-bearing
          case here: RED at 8590496 because it stamps 0.9.8 over a document that says 0.9.9.
  ROUND   `dot-plumbline/jobs/plumbline-cl1-time-record-1`, a job loop() filed (its packet carries
          `finish`, so the emitter takes its round path, :594) that already emitted a custody record at
          8590496. Case 2 reads the path this job actually files through: with no `custody_spec` and no
          override the emitter must refuse; at 8590496 it writes a record stamped 0.9.8 and exits 0.
          That the path is reached is itself asserted (exit 3 with the token `spec-version`, not exit 2
          "no packet"), so a case that could not reach its assertion is an error, not a green.

A SECOND SUBJECT, BECAUSE THE FIRST ONE MOVES A GUARD (case 7)
--------------------------------------------------------------
The editable set is TWO files: `kit/emit_custody.py` and `tools/check_version_claims.py`. The second
holds a claim about the first, and the claim is the thing a fix breaks without noticing.

    tools/check_version_claims.py:70-76   (at 8590496)
      emitter = root / "kit" / "emit_custody.py"
      if emitter.is_file() and spec_version:
          match = re.search(r'^SPEC_VERSION\\s*=\\s*"(\\d+\\.\\d+\\.\\d+)"', emitter.read_text(...), re.M)
          if match:
              out.append(("kit/emit_custody.py SPEC_VERSION", "v" + match.group(1), "v" + spec_version))

Claim 6 of 6 is **conditional on the literal existing**. The moment the emitter resolves its version
instead of holding `SPEC_VERSION = "0.9.8"`, the regex stops matching, the claim is silently DROPPED,
the tool prints `5 claim(s), every one agrees with its pin`, and exits 0. Measured at base in this
tree: `check_version_claims: 6 claim(s), every one agrees with its pin`, exit 0 — claims 1 to 5 rest on
the pin and the vendored bytes and pass on no document at all, so the count is the only thing holding
the guard, and it is a count.

That is why the second file is editable and why this case exists. The fix is free to choose the form —
read the pin the emitter now resolves from, follow the emitter's `resolve_spec_version`, parse the stamp
site, do something nobody has thought of — and the case does not legislate a spelling. It legislates
that the claim DOES NOT VANISH: a claim whose subject is the emitter's stamped version, still agreeing
with the pin, and a total count that is ASSERTED rather than reported.

Case 7 accepts exactly two counts, and each is a deliberate act:
    6  the claim survives in a new form: the same six claims the tool reported at 8590496.
    7  the tool adds exactly one new claim (the fix teaches it one more thing to say). The added label
       is printed on a miss so the reason can be stated and this number re-cut deliberately.
Any other total — 5 above all — is red with the count printed, because 5 is the number the tool prints
when the guard has gone silent, and it is the only number that must never be accepted.

WHY CASE 7 IS NOT A STAND-IN CASE, AND WHERE ITS BITE IS RECORDED
------------------------------------------------------------------
The bite is measured by the Architect and recorded here as a fact with its numbers; it is NOT re-run on
every execution of this bar. Re-running it would mean the bar edits its own second subject on every run
and then asserts on the result — and the Maker cannot touch this file, so nothing it does can affect
that measurement. What this bar measures on every run is the live tree: the claim count, the emitter
claim's agreement with the pin, and a named failure if the claim is gone.

THERE ARE TWO WAYS A CLAIM STOPS GUARDING, AND CASE 7 GRADES BOTH
------------------------------------------------------------------
  A claim that VANISHES: the emitter stops holding a literal, the tool's regex stops matching, the
  claim is dropped, and the count falls 6 -> 5 with the tool still printing agreement. (a)-(c) above
  catch this. It was the only shape this case had until 2026-11-11.

  A claim that LIES: the claim still publishes, still names the file, and its value disagrees with the
  pin — because the tool is not reading the emitter, or reads it wrongly. (a)-(c) do NOT catch this on
  their own: a stub that echoes the pin's version satisfies "publishes, agrees, count 6 or 7" while
  reading nothing. So case 7 ends by CONSTRUCTING this shape at run time: a copy of the committed tree
  with the emitter's literal edited to `PLANTED_EMITTER_VERSION`, the tool untouched, and the bar's
  reading of the tool's own claim list must say the claim LIES — naming both values — and the tool must
  exit non-zero. The claim count is required to be UNCHANGED there, so the control cannot degrade into
  the vanish probe it is meant to complement.

MEASURED BITE, BOTH SHAPES (Architect, 2026-11-11, against this bar's own harness — the LIE shape is
  re-measured on EVERY execution of case 7's (d) control; the VANISH shape was measured out of band and
  runs from this file's own probe helpers):
  VANISH  a disarming stand-in — `kit/emit_custody.py` turned into `SPEC_VERSION = _resolved_spec_version()`
          read from `tools/pin.json`, `tools/check_version_claims.py` left exactly as it is — and the tool
          then printed `check_version_claims: 5 claim(s), every one agrees with its pin`, exit 0. Claim 6
          was gone and the tool said every claim agreed. RED on (c): 5 not in (6, 7).
  LIE     the literal at `kit/emit_custody.py:88` changed from "0.9.8" to "0.9.5", the tool untouched:
          the tool published 6 claims, the emitter claim read `('kit/emit_custody.py SPEC_VERSION',
          'v0.9.5', 'v0.9.8')`, and the tool printed `check_version_claims: kit/emit_custody.py
          SPEC_VERSION: claims 'v0.9.5', pin holds 'v0.9.8'`, exit 1. The bar's reading is
          `the claim about kit/emit_custody.py LIES: kit/emit_custody.py SPEC_VERSION claims 'v0.9.5'
          while the pin holds 'v0.9.8'` — RED, naming the disagreement. That sentence comes from the
          (a0) branch, which reads a PRESENT-but-disagreeing claim BEFORE the agreement assertion, so
          it is reached on the live tree and not only inside (d): measured 2026-11-11, with the
          emitter stamped 0.9.5 that branch fires first and the tuple dump (b) used to print is gone.
          A claim that VANISHES never reaches it — (a) reports it as VANISHED — and the two messages
          are measured to be non-swappable: LIE says LIES and not VANISHED, VANISHED says VANISHED and
          not LIES.

CASES 8 AND 9: THE TOOL'S OWN SELFTEST, RUN FROM THE BAR
---------------------------------------------------------
`tools/check_version_claims.py --selftest` plants one mismatch per rule and reports one line per rule.
It was never run by this bar and nothing else in the tree ran it (`.github/workflows/ci.yml:44` invokes
the tool without `--selftest`; `tests/run_all.py` does not reference it). The tool is EDITABLE this job,
so the rule set is a thing a fix can silently shrink:

  case 8  runs the selftest FROM THE BAR, requires exit 0, every reported line `[PASS]`, and requires the
          four rule names it reports at 8590496 — `clean`, `wrong corpus dir`, `wrong custody commit`,
          `wrong custody version` — to still be there. Each non-`clean` rule must expect at least one
          violation, so a rule cannot be reduced to one that cannot fail.
  case 9  the control: delete ONE rule from a copy's `cases` dict and show that case 8's rule set goes
          RED naming the deleted rule. Measured 2026-11-11: deleting `wrong custody version` left three
          `[PASS]` lines and exit 0 — so a case that graded only the exit code would have passed.

MEASURED BITE (Architect, 2026-11-11, the VANISH shape, recorded when case 7 had only (a)-(c)):
a disarming stand-in — `kit/emit_custody.py` turned into `SPEC_VERSION = _resolved_spec_version()` read
from `tools/pin.json`, with `tools/check_version_claims.py` left exactly as it is — and the tool then
printed `check_version_claims: 5 claim(s), every one agrees with its pin`, exit 0. Claim 6 was gone and
the tool said every claim agreed. Under this case that stand-in is RED: base reading 6 claims, stand-in
reading 5, 5 not in (6, 7), and no claim remains whose subject is the emitter's stamped version. The
control reddens when the guard is disarmed on the one input the fix changes.

That measurement is the VANISH shape. Until 2026-11-11 it was the only shape case 7 had, and it does not
cover a claim that is DEFANGED rather than dropped — see THERE ARE TWO WAYS A CLAIM STOPS GUARDING above,
and (d) in the case, which constructs that shape on every run.

WHY THE SCRATCH TREE IS COMMITTED, AND WHAT IT MEANS FOR CASE 6
---------------------------------------------------------------
`kit/custody_history.py:515-518` refuses a dirty tree. The job tree the Orchestrator builds is a commit
of plumbline at `8590496` WITH THIS BAR COMMITTED INTO IT, so the bar is tracked. In that tree:

    t = tempfile.mkdtemp(); shutil.copytree(REPO, t, ignore=.git, __pycache__, *.pyc)
    git init; git add -A; git commit           # the whole copy, identical to REPO's tree

is the same tree at the same HEAD, clean. The `git status --porcelain` in case 6 is empty with the bar
committed and names `tests/test_emit_spec_version.py` the moment the bar is untracked — which is the
behaviour the Orchestrator's brief wants the bar to have. A tree copied from a checkout where the bar
is untracked stays clean in the copy too (the copy commits everything), so the case measures the SOURCE
tree the bar was run from, not the copy's provenance.

Case 6 is honest about a limit: this file cannot assert on its own bytes (a bar that named its own
digest would break whenever it was touched). What it measures:
  6a. the source tree's `git status --porcelain` is EMPTY after every case above has emitted, read and
      written nothing into it;
  6b. the copy is clean immediately after being committed (the mechanism above holds);
  6c. a file this bar plants in the source tree shows up in the source tree's porcelain — so 6a is a
      real measurement that could fail, not a string that cannot.

THE CONTROL THAT MATTERS HERE (case 5)
--------------------------------------
"Every published verdict still reads as it read" is measured, not promised. Fourteen stored custody/v1
records exist in the tree (`**/*.custody.json`); all fourteen publish `specVersion: 0.9.6`; none of the
fourteen's bytes changes. And the pin still says 0.9.8. A fix that reaches back and re-stamps a stored
record, or that "corrects" the pin to the literal's new meaning, is red here.

RED BEFORE THE FIX, MEASURED AT 8590496
---------------------------------------
  1  RED   the emitter stamps "0.9.8" over a document that says 0.9.9 (the defect, :1179)
  2  RED   the emitter takes the round path, writes a record stamped "0.9.8" and exits 0 (:594); when
           this job's own inputs leave two approval times without an RFC 3339 source it exits 1 with a
           record written — in neither case does it refuse, and refusing (3) is the property.
  3  RED   `--spec-version 0.9.7` is not a flag at 8590496: argparse exits 2 with a usage error; the
          record says nothing, so "the record says 0.9.7 and names --spec-version" is false.
          Round-path half (re-cut, see ROUND PATH under case 3): this fixture's two approvals have no
          `at` in packet.json, inputs/custody.json or custody-events.jsonl, so the round path exits 1
          AT BASE with a record written. The case therefore grades the record — it must carry 0.9.7,
          name `--spec-version` as origin, and show no spec-version gap — and accepts exit 0, 1 or 3.
          It does NOT require exit 0 of a fixture whose exit 1 belongs to the approval times. At
          8590496 argparse still exits 2, so the case is RED there either way.
  4  GREEN a control: at 8590496 the flag is refused before any record exists (argparse, exit 2), so
           "the record never silently picks one" holds trivially. Labelled as a control; it guards
           R1/R3's interaction (the override must not win over the document without saying so).
  5  GREEN a control: no stored record moves, and the pin is untouched, at 8590496 and after any fix
  6  GREEN a control: 8590496 writes nothing into its own tree when the bar's scratch copies are used
  7  GREEN at base, and GREEN is the correct colour for it: at 8590496 the literal is present, the tool
          emits 6 claims and the emitter claim agrees with the pin. It is not a control over the fix
          (a fix cannot satisfy it by luck); it is an IMMOVABLE GUARD over the fix's side effect. It
          reddens on the disarming stand-in measured above, and it reddens if a fix drops or mis-states
          the claim. A guard that can only be green proves nothing unless it has been shown to bite;
          this one has, with its numbers, in MEASURED BITE above — on BOTH shapes, the claim dropped and
          the claim defanged.
  8  GREEN at base: `tools/check_version_claims.py --selftest` exits 0 and reports all four rules there.
          A guard over the second editable file's own guard: the rule set is pinned by name so a fix that
          shrinks it to "exit 0" is red.
  9  GREEN at base: deleting a rule from a copy does not move the exit code, and this case asserts that
          the deletion IS noticed — so it measures case 8's ability to fail, not the tool's health.

The editable set is two files (`kit/emit_custody.py`, `tools/check_version_claims.py`). Both are
needed for one property: the emitter resolves its version, and the repository can still SAY what the
emitter stamps. A fix that changes one and not the other either leaves case 1 red or silently disarms
the guard in case 7.

Exit: 0 every case passes · 1 one or more cases failed (the failing case is named, with its assertion) ·
2 the bar could not run (a fixture is missing, git is absent, the interpreter is too old). Non-zero is
RED; the loop dispatches on it (`kit/conductor_software.dispatch_reason`).
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
HERE = Path(__file__).resolve().parent
REPO = HERE.parent

# ---- the subject, and the two jobs it is reached through -------------------------------------
EMITTER_REL = "kit/emit_custody.py"
INPUTS_JOB_REL = "tests/fixtures/custody/job-rejected"
ROUND_JOB_REL = "dot-plumbline/jobs/plumbline-cl1-time-record-1"

# ---- the document the inputs-path case attests, and what it will declare ----------------------
DOC_VERSION = "0.9.9"      # deliberately not the literal at 8590496 and not the pin
DOC_BODY = (
    "# Evaluator Driven — the custody record\n"
    "\n"
    "**Version %s · candidate · 2026-11-10** · Predicate type "
    "`https://evaluatordriven.com/custody/v1`\n" % DOC_VERSION
)
OVERRIDE_VERSION = "0.9.7"  # not the literal, not the pin, not DOC_VERSION

# ---- the second subject: the tool that claims what the emitter stamps ---------------------------
CLAIMS_TOOL_REL = "tools/check_version_claims.py"

# The counts case 7 accepts. Each is a deliberate act, spelled out in the docstring.
#   6  the claim survives in the new form: the same six the tool reported at 8590496
#   7  the fix teaches the tool exactly one more thing to say (see CLAIM_COUNT_SEVEN_REASON)
CLAIM_COUNTS_OK = (6, 7)
CLAIM_COUNT_SEVEN_REASON = (
    "not yet granted — no fix has argued for it. Re-cut this tuple with a reason on the bar, not by the Maker."
)
# What makes a claim "about the emitter": its label names the file, whatever the fix calls the claim.
EMITTER_HINT = "emit_custody.py"

# ---- case 7b: the planted disagreement (the DEFANGED claim, not the vanished one) ---------------
# A copy of the committed tree whose emitter's stamped version is a DIFFERENT well-formed version
# from the pin's custody specVersion. The claim about the emitter still publishes there (count 6 — it
# has not vanished), and it must be RED: the two values must be read out of the tool's own claim list
# and compared, and the failure must name both. This closes the hole a "vanished claim" probe cannot:
# a claim that echoes the pin without reading the emitter agrees, publishes, and would be green.
PLANTED_EMITTER_VERSION = "0.9.5"   # well-formed, not the pin (0.9.8), not DOC_VERSION, not OVERRIDE
_LITERAL_RE = r'^(SPEC_VERSION\s*=\s*")(\d+\.\d+\.\d+)("\s*)$'

# ---- case 8: the tool's own selftest must run from the bar, and must still have all its rules -----
# These are the four rule names `tools/check_version_claims.py --selftest` reports at 8590496. They are
# pinned by NAME, not by count, because the file is editable this job: a deleted rule leaves the count
# one short AND the name absent, and the name is what the failure has to say.
SELFTEST_RULES_REQUIRED = (
    "clean",
    "wrong corpus dir",
    "wrong custody commit",
    "wrong custody version",
)

# ---- what the tree publishes today, by measurement (see the docstring) -----------------------
PUBLISHED_SPEC_VERSION = "0.9.6"
PINNED_SPEC_VERSION = "0.9.8"
GENERATION_MAX = ">2"

# Clause tags the grader may cite. Each is a sentence of the Owner's requirement, above.
CLAUSES = {
    "C1": "resolve the version from the custody document the job attests",
    "C2": "refuse rather than guess when it cannot resolve it",
    "C3": "`--spec-version` stays available as an explicit override",
    "C4": "no published verdict may move",
    "C5": "proven by a test that fails first",
}

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "bar", "GIT_AUTHOR_EMAIL": "bar@localhost",
    "GIT_COMMITTER_NAME": "bar", "GIT_COMMITTER_EMAIL": "bar@localhost",
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
}


class CaseFailure(AssertionError):
    """A property did not hold. Named with the case id and the clause it measures."""


# The tree's state before the bar runs a single case. Case 6 measures the bar's own footprint against
# this, not against empty: inside the loop the tree necessarily holds the Maker's uncommitted work, and
# a control that reports the subject's dirt as the instrument's dirt cannot be satisfied by any correct
# fix (Job 34: the artifact passed 9/9 committed and was refused uncommitted).
BAR_START = ""


def setUpModule():
    global BAR_START
    BAR_START = _porcelain(REPO)


def die(msg: str) -> None:
    """The bar could not reach its assertion. That is an ERROR (exit 2), never a red."""
    print(f"bar emit_spec_version: ERROR {msg}", file=sys.stderr)
    raise SystemExit(2)


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, env=GIT_ENV)


def _porcelain(root: Path) -> str:
    r = _git(["status", "--porcelain=v1", "--untracked-files=all"], root)
    if r.returncode != 0:
        die(f"`git status` failed in {root}: {r.stderr.strip()[:200]}")
    return r.stdout


def _commit_tree(tree: Path, message: str) -> None:
    """Commit every byte of `tree` at one commit: the copy is the source tree, clean."""
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-qm", message]):
        r = _git(cmd, tree)
        if r.returncode != 0:
            die(f"git {cmd[0]} failed in {tree}: {(r.stderr or r.stdout).strip()[:300]}")


def _fresh_head(tree: Path) -> str:
    r = _git(["rev-parse", "HEAD"], tree)
    if r.returncode != 0:
        die(f"cannot read HEAD of {tree}")
    return r.stdout.strip()


class Scratch:
    """A committed copy of the committed job tree, and jobs copied out of it, all outside the job tree.

    Copied with `.git` and bytecode caches left behind, then `git init` + `git add -A` + `git commit`,
    so the copy is the source tree's bytes at one commit and the emitter's revision refusal
    (custody_history.py:515-518) cannot mask the defect under test.
    """

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="plumbline-emit-spec-"))
        self.tree = self.root / "tree"
        shutil.copytree(REPO, self.tree,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        _commit_tree(self.tree, "bar: the committed tree, one commit")

    def clean_after_commit(self) -> str:
        return _porcelain(self.tree)

    def job(self, rel: str, name: str) -> Path:
        src = REPO / rel
        if not src.is_dir():
            die(f"the job {rel} is not in the tree the bar was run from: {src}")
        dst = self.root / name
        shutil.copytree(src, dst)
        return dst

    def document(self, name: str, body: str = DOC_BODY, commit: bool = True) -> Path:
        """A custody checkout: `SPEC.md`, and (when committed) a git work tree at its own HEAD."""
        d = self.root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SPEC.md").write_text(body, encoding="utf-8")
        if commit:
            _commit_tree(d, "bar: a custody checkout")
        return d

    def emit(self, job: Path, out: Path, *extra: str):
        cmd = [PY, EMITTER_REL, "--job-dir", str(job), "--out", str(out), "--allow-hand-times", *extra]
        proc = subprocess.run(cmd, cwd=str(self.tree), capture_output=True, text=True)
        record = None
        if out.is_file():
            try:
                record = json.loads(out.read_text(encoding="utf-8"))
            except ValueError:
                record = None
        return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), record

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def spec_of(record) -> object:
    if not isinstance(record, dict):
        return None
    return (record.get("predicate") or {}).get("specVersion")


def version_block(record) -> dict:
    if not isinstance(record, dict):
        return {}
    block = ((record.get("predicate") or {}).get("x-plumbline") or {}).get("spec_version")
    return block if isinstance(block, dict) else {}


def add_custody_spec(job: Path, value) -> None:
    """Point the job's custody inputs at a document, as `inputs/custody.json: custody_spec`."""
    p = job / "inputs" / "custody.json"
    if not p.is_file():
        die(f"{job} has no inputs/custody.json to attach a document to")
    body = json.loads(p.read_text(encoding="utf-8"))
    if value is None:
        body.pop("custody_spec", None)
    else:
        body["custody_spec"] = value
    p.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def claims_report(root: Path, tool: Path):
    """Run the claims tool as a PROCESS, in its own tree: (exit, stdout, the claims it published).

    The claim list is read by importing the tool under test, from its own directory, after the exit
    code has been graded — the exit code is the process's, the list is the tool's own answer.
    A tool that does not import is not an error here: it simply publishes no claim, and case 7 says so.
    """
    proc = subprocess.run([PY, str(tool)], cwd=str(root), capture_output=True, text=True)
    listed = None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("claims_tool_under_test", tool)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        listed = list(module.claims(root))
    except BaseException:                                      # noqa: BLE001 - any failure: no list
        listed = None
    return proc.returncode, (proc.stdout or "") + (proc.stderr or ""), listed


def emitter_claim_verdict(listed) -> tuple[bool, str]:
    """(does the emitter's claim agree with the pin?, a sentence naming the values).

    Read PURELY from the tool's own claim list — no assumption about the spelling of the label beyond
    the file it names, and no assumption that there is exactly one such claim. A claim that is absent
    and a claim that is present-but-disagreeing are DIFFERENT failures, and the sentence says which.
    """
    pin = json.loads((REPO / "tools" / "pin.json").read_text(encoding="utf-8"))
    pinned = str(pin.get("custody", {}).get("specVersion", ""))
    rows = [row for row in (listed or []) if EMITTER_HINT in str(row[0])]
    if not rows:
        return False, (f"no claim about {EMITTER_REL} is published at all (the claim VANISHED); "
                       f"claims seen: {[str(r[0]) for r in (listed or [])]}")
    bad = [(str(r[0]), str(r[1]), str(r[2])) for r in rows if str(r[1]) != str(r[2])]
    if bad:
        detail = "; ".join(f"{label} claims {claimed!r} while the pin holds {actual!r}"
                           for label, claimed, actual in bad)
        return False, f"the claim about {EMITTER_REL} LIES: {detail}"
    named = [str(r[1]) for r in rows]
    if ("v" + pinned) not in named:
        return False, (f"the claim(s) about {EMITTER_REL} agree with something, but none names the pin's "
                       f"custody specVersion v{pinned}: they name {named}")
    return True, f"the claim about {EMITTER_REL} publishes and agrees with the pin (v{pinned})"


def plant_emitter_disagreement(src_tree: Path, dst: Path, version: str = PLANTED_EMITTER_VERSION) -> Path:
    """A committed copy of `src_tree` whose emitter stamps `version` instead of whatever it holds.

    The literal at the emitter's stamp site is replaced with another WELL-FORMED version, and nothing
    else is touched: `tools/check_version_claims.py` is left exactly as it is, so its claim still
    matches, still publishes, and now disagrees with the pin. That is the DEFANGED claim — the shape
    a hurried fix takes — as opposed to the vanished claim a dropped literal produces.

    The file is rewritten and the copy re-committed, so a fix that refuses to run on a dirty tree
    (custody_history.py:515-518) still reaches its assertion here.
    """
    if dst.exists():
        die(f"the disagreement copy already exists at {dst}; the bar does not overwrite it")
    shutil.copytree(src_tree, dst, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    emitter = dst / EMITTER_REL
    text = emitter.read_text(encoding="utf-8")
    hit = re.search(_LITERAL_RE, text, re.M)
    if hit is None:
        die(f"{EMITTER_REL} in the copy declares no `SPEC_VERSION = \"x.y.z\"` literal to plant "
            f"against, so this case cannot construct the disagreement it grades")
    emitter.write_text(text[:hit.start()] + hit.group(1) + version + hit.group(3) + text[hit.end():],
                       encoding="utf-8")
    _commit_tree(dst, f"bar: a planted disagreement, emitter stamps {version}")
    return dst


def selftest_report(root: Path) -> tuple[int, str]:
    """Run `tools/check_version_claims.py --selftest` as a PROCESS in `root`: (exit, output)."""
    proc = subprocess.run([PY, CLAIMS_TOOL_REL, "--selftest"], cwd=str(root),
                          capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def selftest_rules_seen(text: str) -> dict:
    """The rule names a selftest's `[PASS]`/`[FAIL]` lines report, mapped to their verdict line.

    The selftest prints one line per rule: `  [PASS] selftest <rule>: N violation(s), expected M`.
    This reads the rules OUT OF THE OUTPUT, so a rule that was deleted shows up as absent rather
    than as an assumption this bar makes.
    """
    seen = {}
    for line in text.splitlines():
        hit = re.search(r"\[(PASS|FAIL)\]\s+selftest\s+(.+?):\s*(\d+)\s+violation\(s\),\s*expected\s+(\d+)",
                        line)
        if hit:
            seen[hit.group(2).strip()] = {"verdict": hit.group(1), "got": hit.group(3),
                                          "expected": hit.group(4), "line": line.strip()}
    return seen


def reach_inputs_path(sp: Scratch, name: str) -> Path:
    """The inputs-path job, reachable: proves the case after this is about the property under test.

    fix must keep working (R3), so this probe cannot itself depend on the property case 1 measures.

    At baseline 8590496 `--spec-version` does not exist, so the probe cannot be satisfied there.
    That is case 3's defect to measure, not this probe's: when the flag is absent the emitter exits 2
    with argparse's usage text, and the calling case proceeds — it will red on the property it
    actually grades (or, for case 4, find no record and return). Anything else is an ERROR, because
    then the case cannot say what it measured.
    """
    job = sp.job(INPUTS_JOB_REL, "job-" + name)
    add_custody_spec(job, None)
    out = sp.root / (name + "-reach.json")
    rc, text, record = sp.emit(job, out, "--spec-version", OVERRIDE_VERSION)
    if rc == 2 and "unrecognized arguments" in text and "--spec-version" in text:
        return job          # the flag does not exist yet: case 3 measures that; this is not an error
    if rc != 0 or spec_of(record) is None:
        raise CaseFailure(
            "the inputs path cannot be reached: " + INPUTS_JOB_REL + " under --spec-version "
            f"{OVERRIDE_VERSION} must emit a record carrying a specVersion, so that a later case's "
            f"result is about the property under test and not about the emitter failing earlier. "
            f"rc={rc}\n{text[-1500:]}"
        )
    return job


class EmitterResolvesSpecVersion(unittest.TestCase):
    """kit/emit_custody.py resolves predicate.specVersion from the document, or refuses."""

    @classmethod
    def setUpClass(cls):
        for rel in (EMITTER_REL, INPUTS_JOB_REL, ROUND_JOB_REL):
            if not (REPO / rel).exists():
                die(f"the bar was run from {REPO}, which has no {rel}")
        cls.sp = Scratch()

    @classmethod
    def tearDownClass(cls):
        cls.sp.close()

    # ---- 1 ---------------------------------------------------------------------------------------
    def test_version_is_read_from_the_custody_document(self):
        """REQ C1 · baseline 8590496: was RED (not a current verdict — the verdict is the ok/FAIL beside this line).

        The job attests a custody checkout whose SPEC.md declares **Version 0.9.9**. The record must
        carry specVersion "0.9.9" and must name the document it read (that SPEC.md, by digest). At
        8590496 the record carries "0.9.8" — the emitter's literal — and names no document.
        """
        reach_inputs_path(self.sp, "doc-reach")
        checkout = self.sp.document("custody-0.9.9")
        job = self.sp.job(INPUTS_JOB_REL, "job-document")
        add_custody_spec(job, str(checkout))
        out = self.sp.root / "document.json"
        rc, text, record = self.sp.emit(job, out)

        self.assertEqual(rc, 0, "a job that attests a readable document must emit (a clean gap-free "
                                f"record is exit 0; this fixture's record is clean at 8590496). rc={rc}\n{text[-2000:]}")
        self.assertEqual(
            spec_of(record), DOC_VERSION,
            "predicate.specVersion must be the version the job's custody document declares "
            f"({DOC_VERSION!r}); the record says {spec_of(record)!r}. A record that attests a document "
            f"and stamps a different version is the self-contradiction this bar exists to forbid.\n{text[-1500:]}",
        )
        block = version_block(record)
        spec_sha = __import__("hashlib").sha256((checkout / "SPEC.md").read_bytes()).hexdigest()
        self.assertEqual(block.get("sha256"), spec_sha,
                         f"x-plumbline.spec_version must name the SPEC.md it read by digest ({spec_sha}); "
                         f"it says {block.get('sha256')!r}")
        self.assertEqual(block.get("origin"), "document",
                         f"x-plumbline.spec_version.origin must say the version came from the document; "
                         f"it says {block.get('origin')!r}")

    # ---- 2 ---------------------------------------------------------------------------------------
    def test_no_document_no_override_refuses(self):
        """REQ C2 · baseline 8590496: was RED on the round path (:594) (not a current verdict — see the ok/FAIL beside this line).

        A job with no custody document and no --spec-version must be REFUSED: exit 3, a refusal that
        names spec-version, and no record written. Measured on a job loop() filed, because that is the
        path whose literal is the other one: at 8590496 this job emits exit 0 and stamps "0.9.8".
        """
        job = self.sp.job(ROUND_JOB_REL, "job-refuse-round")
        out = self.sp.root / "refuse-round.json"
        rc, text, record = self.sp.emit(job, out)
        self.assertEqual(
            rc, 3,
            "with no custody document and no override the emitter must refuse (exit 3); it returned "
            f"{rc}. Exit 2 is a different refusal (no packet, unreadable inputs, not terminal) and does "
            f"not satisfy this case. record={'written' if record is not None else 'none'}\n{text[-2000:]}",
        )
        self.assertIn("spec-version", text,
                      f"the refusal must name the field it could not resolve; it printed:\n{text[-1500:]}")
        self.assertIsNone(record, "a refusal must write no record; one was written")

        # the inputs path must refuse too, on the same property
        inputs_job = self.sp.job(INPUTS_JOB_REL, "job-refuse-inputs")
        add_custody_spec(inputs_job, None)
        out2 = self.sp.root / "refuse-inputs.json"
        rc2, text2, record2 = self.sp.emit(inputs_job, out2)
        self.assertEqual(rc2, 3, f"the inputs path must refuse on the same property; rc={rc2}\n{text2[-1500:]}")
        self.assertIn("spec-version", text2, f"the inputs-path refusal must name the field:\n{text2[-1500:]}")
        self.assertIsNone(record2, "the inputs path wrote a record where it must refuse")

        # an existing record is left as it was when the emitter refuses
        existing = self.sp.job(ROUND_JOB_REL, "job-refuse-existing")
        pre = existing / "custody" / "record.custody.json"
        if not pre.is_file():
            die(f"{ROUND_JOB_REL} no longer carries a record to leave alone")
        before = pre.read_bytes()
        rc3, text3, _ = self.sp.emit(existing, self.sp.root / "refuse-existing.json")
        self.assertEqual(rc3, 3, f"a job with an existing record must still refuse; rc={rc3}\n{text3[-1200:]}")
        self.assertEqual(pre.read_bytes(), before,
                         "the emitter rewrote (or deleted) an existing custody record while refusing")

    # ---- 3 ---------------------------------------------------------------------------------------
    def test_the_override_is_honoured(self):
        """REQ C3 · baseline 8590496: was RED (argparse: `--spec-version` did not exist, exit 2). Not a current verdict — see the ok/FAIL beside this line.

        A job whose artifact is not a custody tree carries the override. The record must carry the
        override's version and say that is where it came from — including a version no literal in the
        emitter names.
        """
        reach_inputs_path(self.sp, "override-reach")
        job = self.sp.job(INPUTS_JOB_REL, "job-override")
        add_custody_spec(job, None)
        out = self.sp.root / "override.json"
        rc, text, record = self.sp.emit(job, out, "--spec-version", OVERRIDE_VERSION)
        self.assertEqual(rc, 0, f"--spec-version {OVERRIDE_VERSION} must be accepted; rc={rc}\n{text[-1500:]}")
        self.assertEqual(spec_of(record), OVERRIDE_VERSION,
                         f"predicate.specVersion must be the override ({OVERRIDE_VERSION!r}); it is "
                         f"{spec_of(record)!r}")
        origin = version_block(record).get("origin")
        self.assertEqual(origin, "--spec-version",
                         f"x-plumbline.spec_version.origin must name the override, so a reader can tell "
                         f"an asserted version from a read one; it says {origin!r}")

        # the override reaches the round path too (:594)
        round_job = self.sp.job(ROUND_JOB_REL, "job-override-round")
        out2 = self.sp.root / "override-round.json"
        rc2, text2, record2 = self.sp.emit(round_job, out2, "--spec-version", OVERRIDE_VERSION)
        # This fixture carries two approvals with no `at` in any source it may read (packet.json,
        # inputs/custody.json, and inputs/custody-events.jsonl holds freeze/pin/dispose only), so at
        # 8590496 it exits 1 having written a record stamped "0.9.8" — the same exit 1 an override
        # cannot and must not fix. The version property is graded on the record, not on an exit code
        # that belongs to the approval times: the record must exist, carry the override, name the
        # override, and show no spec-version gap. A refusal (3) is still accepted and still graded by
        # the origin assertion below.
        self.assertIn(rc2, (0, 1, 3),
                      f"the round path returned {rc2}; 0 or 1 (the fixture's own approval-time gap) "
                      f"or 3 (refuse) are the only outcomes\n{text2[-1500:]}")
        if rc2 != 3:
            self.assertIsNotNone(record2,
                                 f"the round path exited {rc2} without refusing and wrote no record "
                                 f"to grade\n{text2[-1500:]}")
            self.assertNotIn(
                "spec-version", str([g.get("field") for g in
                                     ((record2.get("predicate") or {}).get("x-plumbline") or {}).get("gaps") or []]),
                "the round path under an override reports a spec-version gap: the override did not resolve it",
            )
        self.assertEqual(spec_of(record2), OVERRIDE_VERSION,
                         f"the round path stamped {spec_of(record2)!r} under an override of "
                         f"{OVERRIDE_VERSION!r}")
        self.assertEqual(version_block(record2).get("origin"), "--spec-version",
                         f"the round path must name the override as the origin; it says "
                         f"{version_block(record2).get('origin')!r}")

    # ---- 4 ---------------------------------------------------------------------------------------
    def test_the_override_does_not_collide_with_the_document(self):
        """REQ C1+C3 · baseline 8590496: was GREEN (a control): the record never silently picks between them. Historical label, not the verdict — see the ok/FAIL beside this line.

        Both are given and they disagree. The record must not carry a third value, must not be
        half-from-each, and must either follow the document or be refused naming the collision. At
        8590496 both routes are untaught, so the record says the literal — neither value — and that is
        why this case is green before the fix: it exists to catch a fix that lets the override quietly
        win over the document the job attests, or the document quietly win over an explicit flag.
        """
        reach_inputs_path(self.sp, "collide-reach")
        checkout = self.sp.document("custody-collide")
        job = self.sp.job(INPUTS_JOB_REL, "job-collide")
        add_custody_spec(job, str(checkout))
        out = self.sp.root / "collide.json"
        rc, text, record = self.sp.emit(job, out, "--spec-version", OVERRIDE_VERSION)

        if rc == 2:
            # The flag does not exist yet. Case 3 measures that; this case is a control and must not
            # count the same defect twice, so it can only observe what this program actually does.
            self.assertIsNone(record, "argparse refused the flag yet a record was written")
            return
        self.assertIn(rc, (0, 3), f"a collision is follow-the-document or refuse; rc={rc}\n{text[-1500:]}")
        if rc == 3:
            self.assertIsNone(record, "a refusal wrote a record")
            self.assertIn("spec-version", text, f"the refusal must name the field:\n{text[-1500:]}")
            return
        spec = spec_of(record)
        self.assertIn(spec, (DOC_VERSION, OVERRIDE_VERSION),
                      f"with the document at {DOC_VERSION!r} and the override at {OVERRIDE_VERSION!r} the "
                      f"record says {spec!r}: neither source, so a third answer")
        origin = version_block(record).get("origin")
        self.assertNotEqual(origin, "document",
                            f"the record says {spec!r} was read from the document; with an override in "
                            f"force the origin must say which one won ({origin!r})")
        if spec == OVERRIDE_VERSION:
            self.assertIn("override", str(origin).lower(),
                          f"the override won and the record does not say so: origin={origin!r}")

    # ---- 5 ---------------------------------------------------------------------------------------
    def test_every_published_verdict_is_byte_for_byte_unchanged(self):
        """REQ C4 · baseline 8590496: was GREEN (the control that matters: a measurement, not a promise). Historical label, not the verdict — see the ok/FAIL beside this line.

        Every stored custody/v1 record in the tree publishes what it published before, byte for byte:
        every `*.custody.json` file in the tree keeps the bytes it had. They do not all name one version —
        the fourteen predate the pin (0.9.6), later jobs file their own (0.9.8) — so what is measured is
        that no byte moves while the bar runs, and that `tools/pin.json` keeps naming the version it pins.
        History on disk is not the fix's to rewrite.
        """
        records = sorted(REPO.glob("**/*.custody.json"))
        if not records:
            die("no stored custody record in the tree: the corpus this control measures is gone")
        before = {str(p.relative_to(REPO)): p.read_bytes() for p in records}
        self.assertGreaterEqual(len(before), 14,
                                f"expected at least the fourteen stored records; found {len(before)}")
        for rel, data in before.items():
            picked = re.search(rb'"specVersion"\s*:\s*"([^"]+)"', data)
            self.assertIsNotNone(picked, f"{rel} publishes no specVersion")
            # What a record publishes is history, not this job's subject: the fourteen predate the pin
            # (0.9.6) and later jobs file their own (0.9.8). The property is that no byte of any of them
            # moves while the bar runs — measured below — not that they all name one version.
            self.assertRegex(picked.group(1).decode(), r"^\d+\.\d+\.\d+$",
                             f"{rel} publishes {picked.group(1).decode()!r}, which is not a version")

        # and a run of the bar's own cases moves none of those bytes
        after = {str(p.relative_to(REPO)): p.read_bytes() for p in sorted(REPO.glob("**/*.custody.json"))}
        self.assertEqual(sorted(after), sorted(before), "the set of stored records changed during the bar")
        moved = [rel for rel in before if before[rel] != after[rel]]
        self.assertEqual(moved, [], f"records whose bytes moved: {moved}")

        pin = json.loads((REPO / "tools" / "pin.json").read_text(encoding="utf-8"))
        self.assertEqual(pin.get("custody", {}).get("specVersion"), PINNED_SPEC_VERSION,
                         "tools/pin.json must keep naming the version it pins; the fix may not move the "
                         "pin to match a literal")

    # ---- 6 ---------------------------------------------------------------------------------------
    def test_the_bar_leaves_its_subject_clean(self):
        """PROCESS · baseline 8590496: was GREEN (a control): the bar writes nothing into its subject. Historical label, not the verdict — see the ok/FAIL beside this line.

        (a) the source tree is byte-for-byte in the state it was in before the bar ran (dirt the
        subject brought is the subject's; the bar adds none); (b) the committed
        copy is clean the moment it is committed (so a case cannot be reddened by the emitter's own
        revision refusal); (c) a planted file appears in (a)'s measurement — (a) can fail, which is
        what makes it a measurement.
        """
        status = _porcelain(REPO)
        added = [ln for ln in status.splitlines() if ln not in BAR_START.splitlines()]
        removed = [ln for ln in BAR_START.splitlines() if ln not in status.splitlines()]
        self.assertEqual(
            (added, removed), ([], []),
            "the bar changed the tree it was run from. `git status --porcelain` must be exactly what it "
            "was before the bar ran: the Maker's uncommitted work belongs to the subject, not to the "
            "instrument, and a control that reports the subject's dirt as the instrument's dirt cannot "
            "be satisfied by any correct fix.\n"
            f"added:\n{chr(10).join(added)[:1200]}\nremoved:\n{chr(10).join(removed)[:1200]}")

        stray = self.sp.clean_after_commit()
        self.assertEqual(stray, "",
                         f"the committed copy is not clean after its one commit — the mechanism every case "
                         f"depends on does not hold:\n{stray[:1500]}")

        probe = REPO / (".bar-probe-" + str(os.getpid()))
        try:
            probe.write_text("the bar's own measurement must be able to see a change\n", encoding="utf-8")
            planted = _porcelain(REPO)
        finally:
            try:
                probe.unlink()
            except OSError:
                pass
        self.assertIn(probe.name, planted,
                      "a file planted in the tree did not appear in `git status --porcelain`: the "
                      "measurement is not measuring")

    # ---- 7 ---------------------------------------------------------------------------------------
    def test_the_claim_about_the_emitter_survives_the_emitter_changing(self):
        """REQ C4/C5 · baseline 8590496: was GREEN (the claim exists and agrees there). Not a current verdict — see the ok/FAIL beside this line.

        The guard must not vanish when its subject moves. `tools/check_version_claims.py:70-76` emits
        a claim about `kit/emit_custody.py`'s stamped version ONLY IF the literal `SPEC_VERSION = "x.y.z"`
        is still in the file; the fix changes exactly that, so an untaught tool would drop the claim,
        print "5 claim(s), every one agrees with its pin" and exit 0. This case asserts four things:

          (a) a claim whose subject is the emitter's stamped version is still published — its label
              still names `kit/emit_custody.py`, whatever the form the fix chooses;
          (b) that claim still agrees with the pin's custody specVersion (the pin is frozen; a fix
              cannot make this true by moving it);
          (c) the total count is one of CLAIM_COUNTS_OK (6: the claim survives; 7: the fix added
              exactly one claim, and the added label is printed so the reason can be recorded);
          (d) THE PLANTED DISAGREEMENT: in a copy whose emitter stamps a different version, the claim
              still publishes (count unchanged) and this bar's reading of the tool's claim list says it
              LIES, naming both values, with the tool exiting non-zero.

        (c) is the part that cannot be satisfied by dropping the claim, which is the defect this
        programme keeps finding. (d) is the part that cannot be satisfied by a claim that ECHOES the
        pin without reading the emitter: such a claim publishes, agrees and counts, and (a)-(c) alone
        would call it green. The vanish bite — a disarming stand-in reading 5, exit 0 — was measured by
        the Architect and is recorded in this file's docstring under MEASURED BITE; (d) is not a story,
        it runs on every execution of this case.
        """
        tool = REPO / CLAIMS_TOOL_REL
        self.assertTrue(tool.is_file(), f"the editable set names {CLAIMS_TOOL_REL}, which is not in the "
                                        f"tree at {tool}")
        rc, text, listed = claims_report(REPO, tool)

        self.assertIsNotNone(listed,
                             f"{CLAIMS_TOOL_REL} could not be run or did not answer claims(REPO): a guard "
                             f"that cannot be read cannot be shown to hold. rc={rc}\n{text[-1500:]}")
        # The live tree must be a tree whose claims agree. The ONE exception is a disagreement about the
        # emitter: (d) at the end of this case CONSTRUCTS exactly that shape and grades the tool's answer
        # to it, so a tool that reports a non-zero exit here because the emitter disagrees with the pin
        # is graded there, by name and with its two values. Any other non-zero exit is red here.
        _agrees_live, _why_live = emitter_claim_verdict(listed)
        if not _agrees_live and "LIES" in _why_live:
            pass
        else:
            self.assertEqual(rc, 0,
                             f"{CLAIMS_TOOL_REL} must exit 0 on a tree whose claims all agree; "
                             f"rc={rc}. Reading of the claim list: {_why_live}\n{text[-1500:]}")

        pin = json.loads((REPO / "tools" / "pin.json").read_text(encoding="utf-8"))
        pinned = str(pin.get("custody", {}).get("specVersion", ""))
        self.assertTrue(pinned, "tools/pin.json carries no custody.specVersion for the claim to agree with")

        # (a) a claim about the emitter, whatever spelling the fix chose
        emitter_claims = [row for row in listed if EMITTER_HINT in str(row[0])]
        self.assertTrue(
            emitter_claims,
            f"{CLAIMS_TOOL_REL} published {len(listed)} claim(s) and NONE of them is about "
            f"{EMITTER_REL}. The claim about the emitter's stamped version has VANISHED: the tool "
            f"no longer compares the version the emitter stamps with the version the pin holds, and it "
            f"reports agreement over what is left. Claims seen: {[row[0] for row in listed]}",
        )

        # (a0) A CLAIM THAT LIES IS ITS OWN FAILURE, AND IT IS READ BEFORE THE AGREEMENT.

        # The disagreement must be reported HERE, not swallowed by (b)'s "nothing agrees with the pin":
        # a claim that is PRESENT and DISAGREES names two values, and a reader who is given a tuple dump
        # cannot tell it from a claim that never appeared. This branch is what the docstring's LIE
        # sentence describes, and it is measured: with `kit/emit_custody.py` stamping 0.9.5 and the tool
        # untouched, (b) used to fire first and print `Emitter claims seen: [...]` — the bar's
        # documentation promised a sentence the code never printed.
        #
        # The two controls that keep it honest:
        #   * it only fires when the claim EXISTS — a vanished claim falls through to (a) and (b), which
        #     say VANISHED, so an absent claim can never be reported as a LIE and the two are not swappable;
        #   * a claim about the emitter that is present and agrees is untouched, so this branch cannot
        #     redden a green tree. The verdicts at base are required to be identical: 3 red, 6 green.
        lying = [(str(row[0]), str(row[1]), str(row[2])) for row in emitter_claims
                 if str(row[1]) != str(row[2])]
        if lying:
            self.fail(
                f"the claim about {EMITTER_REL} LIES: "
                + "; ".join(f"{label} claims {claimed!r} while the pin holds {holds!r}"
                            for label, claimed, holds in lying)
                + f". The claim is PRESENT and DISAGREES with tools/pin.json's custody.specVersion — "
                  f"this is a lying claim, not a missing one: the tool publishes a value that "
                  f"contradicts the pin it is supposed to be checked against. {CLAIMS_TOOL_REL} must "
                  f"compare the version the emitter stamps with the version the pin holds, and report "
                  f"the disagreement."
            )

        # (b) the claim agrees with the pin
        agreeing = [row for row in emitter_claims if row[1] == row[2] and str(row[1]).strip()]
        self.assertTrue(
            agreeing,
            "no claim about the emitter's stamped version agrees with the pin's custody specVersion "
            f"({pinned!r}): the tool says the emitter stamps something else, or says nothing. "
            f"Emitter claims seen: {[(row[0], row[1], row[2]) for row in emitter_claims]}",
        )
        self.assertIn(
            "v" + pinned, [str(row[1]) for row in agreeing],
            f"the emitter's claim must still name the version the pin holds (v{pinned}); the agreeing "
            f"claim(s) name {[str(row[1]) for row in agreeing]}. A claim that agrees by naming some "
            f"other value proves nothing about this emitter.",
        )

        # (c) the count is asserted, never reported
        labels = [str(row[0]) for row in listed]
        self.assertIn(
            len(listed), CLAIM_COUNTS_OK,
            f"{CLAIMS_TOOL_REL} published {len(listed)} claim(s); this bar accepts "
            f"{CLAIM_COUNTS_OK[0]} (the claim survives in a new form) or {CLAIM_COUNTS_OK[1]} "
            f"({CLAIM_COUNT_SEVEN_REASON}). "
            + (f"{len(listed)} is the count the tool prints when the emitter claim has been silently "
               f"dropped — measured 2026-11-11 on a disarming stand-in. " if len(listed) < min(CLAIM_COUNTS_OK) else "")
            + f"Claims seen: {labels}",
        )
        if len(listed) == CLAIM_COUNTS_OK[1]:
            self.fail(
                f"count {len(listed)} is accepted only when the one ADDED claim is named here with its "
                f"reason, and this bar does not yet name it: claims are {labels}. Re-cut "
                f"CLAIM_COUNTS_OK on the bar with the added label, or return the tool to "
                f"{CLAIM_COUNTS_OK[0]} claims."
            )

        # (d) THE PLANTED DISAGREEMENT — the claim must go RED when it LIES, not only when it VANISHES.
        #
        # (a)-(c) above are satisfiable by a stub: a claim that echoes the pin's version without ever
        # reading the emitter publishes, agrees, and counts. The vanish probe this bar was measured on
        # (5 claims, not 6/7) catches only the claim that is DROPPED. This control constructs the other
        # shape: the emitter is edited to stamp PLANTED_EMITTER_VERSION, the tool is left untouched, so
        # the claim still publishes — and its value now disagrees with the pin. The tool must report it.
        planted = plant_emitter_disagreement(self.sp.tree, self.sp.root / "tree-disagreeing")
        tool_p = planted / CLAIMS_TOOL_REL
        self.assertTrue(tool_p.is_file(),
                        f"the copy of the tree the disagreement is planted in has no {CLAIMS_TOOL_REL}")
        rc_p, text_p, listed_p = claims_report(planted, tool_p)

        self.assertIsNotNone(
            listed_p,
            f"with the emitter stamping {PLANTED_EMITTER_VERSION!r} (the pin holds "
            f"{PINNED_SPEC_VERSION!r}) {CLAIMS_TOOL_REL} could not be read: a guard that cannot be read "
            f"cannot be shown to bite. rc={rc_p}\n{text_p[-1500:]}",
        )
        self.assertEqual(
            len(listed_p), len(listed),
            f"the disagreement control must hold the claim COUNT constant — it plants a disagreement, "
            f"not a disappearance. The live tree publishes {len(listed)} claim(s); with the emitter "
            f"stamping {PLANTED_EMITTER_VERSION!r} the tool published {len(listed_p)}. If the count "
            f"moved, this control is measuring a vanished claim, not a lying one. "
            f"Claims: {[str(r[0]) for r in listed_p]}",
        )
        agrees_p, why_p = emitter_claim_verdict(listed_p)
        self.assertFalse(
            agrees_p,
            f"PLANTED DISAGREEMENT NOT CAUGHT: with {EMITTER_REL} stamping {PLANTED_EMITTER_VERSION!r} "
            f"and tools/pin.json still holding custody.specVersion {PINNED_SPEC_VERSION!r}, the claim "
            f"about the emitter still reported agreement ({why_p!r}). The claim is DEFANGED: it "
            f"publishes and it agrees, so it is not reading the emitter — it is echoing the pin. A "
            f"claim that cannot go red on a planted disagreement is decorative.",
        )
        self.assertIn(
            "LIES", why_p,
            f"the disagreement control must distinguish a claim that LIES from a claim that VANISHED; "
            f"this one was read as {why_p!r}",
        )
        for value in (PLANTED_EMITTER_VERSION, PINNED_SPEC_VERSION):
            self.assertIn(
                value, why_p,
                f"the disagreement must be NAMED by its two values ({PLANTED_EMITTER_VERSION!r} the "
                f"emitter stamps, {PINNED_SPEC_VERSION!r} the pin holds); the reason reads {why_p!r}",
            )
        self.assertNotEqual(
            rc_p, 0,
            f"{CLAIMS_TOOL_REL} exited 0 on a tree where the emitter stamps {PLANTED_EMITTER_VERSION!r} "
            f"and the pin holds {PINNED_SPEC_VERSION!r}: the tool reported agreement over a claim that "
            f"disagrees with its pin.\n{text_p[-1500:]}",
        )

    # ---- 8 ---------------------------------------------------------------------------------------
    def test_the_claims_tool_selftest_runs_and_keeps_its_rule_set(self):
        """REQ C5 · baseline 8590496: was GREEN (the tool ships a passing selftest there, never run from the bar).

        `tools/check_version_claims.py --selftest` must run FROM THE BAR, exit 0, report every line
        `[PASS]`, and still exercise the four rules it exercises at 8590496:

            clean · wrong corpus dir · wrong custody commit · wrong custody version

        Naming them is the point. `tools/check_version_claims.py` is EDITABLE this job, so a case that
        graded only "exit 0" would let a Maker delete a rule from the selftest and still pass — measured
        2026-11-11: with `wrong custody version` deleted from a copy's `cases` dict, the selftest printed
        three [PASS] lines and exited 0. The rule set is the property, not the exit code.
        """
        self.assertTrue((REPO / CLAIMS_TOOL_REL).is_file(),
                        f"the editable set names {CLAIMS_TOOL_REL}, which is not in the tree")
        rc, text = selftest_report(REPO)
        seen = selftest_rules_seen(text)

        self.assertEqual(
            rc, 0,
            f"`{CLAIMS_TOOL_REL} --selftest` must exit 0 on a tree whose claims all agree; it exited "
            f"{rc}. A selftest that fails is a rule that does not plant its mismatch — the guard is not "
            f"guarding.\n{text[-2500:]}",
        )
        not_pass = {name: row["line"] for name, row in seen.items() if row["verdict"] != "PASS"}
        self.assertEqual(
            not_pass, {},
            f"every line `{CLAIMS_TOOL_REL} --selftest` reports must be [PASS]; these are not: {not_pass}. "
            f"Full output:\n{text[-2500:]}",
        )
        # And nothing may be reported that is neither a line this bar read nor a blank/`[PASS]` line:
        # a rule that printed in some other shape would be invisible to the count above.
        stray = [line for line in text.splitlines()
                 if line.strip() and "[PASS]" not in line and not re.search(r"selftest\s+.+?:\s*\d+\s+violation", line)]
        self.assertEqual(stray, [],
                         f"`{CLAIMS_TOOL_REL} --selftest` printed lines this case cannot read as a rule "
                         f"verdict: {stray}. A rule reported in an unknown shape is a rule this bar "
                         f"cannot pin.")

        missing = [rule for rule in SELFTEST_RULES_REQUIRED if rule not in seen]
        self.assertEqual(
            missing, [],
            f"DELETED SELFTEST RULE(S): {missing}. The rule {(missing or ['(none)'])[0]!r} is missing "
            f"from {CLAIMS_TOOL_REL} --selftest's output: the selftest no longer exercises it. "
            f"{CLAIMS_TOOL_REL} is editable this job, so a deleted rule is a way to pass: measured "
            f"2026-11-11, deleting `wrong custody version` from a copy's `cases` dict left three [PASS] "
            f"lines and exit 0, so a case that graded only the exit code would have passed. This bar "
            f"pins the rule set by name: {list(SELFTEST_RULES_REQUIRED)}. Rules seen: {sorted(seen)}",
        )

        # Each required rule must be one that can FAIL: its expected count must be non-zero, or the
        # rule is clean's shape (a positive control) and pins nothing. `clean` is the only such rule.
        for rule, row in seen.items():
            if rule == "clean":
                self.assertEqual(row["expected"], "0",
                                 f"the `clean` rule must expect 0 violations; it expects {row['expected']}")
            else:
                self.assertNotEqual(
                    row["expected"], "0",
                    f"the rule {rule!r} expects 0 violations, so it plants no mismatch: it is a rule "
                    f"that cannot fail and it pins nothing.",
                )

    # ---- 9 ---------------------------------------------------------------------------------------
    def test_a_deleted_selftest_rule_is_caught(self):
        """REQ C5 · baseline 8590496: was GREEN (the selftest ships whole there).

        The control for case 8, run here rather than recorded as a story: delete ONE rule from the
        selftest's own rule set in a copy of the tree, and case 8's measurement must go RED naming the
        deleted rule. This is what makes case 8 a guard instead of a restatement of exit 0.

        The edit is made to the COPY only; the tree the bar was run from is never written to (case 6).
        """
        target = SELFTEST_RULES_REQUIRED[1]        # a rule that must exist and must be able to fail
        self.assertNotEqual(target, "clean",
                            "the deleted-rule probe must delete a non-clean rule; deleting `clean` would "
                            "probe a different property")
        copy = self.sp.root / "tree-one-rule-short"
        shutil.copytree(self.sp.tree, copy, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
        tool = copy / CLAIMS_TOOL_REL
        source = tool.read_text(encoding="utf-8")

        # Remove the rule's entry from the `cases = {...}` literal, entry by entry, by its key.
        lines, kept, removing, removed = source.splitlines(keepends=True), [], False, []
        for line in lines:
            key = re.match(r'^\s*"([^"]+)":\s*\(', line)
            if key and key.group(1) == target:
                removing = True
            if removing:
                removed.append(line.rstrip())
                if line.strip().endswith("),"):
                    removing = False
                continue
            kept.append(line)
        self.assertTrue(removed,
                        f"could not find the rule {target!r} in {CLAIMS_TOOL_REL}'s selftest to delete; "
                        f"the deleted-rule probe cannot run")
        self.assertNotIn(f'"{target}":', "".join(kept),
                         f"the probe failed to delete {target!r} from the copy")
        tool.write_text("".join(kept), encoding="utf-8")

        rc, text = selftest_report(copy)
        seen = selftest_rules_seen(text)
        missing = [rule for rule in SELFTEST_RULES_REQUIRED if rule not in seen]
        self.assertIn(
            target, missing,
            f"with the rule {target!r} deleted from {CLAIMS_TOOL_REL}'s selftest, this bar's rule set "
            f"did not notice: it is still sending nothing red about {target!r}. Rules seen: "
            f"{sorted(seen)}. Output:\n{text[-2500:]}",
        )
        # The name reaches the assertion, and so does the exit code the deleted rule did not move.
        self.assertEqual(
            rc, 0,
            f"the deleted-rule probe is only meaningful while the selftest still EXITS 0 with a rule "
            f"missing — that is the hole case 8 closes. Here it exited {rc}, so this probe is measuring "
            f"something else.\n{text[-1500:]}",
        )


def main() -> int:
    if sys.version_info < (3, 10):
        die(f"python {sys.version.split()[0]} cannot run this bar (shutil.copytree(ignore=...) and "
            f"Path.glob semantics the bar relies on need >= 3.10)")
    if shutil.which("git") is None:
        die("git is not on PATH: the emitter records its own revision and refuses without one")
    print("bar emit_spec_version: subject %s at %s" % (EMITTER_REL, REPO))
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EmitterResolvesSpecVersion)
    ids = [t._testMethodName for t in suite]
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    failed = len(result.failures) + len(result.errors)
    print(f"bar emit_spec_version: ran {result.testsRun} case(s), failed {failed}; case ids: {', '.join(ids)}")
    if failed:
        print("bar emit_spec_version: RED")
        return 2 if result.errors else 1
    print("bar emit_spec_version: GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
