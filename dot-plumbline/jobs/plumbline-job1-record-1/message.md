The frozen bar is tests/test_job1_fixture_pin.py. Run it:

    python3 tests/test_job1_fixture_pin.py

It is red: Ran 4 tests, FAILED (failures=4). The failures name what is wanted:

  - tests/test_loop_custody_on_finish.py _job() must write custody/bar.md into the temp dir
  - tests/test_loop_custody_sources.py _prepare() must write custody/bar.md into the work dir
  - the sources suite's PREDECESSOR_SHA must follow the moved pin target
  - the predecessor file's bytes must hash to the target the bar names

The bar states the exact bytes and the exact hash it wants. Read it — it is in the tree at
tests/test_job1_fixture_pin.py and it is frozen.

Edit ONLY these two files:
  tests/test_loop_custody_on_finish.py
  tests/test_loop_custody_sources.py

Do not edit the bar, kit/, schemas/, or any other file.
