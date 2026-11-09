# SYNTHETIC FIXTURE — not a job, not a record of anything that happened

Every name, time, score and approval here is invented. Nothing in this folder is evidence of a real
reading and none of it may be submitted as one.

**Why this fixture exists.** It is `job-rejected` with exactly two edits, named by the code the fixture
must exercise (`kit/emit_custody.py`):

1. `inputs/custody.json` → `disposition` carries `state: "given"` (alongside the `by` and `at` the emitter
   already reads), and `packet.json` → `disposition_state: "given"`. So both *sources of record* agree:
   the Owner gave the disposition.
2. `inputs/custody-events.jsonl` → the `dispose` line carries `"state": "declined"` — the shape
   `kit/custody_ledger.py dispose --state declined --by "…"` writes (it writes both, `custody_ledger.py:336`
   and `:344`). So the *live ledger* contradicts the record, by name.

The dispose line's `at`/`by` still agree with `custody.json`, so the disagreement under test is the
**state** alone; the `time` comparison (F1b) stays quiet and cannot account for the result.

This is a **new labelled sibling**, not a mutation of `job-rejected`: `tests/validate_schemas.py` and
`tests/test_plumbline_verify.py` both read `job-rejected` and must keep reading what they were written for.
