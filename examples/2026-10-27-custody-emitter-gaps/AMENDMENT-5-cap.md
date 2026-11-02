# Amendment 5 (post-freeze, Buyer): generation cap, job 2026-10-27-custody-emitter-gaps

| Field | Value |
|---|---|
| Decided by | Steve Moitozo II (S2: Owner, Buyer, Specialist-adopter), acting as Buyer |
| Words, verbatim | "As Buyer I amend the bar to raise the cap from 3 to 4 generations, money cap and time bound unchanged. Draft the gen-4 Maker handoff with the N1/N3/N6 findings." |
| When | 2026-10-28 07:52 EDT (America/New_York, UTC-4) = 2026-10-28T11:52Z |
| Channel / relay path | Steve's answer to question card `t65s389` in the Chief of Staff (Orchestrator) chat. The Orchestrator witnessed it directly and relayed it word for word to the drafter. |
| Amends | The cap term of the bar ("Bounds T_accept 1, T_dim 1, T_reject 0, cap 3 generations", bar.md "Scale and pass rule"; `bounds.cap` 3, `cap_counts` "generations"). It does not change the frozen bytes. This file supersedes the cap number; the pass rule text ("A 0 regenerates (< cap) or goes `needs_owner` (at cap)") now reads against cap 4. |
| Frozen set | This amendment is not in the frozen set. bar.md (sha256 `3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b`), `custody/MANIFEST.sha256` (`f0ed1caf047e12eaa232df235343fae3b07603ac2fe5f8de0e293c93e8f680e7`) and every MANIFEST-listed file are unchanged. The ledger freeze event still matches the bar digest, and P5(e) still passes (`P5-CHECK-amend5-gen4.json`). |

## Why
Iteration 1 used all 3 generations: gen 1 and gen 2 failed, and gen 3 was accepted as Maker commit `7cc38f8`. The
Evaluator then scored it FAIL on N1, N3 and N6 (EVAL-ITER1-VERDICT.md, batch 2). At cap 3 the job went to
`needs_owner` (class `cap_reached`; ledger evaluation line, iteration 1). The Buyer raised the cap by one so a
fourth generation can address those findings.

## What changed (cap term only)
- **Cap:** 4 generations (was 3). Generation 4 is the last one. If any dimension of its evaluation scores 0, the job
  goes to `needs_owner` (at cap).
- **Generation 4** opens on the job branch after this amendment. Its prompt is
  `handoffs/iter2/maker-messages-gen4.json`; the handoff is `handoffs/iter2-maker.md`.

## Unchanged
- **Money cap:** strictly under US$10 of all model/API spend. The key usage was $0.16043365 after iteration 1's
  evaluation (EVAL-ITER1-VERDICT.md).
- **Time bound:** ends **2026-10-28 13:15 EDT (17:15Z)** (AMENDMENT-3). A breach is still `needs_owner`.
- **Per generation:** up to 4 Maker calls, a ceiling of $0.25 per call and $1.00 per generation.
- **Everything else:** all dimensions N1–N9, P1–P6, thresholds, controls, pins, seats, the operator rule, the frozen
  harness (or_call.py `55e8981c…6b38`) and the whole-file protocol (DECISIONS D6).
