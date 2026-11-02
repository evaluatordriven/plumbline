# Amendment 1 (post-freeze, Buyer): clock-time bound for iteration 2, job 2026-10-28-custody-times-ledger-spend

| Field | Value |
|---|---|
| Decided by | Steve Moitozo II (Owner, Buyer, Specialist-adopter), acting as Buyer |
| Decision words, verbatim | "Pause tonight. Resume iteration 2 tomorrow with a new 8-hour clock bound; same $5 budget and cap 3." |
| Decision when / channel | 2026-10-28 21:40 EDT (America/New_York, UTC-4) = 2026-10-29T01:40Z. Steve's widget answer in the Grok Bot chat with Chief of Staff (Orchestrator), witnessed by the Orchestrator. The card id is not on file (DEVIATIONS-orchestrator.md, 21:40 EDT entry, records the words and time only). |
| Go-ahead words, verbatim | "Resume" |
| Go-ahead when / channel | 2026-10-29 06:21 EDT (UTC-4) = 2026-10-29T10:21Z. Steve's message in the Grok Bot chat with Chief of Staff (Orchestrator). Witnessed by the Orchestrator; relayed word for word by the Orchestrator to the helper that drafted and filed this file, which did not witness it. No message id was relayed; seconds not relayed. |
| Amends | The time term of the bar: bar.md "Scale and pass rule", line 48 ("Time: ends **2026-10-29 00:34 EDT** ..."), and the time words of the digest approval (card t96s548, "... by 2026-10-29 00:34 EDT"). It does not change the frozen bytes. |
| Frozen set | This amendment is not in the frozen set. custody/bar.md (sha256 `72e92dc7580e2447f19dfff66aaac02d8484157a6283dcfdda6c7bb2de7561c6`), custody/MANIFEST.sha256 (`acdf764b32bab5e0fa4615590714c49162cbbaecddd00c03c6d8121b59b85d98`) and every MANIFEST-listed file are unchanged; `(cd custody && sha256sum --quiet -c MANIFEST.sha256)` is silent. The ledger freeze event still matches the bar digest. |

## Why
Iteration 1 was scored and FAILED on 2026-10-28 (S1 17/39; E-GLM J2 and J4 FAIL), leaving iterations 2 and 3 of
cap 3. The bar's clock-time bound (8 h from open, ending 2026-10-29 00:34 EDT) would have expired overnight. The
Buyer paused the job at 21:40 EDT and set a new 8-hour bound starting at his go-ahead. No model call was sent after
the pause: the last harness call of the job was settled at 2026-10-29T01:32:41Z (21:32:41 EDT, spend ledger,
J4-b1-3), before the old bound and before the pause; the Maker harness log's last call was received at
2026-10-29T00:02:27Z (2026-10-28 20:02:27 EDT).

## What changed (time term only)
- **Time bound:** ends **2026-10-29 14:21 EDT (UTC-4) = 2026-10-29T18:21:00Z**.
  Arithmetic: go-ahead 2026-10-29 06:21 EDT (10:21Z), rounded down to the minute = 06:21 EDT; + 8 h = 14:21 EDT
  (18:21Z). No model call may be sent at or after it. A breach is `needs_owner`, as before.
- The bound covers iteration 2 and, if one is needed, iteration 3. Any later extension is a new amendment.

## Unchanged
- **Money:** total job spend strictly under US$5.00 on the shared key, US$0.10 reserve, enforced by the frozen
  harness's pre-call guard (or_call.py `d2b320398a8de7a240de30cf9ea3ee54aa5fed8a2d1bc2a616b75fba9713d574`). Spend
  before iteration 2: US$0.295069 (guard, 2026-10-28 21:40 EDT).
- **Cap:** 3 E-DI iterations (iteration 1 used). Maker attempts are limited by money, this clock bound and the
  repeat-failure tripwire.
- **Everything else:** every check, threshold, control, pin, seat, the allow-list, the output contract and the
  no-throttling rule.

## Ledger
One `amendment` line is appended to inputs/custody-events.jsonl by hand (base kit/custody_ledger.py @ 3df1ce5 has no
`amendment` command; packet `self_reference`: missing commands hand-appended and disclosed). Its fields follow
INTERFACE.md line 23 plus `hand_appended: true`.
