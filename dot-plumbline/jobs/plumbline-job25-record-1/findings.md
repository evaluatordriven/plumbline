# Job 25 — findings for the Maker (generation 1)

## The red, measured at db9d6b7 by the Orchestrator with the corpus required

    [PASS] JOB25 a1 a hand time 59 s off is accepted, and the record carries the LOG's time
    [PASS] JOB25 a2 T2c a time typed into custody.json with no ledger line is named
    [PASS] JOB25 a3 T3 with --allow-hand-times the record is written and hand_times lists the hand fields
    [PASS] JOB25 a4 E2 under --allow-hand-times the typed pass time is listed and the record carries the call's time
    [FAIL] JOB25 b1 an evaluator check time the logger never stamped is REFUSED under --allow-hand-times (exit != 0, nothing written)
                 exit 0; record written=True
    [FAIL] JOB25 b2 ...and names EVERY such call BY ID (not only the first)
                 log carries ['eval_artifact','eval_k1','eval_k2']; the refusal named []
    [FAIL] JOB25 c1 the boundary: --allow-hand-times admits a typed time and does NOT admit an unstamped evaluator check time
                 typed admitted=True; unstamped refused=False
    [FAIL] JOB25 d1 any record written under the switch gives every called check its OWN at_source (no collision, none blank)
                 called checks: ['harness-eval-a.log:37','harness-eval-a.log:37']; shared: ['harness-eval-a.log:37']
    PLUMBLINE-TALLY 137/141 PASSED — 4 FAILED

## Rule 12 — every known defect and its measurement

1. The fixture `tests/fixtures/custody/job-rejected` carries NO logger `sent_at`/`received_at` on its three evaluator
   calls. Each call carries `response.created` and a `Date` header ONE SECOND APART:
     eval_artifact  created 12:00:02Z  Date 12:00:03Z
     eval_k1        created 12:01:01Z  Date 12:01:02Z
     eval_k2        created 12:02:04Z  Date 12:02:05Z
   A linked model check's time is the Date header (call.at = received_at or Date or created).
2. The switch `--allow-hand-times` currently admits an unsourced evaluator check time. It must admit a TYPED time and must
   NOT admit a model evaluator's unstamped check time.
3. The hollow record: under the switch the emitter exits 0 and writes a record whose check times are not sourced —
   at db9d6b7 two different checks share the single at_source `harness-eval-a.log:37`.
4. The fix must end both faces: the misread clock AND the hollow record.
5. a1-a4 are main-green behaviours from PR 24's regression set. They must STAY green. Do not touch them, and do not edit
   tests/validate_schemas.py — it is frozen.
6. d1 is vacuously green only if the fix refuses the log and writes nothing; it forbids the other repair, a record sourced
   from the wrong call. A fix that writes a record with a shared at_source fails d1.

## Editable set

    kit/emit_custody.py
    kit/custody_history.py

Nothing else. tests/validate_schemas.py is frozen. Commit is not yours — the Orchestrator commits before measuring.

## Cost

If you measured a cost, write {"amount": N} to the cost file. If you did not, do not invent it.
