#!/usr/bin/env python3
"""Emit a §5 record — with its filed passes, its labelled extensions and its hashes — or emit nothing.

WHY THIS EXISTS. Four jobs were opened after a review told the deployment to produce machine-readable
records, and all four shipped hand-assembled ones that failed the checker: unlabelled extension keys, an
`instrument_in_force` without the runner hash, a `pass_rule` written as a sentence, a violation filed in a
class rule 4 does not have. Every one of those is a SHAPE failure, and a shape failure is what happens when a
person types a record a machine should print. This tool prints it.

WHAT IT DOES NOT DO. It does not decide anything and it invents nothing. Every value comes from the run file
(the Orchestrator's ledger of what actually ran) or from the job's own packet-level facts. It stamps the
artifact and pass hashes, which the corpus assigns to the Orchestrator, not to the Evaluator — so running this
is an ORCHESTRATOR act, and it is named as one.

IT REFUSES RATHER THAN WARNS. An illegal violation class, a blank required field, a pass with no run_ref, a
void pass that carries scores — each stops the write. Then it runs the corpus's own validator on its output: if
the record does not validate, the emitter reports the validator's verdict and exits non-zero. A record that the
law cannot read is not a record, whichever tool produced it.

THE CORPUS COMES FIRST. This command resolves the corpus through tools/edi_corpus.py BEFORE anything is
written (other commands resolve the corpus their own way; see kit/README.md): `--corpus PATH`, else
`$EDI_CORPUS` (unset or "" counts as not set),
else `plugins.edi-loop.corpus` in `$HERMES_HOME/config.yaml` (else `~/.hermes/config.yaml`), first rule set wins.
When one resolves, its `corpus source: <src>` line is printed. A Hermes config that cannot be read (PyYAML not
importable, bad YAML) is reported with its path and treated as no corpus. Exit codes:
  0  the record and its pass files were written and the corpus's validator accepted them
     (also `--print-only`, which writes nothing and needs no corpus)
  1  a refusal (the run cannot become a record), the validator rejected the record, or NO CORPUS resolved:
     with no corpus nothing is written, because a record that nothing has read is a claim, not a record
     (`PLUMBLINE_REQUIRE_CORPUS=1` with no corpus is this case too)
  2  usage: a --corpus, $EDI_CORPUS or Hermes value that is set but is not a corpus (named, never fallen
     through), a `PLUMBLINE_REQUIRE_CORPUS` value other than unset, "", "0" or "1" (named), or a bad --out-dir.
     Nothing is written.

    emit_record.py --run run.json --out-dir <job dir> [--corpus PATH] [--print-only]

run.json, one iteration — the ledger of what ran:

    { "job_id": "job-1", "iteration": 1, "artifact": "iteration-1-artifact.md",
      "ratified": true, "channel_blind": true, "evaluator_identity": "provider/model",
      "instrument": {"version": "...", "rubric_sha256": "...", "code_sha256": "..."},
      "pass_rule": {"accept": 9.5, "dimension_floor": 9.0, "reject": 7.0, "cap": 4},
      "ground_truth": {"ref": "...", "version": "...", "hardness": "DOCUMENT"},
      "mandate_ref": {"doc": "EDI-MANDATE.md", "version": "..."},
      "dimensions": [{"name": "...", "score": 9.9, "scale": "1-10", "anchor_note": "...",
                      "observation": "...", "observation_channel": "...",
                      "ground_truth_access": "blind_to_gt"}],
      "violations": [{"id": "V1", "class": "artifact_missed_standard", "observation": "..."}],
      "verdict": "accept",
      "passes": [{"pass_id": "...", "kind": "scored", "status": "filed", "channel": "...",
                  "provider": "...", "model": "...", "family": "...", "run_ref": "...",
                  "scores": [{"dimension": "D1", "score": 9.9}],
                  "evidence": [{"dimension": "D1", "quote": "verbatim from the artifact"}]}],
      "instance_extensions": [{"name": "artifact_sha256", "label": "instance-specific", "value": "..."}] }
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import edi_corpus  # noqa: E402  (tools/edi_corpus.py: the shared D-E resolver)

# The corpus must hold the validator this tool runs on its output (plus the resolver's own base need).
CORPUS_NEED = ("tools/validate_evaluator_record.py",)

# rule 4's four locators, verbatim. There is no severity scale and no fifth class: a violation filed
# outside these cannot be routed, counted or learned from, so the emitter refuses it.
VIOLATION_CLASSES = {"artifact_missed_standard", "standard_moved", "dimension_unauthorized", "frame_at_fault"}
PASS_KINDS = {"scored", "confirmation"}
PASS_STATUSES = {"filed", "void"}
VERDICTS = {"accept", "regenerate", "needs_owner", "reject"}
HARDNESS = {"INVARIANT", "DOCUMENT", "PRIOR"}
# The corpus's required check is PRESENCE, not non-blank (`if k not in rec`), and `_blank` treats {} and []
# as blank only where it applies — a pass with no scores, a dimension with no observation. Getting this wrong
# in the strict direction is the same defect as getting it wrong in the loose one: measured 2026-10-05, the
# first cut refused a CLEAN record because `violations: []` looked blank, and the corpus's own passing example
# carries exactly that. A tool that refuses legal input teaches people to work around it.
REQUIRED = ("job_id", "iteration", "artifact", "ratified", "channel_blind", "evaluator_identity",
            "instrument", "pass_rule", "ground_truth", "mandate_ref", "dimensions", "violations",
            "verdict", "passes")
# Only these must be non-blank as well as present: `0` and `False` are values, and an empty list is a fact.
MUST_BE_NON_BLANK = ("job_id", "artifact", "evaluator_identity", "verdict")


def blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or v in ({}, [])


def refusals(run: dict) -> list[str]:
    """Everything that stops the write, reported together so one run fixes them all."""
    out = []
    for k in REQUIRED:
        if k not in run:
            out.append(f"missing required run field: {k}")
        elif k in MUST_BE_NON_BLANK and blank(run.get(k)):
            out.append(f"required run field is blank: {k}")
    for k in ("rubric_sha256", "code_sha256"):
        if not (run.get("instrument") or {}).get(k):
            out.append(f"instrument.{k} is required — C30 requires the rubric AND the runner, and the "
                       f"Orchestrator stamps them, not the Evaluator")
    for k in ("accept", "dimension_floor", "reject", "cap"):
        if k not in (run.get("pass_rule") or {}):
            out.append(f"pass_rule.{k} is required")
    if run.get("verdict") and run["verdict"] not in VERDICTS:
        out.append(f"verdict {run['verdict']!r} is not one of {sorted(VERDICTS)} — the four values in §2/§3, "
                   f"never a synonym and never prose")
    if (run.get("ground_truth") or {}).get("hardness") not in HARDNESS:
        out.append(f"ground_truth.hardness must be one of {sorted(HARDNESS)}")
    for i, v in enumerate(run.get("violations") or []):
        if v.get("class") not in VIOLATION_CLASSES:
            out.append(f"violations[{i}].class {v.get('class')!r} is not one of rule 4's four locators "
                       f"{sorted(VIOLATION_CLASSES)} — a class the doctrine does not have cannot be routed")
    for i, d in enumerate(run.get("dimensions") or []):
        for k in ("name", "score", "observation", "observation_channel", "ground_truth_access"):
            if blank(d.get(k)):
                out.append(f"dimensions[{i}] ({d.get('name', '?')}) needs {k} — a dimension with no observation "
                           f"is a forced needs_owner, never a synthesised score")
        if d.get("ground_truth_access") == "saw_gt":
            out.append(f"dimensions[{i}] ({d.get('name', '?')}) saw ground truth: §7.2 fails that dimension")
    for i, p in enumerate(run.get("passes") or []):
        pid = p.get("pass_id", f"passes[{i}]")
        if p.get("kind") not in PASS_KINDS:
            out.append(f"pass {pid}: kind must be one of {sorted(PASS_KINDS)}")
        if p.get("status") not in PASS_STATUSES:
            out.append(f"pass {pid}: status must be one of {sorted(PASS_STATUSES)}")
        for k in ("channel", "run_ref"):
            if blank(p.get(k)):
                out.append(f"pass {pid}: {k} is required by the pass shape")
        if p.get("status") == "void" and not blank(p.get("scores")):
            out.append(f"pass {pid}: a void pass may not carry scores (§5) — file the cause, not a reading")
        if p.get("status") == "void" and blank(p.get("void_cause")):
            out.append(f"pass {pid}: a void pass requires void_cause")
        # §5's pass carries "one entry per dimension the pass observed", and the checker counts a dimension's
        # passes by reading filed["scores"] as a LIST of {dimension, score}. Measured 2026-10-05: a pass whose
        # scores were a dict keyed by dimension validated clean and was counted as observing NOTHING — the
        # record then reported every dimension as resting on 0 passes. Letting a shape nobody reads through is
        # this tool failing at its only job, so it is refused here.
        if p.get("status") == "filed" and p.get("kind") == "scored":
            scores = p.get("scores")
            if blank(scores):
                out.append(f"pass {pid}: a filed scored pass must carry the dimension(s) it observed — "
                           f"\"scores\" is the evidence that the pass happened")
            elif not isinstance(scores, list) or not all(
                    isinstance(s, dict) and not blank(s.get("dimension")) and isinstance(s.get("score"), (int, float))
                    for s in scores):
                out.append(f"pass {pid}: scores must be a LIST of {{dimension, score}} objects — the checker "
                           f"counts a dimension's passes by reading them, and a dict keyed by dimension is "
                           f"counted as observing nothing")
        if not blank(p.get("scores")) and not isinstance(p.get("scores"), list):
            out.append(f"pass {pid}: scores must be a list")
    # C35 (Contracts v1.21.0, proposal 0052 applied as amended) binds the two sides of the link the checker
    # has always counted by string equality. A record that passes must satisfy it, so the emitter refuses at
    # the point of writing rather than letting the validator reject its output.
    declared = [d.get("name") for d in (run.get("dimensions") or []) if not blank(d.get("name"))]
    observed: set[str] = set()
    for p in run.get("passes") or []:
        if p.get("status") != "filed":
            continue
        for s in (p.get("scores") or []) if isinstance(p.get("scores"), list) else []:
            if isinstance(s, dict) and not blank(s.get("dimension")):
                observed.add(str(s["dimension"]))
    # C36 (Contracts v1.22.0, proposal 0053 as amended): an iteration names what it sends back. A regenerate
    # with no violation is not an iteration, and a dimension below the floor carries a violation that names it.
    if run.get("verdict") == "regenerate" and not (run.get("violations") or []):
        out.append("verdict is `regenerate` with no violation — C36: an iteration that names nothing it is "
                   "tasked with is not an iteration. Name what the next iteration must change.")
    pr = run.get("pass_rule")
    if pr is not None and not isinstance(pr, dict):
        # Measured 2026-11-09: `round-01.json` in four filed jobs carries `pass_rule: "accepted"` — the older
        # run shape. `.get` on a string raised AttributeError, so a close died with a traceback where a named
        # refusal belonged, and the failure looked like a Plumbline crash rather than a run the emitter cannot
        # read. Refuse by name and keep reading the rest of the run.
        out.append(f"run.pass_rule is {type(pr).__name__} ({pr!r}); the §5 run shape is an object carrying "
                   f"`dimension_floor` and the thresholds. A bare value is an older run shape, and it cannot be "
                   f"read as a pass rule — re-emit the run from the loop that produced it, or supply the floor.")
        floor = None
    else:
        floor = (pr or {}).get("dimension_floor")
    named = {str(v.get("dimension")) for v in (run.get("violations") or []) if isinstance(v, dict)
             and not blank(v.get("dimension"))}
    if isinstance(floor, (int, float)):
        for d in run.get("dimensions") or []:
            nm, sc = d.get("name"), d.get("score")
            if isinstance(sc, (int, float)) and sc < floor and str(nm) not in named:
                out.append(f"dimension {nm!r} scores {sc} against a floor of {floor} with no violation naming "
                           f"it — C36: the shortfall must be classified into one of rule 4's four locators "
                           f"and its violation must carry `dimension: {nm!r}`. §4 says the deficiency is the "
                           f"loop's; the record reports it rather than reading a defect into the reading.")
    for v in (run.get("violations") or []):
        if isinstance(v, dict) and not blank(v.get("dimension")) and str(v["dimension"]) not in declared:
            out.append(f"a violation names dimension {v['dimension']!r}, which the record does not declare — "
                       f"the same link C35 binds, applied to the violation's own field")

    for pid in sorted(observed - set(declared)):
        out.append(f"a filed pass scores {pid!r}, which the record does not declare — C35: evidence not "
                   f"attributable. Name it exactly as the instrument names it, or do not score it.")
    for name in declared:
        if name not in observed:
            out.append(f"dimension {name!r} is declared but no filed pass observed it — C35: a dimension "
                       f"resting on zero passes fails, because zero is not one (rule 10 labels one, not none)")
    return out


def pass_file(p: dict) -> dict:
    """The filed pass, shape-for-shape with schemas/pass.schema.json. Nothing outside its properties."""
    filed = {"pass_id": p["pass_id"], "kind": p["kind"], "status": p["status"], "channel": p["channel"],
             "rubric_sha256": p.get("rubric_sha256"), "code_sha256": p.get("code_sha256"),
             "run_ref": p["run_ref"]}
    for k in ("provider", "model", "family", "void_cause", "scores", "instance_extensions"):
        if not blank(p.get(k)):
            filed[k] = p[k]
    return filed


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit a §5 record with its filed passes, or emit nothing.")
    ap.add_argument("--run", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--corpus", help="corpus checkout; wins over $EDI_CORPUS and the Hermes config")
    ap.add_argument("--print-only", action="store_true",
                    help="report what would be written; write nothing (no corpus needed)")
    a = ap.parse_args()

    # Resolve the corpus before anything else: a bad setting is a usage error (exit 2, named) even when the
    # run is fine, and no file is written until a corpus is there to validate it (option A).
    corpus, _required = edi_corpus.resolve_or_exit(a.corpus, CORPUS_NEED)

    run = json.loads(Path(a.run).read_text())
    out = Path(a.out_dir).expanduser()
    if not out.is_dir():
        print(f"REFUSED: --out-dir is not a job directory: {out}"); return 2

    stops = refusals(run)
    if stops:
        print(f"REFUSED — {len(stops)} reason(s) the run cannot become a record:")
        for s in stops:
            print(f"  - {s}")
        print("\nnothing written. A record that fails the law is worse than no record, because it looks like one.")
        return 1

    inst = run["instrument"]
    for p in run["passes"]:                        # the Orchestrator stamps C30's hashes onto every pass
        p.setdefault("rubric_sha256", inst["rubric_sha256"])
        p.setdefault("code_sha256", inst["code_sha256"])

    artifact = out / run["artifact"]
    if not artifact.is_file():
        print(f"REFUSED: the artifact the run names is not beside the record: {artifact}"); return 1

    passes_dir = out / "passes"
    names = [{**{k: p[k] for k in ("pass_id", "kind", "status")}, "artifact": f"passes/{p['pass_id']}.json"}
             for p in run["passes"]]
    record = {
        "job_id": run["job_id"], "iteration": run["iteration"], "passes": names,
        "dimensions": run["dimensions"], "pass_rule": run["pass_rule"], "violations": run["violations"],
        "verdict": run["verdict"], "ground_truth_ref": run["ground_truth"]["ref"],
        "ground_truth_version": run["ground_truth"]["version"],
        "ground_truth_hardness": run["ground_truth"]["hardness"], "mandate_ref": run["mandate_ref"],
        "instrument_in_force": inst, "evaluator_identity": run["evaluator_identity"],
        "channel_blind": run["channel_blind"], "ratified": run["ratified"],
        "instance_extensions": [
            {"name": "artifact_ref", "label": "instance-specific",
             "value": f"{run['artifact']} sha256 {sha256(artifact.read_bytes()).hexdigest()}"},
            *run.get("instance_extensions", []),
        ],
    }
    for ext in record["instance_extensions"]:
        if ext.get("label") != "instance-specific":
            print(f"REFUSED: extension {ext.get('name')!r} is not labelled instance-specific (C18)"); return 1

    rec_path = out / f"iteration-{run['iteration']}-eval-record.json"
    if a.print_only:
        print(f"would write {rec_path.name} and {len(names)} pass file(s) under {passes_dir}")
        print(json.dumps(record, indent=2)[:600])
        return 0

    if corpus is None:
        # PLUMBLINE_REQUIRE_CORPUS=1 changes nothing here: with no corpus this tool already writes nothing.
        print(f"  NOTE: {edi_corpus.NO_CORPUS}.")
        print("  Nothing was written: an emitted record that nothing has read is a claim, not a record.")
        return 1

    passes_dir.mkdir(exist_ok=True)
    for p, n in zip(run["passes"], names):
        (passes_dir / f"{p['pass_id']}.json").write_text(json.dumps(pass_file(p), indent=2) + "\n")
    rec_path.write_text(json.dumps(record, indent=2) + "\n")
    print(f"wrote {rec_path.name} + {len(names)} pass file(s) in {passes_dir.name}/")

    checker = corpus.path / "tools" / "validate_evaluator_record.py"
    r = subprocess.run([sys.executable, str(checker), str(rec_path)], capture_output=True, text=True)
    verdict = (r.stdout + r.stderr).strip()
    print("  " + verdict.replace("\n", "\n  "))
    if r.returncode != 0:
        print("  the corpus rejected the emitted record: fix the run, not the checker.")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
