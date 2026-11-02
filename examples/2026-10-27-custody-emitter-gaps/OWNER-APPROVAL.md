# Approval sheet: next Plumbline job

**For:** Steve Moitozo II (S2) · **Drafted:** 2026-10-27 · **Status:** proposed. Nothing is opened or frozen until you sign.

**The job:** fix the three gaps you logged in Plumbline's custody emitter: (1) the finish time is copied from the start time, (2) a missing provider reply is neither refused nor flagged, and (3) stranger bundles leave out the event ledger and the harness logs.

Tick to approve, or write in a change.

| ☐ | Decision | Recommended | Why |
|---|---|---|---|
| ☐ | 1. Mode | Scored | You get a pass/fail verdict against fixed thresholds, not just readings. |
| ☐ | 2. Entry | A (new, commissioned work) | The fix doesn't exist yet and the bar is written first. B would be a relabelled baseline (draft kept). |
| ☐ | 3. Instrument profile | Full | All the checks this repair needs; the minimal profile drops some. |
| ☐ | 4. Pass rule | Every check must pass (each check scores 0 or 1; all must score 1) | Matches "every check PASS" exactly. A failure retries until the cap, then comes to you. |
| ☐ | 5. Limits | 3 attempts; under US$10; under 10 hours | Same limits as the last job. Expected spend is under $1. |
| ☐ | 6. Maker | DeepSeek V4.1 Flash 1017, one logged API call at a time. The Maker bot only sends the calls and applies the returned code unchanged. | Every call is logged, so times and endpoints come from evidence. Bot's role is disclosed. *(Decided by you 16:48 EDT.)* |
| ☐ | 7. Evaluators | A test script (checks N1–N5, N7–N8) plus GLM 5.3 Flash (code reading N6), both run by the Evaluator bot, which gives no score of its own | Fixes last round's two failures: every judging batch has test cases, and every model read is logged. |
| ☐ | 8. Providers (zero data retention, no fallback) | Maker: DeepInfra (fp8). GLM: Z.AI (fp8) | Different model family and different server, both no-retention, both 100 % up today. DeepInfra already worked with this emitter in round 2. |
| ☐ | 9. Fixed versions | custody SPEC 3e3ca58 · Doctrine dc61854 · E-DI a48a4645 · Plumbline base ff350e3 | Nothing upstream has moved, so the existing tests stay valid. |
| ☐ | 10. Target level | CL1 for this job's own record | What you asked for; Grok Bot operators are recorded as "undisclosed". |
| ☐ | 11. Domain standard | The custody spec and Doctrine §7, adopted by you | Same as the last job; no outside expert needed. |
| ☐ | 12. Test cases hidden from evaluators | Kept outside both bots' folders and copied in only when a batch runs. Any remaining shared-box access is disclosed. | The box is shared, so this is the strongest step available. |
| ☐ | 13. Which emitter writes this job's own record | Current main (ff350e3), not the code being fixed | The fixed code shouldn't certify itself. Its known finish-time gap is disclosed. |

**Bar to approve:** `bar.md` sha256 `cce961c777b402af431497830354995802652d8033e3a0892e239081089eefbc` (draft; the hash changes once, at freeze, when the header changes to FROZEN).

Signed: ____________________ Date/time (ET): ____________

## Still open (none block your approval)
- **Job date** is a placeholder (`2026-10-2X`) until the open date is set.
- **Call logger** (`freeze/harness/or_call.py`, about 30 min to write, $0) is written before freeze. Its hash goes into the frozen pins.
- **Test fixtures and planted defects** (about 1 h, $0) are built after you approve, because they're variants of the Maker's code.
