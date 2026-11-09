# SYNTHETIC FIXTURE — a job that PASSED; not a record of any real run

This folder DESCRIBES a job that passed. It is NOT a record of any real run: no job
`fixture-passed` was ever dispatched, no model was called, no evaluator read anything, and no
person approved a bar. Every name, time, score, hash and approval here is invented.

## Why it exists

`tests/validate_schemas.py` has emit-path cases that need a job accepted at its terminal state: they
assert what `kit/emit_custody.py` writes when the job passed. The only other custody fixture,
`../job-rejected/`, describes a REJECTED job — its packet is `terminal_state: rejected`, its §5 record
carries `verdict: reject` and a D2 violation — so it cannot serve those cases however a test is
pointed at it.

## Shape

A scored job that ended `accepted` and whose disposition is `given`: one model maker, one model
evaluator, one pass (`pass-a`) in batch `b1`, a clean control (K1) and a planted control (K2), two
bar dimensions (D1 correctness, D2 completeness) both at or above threshold 9, and NO violations.

## Provenance — what this is not

This file was AUTHORED as a fixture. It was not derived from, copied from, or edited out of any
real job's record, and it does not claim to be one:

- `job_id` is `fixture-passed`, naming itself a fixture. It is not the identity of any real job.
- `retention.location` says "synthetic fixture; not retained anywhere". Nothing here is retained.

A previous custody fixture in this repository carried `job_id: fixture-rejected` and a retention
location pointing at a real-looking job directory. The defect there was not that it was authored —
packet fixtures describe hypothetical jobs throughout this repository — it was that it claimed a
provenance it did not have. This fixture does not make that claim.

## The limit — in the plainest terms

A fixture proves the emitter behaves correctly against a described job shape. It does not prove any
real job happened, and it is not evidence about any real record.

Nothing in this folder may be submitted as evidence of a reading, an approval or a decision.
