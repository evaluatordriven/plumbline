# Amendment 6 (post-freeze, Buyer): the cap counts E-DI iterations, job 2026-10-27-custody-emitter-gaps

> **STATUS: APPLIED** by `AMENDMENT-6-apply.sh` after the Buyer's approval below.

| Field | Value |
|---|---|
| Decided by | Steve Moitozo II (S2: Owner, Buyer, Specialist-adopter), acting as Buyer |
| Words, verbatim | "As Buyer I amend the cap to 3 E-DI iterations, with Maker attempts limited only by budget; money cap and time bound unchanged. Run iteration 3 on the N3 finding." |
| When (UTC) | 2026-10-28T13:32:00Z |
| Channel / relay path | Chief of Staff chat, card t73s419 |
| Basis | Steve, 2026-10-28 08:08 EDT (12:08Z), Chief of Staff (Orchestrator) chat, message t66u, verbatim: "I think we need a differentiate between the makers internal loop and the EDI loop. When I said three iteration, I was talking about three iterations of the EDI loop what the maker does to produce on its turn. I don't think we wanna limit that if it needs to do internal looping to achieve what it needs for a correct result for making I think that's fine within the budget it's given." |
| Amends | The cap term: bar.md "Scale and pass rule" ("cap 3 generations"; `bounds.cap` 3, `cap_counts` "generations"), as amended by AMENDMENT-5 (cap 4 generations), and AMENDMENT-5's "Per generation: up to 4 Maker calls". It does not change the frozen bytes. The pass rule text ("A 0 regenerates (< cap) or goes `needs_owner` (at cap)") now reads against cap 3 E-DI iterations. |
| Frozen set | This amendment is not in the frozen set. bar.md (sha256 `3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b`), `custody/MANIFEST.sha256` (`f0ed1caf047e12eaa232df235343fae3b07603ac2fe5f8de0e293c93e8f680e7`) and every MANIFEST-listed file are unchanged. The ledger freeze event still matches the bar digest; P5(e) is re-run on apply (`P5-CHECK-amend6-gen5.json`). |

## Why
Steve's "three iterations" meant three turns of the E-DI loop, not three Maker attempts. The bar and AMENDMENT-5
counted Maker generations, and AMENDMENT-5 limited each generation to 4 Maker calls. By that count iteration 2 hit
the cap (4 generations) and went to `needs_owner` with one 0 (N3, EVAL-ITER2-VERDICT.md). Counted as Steve meant
it, two E-DI iterations have run, so one remains.

## What changed (cap term only)
- **Cap: 3 E-DI iterations.** An E-DI iteration is one Maker turn (one generation, accepted or not) followed by one
  Evaluator scoring of what that turn produced. A void Evaluator batch does not count; its re-run belongs to the same
  iteration.
- **Count so far.**
  - Iteration 1 = generations 1–3 (gens 1 and 2 failed inside the Maker's turn; gen 3 accepted as `7cc38f8`). It was
    scored by batch 2 (batch 1 void): FAIL (N1, N3, N6).
  - Iteration 2 = generation 4 (`73863fb`). It was scored by batch 3: FAIL (N3).
  - **Iteration 3 = generation 5**, scored by batch 4. It is the last iteration: if any dimension of its evaluation
    scores 0, the job goes to `needs_owner` (at cap).
- **The Maker's turn is not limited by a call count.** Within a generation, the Maker operator may make as many
  logged calls (follow-ups after a failed extract or test, and re-sends after a transport error or a lost call) as
  the budget and the time cutoffs allow:
  - **$0.25** per call (`total_cost`);
  - **$1.00** per generation;
  - the job total stays **< US$10**;
  - the handoff's call cutoffs: no call starts after **11:05 EDT** (15:05Z), and a final call no later than **11:30 EDT**
    (15:30Z).
  The protocol for each call is unchanged.
- **Generation 5** opens on the job branch when this amendment is applied. Base: `73863fb00c72239de0f0c2def4f68d1c6dfd902b`. Prompt:
  `handoffs/iter3/maker-messages-gen5.json` (sha256 `d188cb80871fa959c43af2cde5588cc4ab8319eba00606ca212878f3662b0caa`). Handoff:
  `handoffs/iter3-maker.md`. Evaluator: `handoffs/iter3-evaluator-b4.TEMPLATE.md`.
- This lifts iteration 2's `needs_owner` (class `cap_reached`).

## Unchanged
- **Money cap:** strictly under US$10 of all model/API spend (key usage $0.253801479 after batch 3; about $0.2545
  once batch 3's last call posts).
- **Time bound:** ends **2026-10-28 13:15 EDT (17:15Z)** (AMENDMENT-3). A breach is still `needs_owner`.
- **Everything else:** all dimensions N1–N9, P1–P6, thresholds, controls, pins, seats, the operator rule, the frozen
  harness (or_call.py `55e8981c…6b38`), the whole-file protocol (DECISIONS D6), the allow-list, and AMENDMENT-4
  (E-GLM output cap).
