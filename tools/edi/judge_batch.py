#!/usr/bin/env python3
"""tools/edi/judge_batch.py: a model-judge batch with rotating order.

    judge_batch.py --items ITEMS.json --batch N --rubric FILE --out DIR \
                   --job-spend F --log L --model M \
                   (--tag T --pin-provider P | --ledger LED) [--mock-transport D]

ITEMS.json is a list of {id, text}.  The order for batch N is the list rotated
left by (N-1) mod len.  One tools/edi/or_call.py call is made per item.  The
summary is DIR/summary.json with started_at, finished_at, writer, batch,
order (ids) and results ({id, call, exit, reply_file}).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HARNESS_NAME = "tools/edi/judge_batch.py"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def writer() -> str:
    sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]
    return f"{HARNESS_NAME}@{sha}"


def seat_from_log(log: str) -> str:
    m = re.match(r"harness-([A-Za-z0-9]+)", Path(log).name)
    return m.group(1) if m else "judge"


def safe_name(value: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return s or "item"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run a rotating model-judge batch.")
    ap.add_argument("--items", required=True)
    ap.add_argument("--batch", type=int, required=True)
    ap.add_argument("--rubric", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--job-spend", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--model", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--tag")
    g.add_argument("--ledger")
    ap.add_argument("--pin-provider")
    ap.add_argument("--mock-transport")
    ap.add_argument("--key-file")
    ap.add_argument("--base-url")
    ap.add_argument("--seat")
    a = ap.parse_args(argv)

    if a.tag and not a.pin_provider:
        print("judge_batch: --pin-provider is required with --tag", file=sys.stderr)
        return 2
    try:
        items = json.loads(Path(a.items).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"judge_batch: cannot read --items {a.items}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(items, list):
        print("judge_batch: --items must hold a JSON list", file=sys.stderr)
        return 2
    for item in items:
        if not isinstance(item, dict) or "id" not in item or "text" not in item:
            print("judge_batch: every item must be an object with id and text", file=sys.stderr)
            return 2
    try:
        rubric = Path(a.rubric).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"judge_batch: cannot read --rubric {a.rubric}: {exc}", file=sys.stderr)
        return 2

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    or_call = Path(__file__).with_name("or_call.py")
    if not or_call.is_file():
        print(f"judge_batch: missing sibling {or_call}", file=sys.stderr)
        return 2

    started = now()
    n = len(items)
    k = ((a.batch - 1) % n) if n else 0
    ordered = items[k:] + items[:k]
    seat = a.seat or seat_from_log(a.log)
    results = []

    for idx, item in enumerate(ordered):
        item_id = str(item["id"])
        safe = safe_name(item_id)
        call_name = f"batch{a.batch}_{idx:03d}_{safe}"
        msg_path = out / f"messages-{idx:03d}-{safe}.json"
        msg_path.write_text(json.dumps([
            {"role": "system", "content": rubric},
            {"role": "user", "content": str(item["text"])},
        ], indent=2) + "\n", encoding="utf-8")
        reply_path = out / f"reply-{idx:03d}-{safe}.txt"
        cmd = [
            sys.executable, str(or_call),
            "--seat", seat,
            "--log", a.log,
            "--model", a.model,
            "--messages", str(msg_path),
            "--out", str(reply_path),
            "--call", call_name,
            "--job-spend", a.job_spend,
        ]
        if a.ledger:
            cmd += ["--ledger", a.ledger]
        else:
            cmd += ["--tag", a.tag, "--pin-provider", a.pin_provider]
        if a.mock_transport:
            cmd += ["--mock-transport", a.mock_transport]
        if a.key_file:
            cmd += ["--key-file", a.key_file]
        if a.base_url:
            cmd += ["--base-url", a.base_url]
        proc = subprocess.run(cmd)
        results.append({
            "id": item_id,
            "call": call_name,
            "exit": proc.returncode,
            "reply_file": str(reply_path),
        })

    summary = {
        "started_at": started,
        "finished_at": now(),
        "writer": writer(),
        "batch": a.batch,
        "order": [str(i["id"]) for i in ordered],
        "results": results,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0 if all(r["exit"] == 0 for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
