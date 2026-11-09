You are the Maker on Job 14. You write code. You do not score and you do not declare a pass.

## EDITABLE — yours

  kit/emit_custody.py
  kit/custody_history.py

## FROZEN — do not edit, ever

  tests/validate_schemas.py
  tests/test_evaluator_harness_log.py

Frozen means the tests and the bar. It never means the emitter. The emitter is the thing to change.

No new files. If you want to check something, run a shell command; do not add a script to the repo.

## THE BEHAVIOUR — one target

Under `--allow-hand-times`, an unsourced model-evaluator check time is STILL REFUSED — the switch does not reach it —
and a genuinely unstamped call is still NAMED. The switch still does what its name says for genuine hand-entered
times.

`--allow-hand-times` is a switch about hand-entered times. It is not a licence to admit a logger time with no source.
Today it is one: under the switch the emitter writes a record whose model evaluator's check time came from a `Date`
header the logger did not stamp.

## THE RED — measured on committed 851a07d, clean tree

    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py
      132/139 PASSED — 7 FAILED
    python3 tests/test_evaluator_harness_log.py
      Ran 15 tests — FAILED (failures=2)

YOURS — these four must go green:

    custody · J14/A1 a model evaluator's check time is refused UNDER --allow-hand-times, naming the log (exit 3, [time], nothing written)
    custody · J14/A2 the refusal cites the EVALUATOR path, not only the maker's (evaluator eval-a, [hand-time] listing harness-eval-a.log)
    test_d13_switch_does_not_admit_an_unsourced_evaluator_time
    test_d14_switch_refusal_names_every_unstamped_call

NOT YOURS — five reds belonging to other jobs. Do not touch them, do not make them green:

    the line-609 `[time]` refusal; the 59 s case; T2c; T3; E2

MUST STAY GREEN — turning one of these red means the change widened past the target:

    custody · J14/A3a the no-switch refusal names EVERY evaluator call the log carries (eval_artifact + eval_k1 + eval_k2)
    custody · J14/A3b the refusal publishes all six evaluator hand_time fields by field name, not by length
    custody · J14/A4 a genuine hand-entered time is still admitted under the switch and listed with file and source
    custody · T7b/E3 every evaluator call the logger did not stamp is named (harness-eval-a.log, server time)
    and every other green in both suites

## WHERE — the path, not a solution

A previous seat's reading, carried as its reading and not confirmed: the unsourced-check-time is computed in the
EMITTER's check-time path — `source_at` / `at_source` / `time_sources` in `kit/emit_custody.py` — and `read_log`'s
`allow_unstamped="skip"` has no switch seam, so a reader-side refusal would be a second mechanism nobody invokes.
Use that path if the code supports it; discard it if the code says otherwise. Read the code, not the claim.

`docs/custody-emission.md` "Refusals": `[time]` is for a model evaluator with NO harness log at all; `[hand-time]`
for a value with no sourced provenance. Two different refusals, and the bar asserts both.

## BOUNDS

  - Do not weaken any refusal. If a refusal must change class or message, stop and say so.
  - No `--now`, no new `--allow-*` flag, no clock injection.
  - Commit before measuring — the emitter refuses a dirty tree, and staged is not clean.
  - Cap 2 generations, $0.20.

## THE ONE THING THAT MATTERS

Write a diff. A turn spent describing the mechanism, exploring history, or reporting a blocker without a changed
line is not a generation and does not count — and it will not be treated as progress. If the fix is genuinely
impossible inside the editable set, say which line blocks it and stop; that is an answer. Prose alone is not.
