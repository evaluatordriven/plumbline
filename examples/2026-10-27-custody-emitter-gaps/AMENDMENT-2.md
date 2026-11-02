# Amendment 2 to the approved sheet: job 2026-10-27-custody-emitter-gaps

| Field | Value |
|---|---|
| Decided by | Steve Moitozo II (S2: Owner, Buyer, Specialist-adopter) |
| Words, verbatim | "Amend P5(e) so headers carry the build time and the ledger's freeze event matches the bar digest; bring me the new digest" |
| When | 2026-10-27 17:50 ET (America/New_York, UTC-4), i.e. 2026-10-27T21:50Z |
| Channel | Grok Bot private chat (relayed to the drafter by the Orchestrator; message id not relayed) |
| Amends | the freeze set of commit 73a1485 (bar digest d1b8694f5d024442c0e1343b360d15066ca182d0b44dd9962224994bef745372, MANIFEST f6389624c228e645058c0b29e4973b93c6177ad1ad8fa961fe27c5149d521404) |

## Why
P5(e) required the frozen headers to read `FROZEN <frozenAt>`, the record's `bar.frozenAt`. But
`kit/custody_ledger.py freeze` stamps the freeze at the moment it runs and the emitter takes `bar.frozenAt`
from that ledger event. The headers are inside the hashed bytes that the freeze then pins, so they must be written
before the freeze and cannot carry the ledger's time. As written, P5(e) could not be met. Found while verifying the
17:40 ET freeze approval; nothing was frozen or opened.

## What changed
- **P5(e) (bar.md):** the frozen files (`bar.md`, `bounds`, `controls/README.md`, and the `freeze/harness` and
  `freeze/instrument` files) carry a header `FROZEN-BUILD <build time>`. The build time is no later than the
  ledger freeze event's time. sha256 of the frozen `bar.md` equals the ledger freeze event's `bar_sha256` and the
  record's bar digest. S1 checks this with the new `freeze/instrument/p5check.py`.
- **Controls** (controls repo commit e2a50d4, `build_p5.py`, `controls/p5/`): C-P5c clean (expect PASS), C-P5p planted
  (the ledger freeze digest differs from bar.md; expect FAIL), and C-P5p2 planted (build time later than the freeze;
  expect FAIL). `run_instrument.sh` runs them in every batch. All 3 behave as expected (DISCRIMINATION.txt).
- **Headers** were restamped `FROZEN-BUILD 2026-10-27T21:53:35Z` (one build time for all 13 files).
- **Mechanical consequences:**
  - The or_call.py header changed, so its sha256 is now
    55e8981c1b75a30aef551ac0810b0891b7d41df8d32878db9710650d7ba06b38 (was 5669579d…), and the bar's Harness row is updated.
  - controls/README.md documents the P5 controls and points the builders at e2a50d4.
  - controls/MANIFEST.sha256, MANIFEST.sha256 (now 22 lines, adding p5check.py) and BAR-DIGEST were rebuilt.
- Nothing else changed. N1–N8, the other P-rows, bounds, the briefs, other controls and the subject results all stay
  as they were: main ff350e3 gets N1 FAIL, N2 PASS, N3 FAIL, N4 FAIL, N5 PASS, N7 FAIL, N8 FAIL, the same as amendment 1.

## Approval status
The 17:40 ET Buyer approval of bar digest d1b8694f5d024442c0e1343b360d15066ca182d0b44dd9962224994bef745372 (manifest
f6389624…1404) is **superseded**: those bytes no longer exist in the freeze set. A new approval of the new digest
(BAR-DIGEST, with MANIFEST.sha256) is needed before the freeze.

## Rehearsal (throwaway, deleted)
Done in a temporary worktree of plumbline main ff350e3: open (schema-verified), then the frozen set copied to
`custody/`, then ledger freeze (21:55:17Z), approve buyer, approve specialist (adopted), pin maker
(DeepInfra deepinfra/fp8 at api.deepinfra.com) and pin E-GLM (Z.AI z-ai/fp8 at api.z.ai). p5check PASSED: 13 headers
21:53:35Z ≤ 21:55:17Z, and ledger bar_sha256 = sha256(custody/bar.md). The worktree was removed and pruned. The real
repo was untouched.

At the real freeze, the frozen set must sit beside the ledger's bar file (`custody/bar.md`, with `custody/bounds`,
`custody/controls/README.md` and `custody/freeze/…`), because p5check reads the frozen set from that directory.
