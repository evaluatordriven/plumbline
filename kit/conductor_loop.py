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

A finish is filed by this module or not filed at all. ``loop()`` writes
``summary.json`` with what the finish says and, for a stop a human must see,
``escalation.json`` beside it, and returns the summary. It files nothing and
raises ``CustodyNotDone`` for the one finish it cannot file cleanly: a run
whose clock was replaced took stamps that are not this module's readings.
``datetime`` is the clock seam, so a replaced clock is visible here; nothing
replaces it in a real run, so a real finish is always filed. ``CustodyNotDone``
is an ``Exception`` and never a ``ValueError``, and its ``exit_code`` is 1, 2
or 3 and never 0. A packet refusal is not a finish: it raises ``ValueError``
and writes ``escalation.json`` with ``started_at`` and ``refused_at``, a later
reading of the same clock, and no ``ended_at``. Nothing reads these fields
back: the deadline and the clock stop stay on the monotonic clock, so a
wall-clock jump changes no stop, state, outcome or round count.

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
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime as _datetime
from datetime import timezone

from kit import conductor_software
from kit.conductor_run import _run, run

ACCEPTED = "accepted"
REJECTED = "rejected"
NO_ARTIFACT = "no artifact"
EVALUATOR_FAILED = "evaluator failed"
NO_OBSERVATION = "no observation"
INSTRUMENT_FAILED = "instrument failed"
EVALUATOR_SPLIT = "evaluator split"
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


def emit_custody_for_finish(record_dir, summary):
    """Run ``kit/emit_custody.py`` against ``record_dir``; return its exit code.

    This is the seam ``loop()`` uses to ship a custody record on a finish. It
    calls the emitter, not the close command; the emitter reads the job
    directory on disk — ``packet.json`` and the round records ``loop()`` has
    written — and writes ``custody/record.custody.json`` at the path the close
    command uses. Exit 0 is the only done: the record was written and names no
    hard gap. Any other exit code is not a done finish.

    ``summary`` is carried for the caller's convenience; it is not forwarded.
    The seam's result is exactly what the same command produces on the same
    directory, so a twin run of the emitter side-by-side matches it.
    """
    emitter = os.path.join(os.path.dirname(os.path.abspath(__file__)), "emit_custody.py")
    proc = subprocess.run(
        [sys.executable, emitter, "--job-dir", str(record_dir)],
        capture_output=True,
        text=True,
    )
    return proc.returncode


def _custody_packet(packet, halt):
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
    """
    descriptor = dict(packet) if isinstance(packet, dict) else {}
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
    return halt


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


def _evaluate(packet, result, number, editable_copy, root, deadline, timeout_s, evaluator_fn, record_dir):
    rows = []
    costs = []
    missing = False
    ignore = packet["artifact"].get("ignore") or []
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
            env = os.environ.copy()
            env["PLUMBLINE_TURN"] = json.dumps(turn)
            env["PLUMBLINE_COST"] = cost_path
            exit_code, output = _run(packet["evaluator"]["cmd"], root, bound, env=env)
            one = _take_cost(cost_path)
            if one is None:
                missing = True
            else:
                costs.append(one)
        after = conductor_software.snapshot(root)
        changed = [
            path for path in conductor_software.changed_paths(before, after)
            if not conductor_software.matches_ignore(os.path.relpath(path, root), ignore)
        ]
        if changed:
            rows.append(conductor_software.record_arm(exit_code, output) | {"parsed": parsed})
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
        shape = _shape(parsed)
        rows.append(conductor_software.record_arm(exit_code, output) | {"parsed": parsed})
        if shape:
            return shape, None, rows, None, False, None, costs, missing
    parsed_rows = _parsed(rows)
    if _split(parsed_rows):
        return EVALUATOR_SPLIT, None, rows, None, False, None, costs, missing
    scores = {item["name"]: item["score"] for item in parsed_rows[0]["dimensions"]}
    fired = _class_fired(parsed_rows, packet["escalation"]["classes"])
    mismatch = _mismatch(parsed_rows[0].get("verdict"), scores, packet["bounds"], fired)
    return None, None, rows, scores, mismatch, fired, costs, missing


def _shape(parsed):
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
