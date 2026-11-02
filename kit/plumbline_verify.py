#!/usr/bin/env python3
"""Verify a custody/v1 record at two layers: the standard checker, then x-plumbline.

The standard layer is `checker/check.py` from the pinned custody checkout. It knows nothing about `x-` keys
(SPEC.md line 141): it reads the custody/v1 predicate and ignores every extension. The Plumbline layer is this
file: it runs the standard checker FIRST, then enforces the `x-plumbline` block the record carries.

    plumbline_verify.py --record R --files F --evidence E --ledger L --custody <checkout> [--json OUT]

There is no switch that relaxes a check. The hand-time allowance is read from the record, never from the command
line. Exit codes:
  0  OK at both layers
  3  the standard layer failed (kind `standard`; nothing else is checked)
  4  the standard layer passed and a Plumbline check failed
  2  cannot run (usage, a missing input, or a checker whose sha256 is not the pin)

Every failure prints one line: `FAIL <kind> <field> <file>:<line>` for exits 3 and 4, and every such line names a
non-empty file: a finding about the record itself names the `--record` path. On exit 3 the FAIL line is followed
by one indented line per requirement the standard checker reports FAILED, `  <id> FAILED: <detail>` (for a
checker that prints no JSON report, its own output lines, each prefixed `checker:`). An exit-2 line starts
`NOT CHECKABLE:` instead, because `FAIL <kind>` lines are reserved for the two layers' findings. Kinds: standard,
schema, allowance, hand-time-unflagged, flag-without-source, events, relay-as-approval, spend, shadow.

This file must not import the record emitter (V7): the emitter's logic is checked by separate code. It may use
kit/custody_history.py to parse harness logs.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import custody_history as H  # noqa: E402

SCHEMA_VERSION = "plumbline/x-plumbline/v1"
SCHEMA_PATH = REPO / "schemas" / "x-plumbline" / "x-plumbline-v1.schema.json"
SPEND_TOL = 0.0001
LEDGER_REL = "inputs/custody-events.jsonl"
# The record path given by --record: a finding about the record names it, never an empty file field.
RECORD_PATH: Path | None = None
OWNED = ("verdict", "gaps", "times", "time_tolerance_s", "hand_times", "allowances",
         "generations", "evaluations", "relays", "amendments", "spend", "schema")
# A tool's writer stamp: a .py path under kit/ and 12 lowercase hex (V3). Checked by form only.
WRITER_FORM = re.compile(r"^kit/[A-Za-z0-9_./-]+\.py@[0-9a-f]{12}$")


def file_sha(p: Path) -> str:
    return sha256(Path(p).read_bytes()).hexdigest()


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def relpath(job: Path, p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(Path(job).resolve()).as_posix()
    except ValueError:
        return str(Path(p).resolve())


def ledger_lines(p: Path) -> list[tuple[int, dict]]:
    out: list[tuple[int, dict]] = []
    if not Path(p).is_file():
        return out
    for n, ln in enumerate(Path(p).read_text(encoding="utf-8").splitlines(), 1):
        if not ln.strip():
            continue
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        if isinstance(e, dict):
            e["_line"] = n
            out.append((n, e))
    return out


def writer_source(e: dict):
    w = e.get("writer")
    if w == "hand":
        return "ledger-hand"
    if w in (None, ""):
        return "ledger-no-writer"
    return None


def allowance_writer_ok(w) -> bool:
    """A tool's writer stamp by form: `<relative .py path under kit/>@<12 lowercase hex>`, never `hand`."""
    return isinstance(w, str) and WRITER_FORM.match(w) is not None and ".." not in w


def line_of(path: Path, value, key: str | None = None):
    if value in (None, "") or not Path(path).is_file():
        return None
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    vs = str(value)
    hits = [n for n, ln in enumerate(lines, 1) if vs in ln and (key is None or f'"{key}"' in ln)]
    if not hits:
        hits = [n for n, ln in enumerate(lines, 1) if vs in ln]
    return hits[0] if hits else None


def bar_path(job: Path, custody_json: Path) -> Path:
    """The job's bar file: `bar.file` in inputs/custody.json, relative to the job, default `custody/bar.md`."""
    try:
        ci = load(custody_json) if Path(custody_json).is_file() else {}
    except Exception:
        ci = {}
    rel = ((ci.get("bar") or {}).get("file")) or "custody/bar.md"
    p = Path(rel)
    return p if p.is_absolute() else Path(job) / p


def used_seats(ci: dict) -> set[str]:
    seats: set[str] = set()
    m = ci.get("maker") or {}
    if m.get("kind") == "model":
        seats.add("maker")
    for e in ci.get("evaluators") or []:
        if e.get("kind") == "model":
            seats.add(str(e.get("id")))
    return seats


