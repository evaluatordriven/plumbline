#!/usr/bin/env python3
"""Announce a seat move to the conductor's Bot Chat.

Invoked by the conductor profile's run-loop at its two seat-move hook points:

  * to_seat   -- work is being dispatched to a seat
  * from_seat -- a seat is handing work back

The notice itself is written by ``send_notice`` from the repo-resident
``kit.seat_move_notice`` module, which enqueues it in the conductor profile's
Plumbline mailbox (``runtime/plumbline-seat-notices``).  This script only
enqueues the notice; it does not write the Bot Chat session and installs
nothing.  Any failure from ``send_notice`` propagates, so a seat move that
cannot be announced aborts instead of vanishing.
"""
from __future__ import annotations

import argparse

from kit.seat_move_notice import send_notice


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--direction",
        required=True,
        choices=("to_seat", "from_seat"),
        help="to_seat when dispatching, from_seat when a seat hands back",
    )
    parser.add_argument("--seat", required=True, help="seat name")
    parser.add_argument("--job-id", required=True, help="job identifier")
    args = parser.parse_args(argv)

    if args.direction == "to_seat":
        send_notice(direction="to_seat", seat=args.seat, job_id=args.job_id)
    else:
        send_notice(direction="from_seat", seat=args.seat, job_id=args.job_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
