#!/usr/bin/env python3
"""Redact held-out control text from the batch-3 S1 per-check evidence (job 2026-10-28-custody-times-ledger-spend
close). No model calls; holds no control text. S1 runs its checks against held-out fixtures (template jobs, plants,
expect.json), and some checks echo fixture values into their evidence. A JSON scalar is replaced with a fixed marker
when its value contains a control line, or when its pretty-printed line (`"key": value` / list item, with or
without a trailing comma) contains one. Control lines and the public filter are the leak scan's
(handoffs/close/leak_scan.py). The full files stay on the Owner's box; import_close.py records their sha256 in
custody/evidence/HELD-ON-BOX.sha256.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from leak_scan import lines_of  # noqa: E402

MARK = "[REDACTED: held-out S1 fixture text; full file held on the Owner's box, sha256 in HELD-ON-BOX.sha256]"


def control_lines(controls: Path, public_list: Path) -> list[str]:
    public = set()
    for p in [p for p in public_list.read_text().splitlines() if p]:
        try:
            public.update(lines_of(Path(p).read_text(encoding="utf-8", errors="replace")))
        except (IsADirectoryError, FileNotFoundError):
            pass
    blob = "\n".join(public)
    is_public = lambda s: s in public or s in blob or s.rstrip(",").rstrip() in blob
    ctl = set()
    for p in sorted(controls.rglob("*")):
        if p.is_file():
            for s in lines_of(p.read_text(encoding="utf-8", errors="replace")):
                if len(s) >= 25 and not s.startswith("=== FILE ") and s not in ctl and not is_public(s):
                    ctl.add(s)
    return sorted(ctl)


def _hit(ctl, *texts) -> bool:
    return any(s in t for t in texts for s in ctl)


def _walk(o, ctl, n):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if not isinstance(v, (dict, list)):
                line = f"{json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}"
                if _hit(ctl, line + ",", str(v)):
                    n[0] += 1; out[k] = MARK; continue
            out[k] = _walk(v, ctl, n)
        return out
    if isinstance(o, list):
        out = []
        for v in o:
            if not isinstance(v, (dict, list)) and _hit(ctl, json.dumps(v, ensure_ascii=False) + ",", str(v)):
                n[0] += 1; out.append(MARK); continue
            out.append(_walk(v, ctl, n))
        return out
    return o


def redact_file(path: Path, ctl: list[str]) -> int:
    """Rewrite path in place if it holds control text; return the number of values replaced."""
    raw = path.read_text(encoding="utf-8")
    if not _hit(ctl, raw + "\n" + "\n".join(_strings(json.loads(raw)))):
        return 0
    n = [0]
    o = _walk(json.loads(raw), ctl, n)
    if isinstance(o, dict):
        o["redaction"] = MARK.strip("[]") + f" ({n[0]} values)"
    path.write_text(json.dumps(o, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return n[0]


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)
