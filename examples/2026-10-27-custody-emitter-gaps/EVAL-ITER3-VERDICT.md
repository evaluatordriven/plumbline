# Iteration 3 evaluation verdict: PASS (every dimension scores 1). Terminal state: accepted

| | |
|---|---|
| Job | 2026-10-27-custody-emitter-gaps |
| Subject | Maker generation 5, commit `c7db5b04f23d9687c1ee1f8e9849fa41cb39e6d8` (the batch's `rev.txt`) |
| Evaluator batch | 4, under the frozen set as amended by AMENDMENT-4 (handoff `handoffs/iter3-evaluator-b4.md`) |
| Batch seal | `BATCH-MANIFEST.sha256` sha256 `8d06b7645f4bd8e19c33b4649aa1c4b36cf6652d3fa401d947e7a2e45358bcc0` (267 lines). It does not list itself, it lists every file in the batch dir outside `rev/` and `controls/`, and `sha256sum -c` is OK |
| E-GLM calls approved | Steve Moitozo II, 2026-10-28 10:17 EDT, in the Evaluator's chat (relayed): "Yes, go ahead with batch 4's three E-GLM calls." |
| Verdict written by | Chief of Staff (Orchestrator), 2026-10-28 ~10:35 EDT, from the batch-dir files. No model calls |
| Pass rule (bar.md, frozen `3ced9bc0…970b`) | "pass ⇔ every dimension scores 1." |

## Integrity of the run
- **Subject.** `rev.txt` and the batch's `rev` clone HEAD are both `c7db5b04…`; the clone is clean.
- **Controls.** `controls-before.sha256` and `controls-after.sha256` are identical (551 files). The copy still matches
  them and the frozen `custody/controls/MANIFEST.sha256` (`9764d8e4…60bf`), and the held-out source controls match
  them byte for byte. `s1/permission-errors.txt` is empty.
- **Exit codes.** S1, N6 and P5 all exit 0. `n6/stderr.txt` and `p5/P5-check.stderr` are empty.
- **S1 summary.** `"controls": "as expected", "mutants": "as expected"`. Every C1 (17), record-level (21), P5(e) (3) and
  mutant (5 lines) control gave its expected verdict (`s1--run.log`: 30 expect/got pairs, none differ).
- **E-GLM controls.** Order [subject, G-c1, G-p1]. G-c1 (clean) returned CONFORMS and G-p1 (planted) returned
  DOES_NOT_CONFORM, so `controls_ok: true`. All three calls finished `stop`, were served by Z.AI
  (`z-ai/glm-5.3-flash-20260826`), tried only Z.AI, and the pin held. Messages sha256 for G-c1 and G-p1 equal batch 3's.
- **No throttling.** Each request body has only `model`, `messages`, `provider` {order [z-ai/fp8], allow_fallbacks
  false, zdr true}, `temperature` and `max_tokens` 131072. No reasoning or effort parameter.
- **Subject prompt.** `n6-b4-1.messages.json` (`0820135c…7a67`) carries `kit/emit_custody.py` and
  `kit/custody_history.py` exactly as at `c7db5b0`, in n6_batch.py's numbered-listing form.
- **E-GLM log.** The full log sha256 is `9dee9705bf03b0c8cfd917dc6422188a300816c9810b499df9aeeb3ef0b6ec4f`, as the
  Evaluator reported. It has 3 entries.

## Scores (s1/summary.json `270770e4…52ed`; N6-batch.json `026cb5f7…c939` in the BATCH-MANIFEST)
| Dim | Score | Evidence |
|---|---|---|
| N1 | 1 | PASS on F-genreply-full, F-maker-10min, F-single-call and extra-1-job-rejected |
| N2 | 1 | PASS |
| N3 | 1 | PASS on F-genreply-full, F-maker-10min, F-single-call and **extra-1-job-rejected** (`s1--subject--N3-extra-1-job-rejected.json`, `6835c70d…fcc50`, empty `why`; frozenAt and both approval times now cite `inputs/custody-events.jsonl` lines 1–3). This was iteration 2's one failure |
| N4 | 1 | PASS |
| N5 | 1 | PASS |
| N6 | 1 | E-GLM call `n6-b4-1` (messages `0820135c…7a67`) returned **CONFORMS**, citing `kit/custody_history.py:376, :381, :292, :402` and `kit/emit_custody.py:355, :393`, with valid controls. Reply: `n6--n6-b4-1.reply.txt` (`d42d6ef2…00f3`) |
| N7 | 1 | PASS |
| N8 | 1 | PASS |
| N9 | (control, not scored) | C-N9c, C-N9p and C-N9p0 as expected. M-N9p as expected |
| P5(e) | PASS | p5/P5-check.json `037aacb2…`; re-run by the Orchestrator after this verdict was written: PASS (`P5-CHECK-eval3-verdict.json`) |

Every dimension scores 1, so by the pass rule **iteration 3 PASSES**.

## Cap and terminal state
AMENDMENT-6 sets the cap at 3 E-DI iterations; this is iteration 3, the last. Because it passes, the cap does not
apply. Under the bar, a pass is the algebra's `accept`, and the job's terminal state is **`accepted`**. That is the
instrument's result. The **disposition** (what the Owner does with the accepted artifact: given or declined) is
Steve Moitozo II's own act. It is not inferred from this verdict and has not been given. `CLOSE-apply.sh` is prepared
to record it when he does.

## Notes (they do not change the instrument result above)
1. **Fixture provenance (Evaluator's observation).** `extra-1-job-rejected` was scored on the repository fixture
   `tests/fixtures/custody/job-rejected`, the same fixture the Maker edited in generation 5. The N3 run that failed in
   iteration 2 now passes on a fixture the subject itself changed.
2. **Fixture-only fix (Orchestrator's observation, from the generation-5 close).** The N3 change is mostly in the
   fixture. Its ledger gained freeze, two approve and dispose events that carry the same hand-typed times as its
   `inputs/custody.json`. The freeze event has no `bar_sha256`, so this fixture skips the "bar changed after freeze"
   check. The emitter (`kit/emit_custody.py`) only relaxed its cross-checks: by/at are compared only when both sides
   carry the field, `frozenAt` may come from the ledger, and ledger events are ignored when there are no inputs. It does
   not refuse or flag hand-entered times. The held-out fixtures (F-*), whose ledgers carry real events, passed N3 in
   both iterations 2 and 3.
3. These are not dimensions of the frozen bar. They are carried to the Owner for the disposition, and may inform a
   follow-up bar. They do not change any score.

## Record correction: generation-5 Maker approval
The generation-5 close line (ledger, commit `9255b23`) says that Steve's go-ahead to the Maker was not witnessed by
the Orchestrator and was to be cited verbatim from the E-DI Maker chat. The Maker has now relayed it. **As relayed by
the Maker** (E-DI Maker chat, 2026-10-28 09:43 EDT), Steve said: "Yes, run generation 5 and push the job branch if it
passes." The Orchestrator still has not seen it first-hand. It is recorded in the iteration-3 evaluation ledger line
(`gen5_maker_approval`). The append-only close line is not rewritten.

## Spend
- **E-GLM batch 4.** Σ generation `total_cost` = $0.0162769 (n6-b4-1 0.0142008, n6-b4-2 0.00135035, n6-b4-3
  0.00072575). Key usage went 0.287216475 → 0.303493375 (Δ 0.0162769), exactly equal. The after-read (10:27:19 EDT) was
  156 s after the last call returned, so F5's lag did not recur.
- **Job (model calls).** Key usage started at $0 (`key-usage-maker-iter1-before.json`) and is now **$0.303493375**,
  against a cap of < US$10. Grok Bot operator and Orchestrator spend is not observable (P6) and is declared
  unverifiable.

## Timing
E-GLM calls ran 10:17:27–10:24:43 EDT (14:17:27Z–14:24:43Z). The bound is 13:15 EDT (AMENDMENT-3).

## Evidence committed (custody/evidence/)
- **Batch-4 E-GLM log.** `harness-eval-glm-b4.log` (redacted: n6-b4-2 and n6-b4-3; `b4dce825…9a8f`) and
  `.full.sha256` (full log `9dee9705bf03b0c8cfd917dc6422188a300816c9810b499df9aeeb3ef0b6ec4f`).
- **Batch-4 files.** `eval/iter3-b4/`; see its README for what is verbatim, what is redacted and what is held out.
