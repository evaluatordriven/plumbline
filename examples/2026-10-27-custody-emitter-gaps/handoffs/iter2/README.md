# iter2 inputs (generation 4, AMENDMENT-5: cap 4)
- `maker-messages-gen4.json` (sha256 `ef2cc81c…583c`): the Maker's call-1 prompt for generation 4, built by
  `../build_maker_messages_gen4.py` (deterministic; re-run and `cmp`). The SYSTEM text (whole-file OUTPUT CONTRACT,
  DECISIONS D6) is build_maker_messages.py's, with the base commit changed to `7cc38f8` (the gen-3 Maker commit).
- Built from: the frozen bar (N1-N9 rows and the operator rule); custody SPEC CL1-9/CL1-15 (verbatim, @3e3ca58);
  the same source files as gen 3, read at `7cc38f8`; the frozen harness `or_call.py`; and the Evaluator's
  iteration-1 findings. The findings are the S1 scores, the N1/N3 instrument reasons (record time values already
  redacted to `<held-out fixture value>`), and E-GLM's reply on the subject call `n6-b2-2`. They come only from the
  committed, control-free evidence in `custody/evidence/eval/iter1-b2/`. No held-out control or fixture content is
  included; the builder refuses to run if an unredacted record value is present.
- Handoffs: `../iter2-maker.md` (generation 4), `../iter2-evaluator-b3.TEMPLATE.md` (batch 3, `<MAKER_SHA>` and
  `<LEDGER_SHA>` to fill).
- Digests: `../iter1/MANIFEST.sha256` (the one handoffs manifest).
