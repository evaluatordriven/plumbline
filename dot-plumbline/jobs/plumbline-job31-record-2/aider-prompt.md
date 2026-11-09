# Job 31 — tests/validate_audit.py resolves its audit root from the repo it runs in

## The failing tests are the spec

`tests/test_validate_audit_root.py` is the bar. Read it in full. It is frozen: do
not edit it, and do not edit any other file in the frozen set. Its four checks are
the specification; satisfy them and nothing else.

Run it with:

    python3 tests/test_validate_audit_root.py

Each check builds its own subject checkout and inspects **which records the suite
names as checked** — the `--- <home>/<file> ---` headers and the `<home> N record(s)`
census lines — as well as the exit code. Read the test method bodies and their
docstrings: they state, per case, what must be named and what must not, and what
exit code is expected.

## What the tests require, in the test's own terms

1. `test_1_neighbour_beside_a_census_is_not_read_as_this_tree` — a checkout that
   ships no `dot-plumbline/audits/` of its own, sitting beside a sibling directory
   that has one, must not name the sibling's record as checked, must not report the
   sibling's census as its own, and must not report checking any record.

2. `test_2_implied_empty_root_reads_as_an_explicit_empty_root_does` — with no
   override, the same subject must exit exactly as it does when handed an explicit
   empty root through `PLUMBLINE_AUDIT_ROOT`, and must not name the sibling's record.

3. `test_3_the_override_still_works` — `PLUMBLINE_AUDIT_ROOT=<empty dir>` must still
   be honoured: exit 0, no record named.

4. `test_4_a_clean_parent_with_its_own_record_still_checks_it` — a checkout carrying
   its own `dot-plumbline/audits/` with one record must still check it: the record is
   named, its home is listed, coverage states `(1, 1)`, exit 0.

## The one file you may change

    tests/validate_audit.py

Do not change anything else. Do not refactor the audit runner. Do not touch
`schemas/`, `tools/pin.json`, or any other test. Do not change the suite's grading
logic beyond how it resolves its own root.

## Constraint carried verbatim from the packet

The suite must measure the tree it is run in. `$PLUMBLINE_AUDIT_ROOT`, when set,
still names the root explicitly and wins. The module docstring at line 14 states the
contract the code must keep.

## Do not edit (frozen)

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
