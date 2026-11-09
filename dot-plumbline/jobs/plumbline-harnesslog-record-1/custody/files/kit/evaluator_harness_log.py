"""One reading of a harness log for the custody emitter.

A harness log is what tools/edi/or_call.py appends (its append_entry): one entry
per model call, each carrying `call`, `sent_at`, `received_at` (RFC 3339 UTC),
the `request` url and the `response` model. The file is a JSON list; a file that
holds a single entry object is accepted too.

The emitter asks this module one thing of the log: is it sound, and for a named
call, when did it start and end, and where does that time come from? A malformed,
partial or reversed log raises HarnessLogError naming the entry, so the emitter
can REFUSE the record rather than take a check time from a log it cannot honestly
read.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


class HarnessLogError(Exception):
    """A harness log the record cannot honestly read. `call` names the entry when there is one."""

    def __init__(self, path, reason: str, call: str | None = None):
        self.path = Path(path)
        self.reason = reason
        self.call = call
        where = f"entry {call!r} in {self.path.name}" if call else self.path.name
        super().__init__(f"{where}: {reason}")


def parse_instant(value):
    """A logged time as a UTC datetime, or None when it is not RFC 3339 UTC (...Z)."""
    if not isinstance(value, str) or not RFC3339.match(value):
        return None
    return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)


def _line_of(lines: list, key: str, value) -> int | None:
    """The 1-based line carrying `"key": <value>`, else the first line carrying the value."""
    text = str(value)
    for n, line in enumerate(lines, 1):
        if f'"{key}"' in line and text in line:
            return n
    for n, line in enumerate(lines, 1):
        if text in line:
            return n
    return None


class Entry:
    """One call of a harness log, as the record reads it."""

    def __init__(self, name: str, sent_at: datetime, received_at: datetime,
                 sent_line: int | None, received_line: int | None, log_name: str, raw: dict):
        self.name = name
        self.sent_at = sent_at
        self.received_at = received_at
        self.sent_line = sent_line
        self.received_line = received_line
        self.log_name = log_name
        self.raw = raw

    @property
    def source(self) -> str | None:
        """`<log name>:<line>` of the received time (the check's time), else of the sent time."""
        line = self.received_line if self.received_line is not None else self.sent_line
        return f"{self.log_name}:{line}" if line is not None else None


def read(path) -> dict:
    """Every call of the harness log at `path`, by call name, in file order.

    Raises HarnessLogError when the file is unreadable, is not JSON, is neither a
    list of entries nor a single entry object, or when an entry is missing its call
    name, sent_at or received_at, or has received_at before sent_at.
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise HarnessLogError(p, f"cannot be read: {exc}")
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise HarnessLogError(p, f"is not JSON: {exc}")
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = [data]
    else:
        raise HarnessLogError(p, "is neither a JSON list of harness entries nor one entry object")
    lines = text.splitlines()
    out: dict = {}
    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise HarnessLogError(p, f"entry {i} is not a JSON object")
        raw_call = item.get("call")
        name = raw_call.strip() if isinstance(raw_call, str) and raw_call.strip() else None
        if not name:
            raise HarnessLogError(p, f"entry {i} names no call")
        sent = parse_instant(item.get("sent_at"))
        received = parse_instant(item.get("received_at"))
        if sent is None:
            raise HarnessLogError(p, "sent_at is missing or not RFC 3339 UTC (...Z)", name)
        if received is None:
            raise HarnessLogError(p, "received_at is missing or not RFC 3339 UTC (...Z)", name)
        if received < sent:
            raise HarnessLogError(
                p, f"received_at {item['received_at']} is before sent_at {item['sent_at']}", name)
        out[name] = Entry(name, sent, received,
                          _line_of(lines, "sent_at", item.get("sent_at")),
                          _line_of(lines, "received_at", item.get("received_at")),
                          p.name, item)
    return out