def evidence_dirs(job: Path, ev: Path, ci: dict) -> list[Path]:
    """Where harness logs can be: the verifier's --evidence, the inputs' evidence_dir, and the job itself."""
    out = [Path(ev)]
    rel = (ci.get("evidence_dir") if isinstance(ci, dict) else None) or "custody/evidence"
    out.append(Path(job) / rel)
    out.append(Path(job))
    seen: set[str] = set()
    uniq: list[Path] = []
    for d in out:
        r = str(Path(d).resolve())
        if r not in seen:
            seen.add(r)
            uniq.append(Path(d))
    return uniq


def find_log(job: Path, dirs: list[Path], rel: str | None, pattern: str | None):
    if rel:
        for base in dirs:
            p = Path(base) / rel
            if p.is_file():
                return p
        return None
    hits: list[Path] = []
    seen: set[str] = set()
    for base in dirs:
        if not Path(base).is_dir() or not pattern:
            continue
        for p in sorted(Path(base).glob(pattern)):
            k = str(p.resolve())
            if k not in seen:
                seen.add(k)
                hits.append(p)
    return hits[0] if len(hits) == 1 else None


def read_calls(job: Path, ev_dir: Path, ci: dict):
    by: dict[str, dict] = {}
    allc: list = []
    dirs = evidence_dirs(job, ev_dir, ci)

    def add(seat: str, log):
        if not log:
            return
        try:
            calls = H.read_log(Path(log), H.Refusals(), str(seat))
        except Exception:
            return
        d = by.setdefault(str(seat), {})
        for c in calls:
            name = getattr(c, "name", None) or str(getattr(c, "i", ""))
            d[name] = c
            allc.append(c)

    if isinstance(ci, dict):
        m = ci.get("maker") or {}
        if m.get("kind") == "model":
            add("maker", find_log(job, dirs, m.get("harness_log"), "harness-maker*.log"))
        for e in ci.get("evaluators") or []:
            if e.get("kind") == "model":
                rel = e.get("harness_log") or next(
                    (x.get("evidence_file") for x in ci.get("external") or []
                     if x.get("subject") == e.get("id")), None)
                add(str(e.get("id")), find_log(job, dirs, rel, None))
    if not allc:
        for base in dirs:
            if Path(base).is_dir():
                for log in sorted(Path(base).glob("*.log")):
                    add(log.stem, log)
    return by, allc


def call_cost(c) -> float:
    """A harness call's billed cost, in the order the job's harness uses for its own settle lines: the
    generation reply's `data.total_cost` when present, else the chat reply's `usage.cost` (V5)."""
    raw = getattr(c, "raw", None)
    if not isinstance(raw, dict):
        return 0.0
    gen = raw.get("generation") if isinstance(raw.get("generation"), dict) else None
    if gen is not None:
        data = gen.get("data") if isinstance(gen.get("data"), dict) else gen
        v = data.get("total_cost") if isinstance(data, dict) else None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    resp = raw.get("response") if isinstance(raw.get("response"), dict) else {}
    usage = resp.get("usage") if isinstance(resp.get("usage"), dict) else {}
    v = usage.get("cost") if isinstance(usage, dict) else None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    return 0.0


def call_time(c):
    return getattr(c, "started", None) or getattr(c, "at", None)


def ledger_array(lines: list[tuple[int, dict]], event: str, ledger_rel: str) -> list[dict]:
    return [{**{k: v for k, v in e.items() if k != "_line"},
             "source": f"{ledger_rel}:{e['_line']}"}
            for _, e in lines if e.get("event") == event]


def last_spend_line(lines: list[tuple[int, dict]]):
    sp = None
    for _, e in lines:
        if e.get("event") == "spend":
            sp = e
    return sp


def compute_spend_block(lines: list[tuple[int, dict]], all_calls, ledger_rel: str) -> dict:
    sp = last_spend_line(lines)
    calls_sum = round(sum(call_cost(c) for c in all_calls if getattr(c, "at", None)), 6)
    key_delta = float(sp.get("key_delta_usd") or 0) if sp else 0.0
    return {"calls_sum_usd": calls_sum,
            "key_delta_usd": key_delta,
            "total_usd": max(calls_sum, key_delta),
            "tolerance_usd": SPEND_TOL,
            "source": f"{ledger_rel}:{sp['_line']}" if sp else None}


def hand_key(e: dict):
    try:
        line = int(e.get("line")) if e.get("line") is not None else None
    except (TypeError, ValueError):
        line = None
    return (e.get("field"), e.get("file"), line, e.get("source"))


def hand_sort(k) -> tuple:
    """A total order over hand-time keys: a missing line sorts first, and nothing compares None with an int."""
    line = k[2] if isinstance(k[2], int) and not isinstance(k[2], bool) else -1
    return (str(k[0]), str(k[1]), line, str(k[3]))


