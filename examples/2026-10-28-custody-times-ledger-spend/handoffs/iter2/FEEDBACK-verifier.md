ITERATION 2 FEEDBACK, part verifier (kit/plumbline_verify.py, schemas/x-plumbline/x-plumbline-v1.schema.json,
kit/plumbline_job.py, tests/test_plumbline_verify*.py, new folders under tests/fixtures/custody/)

The files shown above are YOUR iteration-1 files as committed. The schema file, the no-write behaviour, the close
wiring in kit/plumbline_job.py (`NOT CLOSED: Plumbline verify failed (<kind>)`, the `close_refused` row, the
`--allow-hand-times` pass-through) and most kind logic are kept: change only what the items below need. Most of
V1-V6 and V8 could not be scored in iteration 1 because the emitter wrote no record on tool-built jobs (being fixed
in the emitter part); the items below are the verifier's own faults.

Item R1 (the standard layer). Bar V1 (bar.md line 109): the verifier "runs [the pinned checker/check.py] on the
  record at the claimed level, and requires OK before anything else"; bar T6 (line 69) requires the verifier to
  read each emitted record OK. The pinned checker's command line is
  `check.py RECORD --files FILES_DIR --evidence EVIDENCE_DIR [--bar BAR]`, exit 0 OK, 1 FAILED, 2 not checkable; it
  has no `--level` flag (it reads the claimed level from the record).
  What your iteration-1 code did: kit/plumbline_verify.py lines 727-764 (`standard_check(record, custody)`) try four
  invented forms (`RECORD --level L`, `--record RECORD --level L`, `RECORD L`, `--level L RECORD`) and never pass
  `--files`/`--evidence`, so a valid record fails as kind `standard` (exit 3) and nothing else is checked.
  Change: pass the verifier's own `--files` and `--evidence` values through: run
  `[sys.executable, check.py, RECORD, "--files", FILES, "--evidence", EVIDENCE]` once (no guessing forms); exit 0 =
  OK; any other exit = kind `standard`, exit 3. Keep the pin check (exit 2 on a missing or wrong-bytes checker)
  exactly as it is.

Item R2. Bar V7 (line 115): "`kit/plumbline_verify.py` does not import `kit/emit_custody.py` (static import check;
  it may use `custody_history.read_log` to parse logs)".
  What your iteration-1 code did: kit/plumbline_verify.py line 346 carries the emitter's path as a string literal
  (`startswith("kit/emit_custody.py@")`); the static check reads that as a reference to the emitter and exits 2.
  Change: remove every reference to the emitter's module or path from kit/plumbline_verify.py. Do not split, join,
  encode or otherwise disguise the string; that would be the same reference. Check the allowance's `writer` by form
  only (`<relative .py path under kit/>@<12 lowercase hex>`, not `hand`), and keep failing kind `allowance` when the
  allowance is missing, has the wrong switch, a malformed writer, or no tool-clock `at`.

Item R3. Bar V9 (line 117): "`tests/test_plumbline_verify*.py` covers every kind in V1-V8 with repo fixtures in new
  folders."
  What your iteration-1 tests did: no test names kinds `allowance`, `flag-without-source`, `hand-time-unflagged`,
  `relay-as-approval` or `standard`, and no new fixture folder was added under tests/fixtures/custody/.
  Change: add repo fixtures in NEW folders under tests/fixtures/custody/ (never touch a base fixture) and tests
  that assert each kind the verifier prints (`standard`, `schema`, `allowance`, `hand-time-unflagged`,
  `flag-without-source`, `events`, `relay-as-approval`, `spend`, `shadow`, and exit 2 for a wrong-bytes checker),
  plus one clean record that reads exit 0. Build the fixtures with your own tools; keep them small.

Item R4 (check after the emitter fix). Bar V8 (line 116): on a clean tool-built job, `kit/plumbline_job.py close`
  must exit 0 and write the `closed` row; on a verifier failure it exits with the verifier's code, prints
  `NOT CLOSED: Plumbline verify failed (<kind>)` with the verifier's first failure kind, writes `close_refused`, and
  no `closed` row. Your iteration-1 wiring for this is kept; make sure a test covers both outcomes.

Every base test must keep its base result; every new test must pass (bar G2, line 123).
