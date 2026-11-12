"""Finish kinds and dual gates — stop one word meaning five things.

Measured pain 2026-11-12 (Job 40 / custody PR #14): loop terminal_state
``accepted`` while custody checker reported FAILED/none on a hollow emit.
Instrument green is not a release record. This module names finishes so
summary.json and status cards cannot collapse them.

job_class (optional on the packet, x-plumbline.job_class or top-level):
  docs_cut | kit_fix | full_release_record | unknown

Gates on every finish:
  instrument_gate — runner/bar cases (loop stop / pass_rule path)
  custody_gate    — emitted record shape vs hollow / missing / not_run
"""
from __future__ import annotations

import json
import os
from typing import Any

JOB_CLASSES = frozenset({
    "docs_cut",
    "kit_fix",
    "full_release_record",
    "unknown",
})

# Budget floors (USD) — soft warn in preflight; not a hard refuse (Owner may override).
BUDGET_FLOOR_USD = {
    "docs_cut": 0.15,
    "kit_fix": 0.40,
    "full_release_record": 1.00,
    "unknown": 0.0,
}

# Predicate paths that, if all empty/null, mean "not a release record" (maintainer check 2026-11-12).
_HOLLOW_BAR_KEYS = ("digest", "frozenAt", "author", "dimensions")
_HOLLOW_MAKER_KEYS = ("name", "kind", "version")
_HOLLOW_INSTRUMENT_KEYS = ("rubric", "runner")


def job_class_of(packet: dict | None) -> str:
    if not isinstance(packet, dict):
        return "unknown"
    raw = packet.get("job_class")
    if not (isinstance(raw, str) and raw.strip()):
        xp_raw = packet.get("x-plumbline")
        xp = xp_raw if isinstance(xp_raw, dict) else {}
        raw = xp.get("job_class")
    if isinstance(raw, str) and raw.strip() in JOB_CLASSES:
        return raw.strip()
    return "unknown"


def budget_floor_usd(job_class: str) -> float:
    return float(BUDGET_FLOOR_USD.get(job_class, 0.0))


def _empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    if isinstance(val, (list, dict)) and len(val) == 0:
        return True
    return False


def hollow_reasons(record: dict | None) -> list[str]:
    """Why a custody envelope is not a release record (empty list = not hollow by these checks)."""
    if not isinstance(record, dict):
        return ["no record object"]
    pred_raw = record.get("predicate")
    if not isinstance(pred_raw, dict):
        return ["predicate missing or not an object"]
    pred: dict = pred_raw
    reasons: list[str] = []
    bar_raw = pred.get("bar")
    bar = bar_raw if isinstance(bar_raw, dict) else {}
    if all(_empty(bar.get(k)) for k in _HOLLOW_BAR_KEYS):
        reasons.append("bar hollow (digest/frozenAt/author/dimensions empty) — a runner is not a bar")
    maker_raw = pred.get("maker")
    maker = maker_raw if isinstance(maker_raw, dict) else {}
    if all(_empty(maker.get(k)) for k in _HOLLOW_MAKER_KEYS):
        reasons.append("maker hollow (name/kind/version empty)")
    inst_raw = pred.get("instrument")
    inst = inst_raw if isinstance(inst_raw, dict) else {}
    if all(_empty(inst.get(k)) for k in _HOLLOW_INSTRUMENT_KEYS):
        reasons.append("instrument hollow (rubric/runner empty)")
    controls = pred.get("controls")
    if _empty(controls):
        reasons.append("controls empty (CR-2 needs a nonempty list)")
    checks_raw = pred.get("checks")
    checks = checks_raw if isinstance(checks_raw, list) else []
    if checks and all(_empty(c.get("outcome")) if isinstance(c, dict) else True for c in checks):
        reasons.append("checks lack outcome (name+score only is not enough)")
    return reasons


