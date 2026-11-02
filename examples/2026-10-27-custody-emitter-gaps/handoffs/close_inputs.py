#!/usr/bin/env python3
"""Build the close inputs for job 2026-10-27-custody-emitter-gaps. Run by CLOSE-apply.sh; it decides nothing.

    close_inputs.py --job-dir J --run-out PATH --controls-dir DIR

Writes:
  J/inputs/custody.json   the existing ledger mirror (bar, approvals, orchestrator, routing) is kept as is, and
                          levelClaimed, subject, bar author/dimensions, maker, instrument, evaluators, passes,
                          controls, external, retention and separationGaps are added. Disposition is left to
                          CLOSE-apply.sh.
  J/custody/subject-c7db5b0.sha256   the artifact files under test, by digest (the §5 run's `artifact`)
  PATH (--run-out)        the iteration-3 run file for emit_record.py. It must be OUTSIDE J/inputs, because
                          plumbline_job.py close copies it in there.

Every value comes from a file in J: bar.md, the EVAL-ITER3 evidence copy (custody/evidence/eval/iter3-b4) and
the existing inputs. The only absolute paths are the held-out control case files (--controls-dir). These are
digested and never copied (bar P4).
"""
from __future__ import annotations
import argparse, json, re, subprocess
from hashlib import sha256
from pathlib import Path

GROKBOT_GAP = ("Grokbot's underlying model(s) are not disclosed by its operator; family and identifier "
               "recorded as undisclosed.")
P4_GAP = ("Controls and fixtures were held outside the Maker's and Evaluator's working trees with sha256 "
          "committed at freeze, but on a shared box both bots could technically read them; non-reading was "
          "instructed, not enforced.")
SUBJECT_REV = "c7db5b0"
SUBJECT = ["kit/emit_custody.py", "kit/custody_history.py", "tools/pack_stranger_bundle.py",
           "tests/fixtures/custody/job-rejected/inputs/custody-events.jsonl"]
B4 = "eval/iter3-b4"                       # under custody/evidence
S1_AT = "2026-10-28T14:13:53Z"             # mtime of the sealed batch's s1/summary.json (no S1 call log)
RUNNER = "handoffs/iter3-evaluator-b4.md"   # the batch-4 Evaluator procedure (S1, n6_batch.py, p5check.py)
S1_DIMS = ["N1", "N2", "N3", "N4", "N5", "N7", "N8"]


def h(p: Path) -> str:
    return sha256(p.read_bytes()).hexdigest()


