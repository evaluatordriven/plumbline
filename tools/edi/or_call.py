#!/usr/bin/env python3
"""tools/edi/or_call.py: one logged OpenRouter chat call for a job seat.

This is the product-harness version of the frozen job-1 harness.  It keeps the
job-1 log shape (so kit/custody_history.read_log can read it) and adds the job
spend file, per-call GET /api/v1/key checks, --max-cost and a mocked transport.

    or_call.py --seat maker --log custody/evidence/harness-maker.log \
               --model MODEL --tag TAG --pin-provider PROVIDER \
               --messages msgs.json --out reply.txt \
               --job-spend job-spend.json [--call NAME] [--max-cost USD]
    (or take tag + provider from the ledger: --ledger inputs/custody-events.jsonl)

The job spend file is required for calls, --init-spend and --spend-status:
    {job_id, bound_usd, reserve_usd, spend_ledger,
     prices: [{model, tag, prompt_usd_per_token,
               completion_usd_per_token, max_completion_tokens}]}

Exit codes: 0 logged and served by the pin · 2 usage/key/job-spend error,
nothing sent · 3 HTTP/transport error (logged when a request was sent) ·
4 REFUSED: served by another provider, a fallback was tried, or the response
does not say who served it (logged, no --out) · 5 served by the pin but no
/api/v1/generation reply (logged, --out written) · 6 refused by the job spend
bound (nothing sent, no log entry) · 8 refused by --max-cost before sending
(nothing sent, no log entry) · 9 over the cap after settle (logged, settle line
over_cap, no --out).
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://openrouter.ai/api/v1"
# Key file: --key-file, else $OPENROUTER_KEY_FILE, else ~/.openrouter-key. Mode must be 600.
KEY_FILE = os.environ.get("OPENROUTER_KEY_FILE") or os.path.expanduser("~/.openrouter-key")
META_HEADER = ("X-OpenRouter-Metadata", "enabled")
REDACTED = "Bearer [REDACTED]"
# Header names whose values are credentials or session state; matched case-insensitively.
SECRET_HEADERS = frozenset({
    "authorization", "proxy-authorization", "x-api-key", "api-key", "apikey",
    "x-auth-token", "x-access-token", "x-refresh-token", "x-session-token",
    "x-amz-security-token", "x-goog-api-key", "openai-api-key", "anthropic-api-key",
    "cookie", "set-cookie", "set-cookie2", "cookie2",
})
HARNESS_NAME = "tools/edi/or_call.py"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def file_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def writer() -> str:
    return f"{HARNESS_NAME}@{file_sha256()[:12]}"


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _secret_header(name: str) -> bool:
    n = str(name).strip().lower()
    return (n in SECRET_HEADERS or "cookie" in n or "api-key" in n or "apikey" in n
            or "secret" in n or "password" in n or n.endswith("authorization")
            or n.endswith("-token"))


def log_safe_headers(h: dict) -> dict:
    """Copy of headers fit for a log: credential and cookie values masked.

    Names are matched case-insensitively and kept as given. An Authorization
    (or Proxy-Authorization) value that was Bearer becomes 'Bearer [REDACTED]';
    every other masked value becomes '[REDACTED]'. Harmless headers (Date,
    CF-Ray, Content-Type, X-OpenRouter-Metadata, ...) are kept unchanged.
    """
    out = {}
    for k, v in (h or {}).items():
        if not _secret_header(k):
            out[k] = v
        elif (str(k).strip().lower().endswith("authorization") and isinstance(v, str)
              and v.strip().lower().startswith("bearer")):
            out[k] = REDACTED
        else:
            out[k] = "[REDACTED]"
    return out


def norm(v) -> str:
    return re.sub(r"[^a-z0-9]", "", str(v or "").lower())


class Transport:
    """urllib transport; tests swap it for a fake. Returns (status, headers, body)."""

    def request(self, method: str, url: str, headers: dict, body: bytes | None, timeout: float = 300):
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, dict(r.headers.items()), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers.items()) if e.headers else {}, e.read()


class MockTransport:
    """No network.  Replies come from DIR/key.json, DIR/chat.json, DIR/generation.json.

    Each reply file is {"status": N, "headers": {...}, "body": <JSON>}.  Every
    request is appended to DIR/requests.jsonl as {"method", "url", "at"} with a
    real OpenRouter URL and no headers or key material.
    """

    def __init__(self, directory: str):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.requests = self.dir / "requests.jsonl"

    def _record(self, method: str, url: str) -> None:
        with open(self.requests, "a", encoding="utf-8") as f:
            f.write(json.dumps({"method": method, "url": url, "at": now()}, sort_keys=True) + "\n")

    def _reply(self, name: str):
        p = self.dir / name
        if not p.is_file():
            raise FileNotFoundError(str(p))
        data = json.loads(p.read_text(encoding="utf-8"))
        status = int(data.get("status", 200))
        headers = dict(data.get("headers") or {})
        body = data.get("body", {})
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        return status, headers, raw

    def request(self, method: str, url: str, headers: dict, body: bytes | None, timeout: float = 300):
        self._record(method, url)
        if method == "GET" and url.endswith("/key"):
            return self._reply("key.json")
        if method == "POST" and url.endswith("/chat/completions"):
            return self._reply("chat.json")
        if method == "GET" and "/generation" in url:
            return self._reply("generation.json")
        raise FileNotFoundError(f"no mock reply for {method} {url}")


def read_key(path: str, allow_missing: bool = False) -> str:
    p = Path(path)
    if not p.is_file():
        if allow_missing:
            return "mock-key"
        die(f"or_call: no key file at {path}", 2)
    mode = stat.S_IMODE(p.stat().st_mode)
    if mode & 0o077:
        die(f"or_call: key file {path} is readable by group/other (mode {oct(mode)}); chmod 600 it", 2)
    key = p.read_text(encoding="utf-8").strip()
    if not key:
        die(f"or_call: key file {path} is empty", 2)
    return key


def load_job_spend(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        die(f"or_call: no job spend file at {path}", 2)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"or_call: job spend file {path} is not JSON: {exc}", 2)
    if not isinstance(data, dict):
        die(f"or_call: job spend file {path} must be a JSON object", 2)
    for k in ("job_id", "bound_usd", "reserve_usd", "spend_ledger", "prices"):
        if k not in data:
            die(f"or_call: job spend file {path} is missing {k!r}", 2)
    try:
        float(data["bound_usd"])
        float(data["reserve_usd"])
    except (TypeError, ValueError):
        die(f"or_call: job spend file {path} has a non-numeric bound_usd or reserve_usd", 2)
    if not isinstance(data["spend_ledger"], str) or not data["spend_ledger"]:
        die(f"or_call: job spend file {path} has no spend_ledger path", 2)
    if not isinstance(data["prices"], list) or not data["prices"]:
        die(f"or_call: job spend file {path} has no prices snapshot", 2)
    for entry in data["prices"]:
        if not isinstance(entry, dict):
            die(f"or_call: job spend file {path} has a non-object price entry", 2)
        for k in ("model", "tag", "prompt_usd_per_token", "completion_usd_per_token", "max_completion_tokens"):
            if k not in entry:
                die(f"or_call: job spend price entry is missing {k!r}", 2)
        try:
            float(entry["prompt_usd_per_token"])
            float(entry["completion_usd_per_token"])
            int(entry["max_completion_tokens"])
        except (TypeError, ValueError):
            die(f"or_call: job spend price entry has a non-numeric value", 2)
    return data


def pin_from_ledger(ledger: str, seat: str) -> tuple[str, str]:
    p = Path(ledger)
    if not p.is_file():
        die(f"or_call: no ledger at {ledger}", 2)
    try:
        rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except Exception as exc:
        die(f"or_call: ledger {ledger} is not JSON lines: {exc}", 2)
    pins = [e for e in rows if isinstance(e, dict) and e.get("event") == "pin" and e.get("seat") == seat]
    if not pins:
        die(f"or_call: ledger {ledger} has no pin for seat {seat!r} (custody_ledger.py pin first)", 2)
    last = pins[-1]
    if not last.get("slug") or not last.get("provider"):
        die(f"or_call: ledger {ledger} has an incomplete pin for seat {seat!r}", 2)
    return str(last["slug"]), str(last["provider"])


def served_by(resp: dict, gen: dict | None) -> tuple[dict, list]:
    """({source: provider}, [providers tried]) as the response and generation reply state them."""
    served, tried = {}, []
    if isinstance(resp, dict):
        if resp.get("provider"):
            served["response.provider"] = str(resp["provider"])
        om = resp.get("openrouter_metadata") if isinstance(resp.get("openrouter_metadata"), dict) else {}
        sel = [e.get("provider") for e in ((om.get("endpoints") or {}).get("available") or [])
               if isinstance(e, dict) and e.get("selected") and e.get("provider")]
        if sel:
            served["openrouter_metadata.endpoints.selected"] = str(sel[-1])
        tried += [str(a.get("provider")) for a in (om.get("attempts") or [])
                  if isinstance(a, dict) and a.get("provider")]
    if isinstance(gen, dict):
        g = gen.get("data") if isinstance(gen.get("data"), dict) else gen
        if g.get("provider_name"):
            served["generation.provider_name"] = str(g["provider_name"])
        tried += [str(x.get("provider_name") or x.get("provider")) for x in (g.get("provider_responses") or [])
                  if isinstance(x, dict) and (x.get("provider_name") or x.get("provider"))]
    return served, tried


def pin_ok(name, provider: str, tag: str) -> bool:
    n = norm(name)
    return bool(n) and n in {norm(provider), norm(tag.split("/")[0])}


def append_entry(log: Path, entry: dict, key: str) -> None:
    text = json.dumps(entry, ensure_ascii=False)
    if key and key in text:
        die("or_call: the log entry would contain the key; nothing written", 2)
    items = []
    if log.exists() and log.stat().st_size:
        try:
            items = json.loads(log.read_text(encoding="utf-8"))
        except Exception as exc:
            die(f"or_call: {log} is not JSON: {exc}", 2)
        if not isinstance(items, list):
            die(f"or_call: {log} is not a JSON list harness log; refusing to append", 2)
    items.append(entry)
    log.parent.mkdir(parents=True, exist_ok=True)
    tmp = log.with_suffix(log.suffix + ".tmp")
    tmp.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, log)


def _ledger_rows(ledger: Path) -> list:
    if not ledger.exists():
        return []
    rows = []
    for ln in ledger.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            rows.append(json.loads(ln))
    return rows


def ledger_spent(ledger: Path) -> float:
    rows = _ledger_rows(ledger)
    settled = {}
    reserved = {}
    for r in rows:
        if r.get("event") == "settle":
            settled[str(r.get("id"))] = float(r.get("cost_usd", 0.0))
        elif r.get("event") == "reserve":
            reserved[str(r.get("id"))] = float(r.get("worst_usd", 0.0))
    total = sum(settled.values())
    total += sum(worst for rid, worst in reserved.items() if rid not in settled)
    return total


def last_settle_at(ledger: Path):
    vals = [r.get("at") for r in _ledger_rows(ledger)
            if r.get("event") == "settle" and r.get("at")]
    return max(vals) if vals else None


def _append_ledger(ledger: Path, row: dict) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


class SpendLock:
    def __init__(self, ledger: Path):
        self.path = ledger.parent / ".spend.lock"

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(self.path, "a")
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def key_usage(a, key: str, t) -> float | None:
    try:
        status, _, raw = t.request("GET", f"{a.base_url}/key",
                                   {"Authorization": f"Bearer {key}"}, None, timeout=60)
        if status != 200:
            return None
        u = json.loads(raw.decode("utf-8")).get("data", {}).get("usage")
        return float(u) if u is not None else None
    except Exception:
        return None


def guard_state(a, job: dict, key: str, t, ledger: Path, allow_zero_baseline: bool = False) -> dict:
    base_f = ledger.parent / "key-usage-baseline.json"
    st = {
        "ledger": str(ledger),
        "ledger_spent_usd": round(ledger_spent(ledger), 6),
        "bound_usd": float(job["bound_usd"]),
        "reserve_usd": float(job["reserve_usd"]),
        "key_usage_baseline": None,
        "key_usage_now": None,
        "key_usage_delta_usd": None,
    }
    now_u = key_usage(a, key, t)
    if now_u is None:
        st["error"] = "could not read key usage (GET /api/v1/key)"
        return st
    st["key_usage_now"] = now_u
    if base_f.exists():
        try:
            baseline = float(json.loads(base_f.read_text(encoding="utf-8"))["usage"])
        except Exception as exc:
            st["error"] = f"cannot read key-usage baseline {base_f}: {exc}"
            return st
    elif allow_zero_baseline and now_u == 0:
        baseline = 0.0
    else:
        st["error"] = (f"no key-usage baseline at {base_f} "
                       "(run --init-spend once, before the job's first call)")
        return st
    st["key_usage_baseline"] = baseline
    st["key_usage_delta_usd"] = round(now_u - baseline, 6)
    st["spent_usd"] = round(max(st["ledger_spent_usd"], st["key_usage_delta_usd"]), 6)
    st["headroom_usd"] = round(st["bound_usd"] - st["reserve_usd"] - st["spent_usd"], 6)
    return st


def init_spend(a, job: dict, transport=None) -> int:
    t = transport or (MockTransport(a.mock_transport) if a.mock_transport else Transport())
    ledger = Path(job["spend_ledger"])
    base_f = ledger.parent / "key-usage-baseline.json"
    if ledger.exists() or base_f.exists():
        print(f"or_call: {ledger} or {base_f} already exists; --init-spend runs once per job",
              file=sys.stderr)
        return 2
    key = read_key(a.key_file, allow_missing=bool(a.mock_transport))
    u = key_usage(a, key, t)
    if u is None:
        print("or_call: could not read key usage", file=sys.stderr)
        return 3
    ledger.parent.mkdir(parents=True, exist_ok=True)
    base_f.write_text(json.dumps({"job": job["job_id"], "usage": u, "at": now(), "writer": writer()}) + "\n",
                      encoding="utf-8")
    print(json.dumps({"baseline": str(base_f), "usage": u}))
    return 0


def spend_status(a, job: dict, transport=None) -> int:
    t = transport or (MockTransport(a.mock_transport) if a.mock_transport else Transport())
    ledger = Path(job["spend_ledger"])
    base_f = ledger.parent / "key-usage-baseline.json"
    key = read_key(a.key_file, allow_missing=bool(a.mock_transport))
    u = key_usage(a, key, t)
    baseline = None
    if base_f.exists():
        try:
            baseline = float(json.loads(base_f.read_text(encoding="utf-8"))["usage"])
        except Exception:
            baseline = None
    delta = round(u - baseline, 6) if u is not None and baseline is not None else None
    ledger_sum = round(ledger_spent(ledger), 6)
    total = round(max(ledger_sum, delta), 6) if delta is not None else ledger_sum
    data = {
        "read_at": now(),
        "writer": writer(),
        "job_id": job["job_id"],
        "key_usage_usd": u,
        "baseline_usd": baseline,
        "key_delta_usd": delta,
        "ledger_sum_usd": ledger_sum,
        "total_usd": total,
        "last_settle_at": last_settle_at(ledger),
    }
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(data))
    return 0 if u is not None else 3


def call(a, job: dict, transport=None, sleep=time.sleep) -> int:
    t = transport or (MockTransport(a.mock_transport) if a.mock_transport else Transport())
    name = Path(a.log).name
    if not re.fullmatch(r"harness-[A-Za-z0-9._-]+\.log", name):
        print(f"or_call: log name {name!r} must be harness-<seat>[-...].log", file=sys.stderr)
        return 2
    if not name.startswith(f"harness-{a.seat}"):
        print(f"or_call: log {name!r} is not this seat's (harness-{a.seat}*.log)", file=sys.stderr)
        return 2
    if a.ledger:
        tag, provider = pin_from_ledger(a.ledger, a.seat)
        if a.tag and a.tag != tag:
            print(f"or_call: --tag {a.tag} differs from the ledger pin {tag}", file=sys.stderr)
            return 2
    else:
        tag, provider = a.tag, a.pin_provider
    if not tag or not provider:
        print("or_call: need --tag and --pin-provider, or --ledger", file=sys.stderr)
        return 2
    price = None
    for entry in job["prices"]:
        if entry.get("model") == a.model and entry.get("tag") == tag:
            price = entry
            break
    if price is None:
        print(f"or_call: ({a.model}, {tag}) is not in the job spend price snapshot; refusing",
              file=sys.stderr)
        return 2
    p_in = float(price["prompt_usd_per_token"])
    p_out = float(price["completion_usd_per_token"])
    max_out = int(price["max_completion_tokens"])
    if a.max_tokens is None:
        a.max_tokens = max_out
    elif a.max_tokens != max_out:
        print(f"or_call: --max-tokens {a.max_tokens} != endpoint max {max_out}; "
              "throttling is not allowed", file=sys.stderr)
        return 2
    try:
        messages = json.loads(Path(a.messages).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"or_call: cannot read --messages {a.messages}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(messages, list):
        print("or_call: --messages must hold a JSON list of chat messages", file=sys.stderr)
        return 2
    key = read_key(a.key_file, allow_missing=bool(a.mock_transport))
    ledger = Path(job["spend_ledger"])
    worst = len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) * p_in + a.max_tokens * p_out
    if a.max_cost is not None and worst > a.max_cost:
        print(f"or_call: REFUSED by --max-cost before sending "
              f"(worst case {worst:.8f} > {a.max_cost})", file=sys.stderr)
        return 8
    call_name = a.call or f"{a.seat}_call"
    with SpendLock(ledger):
        st = guard_state(a, job, key, t, ledger, allow_zero_baseline=bool(a.mock_transport))
        st.update({"call": call_name, "seat": a.seat, "model": a.model, "tag": tag,
                   "worst_usd": round(worst, 6)})
        if "error" in st or st["spent_usd"] + worst + float(job["reserve_usd"]) >= float(job["bound_usd"]):
            st["decision"] = "REFUSED"
            print(json.dumps(st), file=sys.stderr)
            print(f"or_call: REFUSED by the job spend guard "
                  f"({st.get('error') or 'spent + worst case + reserve >= bound'}); "
                  "nothing sent, nothing logged", file=sys.stderr)
            return 6
        st["decision"] = "ALLOWED"
        rid = uuid.uuid4().hex
        _append_ledger(ledger, {
            "event": "reserve", "id": rid, "at": now(), "job": job["job_id"],
            "seat": a.seat, "call": call_name, "model": a.model, "tag": tag,
            "max_tokens": a.max_tokens, "worst_usd": round(worst, 8),
            "spent_before_usd": st["spent_usd"],
        })
    holder = {}
    rc = 3
    try:
        rc = _send(a, t, sleep, key, tag, provider, messages, call_name, holder)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"or_call: internal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        rc = 3
    finally:
        resp, gen = holder.get("resp"), holder.get("gen")
        cost, src = worst, "worst case (no cost stated)"
        g = (gen.get("data") if isinstance(gen, dict) and isinstance(gen.get("data"), dict) else gen) or {}
        u = (resp.get("usage") if isinstance(resp, dict) else None) or {}
        if isinstance(g, dict) and g.get("total_cost") is not None:
            cost, src = float(g["total_cost"]), "generation.total_cost"
        elif isinstance(u, dict) and u.get("cost") is not None:
            cost, src = float(u["cost"]), "response.usage.cost"
        elif holder.get("status") not in (None, 200) and not (isinstance(resp, dict) and resp.get("id")):
            cost, src = 0.0, (f"HTTP {holder.get('status')} without a generation id "
                              "(not billed; key usage reconciles)")
        over_cap = bool(a.max_cost is not None and cost > a.max_cost
                        and src in ("generation.total_cost", "response.usage.cost"))
        holder["over_cap"] = over_cap
        holder["cost_usd"] = cost
        with SpendLock(ledger):
            settle = {"event": "settle", "id": rid, "at": now(), "job": job["job_id"],
                      "call": call_name, "cost_usd": cost, "source": src}
            if over_cap:
                settle["over_cap"] = True
            _append_ledger(ledger, settle)
    if holder.get("over_cap"):
        print(f"or_call: OVER CAP after settle (cost {holder.get('cost_usd')} > {a.max_cost}); "
              "logged, no reply written", file=sys.stderr)
        return 9
    if rc in (0, 5) and a.out and "content" in holder:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(holder["content"], encoding="utf-8")
    return rc


def _send(a, t, sleep, key, tag, provider, messages, call_name, holder) -> int:
    body = {"model": a.model, "messages": messages,
            "provider": {"order": [tag], "allow_fallbacks": False, "zdr": True},
            "max_tokens": a.max_tokens}
    if a.temperature is not None:
        body["temperature"] = a.temperature
    url = f"{a.base_url}/chat/completions"
    send_headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                    META_HEADER[0]: META_HEADER[1]}
    log_headers = log_safe_headers(send_headers)
    entry = {
        "call": call_name,
        "seat": a.seat,
        "request": {"method": "POST", "url": url, "headers": log_headers, "body": body},
        "harness": {"name": HARNESS_NAME, "sha256": file_sha256()},
    }
    entry["sent_at"] = now()
    try:
        status, hdrs, raw = t.request("POST", url, send_headers, json.dumps(body).encode())
    except Exception as exc:
        entry.update({
            "received_at": now(),
            "response_status": None,
            "response_headers": {},
            "response": None,
            "transport_error": f"{type(exc).__name__}: {exc}",
            "generation": None,
            "generation_status": None,
            "generation_fetched_at": None,
            "verdict": {"ok": False, "refusal": "transport error"},
        })
        append_entry(Path(a.log), entry, key)
        print(f"or_call: transport error, logged: {type(exc).__name__}", file=sys.stderr)
        return 3
    entry["received_at"] = now()
    entry["response_status"], entry["response_headers"] = status, log_safe_headers(hdrs)
    holder["status"] = status
    try:
        resp = json.loads(raw.decode("utf-8"))
    except ValueError:
        resp = {"_raw_text": raw.decode("utf-8", "replace")}
    entry["response"] = resp
    holder["resp"] = resp
    if status != 200 or not isinstance(resp, dict) or not resp.get("id"):
        entry.update({
            "generation": None,
            "generation_status": None,
            "generation_fetched_at": None,
            "verdict": {"ok": False, "refusal": f"HTTP {status}"},
        })
        append_entry(Path(a.log), entry, key)
        print(f"or_call: HTTP {status}, logged", file=sys.stderr)
        return 3
    gen, gstatus = None, None
    for attempt in range(a.gen_tries):
        gurl = f"{a.base_url}/generation?id={resp['id']}"
        try:
            gstatus, _, graw = t.request("GET", gurl, {"Authorization": f"Bearer {key}"},
                                         None, timeout=60)
            if gstatus == 200:
                gen = json.loads(graw.decode("utf-8"))
                break
        except Exception as exc:
            gstatus = f"{type(exc).__name__}"
        if attempt + 1 < a.gen_tries:
            sleep(a.gen_wait)
    entry["generation"], entry["generation_status"], entry["generation_fetched_at"] = gen, gstatus, now()
    holder["gen"] = gen
    served, tried = served_by(resp, gen)
    bad = {s: n for s, n in served.items() if not pin_ok(n, provider, tag)}
    fallback = sorted({n for n in tried if not pin_ok(n, provider, tag)})
    refusal = None
    if not served:
        refusal = "the response and generation reply do not say which provider served the call"
    elif bad:
        refusal = "served by " + ", ".join(f"{n!r} ({s})" for s, n in bad.items()) + \
                  f", not the pin {provider!r} ({tag})"
    elif fallback:
        refusal = f"a fallback was tried: {fallback}"
    entry["verdict"] = {
        "pin": {"tag": tag, "provider": provider},
        "served_by": served,
        "tried": tried,
        "ok": refusal is None,
        "refusal": refusal,
        "generation_reply": gen is not None,
    }
    append_entry(Path(a.log), entry, key)
    content = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    holder["content"] = content
    if refusal:
        print(f"or_call: REFUSED ({refusal}); logged to {a.log}; no reply written", file=sys.stderr)
        return 4
    if gen is None:
        print(f"or_call: served by the pin, but no /api/v1/generation reply after "
              f"{a.gen_tries} tries (last status {gstatus}); logged with generation null",
              file=sys.stderr)
        return 5
    print(json.dumps({
        "logged": a.log,
        "call": entry["call"],
        "id": resp["id"],
        "served_by": served,
        "date": next((v for k, v in hdrs.items() if k.lower() == "date"), None),
    }))
    return 0


def check_key(a, transport=None) -> int:
    """Read-only GET /api/v1/key: proves the key works; prints only status, limit and usage."""
    t = transport or (MockTransport(a.mock_transport) if a.mock_transport else Transport())
    key = read_key(a.key_file, allow_missing=bool(a.mock_transport))
    status, _, raw = t.request("GET", f"{a.base_url}/key", {"Authorization": f"Bearer {key}"},
                               None, timeout=60)
    d = json.loads(raw.decode("utf-8")).get("data", {}) if status == 200 else {}
    print(json.dumps({"status": status, "limit": d.get("limit"), "usage": d.get("usage")}))
    return 0 if status == 200 else 3


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="One logged OpenRouter call for a job seat.")
    ap.add_argument("--key-file", default=KEY_FILE)
    ap.add_argument("--base-url", default=BASE)
    ap.add_argument("--check-key", action="store_true", help="read-only GET /api/v1/key, then exit")
    ap.add_argument("--seat")
    ap.add_argument("--log")
    ap.add_argument("--model")
    ap.add_argument("--tag")
    ap.add_argument("--pin-provider")
    ap.add_argument("--ledger")
    ap.add_argument("--messages")
    ap.add_argument("--out")
    ap.add_argument("--call")
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--temperature", type=float)
    ap.add_argument("--gen-tries", type=int, default=6)
    ap.add_argument("--gen-wait", type=float, default=5.0)
    ap.add_argument("--job-spend")
    ap.add_argument("--mock-transport")
    ap.add_argument("--init-spend", action="store_true",
                    help="record the key-usage baseline once, then exit")
    ap.add_argument("--spend-status", action="store_true",
                    help="write or print guard state, then exit")
    ap.add_argument("--max-cost", type=float)
    ap.add_argument("--spend-ledger", help=argparse.SUPPRESS)
    return ap


def main(argv=None) -> int:
    a = parser().parse_args(argv)
    if a.check_key:
        return check_key(a)
    if a.init_spend:
        if not a.job_spend:
            print("or_call: --job-spend is required", file=sys.stderr)
            return 2
        return init_spend(a, load_job_spend(a.job_spend))
    if a.spend_status:
        if not a.job_spend:
            print("or_call: --job-spend is required", file=sys.stderr)
            return 2
        return spend_status(a, load_job_spend(a.job_spend))
    if not a.job_spend:
        print("or_call: --job-spend is required", file=sys.stderr)
        return 2
    job = load_job_spend(a.job_spend)
    for k in ("seat", "log", "model", "messages"):
        if not getattr(a, k):
            print(f"or_call: --{k.replace('_', '-')} is required", file=sys.stderr)
            return 2
    return call(a, job)


if __name__ == "__main__":
    sys.exit(main())
