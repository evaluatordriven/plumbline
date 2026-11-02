# Maker method: job 2026-10-27-custody-emitter-gaps

Written by Chief of Staff (Orchestrator) for this job's custody record (`maker.method`). It describes how the
Maker worked. It is not a frozen file; its digest is taken when the record is emitted.

## Maker
- Model: DeepSeek V4.1 Flash 1017, `deepseek/deepseek-v4.1-flash-1017`, called through openrouter.ai with
  `provider {order:["deepinfra/fp8"], allow_fallbacks:false, zdr:true}` and the header
  `X-OpenRouter-Metadata: enabled`. Pinned with `custody_ledger.py pin` before the first Maker call.
- Harness: `custody/freeze/harness/or_call.py` (frozen). Each call is logged in full in
  `custody/evidence/harness-maker-deepseek.log`: the request body, the raw response and its headers including
  `Date`, and the `/api/v1/generation` reply.
- Input to each call: the frozen bar, the brief and the files named in that generation's handoff
  (`handoffs/iter*-maker.md`, the message files under `handoffs/iter*/`).
- Output: patches and whole files returned in the model's reply, applied to the job branch.

## Operator (not a custody party)
The E-DI Maker bot (a Grok Bot) operated the harness. It acted only as the harness operator:
- It issued the logged calls through the frozen harness.
- It applied the returned patches verbatim.
- It authored nothing in the artifact itself.

If a returned patch did not apply cleanly, or failed the tests, it went back to the Maker in a new logged call.
The operator never edited, completed or reordered a patch (bar.md, operator rule). This is disclosed in the
record's `separationGaps[]`.

## Generations
Five Maker generations over three E-DI iterations. The Orchestrator wrote each generation's open and close
as a line in `inputs/custody-events.jsonl`. The artifact under evaluation is the branch at `c7db5b0` (generation 5).
