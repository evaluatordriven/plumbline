# Amendment 2 (post-freeze, Owner): T6 scoring of the job-rejected fixture and the null-generation refusal, job 2026-10-28-custody-times-ledger-spend

| Field | Value |
|---|---|
| Decided by | Steve Moitozo II (Owner, Buyer, Specialist-adopter), acting as Owner |
| Decision words, verbatim | "Amend T6: exclude the job-rejected fixture from N1, and count the correct refusal of the null-generation fixture as a run." |
| Decision when / channel | 2026-10-29 09:23 EDT (America/New_York, UTC-4) = 2026-10-29T13:23Z. Steve's answer to a card in the Grok Bot chat with Chief of Staff (Orchestrator). Witnessed by the Orchestrator; relayed word for word to the helper that drafted and filed this file, which did not witness it. The Orchestrator confirmed the words against Steve's message. Card id not relayed; seconds not relayed. |
| Filing approval words, verbatim | "Yes, file Amendment 2 as recommended: separate check, code kept out of the job folder, job-rejected pinned by log hashes. Then take iteration 3 to the Architect." |
| Filing approval when / channel | 2026-10-29 09:31 EDT (UTC-4) = 2026-10-29T13:31Z. Steve's message in the Grok Bot chat with Chief of Staff (Orchestrator). Witnessed by the Orchestrator; relayed word for word to the filing helper. No message id relayed; seconds not relayed. |
| Amends | How check T6 (bar.md line 69, "The prior job's N1–N8 procedure … passes on the subject") is **scored**: the frozen judge `j_T6` (custody/freeze/instrument/judges.py, lines 156–169) and the observation `d_T6` collects (drivers.py, lines 245–263). Nothing else. It does not change the frozen bytes. |
| Frozen set | This amendment is not in the frozen set. custody/bar.md (sha256 `72e92dc7580e2447f19dfff66aaac02d8484157a6283dcfdda6c7bb2de7561c6`), custody/MANIFEST.sha256 (`acdf764b32bab5e0fa4615590714c49162cbbaecddd00c03c6d8121b59b85d98`) and every MANIFEST-listed file are unchanged; `(cd custody && sha256sum --quiet -c MANIFEST.sha256)` is silent. The ledger freeze event still matches the bar digest. |

## Why (instrument/bar conflict)
T6 re-runs the prior job's frozen N1–N8 procedure on this job's subject. Two of its terms cannot both hold for a
correct subject:

1. **N1 vs the job-rejected repo fixture.** T6 runs every repo fixture under tests/fixtures/custody/ as an extra
   run. The fixture `job-rejected` has Maker and Evaluator logs with no logger `sent_at`/`received_at`, by design:
   it is hand-typed, which is why T6 runs with `--allow-hand-times`. The pinned prior `ncheck.py` N1 fails any
   record whose Maker log lacks logger times, with no exception for allowed hand times. So N1 fails on that run
   for every subject, including a correct one. What the bar asks instead stays required: each such field is
   flagged in `x-plumbline.hand_times`, and the verifier reads the record OK.
   In batch 2 (subject c8826468), N1 failed only on the job-rejected run ("missing logger times") and passed on
   every other run. The same N1 failure on this fixture was already recorded in the prior job
   (2026-10-27-custody-emitter-gaps, fu-3.json).
2. **Minimum runs vs N4.** `j_T6` counts only the runs that wrote a record against the frozen minimum. The prior
   bar allows two ways to handle the prior job's null-generation fixture (the one N4 scores):
   - (a) refuse with a non-zero named error and write no record;
   - (b) write a record with CL1-15 NOT-CHECKABLE and a flag.
   A subject that takes (a) passes N4 but is one record short of the minimum, so T6 fails it for a path N4 allows.
   In batch 2 the subject refused with a named error (exit 3) and N4 passed in mode "a (refusal)".

Neither failure is a Maker defect. Re-trying them would spend iterations and trip the repeat-failure tripwire
because of an instrument conflict.

## What changed (T6 scoring only)
- **N1:** the per-run N1 verdict is ignored for one run only: the repo fixture `tests/fixtures/custody/job-rejected`.
  That run must match both pins:
  - its run name is `extra-<n>-job-rejected` (exact match);
  - its `custody/evidence/*.log` files are exactly these two:
    - `harness-maker-fixture.log`, sha256 `59dba98a07c615e00792fa54c742ada79c8fdcc8caa0a1f9adf7883139cc2b6a`;
    - `harness-eval-a.log`, sha256 `1190223bbf91a3be8e80a5b2b67ace443d31012f19527dcf89358f5133e22901`.

  These are the fixture's bytes at base 3df1ce5 and at subject c8826468. If any byte, name or extra log differs,
  the run is not excluded. Every other run's N1 must be PASS, and every written record outside the excluded run
  must have an N1 result. All other N scores (N2, N3, N4, N5, N7, N8) must still be 1.
