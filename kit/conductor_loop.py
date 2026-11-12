"""The mechanical half of the Orchestrator: rounds, the pass rule, the record.

This is not the conductor. It dispatches one turn at a time by calling
kit.conductor_run.run. It does not score, diagnose, or decide. It sends
nothing and never restarts a stopped job. The conductor is still unbuilt.

Every round record this module writes carries wall-clock stamps, taken from
the local zone and spelled as ISO 8601 at second precision with a numeric
offset. ``started_at`` is taken once, when ``loop()`` is entered, before the
packet is loaded; each written round record carries its own ``started_at`` at
the top of its round and an ``ended_at`` taken when that record is written,
inside the job window and in order across rounds.

A finish is written by this module or not written at all. ``loop()`` writes
``summary.json`` with what the finish says and, for a stop a human must see,
``escalation.json`` beside it, and returns the summary. It raises
``CustodyNotDone`` for the one finish it cannot write cleanly: a run
whose clock was replaced took stamps that are not this module's readings.
``datetime`` is the clock seam, so a replaced clock is visible here; nothing
replaces it in a real run, so a real finish is always filed. ``CustodyNotDone``
is an ``Exception`` and never a ``ValueError``, and its ``exit_code`` is 1, 2
or 3 and never 0. A packet refusal is not a finish: it raises ``ValueError``
and writes ``escalation.json`` with ``started_at`` and ``refused_at``, a later
reading of the same clock, and no ``ended_at``. Nothing reads these fields
back: the deadline and the clock stop stay on the monotonic clock, so a
wall-clock jump changes no stop, state, outcome or round count.

Before any Maker turn, ``loop()`` freezes the bar in the ledger, but only when
the job has signalled that it is custody-bearing. It does so right after the
packet is loaded and validated and before the first Maker dispatch: the bar is
``bar.file`` from ``<job>/inputs/custody.json``, read from the same relative
path under the workspace, or, when nothing is declared, the convention file
``<cwd>/custody/bar.md``. It copies that bar into the job directory unchanged
and runs ``kit/custody_ledger.py freeze`` against the job directory, so the
tool stamps its own clock and appends the event to
``inputs/custody-events.jsonl``. ``loop()`` types no ``frozenAt`` value. A job
that prepared neither signal is not refused: nothing is frozen. A
custody-bearing job that names no bar and has no convention bar also fails
closed, because the presence of ``inputs/custody.json`` removes the skip path.
If a named or selected bar cannot be read, or the tool refuses, ``loop()``
raises before the Maker command runs and never calls the emitter.

A finish also has to ship a custody record. ``loop()`` calls
``emit_custody_for_finish(record_dir, summary)`` once, after the round records
and a ``packet.json`` describing the finish exist and before ``summary.json``
or ``escalation.json`` is written. The seam runs ``kit/emit_custody.py`` against
``record_dir`` and returns the emitter's exit code; 0 means the record at
``record_dir/custody/record.custody.json`` was written and names no hard gap.
Any other code is not a done finish: ``loop()`` raises ``CustodyNotDone`` with
that code and writes neither ``summary.json`` nor ``escalation.json``. A packet
refusal is not a finish: the seam is not called and no custody record is
written.

The version the record attests is not typed anywhere. The seam reads the custody
commit and the version that commit's SPEC.md declares from the kit's own
``tools/pin.json``, finds a checkout of that commit on this machine, and names
it in ``inputs/custody.json`` as ``custody_spec`` — the field the emitter already
reads. The emitter itself is unchanged and gains no flag, so the seam's exit
code is still exactly ``emit_custody.py --job-dir J``'s. With no pin, or no
checkout at the pinned commit, nothing is supplied and the emitter's own
``spec-version`` refusal stands.

A clean finish is then closed and filed by ``file_finish(record_dir, halt)``,
the last act of ``loop()``: it writes ``custody/status.json`` into the job
folder (``custody`` or ``missing``, with the record's sha256 and the terminal
state), and copies the folder into ``$PLUMBLINE_FILE_INTO`` — the instance's
``dot-plumbline`` — through ``plumbline_job.file``. A finish whose packet
carries a ``job_id`` is filed under ``jobs/<job_id>``; one that carries none
is the evidence of a run and lands under ``runs/``, because a folder under
``jobs/`` with no id is a job no reader can name. It raises nothing: an
accepted artifact must not be undone by a filing defect, so the outcome lands
in ``summary.json`` as ``filing`` with ``state``, ``filed``, ``dest`` and the
command's own words. With the variable unset the status file is still written
and ``filed`` is false with the reason, never a silent skip. The destination is
configuration rather than an argument because a parameter a caller must
remember is the same defect as remembering to close.
"""
from __future__ import annotations

import sys as _sys

# The loop imports the tree's own modules (tools/build_schemas, tools/edi_corpus) while
# it measures that tree. CPython writes a ``__pycache__/*.pyc`` for each import, the
# snapshot sees new files outside the editable set, and a correct repair is refused as
# an edit outside it. Measured 2026-11-10, Job 32 record-7: three ``kit/*.cpython-311.pyc``
# files written by THIS process. The instrument may not write into its own subject.
_sys.dont_write_bytecode = True

import argparse
import contextlib
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
from datetime import datetime as _datetime
from datetime import timezone

from kit import conductor_software
from kit.conductor_run import _bar_env, _run, run

ACCEPTED = "accepted"
REJECTED = "rejected"
NO_ARTIFACT = "no artifact"
EVALUATOR_FAILED = "evaluator failed"
NO_OBSERVATION = "no observation"
INSTRUMENT_FAILED = "instrument failed"
EVALUATOR_SPLIT = "evaluator split"
SCORING_SET = "scoring set"
CAP_REACHED = "cap reached"
ESCALATION_CLASS = "escalation class"
TAMPERED = "tampered"
MAKER_FAILED = "maker failed"
TIMEOUT_STOP = "timeout"
CLOCK = "clock"
BUDGET = "budget"
BUDGET_UNMEASURED = "budget unmeasured"
HELD_OUT = "held-out leak"
HELD_OUT_UNREADABLE = "held-out unreadable"
NOT_DISPATCHED = "not dispatched"
PACKET_REFUSED = "packet refused"

_STATES = {
    ACCEPTED: ("accepted", "accepted"),
    REJECTED: ("rejected", "rejected"),
    NO_ARTIFACT: ("needs_owner", "no_artifact"),
    EVALUATOR_FAILED: ("needs_owner", "no_observation"),
    NO_OBSERVATION: ("needs_owner", "no_observation"),
    INSTRUMENT_FAILED: ("needs_owner", "no_observation"),
    EVALUATOR_SPLIT: ("needs_owner", "no_observation"),
    SCORING_SET: ("needs_owner", "needs_owner"),
    CAP_REACHED: ("needs_owner", "needs_owner"),
    ESCALATION_CLASS: ("needs_owner", "needs_owner"),
    TAMPERED: ("needs_owner", "needs_owner"),
    MAKER_FAILED: ("needs_owner", "needs_owner"),
    TIMEOUT_STOP: ("needs_owner", "needs_owner"),
    CLOCK: ("needs_owner", "needs_owner"),
    BUDGET: ("needs_owner", "needs_owner"),
    BUDGET_UNMEASURED: ("needs_owner", "needs_owner"),
    HELD_OUT: ("needs_owner", "needs_owner"),
    HELD_OUT_UNREADABLE: ("needs_owner", "needs_owner"),
    NOT_DISPATCHED: ("needs_owner", "needs_owner"),
    PACKET_REFUSED: ("needs_owner", "needs_owner"),
}

_KINDS = {
    CAP_REACHED: "cap_reached",
    REJECTED: "below_floor",
}

_CLASSES = {
    "artifact_missed_standard",
    "standard_moved",
    "dimension_unauthorized",
    "frame_at_fault",
}
_VERDICTS = {"accept", "regenerate", "needs_owner", "reject"}
_HELD_METHOD = (
    "line and sha256 scan: each held-out file's sha256 hex digest, and each of its lines (bytes decoded as UTF-8, "
    "undecodable bytes replaced) that has an alphanumeric character, searched verbatim as a substring of the "
    "findings text; a line with no alphanumeric character is skipped; a path that cannot be opened and read "
    "fails the check"
)
_GAP_GATE = (
    "The gate rerun is a script Evaluator reading held in the same module as "
    "Orchestrator dispatch (DOCTRINE D3.holder, rule 5)."
)
_GAP_ARCH = (
    "Architect proposed packet not recorded after seeing drafts "
    "(D3.Architect vs Contracts §4.2); Owner ratification required"
)


