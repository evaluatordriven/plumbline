#!/usr/bin/env python3
"""Held-out-control leak scan (job 2026-10-28-custody-times-ledger-spend close). No model calls; reads the controls
by path at run time and holds no control text itself. Adapted from 2026-10-28-doctrine-reader-pointer.

A control line is any line (stripped, >= 25 chars) of any file under CONTROLS_DIR; for listing lines of the form
`  NNN + text` / `  NNN   text` the text after the prefix is taken too. Lines that are public (they occur in a
PUBLIC file: the subject listings, the tracked tree of the job branch, the trees of the evaluated revisions), or
occur verbatim inside a public line, are dropped, since they are not control text.
Every FILE given is then searched for each remaining line: as a substring for files up to 2 MB, and line by line
(every line, and every line of every decoded JSON string) for larger files, where a substring search over every
control line would take hours. Exit 0 = no leak, 3 = leak (names only printed).
--allow FILE is a JSON list of {"file": basename, "line_sha256": sha256 of a control line, "why": ...}: that
control line is not counted in that file (reviewed coincidences in files whose digest is pinned). It holds no text.
Usage: leak_scan.py --controls DIR --public-list FILE_OF_PATHS [--public FILE ...] [--allow FILE] FILE...
"""
import argparse, hashlib, json, re, sys
from pathlib import Path

PFX = re.compile(r"^\s*\d+\s[+\- ]\s?(.*)$")
BIG = 2 * 1024 * 1024


def lines_of(text: str):
    for l in text.splitlines():
        s = l.strip()
        yield s
        m = PFX.match(l)
        if m:
            yield m.group(1).strip()
        if s.startswith(("+", "-")) and not s.startswith(("+++", "---")):
            yield s[1:].strip()


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls", required=True)
    ap.add_argument("--public-list")
    ap.add_argument("--public", action="append", default=[])
    ap.add_argument("--allow")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    pub_paths = list(a.public)
    if a.public_list:
        pub_paths += [p for p in Path(a.public_list).read_text().splitlines() if p]
    public = set()
    for p in pub_paths:
        try:
            public.update(lines_of(Path(p).read_text(encoding="utf-8", errors="replace")))
        except (IsADirectoryError, FileNotFoundError):
            pass
    # A control line that occurs verbatim inside public text (with or without its trailing comma) is not
    # held-out text either: e.g. a plant's `"kind": "x",` line inside the subject's `fails.append({"kind": "x", ...`.
    blob = "\n".join(public)
    is_public = lambda s: s in public or s in blob or s.rstrip(",").rstrip() in blob
    ctl = {}
    for p in sorted(Path(a.controls).rglob("*")):
        if p.is_file():
            for s in lines_of(p.read_text(encoding="utf-8", errors="replace")):
                if len(s) >= 25 and not s.startswith("=== FILE ") and s not in ctl and not is_public(s):
                    ctl[s] = str(p.relative_to(a.controls))
    allow = {(x["file"], x["line_sha256"]) for x in (json.loads(Path(a.allow).read_text()) if a.allow else [])}
    lsha = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()
    bad, modes, allowed = [], {"substring": 0, "line": 0}, 0
    for f in a.files:
        if Path(f).is_dir():
            continue
        t = Path(f).read_text(encoding="utf-8", errors="replace")
        try:  # JSON: search the decoded strings too (escapes such as \u2014 or \n would hide a line)
            t += "\n" + "\n".join(strings(json.loads(t)))
        except ValueError:
            pass
        if len(t) <= BIG:
            modes["substring"] += 1
            found = [s for s in ctl if s in t]
        else:
            modes["line"] += 1
            have = set(lines_of(t))
            found = [s for s in have if s in ctl]
        keep = [s for s in found if (Path(f).name, lsha(s)) not in allow]
        allowed += len(found) - len(keep)
        hits = sorted({ctl[s] for s in keep})
        if hits:
            bad.append((f, hits))
    for f, hits in bad:
        print(f"LEAK {f}: lines from {hits}", file=sys.stderr)
    print(f"leak_scan: {len(ctl)} control lines, {len(a.files)} files ({modes['substring']} substring, "
          f"{modes['line']} line-by-line), {len(bad)} with control text, {allowed} allowlisted hits")
    return 3 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