def hand_time_set(job: Path, ledger_path: Path, custody_path: Path, record: dict, evidence: Path) -> list[dict]:
    ci = load(custody_path) if Path(custody_path).is_file() else {}
    lines = ledger_lines(ledger_path)
    ledger_rel = relpath(job, ledger_path)
    try:
        inputs_rel = relpath(job, custody_path)
    except Exception:
        inputs_rel = str(custody_path)
    seats = used_seats(ci)
    calls_by_seat, all_calls = read_calls(job, evidence, ci)
    hand: dict[str, dict] = {}
    seen: set = set()

    def mark(field: str, file: str, line, source: str) -> None:
        hand[field] = {"field": field, "file": file, "line": line, "source": source}

    for n, e in lines:
        src = writer_source(e)
        ev = e.get("event")
        field = None
        if ev == "freeze":
            seen.add("freeze")
            field = "bar.frozenAt"
        elif ev == "approve":
            role = e.get("role")
            seen.add(("approve", role))
            for i, a in enumerate((ci.get("bar") or {}).get("approvals") or []):
                if a.get("role") == role:
                    f = f"bar.approvals[{i}].at"
                    if src:
                        mark(f, ledger_rel, n, src)
                    else:
                        hand.pop(f, None)
            continue
        elif ev == "dispose":
            seen.add("dispose")
            field = "disposition.at"
        elif ev == "pin":
            seat = e.get("seat")
            seen.add(("pin", seat))
            if seat in seats:
                field = f"routing.{seat}.declaredAt"
        else:
            continue
        if field:
            if src:
                mark(field, ledger_rel, n, src)
            else:
                hand.pop(field, None)

    bar = ci.get("bar") or {}
    if "freeze" not in seen and bar.get("frozenAt"):
        mark("bar.frozenAt", inputs_rel, line_of(custody_path, bar.get("frozenAt"), "frozenAt"),
             "inputs-no-ledger")
    for i, a in enumerate(bar.get("approvals") or []):
        if ("approve", a.get("role")) not in seen and a.get("at"):
            mark(f"bar.approvals[{i}].at", inputs_rel, line_of(custody_path, a.get("at"), "at"),
                 "inputs-no-ledger")
    for seat in seats:
        if ("pin", seat) not in seen:
            pin = (ci.get("routing") or {}).get(seat) or {}
            if pin.get("declaredAt"):
                mark(f"routing.{seat}.declaredAt", inputs_rel,
                     line_of(custody_path, pin.get("declaredAt"), "declaredAt"), "inputs-no-ledger")
    if "dispose" not in seen:
        d = ci.get("disposition") or {}
        if d.get("at"):
            mark("disposition.at", inputs_rel, line_of(custody_path, d.get("at"), "at"), "inputs-no-ledger")

    # A typed startedAt/producedAt is a hand time whether or not the maker has a logged call (V3): the tool's
    # time is the log's, and a time typed into custody.json has no tool behind it (as for pass and control times).
    if ci.get("startedAt"):
        mark("startedAt", inputs_rel, line_of(custody_path, ci.get("startedAt"), "startedAt"),
             "inputs-no-ledger")
    if ci.get("producedAt"):
        mark("producedAt", inputs_rel, line_of(custody_path, ci.get("producedAt"), "producedAt"),
             "inputs-no-ledger")

    # A typed pass or control time is a hand time whether or not a harness call is linked: the tool's time is
    # the log's, and a time typed into custody.json has no tool behind it (the emitter's rule, V3).
    for pid, f in (ci.get("passes") or {}).items():
        if not isinstance(f, dict) or not f.get("at"):
            continue
        mark(f"passes.{pid}.at", inputs_rel, line_of(custody_path, f.get("at"), "at"),
             "inputs-no-ledger")

    for k in ci.get("controls") or []:
        if not k.get("at"):
            continue
        mark(f"controls[{k.get('id')}].at", inputs_rel, line_of(custody_path, k.get("at"), "at"),
             "inputs-no-ledger")

    # A call the logger did not stamp `sent_at`/`received_at` carries a server time: a hand time (T7b, V3).
    logs: list[Path] = []
    for base in evidence_dirs(job, evidence, ci):
        if Path(base).is_dir():
            logs += sorted(Path(base).glob("*.log"))
    for log in dict.fromkeys(logs):
        try:
            calls = H.read_log(Path(log), H.Refusals(), "verify")
        except Exception:
            continue
        for c in calls:
            try:
                entries = c.hand_time_entries()
            except Exception:
                entries = []
            for e in entries:
                if isinstance(e, dict) and e.get("field"):
                    hand[str(e["field"])] = e
    return [hand[k] for k in sorted(hand)]


