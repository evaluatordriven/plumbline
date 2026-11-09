# Aider prompt — Job 14, the `--allow-hand-times` boundary

You are editing the Plumbline custody emitter. The failing tests are the spec. Read them; they are
frozen and you may not change them.

## The behaviour to deliver

`--allow-hand-times` is a switch about **hand-entered times** — a value typed into
`inputs/custody.json` that has no ledger line or logger stamp behind it. It is **not** a licence to
admit an **unsourced model-evaluator check time**: a time that exists only because the evaluator's
harness-log call carried no logger `sent_at`/`received_at` and the reader fell back to a server
`Date` header or a response `created` epoch.

Today the switch reaches both. Under `--allow-hand-times` a record is written whose model
evaluator's check times have no logger source. It must be refused, exactly as it is refused without
the switch — same refusal kind, naming the harness log, naming **every** unstamped call (not the
first), nothing written — while a genuinely typed hand time is still admitted and listed.

## Run the bar first, and read it

    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py
    python3 tests/test_evaluator_harness_log.py

Red now (these are yours): `J14/A1`, `J14/A2` in `tests/validate_schemas.py`, and
`test_d13_switch_does_not_admit_an_unsourced_evaluator_time`,
`test_d14_switch_refusal_names_every_unstamped_call` in `tests/test_evaluator_harness_log.py`.

Must stay green — if any of these turns red you have widened the change past the target, and the
generation is returned:

    custody · J14/A3a the no-switch refusal names EVERY evaluator call the log carries
    custody · J14/A3b the refusal publishes all six evaluator hand_time fields by field name
    custody · J14/A4 a genuine hand-entered time is still admitted under the switch
    custody · T7b/E3 every evaluator call the logger did not stamp is named
    custody · V1/V3/T2, T3, E2
    and the other 13 tests in tests/test_evaluator_harness_log.py

Five reds in `tests/validate_schemas.py` belong to **other jobs**. Do not attempt them and do not
make them green: the line-609 `[time]` refusal case, the "hand time 59 s off" case, `T2c`, `T3`'s
switch case, and `E2`.

## Where to look (read, understand, then decide — I am not giving you the change)

- `kit/emit_custody.py` — `build()`, `maker_history()`, `evaluator_history()`, `flag_calls()`, and
  the block around lines 1199–1207 where `xp["hand_times"]` is assembled and, when `hand and not
  allow_hand`, a `hand-time` refusal is added per entry.
- `kit/custody_history.py` — `Call.hand_time_entries()`, which builds those entries from
  `response_headers.Date` / `response.created` when the logger stamped nothing, and
  `Call.source_at()` / `Call.source_started()`.
- `kit/evaluator_harness_log.py` — the strict reader. Read it. **Do not edit it** (outside your set).
- `docs/custody-emission.md`, the Refusals section: `[time]` is reserved for a model evaluator with
  no harness log at all; `[hand-time]` for a time with no sourced provenance. The bar asserts both.

The distinction the bar draws is between *where the value came from*: a typed input value
(`inputs-no-ledger`) versus a value synthesised by the reader from a server header or response
epoch. Confine the switch to the first and refuse the second, by the mechanism the existing code
already uses for refusals — not by a new flag, not by a clock, not by weakening the no-switch path.

## Rules

- Edit **only** `kit/emit_custody.py` and `kit/custody_history.py`. No new files.
- Do not touch `tests/validate_schemas.py` or `tests/test_evaluator_harness_log.py`, ever.
- No `--now`, no new `--allow-*` flag, no clock injection.
- Do not weaken, rename or reclassify any existing refusal. If a case you were not asked to change
  goes red, fix your change rather than the test.
- A diff with no non-comment line change is not a generation. Make the change, then run both
  commands and report the tally and every red case by case.
