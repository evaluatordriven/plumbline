# Amendment 4 (post-freeze, Buyer) — E-GLM output cap: job 2026-10-27-custody-emitter-gaps

> **STATUS: APPLIED** by `AMENDMENT-4-apply.sh` after the Buyer's approval below.

| Field | Value |
|---|---|
| Decided by | Steve Moitozo II (S2: Owner, Buyer, Specialist-adopter), acting as Buyer |
| Words, verbatim | "As Buyer I approve AMENDMENT-4: n6_batch.py max-tokens 800 to 131072, n6 sha 61676024…ee81, manifest f0ed1caf…80e7, bar 3ced9bc0… unchanged. Apply it, push, and send the Evaluator the batch-2 handoff now." |
| When | 2026-10-28T11:36:00Z (UTC; America/New_York is UTC-4) |
| Channel / relay path | Chief of Staff chat, question card t63s373 |
| Amends | One frozen file: `custody/freeze/instrument/n6_batch.py` (the E-GLM batch builder for N6). Only the `--max-tokens` value changes, on docstring line 12 and code line 69: **800 → 131072**. |
| Frozen set | `custody/MANIFEST.sha256` changes on one line (the n6_batch.py entry). The bar is **unchanged**: bar.md sha256 `3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b`. |

## Digests (what the Buyer approves)
| Item | Before (freeze) | After (this amendment) |
|---|---|---|
| `custody/freeze/instrument/n6_batch.py` | `965f6d9098462160e68716ae1ec3256dee896357700c3cc1ae9dad0b629859bd` | `616760242939ae5da88310909a84ce9e6bd464f0e55ae7005f2714d7d749ee81` |
| `custody/MANIFEST.sha256` | `2e9a77fb60a57bdfe889ab7075734c71e62eb67696a7f678a082d8007937dcdd` | `f0ed1caf047e12eaa232df235343fae3b07603ac2fe5f8de0e293c93e8f680e7` |
| `custody/bar.md` | `3ced9bc0…a970b` | unchanged |
| `custody/controls/MANIFEST.sha256` | `9764d8e4…60bf` | unchanged |

The exact change is `AMENDMENT-4-n6_batch.patch` (sha256 `1c91d6158dda43337d159fb0548b1b5bf15722cfe937d40eabbfb983f84dc269`):
```diff
@@ -9,7 +9,7 @@
 Each call: or_call.py --seat eval-glm --model z-ai/glm-5.3-flash --ledger LEDGER (pin z-ai/fp8)
---log OUT/harness-eval-glm-b<N>.log --call n6-b<N>-<k> --temperature 0 --max-tokens 800.
+--log OUT/harness-eval-glm-b<N>.log --call n6-b<N>-<k> --temperature 0 --max-tokens 131072.
@@ -66,7 +66,7 @@
-                                "--messages", str(mf), "--out", str(rf), "--temperature", "0", "--max-tokens", "800"],
+                                "--messages", str(mf), "--out", str(rf), "--temperature", "0", "--max-tokens", "131072"],
```

## Why
E-GLM batch 1 for iter1 (subject `7cc38f8`) is void (`EVAL-ITER1-BATCH1-VOID.md`). All 3 calls to `z-ai/glm-5.3-flash`
ended with `finish_reason: "length"`, 797–798 reasoning tokens of the 800 allowed, and `content: null`. So no reply held
a `VERDICT:` line. GLM 5.3 Flash reasons by default, and the frozen cap of 800 output tokens was used up by reasoning.
Steve, 2026-10-28 07:28 EDT: "Looks like you choked the evaluator model and it didn't produce". His standing preference
is no reasoning limit, with the output cap at the model's maximum. This is the same fix as gen 1 (GEN1-FAILURE.md).

