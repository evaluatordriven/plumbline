#!/usr/bin/env python3
"""Every GitHub Action a workflow uses is pinned by commit, not by tag.

D4.12: a workflow that says `uses: actions/checkout@v4` is running whatever that tag points at
today. A tag is a moving reference — it can be re-pointed, and then the same commit of this
repository executes different code than it did yesterday. A 40-hex commit id cannot move.

    python3 tools/check_action_pins.py            # check this repository's workflows
    python3 tools/check_action_pins.py --selftest # prove the check fails on a tag pin

Exit 0 when every `uses:` is either a local action (`./…`) or a commit id with a `# vX` comment
saying which release that commit was. Exit 1 otherwise, naming the file and the line.

The `# vX` comment is required, not cosmetic: a bare SHA is unreadable to a human reviewer, and a
reviewer who cannot read the pin will eventually ask for the tag back.
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)\s*(?:#\s*(\S+))?\s*$")
PINNED = re.compile(r"^[0-9a-f]{40}$")


def violations(text: str) -> list[str]:
    """Every `uses:` in a workflow body that is not a local action or a commented commit pin."""
    bad = []
    for number, line in enumerate(text.splitlines(), 1):
        match = USES.match(line)
        if not match:
            continue
        target, comment = match.group(1), match.group(2)
        if target.startswith("./"):
            continue
        if "@" not in target:
            bad.append(f"line {number}: {target} names no ref at all")
            continue
        name, ref = target.rsplit("@", 1)
        if PINNED.match(ref):
            if not comment or not re.match(r"^v\d", comment):
                bad.append(f"line {number}: {name}@{ref[:12]}… is pinned but names no release "
                           f"(add `# vN` so a reviewer can read it)")
            continue
        bad.append(f"line {number}: {name}@{ref} is a moving ref; pin the commit id "
                   f"(git ls-remote or the tags API) and add `# {ref}`")
    return bad


def selftest() -> int:
    """Two planted workflows: one tag-pinned, one commit-pinned without its release comment."""
    cases = {
        "tag pin": ("jobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4\n", 1),
        "bare pin": ("jobs:\n  x:\n    steps:\n      - uses: actions/checkout@%s\n" % ("a" * 40), 1),
        "good": ("jobs:\n  x:\n    steps:\n      - uses: actions/checkout@%s # v7\n"
                 "      - uses: ./.github/actions/local\n" % ("a" * 40), 0),
    }
    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, (body, expected) in cases.items():
            path = Path(tmp) / "ci.yml"
            path.write_text(body, encoding="utf-8")
            got = len(violations(path.read_text(encoding="utf-8")))
            ok = got == expected
            print(f"  {'[PASS]' if ok else '[FAIL]'} selftest {name}: {got} violation(s), expected {expected}")
            failed += 0 if ok else 1
    return 1 if failed else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if not files:
        print("check_action_pins: no workflows found under %s" % WORKFLOWS)
        return 0
    total = 0
    for path in files:
        bad = violations(path.read_text(encoding="utf-8"))
        for line in bad:
            print(f"{path.relative_to(REPO)}: {line}")
        total += len(bad)
    if total:
        print(f"check_action_pins: {total} unpinned action(s)")
        return 1
    print(f"check_action_pins: {len(files)} workflow(s), every action pinned by commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
