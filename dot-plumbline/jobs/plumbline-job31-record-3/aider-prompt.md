# JOB 31 — make tests/validate_audit.py resolve its audit root from the repo it is run in

You are editing exactly one file: `tests/validate_audit.py`.

## BLOCKER — READ FIRST AND DO NOT WORK AROUND IT

This work tree cannot run the bar. Every test in `tests/test_validate_audit_root.py`
dies in `_archive_subject()` before any assertion:

    subprocess.CalledProcessError: Command '['git', 'archive',
    '6793e53ddc5071aa252be10f2c0fc18c5a5b0b35']' returned non-zero exit status 128.

That commit object is not in this repo (`git rev-list --all` is 3 commits, no remotes; the
base is present only as an imported snapshot at `9d47fbf`). The bar is FROZEN — do not edit
it. `tests/validate_audit.py` does not call `git archive`; the bar does. So no change you
can legally make will turn this bar green.

You are asked to make the edit the bar describes anyway, on the strength of the assertions
the bar will run once its fixture can build. If, on reading it, you conclude the edit is
still correct and confined, make it. Do not fabricate a passing run, do not add a
fallback SHA resolution, do not touch the bar, and do not create or modify any file other
than `tests/validate_audit.py`.

## THE SPEC — what the frozen bar asserts

`tests/test_validate_audit_root.py` is the spec and is FROZEN. Do not edit it. Its four
checks, over a subject checkout of the base with a schema-valid record named
`2026-12-01-fixture.json`:

1. **test_1_neighbour_beside_a_census_is_not_read_as_this_tree**
   Subject ships no `dot-plumbline/audits/`; a neighbour directory beside it does.
   With `PLUMBLINE_AUDIT_ROOT` unset: the neighbour's record must NOT appear in the
   `--- <home>/<file> ---` headers, the neighbour must NOT appear in the
   `<home> N record(s)` census lines, and if a `checked N record(s) from M home(s)` line is
   printed, N must be 0.

2. **test_2_implied_empty_root_reads_as_an_explicit_empty_root_does** (the C case)
   Same subject, no override: neighbour's record not named, and exit code exactly 0 —
   the same reading as an explicit empty root.

3. **test_3_the_override_still_works**
   `PLUMBLINE_AUDIT_ROOT=<empty dir>` is still honoured: exit 0, no record named.

4. **test_4_a_clean_parent_with_its_own_record_still_checks_it**
   Subject carries its own `dot-plumbline/audits/` with one record, parent has no other
   checkout: `("subject", "2026-12-01-fixture.json")` in the named records, `subject` in
   the named homes, coverage line is exactly `checked 1 record(s) from 1 home(s)`, exit 0.

## WHAT IS WRONG AT BASE

`tests/validate_audit.py:46`

    DEVSPACE = Path(os.environ.get("PLUMBLINE_AUDIT_ROOT") or REPO.parent).expanduser()

`tests/validate_audit.py:113`

    homes = [p for p in sorted(DEVSPACE.glob("*/dot-plumbline/audits")) if p.is_dir()]

With the override unset, `REPO.parent` is the directory *holding* the checkout, so line 113
globs `<parent>/*/dot-plumbline/audits` and reads a sibling checkout's census as this
tree's. The module docstring at line 14 already promises the corrected behaviour
("The search root is the directory holding this checkout, or $PLUMBLINE_AUDIT_ROOT.") but
the code does not keep it; the docstring's first half is itself part of the defect and may
be corrected to match what is actually resolved.

## SCOPE — hard boundaries

- Only `tests/validate_audit.py` may be edited. Nothing else.
- `$PLUMBLINE_AUDIT_ROOT`, when set, still names the root and wins.
- No change to grading logic beyond resolving the audit root: do not touch
  `GENERATIONS`, `generation_for()`, the pass-rule recomputation, the readings-record
  branch, the schema checks, the coverage accounting, or the exit codes that the
  no-records branches return.
- No re-pin, nothing under `schemas/`.
- Do not refactor the runner.
- Do not edit `tests/test_validate_audit_root.py` or any other file in the frozen set.

Note the existing no-records branch at lines 123-136 already distinguishes "this checkout
ships no `dot-plumbline/audits/`" (exit 0 with a NO AUDIT RECORDS IN REACH message) from
"a checkout that HAS one and finds no records" (exit 1). Check 2's exit-0 requirement
follows from that branch once the implied root is the repo itself rather than its parent.
Read those lines before changing anything above them.
