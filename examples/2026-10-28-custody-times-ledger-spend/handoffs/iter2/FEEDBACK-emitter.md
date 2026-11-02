ITERATION 2 FEEDBACK, part emitter (kit/emit_custody.py, tests/validate_schemas.py, new folders under
tests/fixtures/custody/)

The files shown above are YOUR iteration-1 files as committed. T1, T5 (cross-checks no looser than base) and the
T7 no-write rule (the tree is byte-identical after an emit; git status clean after the suite) passed. Keep that
work: change only what the items below need, return every changed file in full, and keep the INTERFACE.md
section 6 anchor lines in their form.

Item E1 (one cause behind most of the failed checks: T3, T4, F1b, F1f, F1h, X1, and the verifier and close checks
V1-V8 that run on records this emitter must write). Bar T4 (bar.md line 67): "A job built at batch time only by the
subject's own tools emits with no switch, exit 0, check.py OK at CL1, and an empty hand_times." Bar F1b (line 76):
"The line carries `at` (tool clock), `decided_at` and `decided_source`, and the record's `disposition.at` =
`decided_at`." INTERFACE.md line 26: `dispose ... --decided-at T` sets `custody.json` `disposition.at = decided_at`.
  What your iteration-1 code did: kit/emit_custody.py lines 784-789 compare custody.json `disposition.at` with the
  ledger dispose line's `at` (`live.get("at") != at`) and refuse with kind `time`
  ("disposition: the ledger says ... at ... but inputs/custody-events.jsonl logged ... at ..."). Your own
  kit/custody_ledger.py (lines 293-315) writes `disposition.at = decided_at` into custody.json and keeps the tool
  clock in the line's `at`, so on every job whose dispose used `--decided-at` (decided_at is always earlier than
  the tool clock) the emitter refuses with `time`, writes no record, and every later step has nothing to read.
  Change: when the dispose line has `decided_at`, the value to compare with custody.json `disposition.at` (and the
  value the record's `disposition.at` gets) is `decided_at`; fall back to `at` only for a dispose line with no
  `decided_at` (the base form). A real mismatch (custody.json disagrees with the line's decided_at, or a different
  `by`) must still refuse with kind `time` (do not loosen it: bar T5 and J1). Keep the hand-time marking at
  lines 793-798 as it is.

Item E2. Bar T2 (line 65) and INTERFACE.md lines 37-45: a time typed into `inputs/custody.json` with no ledger line
  behind it is a hand time with source `inputs-no-ledger`, and "a pass or control with no typed `at` gets its time
  from a tool" — so a pass or control that DOES carry a typed `at` is a hand time even when a harness call is
  linked to it.
  What your iteration-1 code did: kit/emit_custody.py lines 590-597 mark `passes.<id>.at` as `inputs-no-ledger`
  only in the `elif` branch, when no call is linked; with a linked call a typed `passes.<id>.at` is cross-checked
  but never flagged, so the no-switch run did not refuse it as `hand-time`. Lines 701-712 do the same for
  `controls[<id>].at`.
  Change: flag a typed `passes.<id>.at` / `controls[<id>].at` (field, custody.json line from line_in, source
  `inputs-no-ledger`) whether or not a call is linked; keep the cross-check against the call when one is linked.

Item E3. Bar T7 (b) (line 70) and V3 (line 111): "a call that has no logger `sent_at`/`received_at` is either
  refused as `hand-time` or, under `--allow-hand-times`, listed in `x-plumbline.hand_times[]` with source
  `server-header`/`response-created`". Every call in every harness log the emitter reads counts, for both fields.
  What your iteration-1 code did: kit/emit_custody.py checks only the `received_at` of a linked evaluator call
  (lines 590-594, 701-704) and only the first call's `sent_at` and last call's `received_at` of the Maker log
  (lines 459-468), so every other call's `sent_at` / `received_at` is never named. For example, the evaluator calls in the repo
  fixture tests/fixtures/custody/job-rejected/custody/evidence/harness-eval-a.log have no logger `sent_at` (their
  `created`, lines 18, 57 and 96), and those three `.sent_at` hand times were not listed.
  Change: for every call of every harness log read (Maker and each evaluator), flag each of `.sent_at` and
  `.received_at` that has no logger value, with the source and file:line of the server time used (field names as
  INTERFACE.md line 37: `<log file name>#<call or index>.sent_at` / `.received_at`). Never write anything back to a
  log.

Item E4 (check after E1). Bar X1 (line 102) and F1h (line 82): once the tool-built job emits, confirm the record
  carries `x-plumbline.inputs` as a deep copy of custody.json's `x-plumbline` object (your line 861 does this) and
  `generations[]`, `evaluations[]`, `relays[]`, `amendments[]`, `spend` each with its `inputs/custody-events.jsonl:<line>`
  source. These failed in iteration 1 only because no record was written (E1).

Tests: extend tests/validate_schemas.py (or new fixture folders under tests/fixtures/custody/) so a job built only
with kit/custody_ledger.py (freeze/approve/pin/generation/evaluation/dispose --decided-at) emits exit 0 with no
switch and an empty hand_times, and so E2 and E3 are covered. Never rewrite a file that exists under
tests/fixtures/ at base.
