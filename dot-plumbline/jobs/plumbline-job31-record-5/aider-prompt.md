# JOB 31 — make `tests/validate_audit.py` measure the tree it is run in

## What is being asked

`tests/validate_audit.py` must resolve the root it searches for audit records from the
repository it is itself run in, instead of from the parent directory of that repository.
`$PLUMBLINE_AUDIT_ROOT`, when it is set, must still name the root explicitly and win.

## The spec is the failing tests

`tests/test_validate_audit_root.py` is the specification. It is frozen. Do not edit it, do
not weaken it, do not add skips, do not change the test command. Read it in full before
editing anything — its module docstring states the defect, the ratified option C, and why
each assertion is on the *naming* of a record rather than on an exit code.

The red, as measured in the work tree right now:

    $ python3 tests/test_validate_audit_root.py
    ...FF...
    FAIL: test_1_the_base_names_the_neighbour_and_the_work_tree_does_not
      AssertionError: ('neighbour', '2026-12-01-fixture.json') unexpectedly found in
      [('neighbour', '2026-12-01-fixture.json')] : the work tree's suite named the
      neighbour's record as checked by a checkout that does not contain it; it read a
      sibling tree as this one. named=[('neighbour', '2026-12-01-fixture.json')] rc=0

    FAIL: test_2_the_c_case_exits_zero_and_states_it_read_nothing
      AssertionError: ('neighbour', '2026-12-01-fixture.json') unexpectedly found in
      [('neighbour', '2026-12-01-fixture.json')] : the C case: with no override the
      neighbour's record must not be named as checked.

    Ran 8 tests in 3.057s
    FAILED (failures=2)

All eight tests must pass, and the six that pass today must keep passing. In particular
these guards are part of what you must not break:

- `test_0c` — a record under an explicit `$PLUMBLINE_AUDIT_ROOT` must still be discovered
  and named, and exit 0.
- `test_3` — an explicit empty `$PLUMBLINE_AUDIT_ROOT` must exit 0 and name no record.
- `test_4` — a checkout carrying its own `dot-plumbline/audits/` with one record must still
  check it, list it in the `<home> N record(s)` census, and report
  `checked 1 record(s) from 1 home(s)`. The fix must not silence the suite into reading
  nothing anywhere.
- `test_5` — a run with no `EDI_CORPUS` in the environment must still print `SKIP[corpus]`,
  a bogus `EDI_CORPUS` must still be refused with exit 2 and the offending value named, and
  a caller-planted root must not be reached. Do not touch the corpus resolution.

## Constraints

- **Editable set: `tests/validate_audit.py` only.** Nothing else. No file under `schemas/`,
  no `tools/`, no other test file, no packet, no re-pin.
- **Do-not-edit (frozen):** `schemas/job-packet.schema.json`,
  `schemas/evaluator-record.schema.json`, `schemas/audit-record.schema.json`,
  `schemas/compliance-checklist.json`, `schemas/custody-record.schema.json`,
  `tools/pin.json`, `tools/build_schemas.py`, `tools/edi_corpus.py`,
  `tests/validate_schemas.py`, `tests/validate_constitution.py`,
  `tests/validate_pin_prose.py`, `tests/run_all.py`, `tests/test_conductor_loop.py`,
  `tests/test_validate_audit_root.py`.
- Do not change the grading logic beyond how the suite resolves its own root. The checks the
  suite performs, the messages it prints for records it *does* check, and its exit codes for
  those cases stay as they are.
- The module docstring at `tests/validate_audit.py:14` states the intended behaviour
  ("The search root is the directory holding this checkout, or $PLUMBLINE_AUDIT_ROOT"). Keep
  the docstring and the code in agreement; if the resolved behaviour is better described by
  a different sentence, edit that sentence in this same file, and nothing else.
- The suite must stay runnable as `python3 tests/validate_audit.py` from the repository
  root, with no arguments and no environment variables.

## How the attempt will be measured

The dispatch's test command is run in this work tree:

    python3 tests/test_validate_audit_root.py

The attempt is done when that command exits 0 with all eight tests passing, and the only
file changed by this attempt is `tests/validate_audit.py`.
