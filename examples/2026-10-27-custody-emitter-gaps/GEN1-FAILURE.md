# GEN1-FAILURE — job 2026-10-27-custody-emitter-gaps · iteration 1, generation 1 (Maker)

Outcome: **failed — no patch.** Reported by the E-DI Maker bot 2026-10-27 20:21 EDT; facts below re-read by the
Orchestrator from `custody/evidence/harness-maker-deepseek.log` (4 entries) and `custody/evidence/maker/iter1/`.

| call | sent_at → received_at (UTC) | wall | served_by | finish | completion / reasoning tokens | prompt tokens | usage.cost | /generation | or_call exit |
|---|---|---|---|---|---|---|---|---|---|
| maker_iter1_call1 | 23:44:48 → 23:51:41 | 6m53s | DeepInfra | length | 24000 / 19904 | 39618 | $0.010939 | 404 ×6 → null | 5 |
| maker_iter1_call2 | 23:52:33 → 23:58:52 | 6m19s | DeepInfra | length | 24000 / 19904 | 43788 | $0.007587 | 200 ($0.007587) | 0 |
| maker_iter1_call3 | 23:59:32 → 00:08:40 | 9m08s | DeepInfra | stop | 19907 / 19904 | 47958 | $0.009587 | 404 ×6 → null | 5 |
| maker_iter1_call4 | 00:09:24 → 00:19:43 | 10m19s | DeepInfra | length | 24000 / 19904 | 48034 | $0.010819 | 200 ($0.010819) | 0 |

- All 4 calls: served by the pin (DeepInfra, `deepinfra/fp8`, `allow_fallbacks:false`, `zdr:true`), verdict ok.
  Request: `max_tokens 24000`, `temperature 0`, no reasoning parameter (model default: reasoning on, effort high).
- Cause: reasoning consumed exactly 19904 = 24000 − 4096 tokens in every call, leaving 4096 for the answer. Calls 1, 2
  and 4 returned a diff truncated mid-hunk (finish `length`, ~14 KB); call 3 returned only "```". `extract_patch.py`
  found no closed ```diff block in any reply, so nothing was applied or tested; each failure went back verbatim
  (followup_messages.py) as the next call. 4 calls = the generation's call limit → generation 1 closed failed.
- Spend: Σ response `usage.cost` = **$0.038932**; Σ generation `total_cost` = $0.018406 (calls 2 and 4 only).
- **Gap — /generation 404 → null (calls 1, 3):** `/api/v1/generation?id=…` answered 404 on all 6 tries (6 × 5 s
  waits ≈ 25 s after the reply); logged `generation: null`, or_call exit 5. The serving provider is still evidenced by
  `response.provider` and `openrouter_metadata` (verdict ok); `total_cost` for those calls comes only from the
  response's `usage.cost`. For P6 the spend sum uses `usage.cost` per call, and the generation-null calls are flagged.
- **Key-usage counter lag:** key usage before 0 → after $0.028112767; Σ usage.cost $0.038932 − $0.028113 =
  $0.010819 = exactly call 4's cost (the after-read ran ~30 s after call 4; OpenRouter's counter had not caught up).
  The cross-check holds once that lag is accounted for; re-read the key usage before gen 2 starts.
- **Operator pre-send relaunch:** the Maker bot reported one relaunch of a call command before sending, due to an
  unset shell variable; or_call made no request (no log entry, no spend). Disclosed, no effect on the record.
- Not a frozen-file problem: the bar, harness and prompt were followed as written. Generation 2 changes only command
  flags (handoffs/iter1-maker.md, "Generation 2"). Steve (20:30 EDT): "My instinct it to advise the Maker to stop
  choking the model. Let it work".

Ledger (`inputs/custody-events.jsonl`) sha256: before close `2f5e9627…ea18` → after gen-1 close `7ffa7636c87b1422520f65ff2ea633fe903fef44439e1de0c32f306042b2d8b0`
→ after gen-2 open `359a2fa3a81e6dcd763eed77b664f41c023012b73e54911d8e748045046a5933`.
