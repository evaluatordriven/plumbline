# iter3 inputs (generation 5, AMENDMENT-6 DRAFT: cap 3 E-DI iterations)
- **Status.** DRAFT. These are used only if Steve approves AMENDMENT-6 and `AMENDMENT-6-apply.sh` has run.
- **`maker-messages-gen5.json`** (sha256 `d188cb80871fa959c43af2cde5588cc4ab8319eba00606ca212878f3662b0caa`) is the
  Maker's call-1 prompt for generation 5.
  - It is built by `../build_maker_messages_gen5.py`, which is deterministic; re-run it and `cmp`, writing under
    `/workspace/edi-work/…`, never `/tmp`.
  - Its SYSTEM text (the whole-file OUTPUT CONTRACT, DECISIONS D6) is build_maker_messages.py's, with the base commit
    changed to `73863fb` (the gen-4 Maker commit).
- **Built from:**
  - the frozen bar (N1–N9 rows and the operator rule);
  - custody SPEC CL1-9/CL1-15 (verbatim, @3e3ca58);
  - the same source files as gen 3 and gen 4, read at `73863fb`, plus the two inputs of the repository's own synthetic
    fixture `tests/fixtures/custody/job-rejected` (`inputs/custody-events.jsonl`, `inputs/custody.json`), which is
    public and at `73863fb`;
  - the frozen harness `or_call.py`;
  - the Evaluator's iteration-2 findings: the S1 scores, the N3 instrument reasons on `extra-1-job-rejected`, a plain
    statement of what that run is, and E-GLM's CONFORMS reply on the subject call `n6-b3-2`. These come only from the
    committed, control-free evidence in `custody/evidence/eval/iter2-b3/`.
- **No held-out content.** No held-out control or fixture content is included (scanned against
  `/workspace/next-job-controls` and `/workspace/next-job-draft`: 0 non-public lines). The builder refuses to run if
  an unredacted record value is present, or if the failing runs or scores differ from what its text states.
- **Handoffs:**
  - `../iter3-maker.md` (generation 5; the ledger sha is filled by AMENDMENT-6-apply.sh).
  - `../iter3-evaluator-b4.TEMPLATE.md` (batch 4; `<MAKER_SHA>` and `<LEDGER_SHA>` are filled after gen 5).
- **Digests:** `../iter1/MANIFEST.sha256` (the one handoffs manifest).
