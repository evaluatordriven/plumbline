# Maker findings — Job 14, generation 1 of the reopened loop

## ONE TARGET

Under `--allow-hand-times`: an unsourced model-evaluator check time is still REFUSED — the switch does not reach it —
an unstamped call is still NAMED, and genuine hand-entered times are still ADMITTED.

## THE RED, MEASURED BY THE OWNER ON THIS TREE AT 851a07d

    python3 -m pytest tests/test_evaluator_harness_log.py -q
      2 failed, 13 passed in 1.14s
      FAILED  test_d13_switch_does_not_admit_an_unsourced_evaluator_time
      FAILED  test_d14_switch_refusal_names_every_unstamped_call

Failure text, verbatim:

    GAP producedAt: no RFC 3339 UTC time recorded ... 11 hard gap(s), named in x-plumbline.gaps:
    a required field had no source (left null/absent; fix the inputs and re-emit)

at `tests/test_evaluator_harness_log.py:318`.

## TWO FACTS ABOUT YOUR PREVIOUS REASONING, BOTH MEASURED — READ THESE FIRST

**1. The version-mismatch premise is FALSE.** A previous seat concluded *"the test and the emitter are
version-mismatched, the reversal code is elsewhere."* That was measured against this tree: **13 of the 15 tests in the
same file pass, in the same tree, against the same emitter.** A version-mismatched test does not pass 13 times. Do not
go looking for a reversal in another repository. The file runs here and 13 tests pass here.

**2. The tree is CLEAN.** `git status --porcelain` is empty and `git diff` is empty at `851a07d`. Any belief that *"my
uncommitted line is what's throwing every emit off"* is stale and false — **there is no uncommitted line.** Start from a
clean tree; you do not need to clear anything.

## THE TARGET, STATED AS THE WORK

Make those **eleven gaps have sources**, and make **the switch refuse an unsourced evaluator time while naming every
unstamped call**.

The failure is a named gap list — `producedAt` has no RFC 3339 time and ten other fields have no source. It is not a
missing mechanism. Read `x-plumbline.gaps` in the emitted record to see which eleven fields they are before you change
anything.

## EDITABLE — yours

    kit/emit_custody.py
    kit/custody_history.py

## FROZEN — do not edit, ever

    tests/validate_schemas.py
    tests/test_evaluator_harness_log.py

Frozen means the tests and the bar. It never means the emitter. No new files.

## THE FOUR THAT MUST GO GREEN

    custody · J14/A1 a model evaluator's check time is refused UNDER --allow-hand-times, naming the log
    custody · J14/A2 the refusal cites the EVALUATOR path, not only the maker's
    test_d13_switch_does_not_admit_an_unsourced_evaluator_time
    test_d14_switch_refusal_names_every_unstamped_call

## NOT YOURS — five reds belonging to other jobs. Do not touch, do not make green

    the line-609 `[time]` refusal; the 59 s case; T2c; T3; E2

## MUST STAY GREEN

    custody · J14/A3a the no-switch refusal names EVERY evaluator call the log carries
    custody · J14/A3b the refusal publishes all six evaluator hand_time fields by field name
    custody · J14/A4 a genuine hand-entered time is still admitted under the switch
    custody · T7b/E3 every evaluator call the logger did not stamp is named
    and the other 13 passing tests in test_evaluator_harness_log.py

## TEST COMMANDS — both, always

    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py
    python3 tests/test_evaluator_harness_log.py

## BOUNDS

  - Commit before measuring — the emitter refuses a dirty tree; staged is not clean.
  - Do not weaken any refusal. No `--now`, no new `--allow-*` flag.
  - Write a diff. A turn spent describing the mechanism, exploring other repositories, or reporting a blocker with no
    changed line is not a generation. If the fix is genuinely impossible inside the editable set, say which line blocks
    it and stop — that is an answer. Prose alone is not.
