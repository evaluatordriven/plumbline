The frozen bar is tests/test_evaluator_harness_log.py — it is GREEN. Do not break it. Two other defects are yours.

Run the whole suite before you finish, exactly as CI does, WITH the corpus:

    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/run_all.py

It is currently RED: pass=9 fail=3. Two of those three are yours.

## DEFECT A — kit/emit_custody.py, the sibling import

kit/emit_custody.py:84 does:

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import custody_history as H
    import evaluator_harness_log as harness_log

That resolves when the emitter is run as a script, and fails when kit.emit_custody is imported as a package
member. Under the suite it raises:

    ModuleNotFoundError: No module named 'evaluator_harness_log'

and six tests in test_plumbline_verify fail because of it (SpendWithoutSpendLineTests, TypedStartedProducedTests).

The repo's own cross-module pattern is kit/conductor_loop.py:66:

    from kit import conductor_software

Follow how the rest of kit/ imports siblings. It must resolve under BOTH launch shapes: run as a script, and
imported as kit.emit_custody.

## DEFECT B — tests/validate_schemas.py, standard_moved

The Architect has ruled on this one. Verbatim ruling:

    classification: standard_moved
    repair: ii
    reason: "Making the job-rejected fixture emittable under D6/D7 would require rewriting its evaluator log,
    maker log, custody inputs and event ledger so every hand-entered time matches a logged call, and it would
    still break the E3/T7b case that deliberately exercises missing logger times on that same fixture. Moving
    the emit-success checks to a fixture that already supplies real logger times localizes the break to one test
    file and preserves the existing refusal coverage."
    old_assertion: "A model evaluator with no harness log emits a record with a note external about the missing log."
    new_assertion: "A model evaluator with no harness log refuses the record instead of taking check times from an
    unsourced or incomplete log."
    ruling_ref: "tests/test_evaluator_harness_log.py D6 and D7, approved 2026-11-08"

The mechanism, tests/validate_schemas.py:505-510:

    rec_path = TMP / "fixture.custody.json"
    rc, out = emit(FIX, rec_path)
    rec = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.is_file() else {}
    ...
    bad = copy.deepcopy(rec); bad["predicate"]["verdict"] = "reject"

FIX has a model evaluator and no harness log, so under the new contract emit refuses, rec is {}, and line 510
raises KeyError: 'predicate'.

Implement repair (ii): assert the refusal for THAT fixture, and move the emit-path checks onto a fixture that
can actually emit. Do NOT delete the check. Do NOT swallow the KeyError.

## YOUR EDITABLE SET — exactly two files, both in the dispatch `files` list

    kit/emit_custody.py
    tests/validate_schemas.py

Nothing else. Do not edit kit/evaluator_harness_log.py, do not edit tests/test_evaluator_harness_log.py (it is the
frozen bar and it is green), do not edit AGENTS.md, and do not touch the profile directory.

## WHAT "DONE" MEANS

Both of these, run by you before you stop:

    python3 tests/test_evaluator_harness_log.py                      -> must stay OK, 12 tests
    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/run_all.py

Note: on this host validate_audit may fail for a host reason (it scans tmp/*/dot-plumbline/audits/ for local
census records). That one is NOT yours and you must not "fix" it. Everything else must pass.
