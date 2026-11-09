The frozen bar is tests/test_loop_freeze_conditional.py. Run it:

    python3 tests/test_loop_freeze_conditional.py

It is red: Ran 4 tests, FAILED (failures=1, errors=2).

  ERROR  test_no_custody_inputs_and_no_convention_bar_skips_freeze
         freeze_bar(record, work) raises RuntimeError: no bar file at .../custody/bar.md;
         cannot freeze before dispatch. A caller that prepares no custody inputs must not be refused.
  ERROR  test_declared_bar_file_is_frozen
         freeze_bar ignores record_dir/inputs/custody.json's bar.file and looks only at the
         convention path.
  FAIL   test_declared_bar_missing_fails_closed
         AssertionError: 'missing.md' not found in 'no bar file at .../custody/bar.md; ...'
         A declared bar that is missing must fail closed NAMING the declared path.
  ok     test_convention_bar_still_freezes — the convention path already works and must keep working.

Your editable file is kit/conductor_loop.py — and only that file. The bar is your read-only
reference: read it and implement what its tests demand. Plant nothing in it.

The rule the bar encodes: freeze_bar reads the declared bar from record_dir/inputs/custody.json's
bar.file first, falls back to <cwd>/custody/bar.md, fails closed when a bar it was told about is
missing, and skips the freeze entirely for a caller that prepared no custody inputs. The ledger
still stamps the freeze; this function types no time.

Rule 12 applies: the red above is what the bar reports, and the bar is the standard.

Do not edit tests/, schemas/, tools/, kit/custody_ledger.py, or any other kit/ file.
