#!/usr/bin/env python3
"""Deterministic builder of one Maker request (whole-file output protocol) for job
2026-10-28-custody-times-ledger-spend. Stdlib only. Makes no network or model call. Adapted from job
2026-10-28-doctrine-reader-pointer's builder (same OUTPUT CONTRACT, same markers as extract_files.py).

An iteration is several Maker requests, one per PART, made in the order of PARTS. Each request shows the part's
files as they are NOW in the Maker checkout (--rev), so a later part sees what the earlier parts wrote. The field
guide is its own request (part `guide`), never mixed with code (bar, Maker output contract; approval item 30).

Reads only: the frozen bar (--bar), the frozen INTERFACE.md (--interface), files in the Maker checkout (--rev) and
at base (git show BASE:path), and, for part `guide` only, the two field-guide inputs (--fg-owner, --fg-orch, checked
against their pinned sha256s), the frozen fg_rules.json (--fg-rules) and the doctrine copy (--doctrine). It never
reads the held-out controls (/workspace/job-controls/2026-10-28-custody-times-ledger-spend) and never reads the
OpenRouter key. The bar's "Controls: ..." sentences and its planted-controls paragraph are omitted from the prompt.

  build_maker_messages.py --part PART --rev MAKER_CHECKOUT --out MESSAGES.json --bar BAR --interface INTERFACE.md
                          [--fg-owner F --fg-orch F --fg-rules F --doctrine F]       (the four are for --part guide)
Re-running it on the same inputs gives the same bytes.
"""
import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path

BASE = "3df1ce52eddfe18705e380c4b6e99cf617cfa24b"
FG = "docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md"
FG_OWNER_SHA = "fbf070f52a6ca6978604847d6afdcf5d469029ca5e143827291236940c31e344"
FG_ORCH_SHA = "01fe4e161dc5e56dca9e5dac0c4de706798207b4a680d13d154e100e95577e13"
DOCTRINE_SHA256 = "c9b45567f27738ca33662162e44fec121b1e840f34522fd9eb64e8fd3d49d6ed"

# part -> (what it owns, the paths it may return (same rules as extract_files.py PARTS), files shown in full,
#          read-only context files shown in full, extra glob of current files to show)
PARTS = {
    "ledger": dict(
        goal="checks T1, F1a-F1h (ledger commands, tool stamps, writer field) and the T5/T7 refusal logic in "
             "custody_history.py, with new tests",
        allowed="kit/custody_ledger.py, kit/custody_history.py, new tests/test_custody_ledger*.py",
        own=["kit/custody_ledger.py", "kit/custody_history.py"], ctx=[], glob=["tests/test_custody_ledger*.py"]),
    "emitter": dict(
        goal="checks T2-T7, F1h and X1 in kit/emit_custody.py (hand-time refusal, --allow-hand-times, "
             "x-plumbline block), tests/validate_schemas.py coverage, and any NEW fixture folders under "
             "tests/fixtures/custody/",
        allowed="kit/emit_custody.py, tests/validate_schemas.py, new folders under tests/fixtures/custody/",
        own=["kit/emit_custody.py", "tests/validate_schemas.py"],
        ctx=["kit/custody_ledger.py", "kit/custody_history.py"], glob=[]),
    "verifier": dict(
        goal="checks V1-V9: the new kit/plumbline_verify.py, the new schema "
             "schemas/x-plumbline/x-plumbline-v1.schema.json, the close-time hook in kit/plumbline_job.py (V8), "
             "with new tests",
        allowed="kit/plumbline_verify.py (new), schemas/x-plumbline/x-plumbline-v1.schema.json (new), "
                "kit/plumbline_job.py, new tests/test_plumbline_verify*.py, new folders under tests/fixtures/custody/",
        own=["kit/plumbline_verify.py", "schemas/x-plumbline/x-plumbline-v1.schema.json", "kit/plumbline_job.py"],
        ctx=["kit/emit_custody.py", "kit/custody_ledger.py"], glob=["tests/test_plumbline_verify*.py"]),
    "edi": dict(
        goal="checks I1, F7a-F7b, F8a-F8d and P1: tools/edi/ (or_call.py, judge_batch.py, fixture_run.py, "
             "extract_files.py, README.md) with new tests/test_edi_*.py",
        allowed="new files under tools/edi/, new tests/test_edi_*.py",
        own=[], ctx=["dot-plumbline/jobs/2026-10-28-doctrine-reader-pointer/custody/freeze/harness/or_call.py",
                     "dot-plumbline/jobs/2026-10-28-doctrine-reader-pointer/handoffs/extract_files.py"],
        glob=["tools/edi/*", "tests/test_edi_*.py"]),
    "docs": dict(
        goal="checks G3 and J2: docs/custody-emission.md and kit/README.md describe what the other parts built",
        allowed="docs/custody-emission.md, kit/README.md",
        own=["docs/custody-emission.md", "kit/README.md"],
        ctx=["kit/custody_ledger.py", "kit/plumbline_verify.py"], glob=["tools/edi/README.md"]),
    "guide": dict(
        goal="checks G4-G7, J3 and J4: the new Orchestrator field guide (approval item 30)",
        allowed=FG + " (new; the only file of this request)", own=[], ctx=[], glob=[]),
}
ORDER = list(PARTS)

