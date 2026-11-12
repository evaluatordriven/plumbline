#!/usr/bin/env python3
"""One-paste status card for Owner / conduit (Telegram-safe).

  PYTHONPATH=. python3 tools/status_card.py --summary path/to/summary.json
  PYTHONPATH=. python3 tools/status_card.py --record-dir path/to/job-record
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from kit.delight import attach_gates, status_card_lines  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--summary", help="summary.json from a finished loop")
    p.add_argument("--record-dir", help="job record dir (reads summary.json + custody)")
    p.add_argument("--packet", help="optional packet for job_id / job_class")
    p.add_argument("--pr", default=None)
    p.add_argument("--main-version", default=None)
    p.add_argument("--next-human", default=None)
    args = p.parse_args(argv)

    halt: dict = {}
    record_dir = None
    packet = None
    if args.packet and os.path.isfile(args.packet):
        with open(args.packet, encoding="utf-8") as fh:
            packet = json.load(fh)
    if args.summary and os.path.isfile(args.summary):
        with open(args.summary, encoding="utf-8") as fh:
            halt = json.load(fh)
        record_dir = args.record_dir or os.path.dirname(os.path.abspath(args.summary))
    elif args.record_dir:
        record_dir = os.path.abspath(args.record_dir)
        sp = os.path.join(record_dir, "summary.json")
        if os.path.isfile(sp):
            with open(sp, encoding="utf-8") as fh:
                halt = json.load(fh)
        pp = os.path.join(record_dir, "packet.json")
        if packet is None and os.path.isfile(pp):
            with open(pp, encoding="utf-8") as fh:
                packet = json.load(fh)
    else:
        print("status_card: need --summary and/or --record-dir", file=sys.stderr)
        return 2

    if record_dir:
        halt = attach_gates(halt, record_dir, packet if isinstance(packet, dict) else None)

    bounds = {}
    if isinstance(packet, dict) and isinstance(packet.get("bounds"), dict):
        bounds = packet["bounds"]
    budget = None
    if isinstance(bounds.get("budget"), dict):
        budget = bounds["budget"].get("amount")

    job_id = None
    if isinstance(packet, dict):
        job_id = packet.get("job_id") or packet.get("id")
    job_id = job_id or halt.get("job_id")

    text = status_card_lines(
        job_id=job_id if isinstance(job_id, str) else None,
        packet_sha=halt.get("packet_sha256"),
        job_class=halt.get("job_class"),
        instrument_gate=halt.get("instrument_gate"),
        custody_gate=halt.get("custody_gate"),
        finish_kind=halt.get("finish_kind"),
        terminal_state=halt.get("terminal_state"),
        outcome=halt.get("outcome"),
        stop=halt.get("stop"),
        pr=args.pr,
        main_version=args.main_version,
        spend=halt.get("cost"),
        budget=float(budget) if isinstance(budget, (int, float)) else None,
        next_human=args.next_human,
    )
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
