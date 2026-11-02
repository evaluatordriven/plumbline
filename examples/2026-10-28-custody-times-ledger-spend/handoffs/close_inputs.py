#!/usr/bin/env python3
"""Build the close inputs for job 2026-10-28-custody-times-ledger-spend. Run by CLOSE-apply.sh; it decides nothing.

    close_inputs.py --job-dir J --run-dir DIR --controls-dir DIR

Writes:
  J/inputs/custody.json   the existing ledger mirror (bar, approvals, orchestrator, routing) is kept as is, and
                          levelClaimed, subject, bar author/dimensions, maker (with the call filter), instrument,
                          evaluators, passes (iteration 3 only), controls (batch 3: 57 S1 + 11 E-GLM), external,
                          retention and separationGaps are added. Disposition is left to CLOSE-apply.sh.
  J/custody/subject-<rev>.sha256 for 1cb410b, c882646, f95e0d3: the files changed from base 3df1ce5, by digest
  DIR/run-1.json, run-2.json, run-3.json  the §5 run files (OUTSIDE J/inputs; plumbline_job.py close copies them in)

Adapted from 2026-10-28-doctrine-reader-pointer/handoffs/close_inputs.py. Every value comes from a file in J (bar.md,
the evidence imported by handoffs/close/import_close.py, packet.json, the existing inputs) or from git. The only
absolute paths are the held-out control case files (--controls-dir), digested, never copied (bar P4), and the
public frozen instrument (scheck.py) named as the case file of the mutation controls.
"""
from __future__ import annotations
import argparse, json, re, subprocess
from hashlib import sha256
from pathlib import Path

ORCH = "Chief of Staff (Orchestrator)"
BASE = "3df1ce52eddfe18705e380c4b6e99cf617cfa24b"
REVS = {1: "1cb410b", 2: "c882646", 3: "f95e0d3"}
S1_DIMS_ALL = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "F1a", "F1b", "F1c", "F1d", "F1e", "F1f", "F1g", "F1h", "I1",
               "F7a", "F8a", "F8b", "F8c", "F8d", "P1", "X1", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9",
               "G1", "G2", "G3", "G4", "G5", "G6", "G7"]
JS = ["J1", "J2", "J3", "J4"]
ALL = S1_DIMS_ALL + JS
GROKBOT_GAP = ("Grokbot's underlying model(s) are not disclosed by its operator; family and identifier "
               "recorded as undisclosed.")
P4_GAP = ("Controls and fixtures were held outside the Maker's and Evaluator's working trees with sha256 "
          "committed at freeze, but on a shared box both bots could technically read them; non-reading was "
          "instructed, not enforced.")
MAKER_CALLS_EXCLUDED = ["maker_iter1_ledger_a1", "maker_iter1_docs_a1", "maker_iter3_fix_a1", "maker_iter3_fix_a2"]


def h(p: Path) -> str:
    return sha256(p.read_bytes()).hexdigest()


def git(repo: Path, *a: str, b: bool = False):
    out = subprocess.check_output(["git", "-C", str(repo), *a])
    return out if b else out.decode()


def bar_dims(bar: Path) -> list[dict]:
    out = []
    for line in bar.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| ([A-Z]\d+[a-z]?) \| (.+) \| ([^|]+?) \| ([^|]+?) \|$", line)
        if m:
            out.append({"id": m[1], "plumbline_dimension": m[1], "criterion": m[2].strip(),
                        "scale": {"anchors": {"0": "the check does not PASS as stated (includes NOT-RUN)",
                                              "1": "the check PASSES as stated"},
                                  "threshold": 1, "floor": 0},
                        "failureCondition": f"{m[1]} does not PASS as the criterion states, or is not run "
                                            f"(bar.md: binary scale, threshold 1)"})
    ids = [d["id"] for d in out]
    if ids != ALL:
        raise SystemExit(f"bar.md dimension rows parsed as {ids}, expected the 43 checks T1..J4")
    return out