def check_hand_times(hand: list[dict], record: dict, record_path: Path | None = None) -> list[dict]:
    fails: list[dict] = []
    rp = str(record_path) if record_path is not None else "<record>"
    xp = (record.get("predicate") or {}).get("x-plumbline") if isinstance(record, dict) else None
    if not isinstance(xp, dict):
        return fails
    flags = xp.get("hand_times")
    if not isinstance(flags, list):
        return fails
    recomp = {hand_key(e) for e in hand if isinstance(e, dict)}
    got = {hand_key(e) for e in flags if isinstance(e, dict)}
    for k in sorted(recomp - got, key=hand_sort):
        fails.append({"kind": "hand-time-unflagged", "field": k[0], "file": k[1] or rp,
                      "line": k[2] if isinstance(k[2], int) and not isinstance(k[2], bool) else 0})
    for k in sorted(got - recomp, key=hand_sort):
        fails.append({"kind": "flag-without-source", "field": k[0], "file": k[1] or rp,
                      "line": k[2] if isinstance(k[2], int) and not isinstance(k[2], bool) else 0})
    if recomp:
        allowances = xp.get("allowances")
        allowance = allowances.get("hand_times") if isinstance(allowances, dict) else None
        if not isinstance(allowance, dict):
            fails.append({"kind": "allowance", "field": "x-plumbline.allowances.hand_times",
                          "file": rp, "line": 0})
        else:
            if allowance.get("switch") != "--allow-hand-times":
                fails.append({"kind": "allowance", "field": "x-plumbline.allowances.hand_times.switch",
                              "file": rp, "line": 0})
            if not allowance_writer_ok(allowance.get("writer")):
                fails.append({"kind": "allowance", "field": "x-plumbline.allowances.hand_times.writer",
                              "file": rp, "line": 0})
            if not H.parse_ts(allowance.get("at")):
                fails.append({"kind": "allowance", "field": "x-plumbline.allowances.hand_times.at",
                              "file": rp, "line": 0})
    return fails


def check_events(job: Path, ledger_path: Path, record: dict, calls_by_seat: dict) -> list[dict]:
    fails: list[dict] = []
    xp = (record.get("predicate") or {}).get("x-plumbline") if isinstance(record, dict) else None
    if not isinstance(xp, dict):
        return fails
    lines = ledger_lines(ledger_path)
    ledger_rel = relpath(job, ledger_path)
    for ev, key in (("generation", "generations"), ("evaluation", "evaluations"),
                    ("relay", "relays"), ("amendment", "amendments")):
        expected = ledger_array(lines, ev, ledger_rel)
        got = xp.get(key)
        if got != expected:
            fails.append({"kind": "events", "field": f"x-plumbline.{key}", "file": str(ledger_path), "line": 0})

    for _, e in lines:
        if e.get("event") != "evaluation":
            continue
        vf = e.get("verdict_file")
        want = e.get("verdict_sha256")
        if not vf:
            continue
        p = Path(vf) if Path(vf).is_absolute() else Path(job) / vf
        if not p.is_file() or file_sha(p) != want:
            fails.append({"kind": "events", "field": f"evaluations[{e.get('batch')}].verdict_sha256",
                          "file": vf, "line": e.get("_line", 0)})

    opens: dict = {}
    closes: dict = {}
    for _, e in lines:
        if e.get("event") != "generation":
            continue
        k = (e.get("seat"), e.get("n"))
        if e.get("action") == "open":
            opens[k] = e
        elif e.get("action") == "close":
            closes[k] = e
    maker_calls = list((calls_by_seat.get("maker") or {}).values())
    for k, o in opens.items():
        c = closes.get(k)
        if not c:
            fails.append({"kind": "events", "field": f"generations[{k[0]}#{k[1]}].close",
                          "file": str(ledger_path), "line": o.get("_line", 0)})
            continue
        t0, t1 = H.parse_ts(o.get("at")), H.parse_ts(c.get("at"))
        if t0 and t1:
            found = any(call_time(x) and t0 <= call_time(x) <= t1 for x in maker_calls)
            if not found:
                fails.append({"kind": "events", "field": f"generations[{k[0]}#{k[1]}].calls",
                              "file": str(ledger_path), "line": o.get("_line", 0)})

    relays = [e for _, e in lines if e.get("event") == "relay"]
    approvals = ((record.get("predicate") or {}).get("bar") or {}).get("approvals") or []
    for r in relays:
        for a in approvals:
            if (a.get("kind") == "relay" or a.get("relay") or a.get("role") == "relay"
                    or a.get("by") == r.get("from") or a.get("quote") == r.get("quote")):
                fails.append({"kind": "relay-as-approval", "field": "predicate.bar.approvals",
                              "file": str(ledger_path), "line": r.get("_line", 0)})
                break
    return fails


