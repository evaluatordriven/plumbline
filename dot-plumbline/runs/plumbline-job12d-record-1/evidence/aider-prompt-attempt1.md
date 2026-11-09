Frozen-mechanism repair: make the reader's silent skip visible so a harness log that carries no stamped
call cannot be read empty.

FROZEN (do not edit):
  - kit/emit_custody.py     (the emitter under test)
  - kit/evaluator_harness_log.py
  - tests/**               (frozen test battery)

EDITABLE:
  - kit/custody_history.py  (reader + time helper)

Run this from the work tree:
  EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/test_evaluator_harness_log.py

The two failures are real. Each produces a record whose predicate says the evaluator's check time (or the
offending call) is unmeasured — the check `at`, the dimension's verdict, and the record's `evaluator_log` are
all None. Root cause: the emitter reads the harness log with `harness_log.read(log, allow_unstamped="skip")`
(emit_custody.py ~line 1392). When a model evaluator's call carries only a `Date` header with no logger
`sent_at`/`received_at`, the reader SILENTLY drops that call (SkipUnstamped), returns an empty call list, and
`_stamped` comes up empty. `ev_log` then returns None and the dimension has no evidence at all.

The spec is the two failing tests — read them, they say exactly what the record must say:

  tests/test_evaluator_harness_log.py:298-306  test_d13_switch_does_not_admit_an_unsourced_evaluator_time
    D13: under --allow-hand-times an unsourced model-evaluator time is STILL refused, naming the log, and NO
    record is written.
  tests/test_evaluator_harness_log.py:308-319  test_d14_switch_refusal_names_every_unstamped_call
    D14: the naming E3 survives the switch on a log with THREE calls (dim1#p1, dim1#p2, dim1#p3) — every call
    must be named (`dim1#p1`, `dim1#p2`, `dim1#p3`), and the unstamped field is named (`.sent_at`). It must NOT
    abort at the first unstamped entry. Each assertion:
      - line 316  notEqual(returncode, 0) — an unsourced evaluator time was admitted
      - line 317  for n in (1,2,3): assertIn(f"dim1#p{n}") — a call was not named
      - line 318  assertIn(".sent_at") — the unstamped field is not named

What the record must carry on the fix (so the fix is verifiable against the frozen test):
  - D6 guard (emit_custody.py ~1373, `else:` when the caller does not pass one, at the start of
    `ev_evaluator_evaluator_times`) must refuse on MISSING log; the fix cannot satisfy the bar by keeping that
    guard but letting an empty read pass.
  - The fix makes the silent drop loud: when the reader's allow_unstamped="skip" returns no calls (or fewer
    than expected), either (a) refuse by naming the log, or (b) re-read with allow_unstamped="keep" and name the
    unstamped entries. Either way the refusal must name the harness log and, under the switch, every call that
    the skip masked (e.g. `dim1#p1`, `dim1#p2`, `dim1#p3`).

Do NOT touch the bar. Do NOT change which tests exist. Keep D6-D12 green (esp. test_d3, test_d4, test_d5 keep
`harness-eval.log` in time_sources; the happy-path reader is unaffected as long as its callers pass their own
allow_unstamped). Do NOT write the emitter fix by hand — the emitter is frozen; edit the reader/history layer.
