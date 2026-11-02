# Iteration 2 evaluation verdict: FAIL (N3 only). Cap reached, so needs_owner

| | |
|---|---|
| Job | 2026-10-27-custody-emitter-gaps |
| Subject | Maker generation 4, commit `73863fb00c72239de0f0c2def4f68d1c6dfd902b` (the batch's `rev.txt`) |
| Evaluator batch | 3, under the frozen set as amended by AMENDMENT-4 (handoff `handoffs/iter2-evaluator-b3.md`) |
| Batch seal | `BATCH-MANIFEST.sha256` sha256 `d4bec77d36f14bfca019aad13849f64a4c74029d6e8fd1f470b9ab2046a07243` (267 lines). It does not list itself, and `sha256sum -c` is OK |
| E-GLM calls approved | Steve Moitozo II, 2026-10-28 09:04 EDT, in the Evaluator's chat (relayed) |
| Verdict written by | Chief of Staff (Orchestrator), 2026-10-28 09:22 EDT, from the batch-dir files. No model calls |
| Pass rule (bar.md, frozen `3ced9bc0…970b`) | "pass ⇔ every dimension scores 1." |

## Integrity of the run
- **Subject.** `rev.txt` and the batch's `rev` clone HEAD are both `73863fb0…`; the clone is clean.
- **Controls.** `controls-before.sha256` and `controls-after.sha256` are identical (551 files), the copy still matches
  them, and they match the held-out source controls byte for byte. `s1/permission-errors.txt` is empty.
- **Exit codes.** S1, N6 and P5 all exit 0. `n6/stderr.txt` is empty.
- **S1 summary.** `"controls": "as expected", "mutants": "as expected"`. Every C1 (17), record-level (21), P5(e) (3) and
  mutant control gave its expected verdict (`s1--run.log`).
- **E-GLM controls.** Order [G-c1, subject, G-p1]. G-c1 (clean) returned CONFORMS and G-p1 (planted) returned
  DOES_NOT_CONFORM, so `controls_ok: true`. All three calls finished `stop`, were served by Z.AI
  (`z-ai/glm-5.3-flash-20260826`), and the pin held.
- **Subject prompt.** `n6-b3-2.messages.json` (`f4c33896…70a5`) carries `kit/custody_history.py` and
  `kit/emit_custody.py` exactly as at `73863fb`.

## Scores (s1/summary.json `092b82a0…8bfe8b`; N6-batch.json in the BATCH-MANIFEST)
| Dim | Score | Evidence |
|---|---|---|
| N1 | 1 | PASS on F-genreply-full, F-maker-10min, F-single-call and extra-1-job-rejected (the iteration-1 failure is fixed) |
| N2 | 1 | PASS |
| N3 | **0** | PASS on F-genreply-full, F-maker-10min and F-single-call. **FAIL on extra-1-job-rejected** (`s1--subject--N3-extra-1-job-rejected.json`, `39b9980e…11df`): "/bar/frozenAt, /bar/approvals/0/at, /bar/approvals/1/at, /disposition/at: source file 'inputs/custody.json' is not a ledger or harness log in the job". The other four time fields of that record (startedAt, producedAt, checks[0..1].at) PASS |
| N4 | 1 | PASS |
| N5 | 1 | PASS |
| N6 | 1 | E-GLM call `n6-b3-2` (messages `f4c33896…70a5`) returned **CONFORMS**, citing `kit/custody_history.py:376, :381, :399` and `kit/emit_custody.py:347, :385, :455`, with valid controls. Reply: `n6--n6-b3-2.reply.txt` (`7cbeb560…e8b05a`) |
| N7 | 1 | PASS |
| N8 | 1 | PASS |
| N9 | (control, not scored) | C-N9c, C-N9p and C-N9p0 as expected. M-N9p as expected |
| P5(e) | PASS | p5/P5-check.json `037aacb2…` |

There is one 0, so by the pass rule **iteration 2 FAILS, on N3 only**.

### The N3 finding, stated plainly
`extra-1-job-rejected` is the repository's own synthetic fixture `tests/fixtures/custody/job-rejected`; S1 runs every
`tests/fixtures/custody/*/` folder that has `inputs/custody.json` (run_instrument.sh, `subject()`). That fixture's ledger
`inputs/custody-events.jsonl` holds only a `pin` event: no freeze, approval or disposition events. The bar's frozen-at,
the two approval times and the disposition time exist only as hand-entered values in `inputs/custody.json`. The
subject's record cites `inputs/custody.json:14`, `:54`, `:62` and `:155` as their sources (and marks the approvals
`"time_source": "hand-entered"`). N3 accepts only a ledger (`custody-events.jsonl`) or harness-log (`harness-*`) source
line, so those four fields fail. The emitter's behaviour on the held-out fixtures, whose ledgers carry these events,
passes.

## Cap and terminal state
AMENDMENT-5 set the cap to 4 generations (counting Maker generations, as bar.md "Scale and pass rule" and
`custody/bounds` say). The ledger has four: n 1 `failed`, n 2 `failed`, n 3 `accepted`, n 4 `accepted`. The job is
**at cap**. Under the bar as amended, a 0 at cap goes **`needs_owner`** (escalation class `cap_reached`, routed to Steve
Moitozo II, S2, with the shortfall below). No generation is opened by this verdict.

Steve said on 2026-10-28 at 08:08 EDT (Orchestrator chat, t66u) that his "three iterations" meant three iterations of
the E-DI loop, not Maker attempts. A draft Buyer amendment restating the cap that way (AMENDMENT-6-cap.md, PENDING
APPROVAL) is filed separately. Until Steve approves it, this verdict's state stands: `needs_owner`.

## Shortfall carried to the Owner
1. **N3 on the repository fixture job-rejected.** Four time fields (`bar.frozenAt`, `bar.approvals[0..1].at`,
   `disposition.at`) cite the hand-entered `inputs/custody.json`, because the fixture's ledger has no event that carries
   those times. N3 requires a ledger or harness-log source for every time field.

## Spend
- **E-GLM batch 3.** Σ generation `total_cost` = $0.0220778 (0.00151185 + 0.0198922 + 0.00067375). Key usage went
  0.232397429 → 0.253801479 (Δ 0.02140405). The difference, $0.00067375, is exactly `n6-b3-3`'s cost: the after-read
  (09:17:05 EDT) came 11 s after that call returned, before it posted (FOLLOW-UPS F5, recurring).
- **Job.** Key usage ≥ $0.253801479 (≈ $0.2545 once `n6-b3-3` posts) against a cap of < US$10.

## Timing
E-GLM calls ran 09:05:07–09:16:54 EDT (13:05:07Z–13:16:54Z). The bound is 13:15 EDT (AMENDMENT-3).

## Evidence committed (custody/evidence/)
- **Batch-3 E-GLM log.** `harness-eval-glm-b3.log` (redacted, `b8de6def…9279`) and `.full.sha256` (full log
  `beb96465a65c9afc58abd74140044ff344f20c8405e8dc8247ceb152dd71f5b8`).
- **Batch-3 files.** `eval/iter2-b3/`; see its README for what is verbatim, what is redacted and what is held out.