def s1_case(cid: str, CD: Path, scheck: Path) -> tuple[str, str]:
    """(dimension, case file) for an S1 control id."""
    m = re.fullmatch(r"OBS-([A-Z]\d+[a-z]?)\.(clean|planted)", cid)
    if m:
        return m[1], str(CD / "obs" / f"{m[1]}.{m[2]}.json")
    m = re.fullmatch(r"C-([A-Z]\d+[a-z]?)(c|p\d?)", cid)
    assert m, cid
    d, k = m[1], m[2]
    table = {"T5c": CD / "expect.json", "T5p1": scheck, "T5p2": scheck, "T7p": CD / "wrappers" / "C-T7p.py.txt",
             "V7c": CD / "wrappers" / "C-V7s.py.txt", "V7p": CD / "wrappers" / "C-V7p.py.txt", "G1p": scheck,
             "G4p": CD / "fg" / "clean.md", "G5p": CD / "fg" / "p-G5.md", "G6p": CD / "fg" / "p-G6.md",
             "G7p": CD / "fg" / "p-G7.md"}
    p = table.get(d + k) or (CD / "fg" / "clean.md" if k == "c" and d in ("G4", "G5", "G6", "G7") else None)
    assert p is not None and Path(p).is_file(), (cid, p)
    return d, str(p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--controls-dir", required=True)
    a = ap.parse_args()
    J = Path(a.job_dir).resolve(); CD = Path(a.controls_dir).resolve(); RD = Path(a.run_dir).resolve()
    repo = Path(git(J, "rev-parse", "--show-toplevel").strip())
    ev = J / "custody" / "evidence"
    ins = J / "custody" / "freeze" / "instrument"
    scheck = ins / "scheck.py"
    pk = json.loads((J / "packet.json").read_text())

    # -- artifacts --
    subject = git(repo, "diff", "--name-only", BASE, REVS[3]).split()
    for it, rev in REVS.items():
        names = git(repo, "diff", "--name-only", BASE, rev).split()
        lines = [f"{sha256(git(repo, 'show', f'{rev}:{n}', b=True)).hexdigest()}  {n}" for n in names]
        (J / "custody" / f"subject-{rev}.sha256").write_text(
            f"# artifact under evaluation, iteration {it}: maker/custody-times-ledger-spend/iter{it} @ {rev} "
            f"(files changed from base 3df1ce5)\n" + "\n".join(lines) + "\n")

    # -- evidence --
    s1 = {b: json.loads((ev / f"b{b}" / "s1-summary.json").read_text()) for b in (1, 2, 3)}
    gb = {b: {j: json.loads((ev / f"b{b}" / "glm" / f"{j}-batch.json").read_text()) for j in JS} for b in (1, 2, 3)}
    t6a = json.loads((ev / "T6-amend2.json").read_text())
    assert s1[3]["passed"] == 38 and [k for k, v in s1[3]["results"].items() if v != "PASS"] == ["T6"], s1[3]["results"]
    assert t6a["check"] == "T6" and t6a["amendment"] == 2 and t6a["score"] == 1, t6a
    for b in (1, 2, 3):
        for j in JS:
            assert gb[b][j]["controls_ok"] is True and gb[b][j]["dry_run"] is False, (b, j)
    assert all(gb[3][j][j] == "PASS" for j in JS)
    S1_AT = s1[3]["finished_at"][:19] + "Z"
    subj_call = {b: {j: next(i["call"] for i in gb[b][j]["items"] if i["id"] == "subject") for j in JS} for b in (1, 2, 3)}
    side_sha = h(J / "custody" / "x-plumbline.json")
    disc_sha = h(J / "custody" / "DISCLOSURES.md")
    sp = json.loads((J / "custody" / "x-plumbline.json").read_text())["spend"]
    assert sp["reconciled"] is True and (J / "custody" / "evidence" / "spend-status-close.json").is_file(), "no close spend read"

    # -- custody inputs --
    ci = json.loads((J / "inputs" / "custody.json").read_text())
    ci["levelClaimed"] = "CL1"
    ci["files_dir"] = "../../.."
    ci["subject"] = subject
    ci["bar"] = {**ci["bar"], "author": "Steve Moitozo II", "dimensions": bar_dims(J / ci["bar"]["file"])}
    maker_log = json.loads((ev / "harness-maker-deepseek.log").read_text())
    calls = [e["call"] for e in maker_log if e["call"] not in MAKER_CALLS_EXCLUDED]
    assert all(e.get("generation_status") == 200 for e in maker_log if e["call"] in calls)
    assert all(e.get("generation_status") == 404 for e in maker_log if e["call"] in MAKER_CALLS_EXCLUDED)
    ci["maker"] = {"name": pk["maker"]["name"], "kind": "model", "version": "v4.1-flash-1017",
                   "method_file": "custody/method.md", "harness_log": "harness-maker-deepseek.log", "calls": calls,
                   "model": {"family": "deepseek", "identifier": "deepseek/deepseek-v4.1-flash-1017", "readOnly": False}}
    ci["instrument"] = {"rubric_file": "custody/bar.md", "runner_file": "handoffs/iter3/EVALUATOR.md"}
    ci["evaluators"] = [
        {"id": "S1", "name": "S1 instrument script (T1-T7, F1a-F1h, I1, F7a, F8a-F8d, P1, X1, V1-V9, G1-G7)",
         "kind": "script", "script": {"name": "run_instrument.sh", "author": "Chief of Staff (Orchestrator) drafter",
                                      "file": "custody/freeze/instrument/run_instrument.sh"}},
        {"id": "E-GLM", "name": "GLM 5.3 Flash (J1-J4)", "kind": "model", "harness_log": "harness-eval-glm-b3.log",
         "model": {"family": "glm", "identifier": "z-ai/glm-5.3-flash", "readOnly": True}},
    ]
    s1d3 = [d for d in S1_DIMS_ALL if d != "T6"]
    ci["passes"] = {
        "s1-b3": {"evaluator": "S1", "run": 3, "batch": "b3", "at": S1_AT, "dimensions": s1d3,
                  "evidence": {d: f"{d}.json" for d in s1d3}},
        "s1-b3-t6-amend2": {"evaluator": "S1", "run": 3, "batch": "b3", "at": S1_AT, "dimensions": ["T6"],
                            "evidence": {"T6": "T6-amend2.json"}},
        **{f"glm-b3-{j}": {"evaluator": "E-GLM", "run": 3, "batch": "b3", "call": subj_call[3][j], "dimensions": [j],
                           "evidence": {j: f"{j}-{subj_call[3][j]}.json"}} for j in JS},
    }
    ctl = []
    for cid, c in sorted(s1[3]["controls"].items()):
        d, case = s1_case(cid, CD, scheck)
        exp = "conforms" if c["want"] == "PASS" else "does_not_conform"
        outc = "conforms" if c["got"] == "PASS" else "does_not_conform"
        assert c["right"] is True and exp == outc, (cid, c)
        ctl.append({"id": cid, "batch": "b3", "evaluator": "S1", "case_file": case, "expected": exp, "outcome": outc,
                    "dimension": d, "evidence_file": "custody/evidence/b3/s1-summary.json", "at": S1_AT})
    for j in JS:
        for it in gb[3][j]["items"]:
            if it["id"] == "subject":
                continue
            exp = "conforms" if re.fullmatch(r"G-J\dc", it["id"]) else "does_not_conform"
            got = "conforms" if it["verdict"] == "CONFORMS" else "does_not_conform"
            assert it.get("control_ok") is True and got == exp, it
            ctl.append({"id": it["id"], "batch": "b3", "evaluator": "E-GLM",
                        "case_file": str(CD / "glm" / j / it["id"] / "listing.txt"), "expected": exp, "outcome": got,
                        "dimension": j, "call": it["call"], "evidence_file": f"custody/evidence/b3/glm/{j}-batch.json"})
    assert len(ctl) == 68, len(ctl)
    ci["controls"] = ctl
    ci["external"] = [{"requirement": "CL1-15", "subject": "E-GLM", "evidence_file": "harness-eval-glm-b3.log",
                       "readBy": ORCH}]
    ci["retention"] = {"location": "github.com/smoitozo/plumbline (private), branch "
                                   "job/2026-10-28-custody-times-ledger-spend, dot-plumbline/jobs/"
                                   "2026-10-28-custody-times-ledger-spend. The full E-GLM logs, the full S1 summaries, "
                                   "the Orchestrator's deviation log and the held-out controls stay on the Owner's box "
                                   "(/workspace/edi-work/2026-10-28-custody-times-ledger-spend, /workspace/job-controls/"
                                   "2026-10-28-custody-times-ledger-spend); the repo has their sha256 only "
                                   "(custody/evidence/HELD-ON-BOX.sha256, custody/evidence/harness-eval-glm-b*.log.full.sha256).",
                       "public": False}
    ci["separationGaps"] = [
        GROKBOT_GAP,
        "Every Maker call was issued by a harness operator, the E-DI Maker bot (a Grok Bot), which issued the logged "
        "calls through the frozen harness, extracted the returned files verbatim and committed them (custody/method.md). "
        "This was instructed, not enforced.",
        P4_GAP,
        "Held-out control case files are digested from /workspace/job-controls/2026-10-28-custody-times-ledger-spend, "
        "outside the repo. The record carries their sha256 only, so a stranger cannot re-read the cases. The mutation "
        "controls C-T5p1, C-T5p2 and C-G1p have no case file of their own (scheck.py applies the mutation); their "
        "case_file is the frozen public instrument custody/freeze/instrument/scheck.py.",
        "E-GLM ran as four checks (J1-J4) with one harness log each. The base emitter reads one log per evaluator, so "
        "the record's E-GLM log (custody/evidence/harness-eval-glm-b3.log) is the four batch-3 logs merged in sent_at "
        "order and redacted of held-out control text (handoffs/close/redact_glm_log.py); the full logs' sha256 are in "
        "custody/evidence/harness-eval-glm-b3.log.full.sha256 and the full logs stay on the box. Batches 1 and 2 are "
        "filed the same way (harness-eval-glm-b1.log, -b2.log) as evidence for runs 1 and 2.",
        "Controls in the record are batch 3's only (57 S1 + 11 E-GLM, all right). Batches 1 and 2 ran their own "
        "controls, all right (custody/evidence/b1/, b2/ summaries and batch files).",
        f"S1 is a script with no call log. Its pass and control time ({S1_AT}) is the batch-3 S1 run's own "
        "finished_at stamp (scheck.py@49d3a506f6f7). T6 is scored under Amendment 2 (AMENDMENT-2-t6-n1-refusal.md, "
        "ledger line 8) from that same run's output (custody/evidence/T6-amend2.json; frozen T6 verdict FAIL), so "
        "pass s1-b3-t6-amend2 carries the same time. The pass on all 43 checks rests on Amendment 2 (disclosure 20).",
        "S1's batch-3 per-check evidence files that echoed held-out fixture values (F1a-F1h, F8a-F8d, I1, T2, T3, T6, "
        "T6-amend2, T7, V1-V4, V6) are filed redacted (handoffs/close/redact_s1_evidence.py: each such JSON value is "
        "replaced by a fixed marker; ids, verdicts and reasons are kept). The full files stay on the Owner's box; their "
        "sha256 are in custody/evidence/HELD-ON-BOX.sha256, so a stranger can check the verdicts but not re-read the "
        "fixture values.",
        "The leak scan allows one reviewed hit (handoffs/close/leak-allow.json, by line sha256): a bare function "
        "signature that the Maker wrote in its own reasoning in call maker_iter1_edi_a1 equals one line of a held-out "
        "reference copy by naming coincidence. The Maker log's digest is pinned (882ee4e6...), so it is filed unredacted.",
        "The record's Maker call list (maker.calls) leaves out maker_iter1_ledger_a1, maker_iter1_docs_a1, "
        "maker_iter3_fix_a1 and maker_iter3_fix_a2, whose /api/v1/generation fetch returned 404 (the base emitter "
        "refuses a call with no generation endpoint), and the guide calls, which are in separate logs "
        "(harness-maker-deepseek-guide-iter1.log, -iter2.log) because the base emitter reads one Maker log. All of them "
        "are in the evidence folder; startedAt is therefore maker_iter1_emitter_a1's sent_at, not the first call's.",
        "After the approvals and amendments, the generation, evaluation, relay, spend and dispose lines in "
        "inputs/custody-events.jsonl were appended by hand by the Orchestrator at the close, not stamped by "
        "custody_ledger.py (which at 3df1ce5 has no command for them). They were recorded late: each carries "
        "writer \"hand\", recorded_late true, recorded_at and at_source (disclosure 23). The dispose line carries the "
        "Owner's decision time and channel as the Orchestrator received them.",
        "Steve's run go-aheads for iteration 3 (09:55 EDT, card t21s1; 11:08 EDT, card t23s1) were given in the E-DI "
        "Maker's own chat and the batch-2 go-ahead (08:25 EDT, card t11s2) in the E-DI Evaluator's own chat; the "
        "Orchestrator checked them in those transcripts (ledger \"relay\": true). No source was found for the "
        "iteration-1 Maker and Evaluator go-aheads, the guide-a2 go-ahead or the batch-3 go-ahead; they are not in the "
        "ledger.",
        f"Spend (bar P6) is reconciled against a key-usage read at the close (custody/evidence/spend-status-close.json): "
        f"settles US${sp['settled_usd']}, key delta US${sp['key_delta_usd']}; the gap "
        f"{sp['reconciliation']['key_minus_settled_usd']} is the one reserve with no settle (iteration-1 verifier a1, "
        f"ruled LOST), kept open at worst case on the Owner's decision; job total US${sp['total_usd']}. Seven settles use "
        f"response.usage.cost because the generation fetch failed. The Owner's dashboard figure "
        f"(US${sp['reconciliation']['owner_dashboard']['today_usd']}) is not reconciled: disclosure 24.",
        "This record was emitted by base main @ 3df1ce5 (tree 230997f1), not by the branch under test (bar: base "
        "tooling only). That emitter cannot pass x-plumbline fields through, so spend, hand times, relays and the "
        f"post-merge verifier note are in the sidecar custody/x-plumbline.json, sha256 {side_sha}.",
        "Close disclosures 1-24 (1-23 accepted by the Owner 2026-10-29 13:15 EDT; first accepted 12:36 EDT (\"Accept the result with disclosures "
        f"1–22.\"; item 23 added on his instruction); item 24 added at the close): custody/DISCLOSURES.md, sha256 {disc_sha}.",
    ]
    (J / "inputs" / "custody.json").write_text(json.dumps(ci, indent=2, ensure_ascii=False) + "\n")

    # -- run files --
    bar_sha = h(J / "custody" / "bar.md")
    gt = pk["ground_truth"][0]
    RD.mkdir(parents=True, exist_ok=True)
    pids_out = []
    for it in (1, 2, 3):
        s = s1[it]
        sc = {d: (1 if s["results"][d] == "PASS" else 0) for d in S1_DIMS_ALL}
        jsc = {j: (1 if gb[it][j][j] == "PASS" else 0) for j in JS}
        passes = [{"pass_id": f"s1-b{it}", "kind": "scored", "status": "filed", "channel": f"S1 script, batch {it}",
                   "run_ref": f"custody/evidence/b{it}/s1-summary.json", "code_sha256": h(ins / "run_instrument.sh"),
                   "scores": [{"dimension": d, "score": sc[d]} for d in S1_DIMS_ALL if not (it == 3 and d == "T6")]}]
        if it == 3:
            sc["T6"] = 1
            passes.append({"pass_id": "s1-b3-t6-amend2", "kind": "scored", "status": "filed",
                           "channel": "S1 script, batch 3, T6 scored under Amendment 2",
                           "run_ref": "custody/evidence/T6-amend2.json", "code_sha256": h(ins / "run_instrument.sh"),
                           "scores": [{"dimension": "T6", "score": 1}]})
        for j in JS:
            c = subj_call[it][j]
            passes.append({"pass_id": f"glm-b{it}-{j}", "kind": "scored", "status": "filed",
                           "channel": "openrouter.ai -> Z.AI", "provider": "Z.AI", "model": "z-ai/glm-5.3-flash",
                           "family": "glm", "run_ref": f"custody/evidence/harness-eval-glm-b{it}.log#{c}",
                           "rubric_sha256": h(ins / f"rubric-{j}.md"), "code_sha256": h(ins / "jbatch.py"),
                           "scores": [{"dimension": j, "score": jsc[j]}]})
        score = {**sc, **jsc}
        viol = [{"id": f"I{it}-{d}", "class": "artifact_missed_standard", "dimension": d,
                 "observation": (f"{d} FAIL on {REVS[it]}, batch {it} (custody/evidence/b{it}/s1-summary.json)"
                                 if d in sc else
                                 f"{d} DOES_NOT_CONFORM on {REVS[it]}, batch {it} "
                                 f"(custody/evidence/b{it}/glm/{d}-batch.json)")}
                for d in ALL if score[d] == 0]
        verdict = "accept" if not viol else "regenerate"
        assert (it == 3) == (verdict == "accept"), (it, viol)
        run = {
            "job_id": pk["job_id"], "iteration": it, "artifact": f"custody/subject-{REVS[it]}.sha256",
            "ratified": True, "channel_blind": True,
            "evaluator_identity": "S1 script run_instrument.sh (39 checks) + z-ai/glm-5.3-flash via openrouter.ai (J1-J4)",
            "instrument": {"version": f"rubric custody/bar.md, runner handoffs/iter{it}/EVALUATOR.md",
                           "rubric_sha256": bar_sha, "code_sha256": h(J / "handoffs" / f"iter{it}" / "EVALUATOR.md")},
            "pass_rule": {"accept": 1, "dimension_floor": 1, "reject": 0, "cap": 3},
            "ground_truth": {"ref": gt["ref"], "version": gt["version"], "hardness": gt["hardness"]},
            "mandate_ref": pk["mandate_ref"],
            "dimensions": [], "violations": viol, "verdict": verdict, "passes": passes,
        }
        for d in ALL:
            isj = d in JS
            note = " (Amendment 2; frozen T6 FAIL)" if it == 3 and d == "T6" else ""
            run["dimensions"].append({
                "name": d, "score": score[d], "scale": "0-1", "anchor_note": "binary; threshold 1 (bar.md)",
                "observation": (f"{d} {gb[it][d][d]}, controls_ok true (custody/evidence/b{it}/glm/{d}-batch.json)" if isj
                                else f"{d} {'PASS' if score[d] else 'FAIL'}{note} (custody/evidence/b{it}/s1-summary.json)"),
                "observation_channel": (f"E-GLM z-ai/glm-5.3-flash, call {subj_call[it][d]}" if isj
                                        else f"S1 run_instrument.sh, batch {it}"),
                "ground_truth_access": "blind_to_gt"})
        (RD / f"run-{it}.json").write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n")
        pids_out.append(f"run-{it}: {verdict}, {len(viol)} violations, {len(passes)} passes")
    print(f"wrote inputs/custody.json ({len(ctl)} controls), 3 subject digests; " + "; ".join(pids_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