def check_spend(job: Path, ledger_path: Path, record: dict, all_calls) -> list[dict]:
    fails: list[dict] = []
    xp = (record.get("predicate") or {}).get("x-plumbline") if isinstance(record, dict) else None
    if not isinstance(xp, dict):
        return fails
    lines = ledger_lines(ledger_path)
    ledger_rel = relpath(job, ledger_path)
    expected = compute_spend_block(lines, all_calls, ledger_rel)
    sp = xp.get("spend")
    if not isinstance(sp, dict):
        return [{"kind": "spend", "field": "x-plumbline.spend", "file": str(ledger_path), "line": 0}]
    for k in ("calls_sum_usd", "key_delta_usd", "total_usd", "tolerance_usd"):
        if k not in sp:
            fails.append({"kind": "spend", "field": f"x-plumbline.spend.{k}", "file": str(ledger_path), "line": 0})
    calls_sum = float(sp.get("calls_sum_usd") or 0)
    key_delta = float(sp.get("key_delta_usd") or 0)
    total = float(sp.get("total_usd") or 0)
    tol = float(sp.get("tolerance_usd") or 0)
    if abs(calls_sum - expected["calls_sum_usd"]) > SPEND_TOL:
        fails.append({"kind": "spend", "field": "x-plumbline.spend.calls_sum_usd",
                      "file": str(ledger_path), "line": 0})
    if abs(key_delta - expected["key_delta_usd"]) > 1e-9:
        fails.append({"kind": "spend", "field": "x-plumbline.spend.key_delta_usd",
                      "file": str(ledger_path), "line": 0})
    if abs(total - max(calls_sum, key_delta)) > 1e-9:
        fails.append({"kind": "spend", "field": "x-plumbline.spend.total_usd",
                      "file": str(ledger_path), "line": 0})
    if abs(tol - SPEND_TOL) > 1e-12:
        fails.append({"kind": "spend", "field": "x-plumbline.spend.tolerance_usd",
                      "file": str(ledger_path), "line": 0})

    # V5 does not require a spend-ledger line: with none, the block above is the expected one (key_delta 0,
    # total = the calls sum, source null). The settle and key-reading checks apply to the spend line when there
    # is one.
    sp_line = last_spend_line(lines)
    if sp_line:
        lp = Path(sp_line.get("spend_ledger") or "")
        if not lp.is_absolute():
            lp = Path(job) / lp
        if not lp.is_file():
            fails.append({"kind": "spend", "field": "spend_ledger", "file": str(lp), "line": sp_line.get("_line", 0)})
        else:
            labels = {getattr(c, "name", None) or str(getattr(c, "i", "")) for c in all_calls}
            for n, ln in enumerate(lp.read_text(encoding="utf-8").splitlines(), 1):
                if not ln.strip():
                    continue
                try:
                    x = json.loads(ln)
                except ValueError:
                    continue
                if x.get("event") == "settle":
                    call = x.get("call") or x.get("id")
                    if call and call not in labels:
                        fails.append({"kind": "spend", "field": f"settle[{call}]",
                                      "file": str(lp), "line": n})
        rp = Path(sp_line.get("key_reading") or "")
        if not rp.is_absolute():
            rp = Path(job) / rp
        if not rp.is_file():
            fails.append({"kind": "spend", "field": "key_reading", "file": str(rp), "line": sp_line.get("_line", 0)})
        else:
            try:
                r = load(rp)
            except Exception:
                r = {}
            if not r.get("read_at") or not r.get("writer"):
                fails.append({"kind": "spend", "field": "key_reading.read_at",
                              "file": str(rp), "line": 0})
            else:
                read_at = H.parse_ts(r.get("read_at"))
                last = H.parse_ts(sp_line.get("last_settle_at"))
                if read_at and last and (read_at - last).total_seconds() < 180:
                    fails.append({"kind": "spend", "field": "key_reading.read_at",
                                  "file": str(rp), "line": 0})
                if abs(float(r.get("key_delta_usd") or 0) - key_delta) > 1e-6:
                    fails.append({"kind": "spend", "field": "key_reading.key_delta_usd",
                                  "file": str(rp), "line": 0})
    return fails


