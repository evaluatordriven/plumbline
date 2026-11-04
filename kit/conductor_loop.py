"""The mechanical half of the Orchestrator: rounds, the pass rule, the record.

This is not the conductor. It dispatches one turn at a time by calling
kit.conductor_run.run. It does not score, diagnose, or decide. It sends
nothing and never restarts a stopped job. The conductor is still unbuilt.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time

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
    NOT_DISPATCHED: ("needs_owner", "needs_owner"),
    PACKET_REFUSED: ("needs_owner", "needs_owner"),
}

_CLASSES = {
    "artifact_missed_standard",
    "standard_moved",
    "dimension_unauthorized",
    "frame_at_fault",
}
_VERDICTS = {"accept", "regenerate", "needs_owner", "reject"}
_GAP_GATE = (
    "The gate rerun is a script Evaluator reading held in the same module as "
    "Orchestrator dispatch (DOCTRINE D3.holder, rule 5)."
)
_GAP_ARCH = (
    "Architect proposed packet not recorded after seeing drafts "
    "(D3.Architect vs Contracts §4.2); Owner ratification required"
)


def loop(packet, *, record_dir, cwd=None, timeout_s=600, commit=None, evaluator_fn=None) -> dict:
    """Run the rounds the packet names and return the summary record.

    ``packet`` is a path or a loaded dict. A refusal writes ``escalation.json``
    and raises ``ValueError`` before any command runs. Every other end writes
    ``summary.json`` and, unless the stop is accepted, ``escalation.json``.
    This function sends nothing and does not start another loop.
    """
    loaded, packet_sha = _load(packet)
    root = os.path.realpath(cwd) if cwd is not None else os.path.realpath(os.getcwd())
    problems = _problems(loaded, record_dir, root, evaluator_fn)
    os.makedirs(record_dir, exist_ok=True)
    if problems:
        _refuse(record_dir, loaded, problems, packet_sha, commit)
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
        leak = _held_out(json.dumps(findings), loaded["evaluator"].get("held_out") or [])
        findings_path = os.path.join(record_dir, "findings-%02d.json" % number)
        if leak:
            stop = HELD_OUT
            _write_round(
                record_dir, number, None, None, {"method": "line and sha256 scan", "result": "fail", "by": "loop()"},
                None, None, None, False, best_round, 0, stop,
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
                _refuse(record_dir, loaded, [str(exc)], packet_sha, commit)
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
        held = {"method": "line and sha256 scan", "result": "pass" if not leak else "fail", "by": "loop()"}
        _write_round(
            record_dir, number, result, _sha_file(findings_path), held,
            evaluator_rows, reading, pass_rule, mismatch, best_round, round_cost, stop,
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
    state, outcome = _STATES[stop]
    summary_path = os.path.join(record_dir, "summary.json")
    summary = {
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
        "escalation": None,
    }
    if stop != ACCEPTED:
        summary["escalation"] = os.path.join(record_dir, "escalation.json")
    _dump(summary_path, summary)
    if stop != ACCEPTED:
        _dump(summary["escalation"], _escalation(
            loaded, summary, record_dir, round_paths, best_round, by, packet_sha, summary_path,
        ))
    return summary


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


def _refuse(record_dir, packet, problems, packet_sha, commit):
    os.makedirs(record_dir, exist_ok=True)
    _dump(os.path.join(record_dir, "escalation.json"), {
        "terminal_state": "needs_owner",
        "outcome": "needs_owner",
        "stop": PACKET_REFUSED,
        "escalation_kind": "other",
        "route": (packet.get("escalation") or {}).get("route"),
        "human_seat": packet.get("human_seat"),
        "holders": (packet.get("escalation") or {}).get("holders"),
        "problems": problems,
        "question": None,
        "diagnosis": None,
        "why_unobservable": None,
        "options": None,
        "recommendation": None,
        "proposed_packet": None,
        "decision": None,
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
    for path in paths:
        try:
            data = open(path, "rb").read()
        except OSError:
            continue
        if hashlib.sha256(data).hexdigest() in text:
            return True
        for line in data.decode("utf-8", "replace").splitlines():
            if line.strip() and line in text:
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


def _write_round(record_dir, number, result, findings_sha, held, evaluator_rows, reading, pass_rule, mismatch, best_round, cost, stop):
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
    })


def _escalation(packet, summary, record_dir, round_paths, best_round, by, packet_sha, summary_path):
    kind = "other"
    if summary["stop"] == CAP_REACHED:
        kind = "cap_reached"
    elif summary["stop"] == REJECTED:
        kind = "below_floor"
    best = None
    if best_round is not None:
        path = _editable_dir(record_dir, best_round)
        best = {"round": best_round, "editable": path, "sha256": _tree_sha(path)}
    tried = []
    for path in round_paths:
        body = json.load(open(path))
        tried.append({
            "round": body["round"],
            "record": path,
            "record_sha256": _sha_file(path),
            "summary": summary_path,
            "packet_sha256": packet_sha,
            "editable": _editable_dir(record_dir, body["round"]),
            "reading": body.get("reading"),
            "pass_rule": body.get("pass_rule"),
        })
    return {
        "terminal_state": summary["terminal_state"],
        "outcome": summary["outcome"],
        "stop": summary["stop"],
        "by": by,
        "escalation_kind": kind,
        "route": packet["escalation"]["route"],
        "human_seat": packet["human_seat"],
        "holders": packet["escalation"]["holders"],
        "best": best,
        "tried": tried,
        "question": None,
        "diagnosis": None,
        "why_unobservable": None,
        "options": None,
        "recommendation": None,
        "proposed_packet": None,
        "decision": None,
        "packet_sha256": packet_sha,
    }


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
