#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z — part of the freeze set of job 2026-10-27-custody-emitter-gaps; sha256 in ../../MANIFEST.sha256.
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
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://openrouter.ai/api/v1"
KEY_FILE = "/workspace/.openrouter-key"
META_HEADER = ("X-OpenRouter-Metadata", "enabled")
REDACTED = "Bearer [REDACTED]"


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
    messages = json.loads(Path(a.messages).read_text(encoding="utf-8"))
    if not isinstance(messages, list):
        print("or_call: --messages must hold a JSON list of chat messages", file=sys.stderr); return 2
    key = read_key(a.key_file)
    body = {"model": a.model, "messages": messages,
            "provider": {"order": [tag], "allow_fallbacks": False, "zdr": True}}
    if a.max_tokens is not None:
        body["max_tokens"] = a.max_tokens
    if a.temperature is not None:
        body["temperature"] = a.temperature
    url = f"{a.base_url}/chat/completions"
    send_headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", META_HEADER[0]: META_HEADER[1]}
    log_headers = {**send_headers, "Authorization": REDACTED}
    entry = {"call": a.call or f"{a.seat}_call", "seat": a.seat,
             "request": {"method": "POST", "url": url, "headers": log_headers, "body": body},
             "harness": {"name": "freeze/harness/or_call.py",
                         "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    entry["sent_at"] = now()
    try:
        status, hdrs, raw = t.request("POST", url, send_headers, json.dumps(body).encode())
    except Exception as exc:  # transport failure: nothing came back
        entry.update({"received_at": now(), "response_status": None, "response_headers": {}, "response": None,
                      "transport_error": f"{type(exc).__name__}: {exc}", "generation": None,
                      "verdict": {"ok": False, "refusal": "transport error"}})
        append_entry(Path(a.log), entry, key)
        print(f"or_call: transport error, logged: {type(exc).__name__}", file=sys.stderr); return 3
    entry["received_at"] = now()
    entry["response_status"], entry["response_headers"] = status, hdrs
    try:
        resp = json.loads(raw.decode("utf-8"))
    except ValueError:
        resp = {"_raw_text": raw.decode("utf-8", "replace")}
    entry["response"] = resp
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
    if a.out:
        Path(a.out).write_text(content, encoding="utf-8")
    if gen is None:
        print(f"or_call: served by the pin, but no /api/v1/generation reply after {a.gen_tries} tries "
              f"(last status {gstatus}); logged with generation null", file=sys.stderr); return 5
    print(json.dumps({"logged": a.log, "call": entry["call"], "id": resp["id"], "served_by": served,
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
    return ap


def main(argv=None) -> int:
    a = parser().parse_args(argv)
    if a.check_key:
        return check_key(a)
    for k in ("seat", "log", "model", "messages"):
        if not getattr(a, k):
            print(f"or_call: --{k.replace('_', '-')} is required", file=sys.stderr); return 2
    return call(a)


if __name__ == "__main__":
    sys.exit(main())