class datetime(_datetime):
    """The module's clock seam: tests replace ``datetime.now`` on this name.

    ``datetime.datetime`` is an immutable C type, so ``now`` cannot be replaced
    on it; a subclass of it can be, and answers exactly as the base class does
    when it is not replaced.
    """


class CustodyNotDone(Exception):
    """A finish this module does not file. Exit 0 is the only done.

    ``loop()`` raises this instead of returning a summary for a finish whose
    stamps are not its own readings, or whose custody record the emitter could
    not write cleanly. ``exit_code`` is 1, 2 or 3 and is never 0: 1 the work was
    accepted; 2 the work was rejected, below the floor; 3 every stop a human
    must see. It files neither ``summary.json`` nor ``escalation.json``. It is
    not a ``ValueError``: a packet refusal stays one, because a refusal is not a
    finish.

    ``halt`` carries what the record would have said — the stop, its terminal
    state and outcome, the stamps, the rounds, the cap, the best round, the
    spend, the separation gaps and the hashes.
    """

    def __init__(self, halt, exit_code):
        super().__init__(
            "%s is not done (%s / %s) after %s of cap %s rounds, best round %s, "
            "cost %s; no summary and no escalation are filed"
            % (
                halt["stop"], halt["terminal_state"], halt["outcome"],
                halt["rounds"], halt["cap"], halt["best_round"], halt["cost"],
            )
        )
        self.halt = halt
        self.stop = halt["stop"]
        self.exit_code = exit_code


def _exit_code(stop) -> int:
    """1, 2 or 3 for a finish this module does not file. Never 0.

    1 — the work was accepted. 2 — the work was rejected, below the floor. 3 —
    a human must see the finish: every other stop. The exit code names what a
    caller would have had to route on; it is not a state and it is not a
    verdict.
    """
    if stop == ACCEPTED:
        return 1
    if stop == REJECTED:
        return 2
    return 3


def _own_clock() -> bool:
    """True while ``datetime.now`` is this module's clock and not a replacement.

    ``datetime`` is the clock seam. A run that replaces ``now`` on it supplies
    every ``started_at`` and ``ended_at`` the round records and the finish
    carry, so those stamps are not readings this module took, and a finish
    resting on them cannot be filed cleanly: ``loop()`` raises
    ``CustodyNotDone`` for it. Nothing replaces the clock in a real run, so a
    real finish is always filed.

    An unpatched ``now`` is inherited from the base class and is bound to this
    class; a replacement lives in this class's own namespace (or is bound to
    the object that supplies it).
    """
    if "now" in datetime.__dict__:
        return False
    return getattr(datetime.now, "__self__", None) is datetime


_PIN_FILE = os.path.join("tools", "pin.json")


