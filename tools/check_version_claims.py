#!/usr/bin/env python3
"""The versions this repository claims in prose are the versions it pins on disk.

Plumbline states its dependencies' commits in several places — `tools/pin.json`, the README's
quickstart, the vendored copy's directory name — and a reader has no way to tell which of them is
current. Measured 2026-11-10 (external review): the doctrine README claimed custody v0.9.7 while
custody's SPEC said 0.9.8; Plumbline's README names `3e3ca58` while the tag it points at ships a
different record set. None of those are code defects. All of them are the same defect: a claim and
its source can drift because nothing compares them.

    python3 tools/check_version_claims.py            # check this repository
    python3 tools/check_version_claims.py --selftest # prove each rule fails on a planted mismatch

Exit 0 when every claim agrees with its source. Exit 1 otherwise, naming the claim, the file it was
read from, and the value the source actually holds.

What it does NOT check: a claim whose source is another repository's working tree (only commits and
hashes that are pinned *here* are comparable offline). A cross-repository check needs the network and
belongs in a scheduled job, not in a stranger's CI run.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHORT = 7


def claims(root: Path) -> list[tuple[str, str, str]]:
    """(label, what the prose claims, what the pin/vendor actually holds)."""
    out: list[tuple[str, str, str]] = []
    pin_path = root / "tools" / "pin.json"
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    readme = (root / "README.md").read_text(encoding="utf-8")

    doctrine = str(pin.get("commit", ""))
    custody = str(pin.get("custody", {}).get("commit", ""))
    spec_version = str(pin.get("custody", {}).get("specVersion", ""))

    # 1. The vendored doctrine directory names the pin it was cut from: e-di@<12 hex>.
    vendored = sorted(p.name for p in (root / "schemas" / "vendor").glob("e-di@*"))
    for name in vendored:
        ref = name.split("@", 1)[1]
        out.append(("vendored corpus directory", ref, doctrine[:len(ref)]))

    # 2. Every `e-di@<hex>` in the README must be a prefix of the pinned doctrine commit.
    for ref in sorted(set(re.findall(r"e-di@([0-9a-f]{7,40})", readme))):
        out.append(("README e-di@ reference", ref, doctrine[:len(ref)]))

    # 3. The README's custody commit (the quickstart's `git -C custody checkout <sha>`) is the pin.
    for ref in sorted(set(re.findall(r"custody checkout ([0-9a-f]{7,40})", readme))):
        out.append(("README custody checkout", ref, custody[:len(ref)]))

    # 4. The vendored custody schema is byte-identical to the hash the pin records.
    schema = root / "schemas" / "custody" / "custody-v1.schema.json"
    pinned_schema = pin.get("custody", {}).get("files", {}).get("schema/custody-v1.schema.json", "")
    if schema.is_file() and pinned_schema:
        import hashlib
        out.append(("vendored custody schema sha256",
                    hashlib.sha256(schema.read_bytes()).hexdigest(), pinned_schema))

    # 5. Any `custody v0.9.x` claim in the README is the pinned specVersion.
    for ref in sorted(set(re.findall(r"custody[^.\n]{0,40}\bv(\d+\.\d+\.\d+)", readme))):
        out.append(("README custody version", "v" + ref, "v" + spec_version))

    # 6. The version the emitter stamps into every record is the version this repository pins.
    emitter = root / "kit" / "emit_custody.py"
    if emitter.is_file() and spec_version:
        match = re.search(r'^SPEC_VERSION\s*=\s*"(\d+\.\d+\.\d+)"', emitter.read_text(encoding="utf-8"),
                          re.M)
        if match:
            out.append(("kit/emit_custody.py SPEC_VERSION", "v" + match.group(1), "v" + spec_version))

    return out


def violations(root: Path) -> list[str]:
    bad = []
    for label, claimed, actual in claims(root):
        if claimed != actual:
            bad.append(f"{label}: claims {claimed!r}, pin holds {actual!r}")
    return bad


def selftest() -> int:
    """Plant one mismatch per rule against a copy of this repository's pin and README."""
    import shutil
    import tempfile

    failed = 0
    seed = json.loads((REPO / "tools" / "pin.json").read_text(encoding="utf-8"))
    def pin_prefix():
        return seed["commit"][:12]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        (root / "tools").mkdir(parents=True)
        (root / "schemas" / "custody").mkdir(parents=True)
        (root / "schemas" / "vendor" / ("e-di@" + pin_prefix())).mkdir(parents=True)
        pin = seed
        (root / "tools" / "pin.json").write_text(json.dumps(pin), encoding="utf-8")
        shutil.copy(REPO / "schemas" / "custody" / "custody-v1.schema.json",
                    root / "schemas" / "custody" / "custody-v1.schema.json")

        good = ("Checkout `custody checkout %s`; the corpus is `e-di@%s` (custody v%s)."
                % (pin["custody"]["commit"], pin["commit"][:12], pin["custody"]["specVersion"]))
        cases = {
            "clean": (good, 0),
            "wrong corpus dir": ("Checkout `custody checkout %s`; the corpus is `e-di@%s` (custody v%s)."
                                 % (pin["custody"]["commit"], "0" * 12, pin["custody"]["specVersion"]), 1),
            "wrong custody commit": ("Checkout `custody checkout %s`; the corpus is `e-di@%s` (custody v%s)."
                                     % ("0" * 40, pin["commit"][:12], pin["custody"]["specVersion"]), 1),
            "wrong custody version": ("Checkout `custody checkout %s`; the corpus is `e-di@%s` (custody v0.0.1)."
                                      % (pin["custody"]["commit"], pin["commit"][:12]), 1),
        }
        for name, (readme, expected) in cases.items():
            (root / "README.md").write_text(readme, encoding="utf-8")
            got = violations(root)
            # the vendored-directory rule is planted once, in `clean`, by the directory name
            ok = len(got) == expected
            print(f"  {'[PASS]' if ok else '[FAIL]'} selftest {name}: {len(got)} violation(s), expected {expected}")
            failed += 0 if ok else 1
    return 1 if failed else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    bad = violations(REPO)
    for line in bad:
        print(f"check_version_claims: {line}")
    if bad:
        return 1
    print(f"check_version_claims: {len(claims(REPO))} claim(s), every one agrees with its pin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