def load_custody_record(record_dir: str) -> dict | None:
    path = os.path.join(os.path.abspath(str(record_dir)), "custody", "record.custody.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def instrument_gate(halt: dict | None) -> str:
    """pass | fail | incomplete — from loop halt only."""
    if not isinstance(halt, dict):
        return "incomplete"
    stop = halt.get("stop")
    state = halt.get("terminal_state")
    if stop == "accepted" or state == "accepted":
        return "pass"
    if stop in ("packet refused", "no artifact", "maker failed") or state in ("rejected",):
        return "fail"
    if state == "needs_owner":
        return "fail"
    return "incomplete"


def custody_gate(record_dir: str, *, halt: dict | None = None) -> dict:
    """Shape: {status, reasons, record_present, specVersion?}.

    status: pass | hollow | missing | not_run | error
    """
    out: dict[str, Any] = {
        "status": "not_run",
        "reasons": [],
        "record_present": False,
        "specVersion": None,
        "path": os.path.join(os.path.abspath(str(record_dir)), "custody", "record.custody.json"),
    }
    # Emit only runs on a clean finish path; if no custody dir, missing.
    rec = load_custody_record(record_dir)
    if rec is None:
        status_path = os.path.join(os.path.abspath(str(record_dir)), "custody", "status.json")
        if os.path.isfile(status_path):
            try:
                with open(status_path, encoding="utf-8") as fh:
                    st = json.load(fh)
                if st.get("record_present") is False or st.get("state") in ("missing", "open"):
                    out["status"] = "missing"
                    out["reasons"] = [st.get("why") or "custody status says no record"]
                    return out
            except (OSError, json.JSONDecodeError):
                pass
        out["status"] = "missing"
        out["reasons"] = ["no custody/record.custody.json"]
        return out
    out["record_present"] = True
    pred = rec.get("predicate") if isinstance(rec.get("predicate"), dict) else {}
    out["specVersion"] = pred.get("specVersion")
    reasons = hollow_reasons(rec)
    if reasons:
        out["status"] = "hollow"
        out["reasons"] = reasons
        return out
    out["status"] = "pass"
    out["reasons"] = []
    return out


def attach_gates(halt: dict, record_dir: str, packet: dict | None = None) -> dict:
    """Mutate-copy halt with dual gates + job_class. Never invents terminal_state."""
    h = dict(halt) if isinstance(halt, dict) else {}
    jc = job_class_of(packet if isinstance(packet, dict) else h)
    inst = instrument_gate(h)
    cust = custody_gate(record_dir, halt=h)
    h["job_class"] = jc
    h["instrument_gate"] = inst
    h["custody_gate"] = cust["status"]
    h["gates"] = {
        "job_class": jc,
        "instrument": inst,
        "custody": cust,
        "note": (
            "instrument_gate is the runner/loop finish; custody_gate is the emitted "
            "record shape. Bare 'accepted' without custody pass is not a release."
        ),
    }
    # Honest composite for humans — does not change terminal_state (doctrine terminals stay).
    if inst == "pass" and cust["status"] == "pass":
        h["finish_kind"] = "instrument_and_custody"
    elif inst == "pass" and cust["status"] == "hollow":
        h["finish_kind"] = "instrument_only_hollow_custody"
    elif inst == "pass" and cust["status"] == "missing":
        h["finish_kind"] = "instrument_only_no_custody"
    else:
        h["finish_kind"] = "not_accepted_instrument"
    return h


def status_card_lines(
    *,
    job_id: str | None = None,
    packet_sha: str | None = None,
    job_class: str | None = None,
    instrument_gate: str | None = None,
    custody_gate: str | None = None,
    finish_kind: str | None = None,
    terminal_state: str | None = None,
    outcome: str | None = None,
    stop: str | None = None,
    pr: str | None = None,
    main_version: str | None = None,
    spend: float | None = None,
    budget: float | None = None,
    next_human: str | None = None,
) -> str:
    """One pasteable status block (Telegram-safe: no tables)."""
    lines = [
        "PLUMBLINE STATUS",
        f"job: {job_id or '—'}",
        f"job_class: {job_class or '—'}",
        f"packet_sha: {(packet_sha or '—')[:16]}",
        f"terminal_state: {terminal_state or '—'}  outcome: {outcome or '—'}  stop: {stop or '—'}",
        f"instrument_gate: {instrument_gate or '—'}",
        f"custody_gate: {custody_gate or '—'}",
        f"finish_kind: {finish_kind or '—'}",
        f"PR: {pr or '—'}",
        f"main_version: {main_version or '—'}",
    ]
    if spend is not None or budget is not None:
        lines.append(f"spend: {spend if spend is not None else '—'} / budget {budget if budget is not None else '—'}")
    lines.append(f"next_human: {next_human or '—'}")
    return "\n".join(lines)