def check_shadow(job: Path, ledger_path: Path, record: dict, all_calls, hand: list[dict],
                 calls_by_seat: dict) -> list[dict]:
    fails: list[dict] = []
    xp = (record.get("predicate") or {}).get("x-plumbline") if isinstance(record, dict) else None
    if not isinstance(xp, dict):
        return fails
    inputs = xp.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    lines = ledger_lines(ledger_path)
    ledger_rel = relpath(job, ledger_path)
    derived: dict = {
        "schema": SCHEMA_VERSION,
        "time_tolerance_s": H.TOLERANCE_S,
        "hand_times": hand,
        "generations": ledger_array(lines, "generation", ledger_rel),
        "evaluations": ledger_array(lines, "evaluation", ledger_rel),
        "relays": ledger_array(lines, "relay", ledger_rel),
        "amendments": ledger_array(lines, "amendment", ledger_rel),
        "spend": compute_spend_block(lines, all_calls, ledger_rel),
    }
    s5 = xp.get("s5_record") or {}
    if s5.get("name"):
        p = Path(s5["name"]) if Path(s5["name"]).is_absolute() else Path(job) / s5["name"]
        if p.is_file():
            try:
                rec = load(p)
                if "verdict" in rec:
                    derived["verdict"] = rec.get("verdict")
            except Exception:
                pass
    mcalls = calls_by_seat.get("maker") or {}
    derived["times"] = {"startedAt": "harness log" if mcalls else "hand-entered",
                        "producedAt": "harness log" if mcalls else "hand-entered"}

    for key in OWNED:
        if key not in derived or key not in xp:
            continue
        if key == "hand_times":
            if {hand_key(e) for e in xp.get(key) or [] if isinstance(e, dict)} != \
                    {hand_key(e) for e in derived[key] or [] if isinstance(e, dict)}:
                fails.append({"kind": "shadow", "field": f"x-plumbline.{key}",
                              "file": str(ledger_path), "line": 0})
        elif xp.get(key) != derived[key]:
            fails.append({"kind": "shadow", "field": f"x-plumbline.{key}",
                          "file": str(ledger_path), "line": 0})
    for key in OWNED:
        if key in inputs and key in xp and key in derived:
            if xp.get(key) == inputs.get(key) and xp.get(key) != derived[key]:
                fails.append({"kind": "shadow", "field": f"x-plumbline.inputs.{key}",
                              "file": str(ledger_path), "line": 0})
    return fails


def _type_ok(v, t: str) -> bool:
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "string":
        return isinstance(v, str)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "null":
        return v is None
    return True


def _validate(inst, sch, root, path: str) -> list[tuple[str, str]]:
    errs: list[tuple[str, str]] = []
    if sch is True or sch == {}:
        return errs
    if sch is False:
        return [(path, "false schema")]
    if "$ref" in sch:
        ref = sch["$ref"]
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.split("/")[-1]
            return _validate(inst, root["$defs"][name], root, path)
        return errs
    if "const" in sch and inst != sch["const"]:
        errs.append((path, "const"))
    if "enum" in sch and inst not in sch["enum"]:
        errs.append((path, "enum"))
    if "type" in sch:
        ts = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_type_ok(inst, t) for t in ts):
            errs.append((path, "type"))
    for sub in sch.get("allOf") or []:
        errs += _validate(inst, sub, root, path)
    if "anyOf" in sch:
        if not any(not _validate(inst, sub, root, path) for sub in sch["anyOf"]):
            errs.append((path, "anyOf"))
    if "oneOf" in sch:
        ok = sum(1 for sub in sch["oneOf"] if not _validate(inst, sub, root, path))
        if ok != 1:
            errs.append((path, "oneOf"))
    if isinstance(inst, dict):
        for r in sch.get("required") or []:
            if r not in inst:
                errs.append((path + "." + r, "required"))
        props = sch.get("properties") or {}
        for k, v in inst.items():
            if k in props:
                errs += _validate(v, props[k], root, path + "." + k)
            else:
                ap = sch.get("additionalProperties", True)
                if ap is False:
                    errs.append((path + "." + k, "additionalProperties"))
                elif isinstance(ap, dict):
                    errs += _validate(v, ap, root, path + "." + k)
    if isinstance(inst, list) and "items" in sch:
        for i, v in enumerate(inst):
            errs += _validate(v, sch["items"], root, f"{path}[{i}]")
    if isinstance(inst, str):
        if "minLength" in sch and len(inst) < sch["minLength"]:
            errs.append((path, "minLength"))
        if "pattern" in sch and not re.search(sch["pattern"], inst):
            errs.append((path, "pattern"))
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in sch and inst < sch["minimum"]:
            errs.append((path, "minimum"))
        if "maximum" in sch and inst > sch["maximum"]:
            errs.append((path, "maximum"))
    return errs


