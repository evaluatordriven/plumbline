#!/usr/bin/env python3
"""Deterministic builder of the Maker prompt (iter1; whole-file output protocol from generation 3, D6) for job 2026-10-27-custody-emitter-gaps. Stdlib only.

Makes no network or model call. Reads only: the frozen bar.md in this job folder, the frozen harness or_call.py
(for its log format), and source files at the artifact base commit via `git show BASE:path`. It never reads the
held-out controls or fixtures (/workspace/next-job-controls) and never reads the OpenRouter key.

  build_maker_messages.py --repo /workspace/plumbline-pr --out handoffs/iter1/maker-messages.json
Re-running it must give the same bytes (sha256 recorded in handoffs/iter1/MANIFEST.sha256).
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

JOB = Path(__file__).resolve().parent.parent
BASE = "ff350e36dc04ea6baf898acd909787fcc7c1b6d4"
EDITABLE = ["kit/emit_custody.py", "kit/custody_history.py", "kit/custody_ledger.py",
            "tools/pack_stranger_bundle.py", "docs/custody-emission.md", "tests/fixtures/custody/**"]
SOURCES = ["kit/emit_custody.py", "kit/custody_history.py", "kit/custody_ledger.py",
           "tools/pack_stranger_bundle.py", "docs/custody-emission.md",
           "tests/fixtures/custody/job-rejected/README.md", "tests/fixtures/custody/failures/README.md"]
# custody SPEC v0.9.6 @ 3e3ca58de5631bdc58291564303a2e9d25a8653e, SPEC.md sha256 a289ac91...294f, lines 198 and 204, verbatim.
CL1 = [
    "| CL1-9 | In every batch, each evaluator with a check that is not `unobserved` reads at least two controls there: one whose expected outcome is `conforms`, and one whose expected outcome is `does_not_conform`. Every control records its expected and actual outcome. A control is a case whose correct outcome is known in advance. A control whose actual outcome differs from its expected outcome shows its reader could not be relied on: every check by that evaluator in that batch reads `unobserved`, or, if the control names a `dimension`, every such check of that dimension. | semantic |",
    "| CL1-15 | For every model evaluator, `external` holds evidence of its configuration \u2014 for example a harness log showing which model and endpoint answered \u2014 read by a named party who is not the maker. A model's own settings block (`model`) is a claim, not evidence. | external |",
]

SYSTEM = """You are the Maker for a commissioned code fix in the open-source repository smoitozo/plumbline.
You write the whole change yourself. You return the COMPLETE new contents of every file you change or add. A harness
operator writes each returned file into a checkout of base commit """ + BASE + """ exactly as you return
it, byte for byte: it will not edit, complete, merge, reorder or reformat anything, and it writes nothing if any
rule below is broken. Then it runs the test suite. If extraction or the tests fail, you get the verbatim error
output and must return the complete set of files again.

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
4. Each path at most once. No content line may start with <<<PLUMBLINE- . Files you do not return stay as they
   are at the base; there is no delete.
5. Allowed paths only: """ + ", ".join(EDITABLE) + """ (** = any file under that folder).
   Anything else is rejected. Do not touch anything under dot-plumbline/. Keep Python stdlib-only.
6. Keep the change focused: change only what the criteria need; return a file only if you change or add it, and
   keep every line you are not changing exactly as it is at the base (shown below).
7. The existing test suite `tests/validate_schemas.py` (112 cases, all passing at the base) must still pass.
"""

def git_show(repo: str, path: str) -> str:
    return subprocess.run(["git", "-C", repo, "show", f"{BASE}:{path}"], check=True, capture_output=True,
                          text=True).stdout

def bar_section(bar: str, start: str, end: str) -> str:
    i, j = bar.index(start), bar.index(end)
    return bar[i:j].rstrip() + "\n"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    bar = (JOB / "custody/bar.md").read_text(encoding="utf-8")
    dims = bar_section(bar, "## Dimensions (artifact)", "## Process requirements")
    m = re.search(r"Operator rule \(Maker\):.*?written by the Orchestrator\.\n", bar, re.S)
    if not m:
        sys.exit("operator rule not found in bar.md")
    orcall = (JOB / "custody/freeze/harness/or_call.py").read_text(encoding="utf-8")
    parts = [
        "# Task: fix custody emitter gaps 1-3 in smoitozo/plumbline (base main @ " + BASE + ")\n",
        "The frozen pass bar below is the whole acceptance test. Every dimension N1-N8 must PASS; N9 is a control "
        "the evaluator runs (it must keep failing on a bundle with the ledger removed). The evaluator runs its own "
        "held-out fixture jobs (`single-call`, `maker-10min`, `genreply-null`, `genreply-full`) and controls that "
        "you will not see; they are job folders shaped like tests/fixtures/custody/job-rejected, whose Maker and "
        "evaluator harness logs are written by the harness below (one JSON entry per call with `sent_at`, "
        "`received_at`, response headers incl. `Date`, raw response, and the `/api/v1/generation` reply, which "
        "may be null).\n\n"
        "Gap 1 (N1-N3): maker.startedAt / producedAt must come from the logger's `sent_at` of the FIRST Maker call "
        "and `received_at` of the LAST Maker call (not the `created` epoch or the `Date` header), each time with an "
        "`x-plumbline` source naming file and line.\n"
        "Gap 2 (N4-N6): when a model pass has no /api/v1/generation reply, never derive an `endpoint` from routing "
        "config or provider pins; refuse with a named error or record the CL1-15 evidence absent with an "
        "`x-plumbline` flag naming the pass.\n"
        "Gap 3 (N7-N8): the stranger bundle must also carry `inputs/custody-events.jsonl` and every maker/evaluator "
        "harness log the record's times or endpoints came from, so a stranger can re-derive them.\n",
        "## Frozen bar: dimensions (verbatim from custody/bar.md, digest 3ced9bc0...970b)\n\n" + dims,
        "## Frozen bar: operator rule (verbatim)\n\n" + m.group(0),
        "## custody SPEC v0.9.6 @ 3e3ca58, CL1 lines the record must meet (verbatim)\n\n" + "\n".join(CL1) + "\n",
    ]
    for p in SOURCES:
        parts.append(f"## FILE {p} (at base)\n\n```\n{git_show(a.repo, p)}```\n")
    parts.append("## FILE dot-plumbline/jobs/2026-10-27-custody-emitter-gaps/custody/freeze/harness/or_call.py "
                 "(frozen harness that writes the harness logs; reference only, do not modify)\n\n```\n" + orcall + "```\n")
    parts.append("Return your files now, following the OUTPUT CONTRACT exactly.\n")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(parts)}]
    Path(a.out).write_text(json.dumps(msgs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    sys.exit(main())
