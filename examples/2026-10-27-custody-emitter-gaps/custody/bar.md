# BAR — Plumbline custody emitter: gaps 1–3

STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z — digest in BAR-DIGEST

- Job: `2026-10-27-custody-emitter-gaps` · Entry **A** (commissioned fix; see brief.json `proposed.entry_reason`)
- Mode `scored` · profile `full` · own record claims **CL1**
- Bar author of record: **Steve Moitozo II (S2)** (adopts this draft). Drafter: Chief of Staff (Orchestrator) drafter.
- Artifact base: `smoitozo/plumbline` main @ `ff350e3` (tree `4abcfa08`).

## Pins
| Pin | Value |
|---|---|
| custody SPEC / checker | v0.9.6 @ `3e3ca58`; SPEC sha256 `a289ac91…294f`; schema `ad03af92…9f9f`; check.py `aaeb7e05…cd18` |
| Doctrine | Plumbline DOCTRINE.md v0.1 @ `dc61854` (sha256 `c9b45567…d6ed`) |
| E-DI corpus | `a48a4645aaa29947fdc17168d26c69c849941580`, Contracts 1.22.0, Mandate sha256 `ff39f4f1…1de2` |
| Maker model | `deepseek/deepseek-v4.1-flash-1017` via openrouter.ai; `provider {order:["deepinfra/fp8"], allow_fallbacks:false, zdr:true}`; header `X-OpenRouter-Metadata: enabled`. Upstream DeepInfra, host `api.deepinfra.com`. |
| Model evaluator | `z-ai/glm-5.3-flash` via openrouter.ai; `provider {order:["z-ai/fp8"], allow_fallbacks:false, zdr:true}`; same header. Upstream Z.AI, host `api.z.ai`. |
| Upstream choice | Orchestrator, from `/api/v1/endpoints/zdr` read 2026-10-27 16:42 EDT (snapshot sha256 `a93cf2c7…3817e`). Both pinned with `custody_ledger.py pin` before any call. Maker and evaluator differ in family (deepseek ≠ glm) and endpoint. |
| Harness | `freeze/harness/or_call.py` sha256 `55e8981c1b75a30aef551ac0810b0891b7d41df8d32878db9710650d7ba06b38`. Reads the key by path, never logs it; writes one JSON harness log entry per call: request (Authorization redacted), response headers incl. `Date`, raw response, `/api/v1/generation` reply. |

## Scale and pass rule (every dimension)
Binary. `1` = the check PASSes as stated; `0` = anything else, including NOT-RUN. Custody scale: anchors
`{"0","1"}`, threshold `1`, floor `0`. Bounds T_accept 1, T_dim 1, T_reject 0, cap 3 generations.
pass ⇔ every dimension scores 1. A 0 regenerates (< cap) or goes `needs_owner` (at cap). Algebra never
rejects; `rejected` is the Owner's call. Budget < US$10 and < 10 h; either breach → `needs_owner`.

## Dimensions (artifact)
Fixtures are run by S1 against the Maker's revision of the emitter. "Fixture job" = a job dir under
`tests/fixtures/custody/` with `inputs/custody-events.jsonl`, harness logs and an `inputs/custody.json`.

