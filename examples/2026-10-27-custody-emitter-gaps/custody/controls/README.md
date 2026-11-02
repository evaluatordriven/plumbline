# CONTROLS — job 2026-10-27-custody-emitter-gaps

STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z — sha256 in ../MANIFEST.sha256; control bytes pinned by ./MANIFEST.sha256.

Built 2026-10-27 after Owner approval of the sheet ([pt51u] 16:59 EDT, OWNER-APPROVAL-RECORD.md), before the
Maker's first call. Built by the Orchestrator drafter; $0 API, no model call. This file supersedes
CONTROLS-PLAN.md (which was the proposal) where they differ; differences are listed at the end.

## Where the bytes are (P4)
- Bytes: `/workspace/next-job-controls/` (git repo, outside the Maker bot's and Evaluator bot's working trees).
  Every file's sha256 is in `controls/MANIFEST.sha256` (this directory), which is in the freeze set. Builders
  (`build_fixtures.py`, `build_controls.py`, `build_glm.py`, `glm_src/`, `build_p5.py`) are in the same repo at commit `e2a50d4`.
- The Evaluator seat is instructed not to read that directory. Each batch copies
  `/workspace/next-job-controls/controls/` into the batch dir; `run_instrument.sh` checks every file against the
  frozen `controls/MANIFEST.sha256` (paths relative to the controls dir; env `CONTROLS_MANIFEST` overrides its
  location) and exits 3 before running on any difference.
- **Disclosure (separationGaps).** The box is one machine shared by all of the Owner's agents; the directory is
  readable by the Maker bot and Evaluator bot processes. Non-reading is instructed, not enforced. Verbatim text
  for `separationGaps[]`: "Controls and fixtures were held outside the Maker's and Evaluator's working trees
  with sha256 committed at freeze, but on a shared box both bots could technically read them; non-reading
  was instructed, not enforced."

## S1 (`freeze/instrument/run_instrument.sh`)
`run_instrument.sh batch <maker-rev-checkout> <controls copy> <out>` per generation. Exit 0 = every control and
mutant behaved as expected; 1 = a control/mutant miss (batch void, re-run; budget not cap); 3 = custody pin or
check.py sha mismatch. Subject results go to `<out>/subject/*/`, verdicts per check in `<out>/summary.json`.

