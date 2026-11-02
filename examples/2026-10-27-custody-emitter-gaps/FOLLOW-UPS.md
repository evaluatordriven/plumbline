# FOLLOW-UPS — job 2026-10-27-custody-emitter-gaps

- F1 (from DECISIONS D2): add a `generation` subcommand to `kit/custody_ledger.py` (open/close boundary, n, seat,
  prompt digest, clock-stamped like the other events), and teach `kit/emit_custody.py` to read it. Until then the
  Orchestrator hand-appends the line and discloses it.
- F2 (from DECISIONS D1): one seat name per evaluator across instrument, ledger and record (n6_batch.py used
  `eval-glm`, the brief's evaluator id is `E-GLM`); next bar should fix the name before freeze.
- F3 (from DECISIONS D4): a redaction tool for harness logs that carry held-out controls (deterministic, with the
  full-log digest), so the close step is mechanical. Interim: `handoffs/redact_glm_log.py` (2026-10-28, used for
  b1/b2); a future instrument should ship it frozen.

## F4 — /api/v1/generation 404 → generation null (gen 1 calls 1, 3)
The frozen default (6 tries × 5 s) gave up after ~25 s. Gen 2 uses `--gen-tries 12 --gen-wait 20`. Future harness:
longer default wait, and an optional late re-fetch that appends (never rewrites) the generation record.

## F5 — key-usage counter lag
`--check-key` read ~30 s after the last call missed that call's cost ($0.010819). Future harness/handoffs: wait ≥ 2 min
or poll until stable before the after-read.

## F6 — no reasoning control in or_call.py
The harness sends no `reasoning` field, so a reasoning budget can only be steered through max_tokens. If a future job
needs `reasoning.max_tokens`/effort or a total-request timeout, that is a harness change (frozen; needs an amendment).

## F7 — S1 `subject.py` copies fixture file modes
`subject.py` copies each fixture with `shutil.copytree`, which keeps the file modes. A read-only controls copy (batch 1:
`chmod -R a-w`) therefore makes every emitter working copy read-only and breaks the runs (EVAL-ITER1-BATCH1-VOID.md).
Future instrument: copy with `copy_function=shutil.copyfile` (or chmod u+w the working copy), so control protection
cannot leak into the subject run. Frozen; this needs an amendment or the next bar.

## F8 — no spend cap enforced by `n6_batch.py` or `or_call.py`
Neither harness enforces a per-call or per-batch money ceiling. The < US$10 cap and the per-generation ceilings are
kept only by the Orchestrator's planning and the key-usage reads. AMENDMENT-4 raised N6's max_tokens to 131072, so a
runaway reply is bounded only by the endpoint. Future harness: a `--max-cost` per call (abort, or refuse to dispatch,
when the projected or `/generation` cost crosses it) and a batch total checked against GET /api/v1/key before each call.
