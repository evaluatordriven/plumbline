#!/usr/bin/env python3
"""Close spend read (bar P6), job 2026-10-28-custody-times-ledger-spend. No model call.

Uses the FROZEN harness (custody/freeze/harness/or_call.py, sha in custody/MANIFEST.sha256) by import:
  1. guard_state() -- exactly what `or_call.py --spend-status` prints (one free GET /api/v1/key);
  2. one more free GET /api/v1/key through the same Transport, keeping only the key's numeric usage/limit
     fields (the `label` and any other string field are dropped: a label can carry part of the key);
  3. the job spend ledger, summed by UTC day and by EDT (UTC-4) day, for reconciliation.
The key is read by path (--key-file, default the harness's KEY_FILE) and never written; the output is checked
not to contain it. Usage: spend_read_close.py --job-dir J --out FILE
"""
import argparse, hashlib, importlib.util, json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KEEP = ("usage", "usage_daily", "usage_weekly", "usage_monthly", "byok_usage", "byok_usage_daily",
        "byok_usage_weekly", "byok_usage_monthly", "limit", "limit_remaining", "limit_reset",
        "is_free_tier", "is_provisioning_key", "include_byok_in_limit")
EDT = timezone(timedelta(hours=-4))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    J = Path(a.job_dir)
    hp = J / "custody" / "freeze" / "harness" / "or_call.py"
    want = [l.split()[0] for l in (J / "custody" / "MANIFEST.sha256").read_text().splitlines()
            if l.endswith("freeze/harness/or_call.py")][0]
    got = hashlib.sha256(hp.read_bytes()).hexdigest()
    if got != want:
        raise SystemExit(f"frozen harness sha {got} != manifest {want}")
    spec = importlib.util.spec_from_file_location("or_call_frozen", hp)
    oc = importlib.util.module_from_spec(spec); spec.loader.exec_module(oc)
    ns = argparse.Namespace(key_file=oc.KEY_FILE, base_url=oc.BASE, spend_ledger=oc.SPEND_LEDGER)
    ledger = Path(oc.SPEND_LEDGER)
    led_before = hashlib.sha256(ledger.read_bytes()).hexdigest()
    key = oc.read_key(ns.key_file)
    t = oc.Transport()
    read_at = datetime.now(timezone.utc)
    st = oc.guard_state(ns, key, t, ledger)
    status, _h, body = t.request("GET", f"{ns.base_url}/key", {"Authorization": f"Bearer {key}"}, None, timeout=60)
    raw = json.loads(body.decode("utf-8")) if status == 200 else {}
    data = raw.get("data", raw) if isinstance(raw, dict) else {}
    keyfig = {k: data[k] for k in KEEP if k in data}
    dropped = sorted(k for k in data if k not in keyfig)
    led_after = hashlib.sha256(ledger.read_bytes()).hexdigest()
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    res = {r["id"]: r for r in rows if r["event"] == "reserve"}
    stl = {r["id"]: r for r in rows if r["event"] == "settle"}
    by_utc, by_edt = {}, {}
    for r in stl.values():
        d = datetime.strptime(r["at"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        by_utc[d.strftime("%Y-%m-%d")] = round(by_utc.get(d.strftime("%Y-%m-%d"), 0) + r["cost_usd"], 9)
        e = d.astimezone(EDT).strftime("%Y-%m-%d")
        by_edt[e] = round(by_edt.get(e, 0) + r["cost_usd"], 9)
    open_res = [{"id": i, "call": r["call"], "at": r["at"], "worst_usd": r["worst_usd"]}
                for i, r in res.items() if i not in stl]
    last = max((r["at"] for r in rows), default=None)
    out = {"what": "close spend read (bar P6), job 2026-10-28-custody-times-ledger-spend; no model call",
           "read_at": read_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "harness": {"file": "custody/freeze/harness/or_call.py", "sha256": got},
           "key_file": "by path only (harness KEY_FILE); not recorded",
           "spend_status": st,
           "key_get": {"http_status": status, "figures": keyfig, "fields_dropped": dropped,
                       "note": "usage_daily/weekly/monthly are OpenRouter's own windows for this key (UTC days)"},
           "spend_ledger": {"sha256_before": led_before, "sha256_after": led_after, "lines": len(rows),
                            "reserves": len(res), "settles": len(stl),
                            "settled_usd": round(sum(r["cost_usd"] for r in stl.values()), 9),
                            "open_reserves": open_res, "settled_by_utc_day": by_utc,
                            "settled_by_edt_day": by_edt, "last_line_at": last}}
    text = json.dumps(out, indent=1, ensure_ascii=False) + "\n"
    if key in text or key[-12:] in text:
        raise SystemExit("output would contain the key; nothing written")
    Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if status == 200 and "error" not in st and led_before == led_after else 1


if __name__ == "__main__":
    sys.exit(main())
