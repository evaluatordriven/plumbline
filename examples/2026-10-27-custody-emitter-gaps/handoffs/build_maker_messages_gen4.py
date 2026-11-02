#!/usr/bin/env python3
"""Deterministic builder of the generation-4 Maker prompt (iteration 2) for job 2026-10-27-custody-emitter-gaps.
Stdlib only. It makes no network or model call and never reads the OpenRouter key.

This is a documented variant of build_maker_messages.py. It reuses that script's SYSTEM (OUTPUT CONTRACT), CL1 lines,
EDITABLE and SOURCES, and differs in two ways:
  1. The base is the generation-3 Maker commit 7cc38f8 (= ff350e3 + gen 3's accepted files). The sources are read with
     `git show 7cc38f8:path`, and the SYSTEM text names that commit as the base.
  2. It adds the Evaluator's iteration-1 findings (EVAL-ITER1-VERDICT.md). They are read from committed, control-free
     evidence (custody/evidence/eval/iter1-b2/):
       - s1--summary.json: the scores.
       - s1--subject-verdicts.digest.json: the instrument reasons, with record time values already redacted.
       - n6--n6-b2-2.reply.txt: E-GLM's reply on the subject (the subject call, not a control).
     No held-out control or fixture content is read. As a guard, it refuses to build if any reason still carries an
     unredacted quoted record value.

  build_maker_messages_gen4.py --repo /workspace/plumbline-pr --out handoffs/iter2/maker-messages-gen4.json
Re-running it must give the same bytes (sha256 in handoffs/iter1/MANIFEST.sha256).
"""
import argparse, importlib.util, json, re, sys
from pathlib import Path

sys.dont_write_bytecode = True   # no __pycache__ in the job folder

HERE = Path(__file__).resolve().parent
JOB = HERE.parent
spec = importlib.util.spec_from_file_location("bmm", HERE / "build_maker_messages.py")
bmm = importlib.util.module_from_spec(spec); spec.loader.exec_module(bmm)

BASE4 = "7cc38f833f8f5eeceffcb405885adb05141f8c65"
EV = JOB / "custody/evidence/eval/iter1-b2"
SYSTEM4 = bmm.SYSTEM.replace(bmm.BASE, BASE4)
assert SYSTEM4 != bmm.SYSTEM and bmm.BASE not in SYSTEM4


def git_show(repo: str, path: str) -> str:
    import subprocess
    return subprocess.run(["git", "-C", repo, "show", f"{BASE4}:{path}"], check=True, capture_output=True,
                          text=True).stdout


def findings() -> str:
    summ = json.loads((EV / "s1--summary.json").read_text(encoding="utf-8"))
    dig = json.loads((EV / "s1--subject-verdicts.digest.json").read_text(encoding="utf-8"))["verdicts"]
    reply = (EV / "n6--n6-b2-2.reply.txt").read_text(encoding="utf-8")
    for r in dig:
        for w in r["why"]:
            if re.search(r"record '(?!<held-out fixture value>)", w):
                sys.exit("unredacted record value in reasons")
    run = lambda f: f.split("/")[-1][:-5].split("-", 1)[1] if "-" in f.split("/")[-1][:-5] else "(single run)"
    lines = []
    for chk in ("N1", "N3"):
        lines.append(f"### {chk}: FAIL. Instrument reasons, verbatim, per run (runs not listed PASS):\n")
        for r in dig:
            if r["check"] == chk and r["verdict"] != "PASS":
                lines.append(f"- run `{run(r['file'])}`:")
                lines += [f"  - {w}" for w in r["why"]]
        lines.append("")
    scores = ", ".join(f"{k} {v}" for k, v in summ["scores"].items())
    return (
        "## Evaluator findings on the previous generation (iteration 1, generation 3; commit " + BASE4 + ")\n\n"
        "The previous generation's files are the current state of the repository: the base shown below IS your "
        "previous accepted work. The independent evaluator ran the frozen bar against it:\n\n"
        f"S1 instrument scores (1 = PASS, 0 = FAIL): {scores}. N6 (model evaluator): FAIL. Its clean and planted "
        "controls read as expected, so the verdict counts. Every dimension N1-N8 must PASS. Fix N1, N3 and N6, and "
        "keep N2, N4, N5, N7 and N8 passing.\n\n"
        "Run names: `F-single-call`, `F-maker-10min`, `F-genreply-full` and `F-genreply-null` are the held-out fixtures "
        "described above (prefix `F-`). `extra-1-job-rejected` is the repository's own fixture "
        "`tests/fixtures/custody/job-rejected`, which the instrument also runs (N1 covers every emitted record, "
        "including real jobs). Its Maker harness log entry has no `sent_at`/`received_at` (first reason below). Record "
        "time values quoted from fixture records are replaced by '<held-out fixture value>'.\n\n"
        + "\n".join(lines) + "\n"
        "### N6: FAIL. The model evaluator's reply on your code, verbatim (line numbers refer to the base files shown below):\n\n"
        "```\n" + reply + ("" if reply.endswith("\n") else "\n") + "```\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    bar = (JOB / "custody/bar.md").read_text(encoding="utf-8")
    dims = bmm.bar_section(bar, "## Dimensions (artifact)", "## Process requirements")
    m = re.search(r"Operator rule \(Maker\):.*?written by the Orchestrator\.\n", bar, re.S)
    if not m:
        sys.exit("operator rule not found in bar.md")
    orcall = (JOB / "custody/freeze/harness/or_call.py").read_text(encoding="utf-8")
    parts = [
        "# Task: fix custody emitter gaps 1-3 in smoitozo/plumbline (generation 4; base = your generation-3 commit "
        + BASE4 + ", itself on main @ " + bmm.BASE + ")\n",
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
        findings(),
        "## Frozen bar: dimensions (verbatim from custody/bar.md, digest 3ced9bc0...970b)\n\n" + dims,
        "## Frozen bar: operator rule (verbatim)\n\n" + m.group(0),
        "## custody SPEC v0.9.6 @ 3e3ca58, CL1 lines the record must meet (verbatim)\n\n" + "\n".join(bmm.CL1) + "\n",
    ]
    for p in bmm.SOURCES:
        parts.append(f"## FILE {p} (at base {BASE4[:7]})\n\n```\n{git_show(a.repo, p)}```\n")
    parts.append("## FILE dot-plumbline/jobs/2026-10-27-custody-emitter-gaps/custody/freeze/harness/or_call.py "
                 "(frozen harness that writes the harness logs; reference only, do not modify)\n\n```\n" + orcall + "```\n")
    parts.append("Return your files now, following the OUTPUT CONTRACT exactly.\n")
    msgs = [{"role": "system", "content": SYSTEM4}, {"role": "user", "content": "\n".join(parts)}]
    Path(a.out).write_text(json.dumps(msgs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
