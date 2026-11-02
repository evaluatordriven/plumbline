# Amendment 1 to the approved sheet: job 2026-10-27-custody-emitter-gaps

| Field | Value |
|---|---|
| Decided by | Steve Moitozo II (S2: Owner, Buyer, Specialist-adopter) |
| Words, verbatim | "Tighten N1 to use the logger's send and receive times, add the single-call fixture, then bring me the new digest" |
| When | 2026-10-27 17:31 ET (America/New_York, UTC-4), i.e. 2026-10-27T21:31Z |
| Channel | Grok Bot private chat (relayed to the drafter by the Orchestrator; message id not relayed) |
| Amends | the sheet approved 16:59 ET (OWNER-APPROVAL-RECORD.md) and the freeze set of commit 69ec598 (bar digest fcc3628a…bfcf, never approved for freeze) |

## Why
Main ff350e3 PASSED N1 and N2 on the frozen fixtures of commit 69ec598: N1 allowed `startedAt = producedAt`
when exactly one Maker event exists, and the only one-call fixtures had the reply's `created` and `Date` in the
same second. So the bar did not require gap 1 (startedAt/producedAt taken from `created`/`Date` rather than
when the call was sent and received) to be fixed.

## What changed
- **N1 (bar.md):** `startedAt` = the call logger's request-send time (`sent_at`, `freeze/harness/or_call.py`)
  of the first Maker call; `producedAt` = its reply-receive time (`received_at`) of the last Maker call; read
  from the Maker harness log, compared at whole seconds UTC. The "equal only if exactly one Maker event"
  exemption is removed: equal only if that log's send and receive are equal. A call logged without both fails.
  or_call.py already records both (`sent_at` before the POST, `received_at` after the reply); it is unchanged
  (sha256 5669579d…2da9).
- **N2 (bar.md), wording only:** "two Maker calls; the first call's `sent_at` and the last call's
  `received_at` 600 s apart". The check and 600 s threshold are unchanged.
- **P1 (bar.md):** C-N1p added to the S1 per-batch planted list.
- **Fixtures:** every held-out maker log now carries `sent_at`/`received_at`; new **F-single-call** (one call,
  send 18:23:29.307Z, receive 18:23:40.912Z, `created` = `Date` = 18:23:32Z).
- **Controls:** C-N1c (clean, expect N1 PASS), C-N1p and C-N1p2 (planted, expect N1 FAIL); per-batch mutant
  M-N1p (recorded as C-N1p). All record-level controls rebuilt against the rebuilt fixtures.
- **Instrument:** derive.py, ncheck.py (N1; N8 compares at whole seconds), mutate.py (`logger-times`),
  run_instrument.sh (F-single-call in the subject run, M-N1p).
- **bounds:** the frozen `bounds` file P5 names is added, transcribed verbatim from bar.md and the briefs.

Unchanged: every other check, threshold, approved item, pin, provider and budget.

## Consequence for the Maker (disclosed, not a change of terms)
N1 applies to every record, including the Maker's own `tests/fixtures/custody/*` jobs. Main's
`job-rejected` fixture log has no `sent_at`/`received_at`, so N1 FAILs there too until the Maker's fixtures
carry logger times.
