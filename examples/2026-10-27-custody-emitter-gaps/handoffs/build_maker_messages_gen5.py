#!/usr/bin/env python3
"""Deterministic builder of the generation-5 Maker prompt (E-DI iteration 3) for job 2026-10-27-custody-emitter-gaps.
Stdlib only. It makes no network or model call and never reads the OpenRouter key.

DRAFT: it is used only if Steve approves AMENDMENT-6 (cap restated as 3 E-DI iterations).

This is a documented variant of build_maker_messages_gen4.py and reuses build_maker_messages.py's SYSTEM (OUTPUT
CONTRACT), CL1 lines and SOURCES. It differs in three ways:
  1. The base is the generation-4 Maker commit 73863fb (accepted, evaluated in batch 3). Sources are read with
     `git show 73863fb:path`, and the SYSTEM text names that commit as the base.
  2. It adds the Evaluator's iteration-2 findings (EVAL-ITER2-VERDICT.md). They are read from committed, control-free
     evidence (custody/evidence/eval/iter2-b3/):
       - s1--summary.json: the scores.
       - s1--subject-verdicts.digest.json: the instrument reasons, with held-out record values already redacted.
       - n6--n6-b3-2.reply.txt: E-GLM's reply on the subject (the subject call, not a control).
     No held-out control or fixture content is read. As a guard, it refuses to build if any reason still carries an
     unredacted quoted record value, or if the failing runs are not the ones the text below describes.
  3. It also shows the inputs of the repository's own fixture tests/fixtures/custody/job-rejected (public, at 73863fb),
     because the one failing run is that fixture.

  build_maker_messages_gen5.py --repo /workspace/plumbline-pr --out handoffs/iter3/maker-messages-gen5.json
Re-running it must give the same bytes (sha256 in handoffs/iter1/MANIFEST.sha256).
"""
import argparse, importlib.util, json, re, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True   # no __pycache__ in the job folder

HERE = Path(__file__).resolve().parent
JOB = HERE.parent
spec = importlib.util.spec_from_file_location("bmm", HERE / "build_maker_messages.py")
bmm = importlib.util.module_from_spec(spec); spec.loader.exec_module(bmm)

BASE5 = "73863fb00c72239de0f0c2def4f68d1c6dfd902b"
EV = JOB / "custody/evidence/eval/iter2-b3"
FIXTURE_INPUTS = ["tests/fixtures/custody/job-rejected/inputs/custody-events.jsonl",
                  "tests/fixtures/custody/job-rejected/inputs/custody.json"]
SYSTEM5 = bmm.SYSTEM.replace(bmm.BASE, BASE5)
assert SYSTEM5 != bmm.SYSTEM and bmm.BASE not in SYSTEM5


def git_show(repo: str, path: str) -> str:
    return subprocess.run(["git", "-C", repo, "show", f"{BASE5}:{path}"], check=True, capture_output=True,
                          text=True).stdout


def findings() -> str:
    summ = json.loads((EV / "s1--summary.json").read_text(encoding="utf-8"))
    dig = json.loads((EV / "s1--subject-verdicts.digest.json").read_text(encoding="utf-8"))["verdicts"]
    reply = (EV / "n6--n6-b3-2.reply.txt").read_text(encoding="utf-8")
    for r in dig:
        for w in r["why"]:
            if re.search(r"record '(?!<held-out fixture value>)", w):
                sys.exit("unredacted record value in reasons")
    failing = [r for r in dig if r["verdict"] != "PASS"]
    if [r["file"] for r in failing] != ["s1/subject/N3-extra-1-job-rejected.json"]:
        sys.exit("failing runs differ from the text this builder states; stop")
    if summ["scores"] != {"N1": 1, "N2": 1, "N3": 0, "N4": 1, "N5": 1, "N7": 1, "N8": 1}:
        sys.exit("scores differ from the text this builder states; stop")
    if not reply.startswith("VERDICT: CONFORMS"):
        sys.exit("N6 reply is not CONFORMS; stop")
    scores = ", ".join(f"{k} {v}" for k, v in summ["scores"].items())
    why = "\n".join(f"  - {w}" for w in failing[0]["why"])
    return (
        "## Evaluator findings on the previous generation (iteration 2, generation 4; commit " + BASE5 + ")\n\n"
        "The previous generation's files are the current state of the repository: the base shown below IS your "
        "previous accepted work. The independent evaluator ran the frozen bar against it:\n\n"
        f"S1 instrument scores (1 = PASS, 0 = FAIL): {scores}. N6 (model evaluator): PASS. Its clean and planted "
        "controls read as expected, so the verdict counts. Every dimension N1-N8 must PASS. N3 is the only failing "
        "dimension; keep N1, N2, N4, N5, N6, N7 and N8 passing.\n\n"
        "### N3: FAIL on one run only. Instrument reasons, verbatim:\n\n"
        "- run `extra-1-job-rejected`:\n" + why + "\n\n"
        "What that run is. `extra-1-job-rejected` is the repository's own synthetic fixture "
        "`tests/fixtures/custody/job-rejected` (not a held-out fixture); the instrument runs every folder under "
        "`tests/fixtures/custody/` that has `inputs/custody.json`, and checks N3 on every record that is written. Its "
        "ledger `inputs/custody-events.jsonl` (shown below) holds a single `pin` event. It has no event that carries "
        "the bar's frozen-at time, either approval time or the disposition time; those four times exist only as "
        "hand-entered values in `inputs/custody.json` (shown below), and your record cites `inputs/custody.json` as "
        "their source. The bar's N3 accepts only a ledger or harness-log file and line that carries that time; any "
        "time without such a source fails. On the same record, startedAt, producedAt and checks[].at PASS (they cite "
        "harness logs), and every time field on the held-out fixtures PASSes.\n\n"
        "### N6: PASS. The model evaluator's reply on your code, verbatim (line numbers refer to the base files shown below):\n\n"
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
        "# Task: fix custody emitter gaps 1-3 in smoitozo/plumbline (generation 5; base = your generation-4 commit "
        + BASE5 + ", itself on main @ " + bmm.BASE + ")\n",
        "The frozen pass bar below is the whole acceptance test. Every dimension N1-N8 must PASS; N9 is a control "
        "the evaluator runs (it must keep failing on a bundle with the ledger removed). The evaluator runs its own "
        "held-out fixture jobs (`single-call`, `maker-10min`, `genreply-null`, `genreply-full`) and controls that "
        "you will not see, and also every fixture job under `tests/fixtures/custody/`. The held-out jobs are shaped "
        "like tests/fixtures/custody/job-rejected, and their Maker and evaluator harness logs are written by the "
        "harness below (one JSON entry per call with `sent_at`, `received_at`, response headers incl. `Date`, raw "
        "response, and the `/api/v1/generation` reply, which may be null).\n\n"
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
    for p in bmm.SOURCES + FIXTURE_INPUTS:
        parts.append(f"## FILE {p} (at base {BASE5[:7]})\n\n```\n{git_show(a.repo, p)}```\n")
    parts.append("## FILE dot-plumbline/jobs/2026-10-27-custody-emitter-gaps/custody/freeze/harness/or_call.py "
                 "(frozen harness that writes the harness logs; reference only, do not modify)\n\n```\n" + orcall + "```\n")
    parts.append("Return your files now, following the OUTPUT CONTRACT exactly.\n")
    msgs = [{"role": "system", "content": SYSTEM5}, {"role": "user", "content": "\n".join(parts)}]
    Path(a.out).write_text(json.dumps(msgs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
