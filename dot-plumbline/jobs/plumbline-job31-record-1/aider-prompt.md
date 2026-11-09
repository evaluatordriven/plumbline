# JOB 31 — tests/validate_audit.py must resolve its audit root from the repo it is run in

## The bar is the spec

`tests/test_validate_audit_root.py` is the specification. Do not edit it. Do not edit
anything except `tests/validate_audit.py`.

Read the bar's module docstring first: it states each of the four checks and, for each,
what is measured and whether the base is RED or GREEN on it. Read every assertion body.
The assertions are the whole of the requirement; there is no other requirement.

## The defect at the base

`tests/validate_audit.py` line 46:

    DEVSPACE = Path(os.environ.get("PLUMBLINE_AUDIT_ROOT") or REPO.parent).expanduser()

and line 113:

    homes = [p for p in sorted(DEVSPACE.glob("*/dot-plumbline/audits")) if p.is_dir()]

With `PLUMBLINE_AUDIT_ROOT` unset, the suite globs `<parent>/*/dot-plumbline/audits`, so a
checkout that ships no `dot-plumbline/audits/` of its own reads a SIBLING checkout's census
and reports it as this tree's. The exit code does not reveal it: a mis-measured run and a
correct run both exit 0 and both print a clean summary. The measurement is *which record is
named as checked* — the `--- <home>/<file> ---` headers and the `<home> N record(s)` census
lines.

## What the bar requires

Four checks, verbatim from the bar. Run them with `python3 tests/test_validate_audit_root.py`.

1. `test_1_neighbour_beside_a_census_is_not_read_as_this_tree` — a subject with no
   `dot-plumbline/audits/` of its own, sitting beside a neighbour that has one schema-valid
   record. With the override unset, the neighbour's record is NOT named as checked, the
   neighbour's census is NOT listed, and no record is reported as checked.
2. `test_2_implied_empty_root_reads_as_an_explicit_empty_root_does` — the same subject, no
   override: the neighbour's record is not named, and the exit code is exactly what an
   explicit empty root gives (0).
3. `test_3_the_override_still_works` — `PLUMBLINE_AUDIT_ROOT=<empty dir>` is still honoured:
   exit 0, no record named, and no fall-through to the neighbour.
4. `test_4_a_clean_parent_with_its_own_record_still_checks_it` — a subject carrying its own
   `dot-plumbline/audits/` with one schema-valid record, in a parent with no other checkout:
   exit 0, `subject 1 record(s)` listed, the subject's own record named, and the coverage
   line states `checked 1 record(s) from 1 home(s)`.

Checks 3 and 4 are GREEN at the base. They are guards: a fix that deletes the override, or
that silences the suite into reading nothing everywhere, fails them. All four must pass.

## Scope

Editable: `tests/validate_audit.py` and nothing else.

Frozen — do not edit, do not "fix" the bar to match the code:

    schemas/job-packet.schema.json
    schemas/evaluator-record.schema.json
    schemas/audit-record.schema.json
    schemas/compliance-checklist.json
    schemas/custody-record.schema.json
    tools/pin.json
    tools/build_schemas.py
    tools/edi_corpus.py
    tests/validate_schemas.py
    tests/validate_constitution.py
    tests/validate_pin_prose.py
    tests/run_all.py
    tests/test_conductor_loop.py
    tests/test_validate_audit_root.py

Not allowed by the packet: a refactor of the audit runner; any change outside
`tests/validate_audit.py`; a re-pin; anything under `schemas/`; any change to
`tests/validate_audit.py`'s grading logic beyond resolving its own root.

## Known constraint in this work tree — read before you start

The bar's fixture builder shells out to `git archive 6793e53ddc5071aa252be10f2c0fc18c5a5b0b35`
(`BASE` at line 78; the call at line 118). That object is NOT in this repo's object store.
Measured here: `git cat-file -t 6793e53…` → `fatal: could not get object info`,
`git archive 6793e53…` → `fatal: not a tree object`, and `git rev-list --all | grep ^6793e53`
returns nothing. The base tree was imported as `9d47fbf` (`base: pin 6793e53 as an archive`),
whose `tests/validate_audit.py` is byte-identical to the one in this work tree.

So at present all four tests ERROR inside `_archive_subject` before any assertion is
reached. That is a fault in how the bar builds its fixture in this tree, not a fault the
editable file can repair, and repairing it would mean editing the frozen bar — which is out
of scope and which you must not do.

Therefore: make the change `tests/validate_audit.py` needs in order to pass all four checks,
and verify it by the same measurement the bar makes, without depending on that git invocation.
A faithful equivalent of the bar's subject is a copy of this work tree's source (excluding
`dot-plumbline/audits/`, which the subject must not ship) placed in a fresh parent directory
beside a `neighbour/dot-plumbline/audits/` holding one schema-valid record named
`2026-12-01-fixture.json`, then `python3 tests/validate_audit.py` run inside it with
`PLUMBLINE_AUDIT_ROOT` unset. Reproduce the base's failure that way first, then show your
change removes it while leaving checks 3 and 4 green.

Note the generation hazard the bar names (its docstring, `FIXTURE NAMING HAZARD`): only a
record whose filename date is on or after 2026-09-29 validates against the live schema. Use
`2026-12-01-fixture.json`.

## Deliverable

An edit to `tests/validate_audit.py` only, such that the audit root is resolved from the repo
the suite is run in, with `$PLUMBLINE_AUDIT_ROOT`, when set, still naming the root and
winning. Nothing else about the runner or its grading logic changes. The module docstring at
lines 2-29 describes the intended behaviour; if your change makes a line of it untrue, say so
in your reply rather than editing the bar.
