#!/usr/bin/env python3
"""Plumbline behaviour suite.

Two jobs, and they are different jobs:

  PART 1 — DOCTRINE. Each case is a rule from the seven weight-bearing files, with a
  packet or record that must pass and one that must fail. A case that cannot fail is not
  a check (Instrument rule 3: a check that cannot fail certifies nothing).

  PART 2 — ALIGNMENT (the reason this suite exists in this form). Plumbline's schemas are
  DERIVED from the corpus. The invariant that makes that real is one-directional:

      every packet Plumbline accepts, the corpus must accept too.

  Plumbline is an instance (Contracts §8): it may constrain itself MORE, never less. If its
  schema ever accepts something the corpus rejects, Plumbline has quietly become its own law.
  So the corpus's own fixture battery is run through both validators and the direction is
  asserted, not assumed.

  PART 3 — CUSTODY. custody/v1 records (kit/emit_custody.py) are checked against a schema
  DERIVED from the pinned evaluatordriven/custody schema. These cases make the custody drift
  check able to fail (a moved custody, a hand-edited derived schema) and pin the emitter's
  refusals. They need no corpus: set CUSTODY_DIR to a custody checkout to test a real move.

  The fixture battery and its direction invariant run on the VENDORED copy of the corpus's schemas and
  fixtures (schemas/vendor/e-di@<pin8>/), so they run everywhere. Two checks need the corpus itself and are
  reported by id (tools/edi_corpus.py line forms): corpus.pin-on-disk (the pin still matches the corpus on
  disk) and corpus.battery-equality (the vendored copy is still the corpus's bytes). With no corpus each
  prints a SKIP[corpus] line; with PLUMBLINE_REQUIRE_CORPUS=1 each is a FAIL[corpus] line and exit 1.

Run:  python3 tests/validate_schemas.py   (set EDI_CORPUS to a corpus checkout for the corpus.* checks)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    sys.exit("jsonschema is required: pip install -r requirements.txt")

REPO = Path(__file__).resolve().parent.parent
SHIP = REPO / "schemas"
PIN = json.loads((REPO / "tools" / "pin.json").read_text(encoding="utf-8"))
# The corpus checkout is resolved at run time ($EDI_CORPUS, through the shared D-E resolver); pin.json names the
# repository, not a path. A set EDI_CORPUS that is not a corpus exits 2 naming it; it never falls back to the vendored copy.
sys.path.insert(0, str(REPO / "tools"))
import edi_corpus  # noqa: E402

_resolved, REQUIRE_CORPUS = edi_corpus.resolve_or_exit(
    None, ("schemas/job-packet.schema.json", "schemas/evaluator-record.schema.json"), hermes=False)
CORPUS = _resolved.path if _resolved else None
VENDOR = SHIP / "vendor" / f"e-di@{PIN['commit'][:8]}"
VENV_PY = sys.executable

PACKET = json.loads((SHIP / "job-packet.schema.json").read_text(encoding="utf-8"))
RECORD = json.loads((SHIP / "evaluator-record.schema.json").read_text(encoding="utf-8"))
AUDIT = json.loads((SHIP / "audit-record.schema.json").read_text(encoding="utf-8"))
CHECKLIST = json.loads((SHIP / "compliance-checklist.json").read_text(encoding="utf-8"))

V_PACKET = Draft202012Validator(PACKET)
V_RECORD = Draft202012Validator(RECORD)
V_AUDIT = Draft202012Validator(AUDIT)

results: list[tuple[str, bool, str]] = []


def check(section: str, name: str, valid: bool, obj: dict, validator: Draft202012Validator) -> None:
    """A case declares the outcome it must produce. Both directions are recorded."""
    errs = sorted(validator.iter_errors(obj), key=lambda e: list(e.path))
    got = not errs
    ok = got == valid
    why = "" if ok else ("expected INVALID, schema accepted" if not valid else f"expected VALID, schema rejected: {errs[0].message[:70]}")
    results.append((f"{section} · {name}", ok, why))


# ---------------------------------------------------------------- fixtures

def packet(**over) -> dict:
    """A minimal well-formed scored packet. Doctrine-legal, instance-complete."""
    base = {
        "entry": "A",
        "instrument_profile": "full",
        "job_name": "plumbline test job",
        "artifact": "artifact/iter-0",
        "buyer": "Owner",
        "specialist": "vendor docs",
        "maker": {
            "engine": "deepseek/deepseek-v4-flash",
            "version": "2026-09",
            "feedback_forms": ["structured violations", "diff"],
            "task_classes": [{"class": "generation", "shown_by": "run 2026-09-29-a"}],
        },
        "evaluator": "z-ai/glm-5.3-flash",
        "ground_truth": [{"source": "vendor docs", "version": "pinned-1", "hardness": "DOCUMENT", "channel": "back-translation"}],
        "mandate_ref": {"doc": "EDI-MANDATE.md", "version": "short-2026-09-24"},
        "standard_ref": "rubric v1",
        "bounds": {"T_accept": 8.5, "T_dim": 7.0, "T_reject": 6.0, "cap": 3,
                   "budget": {"amount": 2, "unit": "USD"}, "cap_counts": "generations"},
        "human_seat": "Owner via Telegram topic",
        "escalation": "values and doctrine to Owner",
        "mode": "scored",
        "ratified": True,
        "stage": "development",
        "constitution_ref": "plumbline constitution",
        "constitution_version": "1.0",
    }
    base.update(over)
    return base


def record(**over) -> dict:
    base = {
        "job_id": "job-1",
        "iteration": 0,
        # v1.20.0 (§5, proposal 0050 as amended): a record NAMES the passes that produced it, and each named
        # pass is filed beside it. The `artifact` here names the pass but does not materialise it, because this
        # battery checks schemas and not files: the filing rule is asserted by the kit's cases, which run the
        # corpus's own record-and-pass fixtures. A file-level check belongs to the corpus's validator, not here.
        "passes": [{
            "pass_id": "fixture-pass-A", "kind": "scored", "status": "filed",
            "artifact": "pass-fixture-pass-A.json",
        }],
        "dimensions": [{
            "name": "accuracy", "score": 9, "scale": "1-10", "anchor_note": "meets",
            "observation": "back-translation matched the pinned reference on 40/40 clauses",
            "observation_channel": "back-translation", "ground_truth_access": "blind_to_gt",
        }],
        "pass_rule": {"accept": 8.5, "dimension_floor": 7.0, "reject": 6.0, "cap": 3},
        "violations": [],
        "verdict": "accept",
        "ground_truth_ref": "vendor docs",
        "ground_truth_version": "pinned-1",
        "ground_truth_hardness": "DOCUMENT",
        "mandate_ref": {"doc": "EDI-MANDATE.md", "version": "short-2026-09-24"},
        "instrument_in_force": {"version": "r1", "rubric_sha256": "a" * 64, "code_sha256": "b" * 64},
        "evaluator_identity": "z-ai/glm-5.3-flash",
        "channel_blind": True,
        "ratified": True,
    }
    base.update(over)
    return base


def reading(**over) -> dict:
    """A readings-only packet: no Specialist named at the outset ⇒ no bar, no numbers."""
    base = {
        "entry": "B",
        "instrument_profile": "full",
        "job_name": "retrofit census",
        "artifact": "repo@abc123",
        "buyer": "Owner",
        "maker": "unrecoverable",
        "evaluator": "z-ai/glm-5.3-flash",
        "mode": "readings",
        "ratified": True,
        "stage": "architecture",
        "human_seat": "Owner via Telegram topic",
        "standard_ref": "the artifact's own docs and tests, frozen 2026-09-29",
        "reads_before_freeze": ["rubric frozen 2026-09-29T10:00Z; git log read after"],
    }
    base.update(over)
    return base


# ------------------------------------------------- PART 1: doctrine

S = "doctrine"

# §3 + C17(retired→structural): while ratified:false the must-asks may live ONLY in `proposed`.
check(S, "ratified:false with must-asks at top level is rejected",
      False, packet(ratified=False), V_PACKET)
check(S, "ratified:false with only `proposed` is accepted",
      True, {
          "entry": "A", "instrument_profile": "full", "job_name": "unratified job",
          "artifact": "artifact/iter-0", "buyer": "Owner", "evaluator": "z-ai/glm-5.3-flash",
          "maker": "some-engine", "mode": "readings", "ratified": False, "stage": "elicitation",
          "proposed": {"rationale": "thresholds and dimension set proposed, unratified"},
      }, V_PACKET)
check(S, "ratified:false may never reach terminal accepted",
      False, {**{k: v for k, v in packet().items() if k in ("entry", "instrument_profile", "job_name",
             "artifact", "buyer", "maker", "evaluator", "mode", "stage")},
              "ratified": False, "proposed": {}, "terminal_state": "accepted", "outcome": "accepted"}, V_PACKET)

# §2 pairing: terminal state and outcome travel together, and pair only as named.
check(S, "terminal_state without outcome is incomplete",
      False, packet(terminal_state="accepted"), V_PACKET)
check(S, "terminal accepted pairs with outcome accepted",
      True, packet(terminal_state="accepted", outcome="accepted"), V_PACKET)
check(S, "no_observation forces terminal needs_owner",
      False, packet(terminal_state="accepted", outcome="no_observation"), V_PACKET)
check(S, "no_artifact forces terminal needs_owner",
      True, packet(terminal_state="needs_owner", outcome="no_artifact"), V_PACKET)
check(S, "census forces terminal accepted on a readings job",
      True, reading(terminal_state="accepted", outcome="census"), V_PACKET)
check(S, "census on a scored job is rejected (outcome/state/mode must agree)",
      False, packet(terminal_state="accepted", outcome="census"), V_PACKET)

# C29 readings: no bar exists ⇒ no Specialist, no thresholds, no numbers, no rejection.
check(S, "readings job carrying bounds is rejected (no bar exists)",
      False, reading(bounds={"T_accept": 8.5}), V_PACKET)
check(S, "readings job naming a Specialist is rejected (naming one late does not license scoring)",
      False, reading(specialist="vendor docs"), V_PACKET)
check(S, "readings job may not produce rejected",
      False, reading(terminal_state="rejected", outcome="rejected"), V_PACKET)

# C32 entry B: a labelled baseline needs the reads that could reveal a defect.
check(S, "entry B without reads_before_freeze is rejected",
      False, {**packet(entry="B", terminal_state="needs_owner", outcome="needs_owner")}, V_PACKET)

# §4 role separation, via the schema's `not` blocks (the validator is the full gate).
check(S, "Owner may not hold the Evaluator seat (string form)",
      False, packet(evaluator="Owner"), V_PACKET)
check(S, "Owner may not hold the Evaluator seat (object name form)",
      False, packet(evaluator={"name": "Owner"}), V_PACKET)
check(S, "Maker and Evaluator may be different engines",
      True, packet(), V_PACKET)

# §1.6 ground truth hardness is a closed enum and the rows are an array.
check(S, "ground truth hardness is a closed enum",
      False, packet(ground_truth=[{"source": "x", "version": "1", "hardness": "HARD"}]),
      V_PACKET)

# §5 the record.
check(S, "a dimension with no observation cannot be recorded",
      False, {**record(), "dimensions": [{k: v for k, v in record()["dimensions"][0].items() if k != "observation"}]},
      V_RECORD)
check(S, "instrument_in_force is required on the record (C30)",
      False, {k: v for k, v in record().items() if k != "instrument_in_force"}, V_RECORD)
check(S, "instrument_in_force names rubric AND runner hashes",
      False, {**record(), "instrument_in_force": {"version": "r1"}}, V_RECORD)
check(S, "violation class is the closed four-locator enum (rule 4)",
      False, {**record(), "violations": [{"id": "V1", "class": "bad_maker", "observation": "x"}]}, V_RECORD)
check(S, "SEVERITY P0/P1/P2 must not appear — the corpus defines no severity scale",
      False, {**record(), "violations": [{"id": "V1", "class": "artifact_missed_standard",
                                          "observation": "x", "severity": "P0"}]}, V_RECORD)
check(S, "a shortfall with no remedy is legal (remedy is optional; fabricated ones are the defect)",
      True, {**record(), "violations": [{"id": "V1", "class": "frame_at_fault", "observation": "x"}]}, V_RECORD)
check(S, "verdict synonyms are rejected — no 'minor-revision' beside 'regenerate'",
      False, {**record(), "verdict": "minor-revision"}, V_RECORD)
check(S, "ratified:false on a record is representable but can never be accepted (loop rule)",
      True, {**record(), "ratified": False}, V_RECORD)
# v1.20.0: the requirement is asserted, not merely satisfied. A record with no passes is exactly what the
# amendment exists to stop, and this battery would have gone on accepting it while the schema gained the rule.
check(S, "a record that names no pass is rejected (v1.20.0 / §5)",
      False, {k: v for k, v in record().items() if k != "passes"}, V_RECORD)
check(S, "a pass with an unknown kind is rejected (§5: scored or confirmation)",
      False, {**record(), "passes": [{**record()["passes"][0], "kind": "spot-check"}]}, V_RECORD)

# ------------------------------------------------- PART 2 (a): the instance layer, labelled

S = "instance"
check(S, "a scored job must name its standing constitution (instance layer, subordinate to the mandate)",
      False, {k: v for k, v in packet().items() if k not in ("constitution_ref", "constitution_version")},
      V_PACKET)
check(S, "stage is optional today — but the applies_to_stages dependency is OPEN, not settled",
      True, {k: v for k, v in packet().items() if k != "stage"}, V_PACKET)
check(S, "the Maker must carry the task classes it has SHOWN, not claimed (§4.1 / rule 10)",
      False, packet(maker={"engine": "e", "version": "1", "feedback_forms": ["diff"]}), V_PACKET)
check(S, "budget without a stated unit is rejected (the unit is the point)",
      False, packet(bounds={**packet()["bounds"], "budget": {"amount": 2}}), V_PACKET)
check(S, "an undecidable escalation must carry what was tried and why no answer is observable",
      False, packet(discoverability={"classification": "undecidable", "question": "which voice?"}),
      V_PACKET)
check(S, "an undecidable escalation with the four required things is accepted",
      True, packet(discoverability={"classification": "undecidable", "question": "which voice?",
                                    "attempted": ["searched the record"], "why_no_observable_answer": "values",
                                    "options": ["A", "B (recommended)"]}), V_PACKET)
check(S, "a discoverable question may be recorded without escalation fields (it is resolved, not asked)",
      True, packet(discoverability={"classification": "discoverable", "question": "which python?"}),
      V_PACKET)

# an audit record IS a §5 record: the audit-only fields ride in instance_extensions.
S = "audit"
def audit(exts=None):
    return {**record(), "instance_extensions": exts if exts is not None else [
        {"name": "artifact_ref", "label": "instance-specific", "value": "repo@abc123 2026-09-29"},
        {"name": "method_note", "label": "instance-specific", "value": "static read of the tree"},
        {"name": "verdict_derivation", "label": "instance-specific", "value": "mean=10 min=10 -> accept"},
    ]}

check(S, "an audit record with the three checkable extensions validates as a §5 record",
      True, audit(), V_AUDIT)
check(S, "an audit record missing artifact_ref is rejected",
      False, audit([{"name": "method_note", "label": "instance-specific", "value": "x"},
                    {"name": "verdict_derivation", "label": "instance-specific", "value": "y"}]), V_AUDIT)
check(S, "audit fields outside instance_extensions violate the corpus §5 shape",
      False, {**audit(), "verdict_derivation": "mean=10"}, V_AUDIT)
check(S, "an audit still obeys every §5 rule (no observation ⇒ no record)",
      False, {**audit(), "dimensions": [{k: v for k, v in record()["dimensions"][0].items() if k != "observation"}]},
      V_AUDIT)

# ------------------------------------------------- PART 2 (b): provenance + one-directional alignment

S = "alignment"
for fname, schema in (("job-packet", PACKET), ("evaluator-record", RECORD), ("audit-record", AUDIT)):
    names_pin = PIN["commit"][:12] in json.dumps(schema)
    results.append((f"{S} · {fname} schema names the corpus pin it was derived from", names_pin,
                    "" if names_pin else "no pin reference — a derived artifact nobody can attribute"))

checklist_ok = (CHECKLIST["contracts_version"] == PIN["coverage"]["contracts_version"]
                and CHECKLIST["contracts_sha256"] == PIN["files"]["EDI-MACHINE-CONTRACTS.md"])
results.append((f"{S} · checklist is built from the pinned Contracts (v{PIN['coverage']['contracts_version']})",
                checklist_ok, "" if checklist_ok else "checklist/Contracts hash mismatch"))

# corpus.pin-on-disk: needs the corpus itself, so it runs (and is a row) only when one resolves.
if CORPUS:
    detected = PIN["files"].get("EDI-MACHINE-CONTRACTS.md", "")[:16]
    live = (hashlib.sha256((CORPUS / "EDI-MACHINE-CONTRACTS.md").read_bytes()).hexdigest()[:16]
            if (CORPUS / "EDI-MACHINE-CONTRACTS.md").is_file() else "")
    pinned_matches_live = detected == live
    results.append((f"{S} · the pin still matches the corpus on disk ({live})", pinned_matches_live,
                    "" if pinned_matches_live else "corpus moved — re-read the doctrine, then tools/build_schemas.py --repin"))
    edi_corpus.ran("corpus.pin-on-disk", pinned_matches_live)
elif edi_corpus.not_run("corpus.pin-on-disk", REQUIRE_CORPUS, edi_corpus.NO_CORPUS_ENV):
    results.append((f"{S} · corpus present (required by PLUMBLINE_REQUIRE_CORPUS) for corpus.pin-on-disk", False,
                    "no corpus resolved"))

# The one-directional invariant, measured on the corpus's own fixture battery — the VENDORED copy of it, so it runs
# with or without a corpus. The vendored bytes are verified against VENDOR.json and tools/pin.json by
# tools/build_schemas.py --check, and against the corpus itself by corpus.battery-equality below.
vendored_schema = json.loads((VENDOR / "job-packet.schema.json").read_text(encoding="utf-8"))
V_VENDORED = Draft202012Validator(vendored_schema)
fx = sorted((VENDOR / "fixtures").glob("*.json"))
print(f"vendored battery: {len(fx)} fixtures from {(VENDOR / 'fixtures').relative_to(REPO).as_posix()}")
rows, violations = [], []
for f in fx:
    obj = json.loads(f.read_text(encoding="utf-8"))
    mine = V_PACKET.is_valid(obj)
    theirs = V_VENDORED.is_valid(obj)
    rows.append((f.name, mine, theirs))
    if mine and not theirs:
        violations.append(f.name)

print(f"--- corpus fixture battery ({len(rows)} files, vendored), derived vs corpus schema ---")
print(f"{'fixture':<52} {'plumbline':>10} {'corpus':>8}")
for name, mine, theirs in rows:
    flag = "  <-- WEAKENED" if mine and not theirs else ""
    print(f"{name:<52} {str(mine):>10} {str(theirs):>8}{flag}")
print("  (plumbline accepting FEWER than the corpus is the intended direction: the instance layer "
      "constrains itself more, and the corpus's validator remains the floor.)")
results.append((f"{S} · no fixture is accepted by Plumbline and rejected by the corpus ({len(violations)} violations)",
                not violations, "" if not violations else f"WEAKENED: {violations}"))

# corpus.battery-equality: the vendored copy is still the corpus's bytes (schemas and the whole fixture set).
if CORPUS:
    mismatched = []
    for name in ("job-packet.schema.json", "evaluator-record.schema.json"):
        a, b = VENDOR / name, CORPUS / "schemas" / name
        if not (a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()):
            mismatched.append(name)
    corpus_fx = {q.name for q in (CORPUS / "schemas" / "fixtures").glob("*.json")}
    vendored_fx = {q.name for q in fx}
    mismatched += [f"fixtures/{n} (only in {'corpus' if n in corpus_fx else 'vendored copy'})"
                   for n in sorted(corpus_fx ^ vendored_fx)]
    mismatched += [f"fixtures/{n}" for n in sorted(corpus_fx & vendored_fx)
                   if (VENDOR / "fixtures" / n).read_bytes() != (CORPUS / "schemas" / "fixtures" / n).read_bytes()]
    results.append((f"{S} · the vendored schemas and fixture battery are the corpus's bytes "
                    f"({2 + len(corpus_fx)} files)", not mismatched,
                    "" if not mismatched else f"differ: {mismatched[:4]}"))
    edi_corpus.ran("corpus.battery-equality", not mismatched)
elif edi_corpus.not_run("corpus.battery-equality", REQUIRE_CORPUS, edi_corpus.NO_CORPUS_ENV):
    results.append((f"{S} · corpus present (required by PLUMBLINE_REQUIRE_CORPUS) for corpus.battery-equality", False,
                    "no corpus resolved"))

# ---------------------------------------------------------------- PART 3: custody/v1 (corpus-free)
# Plumbline also writes custody/v1 records (kit/emit_custody.py). Their schema is DERIVED from the pinned
# evaluatordriven/custody schema (tools/build_schemas.py --custody); these cases make the drift check able to
# fail and pin the emitter's refusals. None needs the corpus, a network, or a credential.
import shutil, tempfile, zipfile, copy, hashlib, time
from datetime import datetime, timedelta, timezone

S = "custody"
CPIN = PIN.get("custody") or {}
TMP = Path(tempfile.mkdtemp(prefix="plumbline-custody-"))
FIX = REPO / "tests" / "fixtures" / "custody" / "job-rejected"


def res(row):
    """Like the rows above: the reason is printed only when the case misbehaves."""
    name, ok, why = row
    results.append((name, ok, "" if ok else " ".join(str(why).split())[:110]))


def run_py(args, cwd=REPO, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k != "CUSTODY_DIR"}
    env.update(env_extra or {})
    r = subprocess.run([VENV_PY, *args], cwd=cwd, capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


def tree_copy(name):
    """A throwaway copy of just what the custody drift check reads."""
    d = TMP / name
    for sub in ("tools", "schemas"):
        shutil.copytree(REPO / sub, d / sub)
    return d


def clean_checkout(dest):
    """The emitter refuses to run from a dirty tree (it records its own commit), so the cases below run it from a
    throwaway clean commit of this working tree: tracked + untracked-but-not-ignored files, as `git status` sees them."""
    dest.mkdir(parents=True)
    g = subprocess.run(["git", "-C", str(REPO), "ls-files", "-co", "--exclude-standard", "-z"], capture_output=True, text=True)
    names = [n for n in g.stdout.split("\0") if n] if g.returncode == 0 else \
        [str(q.relative_to(REPO)) for q in REPO.rglob("*") if q.is_file() and ".git" not in q.parts and "__pycache__" not in q.parts]
    for n in names:
        if (REPO / n).is_file():
            (dest / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / n, dest / n)
    git = ["git", "-C", str(dest), "-c", "user.name=test", "-c", "user.email=test@localhost", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "clean checkout for custody tests"]):
        subprocess.run(git + args, capture_output=True, check=True)
    return dest


SNAP = clean_checkout(TMP / "tree-clean")


def emit(job, out, tree=None, extra=(), allow_hand=True):
    """Emit a record. Synthetic fixtures are hand-typed by design, so they run with --allow-hand-times (the
    emitter refuses hand times by default; the T2 cases below drive the no-switch path)."""
    args = [str((tree or SNAP) / "kit" / "emit_custody.py"), "--job-dir", str(job), "--out", str(out), *extra]
    if allow_hand:
        args.append("--allow-hand-times")
    return run_py(args)


def job_copy(name, overlay=None):
    d = TMP / name
    shutil.copytree(FIX, d)
    if overlay:
        shutil.copytree(FIX.parent / "failures" / overlay, d, dirs_exist_ok=True)
    return d


def append_text(path, text):
    """Add rows to a job's live event log; the fixture's own rows (its provider pin) stay."""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(text)


def ledger_edit(j, fn):
    c = json.loads((j / "inputs" / "custody.json").read_text()); fn(c)
    (j / "inputs" / "custody.json").write_text(json.dumps(c))


def refused(name, j, tag, out_name=None, **kw):
    """Exit 3, the [tag] refusal printed, and no record written."""
    o = TMP / (out_name or f"{j.name}.json")
    rc, out = emit(j, o, **kw)
    res((f"{S} · {name} (exit 3, [{tag}], nothing written)", rc == 3 and f"[{tag}]" in out and not o.exists(),
         f"exit {rc}: {out.strip()[-100:]}"))
    return out


V_CUST = Draft202012Validator(json.loads((SHIP / "custody" / "custody-v1.schema.json").read_text(encoding="utf-8")))
V_CREC = Draft202012Validator(json.loads((SHIP / "custody-record.schema.json").read_text(encoding="utf-8")))

vend = SHIP / "custody" / "custody-v1.schema.json"
res((f"{S} · pin names custody@{CPIN.get('commit', '?')[:12]} and the vendored schema is its bytes",
                bool(CPIN) and vend.is_file() and hashlib.sha256(vend.read_bytes()).hexdigest()
                == CPIN.get("files", {}).get("schema/custody-v1.schema.json"), "vendored copy differs from the pin"))

rc, out = run_py(["tools/build_schemas.py", "--custody", "--check"])
res((f"{S} · derived custody schema regenerates byte-identical (no upstream given)", rc == 0, out.strip()[-90:]))
rc, out = run_py(["tools/build_schemas.py", "--custody", "--check", "--require-upstream"])
res((f"{S} · --require-upstream with no custody checkout is NOT a pass (exit 2)", rc == 2, f"exit {rc}"))

# a moved custody: a checkout whose schema differs from the pin by one required key
moved = TMP / "custody-moved"
src_dir = os.environ.get("CUSTODY_DIR")
if src_dir and (Path(src_dir) / "schema" / "custody-v1.schema.json").is_file():
    shutil.copytree(src_dir, moved, ignore=shutil.ignore_patterns(".git"))
else:
    (moved / "schema").mkdir(parents=True)
    shutil.copy(vend, moved / "schema" / "custody-v1.schema.json")
sch = json.loads((moved / "schema" / "custody-v1.schema.json").read_text(encoding="utf-8"))
sch["required"] = list(sch["required"]) + ["movedForTest"]
(moved / "schema" / "custody-v1.schema.json").write_text(json.dumps(sch, indent=2), encoding="utf-8")
rc, out = run_py(["tools/build_schemas.py", "--custody", "--check", "--custody-dir", str(moved)])
res((f"{S} · a custody schema that moved is reported as drift (exit 1)",
                rc == 1 and "schema/custody-v1.schema.json changed" in out, f"exit {rc}: {out.strip()[-80:]}"))

t = tree_copy("hand-edited")
d = json.loads((t / "schemas" / "custody-record.schema.json").read_text(encoding="utf-8"))
d["required"] = ["handEdited"]
(t / "schemas" / "custody-record.schema.json").write_text(json.dumps(d, indent=2), encoding="utf-8")
rc, out = run_py([str(t / "tools" / "build_schemas.py"), "--custody", "--check"], cwd=t)
res((f"{S} · a hand-edited derived custody schema is reported (exit 1)",
                rc == 1 and "hand-edited" in out, f"exit {rc}"))
t = tree_copy("vendored-edited")
(t / "schemas" / "custody" / "custody-v1.schema.json").write_text(vend.read_text(encoding="utf-8") + " ", encoding="utf-8")
rc, out = run_py([str(t / "tools" / "build_schemas.py"), "--custody", "--check"], cwd=t)
res((f"{S} · an edited vendored custody schema is reported (exit 1)", rc == 1, f"exit {rc}"))

# the emitter on the synthetic fixture
rec_path = TMP / "fixture.custody.json"
rc, out = emit(FIX, rec_path)
rec = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.is_file() else {}
res((f"{S} · fixture job emits with no gap (exit 0)", rc == 0, out.strip()[-90:]))
check(S, "emitted record is valid against the PINNED custody schema", True, rec, V_CUST)
check(S, "emitted record is valid against the derived Plumbline custody schema", True, rec, V_CREC)
bad = copy.deepcopy(rec); bad["predicate"]["verdict"] = "reject"
check(S, "a bare predicate.verdict is refused (verdict rides only in x-plumbline)", False, bad, V_CREC)
bad = copy.deepcopy(rec); bad["predicate"]["violations"][0]["x-plumbline"].pop("locator", None)
check(S, "a violation with no rule-4 locator is refused", False, bad, V_CREC)
bad = copy.deepcopy(rec); bad["predicate"]["x-plumbline"]["verdict"] = "pass"
check(S, "x-plumbline.verdict outside Plumbline's four verdicts is refused", False, bad, V_CREC)
res((f"{S} · record carries no file the fixture lacks: every digest is a file's",
                rec.get("predicate", {}).get("bar", {}).get("digest", {}).get("sha256")
                == hashlib.sha256((FIX / "custody" / "bar.md").read_bytes()).hexdigest(), "bar digest is not bar.md's"))

j = job_copy("given")
p = json.loads((j / "packet.json").read_text()); p["disposition_state"] = "given"
(j / "packet.json").write_text(json.dumps(p))
rc, out = emit(j, TMP / "given.json")
r2 = json.loads((TMP / "given.json").read_text()) if (TMP / "given.json").is_file() else {}
res((f"{S} · disposition.state is the packet's, not the verdict's (reject + given)",
                r2.get("predicate", {}).get("disposition", {}).get("state") == "given"
                and r2["predicate"]["x-plumbline"]["verdict"] == "reject", out.strip()[-80:]))

j = job_copy("no-disposition")
p = json.loads((j / "packet.json").read_text()); p.pop("disposition_state")
(j / "packet.json").write_text(json.dumps(p))
rc, out = emit(j, TMP / "nodisp.json")
r3 = json.loads((TMP / "nodisp.json").read_text()) if (TMP / "nodisp.json").is_file() else {}
res((f"{S} · no recorded disposition is emitted as null and named, never guessed (exit 1)",
                rc == 1 and r3.get("predicate", {}).get("disposition", {}).get("state") is None
                and any(g["field"] == "disposition.state" for g in r3["predicate"]["x-plumbline"]["gaps"]), f"exit {rc}"))

j = job_copy("bad-remedy")
c = json.loads((j / "inputs" / "custody.json").read_text()); c["violations"]["V1"]["remedy"]["text"] = "a remedy nobody wrote"
(j / "inputs" / "custody.json").write_text(json.dumps(c))
emit(j, TMP / "remedy.json")
r4 = json.loads((TMP / "remedy.json").read_text())
res((f"{S} · a remedy not verbatim in evaluator evidence is dropped, not written",
                "remedy" not in r4["predicate"]["violations"][0]["x-plumbline"], "remedy synthesised"))

j = job_copy("no-violation-dimension")
c = json.loads((j / "inputs" / "custody.json").read_text()); c["violations"]["V1"].pop("dimension")
(j / "inputs" / "custody.json").write_text(json.dumps(c))
rc, out = emit(j, TMP / "nodim.json")
r7 = json.loads((TMP / "nodim.json").read_text())["predicate"]
res((f"{S} · a violation whose bar dimension nobody recorded is null and named, not guessed (exit 1)",
     rc == 1 and r7["violations"][0]["dimension"] is None
     and any(g["field"] == "violations[V1].dimension" for g in r7["x-plumbline"]["gaps"]), f"exit {rc}"))

j = job_copy("same-family")
c = json.loads((j / "inputs" / "custody.json").read_text())
c["maker"]["model"] = dict(c["evaluators"][0]["model"], readOnly=False)
c["maker"]["model"].pop("endpoint", None)
(j / "inputs" / "custody.json").write_text(json.dumps(c))
ml = j / "custody" / "evidence" / "harness-maker-fixture.log"        # the maker's log must show that model too
ml.write_text(ml.read_text().replace("fixture/maker-1", "example-1"))
emit(j, TMP / "same.json")
r5 = json.loads((TMP / "same.json").read_text())["predicate"]
res((f"{S} · same model as maker is computed from identifiers and its family gap recorded",
                r5["evaluators"][0].get("sameModelAsMaker") is True and any("shares model family" in s for s in r5["separationGaps"]),
                "not computed"))

j = job_copy("no-inputs")
(j / "inputs" / "custody.json").unlink()
rc, out = emit(j, TMP / "noinputs.json")
r6 = json.loads((TMP / "noinputs.json").read_text())["predicate"]
res((f"{S} · with no custody inputs the record is honest: nulls, named gaps, exit 1",
                rc == 1 and r6["bar"]["digest"] is None and r6["maker"]["method"] is None
                and len(r6["x-plumbline"]["gaps"]) > 0, f"exit {rc}"))

j = job_copy("open-job")
p = json.loads((j / "packet.json").read_text()); p.pop("terminal_state")
(j / "packet.json").write_text(json.dumps(p))
rc, out = emit(j, TMP / "open.json")
res((f"{S} · a job with no terminal state gets no custody record (exit 2)",
                rc == 2 and not (TMP / "open.json").exists(), f"exit {rc}"))

# ---- history refusals (exit 3): a record that would misstate its own history is not written ----
for ov, tag in (("hand-times", "time"), ("after-emit", "after-emit"), ("router-endpoint", "endpoint"),
                ("agent-approval", "approval")):
    refused(f"failure fixture {ov}", job_copy(f"fail-{ov}", ov), tag)
out_ = refused("hand times typed after the maker call also break event order", job_copy("fail-order", "hand-times"), "order")
j = job_copy("keep-old", "agent-approval"); keep = TMP / "keep-old.json"; keep.write_text("OLD RECORD\n")
rc, _ = emit(j, keep)
res((f"{S} · a refusal leaves an existing record byte-for-byte as it was", rc == 3 and keep.read_text() == "OLD RECORD\n", f"exit {rc}"))

j = job_copy("tol-61")
ledger_edit(j, lambda c: c["passes"]["pass-a"].update(at="2026-10-20T12:01:04Z"))
refused("a hand time 61 s off its harness call (tolerance 60 s)", j, "time")
j = job_copy("tol-59")
ledger_edit(j, lambda c: c["passes"]["pass-a"].update(at="2026-10-20T12:01:02Z"))
rc, out = emit(j, TMP / "tol59.json")
rt = json.loads((TMP / "tol59.json").read_text())["predicate"] if rc == 0 else {}
res((f"{S} · a hand time 59 s off is accepted, and the record carries the LOG's time", rc == 0 and
     rt["checks"][0]["at"] == "2026-10-20T12:00:03Z", f"exit {rc}: {out.strip()[-90:]}"))
j = job_copy("vendor-host")
ledger_edit(j, lambda c: c["maker"]["model"].update(endpoint="api.maker.example"))
o = refused("a hand vendor host when the log shows the routed upstream", j, "endpoint")
res((f"{S} · the endpoint refusal names the upstream the log shows", "api.deepinfra.com" in o, o.strip()[-90:]))
# ---- provider pin through OpenRouter: the endpoint is the DECLARED host, confirmed call by call from the log ----
mx = (rec.get("predicate") or {}).get("maker") or {}
mxx = mx.get("x-plumbline") or {}
res((f"{S} · matching pin: endpoint is the pinned host; aggregator, provider, slug and routing request recorded",
     (mx.get("model") or {}).get("endpoint") == "api.deepinfra.com" and mxx.get("aggregator") == "openrouter.ai"
     and mxx.get("upstream_provider") == "DeepInfra" and mxx.get("provider_slug") == "deepinfra/fp8"
     and (mxx.get("routing") or {}).get("request_ok") is True
     and mxx["routing"]["requests"][0]["provider"] == {"order": ["deepinfra/fp8"], "allow_fallbacks": False, "zdr": True},
     json.dumps(mxx)[:160]))
o = refused("pinned provider, another provider served the call (fallback)", job_copy("pin-fb", "pin-fallback"), "endpoint")
res((f"{S} · the fallback refusal names who served it and the pin", "'Together'" in o and "fallback" in o
     and "'DeepInfra'" in o, o.strip()[-120:]))
o = refused("pinned provider, the log does not say who served the call", job_copy("pin-miss", "pin-provider-missing"), "endpoint")
res((f"{S} · the missing-provider refusal says so", "does not say which provider served it" in o, o.strip()[-120:]))
refused("a pin declared after the seat's first call", job_copy("pin-late", "pin-late"), "order")
j = job_copy("pin-attempt")
lg = j / "custody" / "evidence" / "harness-maker-fixture.log"; x = json.loads(lg.read_text())
x["response"]["openrouter_metadata"] = {"attempts": [{"provider": "Together", "model": "fixture/maker-1", "status": 503},
                                                     {"provider": "DeepInfra", "model": "fixture/maker-1", "status": 200}]}
lg.write_text(json.dumps(x))
o = refused("served by the pin after another provider was tried", j, "endpoint")
res((f"{S} · an attempted fallback is named", "fallback was attempted" in o, o.strip()[-120:]))
j = job_copy("pin-none"); (j / "inputs" / "custody-events.jsonl").unlink(); ledger_edit(j, lambda c: c.pop("routing"))
o = refused("an aggregator call with no provider pin declared", j, "endpoint")
res((f"{S} · no pin: the refusal says the emitter will not guess", "no provider pin was declared" in o, o.strip()[-120:]))
j = job_copy("pin-unlogged"); (j / "inputs" / "custody-events.jsonl").unlink()
refused("a pin typed into the inputs but never logged live", j, "endpoint")
j = job_copy("pin-unpinned", "routing-unpinned")
rc, out = emit(j, TMP / "unpinned.json")
ru = json.loads((TMP / "unpinned.json").read_text()) if (TMP / "unpinned.json").is_file() else {}
gp = [g for g in (ru.get("predicate") or {}).get("x-plumbline", {}).get("gaps", []) if g["field"] == "routing.maker.request"]
res((f"{S} · a request without no-fallback + ZDR is written with a HARD gap (exit 1), what it asked recorded",
     rc == 1 and len(gp) == 1 and gp[0]["hard"] and "allow_fallbacks" in gp[0]["reason"] and "zdr" in gp[0]["reason"]
     and ru["predicate"]["maker"]["x-plumbline"]["routing"]["request_ok"] is False
     and ru["predicate"]["maker"]["model"]["endpoint"] == "api.deepinfra.com", f"exit {rc}: {out.strip()[-120:]}"))
check(S, "the gapped routing record is still valid against the PINNED custody schema", True, ru, V_CUST)
j = job_copy("pin-deny")
lg = j / "custody" / "evidence" / "harness-maker-fixture.log"; x = json.loads(lg.read_text())
x["request"]["provider"] = {"order": ["deepinfra/fp8"], "allow_fallbacks": False, "data_collection": "deny"}
lg.write_text(json.dumps(x))
rc, out = emit(j, TMP / "pin-deny.json")
res((f"{S} · data_collection deny in place of zdr is accepted (exit 0)", rc == 0, out.strip()[-90:]))
j = job_copy("pin-nobody")
lg = j / "custody" / "evidence" / "harness-maker-fixture.log"; x = json.loads(lg.read_text())
x["request"] = {"url": x["request"]["url"], "model": x["request"]["model"]}
lg.write_text(json.dumps(x))
rc, out = emit(j, TMP / "pin-nobody.json")
rb = json.loads((TMP / "pin-nobody.json").read_text()) if (TMP / "pin-nobody.json").is_file() else {}
res((f"{S} · a log without the request body: routing request unreadable is a hard gap (exit 1)",
     rc == 1 and any(g["field"] == "routing.maker.request" and "cannot be read" in g["reason"]
                     for g in rb["predicate"]["x-plumbline"]["gaps"]), f"exit {rc}"))
LEDGER = SNAP / "kit" / "custody_ledger.py"
pin_args = ["pin", "--seat", "maker", "--provider", "DeepInfra", "--slug", "deepinfra/fp8", "--host", "api.deepinfra.com"]
j = job_copy("ledger-pin-late")
rc, out = run_py([str(LEDGER), *pin_args[:1], "--job-dir", str(j), *pin_args[1:]])
res((f"{S} · ledger pin is refused once the seat's log has a call (exit 3)", rc == 3 and "already records" in out, f"exit {rc}: {out.strip()[-90:]}"))
j = job_copy("ledger-pin-ok"); (j / "custody" / "evidence" / "harness-maker-fixture.log").unlink()
(j / "inputs" / "custody-events.jsonl").unlink(); ledger_edit(j, lambda c: c.pop("routing"))
rc, out = run_py([str(LEDGER), "pin", "--job-dir", str(j), *pin_args[1:]])
evs = [json.loads(l) for l in (j / "inputs" / "custody-events.jsonl").read_text().splitlines()] if rc == 0 else []
cj = json.loads((j / "inputs" / "custody.json").read_text())
res((f"{S} · ledger pin before the first call logs the pin live and in the inputs (exit 0)",
     rc == 0 and evs and evs[-1]["event"] == "pin" and evs[-1]["host"] == "api.deepinfra.com"
     and cj["routing"]["maker"]["declaredAt"] == evs[-1]["at"], f"exit {rc}: {out.strip()[-90:]}"))
rc, out = run_py([str(LEDGER), "pin", "--job-dir", str(j), "--seat", "maker", "--provider", "X", "--slug", "x",
                  "--host", "openrouter.ai"])
res((f"{S} · ledger pin refuses the aggregator's own host as the endpoint (exit 2)", rc == 2, f"exit {rc}"))
j = job_copy("no-maker-log"); (j / "custody" / "evidence" / "harness-maker-fixture.log").unlink()
refused("a model maker with no harness log", j, "time")
j = job_copy("wrong-model")
ledger_edit(j, lambda c: c["evaluators"][0]["model"].update(identifier="other-1"))
refused("a recorded model identifier the log's calls did not run", j, "model")
j = job_copy("unlinked-control")
ledger_edit(j, lambda c: c["controls"][0].update(call="eval_nope"))
refused("a control linked to no call in the harness log", j, "time")

j = job_copy("model-approver")
ledger_edit(j, lambda c: c["bar"]["approvals"][1].update(by="fixture-maker"))
refused("an approval by the maker model", j, "approval")
j = job_copy("kind-model")
ledger_edit(j, lambda c: c["bar"]["approvals"][1].update(kind="model"))
refused("an approval marked kind: model", j, "approval")
j = job_copy("no-orchestrator")
ledger_edit(j, lambda c: c.pop("orchestrator"))
refused("approvals with no orchestrator named in the ledger", j, "approval")
j = job_copy("orch-adopted")
ledger_edit(j, lambda c: c["bar"]["approvals"][1].update(by="fixture-cos", kind="agent",
                                                           adopted={"document": "D", "version": "1"}))
refused("the orchestrator, even marked agent with adopted set", j, "approval")
j = job_copy("bot-unmarked")
ledger_edit(j, lambda c: c["bar"]["approvals"][1].update(by="Review Bot"))
p = json.loads((j / "packet.json").read_text()); p["specialist"] = "Review Bot"; (j / "packet.json").write_text(json.dumps(p))
refused("an agent-like approver not marked kind: agent", j, "approval")
j = job_copy("agent-no-adopted")
ledger_edit(j, lambda c: c["bar"]["approvals"][1].update(by="Review Bot", kind="agent"))
p = json.loads((j / "packet.json").read_text()); p["specialist"] = "Review Bot"; (j / "packet.json").write_text(json.dumps(p))
refused("an agent approval with adopted null", j, "approval")
j = job_copy("agent-adopted")
ledger_edit(j, lambda c: c["bar"]["approvals"][1].update(by="Review Bot", kind="agent",
                                                           adopted={"document": "Fixture Review Charter", "version": "1.0"}))
p = json.loads((j / "packet.json").read_text()); p["specialist"] = "Review Bot"; (j / "packet.json").write_text(json.dumps(p))
rc, out = emit(j, TMP / "agent-adopted.json")
res((f"{S} · an agent approval marked kind: agent WITH adopted set is written (exit 0)", rc == 0, out.strip()[-90:]))
j = job_copy("seat-mismatch")
ledger_edit(j, lambda c: c["bar"]["approvals"][1].update(by="Someone Else"))
refused("an approver who is not the packet's named seat holder", j, "approval")

j = job_copy("live-mismatch")
append_text(j / "inputs" / "custody-events.jsonl", json.dumps(
    {"event": "approve", "role": "specialist", "by": "Fixture Specialist", "at": "2026-10-20T10:09:00Z"}) + "\n")
refused("a ledger approval time that differs from the live event log", j, "time")
j = job_copy("live-match")
append_text(j / "inputs" / "custody-events.jsonl", "".join(json.dumps(e) + "\n" for e in (
    {"event": "freeze", "at": "2026-10-20T10:00:00Z", "bar_sha256": hashlib.sha256((FIX / "custody" / "bar.md").read_bytes()).hexdigest()},
    {"event": "approve", "role": "specialist", "by": "Fixture Specialist", "at": "2026-10-20T10:10:00Z"})))
rc, out = emit(j, TMP / "live.json")
rl = json.loads((TMP / "live.json").read_text())["predicate"] if rc == 0 else {}
res((f"{S} · a ledger that matches the live event log is written and says so", rc == 0 and
     rl["bar"]["approvals"][1]["x-plumbline"]["time_source"].startswith("logged live"), f"exit {rc}: {out.strip()[-80:]}"))
j = job_copy("bar-moved")
append_text(j / "inputs" / "custody-events.jsonl", json.dumps({"event": "freeze", "at": "2026-10-20T10:00:00Z", "bar_sha256": "0" * 64}) + "\n")
refused("a bar that changed after its logged freeze", j, "order")

head = subprocess.run(["git", "-C", str(SNAP), "rev-parse", "HEAD", "HEAD^{tree}"], capture_output=True, text=True).stdout.split()
res((f"{S} · the record names the emitter's commit and tree, clean", rec.get("predicate", {}).get("x-plumbline", {}).get("emitter", {})
     .get("commit") == head[0] and rec["predicate"]["x-plumbline"]["emitter"].get("tree") == head[1]
     and rec["predicate"]["x-plumbline"]["emitter"].get("dirty") is False, "emitter revision not recorded"))
rc, out = emit(FIX, TMP / "exp-tree.json", extra=("--expect-revision", head[1][:12]))
res((f"{S} · a stated revision matching the emitter's tree is accepted (survives git am)", rc == 0, out.strip()[-80:]))
refused("a stated revision the emitter is not at", FIX, "revision", "exp-bad.json", extra=("--expect-revision", "deadbeef0"))
dirty = TMP / "tree-dirty"; shutil.copytree(SNAP, dirty)
(dirty / "kit" / "emit_custody.py").write_text((dirty / "kit" / "emit_custody.py").read_text() + "\n# local edit\n")
refused("an emitter whose tree has an uncommitted edit", FIX, "revision", "dirty.json", tree=dirty)
nogit = TMP / "tree-nogit"; shutil.copytree(SNAP / "kit", nogit / "kit")
refused("an emitter outside any git checkout", FIX, "revision", "nogit.json", tree=nogit)

zp = TMP / "bundle.zip"
rc, out = run_py(["tools/pack_stranger_bundle.py", "--job-dir", str(FIX), "--record", str(rec_path), "--out", str(zp)])
ok, why = rc == 0 and zp.is_file(), out.strip()[-80:]
if ok:
    with zipfile.ZipFile(zp) as z:
        man = z.read("MANIFEST.sha256").decode().splitlines()
        bad_rows = [ln for ln in man if hashlib.sha256(z.read(ln.split("  ", 1)[1])).hexdigest() != ln.split("  ", 1)[0]]
        need = {"record.custody.json", "bar/bar.md", "files/artifact.md", "evidence/pass-a-D2.txt", "evidence/harness-eval-a.log"}
        ok = not bad_rows and need <= set(z.namelist())
        why = f"bad rows {bad_rows}" if bad_rows else f"missing {need - set(z.namelist())}"
    rc2, _ = run_py(["tools/pack_stranger_bundle.py", "--job-dir", str(FIX), "--record", str(rec_path), "--out", str(TMP / "b2.zip")])
    ok = ok and (TMP / "b2.zip").read_bytes() == zp.read_bytes()
res((f"{S} · stranger bundle: manifest sha256s match, required files present, packing is deterministic", ok, why))

# ---- T2/T3: hand-entered times are refused by default, flagged (never verified) under --allow-hand-times ----
o = TMP / "t2-refuse.json"
rc, out = emit(FIX, o, allow_hand=False)
res((f"{S} · T2 hand times are refused by default: exit 3, [hand-time], REFUSED (history), nothing written",
     rc == 3 and "[hand-time]" in out and "REFUSED (history)" in out and not o.exists(),
     f"exit {rc}: {out.strip()[-140:]}"))
res((f"{S} · T2c a time typed into custody.json with no ledger line is named (disposition.at, its source)",
     "disposition.at" in out and ("inputs-no-ledger" in out or "ledger-no-writer" in out), out.strip()[-140:]))

j = job_copy("t2b-hand")
append_text(j / "inputs" / "custody-events.jsonl", json.dumps(
    {"event": "approve", "role": "buyer", "by": "Fixture Buyer", "at": "2026-10-20T10:11:00Z",
     "writer": "hand"}) + "\n")
rc, out = emit(j, TMP / "t2b.json", allow_hand=False)
res((f"{S} · T2b a ledger line with writer \"hand\" is a hand time (ledger-hand, named)",
     rc == 3 and "ledger-hand" in out and "bar.approvals[" in out, f"exit {rc}: {out.strip()[-140:]}"))

j = job_copy("t2d-override")
cj = json.loads((j / "inputs" / "custody.json").read_text())
spec_at = next((a.get("at") for a in cj["bar"]["approvals"] if a.get("role") == "specialist"),
               "2026-10-20T10:10:00Z")
append_text(j / "inputs" / "custody-events.jsonl", "".join(json.dumps(e) + "\n" for e in (
    {"event": "approve", "role": "specialist", "by": "Fixture Specialist", "at": spec_at,
     "writer": "kit/custody_ledger.py@abc123def456"},
    {"event": "approve", "role": "specialist", "by": "Fixture Specialist", "at": spec_at,
     "writer": "hand"})))
rc, out = emit(j, TMP / "t2d.json", allow_hand=False)
res((f"{S} · T2d a later hand line overrides an earlier tool line (ledger-hand, named)",
     rc == 3 and "ledger-hand" in out and "bar.approvals[" in out, f"exit {rc}: {out.strip()[-140:]}"))

o = TMP / "t3-allow.json"
rc, out = emit(FIX, o, allow_hand=True)
rx = json.loads(o.read_text())["predicate"]["x-plumbline"] if o.is_file() else {}
ht = rx.get("hand_times") or []
by_field = {e.get("field"): e for e in ht}
res((f"{S} · T3 with --allow-hand-times the record is written and hand_times lists the hand fields with file:line",
     rc == 0 and "disposition.at" in by_field and by_field["disposition.at"].get("line") is not None
     and len(ht) >= 1 and all(e.get("file") and e.get("source") for e in ht), f"exit {rc}: {out.strip()[-140:]}"))
al = (rx.get("allowances") or {}).get("hand_times") or {}
res((f"{S} · T3 the allowance is recorded (switch, the emitter's writer, its tool-clock at)",
     al.get("switch") == "--allow-hand-times" and str(al.get("writer", "")).startswith("kit/emit_custody.py@")
     and bool(al.get("at")), json.dumps(al)[:140]))
res((f"{S} · T3 the switch silences nothing else: the repo overlay failures/hand-times still refuses (time)",
     emit(job_copy("t3-contradiction", "hand-times"), TMP / "t3c.json", allow_hand=True)[0] == 3,
     "the contradiction overlay no longer refuses"))

# ---- F1h: every F1 line is carried into x-plumbline with its file:line source ----
j = job_copy("f1h")
append_text(j / "inputs" / "custody-events.jsonl", "".join(json.dumps(e) + "\n" for e in (
    {"event": "generation", "action": "open", "seat": "maker", "n": 1, "prompt_file": "p.md",
     "prompt_sha256": "a" * 64, "at": "2026-10-20T10:01:00Z", "writer": "kit/custody_ledger.py@abc123def456"},
    {"event": "generation", "action": "close", "seat": "maker", "n": 1, "outcome": "done",
     "at": "2026-10-20T10:20:00Z", "writer": "kit/custody_ledger.py@abc123def456"},
    {"event": "evaluation", "batch": "b1", "evaluator": "eval-a", "verdict_file": "v.json",
     "verdict_sha256": "b" * 64, "at": "2026-10-20T10:30:00Z", "writer": "kit/custody_ledger.py@abc123def456"},
    {"event": "relay", "kind": "relay", "quote": "buyer likes it", "from": "relay-bot",
     "source_chat": "chat-1", "source_at": "2026-10-20T10:31:00Z", "at": "2026-10-20T10:32:00Z",
     "writer": "kit/custody_ledger.py@abc123def456"},
    {"event": "amendment", "file": "amend.md", "file_sha256": "c" * 64, "quote": "tighten D2",
     "channel": "chat-1", "said_at": "2026-10-20T10:33:00Z", "at": "2026-10-20T10:34:00Z",
     "writer": "kit/custody_ledger.py@abc123def456"},
)))
o = TMP / "f1h.json"
rc, out = emit(j, o, allow_hand=True)
rx = json.loads(o.read_text())["predicate"]["x-plumbline"] if o.is_file() else {}
ok = (rc == 0
      and any(e.get("action") == "open" and e.get("n") == 1 for e in rx.get("generations") or [])
      and any(e.get("batch") == "b1" for e in rx.get("evaluations") or [])
      and any(e.get("quote") == "buyer likes it" for e in rx.get("relays") or [])
      and any(e.get("quote") == "tighten D2" for e in rx.get("amendments") or [])
      and all(str(e.get("source", "")).startswith("inputs/custody-events.jsonl:")
              for k in ("generations", "evaluations", "relays", "amendments") for e in rx.get(k) or []))
res((f"{S} · F1h the emitter carries generations/evaluations/relays/amendments into x-plumbline with file:line",
     ok, f"exit {rc}: {out.strip()[-140:]}"))

# ---- X1: the inputs' own x-plumbline is deep-equal under .inputs and cannot shadow the emitter's keys ----
j = job_copy("x1-inputs")
c = json.loads((j / "inputs" / "custody.json").read_text())
inp = {"note": "from inputs", "verdict": "JUNK", "gaps": ["JUNK"], "times": "JUNK",
       "hand_times": "JUNK", "nested": {"k": [1, 2, 3]}}
c["x-plumbline"] = inp
(j / "inputs" / "custody.json").write_text(json.dumps(c, indent=2) + "\n")
o = TMP / "x1.json"
rc, out = emit(j, o, allow_hand=True)
rx = json.loads(o.read_text())["predicate"]["x-plumbline"] if o.is_file() else {}
res((f"{S} · X1 an inputs x-plumbline is deep-equal under .inputs and cannot shadow the emitter's own keys",
     rc == 0 and rx.get("inputs") == inp and rx.get("verdict") != "JUNK"
     and isinstance(rx.get("gaps"), list) and isinstance(rx.get("hand_times"), list)
     and rx.get("times") != "JUNK", f"exit {rc}: {out.strip()[-140:]}"))

# ---- T4/E1/E3: a job whose every time comes from the kit's own tools, and the hand-time coverage they need ----
def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def stamp_log(path, at):
    """Write the logger's own sent_at/received_at into every call of a harness log, as tools/edi/or_call.py
    does. Without them every call is a hand time (T7b), and a job the tools built has none."""
    text = path.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
        items, array = (doc, True) if isinstance(doc, list) else ([doc], False)
    except ValueError:
        items, array = [json.loads(ln) for ln in text.splitlines() if ln.strip()], False
    for c in items:
        if isinstance(c, dict):
            c["sent_at"] = c["received_at"] = at
    path.write_text((json.dumps(items, indent=2) + "\n") if array
                    else "".join(json.dumps(c) + "\n" for c in items), encoding="utf-8")


def tool_built_job(name):
    """The fixture's static facts with every typed time removed, rebuilt only by kit/custody_ledger.py:
    freeze / approve / pin / generation / evaluation / dispose --decided-at (T4, F1b)."""
    j = job_copy(name)
    cj = json.loads((j / "inputs" / "custody.json").read_text(encoding="utf-8"))
    roles = [(a.get("role"), a.get("by")) for a in (cj.get("bar") or {}).get("approvals") or []]
    dsp = cj.get("disposition") or {}
    ev_id = str(((cj.get("evaluators") or [{}])[0]).get("id") or "eval-a")
    for k in ("frozenAt", "approvals"):
        (cj.get("bar") or {}).pop(k, None)
    for k in ("disposition", "routing", "startedAt", "producedAt"):
        cj.pop(k, None)
    for f in (cj.get("passes") or {}).values():
        f.pop("at", None)
    for k in cj.get("controls") or []:
        k.pop("at", None)
    (j / "inputs" / "custody.json").write_text(json.dumps(cj, indent=2) + "\n", encoding="utf-8")
    (j / "inputs" / "custody-events.jsonl").unlink(missing_ok=True)
    pk = json.loads((j / "packet.json").read_text(encoding="utf-8"))
    pk.pop("close", None)          # the tool's clock stamps the events; a fixture close date would pre-date them
    (j / "packet.json").write_text(json.dumps(pk, indent=2) + "\n", encoding="utf-8")

    def run(*args):
        rc, out = run_py([str(LEDGER), *args, "--job-dir", str(j)])
        if rc != 0:
            raise RuntimeError(f"ledger {args[0]} refused: {out.strip()[-200:]}")
        return out

    # a pin is declared before the seat's first call (custody_ledger.py pin): put the fixture's log back after
    mlog = next(iter((j / "custody" / "evidence").glob("harness-maker*.log")), None)
    saved = mlog.read_bytes() if mlog and mlog.is_file() else None
    if saved is not None:
        mlog.unlink()
    run("freeze")
    evs = [json.loads(x) for x in (j / "inputs" / "custody-events.jsonl").read_text().splitlines() if x.strip()]
    fz = _ts(evs[-1]["at"])
    for role, by in roles:
        run("approve", "--role", role, "--by", by)
    run("pin", "--seat", "maker", "--provider", "DeepInfra", "--slug", "deepinfra/fp8", "--host", "api.deepinfra.com")
    if saved is not None:
        mlog.write_bytes(saved)
    run("generation", "open", "--seat", "maker", "--prompt", "custody/bar.md")
    run("generation", "close", "--seat", "maker", "--n", "1", "--outcome", "done")
    run("evaluation", "--batch", "b1", "--evaluator", ev_id, "--verdict", "custody/bar.md")
    # the tools wrote the logs, so every call carries the logger's own times (T7b); the freeze stays earliest
    for lg in (j / "custody" / "evidence").glob("harness-*.log"):
        stamp_log(lg, _iso(fz + timedelta(seconds=1)))
    # dispose --decided-at: the Owner's time, bounded by the last logged check and the tool's clock (F1b, E1)
    last = max([_ts(e["at"]) for e in evs if e.get("at")] + [fz + timedelta(seconds=2)])
    args = ["dispose", "--by", dsp.get("by") or "Fixture Owner"]
    if dsp.get("state") in ("given", "declined"):
        args += ["--state", dsp["state"]]
    for _ in range(6):
        decided = last + timedelta(seconds=1)
        while time.time() < decided.timestamp() + 1.9:
            time.sleep(0.05)
        rc, out = run_py([str(LEDGER), *args, "--job-dir", str(j), "--decided-at", _iso(decided),
                          "--decided-source", "chat"])
        if rc == 0:
            return j
        if "before the last logged check" not in out:
            raise RuntimeError(f"ledger dispose refused: {out.strip()[-200:]}")
        last += timedelta(seconds=1)
    raise RuntimeError("ledger dispose kept refusing (decided_at before the last logged check)")


try:
    TJ = tool_built_job("tool-built")
    tj = json.loads((TJ / "inputs" / "custody.json").read_text(encoding="utf-8"))
    tj["x-plumbline"] = {"note": "from the ledger's inputs", "verdict": "JUNK", "gaps": ["JUNK"],
                         "times": "JUNK", "hand_times": ["JUNK"], "nested": {"k": [1, 2, 3]}}
    (TJ / "inputs" / "custody.json").write_text(json.dumps(tj, indent=2) + "\n", encoding="utf-8")
    o = TMP / "tool-built.json"
    rc, out = emit(TJ, o, allow_hand=False)
    rt = json.loads(o.read_text(encoding="utf-8"))["predicate"] if o.is_file() else {}
    rx = rt.get("x-plumbline") or {}
    res((f"{S} · T4 a job built only with kit/custody_ledger.py emits with no switch (exit 0, empty hand_times)",
         rc == 0 and rx.get("hand_times") == [], f"exit {rc}: {out.strip()[-160:]}"))
    dispo = [json.loads(x) for x in (TJ / "inputs" / "custody-events.jsonl").read_text().splitlines()
             if x.strip() and json.loads(x).get("event") == "dispose"]
    res((f"{S} · F1b the record's disposition.at is the line's decided_at, not the tool clock",
         bool(dispo) and (rt.get("disposition") or {}).get("at") == dispo[-1].get("decided_at")
         and dispo[-1].get("decided_at") != dispo[-1].get("at"),
         f"decided_at {dispo[-1].get('decided_at') if dispo else None}"))
    res((f"{S} · F1h/X1 the tool-built record carries the ledger arrays with file:line and the inputs deep-equal",
         all(str(e.get("source", "")).startswith("inputs/custody-events.jsonl:")
             for k in ("generations", "evaluations") for e in rx.get(k) or [])
         and bool(rx.get("generations")) and bool(rx.get("evaluations"))
         and rx.get("inputs") == tj["x-plumbline"] and rx.get("verdict") != "JUNK"
         and isinstance(rx.get("hand_times"), list)
         and (rx.get("spend") or {}).get("tolerance_usd") == 0.0001,
         json.dumps(rx.get("inputs"))[:140]))
except Exception as exc:
    res((f"{S} · T4 a job built only with kit/custody_ledger.py emits with no switch (exit 0, empty hand_times)",
         False, f"{type(exc).__name__}: {exc}"[:160]))

# E2: a typed pass time is a hand time even when a harness call is linked
j = job_copy("t2-pass-at")
c = json.loads((j / "inputs" / "custody.json").read_text(encoding="utf-8"))
c["passes"]["pass-a"]["at"] = "2026-10-20T12:00:02Z"
(j / "inputs" / "custody.json").write_text(json.dumps(c, indent=2) + "\n", encoding="utf-8")
rc, out = emit(j, TMP / "t2pass.json", allow_hand=False)
res((f"{S} · T2c/E2 a typed passes.<id>.at is a hand time even when a call is linked (inputs-no-ledger)",
     rc == 3 and "passes.pass-a.at" in out and "inputs-no-ledger" in out, f"exit {rc}: {out.strip()[-140:]}"))
o = TMP / "t2pass-allow.json"
rc, out = emit(j, o, allow_hand=True)
ht = {e.get("field"): e for e in ((json.loads(o.read_text())["predicate"]["x-plumbline"]["hand_times"])
                                  if o.is_file() else [])}
res((f"{S} · E2 under --allow-hand-times the typed pass time is listed and the record carries the call's time",
     rc == 0 and (ht.get("passes.pass-a.at") or {}).get("source") == "inputs-no-ledger"
     and json.loads(o.read_text())["predicate"]["checks"][0]["at"] == "2026-10-20T12:00:03Z",
     f"exit {rc}: {out.strip()[-140:]}"))

# E3: every call of every harness log read, both fields (the fixture's evaluator log has no logger sent_at)
rc, out = emit(FIX, TMP / "e3.json", allow_hand=False)
res((f"{S} · T7b/E3 every evaluator call the logger did not stamp is named (harness-eval-a.log, server time)",
     rc == 3 and out.count("harness-eval-a.log#") >= 3 and ".sent_at" in out
     and ("server-header" in out or "response-created" in out), f"exit {rc}: {out.strip()[-160:]}"))

# E1: a real disagreement between custody.json's disposition.at and the line's decided_at still refuses
j = job_copy("dispose-mismatch")
c = json.loads((j / "inputs" / "custody.json").read_text(encoding="utf-8"))
c.setdefault("disposition", {}).update({"at": "2026-10-20T12:30:00Z",
                                        "by": (c.get("disposition") or {}).get("by") or "Fixture Owner"})
(j / "inputs" / "custody.json").write_text(json.dumps(c, indent=2) + "\n", encoding="utf-8")
append_text(j / "inputs" / "custody-events.jsonl", json.dumps(
    {"event": "dispose", "by": c["disposition"]["by"], "at": "2026-10-20T13:00:00Z",
     "decided_at": "2026-10-20T12:31:00Z", "writer": "kit/custody_ledger.py@abc123def456"}) + "\n")
rc, out = emit(j, TMP / "dispose-mismatch.json", allow_hand=True)
res((f"{S} · E1 a dispose line whose decided_at disagrees with custody.json still refuses (time)",
     rc == 3 and "disposition:" in out and "[time]" in out, f"exit {rc}: {out.strip()[-140:]}"))

# ---- V1/V3/T2: a record the emitter wrote verifies at both layers with exit 0 (the verifier's own logic) ----
def _stand_in_checkout(name):
    """A temp custody checkout holding a stand-in checker that refuses unless `--bar` is given (so a verifier
    that forgets it cannot pass again), pinned by its own sha256."""
    d = TMP / name
    (d / "checker").mkdir(parents=True)
    (d / "tools").mkdir(parents=True)
    checker = d / "checker" / "check.py"
    checker.write_text(
        "import json, sys\n"
        "from hashlib import sha256\n"
        "from pathlib import Path\n"
        "def arg(n):\n"
        "    a = sys.argv[1:]\n"
        "    return a[a.index(n) + 1] if n in a and a.index(n) + 1 < len(a) else None\n"
        "if not arg('--bar'):\n"
        "    print('checker: --bar is required', file=sys.stderr)\n"
        "    sys.exit(2)\n"
        "rec = Path(sys.argv[1])\n"
        "files = arg('--files')\n"
        "doc = json.loads(rec.read_text(encoding='utf-8'))\n"
        "for s in doc.get('subject') or []:\n"
        "    p = (Path(files) / s['name']) if files else None\n"
        "    want = (s.get('digest') or {}).get('sha256')\n"
        "    if p is None or not p.is_file() or sha256(p.read_bytes()).hexdigest() != want:\n"
        "        print('checker: subject mismatch for ' + str(s.get('name')), file=sys.stderr)\n"
        "        sys.exit(1)\n"
        "sys.exit(0)\n", encoding="utf-8")
    (d / "tools" / "pin.json").write_text(
        json.dumps({"checker/check.py": hashlib.sha256(checker.read_bytes()).hexdigest()}) + "\n",
        encoding="utf-8")
    return d


def verify_record(rec, job, co):
    return run_py([str(SNAP / "kit" / "plumbline_verify.py"),
                   "--record", str(rec),
                   "--files", str(job / "custody" / "files"),
                   "--evidence", str(job / "custody" / "evidence"),
                   "--ledger", str(job / "inputs" / "custody-events.jsonl"),
                   "--custody", str(co)])


VCO = _stand_in_checkout("verify-checkout")
rt_rec = TMP / "roundtrip.custody.json"
rc, out = emit(FIX, rt_rec, allow_hand=True)
vrc, vout = verify_record(rt_rec, FIX, VCO)
rt_xp = json.loads(rt_rec.read_text())["predicate"]["x-plumbline"] if rt_rec.is_file() else {}
res((f"{S} · V1/V3/T2 a job emitted with --allow-hand-times verifies with exit 0 "
     f"(no flag-without-source, no shadow)",
     rc == 0 and vrc == 0 and "flag-without-source" not in vout and "shadow" not in vout,
     f"emit {rc}, verify {vrc}: {vout.strip()[-160:]}"))
res((f"{S} · T3 every hand time the emitter flagged is in x-plumbline.hand_times with file:line",
     bool(rt_xp.get("hand_times"))
     and all(e.get("field") and e.get("file") and e.get("line") is not None
             for e in rt_xp.get("hand_times") or []),
     json.dumps((rt_xp.get("hand_times") or [])[:2])[:160]))

# ---- F1f: a relay is a report, never an approval (the emitter refuses a relay-only buyer approval) ----
j = job_copy("f1f-relay")
cj = json.loads((j / "inputs" / "custody.json").read_text(encoding="utf-8"))
apps = (cj.get("bar") or {}).get("approvals") or []
spec = next((a for a in apps if a.get("role") == "specialist"), None)
cj["bar"]["approvals"] = [a for a in apps if a.get("role") != "buyer"]
(j / "inputs" / "custody.json").write_text(json.dumps(cj, indent=2) + "\n", encoding="utf-8")
led = j / "inputs" / "custody-events.jsonl"
lines = [json.loads(x) for x in led.read_text(encoding="utf-8").splitlines() if x.strip()] if led.is_file() else []
lines = [e for e in lines if not (e.get("event") == "approve" and e.get("role") == "buyer")]
when = (spec or {}).get("at") or "2026-10-20T10:10:00Z"
if spec and not any(e.get("event") == "approve" and e.get("role") == "specialist" for e in lines):
    lines.append({"event": "approve", "role": "specialist", "by": spec.get("by"), "at": when,
                  "writer": "kit/custody_ledger.py@abc123def456"})
lines.append({"event": "relay", "kind": "relay", "quote": "the buyer is happy", "from": "relay-bot",
              "source_chat": "chat-1", "source_at": when, "at": when,
              "writer": "kit/custody_ledger.py@abc123def456"})
led.write_text("".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")
o = TMP / "f1f-relay.json"
rc, out = emit(j, o, allow_hand=True)
res((f"{S} · F1f a buyer approval that exists only as a relay is refused (approval, buyer, nothing written)",
     rc == 3 and "[approval]" in out and "buyer" in out and not o.exists(), f"exit {rc}: {out.strip()[-140:]}"))
lines.append({"event": "approve", "role": "buyer", "by": "Fixture Buyer", "at": when,
              "writer": "kit/custody_ledger.py@abc123def456"})
led.write_text("".join(json.dumps(e) + "\n" for e in lines), encoding="utf-8")
o2 = TMP / "f1f-relay-ok.json"
rc2, out2 = emit(j, o2, allow_hand=True)
res((f"{S} · F1f a direct buyer approve line removes the relay-only refusal",
     rc2 == 0, f"exit {rc2}: {out2.strip()[-140:]}"))

# ================================================================ JOB 25: the harness-log guard and the
# `--allow-hand-times` boundary.
#
# THE LAW THIS SECTION PINS, in one sentence: the switch admits a TYPED time and does NOT admit a model evaluator's
# unstamped check time. A hand time is a time a person entered; an evaluator's check time is a machine's clock that
# the logger failed to record, and no switch can make it a person's. The emitter must refuse it (exit 3, nothing
# written) with every such call named BY ID, and the four behaviours PR 24 regressed must stay green.
#
# ---------------------------------------------------------------------------------------------------------------
# RE-CUT b1/c1/d1 (2026-11-09, Owner ruling: OPTION 1, the overlay fixture).
#
# The first cut of this section drove b1/c1/d1 against the SHARED `job-rejected` fixture, then edited the typed time
# in a throwaway copy. The Maker refused it and was right, measured: `job-rejected`'s evaluator calls each carry BOTH
# `response_headers.Date` and `response.created`, and a stamped `Date` means the emitter has an instant the logger
# DID record. So the bytes b1 asked to be REFUSED were the same bytes a3/a4/T3/E2 ask to be WRITTEN, and the only
# difference between b1's copy and a4's copy was the VALUE of a typed time (12:00:00Z vs 12:00:02Z) — both within
# tolerance of the log's 12:00:03Z. There was no content difference to key on, so b1 was unsatisfiable against a3/a4
# without a path-name hack. That refusal is recorded in this job's FINDINGS, not repaired by weakening the guard.
#
# THE OVERLAY THAT SEPARATES THEM NOW. `tests/fixtures/custody/failures/unstamped/` is an overlay on `job-rejected`
# (the convention in `failures/README.md`: copy `job-rejected`, copy the overlay's files over it, expect a REFUSAL).
# It carries exactly two content changes, both of which an emitter can READ:
#
#   1. `inputs/custody.json` — `passes.pass-a` has NO `at` key at all. (Not a different value: the typed time is absent.)
#   2. `custody/evidence/harness-eval-a.log` — all three evaluator calls carry NO `response_headers.Date` and NO
#      `received_at`/`sent_at`. The only instant left in the log is each `response.created` epoch.
#
# `kit/custody_history.Call` computes `at = received_at or Date header or created`. With no `received_at` and no
# `Date`, `at` falls to `created` — an epoch the emitter cannot present as a logger-stamped time — and
# `hand_time_entries()` lists BOTH `.sent_at` and `.received_at` for each of the three calls. That is the defect the
# law names: a machine's check time the logger never stamped. It is a fact about the FIXTURE'S CONTENT, and the
# shared fixture has neither property — so the one-line separation is:
#
#     b1's fixture carries NO logger-stamped instant for its evaluator calls (no Date header, no sent_at/received_at)
#     and no typed pass time; a3/a4/T3/E2's fixture carries a Date header on every call and a typed pass time.
#
# A fix keyed on that content (every evaluator call must carry a logger stamp, or the record is refused) leaves
# a3/a4/T3/E2 green and turns b1/c1/d1 red-then-green. A fix keyed on a PATH NAME would not, which is why nothing
# below asserts a path name as the reason for a refusal.
#
# A2 / B CONTROLS (the guard that the refusal is b1's fixture and not the switch being broken):
#   A2 — `job-rejected` UNTOUCHED, switch ON, must still WRITE (exit 0). If a "fix" refuses every job under the
#        switch, A2 goes red.
#   B  — `failures/hand-times` OVERLAY, switch ON, must still REFUSE for its OWN content defect (times typed
#        minutes off the log). The switch admits a hand time; it does not admit a contradiction.
#
# WHAT THE RE-CUT BAR RECORDS (measured by the Architect on the re-cut tree, EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts):
#   * `job-rejected`, switch ON: exit 0, writes, and BOTH checks carry `at_source` == `harness-eval-a.log:37` —
#     one Date header (eval_artifact's) for two different evaluator calls. That collision is why d1 is RED below
#     and is not the b1 defect; it is a SECOND, independent defect this bar also refuses to allow.
#   * `failures/unstamped`, switch ON: exit 0, WRITES, and the record's checks are sourced at
#     `harness-eval-a.log:18` (eval_artifact's `response.created`) with `at_basis` "response created", while
#     `hand_times[]` lists `....sent_at` AND `....received_at` for all three calls. That is b1's red: the record
#     asserts a check time the logger never stamped, and the switch is claimed to authorise it.
#
# THE AUTHORSHIP RULE. The four regression cases (a1-a4) are GREEN at 31ffb42 and must stay green — they are the
# behaviours that work. b1/c1/d1 are RED at 31ffb42 and every red is recorded with its assertion quoted. A2 and B
# are GREEN at 31ffb42, and a case green before the fix is a CONTROL, not evidence: it is labelled as such in the
# report and does not count as measurement of the new behaviour.

JOB25_NEW: list[tuple[str, bool]] = []      # every case added by this bar, with its outcome, for the report


def hl_case(name, ok, why=""):
    """A job-25 case: recorded in `results` like every other, and in JOB25_NEW so the report can say which of its
    cases are new and what each measured."""
    JOB25_NEW.append((name, ok))
    results.append((f"{S} · JOB25 {name}", ok, "" if ok else " ".join(str(why).split())[:200]))
    return ok


def _eval_log_ids(tree: Path) -> list[str]:
    """The call ids the fixture's evaluator log actually carries, read from the log (not from this file), so the
    bar names the calls the log names rather than a list hand-copied into the test."""
    p = tree / "tests" / "fixtures" / "custody" / "job-rejected" / "custody" / "evidence" / "harness-eval-a.log"
    doc = json.loads(p.read_text(encoding="utf-8"))
    items = doc if isinstance(doc, list) else [doc]
    return [c["call"] for c in items if isinstance(c, dict) and c.get("call")]


def _overlay_log_ids(overlay: str) -> list[str]:
    """The call ids the OVERLAY's evaluator log carries — read from the overlay's own bytes on disk."""
    p = FIX.parent / "failures" / overlay / "custody" / "evidence" / "harness-eval-a.log"
    doc = json.loads(p.read_text(encoding="utf-8"))
    items = doc if isinstance(doc, list) else [doc]
    return [c["call"] for c in items if isinstance(c, dict) and c.get("call")]


def _unstamped_properties(job: Path) -> dict:
    """What the b1 fixture IS, read from its bytes. Used to prove the overlay's two content changes are present, so a
    bar that goes green against a stale overlay cannot pass silently."""
    ci = json.loads((job / "inputs" / "custody.json").read_text(encoding="utf-8"))
    log = json.loads((job / "custody" / "evidence" / "harness-eval-a.log").read_text(encoding="utf-8"))
    calls = log if isinstance(log, list) else [log]
    return {
        "pass_at_absent": "at" not in ((ci.get("passes") or {}).get("pass-a") or {}),
        "calls": len([c for c in calls if isinstance(c, dict) and c.get("call")]),
        "calls_with_date": sum(1 for c in calls
                               if isinstance(c, dict) and (c.get("response_headers") or {}).get("Date")),
        "calls_with_logger_stamp": sum(1 for c in calls
                                       if isinstance(c, dict) and (c.get("sent_at") or c.get("received_at"))),
    }


# ---- (a) THE REGRESSION SET: the four main-green behaviours. These are GREEN at 31ffb42 and must stay green. ----
# They are written against the SAME emitter the new cases drive, so if the fix breaks a behaviour PR 24 restored, one
# of these goes red. Their assertions are the ones the existing suite uses (lines 761, 939-981, 786-792), restated
# here so this section is a bar by itself and does not lean on the section above staying put.
#
# THE GUARD MEANS THE BASE FIXTURE IS UNCHANGED. a4 below runs on a COPY of `job-rejected` with a typed pass time
# edited in that copy (as before). a3 runs on `FIX` itself. Neither may be moved onto the unstamped overlay: moving
# them would weaken the guard on existing main-green behaviour to make the new case pass (Owner ruling, rejected).

# (a1) the 59 s sub-line: a typed startedAt 59 s off the log is ACCEPTED and the record carries the LOG's time.
j = job_copy("job25-59s")
_cj = json.loads((j / "inputs" / "custody.json").read_text(encoding="utf-8"))
_cj["startedAt"] = "2026-10-20T10:59:03Z"        # the maker log's first call is at 11:00:00Z: 57 s early, inside ±60
_cj["producedAt"] = "2026-10-20T11:00:17Z"       # the last call is at 11:00:07Z: 10 s late, inside ±60
(j / "inputs" / "custody.json").write_text(json.dumps(_cj, indent=2) + "\n", encoding="utf-8")
_o = TMP / "job25-59s.json"
_rc, _out = emit(j, _o, allow_hand=True)
_pred = json.loads(_o.read_text(encoding="utf-8"))["predicate"] if _o.is_file() else {}
hl_case("a1 a hand time 59 s off is accepted, and the record carries the LOG's time",
        _rc == 0 and _pred.get("startedAt") == "2026-10-20T11:00:00Z",
        f"exit {_rc}; startedAt {_pred.get('startedAt')!r}: {_out.strip()[-160:]}")

# (a2) T2c: a time typed into custody.json with no ledger line is NAMED (disposition.at, its source).
j = job_copy("job25-t2c")
_o = TMP / "job25-t2c.json"
_rc, _out = emit(j, _o, allow_hand=False)
hl_case("a2 T2c a time typed into custody.json with no ledger line is named (disposition.at, its source)",
        _rc == 3 and "disposition.at" in _out and ("inputs-no-ledger" in _out or "ledger-no-writer" in _out)
        and not _o.exists(), f"exit {_rc}: {_out.strip()[-160:]}")

# (a3) T3: with --allow-hand-times the record is written and hand_times lists the hand fields with file:line.
# This is the half of the pair b1 was unsatisfiable against: SAME fixture bytes, SAME switch, must WRITE.
_o = TMP / "job25-t3.json"
_rc, _out = emit(FIX, _o, allow_hand=True)
_ht = (((json.loads(_o.read_text(encoding="utf-8"))["predicate"]["x-plumbline"]).get("hand_times"))
       if _o.is_file() else []) or []
_by_field = {e.get("field"): e for e in _ht}
hl_case("a3 T3 with --allow-hand-times the record is written and hand_times lists the hand fields with file:line",
        _rc == 0 and "disposition.at" in _by_field and _by_field["disposition.at"].get("line") is not None
        and len(_ht) >= 1 and all(e.get("file") and e.get("line") is not None for e in _ht),
        f"exit {_rc}: {_out.strip()[-160:]}")

# (a4) E2: under --allow-hand-times the typed pass time is LISTED and the record carries the CALL's time.
# The call is `eval_artifact`, so "the call's time" is its Date header, 2026-10-20T12:00:03Z (NOT `created`, 12:00:02Z).
# The typed value is deliberately 12:00:02Z — the SAME instant as the log's `created` — because that is the value the
# first cut could not tell from b1 by content. Here it only proves the typed value is overridden by the LOG's Date.
j = job_copy("job25-e2")
_c = json.loads((j / "inputs" / "custody.json").read_text(encoding="utf-8"))
_c["passes"]["pass-a"]["at"] = "2026-10-20T12:00:02Z"    # the typed value; the record must carry the LOG's instead
(j / "inputs" / "custody.json").write_text(json.dumps(_c, indent=2) + "\n", encoding="utf-8")
_o = TMP / "job25-e2.json"
_rc, _out = emit(j, _o, allow_hand=True)
_doc = json.loads(_o.read_text(encoding="utf-8"))["predicate"] if _o.is_file() else {}
_ht_e2 = {e.get("field"): e for e in (_doc.get("x-plumbline") or {}).get("hand_times") or []}
_checks_e2 = _doc.get("checks") or []
hl_case("a4 E2 under --allow-hand-times the typed pass time is listed and the record carries the call's time",
        _rc == 0 and (_ht_e2.get("passes.pass-a.at") or {}).get("source") == "inputs-no-ledger"
        and bool(_checks_e2) and _checks_e2[0].get("at") == "2026-10-20T12:00:03Z",
        f"exit {_rc}; check at {_checks_e2[0].get('at') if _checks_e2 else None!r}: {_out.strip()[-160:]}")


# ---- THE FIXTURE GUARD: the overlay is what it says it is. Not a behaviour case; a premise case. If someone edits
#      `failures/unstamped` back into a stamped copy, every b1/c1/d1 below would pass vacuously against a fixture that
#      no longer carries the defect. This asserts the two content changes by reading the bytes on disk.
_b1_job = job_copy("job25-unstamped", "unstamped")
_p = _unstamped_properties(_b1_job)
hl_case("P1 the b1 fixture carries the defect by content: no typed pass time, no logger stamp on any evaluator call",
        _p["pass_at_absent"] and _p["calls"] > 0 and _p["calls_with_date"] == 0 and _p["calls_with_logger_stamp"] == 0,
        f"fixture properties: {_p}")

# The separation, asserted mechanically rather than asserted in a comment: the SHARED fixture differs on both
# properties, so b1 and a3/a4 are told apart by content and by nothing else.
_shared = _unstamped_properties(job_copy("job25-shared-props"))
hl_case("P2 the separation is content: job-rejected stamps a Date on every evaluator call and types a pass time",
        (not _shared["pass_at_absent"]) and _shared["calls_with_date"] == _shared["calls"] > 0,
        f"job-rejected properties: {_shared}")

_ids = _overlay_log_ids("unstamped")


# ---- (b) THE NEW BEHAVIOUR: an evaluator check time the logger never stamped is REFUSED, every call by id,
#          and the record is not written. RED at 31ffb42, measured: exit 0, a record written. ----
_o = TMP / "job25-unstamped.json"
_rc, _out = emit(_b1_job, _o, allow_hand=True)
hl_case("b1 a model evaluator check time the logger never stamped is REFUSED under --allow-hand-times",
        _rc == 3 and not _o.exists()
        and "harness-eval-a.log#eval_artifact" in _out,
        f"exit {_rc}; record written={_o.exists()}; refusal names eval_artifact="
        f"{'harness-eval-a.log#eval_artifact' in _out}: {_out.strip()[-200:]}")

# every call BY ID — not the first: each id the overlay's log carries must be named, and the count of named ids must
# equal the log's own count, so a fix that names only `eval_artifact`, or only one field, fails here.
_named = [cid for cid in _ids if f"harness-eval-a.log#{cid}" in _out]
hl_case("b2 ...and the refusal names every unstamped evaluator call by id, none left unnamed",
        bool(_ids) and len(_named) == len(_ids),
        f"log carries {_ids}; the refusal named {_named}: {_out.strip()[-260:]}")


# ---- (c) THE SWITCH BOUNDARY: the SAME switch, on two fixtures that differ by content, admits one and refuses the
#          other. Both halves are asserted in one case, so a fix that simply disables the switch (making both refuse)
#          fails on the admitted half, and a fix that simply allows everything fails on the refused half. ----
# The ADMITTED half: `job-rejected` untouched (a Date header on every call, a typed pass time) — must WRITE.
_a2_o = TMP / "job25-a2.json"
_a2_rc, _a2_out = emit(job_copy("job25-a2"), _a2_o, allow_hand=True)
typed_admitted = (_a2_rc == 0 and _a2_o.is_file())
# The REFUSED half: the overlay (no Date header, no typed pass time) — must REFUSE, naming the calls.
unstamped_refused = (_rc == 3) and any(f"harness-eval-a.log#{cid}" in _out for cid in _ids)
hl_case("c1 the boundary: --allow-hand-times admits a stamped fixture and refuses one with no logger-stamped time",
        typed_admitted and unstamped_refused,
        f"stamped fixture admitted={typed_admitted} (exit {_a2_rc}); unstamped refused={unstamped_refused} "
        f"(exit {_rc}): {_out.strip()[-220:]}")


# ---- (d) NO HOLLOW OR MIS-SOURCED RECORD. At 5c3f72d/0f85ddb the switch on wrote a record whose startedAt,
#          producedAt, six evaluator stamps and passes.pass-a.at were sourced from nowhere. At 31ffb42 the shared
#          fixture's record is mis-sourced instead: both checks carry `harness-eval-a.log:37`, one Date header for
#          two different evaluator calls.
# This case drives the SWITCH-ON emit on the SHARED fixture and requires, for any record that is written, that each
# check carrying a `call` carries its OWN `at_source` and that no two checks share one. A fix that refuses the
# shared fixture entirely is caught by a3/a4/A2, not here. RED at 31ffb42 (a record IS written and the sources
# collide) and GREEN after a fix that gives each check its own call's source.
_o = TMP / "job25-sources.json"
_rc, _out = emit(job_copy("job25-sources"), _o, allow_hand=True)
_srcs: list = []
if _o.is_file():
    _p = json.loads(_o.read_text(encoding="utf-8"))["predicate"]
    _srcs = [((c.get("x-plumbline") or {}).get("at_source")) for c in _p.get("checks") or []
             if (c.get("x-plumbline") or {}).get("call")]
_srcs_str = [s for s in _srcs if isinstance(s, str) and s]
_no_source = [i for i, s in enumerate(_srcs) if not s]
_shared_src = sorted({s for s in _srcs_str if _srcs_str.count(s) > 1})
hl_case("d1 any record written under the switch gives every called check its OWN at_source (no collision, none blank)",
        _rc == 0 and bool(_srcs) and not _no_source and not _shared_src,
        f"exit {_rc}; called checks: {_srcs}; without a source: {_no_source}; shared: {_shared_src}")


# ---- B: THE CONTROL WITH A DEFECT. `failures/hand-times` under the SAME switch must still REFUSE for its own
#          content (times typed minutes off the log), so the switch is not silently admitting everything. GREEN at
#          31ffb42 — a control, not measurement of the new behaviour. ----
_b_o = TMP / "job25-b.json"
_b_rc, _b_out = emit(job_copy("job25-hand-times", "hand-times"), _b_o, allow_hand=True)
hl_case("B control: the hand-times overlay still refuses for its own content defect under the switch (exit 3)",
        _b_rc == 3 and "[time]" in _b_out and not _b_o.exists(),
        f"exit {_b_rc}: {_b_out.strip()[-200:]}")


shutil.rmtree(TMP, ignore_errors=True)

# ---------------------------------------------------------------- report

# The case set, as data, so a later reader can diff the set against a baseline commit without parsing the report
# (the bar's requirement (d): a case-set diff against main db9d6b7). Written only when asked, and it is not a case:
# it writes the names and their outcomes, and changes nothing this suite checks.
if os.environ.get("PLUMBLINE_CASE_SET_OUT"):
    Path(os.environ["PLUMBLINE_CASE_SET_OUT"]).write_text(
        "".join(f"{name}\n" for name, _, _ in results), encoding="utf-8")

print()
width = max(len(n) for n, _, _ in results)
for name, ok, why in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<{width}} {why}")
failed = [n for n, ok, _ in results if not ok]
print()
if failed:
    print(f"{len(results) - len(failed)}/{len(results)} PASSED — {len(failed)} FAILED:")
    for n in failed:
        print(f"  - {n}")
    sys.exit(1)
print(f"ALL {len(results)} CASES BEHAVED AS DESIGNED")
