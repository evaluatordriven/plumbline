ONE defect, one file. Defect A is already fixed and committed — do not touch kit/emit_custody.py.

Your editable set is exactly one file, in the dispatch `files` list:

    tests/validate_schemas.py

## THE DEFECT — an Architect ruling, quoted verbatim

    {
      "classification": "standard_moved",
      "repair": "ii",
      "reason": "Making the job-rejected fixture emittable under D6/D7 would require rewriting its evaluator log,
      maker log, custody inputs and event ledger so every hand-entered time matches a logged call, and it would
      still break the E3/T7b case that deliberately exercises missing logger times on that same fixture. Moving
      the emit-success checks to a fixture that already supplies real logger times localizes the break to one test
      file and preserves the existing refusal coverage.",
      "editable_after_ruling": ["tests/validate_schemas.py"],
      "old_assertion": "A model evaluator with no harness log emits a record with a note external about the missing log.",
      "new_assertion": "A model evaluator with no harness log refuses the record instead of taking check times from
      an unsourced or incomplete log.",
      "ruling_ref": "tests/test_evaluator_harness_log.py D6 and D7, approved 2026-11-08"
    }

## THE MECHANISM

tests/validate_schemas.py around line 505:

    rec_path = TMP / "fixture.custody.json"
    rc, out = emit(FIX, rec_path)
    rec = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.is_file() else {}
    res((f"{S} · fixture job emits with no gap (exit 0)", rc == 0, out.strip()[-90:]))
    check(S, "emitted record is valid against the PINNED custody schema", True, rec, V_CUST)
    check(S, "emitted record is valid against the derived Plumbline custody schema", True, rec, V_CREC)
    bad = copy.deepcopy(rec); bad["predicate"]["verdict"] = "reject"

The fixture job at FIX has a MODEL evaluator and no harness log. Under the new contract (D6/D7) the emitter
REFUSES it, so rec is {} and line 510 raises KeyError: 'predicate'.

## WHAT TO DO

Implement repair (ii):

  1. For the FIX fixture (model evaluator, no harness log): assert the REFUSAL. It must not reach the
     deepcopy lines at all.
  2. Move the emit-success checks — "emits with no gap (exit 0)", "valid against the PINNED custody schema",
     "valid against the derived Plumbline custody schema", and the three `bad = copy.deepcopy(rec)` checks that
     follow — onto a fixture that DOES supply real logger times, so the emitter emits a record.
  3. Do NOT delete any check. Do NOT wrap the KeyError in a try/except. The refusal must be asserted positively,
     with the refusal's own text, not by the absence of an exception.

There is already a fixture in the repo that supplies harness-log times: kit/emit_custody.py's expectations and
the corpus battery's own fixtures, plus the shape the frozen bar builds at
tests/test_evaluator_harness_log.py — read that bar for the exact harness-log entry shape
(sent_at, received_at, request.url, response.model) and reuse it.

## WHAT "DONE" MEANS

Run both, and report the numbers:

    python3 tests/test_evaluator_harness_log.py
        -> must stay OK, 12 tests (it is the frozen bar; a change to it is a fail)

    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py
        -> must reach "ALL N CASES BEHAVED AS DESIGNED" and exit 0

Do not edit tests/test_evaluator_harness_log.py, kit/emit_custody.py, kit/evaluator_harness_log.py, or AGENTS.md.
