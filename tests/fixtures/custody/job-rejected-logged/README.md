# SYNTHETIC FIXTURE — not a job, not a record of anything that happened

Every name, time, score and approval here is invented so that `tests/validate_schemas.py` and the
`emit_cmd` smoke can exercise `kit/emit_custody.py` with no corpus, no network and no model call.
Nothing in this folder is evidence of a real reading and none of it may be submitted as one.

Shape: a scored job that ended `rejected` (verdict `reject`, disposition not yet given), one model
evaluator, one batch, a clean and a planted control, one violation located `artifact_missed_standard`.

## This copy: the logger-stamped sibling of `../job-rejected/`

Byte-identical to `../job-rejected/` except `custody/evidence/harness-eval-a.log`, whose three calls
(`eval_artifact`, `eval_k1`, `eval_k2`) carry the logger's own `sent_at`/`received_at`. The instant on
each call is its own `response.created` epoch — the same precedence `kit/custody_history.py` (`Call.at`)
and `tests/validate_schemas.py` (`_server_instant`) use — so stamping moves nothing in the timeline; it
only makes explicit the value the reader already derived.

`tests/fixtures/custody/job-rejected/` must KEEP those six times absent. T7b/E3, J14/A1–A3a, the
`fixture-refused` case and the 61-second tolerance case each exist to observe what the emitter does with
a call the logger did not stamp, and stamping the shared fixture would delete the condition under test.
A case that must EMIT a record from this job with no defect of its own copies THIS folder; a case that
must observe the refusal copies `../job-rejected/`.

Why it exists: Job 14's standard (`kit/emit_custody.py:1221`) made `--allow-hand-times` stop admitting a
model evaluator's unsourced check time, which left two `tests/test_plumbline_verify.py` cases red on a
fixture that encoded the old standard. The repair is the fixture, never the assertion.