def iter_xplumbline(obj, path: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if k == "x-plumbline":
                yield p, v
            else:
                yield from iter_xplumbline(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from iter_xplumbline(v, f"{path}[{i}]")


def check_schema(record: dict, schema_path: Path, record_path: Path | None = None) -> list[dict]:
    fails: list[dict] = []
    rp = str(record_path) if record_path is not None else "<record>"
    if not Path(schema_path).is_file():
        return [{"kind": "schema", "field": "schema file", "file": str(schema_path), "line": 0}]
    try:
        schema = load(schema_path)
    except Exception:
        return [{"kind": "schema", "field": "schema file", "file": str(schema_path), "line": 0}]
    for p, _ in _validate(record, schema, schema, "$"):
        fails.append({"kind": "schema", "field": p, "file": str(schema_path), "line": 0})
    xp = (record.get("predicate") or {}).get("x-plumbline") if isinstance(record, dict) else None
    if not isinstance(xp, dict):
        fails.append({"kind": "schema", "field": "predicate.x-plumbline", "file": rp, "line": 0})
        return fails
    for p, _ in _validate(xp, schema["$defs"]["xPlumbline"], schema, "x-plumbline"):
        fails.append({"kind": "schema", "field": p, "file": str(schema_path), "line": 0})
    if xp.get("schema") != SCHEMA_VERSION:
        fails.append({"kind": "schema", "field": "x-plumbline.schema", "file": rp, "line": 0})
    for p, val in iter_xplumbline(record):
        if p == "predicate.x-plumbline":
            continue
        for q, _ in _validate(val, schema["$defs"]["xNested"], schema, p):
            fails.append({"kind": "schema", "field": q, "file": str(schema_path), "line": 0})
    return fails


def _strip_sha(v):
    if isinstance(v, str):
        v = v.strip()
        if v.startswith("sha256:"):
            v = v[7:]
        return v
    return v


def _is_pin(v) -> bool:
    v = _strip_sha(v)
    return isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) is not None


def _find_pin_in(obj, sha: str):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str):
                vv = _strip_sha(v)
                if vv == sha:
                    return vv
                if vv.startswith("aaeb7e05") and vv.endswith("bcd18"):
                    return vv
                if "checker/check.py" in str(k) and _is_pin(v):
                    return vv
            if isinstance(v, dict):
                path = str(v.get("path") or v.get("file") or "")
                if "checker/check.py" in path:
                    for kk in ("sha256", "digest", "hash"):
                        if _is_pin(v.get(kk)):
                            return _strip_sha(v.get(kk))
                r = _find_pin_in(v, sha)
                if r:
                    return r
            if isinstance(v, list):
                r = _find_pin_in(v, sha)
                if r:
                    return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_pin_in(v, sha)
            if r:
                return r
    return None


def find_pin(custody: Path, check: Path):
    sha = file_sha(check)
    for p in (Path(custody) / "tools" / "pin.json", REPO / "tools" / "pin.json"):
        if not p.is_file():
            continue
        try:
            doc = load(p)
        except Exception:
            continue
        found = _find_pin_in(doc, sha)
        if found:
            return found
    return None


def _find_checker(custody: Path):
    for rel in ("checker/check.py", "check.py", "tools/checker/check.py"):
        p = Path(custody) / rel
        if p.is_file():
            return p
    p = REPO / "checker" / "check.py"
    return p if p.is_file() else None


def standard_check(record: Path, files: Path, evidence: Path, custody: Path, bar: Path | None):
    """Run the pinned checker once: `check.py RECORD --files FILES --evidence EVIDENCE --bar BAR` (V1).

    The pinned checker needs the bar file (the record's `bar.frozenAt` and approvals are checked against it), so
    the verifier passes the job's bar: `bar.file` in inputs/custody.json, relative to the job, default
    `custody/bar.md`. The checker reads the claimed level from the record and knows nothing about `x-` keys.
    Exit 0 = OK; any other exit is the standard layer's failure (exit 3). A missing checker, a missing pin or a
    checker whose bytes are not the pin is exit 2: this tool cannot run.
    """
    check = _find_checker(custody)
    if check is None:
        return 2, None, f"checker/check.py not found under {custody}"
    pin = find_pin(custody, check)
    if pin is None:
        return 2, None, f"no pin names {check}"
    if file_sha(check) != pin:
        return 2, None, f"pinned checker {check} bytes are not the pin"
    cmd = [sys.executable, str(check), str(record),
           "--files", str(files), "--evidence", str(evidence)]
    if bar is not None:
        cmd += ["--bar", str(bar)]
    rv = subprocess.run(cmd, capture_output=True, text=True)
    return (0 if rv.returncode == 0 else 1), rv, ""


def checker_reasons(rv) -> list[str]:
    """Why the pinned checker failed the record, one line per requirement it reports FAILED.

    The custody checker prints a JSON report on stdout: `requirements` maps each id to `{status, detail}`. Each
    `FAILED` requirement gives one line, `<id> FAILED: <detail>`; a `NOT-CHECKABLE` one (blocked by another) is not
    a failing requirement and gives none. A checker whose output is not that report (a stand-in, or a crash) gives
    its own non-empty output lines instead, so the reason is never thrown away.
    """
    if rv is None:
        return []
    out = []
    try:
        doc = json.loads(rv.stdout)
        reqs = doc.get("requirements") if isinstance(doc, dict) else None
    except ValueError:
        reqs = None
    if isinstance(reqs, dict):
        for rid, r in reqs.items():
            if isinstance(r, dict) and r.get("status") == "FAILED":
                detail = " ".join(str(r.get("detail") or "").split())
                out.append(f"{rid} FAILED: {detail}" if detail else f"{rid} FAILED")
        if out or doc.get("verdict"):
            return out or [f"checker verdict {doc.get('verdict')} (exit {rv.returncode}), no requirement FAILED"]
    for stream in (rv.stdout, rv.stderr):
        out += [f"checker: {ln.strip()}" for ln in (stream or "").splitlines() if ln.strip()]
    return out or [f"checker exit {rv.returncode} with no output"]


