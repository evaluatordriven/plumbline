#!/usr/bin/env python3
"""Self-consistency: an audit is a §5 evaluator run, so the audit records must satisfy §5 —
and Plumbline's own output must be checkable by the same algebra it enforces.

WHERE RECORDS LIVE (this changed on 2026-09-29 — see dot-plumbline/README.md)
    A record travels with the artifact (Contracts §10.1), so records are NOT centralised here.
    They are discovered under the convention: every repo may carry

        <repo>/dot-plumbline/audits/*.json

    That means: wsww's audits live in wsww's repo, Plumbline's audits of itself live in this repo's
    dot-plumbline/audits/, and a program with no local checkout keeps its records in its Drive
    project folder — which this script cannot read, so it says so rather than passing silently.
    By default this script searches only THIS checkout's own dot-plumbline/audits/, so a sibling
    checkout that happens to sit beside it is never read as this tree's; $PLUMBLINE_AUDIT_ROOT
    names an explicit root whose immediate subdirectories are searched as checkouts.

Four things are asserted, and each one can fail:

  1. GENERATION MAP. A filed record is judged against the schema generation in force on the day it
     was filed. A record keeps the vocabulary it was written in (Contracts §12).
  2. THE ALGEBRA IS RECOMPUTED, never trusted: every verdict re-derived from §3's pass rule.
  3. THE LIVE SCHEMAS ARE THE CORPUS'S — the derived record schema must still be the corpus §5 shape.
     It is checked against the VENDORED corpus schema (schemas/vendor/e-di@<pin8>/), so it runs with no
     corpus. With a corpus (EDI_CORPUS), corpus.audit-equality also checks that the vendored schema is still
     the corpus's bytes; with none it prints SKIP[corpus] (FAIL[corpus] and exit 1 under
     PLUMBLINE_REQUIRE_CORPUS=1) and the rest of the checks still run.
  4. COVERAGE IS STATED. How many records were checked, from which homes, and which programs were
     NOT checked and why. A validator that silently checks nothing is worse than none.

Usage:  python3 tests/validate_audit.py      (EDI_CORPUS=<e-di checkout> adds corpus.audit-equality)
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

REPO = Path(__file__).resolve().parent.parent
SHIP = REPO / "schemas"
LEGACY = SHIP / "legacy"
PIN = json.loads((REPO / "tools" / "pin.json").read_text(encoding="utf-8"))
# With no override this checkout measures ITSELF (REPO/dot-plumbline/audits/), never REPO.parent, so a
# sibling that ships its own census is not read as this tree's. An explicit $PLUMBLINE_AUDIT_ROOT names a
# directory whose immediate children are searched as checkouts (<root>/*/dot-plumbline/audits).
_AUDIT_ROOT_OVERRIDE = os.environ.get("PLUMBLINE_AUDIT_ROOT")
DEVSPACE = Path(_AUDIT_ROOT_OVERRIDE).expanduser() if _AUDIT_ROOT_OVERRIDE else REPO

GENERATIONS = [
    ("2026-09-20", LEGACY, "pre-observation vocabulary (evidence/evidence_channel, needs_human)"),
    ("2026-09-29", LEGACY / "plumbline-s8-2026-09", "Plumbline §8 extension, pre-doctrine-alignment"),
    ("9999-12-31", SHIP, "derived from the corpus pin (corpus §5 shape; audit fields in instance_extensions)"),
]

# Programs whose records live outside any local checkout. Named, so the gap is visible instead of
# being counted as "nothing to check".
DRIVE_ONLY = {
    "eddie": "records kept in the program's project folder, not in a local checkout",
}


def generation_for(name: str):
    date = name[:10]
    for upper, path, note in GENERATIONS:
        if date < upper:
            return path, note
    return SHIP, GENERATIONS[-1][2]


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


fails = 0
checked = 0
unchecked: list[tuple[str, str]] = []

# --- 3. the live derived record schema still carries the corpus §5 requiredness ----
# Check 3 reads the VENDORED corpus schema, so it needs no corpus. The corpus itself is resolved at run time
# through the shared D-E resolver (tools/edi_corpus.py); a set EDI_CORPUS that is not a corpus exits 2 naming it.
sys.path.insert(0, str(REPO / "tools"))
import edi_corpus  # noqa: E402

_resolved, _required = edi_corpus.resolve_or_exit(None, ("schemas/evaluator-record.schema.json",), hermes=False)
_vendored_record = SHIP / "vendor" / f"e-di@{PIN['commit'][:8]}" / "evaluator-record.schema.json"
corpus_schema = load(_vendored_record)
if _resolved:
    _same = (_resolved.path / "schemas" / "evaluator-record.schema.json").read_bytes() == _vendored_record.read_bytes()
    print(f"[{'ok' if _same else 'FAIL'}] vendored evaluator-record.schema.json is the corpus's bytes "
          f"({_resolved.path}@schemas/evaluator-record.schema.json)")
    if not _same:
        fails += 1
    edi_corpus.ran("corpus.audit-equality", _same)
elif edi_corpus.not_run("corpus.audit-equality", _required, edi_corpus.NO_CORPUS_ENV):
    fails += 1
live_record = load(SHIP / "evaluator-record.schema.json")
live_audit = load(SHIP / "audit-record.schema.json")
Draft202012Validator.check_schema(live_audit)
print("[ok] audit-record.schema.json (derived) is a valid draft 2020-12 schema")

for label, cond in (
    ("live record schema requires exactly the corpus's §5 fields",
     set(corpus_schema["required"]) == set(live_record["required"])),
    ("live record schema is closed (additionalProperties: false), like the corpus's",
     live_record.get("additionalProperties") is False and corpus_schema.get("additionalProperties") is False),
):
    print(f"[{'ok' if cond else 'FAIL'}] {label}")
    if not cond:
        fails += 1
ext_req = [c for c in live_audit.get("allOf", []) if "instance_extensions" in json.dumps(c)]
print(f"[ok] audit schema requires {len(ext_req)} named instance_extensions entries")

# --- discover records under the convention ------------------------------------------
# No override: only this checkout's own dot-plumbline/audits/ is searched. Override: the immediate
# children of the named root are searched as checkouts.
if _AUDIT_ROOT_OVERRIDE:
    homes = [p for p in sorted(DEVSPACE.glob("*/dot-plumbline/audits")) if p.is_dir()]
    scope = f"{DEVSPACE}/*/dot-plumbline/audits/"
else:
    own = REPO / "dot-plumbline" / "audits"
    homes = [own] if own.is_dir() else []
    scope = f"{REPO}/dot-plumbline/audits/"
records = [(home.parent.parent.name, f) for home in homes for f in sorted(home.glob("*.json"))]

print(f"\nhomes discovered under {scope} :")
for home in homes:
    n = len(list(home.glob('*.json')))
    print(f"  {home.parent.parent.name:<24} {n} record(s)")
for name, why in DRIVE_ONLY.items():
    unchecked.append((name, why))

if not records:
    if not (REPO / "dot-plumbline" / "audits").is_dir():
        # The public repository ships no audit records of its own (they stay in the private evidence archive),
        # so there is nothing in reach to validate. Say so by name rather than pass silently; the schema checks
        # above still ran. A checkout that HAS a dot-plumbline/audits/ and finds no records still fails below.
        print("\nNO AUDIT RECORDS IN REACH — this checkout ships no dot-plumbline/audits/ and none was found under "
              f"{DEVSPACE}; only the schema checks above ran.")
        for name, why in unchecked:
            print(f"  unchecked: {name} — {why}")
        sys.exit(1 if fails else 0)
    print("\nNO RECORDS FOUND — nothing was validated. This is a coverage failure, not a pass.")
    for name, why in unchecked:
        print(f"  unchecked: {name} — {why}")
    sys.exit(1)

for program, path in records:
    rec = load(path)
    schema_dir, note = generation_for(path.name)
    audit = Draft202012Validator(load(schema_dir / "audit-record.schema.json"))
    strict = Draft202012Validator(load(schema_dir / "evaluator-record.schema.json"))
    audit_s, strict_s = load(schema_dir / "audit-record.schema.json"), load(schema_dir / "evaluator-record.schema.json")
    checked += 1

    print(f"\n--- {program}/{path.name} ---")
    print(f"  generation: {schema_dir.relative_to(REPO)}  ({note})")

    # --- READINGS RECORDS: §5's schema does not describe this form -----------------------
    # §5's record schema is titled "(scored)" and requires score:number per dimension; C29's
    # readings form requires NEVER numbers. So a readings record is NOT validated against §5 —
    # that would be checking it against a law that does not govern it. It is checked against
    # what the readings form actually promises, and every claim is recomputed from the pass
    # files rather than trusted from the record's own summary. A census whose passes cannot be
    # re-derived is unverifiable, and unverifiable is reported, not passed.
    if rec.get("record_kind") == "readings":
        job_dir = REPO / "dot-plumbline" / "jobs" / rec.get("job_id", "")
        pass_files = sorted(job_dir.glob("pass-*.json"))
        print("  kind: readings — §5 describes the scored form only; checked against the readings form")
        print(f"  declared exit: {rec.get('recommended_exit')} · passes declared: {rec.get('passes')}")
        if not pass_files:
            fails += 1
            print("     *** NO PASS FILES — passes cannot be re-derived, so the census is UNVERIFIED ***")
            continue
        per_pass = {}
        for pf in pass_files:
            pd = json.loads(pf.read_text())
            per_pass[pf.name] = {r["clause"]: r["reading"] for r in pd["readings"]}
        ids = sorted({c for p in per_pass.values() for c in p})
        legal = {"conforms", "does_not_conform", "unobserved"}
        for name, p in per_pass.items():
            miss = [c for c in ids if c not in p]
            if miss:
                fails += 1
                print(f"     *** {name} does not cover every clause — missing {miss} ***")
            bad = {c: v for c, v in p.items() if v not in legal}
            if bad:
                fails += 1
                print(f"     *** {name} carries illegal readings: {bad} ***")
        derived_nc, derived_flap = [], []
        for c in ids:
            vals = {per_pass[n][c] for n in per_pass if c in per_pass[n]}
            if len(vals) == 1:
                if vals == {"does_not_conform"}:
                    derived_nc.append(c)
            else:
                derived_flap.append(c)
        print(f"  recomputed from {len(pass_files)} pass file(s): {len(derived_nc)} stable "
              f"non-conformance(s) {derived_nc}, {len(derived_flap)} flapped")
        s = rec.get("summary", {})
        if sorted(s.get("stable_non_conformances", [])) != sorted(derived_nc):
            fails += 1
            print(f"     *** SUMMARY MISMATCH: declared {s.get('stable_non_conformances')} vs "
                  f"recomputed {derived_nc} ***")
        else:
            print("  declared summary matches the pass files")
        if sorted(s.get("flapped_clauses", [])) != sorted(derived_flap):
            fails += 1
            print(f"     *** FLAP MISMATCH: declared {s.get('flapped_clauses')} vs recomputed "
                  f"{derived_flap} ***")
        overlap = set(s.get("stable_non_conformances", [])) & set(s.get("flapped_clauses", []))
        if overlap:
            fails += 1
            print(f"     *** a clause is reported as BOTH a finding and flapping: {sorted(overlap)} ***")
        if re.search(r'"score"\s*:', json.dumps(rec)):
            fails += 1
            print("     *** a `score` field is present — C29 forbids numbers in the readings form ***")
        inst = rec.get("instrument", {})
        if not inst.get("runner_identical_across_passes"):
            fails += 1
            print("     *** the runner differed across passes — same rubric, different runner is a "
                  "different instrument (C30) ***")
        if not inst.get("rubric_identical_across_passes"):
            fails += 1
            print("     *** the rubric differed across passes (C30) ***")
        continue

    e_strict = list(strict.iter_errors(rec))
    audit_only = set(audit_s.get("properties", {})) - set(strict_s.get("properties", {}))
    extra, genuine = set(), []
    for e in e_strict:
        if e.validator == "additionalProperties":
            found = set(re.findall(r"'([^']+)'", e.message))
            if found and found <= audit_only:
                extra |= found
                continue
        genuine.append(e)
    print(f"  vs §5 evaluator-record (strict): {'valid' if not e_strict else f'{len(e_strict)} error(s)'}")
    if extra:
        print(f"     expected: audit-only fields {', '.join(sorted(extra))} -> this is WHY the extension exists")
    for e in genuine:
        fails += 1
        print(f"     GENUINE §5 BREAK -> {'/'.join(str(p) for p in e.path) or '<root>'}: {e.message[:140]}")

    e_audit = list(audit.iter_errors(rec))
    print(f"  vs audit-record (that generation): {'valid' if not e_audit else 'INVALID'}")
    for e in e_audit[:6]:
        fails += 1
        print(f"     -> {'/'.join(str(p) for p in e.path) or '<root>'}: {e.message[:150]}")

    # --- 2. recompute the verdict from §3, never trust the declared one -------------
    dims = [d["score"] for d in rec["dimensions"]]
    pr = rec["pass_rule"]
    mean, mn = sum(dims) / len(dims), min(dims)
    if rec.get("unjudged_dimensions"):
        derived = "needs_owner"
    elif mean >= pr["accept"] and mn >= pr["dimension_floor"]:
        derived = "accept"
    elif mn < pr["reject"]:
        derived = "reject"
    elif rec["iteration"] >= pr["cap"]:
        derived = "needs_owner"
    else:
        derived = "regenerate"
    legacy_names = path.name < "2026-09-20"
    against = derived.replace("needs_owner", "needs_human") if legacy_names else derived
    print(f"  recomputed: mean={mean:.2f} min={mn} -> {derived}")
    print(f"  declared:   {rec['verdict']}" + ("   (filed before the 2026-09-20 rename; compared as needs_human)" if legacy_names else ""))
    if not against.startswith(rec["verdict"]):
        fails += 1
        print("  *** VERDICT MISMATCH ***")

# --- 4. coverage is stated -----------------------------------------------------------
print(f"\n--- coverage ---")
print(f"  checked {checked} record(s) from {len(homes)} home(s)")
for name, why in unchecked:
    print(f"  NOT CHECKED: {name} — {why}")
print("  Plumbline's own dot-plumbline/audits/ holds the 2026-09-29 census — the first job to audit Plumbline itself.")
print(f"\n{'ALL AUDIT RECORDS CONSISTENT' if fails == 0 else f'{fails} PROBLEM(S)'}")
sys.exit(1 if fails else 0)
