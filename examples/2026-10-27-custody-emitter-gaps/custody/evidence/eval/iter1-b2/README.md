# E-DI Evaluator batch 2, iteration 1 — committed evidence

Source: `/workspace/edi-batches/2026-10-27-custody-emitter-gaps/iter1-b2/` (outside the repo). It is sealed by
`BATCH-MANIFEST.sha256` (sha256 `abea7b104bf3f0c2c01e5ea6a0f0a8dbf199f29c45c0aa834c7f3aa84dc9319f`, copied here).
In a file name, `--` stands for `/` in the batch dir, so `s1--summary.json` is `s1/summary.json`.

- **Verbatim copies.** Each one's sha256 equals its BATCH-MANIFEST line (checked 2026-10-28 ~07:52 EDT): rev.txt, s1/{exit,
  summary.json, run.log, permission-errors.txt}, p5/{exit, P5-check.json, P5-check.stderr}, n6/{exit, stdout.json,
  stderr.txt, key-usage-before.json, key-usage-after.json, n6-b2-2.messages.json, n6-b2-2.reply.txt}. `n6-b2-2` is
  the subject call: the rubric plus the subject's code, with no control content.
- **Redacted, by digest.**
  - `n6--N6-batch.redacted.json`: the lines cited on the held-out controls are redacted.
  - `s1--subject-verdicts.digest.json`: one row per S1 per-check file, giving verdict, reason and full-file sha256.
    The record time values that were quoted from held-out fixtures are redacted.
- **Not committed.** These are held-out material: the controls copy and its listings, `n6-b2-{1,3}` (G-p1 and G-c1),
  the S1 per-check JSONs, run dirs and fixture records, and the full E-GLM log. They are present in the BATCH-MANIFEST
  by sha256 only.
- **E-GLM log (D4).** `../../harness-eval-glm-b2.log` is the redacted copy, made by `handoffs/redact_glm_log.py`.
  `../../harness-eval-glm-b2.log.full.sha256` holds the digest of the unredacted log, `79e2decb…d46b`.
