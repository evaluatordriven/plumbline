#!/usr/bin/env python3
"""Turn-launcher template: stage seat-move notices, run, then consume.

Copy or symlink this into ``~/.hermes/profiles/plumbline-conductor/bin/`` and
call :func:`run_with_notices` from the profile's own turn launcher, passing a
callable that performs the real Bot Chat turn.  This module never shells out to
``hermes`` and never writes the session; it only brackets the turn with
``kit.seat_move_drain``:

    notices, context = prepare_turn(profile_home=...)
    run_turn(context)                                  # the actual turn
    consume_turn(profile_home=...)                     # only on clean success

If ``run_turn`` raises, ``consume_turn`` is not reached and the staged notices
stay in ``inflight`` for the next turn to recover and announce exactly once.
"""
from __future__ import annotations

import argparse
from typing import Callable, Mapping

from kit.seat_move_drain import consume_turn, prepare_turn


def run_with_notices(
    turn: Callable[[str], object],
    *,
    profile_home: str,
    env: Mapping[str, str] | None = None,
):
    """Run ``turn(context)`` with any staged notices, consuming on success."""
    _notices, context = prepare_turn(profile_home=profile_home, env=env)
    result = turn(context)
    consume_turn(profile_home=profile_home, env=env)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-home", required=True)
    parser.parse_args(argv)
    parser.error(
        "seat-move-turn.py is a template: import run_with_notices from the "
        "profile's turn launcher; it does not start a session on its own"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
