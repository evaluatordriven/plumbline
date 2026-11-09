# Maker brief — Job 14, ATTEMPT 3 at generation 1

**Attempt 3 at generation 1.** Attempts 1 and 2 spent no generation: Aider never started (unset environment variables
on the Orchestrator's side). Corrected below, and verified before launch.

## THE EDITABLE SET — unambiguous

> **EDITABLE: `kit/emit_custody.py` and `kit/custody_history.py`.**
> **FROZEN: the tests and the bar** — `tests/validate_schemas.py`, `tests/test_evaluator_harness_log.py`. Do not edit them.

**Frozen means the tests and the bar. It never means the emitter.** The emitter is the thing you are here to change.

If `AGENTS.md` says *"a bar that shells out to the emitter is green only on a committed tree"*, that is about **when the
bar may be believed**, not a freeze on editing the emitter. You may edit the emitter. Commit before the bar can be
believed; that is all it says.

**No new files.** Work in the two files above. If you need to check your own permissions, do it with a shell command —
do not add a script to the repo.

## THE TEST COMMAND — both suites, never one

    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py
    python3 tests/test_evaluator_harness_log.py

**Both.** A run measuring only the harness-log suite cannot see A1 or A2, and a green it reports is not a green.

## THE ONE BEHAVIOUR

> Under `--allow-hand-times`, an **unsourced model-evaluator check time is still refused** — the switch does not reach
> it — **and** a genuinely unstamped call is still **named**. The switch still does what its name says for genuine
> hand-entered times.

## YOUR OWN DIAGNOSIS FROM ATTEMPT 2 — carried verbatim, as your reading, not as instruction

> *"the unsourced-check-time is computed in the **emitter**'s frozen check path (`source_at`/`at_source`/
> `time_sources`). The reader has **no switch seam** — `read_log`'s skip path can't carry the switch's refusal, so an
> added reader refusal would be a second mechanism nobody invokes."*
>
> *"The surgical fix (drop unsourced calls before `allow_unstamped=\"skip\"` admits them; then, under the switch, refuse
> AND name every unstamped call) lives entirely in the **frozen emitter** (`kit/emit_custody.py`)."*

The Orchestrator records that as **your path, not a solution** — it is your reading of the mechanism and it is not
confirmed by the Orchestrator. The emitter is not frozen: it is in your editable set. Use the path if it holds; discard
it if the code says otherwise.

Also note: an inert declaration you left in `kit/custody_history.py` at attempt 2 —

    unstamped: list[dict] = []

— is declared and never used. It is yours: keep it, use it, or remove it. Nobody else will touch your diff.

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

## WHERE

  - `kit/emit_custody.py` — refusals are raised here (`ref.add("hand-time", …)` gated on `allow_hand`); the
    evaluator's check times are assembled here (`source_at`, `at_source`, `time_sources` per your reading). **Yours.**
  - `kit/custody_history.py` — **yours.**
  - `kit/evaluator_harness_log.py` — read it; **not yours to edit.**
  - `docs/custody-emission.md` "Refusals": `[time]` is for a model evaluator with **no harness log at all**;
    `[hand-time]` for a value with no sourced provenance.

## BOUNDS

  - No new files. Do not edit any test file. No `--now`, no new `--allow-*`, no clock injection.
  - **Do not weaken any refusal.** If a refusal must change class or message, stop and say so.
  - **Commit before measuring** — the emitter refuses a dirty tree; staged is not clean.
  - Cap 2 generations, $0.20. A diff with no non-comment line change is not a generation.

## RETURN

  1. `git diff` — the changed lines, named.
  2. One sentence on how the change confines the switch to hand-entered values rather than widening it.
  3. Both test commands, verbatim, with the tally and every red case by case.
  4. Anything you could not do, and why.
