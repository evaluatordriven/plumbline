ONE job, one directory. Build `tests/fixtures/custody/job-emitted/`.

## COPY, DO NOT AUTHOR

`job-emitted/` is `job-rejected/` with a handful of differences. COPY THE TREE FIRST:

    cp -r tests/fixtures/custody/job-rejected tests/fixtures/custody/job-emitted

then edit only the two or three files that actually differ. Authoring 18 files from scratch is what the last
generation died of: a diff-based edit tool pointed at a large new tree spends its budget on compaction instead of
content. Do not rewrite files that do not need to change.

## THE DIFFERENCES — exactly these

  1. `inputs/custody-events.jsonl` — the dispose event must carry BOTH `by` and `state` (a dispose with neither is
     not a legal dispose). Every line already carries `"writer": "tool"`; keep that. No `"writer": "hand"` anywhere:
     the bar asserts no committed fixture uses it.

  2. `custody/evidence/harness-eval-a.log` (and any other model-seat harness log) — every call must carry the
     logger's own `sent_at` and `received_at`, because that is what makes the job emittable under D6/D7. Use the
     times the call's own response already carries: its `response.created` epoch if present, else its `Date`
     header. If a harness log already carries both fields on every call, leave it alone.
     The reason for the exact values: `kit/emit_custody.py` REFUSES when a model evaluator's log has a call with no
     sent_at ("sent_at is missing or not RFC 3339 UTC"), and it refuses when a hand time is more than 60 s from the
     call's own time. Stamp the server's own instant and both refusals clear.

  3. `README.md` — replace the copied one. Say what this fixture is (the EMITTING job: a legal job whose logs carry
     logger times), which calls its logger stamped, and that it exists so no single fixture is asked to be both the
     emitting and the refusing case. `job-rejected/` keeps that job and its logs stay unstamped.

  4. Anything else in the copied tree that names `job-rejected` or describes the refusal case — update the wording
     so the fixture does not describe itself as something it is not.

## THE BAR THAT MEASURES YOU

    python3 tests/test_fixture_shape.py

Currently 1 failure (job-emitted missing) and 2 skips (both conditional on job-emitted existing). Your work is done
when it is **10 tests, 0 failures, 0 skips** — the two skips must RUN and PASS. A skip standing in for a pass is
not done.

    python3 tests/test_evaluator_harness_log.py

must stay **12/12**. It is the capability bar and this job may not cost it.

## YOUR EDITABLE SET

    tests/fixtures/custody/job-emitted/          (the directory you create by copying)

Nothing else. In particular: do NOT touch `tests/validate_schemas.py` in this generation — removing the stamping
mechanism before the fixture exists would leave that file with no way to build an emitting job at all. Do NOT edit
`tests/fixtures/custody/job-rejected/`, `tests/test_fixture_shape.py`, `tests/test_evaluator_harness_log.py`,
`kit/emit_custody.py`, or `AGENTS.md`.
