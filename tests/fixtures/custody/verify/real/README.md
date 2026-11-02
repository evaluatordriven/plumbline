# SYNTHETIC FIXTURE — the record custody's real checker reads

This folder is what `tests.test_plumbline_verify.VerifierKindTests.test_clean_against_real_checker` runs through
custody's real `checker/check.py` (custody @ `3e3ca58de5631bdc58291564303a2e9d25a8653e`, via `CUSTODY_DIR`), both
directly and through `kit/plumbline_verify.py`. It is not evidence of any real job or reading.

- `job/` is a byte-for-byte copy of `tests/fixtures/custody/job-rejected/` (synthetic: every name, time, score
  and approval in it is invented; see `job/README.md`). It carries its own frozen bar at `job/custody/bar.md`,
  the subject under `job/custody/files/`, and the evidence under `job/custody/evidence/`. The job's disposition
  is a rejection; that is the *job's* verdict. The custody record itself is well formed and the checker accepts it.
- `record.custody.json` was emitted, not written by hand, from a clean Plumbline checkout at
  `9369219c478d1b3cf80918facba3bb75ba7307d8`:

      python3 kit/emit_custody.py --job-dir <copy of job/> --out record.custody.json --allow-hand-times

  Its `x-plumbline.emitter` block names that commit, its tree and `dirty: false`.
- **Hand times, flagged.** The synthetic event ledger has no live writer, so the emitter refused its times until
  `--allow-hand-times` was given. The record says so: `x-plumbline.allowances.hand_times` names the switch, and
  `x-plumbline.hand_times[]` lists every time that came from the ledger without a writer. Plumbline never
  verified those times; the real checker does not judge them.

To regenerate it, copy `job/` to a scratch directory and rerun the command above from a clean checkout. The
`emitter` block and the allowance timestamp then change, and the test still holds as long as the checker's
verdict is `OK` and each subject digest matches `job/custody/files/`.