- **Minimum runs:** a run counts if it wrote a record. One more run counts: the null-generation fixture's run,
  if it wrote no record, exited with a code other than 0 or 1, and N4 passed in mode (a) refusal. No other
  refusal counts.
- **Unchanged inside T6:**
  - the prior procedure exits 0, with its controls and mutants as expected;
  - for every written record, including the job-rejected record, every field flagged without the switch is in
    `x-plumbline.hand_times`, and `kit/plumbline_verify.py` exits 0 on it. The job-rejected record's missing
    logger times must therefore still be flagged as hand times, and the record must still verify.
- An observation without the new fields is scored by the original rule. This covers any earlier evidence/T6.json
  and the frozen judge-level control `controls/obs/T6.planted.json`.

## Overlay (code kept out of the job folder)
The overlay files live in `/workspace/edi-work/2026-10-28-custody-times-ledger-spend/amendment-2/` on the
Orchestrator's box. They are not in this repository and are not shown to the Maker. sha256:
- `amend2_t6.py` (the overlay re-scorer): `668a0357d75623afbc5caad81d17ee1d3eade97581f2283acfa0f8166dfb8a47`
- `amend2-instrument.diff`, a unified diff against the frozen drivers.py (`d_T6`) and judges.py (`j_T6`) that
  serves as the logical specification: `d5cce32b8c8ad232869ed11a5fcd9d8cca3f02780757694e1281cc44b4fe1dfe`
- `patched/judges.py`, i.e. the frozen judges.py with the diff applied, which `amend2_t6.py` pins and imports:
  `1c3276a708b35a6acab11be41def23cfb34fad13990b931f5d45323b35377673`
- `patched/drivers.py`, i.e. the frozen drivers.py with the diff applied:
  `86f2f1de24b93bcf9450c6c3f1d47c4d593d7b4189f9dae3ac317d81f4184643`
- `check_amend2.py` (the filing check): `6a140290df48be69e6f218eba28c485d7c02b36ef88daf70a27a2ba99d2fb4b5`
- `check_amend2.out` (its output): `02ab6095a7abb1618aaa8f674873f2ffad24d254e25d74c1ab09a1038d294822`

## How the Evaluator applies it
- The bar digest, MANIFEST.sha256, the ledger freeze event and the bar all stay unchanged. No re-freeze.
- The Evaluator runs the frozen `scheck.py` unchanged. On the same S1 run dir it then checks the overlay shas
  above and runs `amend2_t6.py <S1 run dir> --json <S1 run dir>/evidence/T6-amend2.json`.
  - The script refuses to run unless `patched/judges.py` has the pinned sha.
  - It rebuilds the T6 observation from the frozen `evidence/T6.json` and the prior procedure's own output
    files, i.e. files the frozen run already wrote.
  - It makes no model calls and does not re-run the subject.
- The report gives both the frozen T6 verdict and the amended T6 score. **The pass rule uses the amended T6
  score.** The S1 count is reported both ways, e.g. "S1 n/39 frozen; n'/39 under Amendment 2".
- The Evaluator re-runs `(cd custody && sha256sum --quiet -c MANIFEST.sha256)`, which must be silent.

## Check at filing (no model calls, scratch copies of batch 2's T6 output)
- The frozen control `T6.planted.json` still fails. The batch-2 observation without the new fields still fails
  with its original reasons.
- **Batch-2 output under the amended judge: fails.** The only reasons left are "verify exit 3 ['standard']" on
  the four written records (the verifier did not pass the bar to the checker, an iteration-3 item). The N1 and
  minimum-runs reasons are gone. With every verify forced to 0, which isolates the amended terms, it passes.
- **Negative controls, every one fails as required:**
  - Logger times stripped from a non-excluded run's Maker log, then scored with the pinned prior `ncheck.py n1`:
    N1 FAIL, and the amended T6 fails. A real record missing logger times is still caught.
  - The right run name with a wrong log hash.
  - The right run name with an extra evidence log.
  - The pinned logs under a different run name.
  - A look-alike run name.
  - The job-rejected record with its hand times not listed.
  - The job-rejected record rejected by the verifier.
  - The null-generation refusal with N4 FAIL.
  - The null-generation run exiting 0.
  - A different fixture refusing.
  - A written record with no N1 result.
  - Another N check at 0.

## Unchanged
Every other check, threshold, control, pin, seat, the allow-list, the money terms (under US$5.00, US$0.10
reserve), the cap of 3, the Amendment 1 clock bound (ends 2026-10-29 14:21 EDT), the output contract and the
no-throttling rule all stay as they were.

## Ledger
One `amendment` line is appended to inputs/custody-events.jsonl by hand, because base kit/custody_ledger.py @
3df1ce5 has no `amendment` command. Its fields follow INTERFACE.md line 23 plus `hand_appended: true`, in the same
format as the Amendment 1 line.
