# Job 14 — findings for the Maker

ONE TARGET: under `--allow-hand-times`, an unsourced model-evaluator check time is **refused**; a genuinely unstamped
call is still **named**; and the switch still admits genuine hand-entered times.

## The red, exactly as the bar reports it (committed 851a07d, clean tree)

    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py
      132/139 PASSED — 7 FAILED
    python3 tests/test_evaluator_harness_log.py
      Ran 15 tests — FAILED (failures=2)

YOUR reds:

    custody · J14/A1 a model evaluator's check time is refused UNDER --allow-hand-times, naming the log (exit 3, [time], nothing written)
    custody · J14/A2 the refusal cites the EVALUATOR path, not only the maker's (evaluator eval-a, [hand-time] listing harness-eval-a.log)
    test_d13_switch_does_not_admit_an_unsourced_evaluator_time
    test_d14_switch_refusal_names_every_unstamped_call

Measured behaviour today on the fixture (`tests/fixtures/custody/job-rejected`) at the case's own path:

    --allow-hand-times   rc=0  record WRITTEN   [time]=False  [hand-time]=False
    no switch            rc=3  nothing written  [hand-time]=True

The first row is the defect: under the switch the emitter refuses nothing and writes a record whose model evaluator's
check times came from a `Date` header.

NOT YOURS — five reds that belong to other jobs. Do not touch them, do not make them green:

    the line-609 `[time]` refusal; the 59 s case; T2c; T3; E2   (T3 and E2 are a separate dispose-read and
    typed-time-ordering finding; a job nobody has opened)

MUST STAY GREEN — turning one of these red means the change widened past the target:

    custody · J14/A3a the no-switch refusal names EVERY evaluator call the log carries (eval_artifact + eval_k1 + eval_k2)
    custody · J14/A3b the refusal publishes all six evaluator hand_time fields by field name, not by length
    custody · J14/A4 a genuine hand-entered time is still admitted under the switch and listed with file and source
    custody · T7b/E3 every evaluator call the logger did not stamp is named (harness-eval-a.log, server time)
    and every other green in both suites

## THE MECHANISM — a path, not a diagnosis

  - `kit/emit_custody.py` is where refusals are raised (`ref.add("hand-time", …)` gated on `allow_hand`) and where an
    evaluator's check times are assembled. That is your editable file.
  - `kit/evaluator_harness_log.py` is the reader seam; **read it, do not edit it** — it is outside your set.
  - `docs/custody-emission.md` "Refusals": `[time]` is reserved for a model evaluator with **no harness log at all**;
    `[hand-time]` for a value with no sourced provenance. Two different refusals; the bar asserts both.

The switch's job is hand-entered times. The defect is that it also reaches a logger time with no source. Confine it;
do not extend it, do not disable it.

## BOUNDS

  - Editable: `kit/emit_custody.py`, `kit/custody_history.py`. Nothing else. No new files.
  - Do not edit any test file. No `--now`, no new `--allow-*` flag, no clock injection.
  - Do not weaken any refusal. If a refusal must change class or message, stop and say so.
  - Cap 2 generations, $0.20. A diff with no non-comment line change is not a generation.
  - Commit before measuring — the emitter refuses a dirty tree, and staged is not clean.
