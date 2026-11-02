#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z — S1 instrument, job 2026-10-27-custody-emitter-gaps (author: Chief of Staff (Orchestrator) drafter).
"""Re-derive a custody record's maker times and model endpoints from the ledger and harness logs alone.
Standard library only, no Plumbline code: the stranger step (N8) copies this one file next to the unzipped bundle.

Rules (bar.md "S1 instrument", fixed at freeze):
  maker times         from the maker harness log only (written by freeze/harness/or_call.py), every entry in it:
                      startedAt = the logger's request-send time `sent_at` of the first call (earliest),
                      producedAt = the logger's reply-receive time `received_at` of the last call (latest).
                      Compared at whole seconds UTC ("YYYY-MM-DDTHH:MM:SSZ"; fractions truncated on both sides).
                      An entry without both `sent_at` and `received_at` makes the times underivable (None).
                      Ledger rows, response `created` and the `Date` header are not maker times (bar N1, amendment 1).
  endpoint (per seat) the latest ledger `pin` row for the seat (maker / evaluator id) gives provider + host. The
                      endpoint is that host only if at least one call in the seat's harness log has a non-null
                      /api/v1/generation reply whose provider_name is the pinned provider, and no call's served-by
                      statement (response.provider, generation provider_name) names another provider. Else None.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


def iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s) -> datetime | None:
    if not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).replace(microsecond=0)
    except ValueError:
        return None


def norm(v) -> str:
    return re.sub(r"[^a-z0-9]", "", str(v or "").lower())


def load_log(p: Path) -> list[dict]:
    text = p.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
        items = doc if isinstance(doc, list) else [doc]
    except ValueError:
        items = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
    return [i for i in items if isinstance(i, dict) and "request" in i]


def load_ledger(p: Path | None) -> list[dict]:
    if not p or not p.is_file():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _hdr(h: dict, name: str):
    for k, v in (h or {}).items():
        if k.lower() == name.lower():
            return v
    return None


def maker_times(maker_log: Path | None, ledger: list[dict] | None = None) -> dict:
    """ledger is accepted for interface compatibility and NOT used (amendment 1)."""
    if not (maker_log and maker_log.is_file()):
        return {"events": 0, "startedAt": None, "producedAt": None, "missing_logger_times": []}
    calls = load_log(maker_log)
    sent = [parse_iso(c.get("sent_at")) for c in calls]
    recv = [parse_iso(c.get("received_at")) for c in calls]
    missing = [str(c.get("call") or i) for i, (c, s_, r_) in enumerate(zip(calls, sent, recv)) if not (s_ and r_)]
    if not calls or missing:
        return {"events": len(calls), "startedAt": None, "producedAt": None, "missing_logger_times": missing}
    return {"events": len(calls), "startedAt": iso(min(sent)), "producedAt": iso(max(recv)),
            "missing_logger_times": []}


def same_instant(a, b) -> bool:
    """Two time strings name the same whole second (fractions truncated). None never equals anything."""
    x, y = parse_iso(a), parse_iso(b)
    return x is not None and y is not None and x == y


def served(c: dict) -> list[str]:
    out = []
    resp = c.get("response") if isinstance(c.get("response"), dict) else {}
    if resp.get("provider"):
        out.append(str(resp["provider"]))
    g = c.get("generation")
    if isinstance(g, dict):
        g = g.get("data") if isinstance(g.get("data"), dict) else g
        if g.get("provider_name"):
            out.append(str(g["provider_name"]))
    return out


def reply_provider(c: dict) -> str | None:
    g = c.get("generation")
    if not isinstance(g, dict):
        return None
    g = g.get("data") if isinstance(g.get("data"), dict) else g
    return g.get("provider_name")


def pin_for(ledger: list[dict], seat: str) -> dict | None:
    pins = [r for r in ledger if r.get("event") == "pin" and r.get("seat") == seat]
    return pins[-1] if pins else None


def pin_match(name, pin: dict) -> bool:
    n = norm(name)
    return bool(n) and n in {norm(pin.get("provider")), norm(str(pin.get("slug") or "").split("/")[0])}


def seat_endpoint(log: Path | None, ledger: list[dict], seat: str) -> dict:
    pin = pin_for(ledger, seat)
    if not pin:
        return {"endpoint": None, "why": f"no ledger pin for seat {seat}"}
    if not log or not log.is_file():
        return {"endpoint": None, "why": f"no harness log for seat {seat}"}
    calls = load_log(log)
    others = sorted({s for c in calls for s in served(c) if not pin_match(s, pin)})
    if others:
        return {"endpoint": None, "why": f"served by {others}, not the pin {pin.get('provider')}"}
    ok = [c.get("call") for c in calls if reply_provider(c) and pin_match(reply_provider(c), pin)]
    if not ok:
        return {"endpoint": None, "why": "no non-null /generation reply names the pinned provider"}
    return {"endpoint": pin.get("host"), "why": f"generation replies of {ok} name {pin.get('provider')}; pin host",
            "null_replies": [c.get("call") for c in calls if not isinstance(c.get("generation"), dict)]}


def find_seat_log(ev_dirs: list[Path], seat: str, named: str | None = None) -> Path | None:
    for d in ev_dirs:
        if named and (d / Path(named).name).is_file():
            return d / Path(named).name
    pat = "harness-maker*.log" if seat == "maker" else f"harness-{seat}*.log"
    hits = sorted({p for d in ev_dirs if d.is_dir() for p in d.glob(pat)})
    return hits[0] if len(hits) == 1 else None


def derive(record: dict, ev_dirs: list[Path], ledger_path: Path | None, named_logs: dict | None = None) -> dict:
    """Everything N1/N5/N8 compare: maker times + per-seat endpoints, with the files used."""
    named_logs = named_logs or {}
    ledger = load_ledger(ledger_path)
    pred = record.get("predicate", record)
    mlog = find_seat_log(ev_dirs, "maker", named_logs.get("maker"))
    out = {"ledger": str(ledger_path) if ledger_path and ledger_path.is_file() else None,
           "maker_log": str(mlog) if mlog else None, **maker_times(mlog, ledger), "endpoints": {}}
    if (pred.get("maker") or {}).get("model"):
        out["endpoints"]["maker"] = {**seat_endpoint(mlog, ledger, "maker"), "log": str(mlog) if mlog else None}
    for e in pred.get("evaluators") or []:
        if e.get("model"):
            lg = find_seat_log(ev_dirs, e["id"], named_logs.get(e["id"]))
            out["endpoints"][e["id"]] = {**seat_endpoint(lg, ledger, e["id"]), "log": str(lg) if lg else None}
    return out


def recorded(record: dict) -> dict:
    pred = record.get("predicate", record)
    eps = {}
    if (pred.get("maker") or {}).get("model"):
        eps["maker"] = pred["maker"]["model"].get("endpoint")
    for e in pred.get("evaluators") or []:
        if e.get("model"):
            eps[e["id"]] = e["model"].get("endpoint")
    return {"startedAt": pred.get("startedAt"), "producedAt": pred.get("producedAt"), "endpoints": eps}


if __name__ == "__main__":  # stranger use: derive.py <record> <bundle dir>
    import sys
    rec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    root = Path(sys.argv[2])
    ledgers = sorted(root.rglob("custody-events.jsonl"))
    evd = sorted({p.parent for p in root.rglob("harness-*.log")})
    d = derive(rec, evd, ledgers[0] if len(ledgers) == 1 else None)
    print(json.dumps({"derived": d, "recorded": recorded(rec), "ledgers_found": [str(p) for p in ledgers]}))