SYSTEM = """You are the Maker for a commissioned change in the open-source repository smoitozo/plumbline.
You write the whole change yourself. This request is ONE PART of the change (named below); the other parts are
separate requests. You return the COMPLETE new contents of every file you change in this part. A harness operator
writes each returned file into the Maker checkout (base commit """ + BASE + """ plus the parts already
written) exactly as you return it, byte for byte: it will not edit, complete, merge, reorder or reformat anything,
and it writes nothing if any rule below is broken. Then it runs the test suite. If extraction or the tests fail,
you get the verbatim error output and must return the complete set of files of this part again.

OUTPUT CONTRACT (mandatory):
1. No diffs. For each file you change or add, give one block: a line that is exactly
   <<<PLUMBLINE-FILE path=RELATIVE/PATH>>>
   then the file's complete new contents, then a line that is exactly
   <<<PLUMBLINE-END path=RELATIVE/PATH>>>
   with the same path. The file's contents are every line between those two marker lines, each ending in a
   newline (the newline ending the last content line is the file's final newline). Never abbreviate: no "...",
   no "rest unchanged", no omitted sections; whatever is between the markers becomes the whole file.
2. After the last block, a line that is exactly <<<PLUMBLINE-DONE files=N>>> where N is the number of blocks.
3. Outside the blocks: nothing before DONE except blank lines (no prose, no ``` fences around blocks). After DONE you
   may add up to 20 lines starting with `NOTES:` explaining the change. Nothing else.
4. Each path at most once. No content line may start with <<<PLUMBLINE- . Files you do not return stay exactly as
   they are; there is no delete.
5. Allowed paths for THIS part only: {allowed}. Anything else is rejected. A file that exists under
   tests/fixtures/ at the base is never rewritten (new fixture folders only). Fixture-only or test-only fixes are
   not acceptable.
6. Every test that exists at the base must still pass with the same results; every new test must pass.
"""