def bar_dims(bar: Path) -> list[dict]:
    out = []
    for line in bar.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (N[1-8]) \| (.+?) \| (.+?) \| (.+?) \|$", line)
        if m:
            out.append({"id": m[1], "plumbline_dimension": m[1], "criterion": m[2].strip(),
                        "scale": {"anchors": {"0": "the check does not PASS as stated (includes NOT-RUN)",
                                              "1": "the check PASSES as stated"},
                                  "threshold": 1, "floor": 0},
                        "failureCondition": f"{m[1]} does not PASS as the criterion states, or is not run "
                                            f"(bar.md: binary scale, threshold 1)"})
    ids = [d["id"] for d in out]
    if ids != [f"N{i}" for i in range(1, 9)]:
        raise SystemExit(f"bar.md dimension rows parsed as {ids}, expected N1..N8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--run-out", required=True)
    ap.add_argument("--controls-dir", required=True)
    a = ap.parse_args()
    J = Path(a.job_dir).resolve()
    CD = Path(a.controls_dir).resolve()
    repo = Path(subprocess.check_output(["git", "-C", str(J), "rev-parse", "--show-toplevel"], text=True).strip())
    ev = J / "custody" / "evidence"

    # ---- the subject: the artifact files, as they are at HEAD (checked == c7db5b0 by CLOSE-apply.sh) ----
    lines = [f"{h(repo / n)}  {n}" for n in SUBJECT]
    (J / "custody" / f"subject-{SUBJECT_REV}.sha256").write_text(
        f"# artifact under evaluation: job/2026-10-27-custody-emitter-gaps @ {SUBJECT_REV} "
        f"(files changed from base ff350e3)\n" + "\n".join(lines) + "\n")

    s1 = json.loads((ev / B4 / "s1--summary.json").read_text())
    n6 = json.loads((ev / B4 / "n6--N6-batch.redacted.json").read_text())
    assert s1["controls"] == "as expected" and s1["mutants"] == "as expected", s1
    assert all(s1["scores"][d] == 1 for d in S1_DIMS), s1["scores"]
    assert n6["N6"] == "PASS" and n6["controls_ok"] is True and n6["dry_run"] is False, n6
    calls = {i["id"]: i for i in n6["items"]}

    ci = json.loads((J / "inputs" / "custody.json").read_text())
    ci["levelClaimed"] = "CL1"
    ci["files_dir"] = "../../.."           # the repo root: subject paths are repo paths
    ci["subject"] = SUBJECT
    ci["bar"] = {**ci["bar"], "author": "Steve Moitozo II", "dimensions": bar_dims(J / ci["bar"]["file"])}
    ci["maker"] = {"name": "DeepSeek V4.1 Flash 1017", "kind": "model", "version": "v4.1-flash-1017",
                   "method_file": "custody/method.md", "harness_log": "harness-maker-deepseek.log",
                   "model": {"family": "deepseek", "identifier": "deepseek/deepseek-v4.1-flash-1017",
                             "readOnly": False}}
    # runner = the written procedure that ran the evaluators (precedent: 2026-10-27-custody-v1-emission). Not
    # run_instrument.sh: that is S1's own script, filed as evaluator S1 (custody CL1-16).
    ci["instrument"] = {"rubric_file": "custody/bar.md", "runner_file": RUNNER}
    ci["evaluators"] = [
        {"id": "S1", "name": "S1 instrument script (N1-N5, N7, N8, N9 control)", "kind": "script",
         "script": {"name": "run_instrument.sh", "author": "Orchestrator drafter",
                    "file": "custody/freeze/instrument/run_instrument.sh"}},
        {"id": "E-GLM", "name": "GLM 5.3 Flash (N6)", "kind": "model", "harness_log": "harness-eval-glm-b4.log",
         "model": {"family": "glm", "identifier": "z-ai/glm-5.3-flash", "readOnly": True}},
    ]
    ci["passes"] = {
        "s1-b4": {"evaluator": "S1", "run": 1, "batch": "b4", "at": S1_AT, "dimensions": S1_DIMS,
                  "evidence": {d: f"{B4}/s1--summary.json" for d in S1_DIMS}},
        "glm-b4": {"evaluator": "E-GLM", "run": 1, "batch": "b4", "call": calls["subject"]["call"],
                   "dimensions": ["N6"], "evidence": {"N6": f"{B4}/n6--{calls['subject']['call']}.reply.txt"}},
    }
    ctl = []
    for kind, root in (("record-level", CD / "record-level"), ("p5", CD / "p5")):
        for d in sorted(p for p in root.iterdir() if p.is_dir()):
            cid = d.name
            m = re.match(r"C-(N[1-9]|P5)(c|p)", cid)
            exp = "conforms" if m[2] == "c" else "does_not_conform"
            k = {"id": cid, "batch": "b4", "evaluator": "S1", "case_file": str(d / "CONTROL.json"),
                 "expected": exp, "outcome": exp,           # s1/summary.json: "controls": "as expected"
                 "evidence_file": f"custody/evidence/{B4}/s1--summary.json", "at": S1_AT}
            if m[1] in {x["id"] for x in ci["bar"]["dimensions"]}:
                k["dimension"] = m[1]
            ctl.append(k)
    for gid, exp in (("G-c1", "conforms"), ("G-p1", "does_not_conform")):
        it = calls[gid]
        got = "conforms" if it["verdict"] == "CONFORMS" else "does_not_conform"
        assert it.get("control_ok") is True and got == exp, it
        ctl.append({"id": gid, "batch": "b4", "evaluator": "E-GLM", "case_file": str(CD / "glm" / f"{gid}.txt"),
                    "expected": exp, "outcome": got, "dimension": "N6", "call": it["call"],
                    "evidence_file": f"custody/evidence/{B4}/n6--N6-batch.redacted.json"})
    ci["controls"] = ctl
    ci["external"] = [{"requirement": "CL1-15", "subject": "E-GLM", "evidence_file": "harness-eval-glm-b4.log",
                       "readBy": "Chief of Staff (Orchestrator)"}]
    ci["retention"] = {"location": "github.com/smoitozo/plumbline (private), branch "
                                   "job/2026-10-27-custody-emitter-gaps, dot-plumbline/jobs/"
                                   "2026-10-27-custody-emitter-gaps. Full E-GLM logs and held-out controls stay "
                                   "on the Owner's box (/workspace/edi-batches, /workspace/next-job-controls); the "
                                   "repo has their sha256 only.", "public": False}
    ci["separationGaps"] = [
        GROKBOT_GAP,
        "The Maker's calls were issued by a harness operator, the E-DI Maker bot (a Grok Bot). The operator only "
        "issued the logged calls and applied returned patches verbatim (custody/method.md). This was instructed, "
        "not enforced.",
        P4_GAP,
        "Held-out control case files are digested from /workspace/next-job-controls, outside the repo. The record "
        "carries their sha256 only, so a stranger cannot re-read the cases.",
        "The E-GLM harness logs in the repo are redacted of held-out control text (handoffs/redact_glm_log.py). "
        "The full log's sha256 is in custody/evidence/harness-eval-glm-b4.log.full.sha256, and the full log stays "
        "outside the repo.",
        f"S1 is a script with no call log. Its pass and control time ({S1_AT}) was entered by hand from the "
        "modification time of the sealed batch-4 s1/summary.json.",
        "After the freeze, the generation, amendment, evaluation and dispose lines in "
        "inputs/custody-events.jsonl were appended by hand by the Orchestrator, not stamped by custody_ledger.py. "
        "The dispose line carries the Owner's decision time and channel as the Orchestrator received them.",
        "This record was emitted by base main @ ff350e3 (tree 4abcfa08), not by the artifact under test (bar: "
        "Emitter). Known limitation: that emitter has gap 1 (producedAt), which this job repairs.",
        "Only iteration 3's §5 record is emitted. Iterations 1 and 2 (fail → regenerate) are recorded in "
        "EVAL-ITER1-VERDICT.md, EVAL-ITER2-VERDICT.md and inputs/custody-events.jsonl.",
        "S1 check extra-1-job-rejected (N3) was scored on the repo fixture that the Maker edited in generation 5 "
        "(EVAL-ITER3-VERDICT.md, Notes).",
    ]
    (J / "inputs" / "custody.json").write_text(json.dumps(ci, indent=2, ensure_ascii=False) + "\n")

    # ---- the iteration-3 run file (the §5 ledger of what ran) ----
    bar_sha = h(J / "custody" / "bar.md")
    s1_code = h(J / "custody" / "freeze" / "instrument" / "run_instrument.sh")
    n6_rub = J / "custody" / "freeze" / "instrument" / "rubric-N6.md"
    n6_code = J / "custody" / "freeze" / "instrument" / "n6_batch.py"
    run = {
        "job_id": json.loads((J / "packet.json").read_text())["job_id"], "iteration": 3,
        "artifact": f"custody/subject-{SUBJECT_REV}.sha256", "ratified": True, "channel_blind": True,
        "evaluator_identity": "S1 script run_instrument.sh (N1-N5, N7, N8) + z-ai/glm-5.3-flash via openrouter.ai (N6)",
        "instrument": {"version": f"rubric custody/bar.md, runner {RUNNER}", "rubric_sha256": bar_sha,
                       "code_sha256": h(J / RUNNER)},
        "pass_rule": {"accept": 1, "dimension_floor": 1, "reject": 0, "cap": 3},
        "ground_truth": {"ref": "custody@3e3ca58", "version": "3e3ca58", "hardness": "INVARIANT"},
        "mandate_ref": {"doc": "EDI-MANDATE.md", "version": "a48a4645"},
        "dimensions": [], "violations": [], "verdict": "accept",
        "passes": [
            {"pass_id": "s1-b4", "kind": "scored", "status": "filed", "channel": "S1 script, batch 4",
             "run_ref": f"custody/evidence/{B4}/s1--summary.json", "code_sha256": s1_code,
             "scores": [{"dimension": d, "score": 1} for d in S1_DIMS]},
            {"pass_id": "glm-b4", "kind": "scored", "status": "filed", "channel": "openrouter.ai -> Z.AI",
             "provider": "Z.AI", "model": "z-ai/glm-5.3-flash", "family": "glm",
             "run_ref": f"custody/evidence/harness-eval-glm-b4.log#{calls['subject']['call']}",
             "rubric_sha256": h(n6_rub), "code_sha256": h(n6_code),
             "scores": [{"dimension": "N6", "score": 1}]},
        ],
    }
    for d in [f"N{i}" for i in range(1, 9)]:
        is6 = d == "N6"
        run["dimensions"].append({
            "name": d, "score": 1, "scale": "0-1", "anchor_note": "binary; threshold 1 (bar.md)",
            "observation": (f"N6 CONFORMS, controls_ok true (custody/evidence/{B4}/n6--N6-batch.redacted.json)"
                            if is6 else f"{d} PASS (custody/evidence/{B4}/s1--summary.json)"),
            "observation_channel": "E-GLM z-ai/glm-5.3-flash, call " + calls["subject"]["call"] if is6
            else "S1 run_instrument.sh, batch 4",
            "ground_truth_access": "blind_to_gt"})
    Path(a.run_out).write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote inputs/custody.json ({len(ctl)} controls), custody/subject-{SUBJECT_REV}.sha256, {a.run_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
