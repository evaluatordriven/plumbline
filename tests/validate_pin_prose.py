#!/usr/bin/env python3
"""
Prose pins must agree with the machine pin.

The pin is written down in three places: `tools/pin.json` (machine), `AGENTS.md` (prose) and
`README.md` (prose). Only the machine one was checked. On 2026-09-30 a re-pin updated pin.json and
every derived schema while BOTH prose copies went on naming the previous commit — two drifts, one of
them committed before the second was even noticed, and a third copy found in README.md after that.

EARNED, NOT SPECULATIVE. The project rule is that a check must have a job that needed it, and here
the job produced three real instances in a single day. `--root` exists so the check can be SHOWN to
fail rather than merely asserted to pass: point it at a tree holding the pre-fix prose and it must
exit non-zero.

Rule: every `e-di@<sha>` in the prose is either the pinned commit, or sits on a line that records a
transition (contains `->`) — which is how a move is written down on purpose. The pinned commit must
appear in AGENTS.md, so the prose cannot silently drop the pin altogether.
"""
import argparse
import json
import pathlib
import re
import sys

PROSE = ('AGENTS.md', 'README.md')
PIN_RE = re.compile(r'e-di@([0-9a-f]{7,40})')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=str(pathlib.Path(__file__).resolve().parent.parent))
    args = ap.parse_args()
    root = pathlib.Path(args.root)

    pin_file = root / 'tools' / 'pin.json'
    if not pin_file.exists():
        print(f'FAIL  no pin at {pin_file}')
        return 1
    pin = json.loads(pin_file.read_text())['commit']

    problems, seen_in = [], {}
    for name in PROSE:
        path = root / name
        if not path.exists():
            problems.append(f'{name}: missing')
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            for sha in PIN_RE.findall(line):
                # The prose writes an abbreviated sha; pin.json holds the full one. Compare by
                # PREFIX — sha.startswith(pin) is wrong and silently never matches, which is
                # exactly how a check passes forever while checking nothing.
                if pin.startswith(sha):
                    seen_in.setdefault(name, []).append(n)
                elif '->' in line:
                    continue  # a documented transition, e.g. "edi@old -> edi@new"
                else:
                    problems.append(f'{name}:{n} names e-di@{sha[:12]} but the pin is {pin[:12]}')

    if 'AGENTS.md' not in seen_in:
        problems.append('AGENTS.md names no pin at all — the prose dropped it')

    if problems:
        print('PROSE PIN MISMATCH')
        for p in problems:
            print(f'  - {p}')
        print(f'\n  pin.json holds: {pin}')
        print('  Fix the prose, or re-pin and fix all three. A stale prose pin is a doc asserting')
        print('  a commit the repo does not hold.')
        return 1

    where = ', '.join(f'{k}:{v[0]}' for k, v in sorted(seen_in.items()))
    print(f'PROSE PINS AGREE  e-di@{pin[:12]}  ({where})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