def _pinned_custody():
    """``custody`` from the kit's own ``tools/pin.json``, or None when it cannot be read.

    ``commit`` and ``specVersion`` are READ from the pin and never typed here:
    ``tools/build_schemas.py --custody`` derives ``specVersion`` from the ``**Version X.Y.Z**``
    header of the SPEC.md at that commit, so a re-pin cannot leave the version behind (the
    failure that derivation exists to prevent, measured 2026-11-10). A pin that cannot be read
    is not a licence to guess a version: the seam then names no document and the emitter
    refuses for itself, which is the refusal this seam must not paper over.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        with open(os.path.join(root, _PIN_FILE), encoding="utf-8") as handle:
            body = json.load(handle)
    except (OSError, ValueError):
        return None
    custody = body.get("custody") if isinstance(body, dict) else None
    if not isinstance(custody, dict):
        return None
    commit = custody.get("commit")
    version = custody.get("specVersion")
    if not (isinstance(commit, str) and commit.strip()):
        return None
    if not (isinstance(version, str) and version.strip()):
        return None
    files = custody.get("files") if isinstance(custody.get("files"), dict) else {}
    spec = files.get("SPEC.md")
    return {
        "root": root,
        "commit": commit.strip(),
        "version": version.strip(),
        "spec_sha256": spec if isinstance(spec, str) else None,
    }


def _git_head(path):
    """The commit a checkout's work tree is at, or None when it is not a readable checkout."""
    try:
        proc = subprocess.run(
            ["git", "-C", path, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip() or None


def _custody_checkout(pin):
    """A custody checkout that IS the pinned document, or None.

    Looked for where the pin can be honoured: ``$PLUMBLINE_CUSTODY``, a ``custody/`` beside this
    repo, then one inside it — the places the seat already looks, so no path is typed here and
    the convention is not overridden by a guess.

    The document's own bytes are the AUTHORITY: a checkout whose ``SPEC.md`` hashes to the digest
    the pin records IS the document the job attests, whether or not ``git`` can be asked about it.
    A ``git`` that answers nothing must not veto a correct document — a checkout on a runner the
    seat does not own, or one archived without its history, is still the pinned bytes — so a
    silent HEAD is tolerated. The commit is BELT-AND-BRACES: a ``git`` that answers with another
    commit is evidence the work tree is at the wrong revision, and the checkout is refused. A
    checkout whose digest does not match is refused outright, so tolerating a silent git never
    becomes tolerating bytes that are not the document. Nothing is derived from the pin when no
    checkout matches.
    """
    candidates = []
    env = (os.environ.get("PLUMBLINE_CUSTODY") or "").strip()
    if env:
        candidates.append(env)
    candidates.append(os.path.join(os.path.dirname(pin["root"]), "custody"))
    candidates.append(os.path.join(pin["root"], "custody"))
    for candidate in candidates:
        checkout = os.path.abspath(os.path.expanduser(candidate))
        spec = os.path.join(checkout, "SPEC.md")
        if not os.path.isfile(spec):
            continue
        try:
            digest = _sha_file(spec)
        except OSError:
            continue
        if pin["spec_sha256"] and digest != pin["spec_sha256"]:
            continue
        head = _git_head(checkout)
        if head is not None and head != pin["commit"]:
            continue
        return checkout
    return None


def _supply_custody_document(record_dir, checkout):
    """Name the pinned custody document in the job's custody inputs.

    ``kit/emit_custody.py`` reads ``inputs/custody.json: custody_spec`` to resolve the version
    the record attests, so the seam supplies exactly that key and merges the rest of the file
    untouched. A job that already names its own document keeps it: the seat that wrote the
    inputs made a choice, and overriding it would attest a document the job did not name. A file
    that cannot be parsed is left as it is — it is not this seam's to rewrite, and the emitter
    names the refusal.
    """
    path = os.path.join(str(record_dir), "inputs", "custody.json")
    body = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                loaded = json.load(handle)
        except (OSError, ValueError):
            return
        if not isinstance(loaded, dict):
            return
        body = loaded
        named = body.get("custody_spec")
        if isinstance(named, str) and named.strip():
            return
    body["custody_spec"] = checkout
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(body, handle, indent=2, sort_keys=True)
        handle.write("\n")


def emit_custody_for_finish(record_dir, summary):
    """Run ``kit/emit_custody.py`` against ``record_dir``; return its exit code.

    This is the seam ``loop()`` uses to ship a custody record on a finish. It
    calls the emitter, not the close command; the emitter reads the job
    directory on disk — ``packet.json`` and the round records ``loop()`` has
    written — and writes ``custody/record.custody.json`` at the path the close
    command uses. Exit 0 is the only done: the record was written and names no
    hard gap. Any other exit code is not a done finish.

    It supplies the record's version before it runs. The emitter refuses a
    record whose ``predicate.specVersion`` has no source, and it will not fall
    back to a flag or to a literal; so this seam names the custody document the
    job attests. ``tools/pin.json`` records the custody commit and the version
    its SPEC.md declares, a checkout of that commit is found on this machine,
    and the job's ``inputs/custody.json`` carries it as ``custody_spec`` — the
    field the emitter already reads. The version is therefore read from the pin
    and the document, never typed in this module, and the emitter runs
    unchanged: no flag is added, so this seam's exit code is still exactly what
    ``emit_custody.py --job-dir J`` produces on the same directory. With no pin,
    or no checkout at the pinned commit, nothing is supplied and the emitter's
    own refusal stands.

    ``summary`` is carried for the caller's convenience; it is not forwarded.
    """
    emitter = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emit_custody.py")
    pin = _pinned_custody()
    if pin is not None:
        checkout = _custody_checkout(pin)
        if checkout is not None:
            _supply_custody_document(record_dir, checkout)
    proc = subprocess.run(
        [sys.executable, emitter, "--job-dir", str(record_dir)],
        capture_output=True,
        text=True,
    )
    return proc.returncode


def _custody_packet(packet, halt, job_id=None):
    """The ``packet.json`` a finish leaves for the emitter to read.

    The emitter reads the finish out of the job directory, so before the seam is
    called this module records what the finish says. Because the emitter never
    sees ``summary.json`` (that file is written only after a clean record), the
    finish has to be reachable from ``packet.json`` alone: its fields are
    written at the top level in the same snake_case the round records and the
    escalation use, again in the camelCase the record's gap vocabulary uses
    (``startedAt``, ``endedAt``), and nested under ``finish``/``summary`` so a
    reader that expects the summary as an object finds it. The ratified packet's
    own fields are kept alongside so the record's subject can be drawn from
    them.

    The descriptor carries a ``job_id`` only when the packet this job was handed
    names one. ``plumbline_job.do_file()`` files a folder under ``jobs/`` only
    when its packet carries an id — a folder under ``jobs/`` with no id is a job
    no reader can read — so a finish whose packet names none is not a job and is
    not filed as one. Nothing here invents an identity: a temporary record
    directory's basename is not a job id, and writing one into the packet would
    change, after dispatch, the terms the job was handed (measured 2026-11-12,
    Job 38d: the fallback to the record directory's name is how
    ``jobs/tmp3oudgzx8`` came to exist). The optional ``job_id`` is an identity a
    CALLER asserts — never a fallback to the scratch folder the finish ran in.
    """
    descriptor = dict(packet) if isinstance(packet, dict) else {}
    if not (isinstance(descriptor.get("job_id"), str) and descriptor["job_id"].strip()):
        fallback = job_id if isinstance(job_id, str) else ""
        if fallback.strip():
            descriptor["job_id"] = fallback.strip()
    finish = {
        "terminal_state": halt["terminal_state"],
        "outcome": halt["outcome"],
        "stop": halt["stop"],
        "rounds": halt["rounds"],
        "cap": halt["cap"],
        "accepted_round": halt["accepted_round"],
        "best_round": halt["best_round"],
        "cost": halt["cost"],
        "separation_gaps": halt["separation_gaps"],
        "started_at": halt["started_at"],
        "ended_at": halt["ended_at"],
        "packet_sha256": halt["packet_sha256"],
        "rounds_sha256": halt["rounds_sha256"],
        "commit": halt["commit"],
    }
    descriptor.update(finish)
    descriptor.update({
        "terminalState": halt["terminal_state"],
        "startedAt": halt["started_at"],
        "endedAt": halt["ended_at"],
        "packetSha256": halt["packet_sha256"],
        "roundsSha256": halt["rounds_sha256"],
        "bestRound": halt["best_round"],
        "acceptedRound": halt["accepted_round"],
        "finish": dict(finish),
        "summary": dict(finish),
    })
    return descriptor


def freeze_bar(record_dir, root):
    """Freeze the bar in the ledger, live, before the Maker is dispatched.

    The bar is the one the job declares: ``bar.file`` in
    ``record_dir/inputs/custody.json``, taken from the same relative path under
    ``root``; when nothing is declared, the convention file
    ``<root>/custody/bar.md``. The ledger tool names a bar relative to the job
    directory, so the bar's bytes are copied there unchanged and the tool is
    pointed at that copy. The tool stamps the freeze from its own clock and
    appends the event to ``inputs/custody-events.jsonl``; this module types no
    time.

    A declared bar that cannot be read fails closed: this raises, naming the
    declared path, before the Maker command runs — no Maker call and no
    ``emit_custody.py`` run. A job is custody-bearing when
    ``record_dir/inputs/custody.json`` exists or the convention bar exists. A
    custody-bearing job that names no ``bar.file`` and has no convention bar
    also fails closed: the presence of the custody inputs removes the skip
    path, so it cannot lose its bar silently. A caller that prepared neither
    signal is not refused: nothing is frozen and nothing is written.
    """
    job = os.path.abspath(str(record_dir))
    declared = os.path.join(job, "inputs", "custody.json")
    convention = os.path.join(root, "custody", "bar.md")
    rel = _declared_bar(job)
    if rel is None:
        if not os.path.isfile(convention):
            if os.path.isfile(declared):
                raise RuntimeError(
                    "job is custody-bearing but names no bar.file in %s and no convention bar "
                    "exists at %s; cannot freeze before dispatch" % (declared, convention)
                )
            return
        rel = "custody/bar.md"
    source = os.path.join(root, rel)
    if os.path.isabs(rel) or not os.path.isfile(source):
        raise RuntimeError("no bar file at %s; cannot freeze before dispatch" % source)
    dest = os.path.join(job, rel)
    if not _inside(os.path.realpath(dest), os.path.realpath(job)):
        raise RuntimeError("declared bar %s is outside the job directory; cannot freeze" % rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(source, dest)
    ledger = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custody_ledger.py")
    proc = subprocess.run(
        [sys.executable, ledger, "freeze", "--job-dir", job, "--bar", rel],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or "exit %s" % proc.returncode
        raise RuntimeError("the bar could not be frozen in %s: %s" % (job, detail))


def _declared_bar(job):
    """``bar.file`` from ``<job>/inputs/custody.json``, or None if not declared.

    A missing, unreadable or malformed file declares nothing, so the caller may
    still fall back to the convention bar. A named bar is returned as written:
    a path that cannot be read is then named in the failure, which is what the
    fail-closed rule requires.
    """
    path = os.path.join(job, "inputs", "custody.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            body = json.load(handle)
    except (OSError, ValueError):
        return None
    bar = body.get("bar") if isinstance(body, dict) else None
    rel = bar.get("file") if isinstance(bar, dict) else None
    if not isinstance(rel, str) or not rel.strip():
        return None
    return rel


def loop(packet, *, record_dir, cwd=None, timeout_s=600, commit=None, evaluator_fn=None) -> dict:
    """Run the rounds the packet names, then file the finish and return it.

    ``packet`` is a path or a loaded dict. A refusal writes ``escalation.json``
    and raises ``ValueError`` before any command runs; a refusal is not a
    finish. Every other end calls ``emit_custody_for_finish`` once, after the
    round records and a ``packet.json`` describing the finish exist, and only if
    that seam returns 0 does it file its finish — ``summary.json``, and
    ``escalation.json`` for a stop a human must see — and return the summary.
    If the seam returns 1, 2 or 3, or the finish's stamps came from a replaced
    clock, it raises ``CustodyNotDone`` with what the record would have said and
    writes neither file. This function sends nothing and does not start another
    loop.
    """
    started_at = _stamp()
    try:
        loaded, packet_sha = _load(packet)
    except Exception as exc:
        os.makedirs(record_dir, exist_ok=True)
        _refuse(
            record_dir,
            packet if isinstance(packet, dict) else {},
            ["packet could not be loaded: %s" % exc],
            started_at,
        )
        raise
    root = os.path.realpath(cwd) if cwd is not None else os.path.realpath(os.getcwd())
    problems = _problems(loaded, record_dir, root, evaluator_fn)
    os.makedirs(record_dir, exist_ok=True)
    if problems:
        _refuse(record_dir, loaded, problems, started_at)
        raise ValueError("; ".join(problems))

    freeze_bar(record_dir, root)

    artifact = loaded["artifact"]
    bounds = loaded["bounds"]
    budget = bounds["budget"]
    cap = bounds["cap"]
    deadline = time.monotonic() + float(budget["time_hours_lt"]) * 3600
    spend = 0.0
    best_round = None
    best_scores = None
    defects: list[dict] = []
    solutions: list[dict] = []
    round_paths: list[str] = []
    stop = None
    by = None
    accepted_round = None
    last = 0

    for number in range(1, cap + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stop = CLOCK
            break
        round_started_at = _stamp()
        if number > 1 and best_round is not None and best_round != number - 1:
            _restore(root, artifact["editable"], _editable_dir(record_dir, best_round))
        findings = {
            "round": number,
            "cap": cap,
            "best": None if best_round is None else {
                "round": best_round,
                "editable": _editable_dir(record_dir, best_round),
                "sha256": _tree_sha(_editable_dir(record_dir, best_round)),
            },
            "defects": defects,
            "solutions": solutions,
        }
        try:
            leak = _held_out(json.dumps(findings), loaded["evaluator"].get("held_out") or [])
        except OSError as exc:
            stop = HELD_OUT_UNREADABLE
            _write_round(
                record_dir, number, None, None,
                {"method": _HELD_METHOD, "result": "fail", "by": "loop()", "reason": str(exc)},
                None, None, None, False, best_round, 0, stop,
                round_started_at, _stamp(),
            )
            last = number
            round_paths.append(os.path.join(record_dir, "round-%02d.json" % number))
            break
        findings_path = os.path.join(record_dir, "findings-%02d.json" % number)
        if leak:
            stop = HELD_OUT
            _write_round(
                record_dir, number, None, None, {"method": _HELD_METHOD, "result": "fail", "by": "loop()"},
                None, None, None, False, best_round, 0, stop,
                round_started_at, _stamp(),
            )
            last = number
            round_paths.append(os.path.join(record_dir, "round-%02d.json" % number))
            break
        _dump(findings_path, findings)
        bound = remaining if timeout_s is None else min(timeout_s, remaining)
        clock_cut = timeout_s is None or remaining <= timeout_s
        cost_path = os.path.join(record_dir, "cost-%02d-maker.json" % number)
        try:
            result = run(
                artifact["test_cmd"],
                artifact["frozen"],
                artifact["editable"],
                loaded["maker"]["cmd"],
                commit=commit,
                cwd=root,
                timeout_s=bound,
                ignore=artifact.get("ignore") or [],
                require_red=(number == 1),
                maker_env={
                    "PLUMBLINE_FINDINGS": findings_path,
                    "PLUMBLINE_COST": cost_path,
                },
                # A detached engine must be waited for, not sampled: route-maker exits 0 the
                # moment it detaches, so measuring the tree on its return reads a Maker that
                # has not finished (measured 2026-11-09, Job 31 record-3: the fix landed 56 s
                # after the loop had already written "no artifact").
                await_exit_file=os.path.join(record_dir, "aider-exit.json"),
                await_dispatch_file=os.path.join(record_dir, "aider-dispatch.json"),
            )
        except ValueError as exc:
            if number == 1:
                _refuse(record_dir, loaded, [str(exc)], started_at)
            raise
        editable_copy = _editable_dir(record_dir, number)
        _snapshot_editable(root, artifact["editable"], editable_copy)
        produced = result.get("reason") != NO_ARTIFACT
        stop, by = _classify(result, clock_cut)
        if stop is None and time.monotonic() >= deadline:
            stop, by = CLOCK, None
        maker_cost = _take_cost(cost_path)
        round_cost = 0.0
        if maker_cost is not None:
            round_cost += maker_cost
            spend += maker_cost
        if stop is None and budget["amount"] > 0 and maker_cost is None:
            stop = BUDGET_UNMEASURED
        elif stop is None:
            if budget["amount"] > 0 and spend >= budget["amount"]:
                stop = BUDGET
            elif budget["amount"] == 0 and round_cost > 0:
                stop = BUDGET
        reading = {}
        evaluator_rows = []
        pass_rule = None
        mismatch = False
        scores = None
        if stop is None and result.get("rerun", {}).get("exit") != 0:
            observation = "rerun exit %s sha256 %s" % (
                result["rerun"]["exit"], result["rerun"]["output_sha256"],
            )
            violation = {
                "id": "gate",
                "class": "artifact_missed_standard",
                "dimension": None,
                "observation": observation,
            }
            reading = {
                "from": "gate",
                "verdict": "regenerate",
                "dimensions": [],
                "violations": [violation],
            }
            pass_rule = "regenerate"
            defects.append({
                "round": number,
                "id": "gate",
                "class": "artifact_missed_standard",
                "dimension": None,
                "observation": observation,
            })
        elif stop is None:
            ev_stop, ev_by, evaluator_rows, scores, mismatch, fired, eval_costs, eval_missing = _evaluate(
                loaded, result, number, editable_copy, root, deadline, timeout_s, evaluator_fn, record_dir,
            )
            for one in eval_costs:
                round_cost += one
                spend += one
            if ev_stop:
                stop, by = ev_stop, ev_by
            elif budget["amount"] > 0 and eval_missing:
                stop = BUDGET_UNMEASURED
            elif budget["amount"] > 0 and spend >= budget["amount"]:
                stop = BUDGET
            elif budget["amount"] == 0 and round_cost > 0:
                stop = BUDGET
            elif fired:
                stop = ESCALATION_CLASS
            else:
                pass_rule = _pass_rule(scores, bounds)
                if pass_rule == ACCEPTED:
                    stop = ACCEPTED
                    accepted_round = number
                elif pass_rule == REJECTED:
                    stop = REJECTED
                else:
                    pass_rule = "regenerate"
            parsed_rows = _parsed(evaluator_rows)
            if parsed_rows:
                first = parsed_rows[0]
                reading = {
                    "from": "evaluator",
                    "verdict": first.get("verdict"),
                    "dimensions": first.get("dimensions"),
                    "violations": first.get("violations"),
                }
            if scores:
                for parsed in parsed_rows:
                    for item in parsed.get("violations") or []:
                        defects.append({
                            "round": number,
                            "id": item.get("id"),
                            "class": item.get("class"),
                            "dimension": item.get("dimension"),
                            "observation": item.get("observation"),
                        })
                        if item.get("remedy"):
                            solutions.append({
                                "round": number, "id": item.get("id"), "remedy": item.get("remedy"),
                            })
        if produced and stop not in (NO_ARTIFACT, PACKET_REFUSED):
            if best_round is None:
                best_round, best_scores = number, scores
            elif scores and (best_scores is None or _better(scores, best_scores)):
                best_round, best_scores = number, scores
        held = {"method": _HELD_METHOD, "result": "pass" if not leak else "fail", "by": "loop()"}
        _write_round(
            record_dir, number, result, _sha_file(findings_path), held,
            evaluator_rows, reading, pass_rule, mismatch, best_round, round_cost, stop,
            round_started_at, _stamp(),
        )
        last = number
        round_paths.append(os.path.join(record_dir, "round-%02d.json" % number))
        if stop:
            break
        if number == cap:
            stop = CAP_REACHED
            break

    if stop is None:
        stop = CAP_REACHED
    ended_at = _stamp()
    state, outcome = _STATES[stop]
    halt = {
        "terminal_state": state,
        "outcome": outcome,
        "stop": stop,
        "rounds": last,
        "cap": cap,
        "accepted_round": accepted_round,
        "best_round": best_round,
        "cost": spend,
        "separation_gaps": [_GAP_GATE, _GAP_ARCH] if stop != ACCEPTED else [],
        "rounds_sha256": [_sha_file(path) for path in round_paths],
        "packet_sha256": packet_sha,
        "commit": conductor_software.record_field(commit),
        "started_at": started_at,
        "ended_at": ended_at,
    }
    if not _own_clock():
        raise CustodyNotDone(halt, _exit_code(stop))
    _dump(os.path.join(record_dir, "packet.json"), _custody_packet(loaded, halt))
    code = emit_custody_for_finish(record_dir, halt)
    if code != 0:
        raise CustodyNotDone(halt, code if code in (1, 2, 3) else 3)
    _file_finish(record_dir, loaded, halt, round_paths, best_round, by)
    halt["filing"] = file_finish(record_dir, halt)
    # Dual gates (2026-11-12 delight): instrument finish ≠ custody release record.
    # terminal_state stays doctrine-pure; finish_kind / gates name the human truth.
    try:
        from kit.delight import attach_gates
        halt = attach_gates(halt, record_dir, loaded if isinstance(loaded, dict) else None)
    except Exception as _delight_err:  # noqa: BLE001 — finish must still file
        halt["gates_error"] = "%s: %s" % (type(_delight_err).__name__, _delight_err)
    _dump(os.path.join(record_dir, "summary.json"), halt)
    # The folder was copied BEFORE this row existed, so the filed copy could not say how it was filed.
    # Measured 2026-11-09 on Job 31's first close: the filed summary carried `filing: null` while the live one
    # carried the row. A record that cannot describe its own filing is the same defect as a status file that
    # cannot describe its own custody — so the final summary is written into the copy as well.
    filed = halt["filing"].get("dest")
    if halt["filing"].get("filed") and filed and os.path.isdir(filed):
        _dump(os.path.join(filed, "summary.json"), halt)
    return halt


def _filed_name(record_dir, halt=None):
    """The folder name a finish is filed under.

    A job is filed under the identity its packet names — never under the scratch
    directory it happened to run in. ``loop()`` cannot pass ``job_id`` to
    ``do_file()`` as a parameter of its own: the destination name is the job's,
    not the caller's. So the name is read back from the ``packet.json`` this
    finish wrote, which is the same file ``do_file()`` classifies from.

    Owner ruling 2026-11-12 ("A"): a finish whose packet names no id is filed
    under ``runs/finish-<started_at>`` from the halt — stable, not a scratch
    basename, and nothing reads ``runs/`` as a job. Inventing a ``job_id`` on the
    packet is forbidden; vanishing is forbidden.
    """
    try:
        with open(os.path.join(str(record_dir), "packet.json"), encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, ValueError):
        doc = None
    if isinstance(doc, dict):
        name = doc.get("job_id")
        if isinstance(name, str) and name.strip():
            return name.strip()
    # no job_id → finish-<started_at> (Owner A). Filesystem-safe: drop ":" and
    # fold the offset so the name is one path component.
    started = ""
    if isinstance(halt, dict):
        raw = halt.get("started_at") or halt.get("startedAt") or ""
        if isinstance(raw, str):
            started = raw.strip()
    if started:
        safe = (
            started.replace(":", "")
            .replace("+", "p")
            .replace("/", "-")
        )
        # keep a compact readable form: finish-2026-11-12T141045p0000
        return "finish-%s" % safe
    # last resort: still not a jobs/ mint from the scratch dir name alone —
    # do_file will place this under runs/ as kind=run.
    return "finish-unknown"


def file_finish(record_dir, halt):
    """State the job's custody status in its own folder, then file it, as the Orchestrator's last act.

    WHY HERE, AND NOT IN A CONDUCTOR'S CHECKLIST. A finished loop() used to leave the folder wherever it ran:
    no ``custody/status.json``, and no copy under ``dot-plumbline/jobs/``. Measured 2026-11-09, ``jobs/`` held
    two jobs while roughly twenty-five had run, because filing was a sentence in a commit message
    (``988c8ac``) and every dispatch wrote to ``/tmp``. The repo's own record said the program had stopped in
    November while the loop kept working. The seat that decides the terminal state is the seat that closes the
    job; a person running ``close`` afterward is the same defect as remembering to file.

    WHY THE DESTINATION IS CONFIGURATION AND NOT A PARAMETER. ``loop()`` must not gain an argument a caller has
    to remember — that is the defect this fixes, one level up. ``PLUMBLINE_FILE_INTO`` names the instance's
    ``dot-plumbline`` once, in the seat's entry script; a caller who does not set it gets a status file and a
    ``filed: false`` row saying no destination was configured, never a silent skip.

    WHY THE FILED FOLDER IS NAMED BY THE JOB. A finish runs in a temporary record directory, and filing copies
    that folder under the destination. Left to itself the copy takes the scratch directory's name — measured
    2026-11-12 (Job 38d): ``dot-plumbline/jobs/tmp3oudgzx8``, a folder under ``jobs/`` that no reader can name
    because it is nobody's job. So the name handed to ``do_file()`` is the packet's own ``job_id``. A finish
    whose packet names no id is not a job, so it is not filed under ``jobs/``: an invented identity is worse
    than a missing name. It is still filed — as the evidence of a run, under ``runs/``, where nothing reads it
    as a closed job — because the record of a finish must outlive the scratch directory it ran in. The
    destination is still configuration, not a parameter — the NAME is the job's, and it is read from the job's
    own terms.

    WHY IT CANNOT RAISE. An accepted artifact must not be undone by a filing defect: the work is done, the
    record either shipped or did not, and a traceback here would fail a job that already passed. Every outcome
    is a row in ``summary.json`` — ``state``, ``filed``, ``dest`` and the command's own words — so the failure
    is readable in the record instead of in a transcript nobody kept.
    """
    record = os.path.join(str(record_dir), "custody", "record.custody.json")
    state = "custody" if os.path.isfile(record) else "missing"
    row = {"state": state, "filed": False, "dest": None, "detail": ""}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import plumbline_job

        plumbline_job.write_status(
            record_dir, state,
            terminal_state=halt.get("terminal_state"),
            record_sha256=(hashlib.sha256(open(record, "rb").read()).hexdigest() if state == "custody" else None),
            why=(
                "the custody record shipped with this finish; its sha256 is named here so a later edit to the "
                "folder is visible as a disagreement, not as a detail someone has to remember."
                if state == "custody" else
                "loop() returned a finish with no custody record in the folder. The job is closed and its record "
                "is missing; that is a defect the summary carries, not a state the folder should hide."
            ),
        )
        into = (os.environ.get("PLUMBLINE_FILE_INTO") or "").strip()
        if not into:
            row["detail"] = ("no destination configured: PLUMBLINE_FILE_INTO is unset. The status file is written "
                             "and the job is not filed; this row is the record of that.")
            return row
        name = _filed_name(record_dir, halt)
        # packet job_id → jobs/<id>; no id → runs/finish-<started_at> (Owner A).
        try:
            with open(os.path.join(str(record_dir), "packet.json"), encoding="utf-8") as handle:
                _pkt = json.load(handle)
        except (OSError, ValueError):
            _pkt = {}
        _has_id = isinstance((_pkt or {}).get("job_id"), str) and (_pkt.get("job_id") or "").strip()
        _bucket = "jobs" if _has_id else "runs"
        args = argparse.Namespace(job_dir=str(record_dir), into=into, run_log=None, force=True,
                                  backfill=False, allow_incomplete=False, name=name)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = plumbline_job.do_file(args)
        row["filed"] = code == 0
        if row["filed"]:
            # Say where the filer ACTUALLY wrote. A row that names a folder which is not there
            # sends a reader to nothing. JOB → jobs/<job_id>; id-less finish → runs/finish-<started_at>.
            row["dest"] = str(
                pathlib.Path(into).expanduser().resolve()
                / _bucket
                / name
            )
        row["detail"] = (buffer.getvalue() or "").strip()[-800:]
    except Exception as exc:  # filing must not undo a finish; the row is the report
        row["detail"] = "filing raised %s: %s" % (type(exc).__name__, exc)
    return row


def _file_finish(record_dir, packet, halt, round_paths, best_round, by):
    """Write the finish: ``summary.json``, and an escalation for a stop.

    ``summary.json`` is what the finish says. ``escalation.json`` is written
    only for a stop a human must see — never for an accepted finish — and
    carries the route and holders the packet names, the best round's snapshot,
    one row per written round record with its sha256, the seat that made the
    stop (``by``) and the stamps. The question, diagnosis, why-unobservable,
    options, recommendation, proposed packet and decision are the Architect's
    to write; this module leaves them null.
    """
    _dump(os.path.join(record_dir, "summary.json"), halt)
    if halt["stop"] == ACCEPTED:
        return
    escalation = packet.get("escalation") if isinstance(packet.get("escalation"), dict) else {}
    best = None
    if best_round is not None:
        editable = _editable_dir(record_dir, best_round)
        best = {"round": best_round, "editable": editable, "sha256": _tree_sha(editable)}
    _dump(os.path.join(record_dir, "escalation.json"), {
        "terminal_state": halt["terminal_state"],
        "outcome": halt["outcome"],
        "stop": halt["stop"],
        "escalation_kind": _KINDS.get(halt["stop"], "other"),
        "route": escalation.get("route"),
        "human_seat": packet.get("human_seat"),
        "holders": escalation.get("holders"),
        "problems": [],
        "question": None,
        "diagnosis": None,
        "why_unobservable": None,
        "options": None,
        "recommendation": None,
        "proposed_packet": None,
        "decision": None,
        "best": best,
        "tried": [
            {"round": index + 1, "record": path, "record_sha256": _sha_file(path)}
            for index, path in enumerate(round_paths)
        ],
        "by": by or "loop()",
        "started_at": halt["started_at"],
        "ended_at": halt["ended_at"],
    })


def _stamp() -> str:
    """Now, as every record this module writes spells it."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load(packet):
    if isinstance(packet, (str, os.PathLike)):
        raw = open(packet, "rb").read()
        return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()
    raw = json.dumps(packet, sort_keys=True).encode("utf-8")
    return packet, hashlib.sha256(raw).hexdigest()


def _problems(packet, record_dir, root, evaluator_fn) -> list[str]:
    problems = []
    if packet.get("ratified") is not True:
        problems.append("ratified is not true")
    if packet.get("mode") != "scored":
        problems.append("mode is not scored (%s)" % packet.get("mode"))
    if not str(packet.get("human_seat") or "").strip():
        problems.append("human_seat is blank")
    artifact = packet.get("artifact") if isinstance(packet.get("artifact"), dict) else {}
    maker = packet.get("maker") if isinstance(packet.get("maker"), dict) else {}
    evaluator = packet.get("evaluator") if isinstance(packet.get("evaluator"), dict) else {}
    bounds = packet.get("bounds") if isinstance(packet.get("bounds"), dict) else {}
    budget = bounds.get("budget") if isinstance(bounds.get("budget"), dict) else {}
    escalation = packet.get("escalation") if isinstance(packet.get("escalation"), dict) else {}
    if not _strings(artifact.get("test_cmd")):
        problems.append("artifact.test_cmd is not a non-empty list of strings")
    if not _strings(artifact.get("frozen")):
        problems.append("artifact.frozen is missing")
    editable = artifact.get("editable")
    if not isinstance(editable, list):
        problems.append("artifact.editable is not a list")
    else:
        for rel in editable:
            if not isinstance(rel, str) or not rel.strip():
                problems.append("artifact.editable has an entry that is not a non-empty string")
                continue
            if os.path.isabs(rel):
                problems.append("artifact.editable entry is absolute: %s" % rel)
                continue
            if not _inside(os.path.realpath(os.path.join(root, rel)), root):
                problems.append("artifact.editable entry resolves outside cwd: %s" % rel)
    if not _strings(maker.get("cmd")):
        problems.append("maker.cmd is not a non-empty list of strings")
    if maker.get("handoff") != "rule12":
        problems.append("maker.handoff is not rule12")
    if evaluator_fn is None and not _strings(evaluator.get("cmd")):
        problems.append("evaluator.cmd is not a non-empty list of strings")
    runs = evaluator.get("runs")
    if type(runs) is not int or runs < 2:
        problems.append("evaluator.runs is not an int of at least 2")
    for name in ("T_accept", "T_dim", "T_reject"):
        if name not in bounds or not _number(bounds.get(name)):
            problems.append("%s is not a number" % name)
    cap = bounds.get("cap")
    if type(cap) is not int or cap < 1:
        problems.append("cap is not an int of at least 1")
    if "cap_counts" in bounds and bounds.get("cap_counts") != "generations":
        problems.append("cap_counts is not generations")
    if not _number(budget.get("time_hours_lt")) or budget.get("time_hours_lt") <= 0:
        problems.append("budget.time_hours_lt is not a positive number")
    if not _number(budget.get("amount")) or budget.get("amount") < 0:
        problems.append("budget.amount is not a number of 0 or more")
    # The scope of a scored job is declared or it is legacy — never inferred. A packet
    # that declares bounds.scoring_set is scored over that set, and a declared set that
    # drops a case the Maker bar collects is refused: that is the Job 35 shape, where
    # sixteen dimensions were scored and a case the bar does not collect turned an accept
    # into a regenerate. A packet that declares nothing is the packet every caller wrote
    # before Job 36: it is admitted and scored exactly as it was, because an absent set is
    # neither a refusal nor a licence to score everything (Job 37's compat rule). A set
    # that is PRESENT is validated wherever it appears, so an empty or malformed
    # declaration can never pass itself off as a legacy packet. A suite that is an inline
    # program names no bar and collects no cases, so it has no bar scope to compare
    # against; that path is left exactly as it was.
    bar = _bar_file(packet, root)
    declared = bounds.get("scoring_set")
    trouble = _scoring_set_problems(declared)
    problems.extend(trouble)
    if declared is not None and not trouble and bar is not None:
        omitted = _missing_cases(_scored_set(bounds), _collected_cases(bar, root))
        if omitted:
            problems.append(
                "bounds.scoring_set omits a case the Maker bar collects: %s"
                % ", ".join(omitted)
            )
    if escalation.get("route") != ["Architect", "Owner"]:
        problems.append("escalation.route is not ['Architect', 'Owner']")
    if not isinstance(escalation.get("classes"), list):
        problems.append("escalation.classes is not a list")
    holders = escalation.get("holders") if isinstance(escalation.get("holders"), dict) else {}
    architect = str(holders.get("architect") or "")
    if not architect.strip():
        problems.append("holders.architect is blank")
    orch = holders.get("orchestrator")
    scripts = []
    escalations = []
    if isinstance(orch, list):
        for index, item in enumerate(orch):
            if not isinstance(item, dict):
                continue
            if item.get("does") == "rounds" and item.get("kind") == "script":
                scripts.append(item)
            if item.get("does") == "escalations":
                escalations.append(item)
            if not str(item.get("tested") or "").strip():
                problems.append(
                    "holders.orchestrator[%d] (%s) has no tested" % (index, item.get("does"))
                )
    if len(scripts) != 1:
        problems.append("holders.orchestrator has no script holder for rounds")
    if len(escalations) != 1:
        problems.append("holders.orchestrator has no escalations holder")
    folded = architect.strip().casefold()
    names = []
    if isinstance(orch, list):
        names = [str(item.get("holder") or "").strip().casefold() for item in orch if isinstance(item, dict)]
    if folded and folded in names:
        problems.append("holders.architect equals an orchestrator holder")
    rec = conductor_software.resolve(record_dir, root)
    if _inside(rec, root):
        problems.append("record_dir resolves inside cwd")
    if _holds_files(record_dir):
        problems.append("record_dir already holds files")
    return problems


def _strings(value) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(isinstance(item, str) and item for item in value)


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _scored_set(bounds) -> list[str]:
    """The dimension names ``bounds.scoring_set`` declares, in the order it gives them.

    This is the packet's declaration and nothing else. An absent, empty or malformed
    block answers ``[]``, so a caller can tell a declaration from its absence; whether
    an ``[]`` may be admitted at all is ``_problems``' question and this reader does not
    judge it — an absent set is the legacy packet, a present empty one is refused.
    ``_evaluate`` builds the dict ``_pass_rule`` sees from this list when a set is
    declared, which is how the set the rule reads is the set the record can name; with
    no set declared the whole reply is scored, as it was before Job 36.
    """
    if not isinstance(bounds, dict):
        return []
    declared = bounds.get("scoring_set")
    if not isinstance(declared, list):
        return []
    return [name for name in declared if isinstance(name, str) and name.strip()]


def _scoring_set_problems(declared) -> list[str]:
    """Why ``bounds.scoring_set`` cannot be admitted, or ``[]`` when it can.

    An ABSENT set is the legacy packet and is admitted (Job 37's compat rule): it is
    neither a refusal nor a licence to score everything, and ``_scored_set`` answers
    ``[]`` for it so the caller can tell the two apart. A set that is PRESENT is
    validated: a non-empty list of non-empty strings with no duplicate. A string is
    refused rather than iterated as characters (``"nope"`` would score over ``n``,
    ``o``, ``p``, ``e`` and score nothing — a silent green), an empty list is refused
    rather than read as "score everything", and a duplicate is refused because two
    names for one case make the set's order meaningless.
    """
    if declared is None:
        return []
    if not isinstance(declared, list) or not declared:
        return [
            "bounds.scoring_set is not a non-empty list of dimension names: %r" % (declared,)
        ]
    problems = []
    seen = set()
    for name in declared:
        if not isinstance(name, str) or not name.strip():
            problems.append(
                "bounds.scoring_set holds an entry that is not a non-empty string: %r" % (name,)
            )
        elif name in seen:
            problems.append("bounds.scoring_set names %s twice" % name)
        else:
            seen.add(name)
    return problems


def _missing_cases(declared, collected) -> list[str]:
    """The cases the Maker bar collects that ``declared`` leaves out.

    A declared set may be a superset of what the bar collects — naming a case the bar
    drops is admitted — but it may not drop one the bar keeps: a case outside the set
    is a case nothing measures.
    """
    held = set(declared)
    return [name for name in collected if name not in held]


def _bar_file(packet, root):
    """The Maker bar the packet's gate suite names, or None when it names no file.

    ``artifact.test_cmd`` names the bar as the first argument after the interpreter
    (``[python3, "tests/bar.py"]``); that file is what ``load_tests``, if the bar has
    one, collects cases from. A suite that runs an inline program or a module
    (``[python3, "-c", ...]``, ``[python3, "-m", ...]``) names no bar, so there is no
    collected set to declare and none is required.

    The bar is read from the command's shape, not from the tree: the path is returned
    whether or not it exists under ``root``. The packet names the bar it means to run,
    and a suite whose file is missing is a failure the run itself reports. Requiring
    the file to be present here would make whether a job must declare its scope depend
    on which tree a reply happens to be admitted in — and an absent set is the defect
    this job exists to stop, not one to re-open when the bar cannot be found.
    """
    artifact = packet.get("artifact") if isinstance(packet.get("artifact"), dict) else {}
    cmd = artifact.get("test_cmd")
    if not _strings(cmd):
        return None
    program = os.path.basename(cmd[0]).lower()
    if not (program in ("py", "pyw") or program.startswith("python")):
        return _bar_path(cmd[0], root)
    for part in cmd[1:]:
        if not isinstance(part, str) or not part:
            continue
        if part.startswith("-"):
            return None
        return _bar_path(part, root)
    return None


def _bar_path(part, root):
    """The bar path a ``test_cmd`` argument names, read relative to ``root``."""
    return part if os.path.isabs(part) else os.path.realpath(os.path.join(root, part))


_COLLECT_SCRIPT = r"""
import importlib.util as _u
import json as _json
import sys as _sys
import unittest as _unittest

_spec = _u.spec_from_file_location("plumbline_bar_under_test", _sys.argv[1])
_module = _u.module_from_spec(_spec)
_sys.modules["plumbline_bar_under_test"] = _module
_spec.loader.exec_module(_module)
_names = []


def _walk(test):
    if isinstance(test, _unittest.TestSuite):
        for _one in test:
            _walk(_one)
    else:
        _name = test.id().rsplit(".", 1)[-1]
        if _name.startswith("test_"):
            _name = _name[len("test_"):]
        _names.append(_name)


_walk(_unittest.defaultTestLoader.loadTestsFromModule(_module))
_sys.stdout.write(_json.dumps(_names))
"""


def _collected_cases(path, root) -> list[str]:
    """The dimension names the Maker bar collects, read by running its own ``load_tests``.

    "Collected" is what ``unittest`` collects from the bar, so where the bar defines a
    ``load_tests`` that drops a class, those cases are not collected — which is exactly
    how the Job 35 bar came to have fourteen cases while sixteen were scored. The names
    are the test method names with ``test_`` removed, the same spelling a dimension
    carries. The collection runs in a child, with bytecode writing off, so importing a
    bar cannot leave a ``__pycache__`` in the tree being measured or pollute the loop's
    own process. A bar that cannot be imported collects nothing to compare against: an
    unreadable bar is a failure the suite itself will report, never a reason to invent a
    scope here.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-B", "-c", _COLLECT_SCRIPT, path],
            capture_output=True,
            text=True,
            env=_bar_env(),
            cwd=root,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    try:
        names = json.loads(proc.stdout)
    except ValueError:
        return []
    return [name for name in names if isinstance(name, str)]


def _inside(child, parent) -> bool:
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False


def _holds_files(path) -> bool:
    if not os.path.isdir(path):
        return False
    for _dir, _names, files in os.walk(path):
        if files:
            return True
    return False


def _refuse(record_dir, packet, problems, started_at):
    escalation = packet.get("escalation") if isinstance(packet.get("escalation"), dict) else {}
    os.makedirs(record_dir, exist_ok=True)
    _dump(os.path.join(record_dir, "escalation.json"), {
        "terminal_state": "needs_owner",
        "outcome": "needs_owner",
        "stop": PACKET_REFUSED,
        "escalation_kind": "other",
        "route": escalation.get("route"),
        "human_seat": packet.get("human_seat"),
        "holders": escalation.get("holders"),
        "problems": problems,
        "question": None,
        "diagnosis": None,
        "why_unobservable": None,
        "options": None,
        "recommendation": None,
        "proposed_packet": None,
        "decision": None,
        "started_at": started_at,
        "refused_at": _stamp(),
    })


def _classify(result, clock_cut):
    if not result.get("dispatched"):
        return NOT_DISPATCHED, None
    if result.get("hashes_unchanged") is False or result.get("reason") == "edit outside editable":
        return TAMPERED, "maker"
    if result.get("reason") == MAKER_FAILED:
        return MAKER_FAILED, None
    if result.get("reason") == "timeout":
        return (CLOCK if clock_cut else TIMEOUT_STOP), None
    if result.get("reason") == NO_ARTIFACT:
        return NO_ARTIFACT, None
    return None, None


def _evaluator_env(turn: dict, cost_path: str) -> dict:
    """The environment the Evaluator's turn is run in.

    It carries the turn and the cost path, and it inherits the no-bytecode setting of
    the other arms: an evaluator that imports the artifact it is judging must not leave
    ``__pycache__`` inside it. Measured 2026-11-10, Job 32 record-8: a passing Maker turn
    was followed by TAMPERED because the evaluator's own python wrote into the tree.
    """
    env = _bar_env()
    env["PLUMBLINE_TURN"] = json.dumps(turn)
    env["PLUMBLINE_COST"] = cost_path
    return env


def _evaluate(packet, result, number, editable_copy, root, deadline, timeout_s, evaluator_fn, record_dir):
    rows = []
    costs = []
    missing = False
    ignore = packet["artifact"].get("ignore") or []
    # The scope is the packet's, taken once, before any reply is read. A set inferred
    # from what the Evaluator sent would score whatever it was handed, which is the Job
    # 35 defect wearing a declaration's clothes. A PRESENT set that cannot be admitted —
    # an empty list, a string, a name that is not a name — is refused here too, so the
    # refusal does not depend on the caller having gone through _problems first. An
    # ABSENT set is the legacy packet: no refusal, and every dimension in the reply is
    # scored, exactly as it was before Job 36 (Job 37's compat rule).
    bounds = packet.get("bounds") if isinstance(packet.get("bounds"), dict) else {}
    declared = _scored_set(bounds)
    if _scoring_set_problems(bounds.get("scoring_set")) and _bar_file(packet, root) is not None:
        return SCORING_SET, None, rows, None, False, None, costs, missing
    turn = {
        "round": number,
        "artifact": editable_copy,
        "artifact_sha256": _tree_sha(editable_copy),
        "gate": {key: value for key, value in result.items() if key != "maker"},
    }
    for index in range(packet["evaluator"]["runs"]):
        left = deadline - time.monotonic()
        if left <= 0:
            return CLOCK, None, rows, None, False, None, costs, missing
        bound = left if timeout_s is None else min(timeout_s, left)
        before = conductor_software.snapshot(root)
        cost_path = os.path.join(record_dir, "cost-%02d-eval-%d.json" % (number, index))
        parsed = None
        if evaluator_fn is not None:
            try:
                parsed = evaluator_fn(turn, root)
                exit_code, output = 0, json.dumps(parsed).encode("utf-8")
            except Exception:
                rows.append({"exit": "error", "output_sha256": conductor_software.NOT_RECORDED, "parsed": None})
                return EVALUATOR_FAILED, None, rows, None, False, None, costs, missing
        else:
            env = _evaluator_env(turn, cost_path)
            exit_code, output = _run(packet["evaluator"]["cmd"], root, bound, env=env)
            one = _take_cost(cost_path)
            if one is None:
                missing = True
            else:
                costs.append(one)
        # Keep the evaluator's own bytes. Measured 2026-11-10, Job 32 record-10: exit 1,
        # no score file, no reply file, and the record held only the output hash — so the
        # reader could not tell the seat from the route's shape check from a spent turn.
        if output:
            keep_dir = os.path.join(record_dir, "evidence")
            os.makedirs(keep_dir, exist_ok=True)
            with open(os.path.join(keep_dir, "eval-%02d-%d.log" % (number, index)),
                      "wb") as fh:
                fh.write(output)
        after = conductor_software.snapshot(root)
        changed = [
            path for path in conductor_software.changed_paths(before, after)
            if not conductor_software.matches_ignore(os.path.relpath(path, root), ignore)
        ]
        if changed:
            # Name the paths. Measured 2026-11-10, Job 32 record-8: the round said
            # "tampered" with `passed: true` and no attribution, and the reader could
            # not tell that the MAKER's turn had passed and the EVALUATOR's own run had
            # written into the tree. A verdict that does not name its cause costs a round.
            rows.append(conductor_software.record_arm(exit_code, output) | {
                "parsed": parsed,
                "changed": [os.path.relpath(path, root) for path in changed],
            })
            return TAMPERED, "evaluator", rows, None, False, None, costs, missing
        if exit_code == conductor_software.TIMEOUT or exit_code != 0:
            rows.append(conductor_software.record_arm(exit_code, output) | {"parsed": None})
            return EVALUATOR_FAILED, None, rows, None, False, None, costs, missing
        if parsed is None:
            try:
                parsed = json.loads(output.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                rows.append(conductor_software.record_arm(exit_code, output) | {"parsed": None})
                return EVALUATOR_FAILED, None, rows, None, False, None, costs, missing
        shape = _shape(parsed, bounds)
        rows.append(conductor_software.record_arm(exit_code, output) | {"parsed": parsed})
        if shape:
            # A refusal that names a dimension is a scope refusal, not one of the closed
            # stop words. Its own words are kept on the row so the reader can tell which
            # case was outside the declaration, and the round carries a stop it can name.
            rows[-1]["shape"] = shape
            return (shape if shape in _STATES else SCORING_SET), None, rows, None, False, None, costs, missing
    parsed_rows = _parsed(rows)
    if _split(parsed_rows):
        return EVALUATOR_SPLIT, None, rows, None, False, None, costs, missing
    found = {item["name"]: item["score"] for item in parsed_rows[0]["dimensions"]}
    # Declared order, exactly the declared set: a reader must be able to tell a case
    # that scored from a case that was never scored, and the rule must be handed
    # nothing the packet did not name.
    scores = (
        {name: found[name] for name in declared}
        if declared and all(name in found for name in declared)
        else found
    )
    fired = _class_fired(parsed_rows, packet["escalation"]["classes"])
    mismatch = _mismatch(parsed_rows[0].get("verdict"), scores, packet["bounds"], fired)
    return None, None, rows, scores, mismatch, fired, costs, missing


def _shape(parsed, bounds):
    """Why the Evaluator's reply cannot be admitted, or None when it can.

    ``bounds`` is the packet's, so the declared ``scoring_set`` — never the reply —
    decides the scope. A dimension outside the set and a declared case the reply omits
    are both refused by name: a case outside the set is not scored, and a case the set
    declares is not silently averaged over the rest, because fifteen of sixteen passing
    still leaves one case unmeasured. A packet that declares no set has no scope to
    enforce here and the reply is judged by the shape checks alone, which is the
    behaviour every existing caller already relies on.
    """
    if not isinstance(parsed, dict):
        return EVALUATOR_FAILED
    dims = parsed.get("dimensions")
    if not isinstance(dims, list) or not dims:
        return EVALUATOR_FAILED
    for item in dims:
        if not isinstance(item, dict) or "name" not in item or not _number(item.get("score")):
            return EVALUATOR_FAILED
        if not str(item.get("observation") or "").strip():
            return NO_OBSERVATION
    controls = parsed.get("controls")
    if not isinstance(controls, dict) or "should_pass" not in controls or "should_fail" not in controls:
        return EVALUATOR_FAILED
    if controls.get("should_pass") != "passed" or controls.get("should_fail") != "failed":
        return INSTRUMENT_FAILED
    if parsed.get("verdict") not in _VERDICTS:
        return EVALUATOR_FAILED
    violations = parsed.get("violations")
    if not isinstance(violations, list):
        return EVALUATOR_FAILED
    for item in violations:
        if not isinstance(item, dict) or item.get("class") not in _CLASSES:
            return EVALUATOR_FAILED
    declared = _scored_set(bounds)
    if declared:
        scope = set(declared)
        named = [item.get("name") for item in dims]
        for name in named:
            if name not in scope:
                return "%s: %r is not a case bounds.scoring_set declares" % (SCORING_SET, name)
        held = set(named)
        for name in declared:
            if name not in held:
                return "%s: the reply omits %r, which bounds.scoring_set declares" % (
                    SCORING_SET, name,
                )
    return None


def _parsed(rows):
    return [row["parsed"] for row in rows if row.get("parsed")]


def _split(rows) -> bool:
    if len(rows) < 2:
        return False
    first = rows[0]
    for other in rows[1:]:
        if other.get("verdict") != first.get("verdict"):
            return True
        a = {item["name"]: item["score"] for item in first["dimensions"]}
        b = {item["name"]: item["score"] for item in other["dimensions"]}
        if a != b:
            return True
    return False


def _class_fired(rows, classes) -> str | None:
    listed = set(classes or [])
    for row in rows:
        for item in row.get("violations") or []:
            if item.get("class") in listed:
                return item["class"]
    return None


def _pass_rule(scores, bounds):
    values = list(scores.values())
    mean = sum(values) / len(values)
    low = min(values)
    if mean >= bounds["T_accept"] and low >= bounds["T_dim"]:
        return ACCEPTED
    if low < bounds["T_reject"]:
        return REJECTED
    return "regenerate"


def _mismatch(verdict, scores, bounds, fired) -> bool:
    if fired:
        return verdict != "needs_owner"
    applied = _pass_rule(scores, bounds)
    expected = {"accepted": "accept", "rejected": "reject", "regenerate": "regenerate"}[applied]
    return verdict != expected


def _better(new, old) -> bool:
    if set(new) != set(old):
        return False
    improved = any(new[name] > old[name] for name in old)
    worse = any(new[name] < old[name] for name in old)
    return improved and not worse


def _held_out(text, paths) -> bool:
    """True if a held-out file's sha256 or one of its lines is in ``text``.

    A path that cannot be opened and read raises ``OSError`` naming the path
    and the OS error: the check was not made, so it is neither "no leak" nor
    a leak. A line with no alphanumeric character (``{``, ``},``) is not
    evidence; every other line is, however short.
    """
    for path in paths:
        try:
            data = open(path, "rb").read()
        except OSError as exc:
            raise OSError("held-out path %s cannot be read: %s" % (path, exc)) from exc
        if hashlib.sha256(data).hexdigest() in text:
            return True
        for line in data.decode("utf-8", "replace").splitlines():
            if any(ch.isalnum() for ch in line) and line in text:
                return True
    return False


def _take_cost(path):
    try:
        body = json.load(open(path))
    except (OSError, json.JSONDecodeError):
        return None
    amount = body.get("amount") if isinstance(body, dict) else None
    if not _number(amount):
        return None
    return float(amount)


def _editable_dir(record_dir, number):
    return os.path.join(record_dir, "round-%02d" % number, "editable")


def _snapshot_editable(root, editable, dest):
    os.makedirs(dest, exist_ok=True)
    for rel in editable:
        if os.path.isabs(rel):
            continue
        src = os.path.join(root, rel)
        if not os.path.lexists(src):
            continue
        if not _inside(os.path.realpath(src), root):
            continue
        target = os.path.join(dest, rel)
        if os.path.isdir(src):
            shutil.copytree(src, target, dirs_exist_ok=True, symlinks=True)
        elif os.path.isfile(src):
            parent = os.path.dirname(target)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(src, target)


def _clear(path):
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def _restore(root, editable, snap):
    for rel in editable:
        if os.path.isabs(rel):
            continue
        live = os.path.join(root, rel)
        saved = os.path.join(snap, rel)
        if not os.path.lexists(saved):
            _clear(live)
            continue
        _clear(live)
        if os.path.isdir(saved) and not os.path.islink(saved):
            shutil.copytree(saved, live, symlinks=True)
        elif os.path.isfile(saved):
            parent = os.path.dirname(live)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(saved, live)


def _write_round(
    record_dir, number, result, findings_sha, held, evaluator_rows, reading, pass_rule, mismatch, best_round,
    cost, stop, started_at, ended_at,
):
    path = os.path.join(record_dir, "round-%02d.json" % number)
    _dump(path, {
        "round": number,
        "run": result,
        "findings_sha256": findings_sha or conductor_software.NOT_RECORDED,
        "held_out": held,
        "evaluator": evaluator_rows or [],
        "reading": reading,
        "pass_rule": pass_rule,
        "verdict_mismatch": bool(mismatch),
        "best_round": best_round,
        "cost": cost,
        "stop": stop,
        "started_at": started_at,
        "ended_at": ended_at,
    })


def _dump(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(body, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _sha_file(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _tree_sha(path) -> str:
    digest = hashlib.sha256()
    if not os.path.exists(path):
        return digest.hexdigest()
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, path).replace(os.sep, "/")
            digest.update(rel.encode("utf-8"))
            with open(full, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()
