#!/usr/bin/env python3
"""Write the Maker's whole-file reply into a checkout, byte for byte. Stdlib only; no network; no model call.

  extract_files.py REPLY.txt TARGET_DIR [--list OUT.txt] [--check]

REPLY FORMAT (the Maker's OUTPUT CONTRACT; build_maker_messages.py states the same rules to the model):
  The reply is a sequence of file blocks followed by one DONE line, then optional NOTES lines:

    <<<PLUMBLINE-FILE path=kit/emit_custody.py>>>
    ...complete new contents of the file...
    <<<PLUMBLINE-END path=kit/emit_custody.py>>>
    <<<PLUMBLINE-DONE files=1>>>
    NOTES: ...

  * A marker line is exactly the marker text followed by "\\n" (a "\\r" before the "\\n" is NOT accepted).
  * A file's contents are the bytes from just after the "\\n" ending its FILE line up to (not including) the first
    byte of its END line. So the newline that ends the last content line is part of the file: the extractor
    adds no trailing newline, strips none, and changes no other byte (no decoding, no line-ending or whitespace
    normalization). A FILE line followed directly by its END line is an empty file. A file whose last byte is not
    "\\n" cannot be expressed (every editable file at the base ends in "\\n").
  * The END line repeats the FILE line's path exactly. DONE's count equals the number of FILE blocks.
  * Outside blocks only blank lines may appear before DONE; after DONE only blank lines and up to 20 lines starting
    with "NOTES:". No other text, no ``` fences around the blocks.
  * No content line may start with "<<<PLUMBLINE-" (that is how a missing END is detected).
  * Each path at most once. Paths: exactly one of ALLOWED, or a file under tests/fixtures/custody/; relative, "/"
    separated, no "." / ".." / empty segments, no backslash, no leading "/", printable ASCII without spaces.
  * There is no delete operation; a file not returned stays as it is.

All checks run before anything is written: any violation (malformed marker, unterminated block = truncation,
missing or wrong DONE, an END marker not at a line start, stray text, bad or disallowed path, duplicate path, target is a symlink or a directory)
→ exit 1, a one-line reason on stderr starting "extract_files: ", and NOTHING is written. Exit 0: every file
written (parents created as needed), "extract_files: wrote <path> (<n> bytes, sha256 <hex>)" per file on stdout,
and the paths one per line in --list OUT.txt if given. --check validates only (writes nothing).
Exit 2: usage error.
"""
import hashlib, re, sys
from pathlib import Path

ALLOWED = ("kit/emit_custody.py", "kit/custody_history.py", "kit/custody_ledger.py",
           "tools/pack_stranger_bundle.py", "docs/custody-emission.md")
ALLOWED_PREFIX = "tests/fixtures/custody/"
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
    if p in ALLOWED:
        return
    if p.startswith(ALLOWED_PREFIX) and len(p) > len(ALLOWED_PREFIX):
        return
    raise Refuse(f"path not allowed: {p}")


def parse(data: bytes) -> list[tuple[str, bytes]]:
    lines = [ln for ln in re.split(rb"(?<=\n)", data) if ln]   # split on "\n" only; every byte kept
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
                        raise Refuse(f"line {j + 1}: END marker for {path} is not at the start of a line (the file's "
                                     f"last line must end with a newline before the END line)")
                    j += 1
                if j >= n:
                    raise Refuse(f"block for {path} (FILE at line {i + 1}) has no END line: reply truncated")
                e = RE_END.match(lines[j])
                if not e:
                    raise Refuse(f"line {j + 1}: expected <<<PLUMBLINE-END path={path}>>>, got a malformed or "
                                 f"other marker line (a content line may not start with <<<PLUMBLINE-)")
                if e.group(1).decode("ascii", "replace") != path:
                    raise Refuse(f"line {j + 1}: END path {e.group(1).decode('ascii', 'replace')!r} "
                                 f"does not match FILE path {path!r}")
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
        raise Refuse("no <<<PLUMBLINE-DONE files=N>>> line: reply truncated or malformed")
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
    args, lst, check = [], None, False
    it = iter(argv)
    for a in it:
        if a == "--list":
            lst = next(it, None)
            if lst is None:
                print("usage: extract_files.py REPLY.txt TARGET_DIR [--list OUT.txt] [--check]", file=sys.stderr); return 2
        elif a == "--check":
            check = True
        else:
            args.append(a)
    if len(args) != 2:
        print("usage: extract_files.py REPLY.txt TARGET_DIR [--list OUT.txt] [--check]", file=sys.stderr); return 2
    reply, root = Path(args[0]), Path(args[1])
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
    except Refuse as e:
        print(f"extract_files: {e}; nothing written", file=sys.stderr)
        return 1
    if check:
        for path, body in files:
            print(f"extract_files: ok {path} ({len(body)} bytes, sha256 {hashlib.sha256(body).hexdigest()})")
        return 0
    for path, body in files:
        t = root / path
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_bytes(body)
        print(f"extract_files: wrote {path} ({len(body)} bytes, sha256 {hashlib.sha256(body).hexdigest()})")
    if lst:
        Path(lst).write_text("".join(p + "\n" for p, _ in files), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