def snapshot(paths) -> dict:
    out: dict = {}
    for p in paths:
        p = Path(p)
        if p.is_file():
            out[str(p)] = file_sha(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    out[str(f)] = file_sha(f)
    return out


def _loc(f: dict, fallback: str) -> tuple[str, int]:
    """A failure's file and line: never an empty file, always a non-negative integer line."""
    file = f.get("file")
    if not isinstance(file, str) or not file.strip():
        file = fallback
    line = f.get("line")
    if not isinstance(line, int) or isinstance(line, bool) or line < 0:
        line = 0
    return file, line


def finish(code: int, failures: list[dict], json_out: str | None) -> int:
    fallback = str(RECORD_PATH) if RECORD_PATH is not None else "<record>"
    rows = []
    for f in failures:
        file, line = _loc(f, fallback)
        rows.append({**f, "file": file, "line": line})
    for f in rows:
        if code == 2:
            msg = f.get("message") or f.get("field")
            print(f"NOT CHECKABLE: {msg} ({f['file']}:{f['line']})")
        else:
            print(f"FAIL {f.get('kind')} {f.get('field')} {f['file']}:{f['line']}")
            for why in f.get("reasons") or []:
                print(f"  {why}")
    if json_out:
        Path(json_out).write_text(json.dumps({"exit": code, "failures": rows}, indent=2) + "\n",
                                  encoding="utf-8")
    return code


def main(argv=None) -> int:
    global RECORD_PATH
    ap = argparse.ArgumentParser(description="Verify a custody/v1 record at the standard and Plumbline layers.")
    ap.add_argument("--record", required=True)
    ap.add_argument("--files", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--custody", required=True)
    ap.add_argument("--json")
    a = ap.parse_args(argv)

    record = Path(a.record).expanduser()
    RECORD_PATH = record
    files = Path(a.files).expanduser()
    evidence = Path(a.evidence).expanduser()
    ledger = Path(a.ledger).expanduser()
    custody = Path(a.custody).expanduser()

    if not record.is_file():
        return finish(2, [{"kind": "standard", "field": "record", "file": str(record), "line": 0,
                           "message": f"record {record} not found"}], a.json)
    if not ledger.is_file():
        return finish(2, [{"kind": "standard", "field": "ledger", "file": str(ledger), "line": 0,
                           "message": f"ledger {ledger} not found"}], a.json)
    if not custody.is_dir():
        return finish(2, [{"kind": "standard", "field": "custody", "file": str(custody), "line": 0,
                           "message": f"custody checkout {custody} not found"}], a.json)

    job = ledger.parent.parent if ledger.parent.name == "inputs" else files
    if not (job / "packet.json").is_file() and (evidence.parent.parent / "packet.json").is_file():
        job = evidence.parent.parent
    custody_json = ledger.parent / "custody.json"
    bar = bar_path(job, custody_json)
    if not Path(bar).is_file():
        return finish(2, [{"kind": "standard", "field": "bar", "file": str(bar), "line": 0,
                           "message": f"bar file {bar} not found"}], a.json)

    before = snapshot([record, files, evidence, ledger])
    code, rv, why = standard_check(record, files, evidence, custody, bar)
    if code == 2:
        return finish(2, [{"kind": "standard", "field": "pinned checker", "file": str(custody),
                           "line": 0, "message": why}], a.json)
    if code != 0:
        return finish(3, [{"kind": "standard", "field": "record", "file": str(record), "line": 0,
                           "reasons": checker_reasons(rv)}], a.json)

    try:
        rec = load(record)
    except Exception:
        return finish(2, [{"kind": "standard", "field": "record", "file": str(record), "line": 0,
                           "message": f"record {record} is not JSON"}], a.json)

    failures = check_schema(rec, SCHEMA_PATH, record)
    if failures:
        return finish(4, failures, a.json)

    ci = load(custody_json) if custody_json.is_file() else {}
    calls_by_seat, all_calls = read_calls(job, evidence, ci)
    hand = hand_time_set(job, ledger, custody_json, rec, evidence)

    failures += check_hand_times(hand, rec, record)
    failures += check_events(job, ledger, rec, calls_by_seat)
    failures += check_spend(job, ledger, rec, all_calls)
    failures += check_shadow(job, ledger, rec, all_calls, hand, calls_by_seat)

    after = snapshot([record, files, evidence, ledger])
    if before != after:
        failures.append({"kind": "writes", "field": "inputs", "file": str(job), "line": 0})

    return finish(4 if failures else 0, failures, a.json)


if __name__ == "__main__":
    sys.exit(main())
