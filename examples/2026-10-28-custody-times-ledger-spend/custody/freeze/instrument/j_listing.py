#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — E-GLM listing builder (J1, J2, J3, J4), job 2026-10-28-custody-times-ledger-spend.
"""Deterministic reading text for one revision (stdlib + git only).

  J1: every hunk of `git diff -U8 <BASE>..HEAD` over the J1 files (a new file shows whole, all "+"), as the
      revision's numbered lines: added "+", context " ", removed "-" (no number).
  J2: the revision's whole docs/custody-emission.md, numbered; lines added or changed since BASE marked "+".

  J3, J4: the revision's whole docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md, numbered (item 30; a new file, so no marks).

  j_listing.py --check J1|J2|J3|J4 --rev CHECKOUT [--out FILE]
"""
import argparse, re, subprocess, sys

BASE = "3df1ce52eddfe18705e380c4b6e99cf617cfa24b"
J1_FILES = ["kit/emit_custody.py", "kit/custody_history.py", "kit/custody_ledger.py", "kit/plumbline_job.py",
            "kit/plumbline_verify.py"]
J2_FILE = "docs/custody-emission.md"
FG_FILE = "docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md"


def _diff(rev, files, u):
    return subprocess.run(["git", "-C", rev, "diff", f"-U{u}", "--no-color", "--no-renames", f"{BASE}..HEAD", "--", *files],
                          capture_output=True, check=True).stdout.decode("utf-8")


def j1(rev):
    out, n, cur = [], 0, None
    for l in _diff(rev, J1_FILES, 8).split("\n"):
        if l.startswith("diff --git"):
            cur = None; continue
        if l.startswith("+++ "):
            cur = l[6:] if l.startswith("+++ b/") else l[4:]
            out.append(f"=== FILE {cur} (line numbers are the revision's) ==="); continue
        if l.startswith(("--- ", "index ", "new file mode", "deleted file mode", "similarity", "Binary")) or cur is None:
            continue
        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", l)
        if m:
            n = int(m.group(1)); out.append("..."); continue
        if l.startswith("+"):
            out.append(f"{n:5d} + {l[1:]}"); n += 1
        elif l.startswith("-"):
            out.append(f"      - {l[1:]}")
        elif l.startswith(" "):
            out.append(f"{n:5d}   {l[1:]}"); n += 1
    return "\n".join(out) + "\n"


def j2(rev):
    added, n = set(), 0
    for l in _diff(rev, [J2_FILE], 0).split("\n"):
        m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", l)
        if m:
            s, c = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            added.update(range(s, s + c))
    text = subprocess.run(["git", "-C", rev, "show", f"HEAD:{J2_FILE}"], capture_output=True, check=True).stdout.decode("utf-8")
    out = [f"=== FILE {J2_FILE} (the whole file at the revision; lines marked + were added or changed) ==="]
    for i, l in enumerate(text.split("\n"), 1):
        if i == len(text.split("\n")) and l == "":
            break
        out.append(f"{i:5d} {'+' if i in added else ' '} {l}")
    return "\n".join(out) + "\n"


def jfg(rev):
    p = subprocess.run(["git", "-C", rev, "show", f"HEAD:{FG_FILE}"], capture_output=True)
    if p.returncode != 0:
        return f"=== FILE {FG_FILE} is MISSING at the revision ===\n"
    text = p.stdout.decode("utf-8", "replace")
    out = [f"=== FILE {FG_FILE} (the whole file at the revision, numbered) ==="]
    ls = text.split("\n")
    if ls and ls[-1] == "":
        ls = ls[:-1]
    out += [f"{i:5d}   {l}" for i, l in enumerate(ls, 1)]
    return "\n".join(out) + "\n"


def listing(check, rev):
    return {"J1": j1, "J2": j2, "J3": jfg, "J4": jfg}[check](rev)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--check", required=True, choices=["J1", "J2", "J3", "J4"])
    ap.add_argument("--rev", required=True); ap.add_argument("--out")
    a = ap.parse_args()
    t = listing(a.check, a.rev)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(t)
    else:
        sys.stdout.write(t)


if __name__ == "__main__":
    main()
