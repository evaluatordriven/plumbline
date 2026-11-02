# GEN2-FAILURE — job 2026-10-27-custody-emitter-gaps · iteration 1, generation 2 (Maker)

Outcome: **failed: no patch applied.** Reported by the E-DI Maker bot at 22:16 EDT on 2026-10-27. The Orchestrator
re-read the facts below from `custody/evidence/harness-maker-deepseek.log` (entries 5–8) and
`custody/evidence/maker/iter1-gen2/`.
Flags: `--temperature 0 --max-tokens 131072 --gen-tries 12 --gen-wait 20`, with no reasoning parameter. The prompt was unchanged (`fbe8215d…1bd2`).

| call | sent → received (UTC) | served_by | finish | usage completion / reasoning / prompt (native) | generation tokens_completion / tokens_prompt (normalized) | cost | git apply --check |
|---|---|---|---|---|---|---|---|
| maker_iter1_gen2_call1 | 00:55:15 → 01:18:32 | DeepInfra | stop | 68436 / 62889 / 39618 | 62919 / 36493 | $0.020242935 | `corrupt patch at line 16` |
| maker_iter1_gen2_call2 | 01:19:14 → 01:31:24 | DeepInfra | stop | 35319 / 30264 / 45232 | 31110 / 41247 | $0.011056709 | `patch failed: kit/emit_custody.py:490` |
| maker_iter1_gen2_call3 | 01:32:04 → 01:54:09 | DeepInfra | stop | 71898 / 67114 / 50375 | 62482 / 45598 | $0.021779571 | `patch fragment without header at line 106` |
| maker_iter1_gen2_call4 | 01:54:57 → 02:12:58 | DeepInfra | stop | 52125 / 46768 / 55256 | 47342 / 49706 | $0.015957940 | `corrupt patch at line 164` |

- All 4 calls were served by the pin, and every generation reply returned 200. The gen-2 flags removed the gen-1
  problem: each call finished with `stop` and returned a complete diff block (16–18 KB). Each call took 12–23 min.
- Every diff failed `git apply --check`. The errors were malformed hunks (wrong line counts or context, and a hunk
  with no header). The model could not reliably produce a diff that applies to a ~50 KB file. Each failure went back
  verbatim as the next call. After 4 calls, generation 2 closed as failed.
- **Spend:** the per-call costs sum to $0.069037151, and the response `usage.cost` and the generation `total_cost`
  agree. The key's usage went from 0.038931696 to 0.107968847, a change of $0.069037151, which matches exactly. There
  was no counter lag this time, because the after-read was delayed as F5 asked. The job's Maker spend so far is
  $0.107969.
- **Two token-count notes** (they don't change the cost):
  1. The response's `usage` counts are higher than the generation reply's `tokens_*` counts. `usage` holds native
     (DeepSeek-tokenizer) counts, and they equal the generation reply's `native_tokens_*` fields. The generation
     reply's `tokens_prompt` and `tokens_completion` are OpenRouter's normalized counts. Cost is billed on native
     counts.
  2. On call 3, the reasoning count (67114, native) is higher than the generation reply's completion count (62482,
     normalized). The two numbers are on different scales, so this isn't a contradiction. In native counts,
     reasoning 67114 is less than completion 71898. The same mismatch exists on every call. It shows only on call 3
     because its answer outside reasoning was short (4784 native tokens) compared with the gap between the two
     tokenizers.
  For P6 and the record, use one scale per field. Spend is `total_cost`. Token counts should be quoted with their
  scale (native or normalized).
- The job clock started at the first Maker call, 19:44:48 EDT on 2026-10-27. Generation 2 ended at 22:12:58 EDT.
- Next step: Steve, 22:20 EDT: "Commit the gen-2 evidence, then run gen 3 with the model returning whole files that
  the Maker writes exactly as returned" (DECISIONS D6).
