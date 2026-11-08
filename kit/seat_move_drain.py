"""Stage seat-move notices for one conductor turn.

The Plumbline mailbox (``runtime/plumbline-seat-notices``) is written by side
processes through ``kit.seat_move_notice``.  The conductor's turn launcher uses
this module to hand those notices to the Bot Chat exactly once:

* :func:`prepare_turn` recovers notices left staged by a previous failed turn,
  drains the mailbox in FIFO order into the ``inflight`` staging directory, and
  returns the parsed notices plus the context string to announce.
* :func:`consume_turn` is called only after the turn completes successfully.
  Until it is called, the notices remain in ``inflight`` and a later
  :func:`prepare_turn` recovers and re-announces them.

A crash between staging and consumption therefore loses nothing: the notice is
still on disk and is announced on the retry.  A clean turn removes the staged
files, so a notice is never announced twice.

Everything here operates inside the given profile home.  The module never
writes a Hermes session, never shells out to ``hermes``, and claims no lease.
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Mapping

__all__ = [
    "prepare_turn",
    "consume_turn",
    "format_context",
    "mailbox_dir",
    "inflight_dir",
]

_MAILBOX_REL = pathlib.Path("runtime") / "plumbline-seat-notices"
_INFLIGHT = "inflight"
_FLAG = "PLUMBLINE_SEAT_NOTICE"


def _enabled(env: Mapping[str, str] | None) -> bool:
    source = os.environ if env is None else env
    return str(source.get(_FLAG, "1")).strip() != "0"


def mailbox_dir(profile_home) -> pathlib.Path:
    """Return the Plumbline seat-notice mailbox for ``profile_home``."""
    return pathlib.Path(profile_home).expanduser() / _MAILBOX_REL


def inflight_dir(profile_home) -> pathlib.Path:
    """Return the in-flight staging directory inside the mailbox."""
    return mailbox_dir(profile_home) / _INFLIGHT


def _order_key(path: pathlib.Path):
    """FIFO order: creation time first, then the producer's filename."""
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        mtime = 0
    return (mtime, path.name)


def _load_notice(path: pathlib.Path) -> dict:
    # ``json.load`` raises ``JSONDecodeError`` on a corrupt receipt; do not
    # swallow it, because replaying garbage silently is worse than stopping.
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"seat notice {path.name!r} is not a JSON object")
    return data


def _recover_inflight(mailbox: pathlib.Path, inflight: pathlib.Path) -> None:
    if not inflight.is_dir():
        return
    staged = sorted(inflight.glob("*.json"), key=_order_key)
    if staged:
        mailbox.mkdir(parents=True, exist_ok=True)
        for path in staged:
            os.replace(path, mailbox / path.name)
    try:
        inflight.rmdir()
    except OSError:
        # Directory not empty (unexpected file) or vanished; leave it.
        pass


def format_context(notices) -> str:
    """Render notices as Bot Chat prose, or ``""`` when there is nothing."""
    if not notices:
        return ""
    lines = ["Seat-move notices awaiting announcement:"]
    for notice in notices:
        lines.append(
            "- {direction}: seat {seat}, job {job}, notice {notice_id}".format(
                direction=notice.get("direction", "?"),
                seat=notice.get("seat", "?"),
                job=notice.get("job_id", "?"),
                notice_id=notice.get("notice_id", "?"),
            )
        )
    return "\n".join(lines) + "\n"


def prepare_turn(*, profile_home, env: Mapping[str, str] | None = None):
    """Stage pending notices for a turn.

    Returns ``(notices, context)``.  The mailbox is emptied into ``inflight``
    only after every receipt parses, so a corrupt file leaves the mailbox
    untouched and raises.  A failed turn (no ``consume_turn``) keeps the files
    in ``inflight``; the next call recovers and announces them.
    """
    if not _enabled(env):
        return [], ""

    mailbox = mailbox_dir(profile_home)
    inflight = mailbox / _INFLIGHT

    _recover_inflight(mailbox, inflight)

    if not mailbox.is_dir():
        return [], ""

    waiting = sorted(mailbox.glob("*.json"), key=_order_key)
    if not waiting:
        return [], ""

    # Parse before staging: fail closed on a corrupt receipt.
    notices = [_load_notice(path) for path in waiting]

    inflight.mkdir(parents=True, exist_ok=True)
    for path in waiting:
        os.replace(path, inflight / path.name)

    return notices, format_context(notices)


def consume_turn(*, profile_home, env: Mapping[str, str] | None = None) -> int:
    """Mark a successful turn by deleting the staged notices.

    Returns the number of staged files removed.  Call only after the turn has
    completed without raising; a failed turn must leave ``inflight`` intact so
    the notice is recoverable and is announced exactly once on the retry.
    """
    if not _enabled(env):
        return 0

    inflight = inflight_dir(profile_home)
    if not inflight.is_dir():
        return 0

    removed = 0
    for path in inflight.glob("*.json"):
        try:
            path.unlink()
            removed += 1
        except FileNotFoundError:
            pass
    try:
        inflight.rmdir()
    except OSError:
        pass
    return removed
