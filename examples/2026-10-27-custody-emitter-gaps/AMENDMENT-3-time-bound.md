# Amendment 3 (post-freeze, Buyer) — time bound: job 2026-10-27-custody-emitter-gaps

| Field | Value |
|---|---|
| Decided by | Steve Moitozo II (S2: Owner, Buyer, Specialist-adopter), acting as Buyer |
| Words, verbatim | "A: amend the bar as Buyer to extend the time bound so gen 3 can run, money cap unchanged." |
| When | 2026-10-28 06:21 EDT (America/New_York, UTC-4) = 2026-10-28T10:21Z (time as relayed) |
| Channel / relay path | Steve's answer in the E-DI Maker bot's chat, relayed word for word by the E-DI Maker bot to the Orchestrator, then to the drafter. The Orchestrator did not witness it directly. No message id was relayed. |
| Amends | The time term of the bar's budget ("Budget < US$10 and < 10 h; either breach → `needs_owner`", bar.md "Scale and pass rule"; `bounds`; brief.json `bounds.budget.time_hours_lt` 10). It does not change the frozen bytes. |
| Frozen set | This amendment is not in the frozen set. bar.md (sha256 `3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b`), `custody/MANIFEST.sha256` (`2e9a77fb60a57bdfe889ab7075734c71e62eb67696a7f678a082d8007937dcdd`) and every MANIFEST-listed file are unchanged. The ledger freeze event still matches the bar digest, and P5(e) still passes (`P5-CHECK-amend3.json`). |

## Why
The bar's time term ran from the first Maker dispatch (2026-10-27 19:44:48 EDT, `maker_iter1_call1` `sent_at`
23:44:48Z). The operating cutoff for the job was 2026-10-28 03:15 EDT, and gen-3 calls could not start after
02:15 EDT (handoffs/iter1-maker.md, Generation 3). Generation 3, opened at 2026-10-28T02:23:56Z (22:23:56 EDT), made
no Maker call before that cutoff (there is no `maker/iter1-gen3/` evidence and the harness log holds 8 entries). The
Buyer extended the time bound so generation 3 can run.

Note for the record: the 10 h bound, measured strictly from the first Maker dispatch, would have ended at
2026-10-28 05:44:48 EDT. The ~03:15 EDT end is the operating cutoff that the handoffs used. This amendment sets an
explicit end, so either reading is superseded.

## What changed (time term only)
- **Time bound:** extended by another 10 hours. It now **ends 2026-10-28 13:15 EDT (17:15Z)**. A breach after that
  is still `needs_owner`.
- **Gen-3 call-start cutoff:** no Maker call may start after **2026-10-28 12:15 EDT (16:15Z)**.

## Unchanged
- **Money cap:** strictly under US$10 of all model/API spend. The Maker has spent $0.107969 so far.
- **Generations:** cap 3. Generation 3 is still the last generation of iteration 1. It may make up to 4 calls, its
  ceiling is $1.00, and each call's ceiling is $0.25.
- **Gen-3 inputs and output protocol:** whole files per DECISIONS D6, written by `handoffs/extract_files.py`. The
  prompt is `handoffs/iter1/maker-messages-gen3.json` (`10193b5c0ca09d3194829268047584439a559397519aa28e1fb5177c2275bb57`).
- **Flags and harness:** `--temperature 0 --max-tokens 131072 --gen-tries 12 --gen-wait 20`, with no reasoning
  parameters. The frozen harness is or_call.py `55e8981c…6b38`.
- **Everything else:** all dimensions N1–N9, P1–P6, the thresholds, controls, pins, seats and the operator rule.
