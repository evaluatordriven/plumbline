# Method, job 2026-10-28-custody-times-ledger-spend

Maker: DeepSeek V4.1 Flash 1017 (deepseek/deepseek-v4.1-flash-1017) via openrouter.ai, provider order deepinfra/fp8,
no fallbacks, ZDR. Every Maker call was issued by a harness operator, the E-DI Maker bot (a Grok Bot), through the
frozen harness; the operator extracted the returned files verbatim (handoffs/extract_files.py) and committed them on
maker/custody-times-ledger-spend/iterN. This was instructed, not enforced.

Iterations (one generation each; bar cap 3):
- 1: calls maker_iter1_* (harness-maker-deepseek.log, -guide-iter1.log), revision 1cb410b. Batch 1: regenerate.
- 2: calls maker_iter2_* (harness-maker-deepseek.log, -guide-iter2.log), revision c882646. Batch 2: regenerate.
- 3: calls maker_iter3_fix_a1..a4 (harness-maker-deepseek.log), revision f95e0d3. Batch 3: accept (43/43 with
  Amendment 2's T6; EVAL-ITER3-VERDICT.md).

Maker calls left out of the record's maker call list (`maker.calls`): maker_iter1_ledger_a1, maker_iter1_docs_a1,
maker_iter3_fix_a1 and maker_iter3_fix_a2 (their /api/v1/generation fetch returned 404, so the base emitter cannot read
an endpoint for them) and the two guide logs (the base emitter reads one Maker log). They stay in the evidence logs.

Evaluators: S1 (custody/freeze/instrument/run_instrument.sh, scheck.py) and E-GLM (z-ai/glm-5.3-flash via
openrouter.ai, provider z-ai/fp8; jbatch.py, rubric-J1..4.md). E-GLM ran as four checks with one log each; the record
uses one merged log per batch (harness-eval-glm-bN.log), redacted of held-out control text
(handoffs/close/redact_glm_log.py). S1's batch-3 per-check evidence (custody/evidence/<check>.json, T6-amend2.json)
is filed redacted where a check echoed held-out fixture values (handoffs/close/redact_s1_evidence.py: each such value is
replaced by a fixed marker; ids, verdicts and reasons are kept); the full files stay on the Owner's box, sha256 in
custody/evidence/HELD-ON-BOX.sha256.
