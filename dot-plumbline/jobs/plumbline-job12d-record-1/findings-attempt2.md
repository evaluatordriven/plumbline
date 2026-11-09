# Maker brief — Job 14, ATTEMPT 2 at generation 1

**Attempt 2 at generation 1.** Attempt 1 spent no generation: Aider never ran (an unset log path), and the seat wrote a
dispatch that narrowed the target. Corrected below.

## THE EDITABLE SET — read this first, it is unambiguous

> **EDITABLE: `kit/emit_custody.py` and `kit/custody_history.py`.**
> **FROZEN: the tests and the bar** — `tests/validate_schemas.py`, `tests/test_evaluator_harness_log.py`. Do not edit them.

**Frozen means the tests and the bar. It never means the emitter.** The emitter is the thing you are here to change.

If you read in `AGENTS.md` that *"a bar that shells out to the emitter is green only on a committed tree"* — that
sentence is about **when the bar may be believed**, not a freeze on editing the emitter. You may edit the emitter.
You must **commit** before the bar can be believed; that is all it says.

The reds you are chasing are on the **emit path**. `kit/custody_history.py` alone cannot fix them. Both files in your
set are yours to use; use whichever the fix needs.

## THE TEST COMMAND — both suites, never one

    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py
    python3 tests/test_evaluator_harness_log.py

**Both.** A run that measures only `test_evaluator_harness_log.py` cannot see A1 or A2 at all, and a green it reports
is not a green. Do not narrow the test command.

## THE ONE BEHAVIOUR

> Under `--allow-hand-times`, an **unsourced model-evaluator check time is still refused** — the switch does not reach
> it — **and** a genuinely unstamped call is still **named**. The switch still does what its name says for genuine
> hand-entered times.

`--allow-hand-times` is about **hand-entered times**. It is not a licence to admit a logger time with no source.

## THE RED

    validate_schemas            132/139 PASSED — 7 FAILED
    test_evaluator_harness_log  Ran 15 tests — FAILED (failures=2)

**YOURS — these four must go green:**

    custody · J14/A1 a model evaluator's check time is refused UNDER --allow-hand-times, naming the log (exit 3, [time], nothing written)
    custody · J14/A2 the refusal cites the EVALUATOR path, not only the maker's (evaluator eval-a, [hand-time] listing harness-eval-a.log)
    test_d13_switch_does_not_admit_an_unsourced_evaluator_time
    test_d14_switch_refusal_names_every_unstamped_call

**NOT YOURS — five reds belonging to other jobs. Do not touch, do not make green:**

    the line-609 `[time]` refusal; the 59 s case; T2c; T3; E2

**MUST STAY GREEN — turning one of these red means the change widened past the target:**

    custody · J14/A3a the no-switch refusal names EVERY evaluator call the log carries (eval_artifact + eval_k1 + eval_k2)
    custody · J14/A3b the refusal publishes all six evaluator hand_time fields by field name, not by length
    custody · J14/A4 a genuine hand-entered time is still admitted under the switch and listed with file and source
    custody · T7b/E3 every evaluator call the logger did not stamp is named (harness-eval-a.log, server time)
    and every other green in both suites

## WHERE TO LOOK

  - `kit/emit_custody.py` — refusals are raised here (`ref.add("hand-time", …)` gated on `allow_hand`), and the
    evaluator's check times are assembled here. This is the likeliest site and it is **yours**.
  - `kit/custody_history.py` — also yours.
  - `kit/evaluator_harness_log.py` — the reader seam. **Read it; it is NOT yours to edit.**
  - `docs/custody-emission.md` "Refusals": `[time]` is reserved for a model evaluator with **no harness log at all**;
    `[hand-time]` for a value with no sourced provenance. Two different refusals; the bar asserts both.

## BOUNDS

  - Editable: `kit/emit_custody.py`, `kit/custody_history.py`. Nothing else. No new files.
  - Do not edit any test file, ever.
  - No `--now`, no new `--allow-*` flag, no clock injection.
  - **Do not weaken any refusal.** If a refusal must change class or message, stop and say so — do not edit quietly.
  - **Commit before measuring.** The emitter refuses a dirty tree; staged is not clean.
  - Cap 2 generations, $0.20. A diff with no non-comment line change is not a generation.

## RETURN

  1. `git diff` — the changed lines, named.
  2. One sentence on how the change confines the switch to hand-entered values rather than widening it.
  3. Both test commands, verbatim, with the full tally and every red case by case.
  4. Anything you could not do, and why.