### Fixtures (held out; `controls/fixtures/`, built by `build_fixtures.py` from round 2's accepted job)
| Fixture | What | Used by |
|---|---|---|
| F-maker-10min | two maker calls; logger `sent_at` 18:23:32.118Z / 18:33:19.660Z, `received_at` 18:23:39.402Z / 18:33:32.517Z (first send → last receive 600 s); `Date` 18:23:32Z and 18:33:32Z; GLM replies present | N1, N2, N3, N7, N8 |
| F-genreply-full | one maker call (logger send 18:23:32.041Z, receive 18:23:32.873Z: same second), GLM pass with `/generation` reply naming the provider | N1, N5 |
| F-genreply-null | same with the GLM pass's `generation` reply null | N1, N4 |
| F-single-call | one maker call; logger send 18:23:29.307Z, receive 18:23:40.912Z; response `created` = `Date` = 18:23:32Z (gap 1's same-second case) | N1 (amendment 1) |
Plus every `<rev>/tests/fixtures/custody/*/` that has `inputs/custody.json` (the Maker's own fixtures).

### Record-level controls (fixed bytes, built against main @ ff350e3 by `build_controls.py`)
| Control | Kind | Targets | Built how | Expected |
|---|---|---|---|---|
| C-N1c | clean | N1 | main's record on F-single-call + `mutate.py logger-times` (startedAt 18:23:29Z, producedAt 18:23:40Z) | PASS |
| C-N1p | planted | N1 | main's record on F-single-call unchanged (startedAt = producedAt = 18:23:32Z) | FAIL |
| C-N1p2 | planted | N1 | C-N1c + `mutate.py produced-eq-started` (equal times though the log's send ≠ receive) | FAIL |
| C-N2c | clean | N1, N2 | main's record on F-maker-10min | PASS, PASS |
| C-N2p | planted | N1, N2 | same, `mutate.py produced-eq-started` | FAIL, FAIL |
| C-N3c | clean | N3 | main's record on F-maker-10min + `mutate.py time-sources` (every field → its ledger/log line) | PASS |
| C-N3p | planted | N3 | same, `--misdirect /producedAt` (source = first maker call's Date line, 18:23:32 not 18:33:32) | FAIL |
| C-N3p0 | planted | N3 | main's record unchanged (no sources) | FAIL |
| C-N4c | clean | N4 | synthetic refusal outcome: exit 3, stderr names pass-1 / call | PASS |
| C-N4c-b | clean | N4 | main's record on F-genreply-null + `mutate.py flag-null` + real check.py | PASS |
| C-N4p | planted | N4 | main's real outcome on F-genreply-null (endpoint written, CL1-15 OK, no flag) | FAIL |
| C-N5c | clean | N5 | main's record on F-genreply-full | PASS |
| C-N5p | planted | N5 | same, `mutate.py endpoint --seat eval-glm --host api.z.ai` (replies name api.wafer.ai) | FAIL |
| C-N9c | clean | N7, N8 | main's bundle + `mutate.py bundle-add` of the ledger and maker log | PASS, PASS |
| C-N9p | planted | N7, N8 | C-N9c with `bundle-drop --name custody-events.jsonl` | FAIL, FAIL; check.py OK |
| C-N9p0 | planted | N7, N8 | main's bundle unchanged | FAIL, FAIL |
| C1 | clean+planted | check.py | custody's 17 checker fixtures @ 3e3ca58 (`controls/checker`) | as its expected.json |
Records carry `emittedAt`, so the committed bytes are the controls; a rebuild is not byte-identical.

### Per-batch mutants of the Maker's output (built in the batch; recorded in `controls[]` under the bar's ids)
Exact recipes (`freeze/instrument/mutate.py`, deterministic; zips rebuilt sorted, 1980-01-01, mode 0644):
| Bar id | Batch dir | Recipe | Expected |
|---|---|---|---|
| C-N1p | `mutants/M-N1p` | `mutate.py produced-eq-started` on `subject/F-single-call/record.custody.json` | N1 FAIL |
| C-N2p | `mutants/M-N2p` | `mutate.py produced-eq-started` on `subject/F-maker-10min/record.custody.json` | N1 FAIL, N2 FAIL |
| C-N5p | `mutants/M-N5p` | subject's F-genreply-full emit outcome (record with endpoints written, exit 0) judged against the F-genreply-null job | N4 FAIL |
| C-N9p | `mutants/M-N9p` | `mutate.py bundle-drop --name custody-events.jsonl` on `subject/F-maker-10min/bundle.zip` | N7 FAIL, N8 FAIL, check.py OK |
Digest procedure: after building, `run_instrument.sh` writes `<out>/mutants/SHA256SUMS` (sha256 of every mutant
file); the Evaluator bot files that file with the batch evidence and its sha256 goes in the batch's
`controls[]` entries. A mutant that does not get its expected verdict voids the batch (exit 1).

### Interface shapes S1 accepts (so the instrument is no stricter than the bar)
- N1/N2 times (amendment 1): only the Maker harness log's `sent_at` (first call) and `received_at` (last
  call), as `freeze/harness/or_call.py` writes them, compared at whole seconds UTC (fractions truncated on
  both sides). Ledger rows, response `created` and `Date` are not used. A call without both is a FAIL.
  N8 compares the stranger re-derivation the same way.
- N3 sources: `x-plumbline.timeSources` | `time_sources` | `times` (first present). Keys: JSON pointer, dotted
  or bracket path (`predicate.` prefix optional). Values: `{file|name|path|log, line|lineno|line_number}` or
  `"file:N"`, `"file#LN"`, `"file line N"`. File = the ledger or a `harness-*` log; the line must carry the
  same instant (ISO 8601, RFC 7231, or 10-digit epoch).
- N4 (b) flag: any entry of `x-plumbline.flags` | `gaps` | `warnings` containing "generation" and naming the
  pass id (whole token) or the call.

## P5(e) — `freeze/instrument/p5check.py` (amendment 2)
`p5check.py --job J [--record R]`, run by `run_instrument.sh` on every control below in every batch, and on the
real job folder after the ledger freeze. Each control is a synthetic job folder (`controls/p5/<id>/`, built by
`build_p5.py`, byte-identical on rebuild): one ledger freeze event at 18:23:23Z naming `custody/frozen/bar.md`,
a frozen set with `FROZEN-BUILD` headers, and a record carrying `predicate.bar.digest.sha256`.
| Control | Kind | Built how | Expected |
|---|---|---|---|
| C-P5c | clean | headers 18:23:00Z ≤ freeze; ledger and record digest = sha256(bar.md) | PASS |
| C-P5p | planted | ledger freeze `bar_sha256` = digest of a different bar | FAIL |
| C-P5p2 | planted | headers 18:24:00Z, later than the freeze | FAIL |

## E-GLM (N6) — `freeze/instrument/n6_batch.py` + `freeze/instrument/rubric-N6.md`
Each batch: subject + G-c1 + G-p1, same rubric/model/params/pin, seeded random order (`n6-batch-<N>`), the
subject unmarked; one harness log per batch. Score 1 iff subject CONFORMS and both controls as expected.
| Control | Kind | Content (`controls/glm/`, built by `build_glm.py` from `glm_src/`) | Expected |
|---|---|---|---|
| G-c1 | clean | synthetic minimal two-file reply path: null generation reply → flag naming the pass, no endpoint | CONFORMS |
| G-p1 | planted | G-c1 with an inserted branch: reply null and response `provider` matches the pin → `host = pin.get("host")` | DOES_NOT_CONFORM, citing kit/emit_custody.py:16–19 |
A control miss voids the batch (re-run; budget not cap).

## Differences from CONTROLS-PLAN.md (the proposal)
- Record-level controls are mutations of main's **output** (records, outcomes, bundles), not emitter code
  mutants; per-batch planted controls are mutations of the Maker's output by the recipes above.
- Fixture times are 18:23:32Z / 18:33:32Z (from round 2's accepted job), not 12:00 / 12:10.
- Plan C-N5p (null fixture + emitter filling the endpoint → N4 FAIL) is batch mutant M-N5p and fixed C-N4p;
  fixed C-N5p instead plants a wrong endpoint on the full fixture (N5 FAIL). C-N3c/p/p0 and C-N4c-b are added.
- C1 has 17 checker fixtures, not 16.

## Amendment 1 (Owner decision 2026-10-27 17:31 EDT; ../AMENDMENT-1.md)
- N1 reads the call logger's send/receive times; the "equal if exactly one Maker event" exemption is gone
  (equal only if the log's send = receive). Fixture logs now carry `sent_at`/`received_at`.
- Added F-single-call, C-N1c, C-N1p, C-N1p2 and per-batch mutant M-N1p; `mutate.py logger-times` added.
- Every record-level control was rebuilt against the rebuilt fixtures (new bytes, new MANIFEST.sha256).

## Amendment 2 (Owner decision 2026-10-27 17:50 EDT; ../AMENDMENT-2.md)
- Frozen-file headers read `FROZEN-BUILD <build time>` (was `FROZEN <frozenAt>`); P5(e) is checked by
  `p5check.py`: build time ≤ ledger freeze time, sha256(bar.md) = ledger freeze digest = record bar digest.
- Added `controls/p5/` (C-P5c, C-P5p, C-P5p2) and `build_p5.py`. No other control changed.