## Source for the value
`max_completion_tokens` = **131072** for the pinned endpoint "Z.AI | z-ai/glm-5.3-flash-20260826" (`tag z-ai/fp8`).
Its `context_length` is 1048576, prompt costs $0.15/M tokens and completion costs $0.50/M. `supported_parameters` lists
`max_tokens`. Source: https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints (public, no key). It was fetched
2026-10-28T11:29:09Z (07:29 EDT). The snapshot is `AMENDMENT-4-glm-endpoints-2026-10-28T112909Z.json`, sha256
`fb14ed6c1daaf949a99db3e9aeffd4cd35c394c418c835fa3bf851d10dde8a46`.

## What still holds (token-related parsing assumptions)
- **No reasoning parameters.** n6_batch.py passes only `--temperature 0 --max-tokens N` to the frozen `or_call.py`
  (`55e8981c…6b38`). or_call sends `max_tokens` only when given, and sends no `reasoning`, `reasoning_effort` or
  `include_reasoning`. So GLM reasons at its default, unlimited except by the cap.
- **The verdict is read from content only.** or_call writes `choices[0].message.content` (or `""`) to the reply file.
  `parse()` takes the first `VERDICT:\s*(CONFORMS|DOES_NOT_CONFORM)` and the first `LINES:` line from that file.
  Reasoning text is never in the reply file, so a larger cap changes how much room the model has, not what is parsed.
  A reply that still ends `length` with no content parses to verdict None, and N6 is `void` as before.
- **The cap fits the context.** The largest batch-1 prompt was 28027 tokens. 28027 + 131072 is far below the 1048576 context.
- **Unchanged and not addressed here:** the rubric, the control set, the shuffle seed, the parse regexes, the pin and the
  scoring rule. The parse takes the first `VERDICT:` match, which was already true at 800.

## FROZEN-BUILD header (decision for Steve)
Line 2 of n6_batch.py stays `# STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z …`, unchanged, because this amendment changes
only the max-tokens value. p5check (P5(e)) does not pin file digests. It requires a header whose build time is no later
than the ledger freeze (2026-10-27T21:57:46Z), so the unchanged header still PASSES (simulated on a copy). The header
time then dates the file's original build, not these exact bytes. This record and the ledger line are where the change
is written down. Restamping the header with a post-freeze time would FAIL P5(e) ("build time … later than the ledger
freeze"). A second freeze event would also fail ("exactly one required").

## Records that cite the old digests (kept as history, not edited)
- `FREEZE-RECEIPT.json` `manifestDigest` 2e9a77fb…, and the Buyer approval statement "…with manifest 2e9a77fb…": this
  amendment supersedes that digest for later runs.
- `AMENDMENT-3-time-bound.md` cites 2e9a77fb… as the frozen set at that time.
- Nothing pins the n6_batch.py digest except `custody/MANIFEST.sha256`. p5check, run_instrument.sh and subject.py do not
  read `custody/MANIFEST.sha256`. The Evaluator's E2 precondition (`sha256sum -c MANIFEST.sha256`) does, and passes on the
  regenerated manifest.

## Unchanged
- **Money cap:** < US$10. **Time bound:** ends 2026-10-28 13:15 EDT (17:15Z), per AMENDMENT-3. **Generations:** cap 3.
- Every dimension N1–N9, P1–P6, the thresholds, controls, pins, seats and the operator rule.

## Ledger line (appended by `AMENDMENT-4-apply.sh`)
`{"event": "amendment", "n": 4, "at": <apply time>, "by": "Steve Moitozo II (S2)", "role": "buyer", "decided_at": <A4_DECIDED_AT>,
"file": "AMENDMENT-4-n6-max-tokens.md", "sha256": <sha of this file as applied>, "terms": {"n6_batch_max_tokens": {"from": 800, "to": 131072},
"n6_batch_sha256": {"from": "965f6d90…59bd", "to": "61676024…ee81"}, "manifest_sha256": {"from": "2e9a77fb…dcdd", "to": "f0ed1caf…80e7"},
"bar_sha256": "unchanged 3ced9bc0…a970b", "source": <endpoints URL + snapshot sha>}, "recorded_by": "Chief of Staff (Orchestrator)", "note": …}`