def git_show(repo: str, rev: str, path: str) -> str | None:
    r = subprocess.run(["git", "-C", repo, "show", f"{rev}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def current(rev_dir: Path, path: str) -> str | None:
    p = rev_dir / path
    return p.read_text(encoding="utf-8") if p.is_file() else None


def section(bar: str, start: str, end: str) -> str:
    i = bar.index(start); j = bar.index(end, i)
    return bar[i:j].rstrip() + "\n"


def strip_controls(text: str) -> str:
    # drop "Controls: ..." / "Planted C-..." up to the end of the table cell (the next " | ")
    text = re.sub(r" ?(?:Controls:|Planted C-)[^|]*?(?= \| )",
                  " [the evaluator's held-out controls for this check are omitted from the Maker prompt]", text)
    return text


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fence(text: str) -> str:
    f = "````" if "```" in text else "```"
    return f"{f}\n{text}{'' if text.endswith(chr(10)) else chr(10)}{f}\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", required=True, choices=ORDER); ap.add_argument("--rev", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--bar", required=True)
    ap.add_argument("--interface", required=True)
    for k in ("--fg-owner", "--fg-orch", "--fg-rules", "--doctrine"):
        ap.add_argument(k)
    a = ap.parse_args()
    rev = Path(a.rev); P = PARTS[a.part]
    barb = Path(a.bar).read_bytes(); bar = barb.decode("utf-8")
    allow = section(bar, "## Allow-list (spec)", "## Scale and pass rule")
    contract = section(bar, "## Maker output contract", "## Checks (artifact)")
    checks = strip_controls(section(bar, "## Checks (artifact)", "Planted S1 controls"))
    parts = [f"# Part `{a.part}` ({ORDER.index(a.part) + 1} of {len(ORDER)}): {P['goal']}\n",
             "The commission is the frozen bar below (custody/bar.md, sha256 " + hashlib.sha256(barb).hexdigest() +
             "). This request covers only the part named above; the parts, in order, are " +
             ", ".join(f"`{p}`" for p in ORDER) + ". Allowed paths for this part: " + P["allowed"] + ".\n",
             "## Frozen bar: allow-list (verbatim)\n\n" + allow,
             "## Frozen bar: Maker output contract (verbatim)\n\n" + contract]
    if a.part == "guide":
        for k in ("fg_owner", "fg_orch", "fg_rules", "doctrine"):
            if not getattr(a, k):
                ap.error("--part guide needs --fg-owner, --fg-orch, --fg-rules and --doctrine")
        own, orch, rules, doc = (Path(getattr(a, k)) for k in ("fg_owner", "fg_orch", "fg_rules", "doctrine"))
        for p, want in ((own, FG_OWNER_SHA), (orch, FG_ORCH_SHA), (doc, DOCTRINE_SHA256)):
            if sha(p) != want:
                raise SystemExit(f"build_maker_messages: {p.name} sha256 {sha(p)} != pinned {want}; nothing written")
        g = section(bar, "### G4–G7", "### J:")
        j = "\n".join(l for l in checks.splitlines() if l.startswith(("| ID", "|---", "| J3", "| J4"))) + "\n"
        parts += [
            "## What to write\n\nWrite ONE new file, `" + FG + "`: the Plumbline Orchestrator field guide. Merge the "
            "two drafts below into one document: the Owner's draft gives the base structure and the generic "
            "\"Owner\" voice; the Orchestrator's guide gives the newer content. Requirements (approval item 30):\n"
            "(a) a status line near the top: the document is non-normative and the doctrine wins on conflict;\n"
            "(b) it reflects the Owner decisions of 2026-10-28 15:52 EDT: the tripwire at exactly 3 of the same "
            "failure class, then change the request; the shared key behind the harness pre-call spend guard, with "
            "key-usage reconciliation called an upper bound (do not recommend a per-job key); the cross-family "
            "pre-read optional, decided per job on the approval sheet;\n"
            "(c) it keeps these rules: finish_reason length with empty content is its own failure class (stop at the "
            "first one); no throttling (endpoint max output, no reasoning limit), sized tasks, finish_reason logged on "
            "every call; the cap counts E-DI iterations; handoffs name the command that writes files; check handoffs "
            "against standing rules; a live test of each model instrument is a freeze gate; write-once evidence; "
            "relayed approvals are not approvals; no /tmp;\n"
            "(d) every rule is paired with its real story (the concrete incident from a real job or review that "
            "taught it, taken from the drafts), placed with the rule, in field-guide style;\n"
            "(e) no verbatim quotes of the Owner (paraphrase Owner decisions as Owner decisions); no personal names, "
            "no email addresses, no absolute local paths, no key material or key fingerprints. Model and organization "
            "names the drafts already cite are fine;\n"
            "(f) the stale open items become a short list under a heading containing \"Carried forward\".\n"
            "Expect about 15 KB. Return exactly one file block.\n",
            "## Frozen bar: the field-guide checks (verbatim, controls omitted)\n\n" + strip_controls(g) + "\n" + j,
            "## fg_rules.json (frozen; the exact anchors, normalization and denylist G5-G7 apply)\n\n" +
            fence(rules.read_text(encoding="utf-8")),
            f"## Input 1: the Owner's draft (owner-draft.md, sha256 {FG_OWNER_SHA})\n\n" + fence(own.read_text(encoding="utf-8")),
            f"## Input 2: the Orchestrator's guide (orchestrator-guide.md, sha256 {FG_ORCH_SHA})\n\n" + fence(orch.read_text(encoding="utf-8")),
            "## DOCTRINE.md v0.1 @ dc61854 (evaluatordriven/doctrine, CC BY 4.0; the guide must not contradict it)\n\n" +
            fence(doc.read_text(encoding="utf-8")),
        ]
    else:
        parts += ["## Frozen bar: checks (verbatim, controls omitted)\n\n" + checks,
                  "## INTERFACE.md (frozen; how the instrument calls the subject)\n\n" +
                  fence(Path(a.interface).read_text(encoding="utf-8"))]
        shown = list(P["own"])
        for pat in P["glob"]:
            shown += sorted(str(p.relative_to(rev)) for p in rev.glob(pat) if p.is_file() and str(p.relative_to(rev)) not in shown)
        for path in shown:
            t = current(rev, path)
            base = git_show(str(rev), BASE, path)
            tag = "new in this iteration" if base is None else ("as at base" if t == base else "as written by an earlier part or attempt")
            parts.append(f"## FILE {path} ({tag})\n\n" + fence(t) if t is not None else f"## FILE {path}: does not exist yet (new file)\n")
        for path in P["ctx"]:
            t = current(rev, path)
            if t is not None:
                parts.append(f"## CONTEXT (read only; not in this part) {path}\n\n" + fence(t))
        tests = sorted(p.name for p in (rev / "tests").glob("*.py"))
        parts.append("## Tests present now under tests/\n\n" + "\n".join(tests) + "\n")
    parts.append("Return your files now, following the OUTPUT CONTRACT exactly.\n")
    msgs = [{"role": "system", "content": SYSTEM.replace("{allowed}", P["allowed"])},
            {"role": "user", "content": "\n".join(parts)}]
    Path(a.out).write_text(json.dumps(msgs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"build_maker_messages: part {a.part} -> {a.out} ({len(json.dumps(msgs))} chars, sha256 "
          f"{hashlib.sha256(Path(a.out).read_bytes()).hexdigest()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
