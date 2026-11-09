# Job 25 — make the four failing JOB25 cases pass

The failing tests are the spec. Read them, do not edit them.

Run the bar from the work tree:

    cd /home/jarbis1/tmp/plumbline-hl-redo
    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py

Measured state at the base commit right now: `140/144 PASSED — 4 FAILED`.
The four failing ids are `custody · JOB25 b1`, `b2`, `c1`, `d1`.
Make those four pass and leave the other 140 passing.

## FROZEN — do NOT edit these, in any way

- `tests/validate_schemas.py`
- `tests/fixtures/**` — every fixture, including `tests/fixtures/custody/job-rejected/**`
  and the overlays under `tests/fixtures/custody/failures/**`

Do not add cases, delete cases, skip cases, change an assertion, or edit a fixture the bar
reads. A change to a frozen file fails the job even if the tally goes green. If a case looks
wrong to you, say so in the report and stop on it — do not edit it into agreement.

## Editable — only these two files

    kit/emit_custody.py
    kit/custody_history.py

Nothing else. Do not create new files under the work tree. Do not touch any other
`packet.json` or any other job's records.

## The four failing cases, quoted from the bar

1. **b1** — "a model evaluator check time the logger never stamped is REFUSED under
   `--allow-hand-times`". Measured: `exit 0; record written=True`. Asserts `_rc == 3`,
   `not _o.exists()`, and `"harness-eval-a.log#eval_artifact"` present in the emitter's
   output.

2. **b2** — "...and the refusal names every unstamped evaluator call by id, none left
   unnamed". The overlay log carries `['eval_artifact', 'eval_k1', 'eval_k2']`; the refusal
   named `[]`. Asserts that for __every__ id the log carries, `harness-eval-a.log#<id>`
   appears in the output — not only the first.

3. **c1** — "the boundary: `--allow-hand-times` admits a stamped fixture and refuses one with
   no logger-stamped time". Measured: `typed admitted=True; unstamped refused=False`. Asserts
   both halves in one case: `job-rejected` (untouched) under the switch exits 0 and writes;
   the unstamped overlay under the same switch exits 3 and names the calls.

4. **d1** — "any record written under the switch gives every called check its OWN `at_source`
   (no collision, none blank)". Measured: both called checks carry `harness-eval-a.log:37`.
   Asserts, for any record written under the switch: `_rc == 0`, at least one called check,
   no called check with a blank/missing `x-plumbline.at_source`, and no two called checks
   sharing one `at_source`.

Read the case bodies (section headed `JOB 25`, `hl_case` calls, roughly lines 1145–1337 of
`tests/validate_schemas.py`) for exactly what each asserts; the comments state what each
fixture carries.

## What must stay green

- **a1–a4** — main-green behaviours from PR 24's regression set. SAME fixture bytes, SAME
  switch: a3 and a4 must still WRITE under `--allow-hand-times`. Do not change their
  behaviour. Do not move them onto the unstamped overlay.
- **P1, P2** — fixture premise cases (read the overlay's bytes; a stale overlay must not let
  a case pass vacuously).
- **B** — `failures/hand-times` under the same switch must still refuse with exit 3,
  `[time]` in the output, nothing written.
- Every other passing case (schema, kit, corpus sections above `JOB 25`): leave green.

## Context you may need — facts, not a solution

- `tests/fixtures/custody/job-rejected/`: each of its three evaluator calls in
  `custody/evidence/harness-eval-a.log` carries `response.created` and a
  `response_headers.Date` one second apart, and carries no logger `sent_at` /
  `received_at`; `inputs/custody.json` types a `passes.pass-a.at`. A linked model check's
  time is the Date header (call.at = `received_at` or Date or `created`) — so its check time
  is backed by the log even without a logger stamp.
- `tests/fixtures/custody/failures/unstamped/**`: its calls carry no `Date` header and its
  `inputs/custody.json` has no `passes.pass-a.at`. That is the defect b1/b2/c1 must refuse.
- The bar derives the call ids from the overlay log at run time — do not hard-code a list of
  ids in the emitter; name what the log carries.
- Files of interest in `kit/emit_custody.py`: the check-building code (search `at_source`,
  `allow_hand`, `checks[`, `source_at`), around lines 900–1050, and the refusal/emit tail
  near line 1501. `kit/custody_history.py` reads the logs.

## Constraints

- Keep the exit codes the bar distinguishes: a refusal under the switch is `3`; nothing
  written. Do not invent a new code.
- Refuse every unstamped evaluator call by id, and write nothing, when the switch cannot
  source a check's time. Do not weaken any existing refusal, gap, or `x-plumbline` field to
  get green.
- No new dependencies. If a shared helper is needed, put it in one of the two editable
  files.
- When done, run the test command above and report the tally line verbatim plus
  `git diff --stat`. Do not claim a pass you did not observe.

## Report back

1. The tally line before your change.
2. The tally line after your change.
3. What you changed, in which file, and why each of b1/b2/c1/d1 now holds.
4. Any case you believe is unsatisfiable as written, with the fixture evidence, and stop.
