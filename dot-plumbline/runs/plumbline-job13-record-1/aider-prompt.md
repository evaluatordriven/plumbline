# Job 13 — the dispose line's `state` is read or refused by name, never dropped silently

## The failing tests are the spec

`tests/test_disposition_line_state.py` is the standard. It currently reads (baseline, committed):

    2 failed, 3 passed

    FAILED test_A_contradiction_is_refused_naming_both_values
    FAILED test_C_unreadable_state_shape_is_refused_by_name
    PASSED test_B_agreement_emits_and_changes_nothing
    PASSED test_A2_the_packet_and_custody_json_are_the_two_record_sources
    PASSED test_D_two_real_records_with_a_disposition_block_still_emit

Make **A** and **C** pass. Do **not** break **B**, **A2** or **D**. Read the test file in full — its
module docstring, each case's docstring and each assertion is the requirement. Nothing below overrides
it; where they differ the test wins.

## What the emitter must do (the shape of the change)

`kit/emit_custody.py` reads the record's disposition state from ONE source today:
`state = packet.get("disposition_state")`. The ledger's `dispose` line (from `inputs/custody-events.jsonl`,
already available as `ev_log.get("dispose")`) carries its own `state`, and nothing compares it. Three
outcomes are required:

1. **Contradiction** — the line's `state` is a known disposition value and differs from the state the
   record would carry: the emitter must FAIL, exit code 1, and the refusal must name BOTH values — the
   line's value and the value the record would have carried — and the field name `disposition.state`.
   The written record (tests read the `--out` file) must carry a gap whose `field` is
   `disposition.state`.
2. **Agreement** — the line's `state` equals the state the record would carry: ignored. Exit 0, the
   record's `disposition.state` unchanged, no `disposition.state` gap added.
3. **Unreadable** — the line's `state` is a shape the emitter does not recognise (e.g. an object
   `{"value": "given"}`): refused by name, exit 1, same `disposition.state` field. The refusal text
   must say the shape was not read ("unreadable", "not a known", or "shape"). The record must NOT
   carry that object as its `disposition.state` (it stays the packet's value / a string).

## Hard constraints — the bar is green only if these hold

- **The record's `disposition.state` stays the packet's `disposition_state`.** The ledger line is
  CHECKED, never USED. A change that makes the line's `state` (or `by`) the record's value is WRONG
  even if the tests pass. See the emitter's own docstring, lines 14-15, and the test module's
  "WHAT THE BAR MUST NOT REQUIRE" section: no third source of record.
- **Reuse the existing `disposition.state` gap (exit 1).** Do not invent a new refusal kind, a new
  `H.Refusals` kind, a new gap field, or a new exit code. A hard gap on `disposition.state` is
  already what makes `main()` return 1 and is already written into `x-plumbline.gaps`.
- No corpus change, no version bump, no change to the custody/v1 record shape.
- Do not fabricate: a gap whose reason cannot be sourced is not acceptable — the values named must be
  the actual values read.

## Files — do not edit these

FROZEN — do not read, restructure, or edit:

- `tests/test_disposition_line_state.py`
- `tests/fixtures/custody/job-disposition-line/**` (every file in that directory)

Editing a frozen file invalidates the run. If you believe a test is wrong, stop and say so; do not
change it.

## Editable

- `kit/emit_custody.py` — the only file you may modify.

## Acceptance

From the repository root:

    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 -m pytest tests/test_disposition_line_state.py -q

must report `5 passed`.

Then the whole suite must not regress. Baseline at the committed tree is:

    2 failed, 258 passed, 3 skipped

so after the change:

    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 -m pytest tests -q

must report `260 passed, 3 skipped` (zero failed). A pre-existing unrelated red in
`tests/run_all.py`'s `validate_audit` suite is not yours and is not in this command's scope.

## Style

Match the surrounding code in `kit/emit_custody.py`: a short comment naming why the check exists,
the existing `gaps.add(field, reason)` idiom, f-strings with `!r` for values, lines within the file's
existing width. No new imports are needed.
