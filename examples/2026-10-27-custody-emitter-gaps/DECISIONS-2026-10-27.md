# DECISIONS — 2026-10-27 · job 2026-10-27-custody-emitter-gaps

Owner/Buyer: **Steve Moitozo II (S2)**, 2026-10-27 18:31 EDT (22:31Z), verbatim (relayed by the Orchestrator):
> "Go with all four recommendations and start iteration 1"

The four recommendations were the Orchestrator's, made after the iter1 handoffs (commit f3a63de). They change no
frozen byte: bar.md (3ced9bc0…970b), MANIFEST.sha256 (2e9a77fb…dcdd) and controls/MANIFEST.sha256 (9764d8e4…60bf)
still verify. Done by the Chief of Staff (Orchestrator) drafter.

## D1 — Second ledger pin, seat `eval-glm`
- Why: frozen `custody/freeze/instrument/n6_batch.py` calls `or_call.py --seat eval-glm --ledger …`; the evaluator's
  pin was declared as seat `E-GLM`, so the frozen instrument could not find a pin (exit before any network call).
- Done: `python3 kit/custody_ledger.py pin --job-dir <job> --seat eval-glm --provider Z.AI --slug z-ai/fp8 --host api.z.ai --via openrouter.ai`
  → `logged pin at 2026-10-27T22:32:11Z (eval-glm -> Z.AI [z-ai/fp8] at api.z.ai via openrouter.ai)`. Same values as
  the `E-GLM` pin. No `eval-glm` (or `E-GLM`) call had been made, so this is a pin before the seat's first call.
  custody_ledger.py also added `routing.eval-glm` to inputs/custody.json. The emitter keeps reading the evaluator's
  pin under its id `E-GLM`; `eval-glm` is the harness seat name used by the frozen instrument and its log names
  (`harness-eval-glm-b<N>.log`).
- Verified (no model call): or_call's `pin_from_ledger` resolves `eval-glm` → (`z-ai/fp8`, `Z.AI`), `E-GLM` → same,
  `maker` → (`deepinfra/fp8`, `DeepInfra`); `or_call.py --check-key` → HTTP 200, usage 0.

## D2 — Generation-1 boundary line, hand-appended
- The bar (Operator rule) requires "the generation boundary is a ledger line written by the Orchestrator";
  `kit/custody_ledger.py` has no generation command (GAP; see FOLLOW-UPS.md F1). The Orchestrator appended one JSON
  line to `inputs/custody-events.jsonl` by hand at the moment it opened generation 1:
  ```
  {"event": "generation", "n": 1, "boundary": "open", "at": "2026-10-27T22:32:12Z", "by": "Chief of Staff (Orchestrator)", "seat": "maker", "prompt_sha256": "fbe8215d84559a319bb288fc33bf29be53ab0455b0d2c3fcf7ed6639953b1bd2", "note": "hand-appended by the Orchestrator: kit/custody_ledger.py has no generation command (DECISIONS-2026-10-27.md D2, FOLLOW-UPS)"}
  ```
- Ledger `inputs/custody-events.jsonl` sha256: before D1 `4ac248ef4c7dfc9504a92b13dc37e4086517987134d63f7cd5070d225ba0b301`;
  after D1 `01b26dc095bc7fe96e30a7ff9d18e709215f66bd380c924539b4b03e5b254c7a`;
  after D2 `2f5e9627a20b3a761328260c4d6ea70348d218c5d03e1948191be2529266ea18`.
- P5(e) re-run after D1+D2: `p5check.py --job <job>` → **PASS** (`P5-CHECK-gen1-open.json`).
- Disclosed for the record's `x-plumbline`: the emitter at ff350e3 reads an unknown event type as the last of its
  kind and ignores it; the line is evidence for the generation count, not a custody field.

## D3 — Brief path list clarified: `kit/custody_history.py` is in scope
- `brief.json` `artifact.paths` lists kit/emit_custody.py, kit/custody_ledger.py, tools/pack_stranger_bundle.py,
  docs/custody-emission.md, tests/fixtures/custody/**. Clarification (not an amendment of frozen bytes): the Maker may
  also edit `kit/custody_history.py`, the emitter's own module (imported as `H`): the gap-1 log parsing
  (`created` / `Date` basis) lives there, and the frozen N6 rubric (`n6_batch.py` FILES) already reads it as subject.
- The Maker prompt is unchanged: `handoffs/iter1/maker-messages.json` sha256 `fbe8215d84559a319bb288fc33bf29be53ab0455b0d2c3fcf7ed6639953b1bd2`
  (it already lists custody_history.py as editable).

## D4 — E-GLM harness log policy at close
- `n6_batch.py` logs the full requests, which carry held-out control text (controls/glm/G-*.txt). At close the
  Orchestrator commits `custody/evidence/harness-eval-glm-b<N>.log` with each held-out control text redacted
  (replaced by `[REDACTED held-out control <id> sha256 <digest of the control file>]`), plus
  `custody/evidence/harness-eval-glm-b<N>.log.full.sha256` holding the sha256 of the unredacted log. The full log
  stays outside the repo under `/workspace/edi-batches/2026-10-27-custody-emitter-gaps/`. Disclosed in the record's
  `separationGaps[]`/`x-plumbline` (CL1-15 evidence is the redacted log + full-log digest; full log available on request).

## D5 — Generation 1 closed failed; generation 2 opened (20:31 EDT)
Gen 1: 4 calls, no diff extracted (reasoning 19904 of max_tokens 24000; GEN1-FAILURE.md). Hand-appended close line
(n 1, boundary close, outcome failed, calls maker_iter1_call1..4) and gen-2 open line (prompt unchanged, fbe8215d…).
Ledger sha 2f5e9627…ea18 → 7ffa7636…d8b0 (close) → 359a2fa3…5933 (open). Per Steve (20:30 EDT, "stop choking the
model. Let it work"): gen 2 runs `--max-tokens 131072` (pinned endpoint deepinfra/fp8 max_completion_tokens, live
OpenRouter endpoints API), no reasoning/effort parameter, `--gen-tries 12 --gen-wait 20`. Command flags only, no
frozen file changed, no amendment.

## D6 — Generation 2 closed failed; generation 3 uses whole-file output (Steve, 22:20 EDT)
Steve Moitozo II, 2026-10-27 22:20 EDT (card answer): "Commit the gen-2 evidence, then run gen 3 with the model
returning whole files that the Maker writes exactly as returned".
Gen 2: 4 calls, all `stop` with complete diffs, none applied (GEN2-FAILURE.md). Hand-appended close line (n 2, outcome
failed). Gen 3 changes the output protocol in the handoff tools only. These files are not frozen:
build_maker_messages.py (new OUTPUT CONTRACT: `<<<PLUMBLINE-FILE path=…>>>` / `<<<PLUMBLINE-END path=…>>>` /
`<<<PLUMBLINE-DONE files=N>>>`), the new extract_files.py (writes the returned bytes exactly, all-or-nothing, allow-list
= brief paths + kit/custody_history.py per D3), and followup_messages.py (a failure goes back verbatim). The new prompt
is handoffs/iter1/maker-messages-gen3.json. The flags are unchanged from gen 2. The bar's operator rule ("a returned
patch … the operator never edits, completes or reorders it") is read with "patch" meaning the returned change, whole
files included. Writing files exactly as returned meets it, so bar.md and every MANIFEST-listed file are unchanged
and no amendment is needed.
