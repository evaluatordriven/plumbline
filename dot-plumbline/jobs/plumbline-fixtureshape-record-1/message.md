The frozen bar is tests/test_fixture_shape.py. Run it:

    python3 tests/test_fixture_shape.py

It is red on exactly one check: test_06_emit_fixture_exists -- "the emit fixture 'job-emitted' must exist as a
separate directory". Two other checks SKIP because that fixture does not exist yet. Everything else passes.

## YOUR EDITABLE SET -- TWO ENTRIES

  1. `tests/fixtures/custody/job-emitted/`  -- A DIRECTORY YOU CREATE. This is not a list of leaf paths; the bar
     walks every fixture directory under tests/fixtures/custody/ and reads whatever it finds. Build a complete,
     LEGAL job fixture there, in the same shape as tests/fixtures/custody/job-rejected/, with these differences:
       - its harness logs carry the logger's own sent_at and received_at on EVERY call (that is what makes it
         emittable under D6/D7);
       - every ledger line in inputs/custody-events.jsonl declares "writer": "tool";
       - its dispose event names both "by" and "state" (a dispose with neither is not a legal dispose);
       - no "writer": "hand" anywhere -- the bar asserts that no committed fixture uses it.
     Read job-rejected as your template and copy its structure. Do not edit job-rejected itself.

  2. `tests/validate_schemas.py` -- remove the runtime-stamping mechanism, do not add to it.

## WHAT MUST DISAPPEAR FROM tests/validate_schemas.py

This job exists because that file stamped harness times onto copies of job-rejected at runtime. Three checks that
exist to test an UNSTAMPED call silently lost their condition. Remove the mechanism:

  - `_stamp_logger_times(path)` -- the helper that writes sent_at/received_at into a log file. Delete it.
  - `LOGGED = logger_stamped("fixture-logged")` -- the module-level stamped copy. Delete it.
  - `logger_stamped(name)` -- the function that copies FIX and stamps every harness log. Delete it.
  - `job_copy_logged(name, overlay=None)` -- delete it.
  - `job_copy(name, overlay=None)` -- STOP copying LOGGED. It must copy the committed fixture directly
    (`shutil.copytree(FIX, d)`), so no runtime stamping happens anywhere.
  - `job_copy_raw(name, overlay=None)` -- once job_copy copies FIX, this is a duplicate. Delete it and point its
    callers at job_copy.

  Then repoint the EMIT-PATH cases at the new committed fixture: the checks that need a record to be written
  (the emit-success checks, the 59-second tolerance case, E2 under --allow-hand-times) take
  `tests/fixtures/custody/job-emitted/` instead of a stamped copy. The checks that must REFUSE (T7b/E3 naming
  every call the logger did not stamp, and the plain refusal cases) stay on `job-rejected`.

  Do NOT delete any check. Do NOT weaken an assertion. If a check's meaning genuinely must change, stop and say
  which and why rather than changing it.

## WHAT "DONE" MEANS

Run all three, and report the numbers:

    python3 tests/test_fixture_shape.py                    -> 10 tests, 0 failures, 0 skips
    python3 tests/test_evaluator_harness_log.py            -> 12 tests, OK (the capability bar; this job may not cost it)
    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/run_all.py

The two skips must RUN and PASS once job-emitted exists. A skip standing in for a pass is not done.

DO NOT EDIT: tests/test_fixture_shape.py (the frozen bar), tests/test_evaluator_harness_log.py, kit/emit_custody.py,
kit/evaluator_harness_log.py, tests/fixtures/custody/job-rejected/, AGENTS.md.
