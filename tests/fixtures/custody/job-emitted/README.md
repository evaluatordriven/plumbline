# SYNTHETIC EMIT FIXTURE — not a job, not a record of anything that happened

This fixture is the logger-stamped partner of `job-rejected/`.  Every model-seat
harness call here carries the logger's own `sent_at` and `received_at`, copied
from the call's own `response.created` epoch.  Those instants are:

- `harness-maker-fixture.log`  `fixture/maker-1`  → `2026-10-20T11:00:00Z`
- `harness-eval-a.log`       `eval_artifact`    → `2026-10-20T12:00:02Z`
- `harness-eval-a.log`       `eval_k1`          → `2026-10-20T12:01:01Z`
- `harness-eval-a.log`       `eval_k2`          → `2026-10-20T12:02:04Z`

The ledger lines are identical to `job-rejected/` and are all `writer: tool`.
The disposition event carries `by: Fixture Buyer` and `state: given`.

This fixture is intended for tests that exercise a successful custody/v1
emission under `kit/emit_custody.py` (for example, `tests/test_fixture_shape.py`).
Nothing here is evidence of a real reading and none of it may be submitted as one.
