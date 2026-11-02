# E-DI Evaluator batch 4, iteration 3 — committed evidence

Source: `/workspace/edi-batches/2026-10-27-custody-emitter-gaps/iter3-b4/` (outside the repo). It is sealed by
`BATCH-MANIFEST.sha256` (sha256 `8d06b7645f4bd8e19c33b4649aa1c4b36cf6652d3fa401d947e7a2e45358bcc0`, 267 lines, copied
here). In a file name, `--` stands for `/` in the batch dir, so `s1--summary.json` is `s1/summary.json`.

- **Verbatim copies.** Each one's sha256 equals its BATCH-MANIFEST line (checked 2026-10-28 ~10:31 EDT): rev.txt,
  s1/{exit, summary.json, run.log, permission-errors.txt, subject/N3-extra-1-job-rejected.json}, p5/{exit,
  P5-check.json, P5-check.stderr}, n6/{exit, stdout.json, stderr.txt, key-usage-before.json, key-usage-after.json,
  n6-b4-1.messages.json, n6-b4-1.reply.txt}.
  - In batch 4 the order was [subject, G-c1, G-p1], so `n6-b4-1` is the subject call: the rubric plus the subject's
    code, with no control content.
  - `s1--subject--N3-extra-1-job-rejected.json` is the S1 N3 check on the repository's own synthetic fixture
    `tests/fixtures/custody/job-rejected` (public, at the subject commit), the run that failed in iteration 2. It
    PASSes here and is committed whole.
- **Redacted, by digest.**
  - `n6--N6-batch.redacted.json`: the lines cited on the held-out controls (G-c1, G-p1) are redacted.
  - `s1--subject-verdicts.digest.json`: one row per S1 per-check file (15), giving verdict, reason and full-file
    sha256. Reasons quoting held-out fixtures (F-* runs) would be redacted; in this batch every run PASSes with an
    empty reason list, so nothing needed redacting.
- **Not committed.** These are held-out material: the controls copy and its listings, `n6-b4-{2,3}` (G-c1 and G-p1),
  the other S1 per-check JSONs, run dirs and fixture records, mutants, and the full E-GLM log. They are present in the
  BATCH-MANIFEST by sha256 only.
- **E-GLM log (D4).** `../../harness-eval-glm-b4.log` is the redacted copy (`b4dce825…9a8f`, calls n6-b4-2 and n6-b4-3
  redacted), made by `handoffs/redact_glm_log.py`. `../../harness-eval-glm-b4.log.full.sha256` holds the digest of the
  unredacted log, `9dee9705…ec4f`.
