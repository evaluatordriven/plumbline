#!/usr/bin/env python3
"""tools/edi/extract_files.py: write a whole-file reply into a checkout.

    extract_files.py REPLY.txt TARGET_DIR [--list OUT.txt] [--check]

The reply format is the Maker output contract: one FILE marker line, the
complete new contents, one matching END line, repeated, then one DONE line with
the block count, then optional NOTES lines.  The bytes between the FILE and END
lines are written exactly as they appear; the extractor adds and strips nothing.

All checks run before anything is written.  A malformed marker, a missing END,
a wrong DONE count, stray text, a bad or duplicate path, or an unsafe target
makes the command exit 1 with a one-line reason and writes nothing.  --check
validates only.  Exit 2 is a usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

PFX = b"<<<PLUMBLINE-"
RE_FILE = re.compile(rb"<<<PLUMBLINE-FILE path=([^\s>]+)>>>\n\Z")
RE_END = re.compile(rb"<<<PLUMBLINE-END path=([^\s>]+)>>>\n\Z")
RE_DONE = re.compile(rb"<<<PLUMBLINE-DONE files=(0|[1-9][0-9]*)>>>\n?\Z")
RE_PATH = re.compile(r"[!-~]+\Z")


class Refuse(Exception):
    pass


def check_path(p: str) -> None:
    if not RE_PATH.match(p) or "\\" in p or p.startswith("/"):
        raise Refuse(f"bad path {p!r}")
    if any(s in ("", ".", "..") for s in p.split("/")):
        raise Refuse(f"bad path {p!r}")


def parse(data: bytes) -> list[tuple[str, bytes]]:
    lines = [ln for ln in re.split(rb"(?<=\n)", data) if ln]
    files: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    i, n, done = 0, len(lines), None
    while i < n:
        ln = lines[i]
        if ln.startswith(PFX):
            m = RE_FILE.match(ln)
            if m:
                path = m.group(1).decode("ascii")
                check_path(path)
                if path in seen:
                    raise Refuse(f"path returned twice: {path}")
                seen.add(path)
                start = i + 1
                j = start
                endtxt = f"<<<PLUMBLINE-END path={path}>>>".encode()
                while j < n and not lines[j].startswith(PFX):
                    if endtxt in lines[j]:
                        raise Refuse(
                            f"line {j + 1}: END marker for {path} is not at the start of a line "
                            "(the file's last line must end with a newline before the END line)"
                        )
                    j += 1
                if j >= n or RE_DONE.match(lines[j]):
                    raise Refuse(
                        f"block for {path} (FILE at line {i + 1}) has no END line: reply truncated"
                    )
                e = RE_END.match(lines[j])
                if not e:
                    raise Refuse(
                        f"line {j + 1}: expected END for {path}, got a malformed or other marker line "
                        "(a content line may not start with the marker prefix)"
                    )
                if e.group(1).decode("ascii", "replace") != path:
                    raise Refuse(
                        f"line {j + 1}: END path {e.group(1).decode('ascii', 'replace')!r} "
                        f"does not match FILE path {path!r}"
                    )
                files.append((path, b"".join(lines[start:j])))
                i = j + 1
                continue
            d = RE_DONE.match(ln)
            if d:
                done = (i, int(d.group(1)))
                break
            raise Refuse(f"line {i + 1}: malformed or unexpected marker line {ln[:80]!r}")
        if ln.strip(b" \t\r\n"):
            raise Refuse(f"line {i + 1}: text outside a file block before DONE: {ln[:80]!r}")
        i += 1
    if done is None:
        raise Refuse("no DONE line: reply truncated or malformed")
    at, count = done
    if count != len(files):
        raise Refuse(f"DONE says files={count} but the reply has {len(files)} file block(s)")
    if not files:
        raise Refuse("the reply returns no files")
    notes = 0
    for k in range(at + 1, n):
        ln = lines[k]
        if not ln.strip(b" \t\r\n"):
            continue
        if ln.startswith(b"NOTES:"):
            notes += 1
            if notes > 20:
                raise Refuse("more than 20 NOTES: lines after DONE")
            continue
        raise Refuse(f"line {k + 1}: text after DONE that is not a NOTES: line: {ln[:80]!r}")
    if not lines[at].endswith(b"\n") and at != n - 1:
        raise Refuse("malformed DONE line")
    return files


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Write whole-file reply blocks into a checkout.")
    ap.add_argument("reply")
    ap.add_argument("target")
    ap.add_argument("--list", dest="list_out")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    reply, root = Path(a.reply), Path(a.target)
    try:
        files = parse(reply.read_bytes())
        if not root.is_dir():
            raise Refuse(f"target dir {root} does not exist")
        rr = root.resolve()
        for path, _ in files:
            t = root / path
            cur = root
            for seg in path.split("/"):
                cur = cur / seg
                if cur.is_symlink():
                    raise Refuse(f"{path}: {cur} is a symlink")
            if t.exists() and not t.is_file():
                raise Refuse(f"{path}: target exists and is not a regular file")
            if rr not in t.resolve().parents:
                raise Refuse(f"{path}: resolves outside the target dir")
    except (Refuse, OSError) as e:
        print(f"extract_files: {e}; nothing written", file=sys.stderr)
        return 1
    if a.check:
        for path, body in files:
            print(f"extract_files: ok {path} ({len(body)} bytes, "
                  f"sha256 {hashlib.sha256(body).hexdigest()})")
        return 0
    for path, body in files:
        t = root / path
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_bytes(body)
        print(f"extract_files: wrote {path} ({len(body)} bytes, "
              f"sha256 {hashlib.sha256(body).hexdigest()})")
    if a.list_out:
        Path(a.list_out).write_text("".join(p + "\n" for p, _ in files), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
