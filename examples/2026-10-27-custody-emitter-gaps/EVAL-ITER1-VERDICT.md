# Iteration 1 evaluation verdict: FAIL (N1, N3, N6). Cap reached, so needs_owner

| | |
|---|---|
| Job | 2026-10-27-custody-emitter-gaps |
| Subject | Maker generation 3, commit `7cc38f833f8f5eeceffcb405885adb05141f8c65` (the batch's `rev.txt`) |
| Evaluator batch | 2 (batch 1 is void: EVAL-ITER1-BATCH1-VOID.md), under the frozen set as amended by AMENDMENT-4 |
| Batch seal | `BATCH-MANIFEST.sha256` sha256 `abea7b104bf3f0c2c01e5ea6a0f0a8dbf199f29c45c0aa834c7f3aa84dc9319f`. It does not list itself, and `sha256sum -c` is OK |
| Verdict written by | Chief of Staff (Orchestrator), 2026-10-28 ~07:52 EDT, from the batch-dir files. No model calls |
| Pass rule (bar.md, frozen `3ced9bc0…970b`) | "pass ⇔ every dimension scores 1." |

## Integrity of the run
- **Controls.** The controls tree was identical before and after the run (`cmp` OK, 551 files). `s1/permission-errors.txt` is empty.
- **Exit codes.** S1, N6 and P5 all exit 0.
- **S1 summary.** `"controls": "as expected", "mutants": "as expected"`. Every C1, record-level, P5(e) and mutant
  control gave its expected verdict (`s1--run.log`).
- **E-GLM controls.** G-p1 (planted) returned DOES_NOT_CONFORM and G-c1 (clean) returned CONFORMS, so `controls_ok: true`.
  The order was [G-p1, subject, G-c1]. All three calls finished `stop`, were served by Z.AI, and the pin held.

## Scores (s1/summary.json `d3ffc998…`; N6-batch.json in the BATCH-MANIFEST)
| Dim | Score | Evidence |
|---|---|---|
| N1 | **0** | PASS on F-genreply-full, F-maker-10min and F-single-call. **FAIL on extra-1-job-rejected**, which says: "maker call(s) without the logger's sent_at/received_at: ['0']"; "startedAt: record '…' != sent_at of the first maker call None"; "producedAt: record '…' != received_at of the last maker call None" |
| N2 | 1 | PASS |
| N3 | **0** | FAIL on every job (F-genreply-full, F-maker-10min, F-single-call, extra-1-job-rejected), which says: "no time field names a {file, line} source in x-plumbline (timeSources \| time_sources \| times)" |
| N4 | 1 | PASS. The F-genreply-null refusal (exit 3) is the expected path (a) |
| N5 | 1 | PASS |
| N6 | **0** | E-GLM call `n6-b2-2` (messages `e103d000…2d37`) returned **DOES_NOT_CONFORM**, citing `kit/custody_history.py:284, :289, :305, :213`, with valid controls. Reply: `n6--n6-b2-2.reply.txt` (`961099fd…`) |
| N7 | 1 | PASS |
| N8 | 1 | PASS |
| N9 | (control, not scored) | C-N9c, C-N9p and C-N9p0 as expected. M-N9p as expected |
| P5(e) | PASS | p5/P5-check.json `037aacb2…` |

There are three 0s, so by the pass rule **iteration 1 FAILS**.

## Cap and terminal state
The bar text is quoted verbatim from bar.md, "Scale and pass rule". It is also transcribed in `custody/bounds`, which says "on any difference bar.md governs":
> Bounds T_accept 1, T_dim 1, T_reject 0, cap 3 generations.
> pass ⇔ every dimension scores 1. A 0 regenerates (< cap) or goes `needs_owner` (at cap). Algebra never
> rejects; `rejected` is the Owner's call.

In `custody/bounds` and brief.json `bounds`: `"cap": 3, "cap_counts": "generations"`. AMENDMENT-3 says: "Generations: cap 3.
Generation 3 is still the last generation of iteration 1."

The cap counts **Maker generations**, not Maker+Evaluator rounds. The ledger has three generations: n 1 closed `failed`,
n 2 closed `failed`, and n 3 closed `accepted`. So the job is **at cap**, and the earlier statement "gen 3 is the last
generation the bar allows" was correct.

Two lines in the unfrozen `packet.json` say "iterations": "Any 0 with iterations < cap -> regenerate" and "k = 3 iteration
bound (= cap)". The frozen bar governs, and the bar says generations.

An "iteration 2" would need a 4th Maker generation, and **the bar does not allow it**. The state that applies is
**`needs_owner`**, under escalation class `cap_reached`, routed to Steve Moitozo II (S2) and carrying the shortfalls
(packet.json `escalation`). The Owner chooses what happens next. One option is `rejected` ("the Owner's call"). The
other is a post-freeze Buyer amendment that raises the cap, done the same way as AMENDMENT-3 and AMENDMENT-4. Nothing was
dispatched and no generation line was opened.

## Timing, if the Owner amends the cap (planning only, not a plan of record)
The time bound is 13:15 EDT (AMENDMENT-3). Working backwards:
- **Record emission and close.** Keep 45 min, so evaluation must finish by 12:30.
- **Evaluator batch.** Batch 2 took about 8 min of E-GLM (11:39–11:45Z) plus S1. With verification and a ledger line, allow
  20 min, so the **Evaluator must be dispatched by 12:10**.
- **Maker generation.** Observed call times are 4.8 to 26 min (gens 2 and 3), plus about 5 min of extract, apply and tests per call.
  - Two calls (one retry) need about 62 min, so the **latest safe Maker start is ~11:05 EDT**.
  - The full four calls allowed in a gen-3-style generation need about 124 min, so the latest start is ~10:05 EDT.
- **Before the Maker.** A Buyer amendment (draft, approve, apply) and the iter2 handoff take about 30 min.
- **Realistic if the Owner decides by about 09:30 EDT.** Between 09:30 and 10:30, plan on two calls at most. After about
  10:30, the Owner should not plan a generation.

## Shortfalls carried to the Owner
1. **N1 on extra-1-job-rejected.** The harness log of that job's Maker call has no logger `sent_at`/`received_at`. The
   subject still writes `startedAt`/`producedAt` instead of refusing them or leaving them unset and flagging them.
2. **N3.** The emitted `x-plumbline` names no `{file, line}` source for any time field, in any job.
3. **N6.** E-GLM: `endpoint_of` requires only that the generation reply be a dict, never that it name a provider. It then
   accepts a pin match from response metadata (`served_by`, l.213; l.289), and the pinned host is written (l.305).

## Spend
- **E-GLM batch 2.** Σ generation `total_cost` = $0.00919725 (0.00051851 + 0.00783289 + 0.00084585). Key usage went
  0.15208225 → 0.16043365.
- **Job.** Key usage is $0.16043365 against a cap of < US$10. It was 0 before gen 1 (GEN1-FAILURE.md).

## Evidence committed (custody/evidence/)
- **Batch-2 E-GLM log.** `harness-eval-glm-b2.log` (redacted, `576abd04…`) and `.full.sha256` (full log
  `79e2decb79e352ba4146cfdd88799e752b4e41f1b4528e1d5c291f0e0139d46b`).
- **Batch-1 E-GLM log (void batch).** `harness-eval-glm-b1.log` (redacted, `fc4fe680…`) and `.full.sha256` (full log `80de3e9f…368b`).
- **Batch-2 files.** `eval/iter1-b2/`; see its README for what is verbatim, what is redacted and what is held out.
- **Redaction tool.** `handoffs/redact_glm_log.py` (F3). It redacts the held-out control requests and the replies to them
  as well, and it refuses to write if any control line remains.
