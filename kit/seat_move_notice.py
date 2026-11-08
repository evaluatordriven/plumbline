"""Queue seat-move notices for the conductor's Bot Chat.

The conductor's Bot Chat is a CLI session, and a side process must not write a
session it does not own.  This module therefore gives the side process a
Plumbline-private mailbox under the conductor profile's runtime directory:

    <profile_home>/runtime/plumbline-seat-notices/

``send_notice`` durably enqueues one JSON notice and returns its notice id.  The
conductor's own turn calls ``drain_notices`` and emits the drained notices as
its own prose in the Bot Chat.

The mailbox is private to Plumbline.  It does not use any engine Bot Chat
delivery path, take any session lease, or run any subprocess.

Set PLUMBLINE_SEAT_NOTICE=0 to disable delivery.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

DEFAULT_PROFILE = "plumbline-conductor"
VALID_DIRECTIONS = ("to_seat", "from_seat")
MAILBOX_NAME = "plumbline-seat-notices"

__all__ = ["send_notice", "drain_notices"]

_last_seq = 0


def _next_seq() -> int:
    global _last_seq
    seq = time.time_ns()
    if seq <= _last_seq:
        seq = _last_seq + 1
    _last_seq = seq
    return seq


def _resolve_profile_home(
    profile_home: str | os.PathLike | None,
    environ: Mapping[str, str],
    profile: str,
) -> Path:
    if profile_home is not None:
        return Path(profile_home)
    explicit = environ.get("PLUMBLINE_PROFILE_HOME")
    if explicit:
        return Path(explicit)
    home = environ.get("HOME") or os.environ.get("HOME")
    if not home:
        raise RuntimeError(
            "cannot locate conductor profile home: pass profile_home, "
            "set PLUMBLINE_PROFILE_HOME, or set HOME"
        )
    return Path(home) / ".hermes" / "profiles" / profile


def _mailbox_dir(profile_home: Path) -> Path:
    return profile_home / "runtime" / MAILBOX_NAME


def _is_disabled(environ: Mapping[str, str]) -> bool:
    value = str(environ.get("PLUMBLINE_SEAT_NOTICE", "1")).strip().lower()
    return value in {"0", "false", "no", "off"}


def send_notice(
    *,
    direction: str,
    seat: str,
    job_id: str,
    profile_home: str | os.PathLike | None = None,
    env: Mapping[str, str] | None = None,
    profile: str = DEFAULT_PROFILE,
) -> str | None:
    """Durably enqueue one seat-move notice and return its notice id.

    Safe to call from a side process: it touches only the mailbox directory,
    claims no session, and needs no TTY.  Returns None when delivery is
    disabled with PLUMBLINE_SEAT_NOTICE=0.  Raises ValueError on an unknown
    direction and propagates any write failure, so a seat move that cannot be
    announced aborts instead of vanishing.
    """
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"unknown seat-move direction: {direction!r}")

    environ = os.environ if env is None else env
    if _is_disabled(environ):
        return None

    home = _resolve_profile_home(profile_home, environ, profile)
    mailbox = _mailbox_dir(home)
    mailbox.mkdir(parents=True, exist_ok=True)

    notice_id = uuid.uuid4().hex
    now = time.time()
    payload = {
        "notice_id": notice_id,
        "direction": direction,
        "seat": seat,
        "job_id": job_id,
        "queued_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "queued_at_epoch": now,
    }

    dest = mailbox / f"{_next_seq():020d}-{notice_id}.json"
    fd, tmp_path = tempfile.mkstemp(
        prefix=".tmp-", suffix=".json", dir=str(mailbox)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, dest)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return notice_id


def drain_notices(
    *,
    profile_home: str | os.PathLike | None = None,
    env: Mapping[str, str] | None = None,
    profile: str = DEFAULT_PROFILE,
) -> list[dict]:
    """Return every queued notice in FIFO order and remove consumed files.

    The conductor's own turn calls this and emits the notices as its own prose.
    Raises if the mailbox cannot be read, so a notice is never silently
    dropped.  An absent mailbox drains to an empty list.
    """
    environ = os.environ if env is None else env
    home = _resolve_profile_home(profile_home, environ, profile)
    mailbox = _mailbox_dir(home)

    try:
        names = sorted(os.listdir(mailbox))
    except FileNotFoundError:
        return []

    notices = []
    for name in names:
        if not name.endswith(".json"):
            continue
        path = mailbox / name
        with path.open(encoding="utf-8") as fh:
            notice = json.load(fh)
        path.unlink()
        notices.append(notice)
    return notices