| ID | Criterion (PASS when) | Evaluator | Evidence |
|---|---|---|---|
| N1 | For every emitted record (all fixture jobs + every real job in the run), `maker.startedAt` = the call logger's request-send time (`sent_at`, written by `freeze/harness/or_call.py`) of the **first** Maker call and `producedAt` = its reply-receive time (`received_at`) of the **last** Maker call, read from the Maker harness log and compared at whole seconds UTC. Equal only if that log's send and receive times are equal. A Maker call logged without both times fails. Fixture `single-call` (one Maker call, send ≠ receive) is in every run. (Amendment 1.) | S1 script | `evidence/N1.json` (per record: source lines, both times, verdict) |
| N2 | On fixture `maker-10min` (two Maker calls; the first call's `sent_at` and the last call's `received_at` 600 s apart), the emitter gives `producedAt − startedAt = 600 s`. (Planted half = control C-N2p.) | S1 script | `evidence/N2.json` |
| N3 | Every time field in the record (`frozenAt`, `startedAt`, `producedAt`, `checks[].at`, approvals, disposition) has an `x-plumbline` source naming a ledger or harness-log file and line; that line carries that time. Any time without a source fails. | S1 script | `evidence/N3.json` |
| N4 | On fixture `genreply-null` (a model pass whose `/api/v1/generation` reply is missing/null) the emitter either (a) exits non-zero with a named error, or (b) records that evaluator's CL1-15 evidence absent so check.py reads NOT-CHECKABLE **and** writes an `x-plumbline` flag naming the pass. It never writes an `endpoint` no reply evidences. | S1 script | `evidence/N4.json` (exit code, stderr, record diff, check.py output) |
| N5 | On fixture `genreply-full` (all replies present) N4's procedure passes and each endpoint equals the reply's provider host. (Planted half = control C-N5p.) | S1 script | `evidence/N5.json` |
| N6 | The generation-reply code path in `kit/emit_custody.py` has no fallback that derives an `endpoint` from routing config or provider pins. Answer: `CONFORMS`/`DOES_NOT_CONFORM` + cited line numbers. | **E-GLM** model (logged OpenRouter call) | `evidence/N6-<call>.json` + harness log + generation reply |
| N7 | Each stranger bundle zip contains the record, bar, subject files, every `checks[].evidence` and `external[].evidence` file, **plus** `inputs/custody-events.jsonl` and every maker/evaluator harness log the record's times or endpoints came from. | S1 script | `evidence/N7.json` (zip listing vs required list) |
| N8 | Stranger procedure (frozen I7: empty HOME, `env -i`, anonymous clone of custody at pin): check.py reads OK **and** the stranger re-derives `startedAt`, `producedAt` and each endpoint from the bundled ledger/logs, equal to the record. | S1 script (stranger) | `evidence/N8.json` + transcript |
| N9 | **Control, not scored.** Bundle with the ledger removed: N7 and N8 FAIL while check.py still reads OK. Proves N7/N8 catch what CL1 alone does not. Recorded in `controls[]` (C-N9p). | S1 script | `controls/evidence/C-N9p.json` |

## Process requirements for this job's own record (CL1)
These are not artifact dimensions; the Orchestrator verifies them before close, and check.py on the
job's own record is the final read. Each is mapped to its CL1 line.

