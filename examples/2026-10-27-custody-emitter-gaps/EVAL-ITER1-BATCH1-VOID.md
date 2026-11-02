# iter1 Evaluator batch 1: VOID (Orchestrator-side causes) · job 2026-10-27-custody-emitter-gaps

| Field | Value |
|---|---|
| Subject | Maker commit `7cc38f833f8f5eeceffcb405885adb05141f8c65` (gen 3, accepted) |
| Handoff | `handoffs/iter1-evaluator.md` (batch 1) |
| Batch dir | `/workspace/edi-batches/2026-10-27-custody-emitter-gaps/iter1` (outside every repo; holds held-out control bytes) |
| Ran | E-GLM calls 2026-10-28 07:05:27 → 07:06:33 EDT (11:05:27Z → 11:06:33Z) |
| Declared void by | Chief of Staff (Orchestrator), 2026-10-28 ~07:29 EDT. Steve, 07:28 EDT: "Looks like you choked the evaluator model and it didn't produce" |
| Counts against | the budget, not the generation cap. No N1–N8 verdict from this batch is used for the pass rule. |

## Evidence (sha256, from the batch dir)
| File | sha256 |
|---|---|
| `BATCH-MANIFEST.sha256` (220 lines) | `1556906a5fd8f6a671d65b9acb391d4707fec12d9180237012a6a3f9dbcaf9ee` |
| `n6/harness-eval-glm-b1.log` (full E-GLM log, 3 entries; holds control texts, never committed) | `80de3e9f650d723d9a545dc60f8f4d2a764bf7a5f8f36f0a1d070c6c2473368b` |
| `n6/N6-batch.json` | `aaffc0a0acd2cf52f233891df587d9e22a89b23b7d5c828932ba9a437e5b8f97` |
| `s1/summary.json` | `2b448e7b81542d8d8c7066ddfea9ed9b21b7e4a677f96468790eebd979405b30` |
| `s1/run.log` | `2fd6ef1da3b1e565e6b13144d7912bf34e977dea5a727f360c502e6b975de000` |
| `p5/P5-check.json` (P5(e) PASS, exit 0) | `037aacb247d2beb5e54e2f51d7918a72a005113a8c04545c09fb8ecd38d3b1a6` |

## Cause (a): the controls copy was made read-only (S1: N1, N2, N5, N7, N8 and the mutants depend on the environment)
Handoff section 2 ran `cp -a "$SRC" "$B/controls" && chmod -R a-w "$B/controls"`. Frozen `subject.py:29` copies each
fixture with `shutil.copytree`, which keeps file modes. So the emitter's own working copy was read-only, and
`kit/emit_custody.py` exited 1 with `PermissionError: [Errno 13] Permission denied: …/job/custody/record.custody.json`
on fixtures **F-genreply-full, F-maker-10min and F-single-call** (`s1/subject/runs/<F>/emit.json`, exit 1, all three).
S1 `summary.json`: controls "as expected", mutants "as expected"; subject N1 FAIL, N2 ERROR, N3 FAIL, N4 PASS, N5 FAIL
(`emitter exit 1 / record absent`), N7 FAIL, N8 FAIL. Every FAIL or ERROR that runs on those three fixtures was caused by
the environment, not by the subject. The mutant outcomes ran in the same read-only environment, so they cannot be
trusted either. This was an Orchestrator error in the handoff. The instrument and the subject are not at fault.

## Cause (b): E-GLM output cap of 800 tokens (N6 void)
Frozen `n6_batch.py` hard-codes `--max-tokens 800`. All 3 calls (`n6-b1-1` subject, `n6-b1-2` G-c1, `n6-b1-3` G-p1;
Z.AI, pin `z-ai/fp8`) returned `finish_reason: "length"`, with 797/798/798 reasoning tokens out of 800 completion tokens
and `content: null`. or_call exited 0 each time and wrote empty replies. `N6-batch.json`: `controls_ok: false`,
`subject_verdict: null`, `N6: "void"`. Fix: AMENDMENT-4 (pending approval) sets the cap to the endpoint maximum, 131072.

## Cause (c): minor; the seal listed itself
The section-6 command wrote `BATCH-MANIFEST.sha256` inside the tree it was hashing, so line 1 is the file itself with the
empty-file hash `e3b0c442…b855`. The other 219 lines are valid. The batch-2 handoff excludes the file.

## Spend (E-GLM)
Sum of `total_cost` in the generation replies: **$0.00571275** (0.00460405 + 0.00056935 + 0.00053935). Prompt tokens:
28027 / 1129 / 1185. Key usage moved 0.1463695 → 0.1515429 (Δ $0.0051734; key usage can lag the generation totals).
Job spend so far is about $0.152, against a cap of < US$10.

## Real signal (not caused by the environment): N1 and N3 FAIL on `extra-1-job-rejected`
That fixture was not affected. The emitter exited 0 and wrote a record (`s1/subject/runs/extra-1-job-rejected/emit.json`).
- **N1 FAIL:** "maker call(s) without the logger's sent_at/received_at". The record's `startedAt` and `producedAt`
  do not equal the logger times, which are absent (None). So the subject writes run times that the harness log does
  not support. (The fixture's own time values are held-out content and are left out here.)
- **N3 FAIL:** "no time field names a {file, line} source in x-plumbline (timeSources | time_sources | times)". The
  record's time fields (bar frozenAt and approval times, startedAt, producedAt, check times, disposition time) have no
  source map.
These verdicts will very likely repeat in batch 2. If so, iter1 fails the pass rule on N1 and N3 whatever N6 says.

## Not addressed (instrument note, frozen)
`subject.py` copies fixtures with their modes, so a read-only controls copy breaks every emitter run. This makes the
instrument fragile but is not a subject defect. It is frozen and was not changed. Logged here for FOLLOW-UPS.
