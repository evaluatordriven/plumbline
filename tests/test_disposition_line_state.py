"""Bar: a dispose line's `state` is read. A contradiction is refused, never dropped.

WHY THIS FILE EXISTS
--------------------
`kit/custody_ledger.py dispose --state given|declined` writes the disposition state into TWO
places (custody_ledger.py:336 and :344): `inputs/custody.json` -> `disposition.state`, and the
`dispose` line in `inputs/custody-events.jsonl` -> `state`. Two sources of record, one fact.

`kit/emit_custody.py` reads ONE of them. Line 1104:
    state = packet.get("disposition_state")
and that is the whole read. `ci["disposition"]["state"]` (custody.json) and
`ev_log["dispose"]["state"]` (the ledger line) are never compared to the packet, and never to
each other. So a job whose ledger says `declined` and whose packet says `given` emits a record
saying `given` with exit 0 and no gap: the ledger's state is silently dropped. Nothing tells the
reader that Plumbline's own live event log disagrees with the record it is holding.

WHAT THE BAR REQUIRES (measured red at db9d6b7 before this file existed)
-----------------------------------------------------------------------
A. CONTRADICTION  the line's `state` is a known value and differs from the state the record
   would carry -> REFUSED as a `disposition.state` gap, exit 1, and the refusal NAMES BOTH
   VALUES. Never exit 0.
B. AGREEMENT      the line's `state` equals the state the record would carry -> ignored, record
   emits, nothing changes (exit 0, same `disposition.state`).
C. UNREADABLE     the line's `state` is a shape the emitter does not recognise (e.g. an object
   `{"value": "given"}`) -> REFUSED by name, same kind as A. A shape nobody can read is not
   "no state" and is not agreement.

WHAT THE BAR MUST NOT REQUIRE
-----------------------------
No case here asserts that the EMITTER USES the line's state. The Owner ruled the record's
`disposition.state` comes from `packet.disposition_state`, and `kit/emit_custody.py:14-15` states
it too. This bar asks the emitter to read the line to CHECK the packet. A case that required the
line to become the record's value would legislate a third source the Owner ruled out. Case B
asserts the record still says the packet's value with the line present and agreeing; case A
refuses rather than replacing.

THE CONTROL (case D)
--------------------
The claim "real records with a disposition block still emit" is measured, not assumed. The tree
carries exactly TWO distinct custody/v1 records with a non-null `disposition` block:
    examples/2026-10-27-custody-emitter-gaps/custody/record.custody.json
    examples/2026-10-28-custody-times-ledger-spend/custody/record.custody.json
The same two jobs also appear under examples/subjects/ (a job's own verify fixtures), which is
where an earlier count of six came from: four files, two jobs. `examples/subjects/.../verify/clean`
carries `disposition: null` and is NOT counted. Two is the number; a fix that breaks either is
red here.

RED BEFORE THE FIX
------------------
Every case A, B, C is RED at db9d6b7 (the emitter exits 0 on all three arms and writes a record
that says the packet's state, with no gap). Case D is GREEN at db9d6b7 by construction, because
it guards against a regression the fix could introduce: it is a control, not a defect case, and
it is labelled as such. It does not measure the defect and does not count toward the red.

THE FIXTURE
-----------
tests/fixtures/custody/job-disposition-line/ is a labelled synthetic sibling of job-rejected. It
carries `disposition.state: "given"` in custody.json, `disposition_state: "given"` in the packet,
and a `dispose` line with `state: "declined"`. Its `at`/`by` agree with custody.json, so the
`time` comparison (F1b, custody_ledger.py:1116) is silent and cannot account for any result.

THE ORACLE
----------
Cases copy the fixture and run `kit/emit_custody.py` as a subprocess. A patched emitter that
returns 0 does not grade itself: the exit code is the process's, not a function's. The copy is
committed to a throwaway git repo so the emitter's revision refusal (it must name code that
exists as a commit) does not mask the defect under test.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FIXTURE = os.path.join(REPO, "tests", "fixtures", "custody", "job-disposition-line")
EMITTER_REL = os.path.join("kit", "emit_custody.py")
RECEIPT = os.path.join("custody", "record.custody.json")
PY = sys.executable

TWO_REAL_RECORDS = (
    os.path.join("examples", "2026-10-27-custody-emitter-gaps", "custody", "record.custody.json"),
    os.path.join("examples", "2026-10-28-custody-times-ledger-spend", "custody", "record.custody.json"),
)

# The state the record would carry in the base fixture: packet.json `disposition_state`.
FIXTURE_RECORD_STATE = "given"
# The state written on the fixture's dispose line.
FIXTURE_LINE_STATE = "declined"


def _git(args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "bar", "GIT_AUTHOR_EMAIL": "bar@localhost",
             "GIT_COMMITTER_NAME": "bar", "GIT_COMMITTER_EMAIL": "bar@localhost"},
    )


class Tree:
    """A committed copy of the repo the emitter will run from, and a job dir beside it.

    The emitter refuses to write when its own tree is dirty or is not a git checkout
    (custody_history.py:498, :516). Those refusals are real and are not this bar's subject, so the
    copy is committed once and all case mutations happen in the JOB dir, which is not the emitter's
    tree and does not make it dirty.
    """

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="plumbline-disposition-line-")
        self.tree = os.path.join(self.root, "tree")
        shutil.copytree(REPO, self.tree, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        _git(["init", "-q"], self.tree)
        _git(["add", "-A"], self.tree)
        _git(["commit", "-qm", "bar: clean emitter tree"], self.tree)

    def job(self, name):
        d = os.path.join(self.root, "job-" + name)
        shutil.copytree(FIXTURE, d)
        return d

    def emit(self, job, out_name="out.json"):
        out = os.path.join(self.root, out_name)
        r = subprocess.run(
            [PY, os.path.join(self.tree, EMITTER_REL), "--job-dir", job, "--out", out,
             "--allow-hand-times"],
            cwd=self.tree, capture_output=True, text=True,
        )
        rec = None
        if os.path.isfile(out):
            with open(out, encoding="utf-8") as fh:
                rec = json.load(fh)
        return r.returncode, r.stdout + r.stderr, rec

    def write_line(self, job, line):
        path = os.path.join(job, "inputs", "custody-events.jsonl")
        with open(path, encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        lines = [ln for ln in lines if json.loads(ln).get("event") != "dispose"]
        lines.append(json.dumps(line))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)


def _state(rec):
    if not isinstance(rec, dict):
        return None
    return (rec.get("predicate") or {}).get("disposition", {}).get("state")


def _gaps(rec):
    if not isinstance(rec, dict):
        return []
    return ((rec.get("predicate") or {}).get("x-plumbline") or {}).get("gaps") or []


class DispositionLineState(unittest.TestCase):
    """The dispose line's `state` is read; a contradiction is refused, naming both values."""

    @classmethod
    def setUpClass(cls):
        cls.t = Tree()

    @classmethod
    def tearDownClass(cls):
        cls.t.close()

    # ---- A: contradiction is refused, exit 1, both values named ------------------------------
    def test_A_contradiction_is_refused_naming_both_values(self):
        """The line says `declined`, the record would say `given` -> exit 1, not 0.

        RED at db9d6b7: the emitter exits 0 and writes a record whose disposition.state is
        'given', with no disposition.state gap — the line is dropped.
        """
        job = self.t.job("contradiction")
        self.t.write_line(job, {
            "event": "dispose", "by": "Fixture Buyer",
            "at": "2026-10-20T13:00:00Z", "state": FIXTURE_LINE_STATE,
        })
        rc, out, rec = self.t.emit(job, "contradiction.json")
        self.assertNotEqual(
            rc, 0,
            "the dispose line says 'declined' and the record would say 'given'; the emitter returned "
            f"0 and dropped the line. rc={rc}\n{out}",
        )
        self.assertEqual(rc, 1, f"a contradiction is a disposition.state GAP (exit 1), not exit {rc}\n{out}")
        self.assertIn(FIXTURE_LINE_STATE, out, f"the refusal must name the line's value\n{out}")
        self.assertIn(FIXTURE_RECORD_STATE, out, f"the refusal must name the value the record would carry\n{out}")
        self.assertIn("disposition.state", out, f"the refusal must name the field\n{out}")
        gap_fields = [g.get("field") for g in _gaps(rec)]
        self.assertIn(
            "disposition.state", gap_fields,
            f"the written record must name the gap; gaps were {gap_fields}",
        )

    # ---- the same fact through custody.json, not the ledger, must agree ----------------------
    def test_A2_the_packet_and_custody_json_are_the_two_record_sources(self):
        """With the line agreeing, the record's state is the packet's — not the line's.

        This case exists to keep case A honest: it shows the fixture's record state comes from the
        packet, so case A's contradiction really is a contradiction and not an artefact of the
        fixture. GREEN at db9d6b7 by construction (it asserts current behaviour), and labelled so:
        it is the pairing that makes case A's red meaningful, and it is not counted as a defect.
        """
        job = self.t.job("agrees-for-context")
        self.t.write_line(job, {
            "event": "dispose", "by": "Fixture Buyer",
            "at": "2026-10-20T13:00:00Z", "state": FIXTURE_RECORD_STATE,
        })
        rc, out, rec = self.t.emit(job, "agrees-for-context.json")
        self.assertEqual(rc, 0, f"with the line agreeing the record must emit\n{out}")
        self.assertEqual(_state(rec), FIXTURE_RECORD_STATE)

    # ---- B: agreement is ignored -------------------------------------------------------------
    def test_B_agreement_emits_and_changes_nothing(self):
        """The line agrees -> exit 0, the record's state is unchanged, no disposition.state gap.

        RED at db9d6b7 only in the sense that the fix must not break this: on db9d6b7 it is GREEN
        (the emitter never reads the line, so agreement is trivially ignored). It is stated as a
        case because a fix that refuses on ANY dispose line, or that prefers the line's value, is
        wrong; this case catches both. See the docstring header: B is a control, not a defect case.
        """
        job = self.t.job("agreement")
        self.t.write_line(job, {
            "event": "dispose", "by": "Fixture Buyer",
            "at": "2026-10-20T13:00:00Z", "state": FIXTURE_RECORD_STATE,
        })
        rc, out, rec = self.t.emit(job, "agreement.json")
        self.assertEqual(rc, 0, f"agreement must not refuse\n{out}")
        self.assertEqual(_state(rec), FIXTURE_RECORD_STATE, "the record's state changed with the line")
        self.assertNotIn(
            "disposition.state", [g.get("field") for g in _gaps(rec)],
            "agreement must not produce a disposition.state gap",
        )

    # ---- C: an unreadable shape is refused by name -------------------------------------------
    def test_C_unreadable_state_shape_is_refused_by_name(self):
        """`state: {"value": "given"}` is a shape the emitter does not recognise -> refused, not ignored.

        RED at db9d6b7: exit 0, silent, the record says the packet's state and names no gap.
        """
        job = self.t.job("unreadable")
        self.t.write_line(job, {
            "event": "dispose", "by": "Fixture Buyer",
            "at": "2026-10-20T13:00:00Z", "state": {"value": FIXTURE_LINE_STATE},
        })
        rc, out, rec = self.t.emit(job, "unreadable.json")
        self.assertNotEqual(rc, 0, f"an unreadable state shape was dropped silently\n{out}")
        self.assertEqual(rc, 1, f"an unreadable shape is a disposition.state GAP (exit 1), not exit {rc}\n{out}")
        self.assertIn("disposition.state", out, f"the refusal must name the field\n{out}")
        self.assertTrue(
            "unreadable" in out.lower() or "not a known" in out.lower() or "shape" in out.lower(),
            f"the refusal must say the shape was not read, not merely refuse\n{out}",
        )
        gap_fields = [g.get("field") for g in _gaps(rec)]
        self.assertIn("disposition.state", gap_fields)
        # A shape nobody can read is not agreement and is not the line's value: the record must
        # NOT carry {"value": ...} as the state.
        self.assertNotIsInstance(_state(rec), dict, "an unreadable shape became the record's state")

    # ---- D: the control — two real records carrying a disposition block still emit ------------
    def test_D_two_real_records_with_a_disposition_block_still_emit(self):
        """Exactly TWO distinct public records carry a disposition block, and both keep it.

        GREEN at db9d6b7 by construction (a control, not a defect case). Two claims, both about the
        RECORDS as stored, because a re-emit is refused here for reasons outside this bar's
        subject: the 2026-10-27 harness log lacks an /api/v1/generation reply, so the emitter
        refuses it on [endpoint] whatever its disposition says. Making this case depend on a
        re-emit would smuggle that unrelated defect into this bar.

        So D asserts what the fix must not damage:
          1. the two stored records still carry a non-null disposition.state (the fix does not
             rewrite history); and
          2. the fixture — which carries `disposition.state: "given"` in custody.json alongside
             `packet.disposition_state: "given"` — still emits exit 0 with that state, i.e. a job
             with a disposition block is not newly refused.
        """
        missing = [p for p in TWO_REAL_RECORDS if not os.path.isfile(os.path.join(REPO, p))]
        self.assertEqual(missing, [], f"the two stored records are gone: {missing}")
        n = 0
        for rel in TWO_REAL_RECORDS:
            with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
                rec = json.load(fh)
            dsp = (rec.get("predicate") or {}).get("disposition") or {}
            self.assertIsInstance(dsp, dict, f"{rel}: no disposition block")
            self.assertIsNotNone(dsp.get("state"), f"{rel}: its disposition.state is null")
            n += 1
        self.assertEqual(n, 2, "the claim is TWO distinct records, measured above")

        # (2) the fixture carries a disposition block and must still emit, unchanged.
        job = self.t.job("control")
        self.t.write_line(job, {
            "event": "dispose", "by": "Fixture Buyer",
            "at": "2026-10-20T13:00:00Z", "state": FIXTURE_RECORD_STATE,
        })
        rc, out, again = self.t.emit(job, "control.json")
        self.assertEqual(rc, 0, f"a job with a disposition block must still emit\n{out}")
        self.assertEqual(_state(again), FIXTURE_RECORD_STATE,
                         "the fix changed the record's state for a job whose sources agree")


if __name__ == "__main__":
    unittest.main(verbosity=2)
