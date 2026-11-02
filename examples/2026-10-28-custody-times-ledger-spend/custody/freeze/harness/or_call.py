#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — part of the freeze set of job 2026-10-28-custody-times-ledger-spend; sha256 in ../../MANIFEST.sha256.
# Derived from job 2026-10-28-doctrine-reader-pointer or_call.py (frozen, sha256 d345c151...7880): JOB_ID, BOUND_USD,
# RESERVE_USD and the snapshot time changed; PRICES re-read from the 2026-10-28T18:55:55Z snapshot (values unchanged).
"""or_call.py: one logged OpenRouter chat call for a seat of an E-DI job (Maker or model evaluator).

    or_call.py --seat maker --log custody/evidence/harness-maker-deepseek.log \
               --model deepseek/deepseek-v4.1-flash-1017 --tag deepinfra/fp8 --pin-provider DeepInfra \
               --messages msgs.json --out reply.txt [--call maker_call_2] [--max-tokens N] [--temperature T]
    (or take tag + provider from the ledger:  --ledger inputs/custody-events.jsonl  instead of --tag/--pin-provider)

What it does, in order:
  1. Reads the OpenRouter key from --key-file (default /workspace/.openrouter-key) by path. Refuses when the file
     is missing, empty, or readable by group/other. The key is never printed and never written anywhere.
  2. POSTs /api/v1/chat/completions with body.provider = {"order":[TAG], "allow_fallbacks":false, "zdr":true}
     and header "X-OpenRouter-Metadata: enabled".
  3. GETs /api/v1/generation?id=<response id> (retrying while the stats are not ready).
  4. Appends ONE entry to the seat's harness log (a JSON list; the format kit/custody_history.py read_log reads):
       call, seat, request {method, url, headers (Authorization redacted), body}, sent_at,
       response_status, response_headers (all, incl. Date), response (raw JSON), received_at,
       generation (raw /api/v1/generation JSON reply, or null), generation_status, generation_fetched_at,
       harness {name, sha256 of this file}, verdict {served_by, pin, ok, refusal}.
     Times are this host's UTC clock (ISO 8601 Z); the server clock is in response_headers.Date.
  5. Checks who served the call (response.provider, openrouter_metadata selected endpoint, generation
     provider_name, generation provider_responses). Anything other than the pinned provider, or no statement
     at all, is a REFUSAL: the entry is still logged (it is evidence), but no reply is written to --out.

Exit codes: 0 logged, served by the pin, reply written · 2 usage/key error, nothing sent · 3 HTTP/transport
error (logged when a request was sent) · 4 REFUSED: served by another provider, a fallback was tried, or the
response does not say who served it (logged, no --out) · 5 served by the pin but the /api/v1/generation reply
was not obtained (logged with generation null, --out written; the record must then flag it, bar N4).

The log never contains the key: the Authorization header is replaced before logging, and the serialized entry
is scanned for the key string before it is written (exit 2, nothing written, if it would appear).

SPEND GUARD (job 2026-10-28-custody-times-ledger-spend, approval sheet: the shared key, bound < US$5.00, reserve US$0.10):
  * Only the (model, tag) pairs in PRICES may be called (prices = the saved ZDR snapshot 2026-10-28T18:55:55Z).
  * NO THROTTLING: max_tokens is always the endpoint maximum from PRICES (omitted = set to it; any other value
    = exit 2). No reasoning/effort parameter is ever sent.
  * Before anything is sent, under an exclusive lock on the job spend ledger (JSON lines, outside the repo):
        worst  = bytes(messages JSON) x prompt price + max_tokens x completion price   (bytes >= tokens)
        ledger = sum(settled cost) + sum(worst of reserves never settled)
        keyuse = key usage now (GET /api/v1/key, free) - key usage at --init-spend   (shared key: conservative)
        spent  = max(ledger, keyuse)
     REFUSE (exit 6, nothing sent, no harness log entry) when spent + worst + RESERVE_USD >= BOUND_USD, or the key
     usage cannot be read, or the baseline is missing. Otherwise append a `reserve` line (worst case) and send.
  * After the call, append a `settle` line: cost = generation reply total_cost, else response usage.cost, else the
    worst case (HTTP error without an id: 0, OpenRouter bills no failed request; key usage reconciles it).
  * --spend-ledger other than the job ledger = TEST MODE: the guard runs and decides, then exit 6 (refused) or
    exit 7 (would send), and NOTHING is sent (with the real transport).
  * --init-spend: write key-usage-baseline.json beside the ledger (refuses if a ledger or baseline exists).
  * --spend-status: print ledger total, key-usage delta, remaining headroom; sends nothing paid.
Exit 6 = REFUSED by the spend guard (nothing sent) · 7 = test mode, guard would allow (nothing sent) ·
10 = finish_reason "length" with empty content: logged, no reply written; a failure class of its own (stop, do not retry).
Every log entry carries "finish_reason" (null when no reply came back) and, when a reply came back, "content_empty".
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
KEY_FILE = "/workspace/.openrouter-key"
META_HEADER = ("X-OpenRouter-Metadata", "enabled")
REDACTED = "Bearer [REDACTED]"
JOB_ID = "2026-10-28-custody-times-ledger-spend"
SPEND_LEDGER = f"/workspace/edi-work/{JOB_ID}/spend/spend-ledger.jsonl"
BOUND_USD = 5.00        # strict: total job spend must stay < BOUND_USD
RESERVE_USD = 0.10      # margin kept free under the bound (pricing/estimate error)
# (model, tag) -> USD per prompt token, USD per completion token, endpoint max_completion_tokens.
# Source: /api/v1/models/<model>/endpoints snapshot 2026-10-28T18:55:55Z (custody/zdr-endpoints-*.json + models-*.json).
PRICES = {
    ("deepseek/deepseek-v4.1-flash-1017", "deepinfra/fp8"): (0.000000098, 0.000000294, 131072),
    ("z-ai/glm-5.3-flash", "z-ai/fp8"): (0.00000015, 0.0000005, 131072),
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def norm(v) -> str:
    return re.sub(r"[^a-z0-9]", "", str(v or "").lower())


class Transport:
    """urllib transport; tests swap it for a fake. Returns (status, headers dict, body bytes)."""
    def request(self, method: str, url: str, headers: dict, body: bytes | None, timeout: float = 300):
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, dict(r.headers.items()), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers.items()) if e.headers else {}, e.read()


def read_key(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"or_call: no key file at {path}")
    mode = stat.S_IMODE(p.stat().st_mode)
    if mode & 0o077:
        raise SystemExit(f"or_call: key file {path} is readable by group/other (mode {oct(mode)}); chmod 600 it")
    key = p.read_text(encoding="utf-8").strip()
    if not key:
        raise SystemExit(f"or_call: key file {path} is empty")
    return key


def pin_from_ledger(ledger: str, seat: str) -> tuple[str, str]:
    pins = [json.loads(ln) for ln in Path(ledger).read_text(encoding="utf-8").splitlines() if ln.strip()]
    pins = [e for e in pins if e.get("event") == "pin" and e.get("seat") == seat]
    if not pins:
        raise SystemExit(f"or_call: ledger {ledger} has no pin for seat {seat!r} (custody_ledger.py pin first)")
    return pins[-1]["slug"], pins[-1]["provider"]


def served_by(resp: dict, gen: dict | None) -> tuple[dict, list]:
    """({source: provider}, [providers tried]) as the response and the generation reply state them."""
    served, tried = {}, []
    if isinstance(resp, dict):
        if resp.get("provider"):
            served["response.provider"] = str(resp["provider"])
        om = resp.get("openrouter_metadata") if isinstance(resp.get("openrouter_metadata"), dict) else {}
        sel = [e.get("provider") for e in ((om.get("endpoints") or {}).get("available") or [])
               if isinstance(e, dict) and e.get("selected") and e.get("provider")]
        if sel:
            served["openrouter_metadata.endpoints.selected"] = str(sel[-1])
        tried += [str(a.get("provider")) for a in (om.get("attempts") or []) if isinstance(a, dict) and a.get("provider")]
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
        raise SystemExit("or_call: the log entry would contain the key; nothing written")
    items = []
    if log.exists() and log.stat().st_size:
        items = json.loads(log.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            raise SystemExit(f"or_call: {log} is not a JSON list harness log; refusing to append")
    items.append(entry)
    log.parent.mkdir(parents=True, exist_ok=True)
    tmp = log.with_suffix(log.suffix + ".tmp")
    tmp.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, log)


# ---------------------------------------------------------------- spend guard
def _ledger_rows(ledger: Path) -> list:
    if not ledger.exists():
        return []
    return [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]


def ledger_spent(ledger: Path) -> float:
    rows = _ledger_rows(ledger)
    settled = {r["id"]: float(r["cost_usd"]) for r in rows if r.get("event") == "settle"}
    total = 0.0
    for r in rows:
        if r.get("event") == "reserve":
            total += settled.get(r["id"], float(r["worst_usd"]))
    return total


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
        status, _, raw = t.request("GET", f"{a.base_url}/key", {"Authorization": f"Bearer {key}"}, None, timeout=60)
        if status != 200:
            return None
        u = json.loads(raw.decode("utf-8")).get("data", {}).get("usage")
        return float(u) if u is not None else None
    except Exception:
        return None


def guard_state(a, key: str, t, ledger: Path) -> dict:
    base_f = ledger.parent / "key-usage-baseline.json"
    st = {"ledger": str(ledger), "ledger_spent_usd": round(ledger_spent(ledger), 6), "bound_usd": BOUND_USD,
          "reserve_usd": RESERVE_USD, "key_usage_baseline": None, "key_usage_now": None, "key_usage_delta_usd": None}
    if not base_f.exists():
        st["error"] = f"no key-usage baseline at {base_f} (run --init-spend once, before the job's first call)"
        return st
    st["key_usage_baseline"] = float(json.loads(base_f.read_text(encoding="utf-8"))["usage"])
    now_u = key_usage(a, key, t)
    if now_u is None:
        st["error"] = "could not read key usage (GET /api/v1/key)"
        return st
    st["key_usage_now"] = now_u
    st["key_usage_delta_usd"] = round(now_u - st["key_usage_baseline"], 6)
    st["spent_usd"] = round(max(st["ledger_spent_usd"], st["key_usage_delta_usd"]), 6)
    st["headroom_usd"] = round(BOUND_USD - RESERVE_USD - st["spent_usd"], 6)
    return st


def init_spend(a, transport=None) -> int:
    t = transport or Transport()
    ledger = Path(a.spend_ledger)
    base_f = ledger.parent / "key-usage-baseline.json"
    if ledger.exists() or base_f.exists():
        print(f"or_call: {ledger} or {base_f} already exists; --init-spend runs once per job", file=sys.stderr); return 2
    key = read_key(a.key_file)
    u = key_usage(a, key, t)
    if u is None:
        print("or_call: could not read key usage", file=sys.stderr); return 3
    ledger.parent.mkdir(parents=True, exist_ok=True)
    base_f.write_text(json.dumps({"job": JOB_ID, "usage": u, "at": now()}) + "\n", encoding="utf-8")
    print(json.dumps({"baseline": str(base_f), "usage": u}))
    return 0


def spend_status(a, transport=None) -> int:
    t = transport or Transport()
    key = read_key(a.key_file)
    print(json.dumps(guard_state(a, key, t, Path(a.spend_ledger))))
    return 0


def call(a, transport: Transport | None = None, sleep=time.sleep) -> int:
    t = transport or Transport()
    if not re.fullmatch(r"harness-[A-Za-z0-9._-]+\.log", Path(a.log).name):
        print(f"or_call: log name {Path(a.log).name!r} must be harness-<seat>[-...].log", file=sys.stderr); return 2
    if not Path(a.log).name.startswith(f"harness-{a.seat}"):
        print(f"or_call: log {Path(a.log).name!r} is not this seat's (harness-{a.seat}*.log)", file=sys.stderr); return 2
    if a.ledger:
        tag, provider = pin_from_ledger(a.ledger, a.seat)
        if a.tag and a.tag != tag:
            print(f"or_call: --tag {a.tag} differs from the ledger pin {tag}", file=sys.stderr); return 2
    else:
        tag, provider = a.tag, a.pin_provider
    if not tag or not provider:
        print("or_call: need --tag and --pin-provider, or --ledger", file=sys.stderr); return 2
    price = PRICES.get((a.model, tag))
    if price is None:
        print(f"or_call: ({a.model}, {tag}) is not in the frozen PRICES table; refusing", file=sys.stderr); return 2
    p_in, p_out, max_out = price
    if a.max_tokens is None:
        a.max_tokens = max_out
    elif a.max_tokens != max_out:
        print(f"or_call: --max-tokens {a.max_tokens} != endpoint max {max_out}; throttling is not allowed", file=sys.stderr); return 2
    messages = json.loads(Path(a.messages).read_text(encoding="utf-8"))
    if not isinstance(messages, list):
        print("or_call: --messages must hold a JSON list of chat messages", file=sys.stderr); return 2
    key = read_key(a.key_file)
    ledger = Path(a.spend_ledger)
    test_mode = ledger.resolve() != Path(SPEND_LEDGER).resolve()
    worst = len(json.dumps(messages, ensure_ascii=False).encode("utf-8")) * p_in + a.max_tokens * p_out
    call_name = a.call or f"{a.seat}_call"
    with SpendLock(ledger):
        st = guard_state(a, key, t, ledger)
        st.update({"call": call_name, "seat": a.seat, "model": a.model, "tag": tag, "worst_usd": round(worst, 6),
                   "test_mode": test_mode})
        if "error" in st or st["spent_usd"] + worst + RESERVE_USD >= BOUND_USD:
            st["decision"] = "REFUSED"
            print(json.dumps(st), file=sys.stderr)
            print(f"or_call: REFUSED by the spend guard ({st.get('error') or 'spent + worst case + reserve >= bound'}); "
                  "nothing sent, nothing logged", file=sys.stderr)
            return 6
        st["decision"] = "ALLOWED"
        if test_mode and transport is None:
            print(json.dumps(st))
            print("or_call: TEST MODE (non-job spend ledger): guard would allow; nothing sent", file=sys.stderr)
            return 7
        rid = uuid.uuid4().hex
        _append_ledger(ledger, {"event": "reserve", "id": rid, "at": now(), "job": JOB_ID, "seat": a.seat,
                                "call": call_name, "model": a.model, "tag": tag, "max_tokens": a.max_tokens,
                                "worst_usd": round(worst, 8), "spent_before_usd": st["spent_usd"]})
    holder = {}
    try:
        rc = _send(a, t, sleep, key, tag, provider, messages, call_name, holder)
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
            cost, src = 0.0, f"HTTP {holder.get('status')} without a generation id (not billed; key usage reconciles)"
        with SpendLock(ledger):
            _append_ledger(ledger, {"event": "settle", "id": rid, "at": now(), "call": call_name,
                                    "cost_usd": cost, "source": src})
    return rc


def _send(a, t, sleep, key, tag, provider, messages, call_name, holder) -> int:
    body = {"model": a.model, "messages": messages,
            "provider": {"order": [tag], "allow_fallbacks": False, "zdr": True}, "max_tokens": a.max_tokens}
    if a.temperature is not None:
        body["temperature"] = a.temperature
    url = f"{a.base_url}/chat/completions"
    send_headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", META_HEADER[0]: META_HEADER[1]}
    log_headers = {**send_headers, "Authorization": REDACTED}
    entry = {"call": call_name, "seat": a.seat,
             "request": {"method": "POST", "url": url, "headers": log_headers, "body": body},
             "harness": {"name": "freeze/harness/or_call.py",
                         "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    entry["sent_at"] = now()
    try:
        status, hdrs, raw = t.request("POST", url, send_headers, json.dumps(body).encode())
    except Exception as exc:  # transport failure: nothing came back
        entry.update({"received_at": now(), "response_status": None, "response_headers": {}, "response": None,
                      "finish_reason": None, "transport_error": f"{type(exc).__name__}: {exc}", "generation": None,
                      "verdict": {"ok": False, "refusal": "transport error"}})
        append_entry(Path(a.log), entry, key)
        print(f"or_call: transport error, logged: {type(exc).__name__}", file=sys.stderr); return 3
    entry["received_at"] = now()
    entry["response_status"], entry["response_headers"] = status, hdrs
    holder["status"] = status
    try:
        resp = json.loads(raw.decode("utf-8"))
    except ValueError:
        resp = {"_raw_text": raw.decode("utf-8", "replace")}
    entry["response"] = resp
    holder["resp"] = resp
    ch0 = ((resp.get("choices") or [{}])[0] if isinstance(resp, dict) else {}) or {}
    entry["finish_reason"] = ch0.get("finish_reason")          # logged on every call that got a reply (None otherwise)
    entry["content_empty"] = not ((ch0.get("message") or {}).get("content") or "").strip()
    if status != 200 or not isinstance(resp, dict) or not resp.get("id"):
        entry.update({"generation": None, "verdict": {"ok": False, "refusal": f"HTTP {status}"}})
        append_entry(Path(a.log), entry, key)
        print(f"or_call: HTTP {status}, logged", file=sys.stderr); return 3
    gen, gstatus = None, None
    for attempt in range(a.gen_tries):
        gurl = f"{a.base_url}/generation?id={resp['id']}"
        try:
            gstatus, _, graw = t.request("GET", gurl, {"Authorization": f"Bearer {key}"}, None, timeout=60)
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
        refusal = "served by " + ", ".join(f"{n!r} ({s})" for s, n in bad.items()) + f", not the pin {provider!r} ({tag})"
    elif fallback:
        refusal = f"a fallback was tried: {fallback}"
    entry["verdict"] = {"pin": {"tag": tag, "provider": provider}, "served_by": served, "tried": tried,
                        "ok": refusal is None, "refusal": refusal, "generation_reply": gen is not None}
    append_entry(Path(a.log), entry, key)
    if refusal:
        print(f"or_call: REFUSED ({refusal}); logged to {a.log}; no reply written", file=sys.stderr); return 4
    content = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    if entry.get("finish_reason") == "length" and not content.strip():
        print("or_call: finish_reason=length with empty content (its own failure class: stop, do not retry); "
              f"logged to {a.log}; no reply written", file=sys.stderr); return 10
    if a.out:
        Path(a.out).write_text(content, encoding="utf-8")
    if gen is None:
        print(f"or_call: served by the pin, but no /api/v1/generation reply after {a.gen_tries} tries "
              f"(last status {gstatus}); logged with generation null", file=sys.stderr); return 5
    print(json.dumps({"logged": a.log, "call": entry["call"], "id": resp["id"], "served_by": served,
                      "finish_reason": entry.get("finish_reason"),
                      "date": next((v for k, v in hdrs.items() if k.lower() == "date"), None)}))
    return 0


def check_key(a, transport: Transport | None = None) -> int:
    """Read-only GET /api/v1/key: proves the key works; prints only status, limit and usage."""
    t = transport or Transport()
    key = read_key(a.key_file)
    status, _, raw = t.request("GET", f"{a.base_url}/key", {"Authorization": f"Bearer {key}"}, None, timeout=60)
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
    ap.add_argument("--spend-ledger", default=SPEND_LEDGER, help="job spend ledger (other path = TEST MODE, nothing sent)")
    ap.add_argument("--init-spend", action="store_true", help="record the key-usage baseline once, then exit")
    ap.add_argument("--spend-status", action="store_true", help="print guard state (free GET /api/v1/key), then exit")
    return ap


def main(argv=None) -> int:
    a = parser().parse_args(argv)
    if a.check_key:
        return check_key(a)
    if a.init_spend:
        return init_spend(a)
    if a.spend_status:
        return spend_status(a)
    for k in ("seat", "log", "model", "messages"):
        if not getattr(a, k):
            print(f"or_call: --{k.replace('_', '-')} is required", file=sys.stderr); return 2
    return call(a)


if __name__ == "__main__":
    sys.exit(main())
