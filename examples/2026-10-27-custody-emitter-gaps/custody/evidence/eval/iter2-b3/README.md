# E-DI Evaluator batch 3, iteration 2 — committed evidence

Source: `/workspace/edi-batches/2026-10-27-custody-emitter-gaps/iter2-b3/` (outside the repo). It is sealed by
`BATCH-MANIFEST.sha256` (sha256 `d4bec77d36f14bfca019aad13849f64a4c74029d6e8fd1f470b9ab2046a07243`, copied here).
In a file name, `--` stands for `/` in the batch dir, so `s1--summary.json` is `s1/summary.json`.

- **Verbatim copies.** Each one's sha256 equals its BATCH-MANIFEST line (checked 2026-10-28 ~09:20 EDT): rev.txt,
  s1/{exit, summary.json, run.log, permission-errors.txt, subject/N3-extra-1-job-rejected.json}, p5/{exit,
  P5-check.json, P5-check.stderr}, n6/{exit, stdout.json, stderr.txt, key-usage-before.json, key-usage-after.json,
  n6-b3-2.messages.json, n6-b3-2.reply.txt}.
  - `n6-b3-2` is the subject call: the rubric plus the subject's code, with no control content.
  - `s1--subject--N3-extra-1-job-rejected.json` is the one failing S1 check. Its run is the repository's own synthetic
    fixture `tests/fixtures/custody/job-rejected` (public, at the subject commit), not a held-out fixture, so it is
    committed whole.
- **Redacted, by digest.**
  - `n6--N6-batch.redacted.json`: the lines cited on the held-out controls (G-c1, G-p1) are redacted.
  - `s1--subject-verdicts.digest.json`: one row per S1 per-check file, giving verdict, reason and full-file sha256.
    Record time values quoted from held-out fixtures (F-* runs) would be redacted; in this batch every F-* run PASSes,
    so no reason carries one.
- **Not committed.** These are held-out material: the controls copy and its listings, `n6-b3-{1,3}` (G-c1 and G-p1),
  the other S1 per-check JSONs, run dirs and fixture records, mutants, and the full E-GLM log. They are present in the
  BATCH-MANIFEST by sha256 only.
- **E-GLM log (D4).** `../../harness-eval-glm-b3.log` is the redacted copy, made by `handoffs/redact_glm_log.py`.
  `../../harness-eval-glm-b3.log.full.sha256` holds the digest of the unredacted log, `beb96465…f5b8`.