| P | Requirement | CL1 line(s) |
|---|---|---|
| P1 (a) | Every judging batch of E-GLM contains ≥1 clean (`conforms`) and ≥1 planted (`does_not_conform`) control, sent in the same batch as the N6 read. Every S1 batch likewise (C-N1p, C-N2p, C-N5p, C-N9p planted + clean fixtures). | CL1-9, CL1-16 |
| P2 (b) | E-GLM is a logged OpenRouter call: `z-ai/glm-5.3-flash`, one ZDR upstream chosen by the Orchestrator, `provider {order:[tag], allow_fallbacks:false, zdr:true}`, `X-OpenRouter-Metadata: enabled`. The E-DI Evaluator bot runs and records it: raw request, raw response incl. provider metadata, and the `/api/v1/generation` reply, saved as `custody/evidence/harness-eval-glm*.log`. The record's `external[]` has a CL1-15 entry for E-GLM, `readBy` = Chief of Staff (Orchestrator) (not the Maker). The Evaluator bot issues **no score of its own**; it is not listed in `evaluators[]`. | CL1-15, CL1-6, CL1-8 |
| P3 (c) | One harness log per seat: Maker `harness-maker-deepseek*.log`, E-GLM `harness-eval-glm*.log`, S1 run log. Every `model` block filled only from those logs and the ledger pin (Maker `{family: deepseek, identifier: deepseek/deepseek-v4.1-flash-1017, endpoint: <from log>, readOnly: false}`); `startedAt`/`producedAt` are never typed. The Maker's operator (E-DI Maker bot) only issues the logged calls and applies the returned patches verbatim; `maker.method` (method.md) states this, and `separationGaps[]` discloses it. Any Grok Bot party named in the record (operators, Orchestrator) uses `{family: "undisclosed", identifier: "grok.com/bot (version not disclosed)", endpoint: "grok.com"}`, and `separationGaps[]` carries verbatim: "Grokbot's underlying model(s) are not disclosed by its operator; family and identifier recorded as undisclosed." | CL1-4, CL1-1, CL1-11, CL1-15 |
| P4 (d) | Controls and fixtures are unreadable by the Evaluator seat (held outside its working tree; sha256 committed at freeze, bytes released into the batch only), or the shared-box readability is disclosed in `separationGaps[]`. | CL1-11 (disclosure); supports CL1-9 validity |
| P5 (e) | Frozen files say frozen: `bar.md`, `bounds`, `controls/README.md` and the `freeze/harness` and `freeze/instrument` files carry a header `FROZEN-BUILD <build time>` in the hashed bytes; the build time is no later than the ledger freeze event's time; and sha256 of the frozen `bar.md` equals the bar digest recorded in the ledger freeze event and the record's bar digest. Checked by S1 `freeze/instrument/p5check.py` (controls C-P5c clean, C-P5p and C-P5p2 planted). (Amendment 2.) | CL1-14 (bar digest is of the frozen bytes), CL1-1 (frozenAt) |
| P6 (f) | Spend observable: Maker and E-GLM cost from each `/generation` reply (`total_cost`) summed into `x-plumbline.spend`, cross-checked against the key's `usage` before and after (GET /api/v1/key). Grok Bot operator/Orchestrator spend declared **unverifiable** there. | none in CL1 — E-DI budget bound; disclosure via `x-plumbline` |

Operator rule (Maker): a returned patch that does not apply cleanly, or fails tests, goes back to the
Maker in a new logged call; the operator never edits, completes or reorders it. Each Maker generation is
one or more logged calls; the generation boundary is a ledger line written by the Orchestrator.

Emitter of this job's own record: base `main @ ff350e3` (not the artifact under test), from a clean
checkout with `PLUMBLINE_EXPECT_REVISION` set. Known limitation disclosed in `x-plumbline`: that emitter
has gap 1 (producedAt), which this job repairs.

Also required for CL1 but already standard: approvals (buyer + specialist-adopted, `by` Steve, barDigest)
recorded before the Maker's first call (CL1-3, CL1-1); evaluators ≠ maker/bar author, S1 author ≠ Steve
(CL1-6); every dimension N1–N8 has a check (CL1-7); score ≥ 1 ⇔ conforms (CL1-17); retention,
disposition, subject/bar digests (CL1-12/13/14).

## Seats
| Seat | Holder | Custody kind |
|---|---|---|
| Owner / Buyer / Architect / bar author | Steve Moitozo II (S2) | person |
| Specialist | custody SPEC v0.9.6 + DOCTRINE v0.1 §7, adopted, by Steve | adopted |
| Maker | DeepSeek V4.1 Flash 1017 via OpenRouter ZDR (deepinfra/fp8) | model, family `deepseek`, readOnly false |
| Maker operator | E-DI Maker bot — issues logged calls, applies patches verbatim, authors nothing | (not a custody party; disclosed) |
| Evaluator seat | E-DI Evaluator bot — operates S1 and E-GLM, files evidence | (not an evaluator entry) |
| Evaluator S1 | `freeze/instrument/run_instrument.sh` — author: Orchestrator drafter | script |
| Evaluator E-GLM | GLM 5.3 Flash via OpenRouter ZDR | model, family `glm`, readOnly true |
| Orchestrator | Chief of Staff (Grok Bot) | — (runs loop; `readBy` on CL1-15) |
