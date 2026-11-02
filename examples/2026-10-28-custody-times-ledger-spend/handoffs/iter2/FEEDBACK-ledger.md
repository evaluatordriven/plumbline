ITERATION 2 FEEDBACK, part ledger (kit/custody_ledger.py, kit/custody_history.py, tests/test_custody_ledger*.py)

The files shown above are YOUR iteration-1 files as committed (base 3df1ce5 + your iteration-1 parts). Most of
this part passed the evaluator's checks (T1, F1b's own bounds, F1c, F1e, F1g all passed). Keep that work: change
only what the items below need, and return every file you change in full. Do not rewrite passing code.

Item L1. Bar F1a (bar.md line 75) and F1d (bar.md line 78); INTERFACE.md lines 15-16 and 22.
  Requires: every refusal "exits non-zero (2 = usage, 3 = refused), prints a line starting `REFUSED:` on stderr,
  and changes neither the ledger nor `custody.json`". With `--summary`, the `evaluation` line carries
  `summary_file, summary_sha256, started_at, finished_at, summary_writer` copied from the summary's own stamp, and
  a summary with no stamp is refused.
  What your iteration-1 code did: kit/custody_ledger.py lines 211-212 declare `--verdict` as `required=True`, so an
  `evaluation` call that names `--summary FILE` and no `--verdict` stops in argparse (exit 2, stderr
  "error: the following arguments are required: --verdict", no `REFUSED:` line). The stamped-summary path was
  therefore never reached: no line was appended, so no summary_sha256 / started_at / finished_at / summary_writer,
  and a summary with no stamp was not refused with `REFUSED:`.
  Change: (a) accept `evaluation ... --summary FILE` without `--verdict` (INTERFACE.md line 6: anything not named
  there is your choice); when `--verdict` is absent, the summary file is also the verdict file (`verdict_file` and
  `verdict_sha256` name it). Keep `--verdict` alone and `--verdict` + `--summary` working exactly as now.
  (b) every usage error of every command (argparse errors included) must still exit 2 AND print a line starting
  `REFUSED:` on stderr, with the ledger and custody.json byte-identical.

Item L2. Bar P1 (bar.md line 101): "a log entry from the subject's `or_call.py` (mocked) has every key that job 1's
  frozen harness writes, and `custody_history.read_log` reads it."
  What your iteration-1 code did: kit/custody_history.py line 219 `def read_log(path: Path, ref: Refusals, who:
  str)`; called with only the log path it raises TypeError (missing `ref` and `who`), so the read failed.
  Change: make `ref` and `who` optional (`ref: Refusals | None = None, who: str = "log"`; a fresh Refusals() when
  None) so `read_log(path)` works and returns the calls. Every existing caller keeps working unchanged. Do not
  change TOLERANCE_S or any cross-check (bar T5, line 68; INTERFACE.md section 6).

Tests: add or extend tests/test_custody_ledger*.py for L1 (a, b) and L2. Every base test must keep its base
result; every new test must pass (bar G2, line 123).
