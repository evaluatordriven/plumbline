# Custody emission runbook — custody/v1 records from Plumbline jobs

For the Orchestrator. This page covers how to run small real jobs that end `accepted`, `needs_owner` and
`rejected`, collect one custody/v1 record from each, and pack each record for a stranger. Plumbline makes no
model call on its own: every model call is one you make, through your own harness, or through the kit's product
harness `tools/edi/or_call.py` (see "The product harness: `tools/edi/`").

A record is judged at **two layers**. The **standard layer** is the custody corpus's own `checker/check.py` at
CL1; per SPEC.md line 141 it ignores every key that begins with `x-`. The **Plumbline layer** is
`kit/plumbline_verify.py`: it runs `check.py` first, requires OK, and then enforces the `x-plumbline` block the
emitter writes. `x-plumbline` is enforced by Plumbline's verifier only; the standard check.py ignores it. See
"The two layers" below.

## What a close now writes

A job that closes at a terminal state writes everything it wrote before, unchanged: the §5 records, `passes/`,
the packet facts, the run-log row and `inputs/`. It then writes one more file:

    dot-plumbline/jobs/<job-id>/custody/record.custody.json

That file is an in-toto Statement with predicateType `https://evaluatordriven.com/custody/v1`, following custody
SPEC.md v0.9.6 at `evaluatordriven/custody@3e3ca58de563`. The predicate holds only section-4 fields. Plumbline's
own facts sit under `predicate["x-plumbline"]` and the per-check, per-control and per-violation `x-plumbline`
keys:

- `schema` (`"plumbline/x-plumbline/v1"`), `verdict` and `terminal_state`.
- `outcome`.
- The final §5 record and the packet, each by sha256.
- Each violation's rule-4 `locator`.
- `gaps`, `times`, `time_tolerance_s`.
- `hand_times[]` — every hand time the record carries, each `{field, file, line, source}` — and `allowances`
  (`hand_times: {switch, writer, at}` only when `--allow-hand-times` was given and the set is not empty).
- `generations[]`, `evaluations[]`, `relays[]`, `amendments[]` and `spend` — the ledger's own events, each with
  its `inputs/custody-events.jsonl:<line>` source (see "Logging events live").
- `inputs` — a deep copy of the `x-plumbline` object in `inputs/custody.json`, when there is one. Input data
  appears only under `x-plumbline.inputs`; it never shadows the emitter's own keys.

`disposition.state` is copied from the packet's `disposition_state`. It never comes from the verdict.

| Exit code | Meaning |
|---|---|
| 0 | Complete. |
| 1 | Written, with a hard gap named in `x-plumbline.gaps`: a required fact had no source (left null/absent; fix the inputs and re-emit), or an OpenRouter routing request that did not ask for the pin, no fallback and ZDR (`routing.<seat>.request`; the run did it, so re-emitting cannot fix it). |
| 2 | Refused. There is no packet, or the job is not at a terminal state. Nothing written. |
| 3 | **Refused: the record would misstate its own history** (see "Refusals" below). This includes every hand time when `--allow-hand-times` is not given (`hand-time`). Every such fact is printed as `[kind] …`; nothing is written and an existing record is left as it was. `close` still closes the job and returns 3, with "CLOSED, BUT THE CUSTODY RECORD IS NOT WRITTEN". |

`plumbline_job.py close` runs the emitter, then `kit/plumbline_verify.py` on the new record. If the verifier
fails, close exits with the verifier's code (3 or 4), prints `NOT CLOSED: Plumbline verify failed (<kind>)`,
writes a run-log row `close_refused` with the kind, and writes **no** `closed` row; re-running close after a fix
retries. `plumbline_job.py custody` (re-emit) runs the verifier too and returns its code. Both accept
`--allow-hand-times` (passed to the emitter) and `--custody <checkout>` (default: env `PLUMBLINE_CUSTODY`).

## The two layers

The **standard layer** is the custody corpus's `checker/check.py`, run at the claimed level (CL1). It checks the
custody/v1 predicate. Per SPEC.md line 141 it **ignores every key that begins with `x-`**, so it never reads
`x-plumbline` — no matter what the extension says. A record that passes `check.py` has passed the standard layer
and nothing more.

The **Plumbline layer** is `kit/plumbline_verify.py`. It runs `check.py` first and requires OK; only then does it
enforce `x-plumbline`. It never relaxes a check: there is no switch on the command line, and the hand-time
allowance is read from the record, never supplied by the caller. So **`x-plumbline` is enforced by Plumbline's
verifier only; the standard check.py ignores it.**

    python3 kit/plumbline_verify.py --record R --files F --evidence E --ledger L --custody <checkout> [--json OUT]

The job's `custody.json` is the file `custody.json` beside `L` (the ledger, `inputs/custody-events.jsonl`).

| Exit | Meaning |
|---|---|
| 0 | OK at both layers. |
| 3 | The standard layer failed (kind `standard`; nothing else is checked). |
| 4 | The standard layer passed and a Plumbline check failed. |
| 2 | Cannot run: usage, a missing input, or a checker whose `check.py` sha256 is not the pin. |

Each failure prints one stdout line `FAIL <kind> <field> <file>:<line>`, and `--json OUT` writes
`{"exit": N, "failures": [{"kind","field","file","line"}]}`. The kinds:

| Kind | Enforces |
|---|---|
| `standard` | the standard `check.py` is OK (else exit 3, nothing else checked). |
| `schema` | every `x-plumbline` block validates against `schemas/x-plumbline/x-plumbline-v1.schema.json`, and `x-plumbline.schema` is `plumbline/x-plumbline/v1`. |
| `allowance` | `allowances.hand_times` is present whenever the hand-time set is non-empty, with the switch, the emitter's `writer`, and its tool-clock `at`. |
| `hand-time-unflagged` | a hand time the verifier recomputes from the ledger, `inputs/custody.json`, or a server-time log call is missing from `x-plumbline.hand_times[]`. |
| `flag-without-source` | a flag in `x-plumbline.hand_times[]` has no hand line behind it. |
| `events` | `generations[]`, `evaluations[]`, `relays[]` and `amendments[]` match the ledger one-to-one, each generation has a Maker call between its open and close, and each evaluation's verdict sha256 matches the file. |
| `relay-as-approval` | a relay is listed among approvals (a relay is a report, not an approval). |
| `spend` | `x-plumbline.spend` adds up: `calls_sum_usd` equals the sum of the harness logs' per-call `total_cost` within **US$0.0001** (rounding only), `total_usd = max(calls_sum_usd, key_delta_usd)`, and the key reading is stamped and read ≥ 3 min after the last settle. |
| `shadow` | input data appears only under `x-plumbline.inputs`; every emitter-owned key holds the value the verifier re-derives from the record, ledger and logs. |

A run that changes one of its inputs also fails (`writes`). The verifier never writes its inputs (V7), and it does
not import the emitter (V7), so its check is separate code.

## Where each fact about time, endpoint, approver and revision comes from

A time with no tool-written ledger line or logger time behind it is a **hand time**: refused by default
(`hand-time`), and with `--allow-hand-times` flagged in `x-plumbline.hand_times[]` and never verified (see "Hand
times" above). A logged time is still cross-checked against any typed value within 60 s. A typed host or approver
is refused when it differs from what the log or the ledger says.

| Fact | Source | A hand-entered value (a typed time with no tool stamp behind it) is… |
|---|---|---|
| `startedAt` | the maker harness log: the earliest call's logger `sent_at`/`received_at` | a hand time (`inputs-no-ledger`): refused by default; under `--allow-hand-times` flagged and never verified. Cross-checked against the log within 60 s |
| `producedAt` | the maker harness log: the last call's logger `received_at`/`sent_at` | a hand time, as for `startedAt` |
| `passes.<id>.at` (`checks[].at`) | the evaluator harness call linked to the pass (`passes.<id>.call`): its logger `received_at` | a hand time even when a call is linked (`inputs-no-ledger`): refused by default, flagged under the switch, never verified; cross-checked within 60 s |
| control times (`controls[<id>].at`) | the linked evaluator call (`controls[].call`, default `eval_<id>` e.g. `eval_k1`): its logger `received_at` | a hand time even when a call is linked (`inputs-no-ledger`): refused by default, flagged under the switch, never verified; cross-checked within 60 s |
| `model.endpoint` (maker, evaluator), `checks[].endpoint` | a call made straight to a provider: the request URL host in the harness log. A call through OpenRouter (`openrouter.ai`): the upstream host **the Orchestrator declared for that seat** with `custody_ledger.py pin` before the seat's first call, and only when every call's log shows that provider served it (see "Provider pin and routing request") | refused if it differs. Never a default, never looked up from a table, never the model vendor's host by assumption |
| the aggregator, upstream and routing | recorded under `x-plumbline` on the maker and each evaluator: `harness_log`, `calls`, `aggregator` (`openrouter.ai`), `upstream_provider` (as the log names it), `provider_slug`, `endpoint_basis`, and `routing = {pin, requests: [{provider: <what the request body asked>, calls}], request_ok}` | — |
| `bar.frozenAt`, `approvals[].at`, `disposition.at` | no harness log exists: **logged live** with `kit/custody_ledger.py` (below). Each approval records `x-plumbline.time_source` | a typed value with no ledger line behind it (`inputs-no-ledger`), a ledger line with `writer: "hand"` (`ledger-hand`) or no `writer` (`ledger-no-writer`) is a hand time: refused by default, flagged under the switch, never verified |
| emitter revision | `git rev-parse HEAD` and `HEAD^{tree}` of the checkout the emitter runs from: `x-plumbline.emitter = {commit, tree, dirty: false, statedRevision, kit_revision}` | refused when dirty, or not the stated revision |

A harness-log call whose log carries no logger `sent_at`/`received_at` — only the response `Date` header or
`created` — is a hand time too, with source `server-header` or `response-created`. The emitter reads the server
time to show the value; it never writes it back into the log.

**Tolerance: 60 seconds** (`TOLERANCE_S` in `kit/custody_history.py`). It absorbs a time typed to the minute
(truncation loses up to 59 s) and ordinary clock skew between the harness host and the provider. It does not absorb
a time typed from memory minutes later, which is what it exists to catch. A hand-entered time may never be later
than the emission at all; a log-derived time may be up to 60 s later (server clock skew).

**Harness log format.** One JSON object per model call, a JSON list of them, or JSON Lines. Each call:
`{"call": "<name>", "request": {"url", "model", "messages", "provider": {…}, …}, "response": {"id", "created",
"model", "provider"?, "openrouter_metadata"?, …}, "response_headers": {"Date": "<RFC 7231>", …},
"generation"?: <the GET /api/v1/generation?id=<response id> reply>}`. The request may instead be logged as
`"request": {"url", "body": {…}}`. For OpenRouter calls the request **body** must be logged whole, because the
routing request is read from it. `call` names are needed only in a log holding several calls.
Each call's `model` must equal the recorded `identifier`, or end with `/<identifier>` (e.g. `deepseek/deepseek-chat`
for `deepseek-chat`).

## Hand times: refused by default, flagged under the switch

A **hand time** is a time whose only source is a ledger line with `writer: "hand"` (`ledger-hand`), a ledger line
with no `writer` (`ledger-no-writer`), a value typed into `inputs/custody.json` with no ledger line behind it
(`inputs-no-ledger`), or a server time (a log time taken from the response `Date` header, `server-header`, or from
`created`, `response-created`) that no logger `sent_at`/`received_at` recorded.

**Hand times are refused by default.** With no switch, the emitter exits 3 with kind `hand-time`, prints one line
per hand time — `  [hand-time] <field> <file>:<line> (<source>)` — names every hand-time field and its file:line,
and writes nothing.

**The switch flags hand times and never verifies them.** `--allow-hand-times` does not check the time against a
log or a clock. It records each hand time in `x-plumbline.hand_times[]` and, when the set is non-empty, writes
`x-plumbline.allowances.hand_times = {switch: "--allow-hand-times", writer: "kit/emit_custody.py@<sha12>", at}`.
The listing is not disclosure-only: the verifier fails a record whose flags lack the allowance or disagree with
the ledger and logs (`allowance`, `hand-time-unflagged`, `flag-without-source`), and close refuses on that failure
(V8). The switch silences nothing else — a repo overlay whose log contradicts the hand time still exits 3 with the
switch on.

**Reported times are accepted only through the bounding commands.** A time a person reported (the Owner's
decision, a relay's source time, an amendment's time) is not a hand time when it is entered through a ledger
command that bounds it and names its source: `dispose --decided-at T --decided-source S` (bounded between the last
logged check and the tool's clock), `relay --source-at T` and `amendment --said-at T` (bounded between the freeze
and the tool's clock). The tool stamps the line and stores the reported time beside it.

**A relay is a report, not an approval.** The emitter never counts a relay as an approval; a buyer approval that
exists only as a relay is refused as a missing approval (`approval`), and the verifier reports `relay-as-approval`
if a relay is listed among approvals.

The field names used in the refusal lines, in `x-plumbline.hand_times[].field`, and by the verifier:
`bar.frozenAt`, `bar.approvals[<i>].at`, `routing.<seat>.declaredAt`, `disposition.at`, `startedAt`,
`producedAt`, `passes.<id>.at`, `controls[<id>].at`, `<log file name>#<call or index>.sent_at` and `.received_at`.
When a later ledger line sets the same field as an earlier one, the later line's value, line and source are the
ones used and reported.

## Refusals (exit 3)

Each refusal line starts with its kind. One example of each, from the synthetic fixtures in
`tests/fixtures/custody/failures/`:

| Kind | Refused when | Example line |
|---|---|---|
| `hand-time` | a time's only source is a hand line, a ledger line with no `writer`, a typed value with no ledger line behind it, or a server time no logger recorded | `  [hand-time] disposition.at inputs/custody.json:42 (inputs-no-ledger)` |
| `time` | under `--allow-hand-times`, a hand time is more than 60 s off its harness call (the switch silences nothing else); a model maker/evaluator has no harness log; a pass or control is linked to no call; a log call has no time at all; a ledger value differs from the live event log | `[time] startedAt: hand-entered 2026-10-20T11:13:00Z but harness log harness-maker-fixture.log#0 puts it at 2026-10-20T11:00:00Z (+780 s; tolerance ±60 s)` |
| `order` | a seat's provider pin declared after that seat's first call; not frozenAt < startedAt ≤ producedAt ≤ every check; an approval before frozenAt or after startedAt (the maker's first call); the last check after disposition.at; any event other than the disposition after the packet's `close.date`; the bar changed after its logged freeze | `[order] bar.approvals[1].at (specialist) 2026-10-20T11:12:00Z is after startedAt (the maker's first call) 2026-10-20T11:00:00Z` |
| `after-emit` | any event dated after the emission | `[after-emit] disposition.at 2099-01-01T00:05:00Z is after this record's emission at …: a record cannot report an event that had not happened` |
| `endpoint` | an aggregator call with no provider pin for its seat; a pin not logged live, or differing from the live log; a call the log does not say who served; a call served by, or also tried at, a provider other than the pin (a fallback); a direct call from a pinned seat; a hand-entered endpoint that differs | see "Provider pin and routing request" for the exact lines |
| `model` | a call ran a model other than the recorded identifier | `[model] evaluator eval-a: harness-eval-a.log#eval_artifact ran model 'example-1', not the recorded identifier 'other-1'` |
| `approval` | see "Who may approve" | `[approval] bar.approvals[1] (specialist) is by 'Fixture Orchestrator (Chief of Staff)', the orchestrating agent. …` |
| `revision` | the emitter's checkout is dirty, is not a git checkout, or is not the stated revision | `[revision] stated revision deadbeef0 matches neither the emitter's commit 4d6c360c2186 nor its tree ad75d121b1f5` |
| `harness-log` | a named harness log is unreadable or not JSON | `[harness-log] maker: harness-maker-fixture.log is not a JSON harness log (request/response/response_headers per call), so no time or endpoint can be read from it` |

## Who may approve

custody approvals are records of who approved, not signatures. The emitter keeps them that way and refuses an
approval that misstates who approved:

- The ledger must name the orchestrating agent: `"orchestrator": {"name": "VizH (Chief of Staff)", "kind": "agent", "aliases": ["VizH"]}`. Without it, every approval is refused.
- An approval by the orchestrator (name or alias, case-insensitive) is refused, **always**, even marked as an agent.
- An approval by a model (`kind: "model"`, or `by` naming the maker or an evaluator, by name, id or identifier) is refused.
- `kind` is `person` (default), `agent` or `model`. An `agent` approval counts only with `adopted: {document, version}` set (the agent adopted a published document). A `person` approval whose `by` reads like an agent (agent, bot, assistant, orchestrator, chief of staff, gpt, claude, grok, …) is refused: mark it, or have the person approve.
- If the packet names a `buyer` or `specialist`, the approval for that role must be by the same party.
- **A relay is a report, not an approval.** An approval that exists only as a relay is refused as a missing approval; the emitter never promotes a relay to an approver.

## The emitter's revision

The record names the commit and tree of the checkout the emitter ran from. The emitter refuses (exit 3) when:

- it is not running from a git checkout;
- the checkout has a tracked change, or an untracked file that is not ignored, **outside `dot-plumbline/` and the
  job folder being emitted** (both are job state, not code);
- a stated revision is given (`--expect-revision`, `$PLUMBLINE_EXPECT_REVISION`, or ledger `emitter_revision`) and
  it is a prefix (≥ 7 hex) of neither the commit nor the tree. **Use the tree**: `git am` re-creates the commit with
  a new SHA, but the tree is the same bytes.

## Prerequisites

| Need | Detail |
|---|---|
| Python 3.10+ | The emitter, drift check and packer use only the standard library. The test suite needs `jsonschema`, which the venv has. |
| E-DI corpus at the pin, **for `close` only** | The corpus is a private repository (its public reading copy is `github.com/evaluatordriven/doctrine`, which has no machine files). With access, clone it and check out `a48a4645aaa29947fdc17168d26c69c849941580`, then pass `--corpus <that checkout>` (or set `$EDI_CORPUS`). **A checkout at the corpus tip is NOT at the pin.** At tip (`f9c6f752…`) its `schemas/evaluator-record.schema.json` rejects the `passes` key that `kit/emit_record.py` writes, so a **scored** close against it stops at "the corpus rejected the emitted record" (observed 2026-10-27). A readings close against it did complete. |
| public doctrine: `github.com/evaluatordriven/doctrine` (DOCTRINE.md v0.1 @ `dc61854`) | For reading alongside the private corpus. The tools and schemas still pin the private corpus; nothing here reads the public doctrine. |
| custody checkout (optional) | `git clone https://github.com/evaluatordriven/custody && git -C custody checkout 3e3ca58de5631bdc58291564303a2e9d25a8653e`. You need it for `checker/check.py` (the standard layer), `kit/plumbline_verify.py` (the Plumbline layer) and the upstream half of the drift check. |
| Hermes | **Not needed.** Nothing here reads `~/.hermes`. Every command runs with an empty `HOME`. |
| Keys | **Only your model keys**, for the maker and the evaluator. Use whatever your harness reads, e.g. the provider API-key environment variable. Plumbline, the emitter and the packer read no key. |

## Models

custody CL1 needs at least one model evaluator per batch that is not the maker's model:

- `sameModelAsMaker` is computed from the identifiers, and true is a separation gap.
- A different **family** keeps `separationGaps` empty. The emitter adds an entry automatically when the families match.

A small, cheap setup is enough:

| Seat | Example | Notes |
|---|---|---|
| Maker | any model, `kind: "model"`, e.g. family `deepseek` | Writes the artifact. Record `{family, identifier, readOnly: false}`; the endpoint comes from its harness log. Save the log as `custody/evidence/harness-maker*.log`. |
| Evaluator | a different family, e.g. `glm`, read-only | One call per pass and per control, each named in the log (`eval_artifact`, `eval_k1`, `eval_k2`). Save its raw reply as the evidence file, and save the harness log (CL1-15). |

Use `family` lowercase with hyphens and no version (`^[a-z]+(-[a-z]+)*$`). **Endpoint**: call the provider
directly (the request URL host is then the endpoint), or through OpenRouter with the seat **pinned** to one
upstream provider, declared before the seat starts (next section).

## Provider pin and routing request (OpenRouter)

custody SPEC section 4: the endpoint is the service that answered, and a router is not it. Through OpenRouter, the
emitter therefore needs (1) which provider the Orchestrator chose, declared before any call, (2) proof in each
call's log that this provider, and no other, served it, and (3) the request having asked OpenRouter for exactly
that. The emitter guesses none of these.

**1. Declare the pin** for each seat before the seat's first call (the Maker's pin before the Maker starts;
declare every seat's pin then, so no seat is chosen after seeing output):

```sh
python3 kit/custody_ledger.py pin --job-dir J --seat maker  --provider "<name as OpenRouter's responses give it>" \
    --slug <provider slug for provider.order> --host <that provider's own API host>
python3 kit/custody_ledger.py pin --job-dir J --seat eval-a --provider "…" --slug … --host …
```

It writes `routing.<seat> = {via: "openrouter.ai", provider, slug, host, declaredAt}` into `inputs/custody.json`
and a `pin` event into `inputs/custody-events.jsonl`. It refuses (exit 3) once the seat's harness log records a
call, and refuses (exit 2) the aggregator's own host as `--host`. `--host` is the host the record will name as
the endpoint. It is the Orchestrator's declaration, recorded as such in `endpoint_basis`. The emitter does not
look it up.

**2. Who served each call** is read from the log, in this order. All are OpenRouter-documented fields:

| Source in the call's log | OpenRouter documentation |
|---|---|
| `response.provider` | the provider name on a sync response. `openapi.json` refers to "the `provider` field of sync responses" (BatchObject.provider). It is **not** listed in the ChatResult schema at https://openrouter.ai/docs/api/reference/overview |
| `response.openrouter_metadata.endpoints.available[selected].provider`, `…attempts[].provider` | opt-in: send header `X-OpenRouter-Metadata: enabled` (https://openrouter.ai/openapi.json, `/chat/completions` parameters; schemas OpenRouterMetadata, RouterAttempt) |
| `generation.data.provider_name`, `generation.data.provider_responses[]` | `GET https://openrouter.ai/api/v1/generation?id=<response id>` (https://openrouter.ai/docs/api/api-reference/generations/get-generation). The harness logs this reply under `generation` |

Response headers are not read. OpenRouter documents no provider header. A name matches the pin when it equals,
ignoring case and punctuation, the pinned `provider` or the first part of the pinned `slug` (`deepinfra/fp8` →
`deepinfra`). **Log `generation` or enable `openrouter_metadata`**. These are the only sources that show the
providers *tried*, so they are the only way to see a fallback that failed over.

**3. The routing request** is read from each call's request body, `provider` object
(https://openrouter.ai/docs/features/provider-routing):

| Field | Required value | Why |
|---|---|---|
| `provider.order` | exactly one slug, equal to the pinned `slug` | "OpenRouter will try them one at a time and proceed to other providers if none are operational" |
| `provider.allow_fallbacks` | `false` | default `true`; the doc: "If you don't want to allow any other providers, you should disable fallbacks as well" |
| `provider.zdr` | `true` (preferred), **or** `provider.data_collection: "deny"` | `zdr: true` restricts routing to Zero Data Retention endpoints. `data_collection: "deny"` only excludes providers that store or train on data, which is weaker. The doc says the request's `zdr` is ORed with the account setting, so it can only turn ZDR on |
| `models` | absent or a single model | a list of several is a model fallback |

**Refuse or gap: a request that did not ask for this is a HARD GAP (exit 1), not a refusal.** The record is
written, with `x-plumbline.gaps[]` field `routing.<seat>.request` naming what was missing, and
`x-plumbline.routing.request_ok: false` next to exactly what was asked. Why a gap:

- A refusal (exit 3) in this emitter means the record *would misstate* a fact. Here every fact it writes is still
  true. The endpoint is backed by the log's served-by check, and the request is recorded verbatim.
- What is wrong is the run, not the record, and re-emitting cannot fix it. A refusal would withhold the only
  document that shows a stranger the prompt was not held to one zero-retention provider. A hard gap keeps the
  record honest and visible, and it still exits non-zero. A missing request body is the same hard gap ("cannot
  be read").
- What *would* misstate is still refused: a fallback that happened, a served-by the log does not show, or a
  late pin.

The exact lines (fixtures `tests/fixtures/custody/failures/pin-*`, `routing-unpinned`):

```
# no pin declared for a seat that went through OpenRouter (exit 3)
[endpoint] maker: harness-maker-fixture.log#0 went to the aggregator openrouter.ai and no provider pin was declared for this seat (custody_ledger.py pin, before its first call); the emitter will not guess which host answered (custody SPEC 4: a router is not the service that answered)
# fallback: another provider served (pin-fallback, exit 3)
[endpoint] maker: harness-maker-fixture.log#0 was served by 'Together' (response provider), 'Together' (generation provider_name), not the pinned provider 'DeepInfra' (deepinfra/fp8): a fallback to another provider; the record would name api.deepinfra.com for a call it did not answer
# provider missing from the log (pin-provider-missing, exit 3)
[endpoint] maker: harness-maker-fixture.log#0 went to openrouter.ai and the log does not say which provider served it (no response `provider`, no `openrouter_metadata`, no logged /api/v1/generation stats); the pin to 'DeepInfra' cannot be confirmed and the emitter will not guess
# pin after the first call (pin-late, exit 3)
[order] maker: provider pin declared at '2026-10-20T11:05:00Z', after the seat's first call harness-maker-fixture.log#0 (2026-10-20T11:00:00Z); a pin chosen after the calls is not a pin
# routing request without one provider / no-fallback / ZDR (routing-unpinned, exit 1, record written)
GAP  routing.maker.request: harness-maker-fixture.log#0 did not ask OpenRouter for the pin: provider.order is ['deepinfra/fp8', 'together'], not exactly one provider; provider.allow_fallbacks is absent, not false (OpenRouter's default is true: other providers may serve); neither provider.zdr true nor provider.data_collection "deny" (zdr absent, data_collection absent). The served provider is still read from the log, but nothing in the request kept the prompt on one zero-retention provider. Re-emitting cannot fix this; the run's own request did it.
# request body not logged (exit 1): the same gap, reason "the log does not carry the request body, so the routing request cannot be read"
```

**Model slugs** (OpenRouter `GET https://openrouter.ai/api/v1/models`, read 2026-10-27):

| Seat | Model | Slug | Note |
|---|---|---|---|
| Maker | DeepSeek V4.1 Flash 1017 | `deepseek/deepseek-v4.1-flash-1017` | canonical `deepseek/deepseek-v4.1-flash-20261017`. Not `deepseek/deepseek-v4.1-flash` (the 0910 release) |
| Evaluator | GLM 5.3 Flash | `z-ai/glm-5.3-flash` | canonical `z-ai/glm-5.3-flash-20260826`. Not `z-ai/glm-5.3-flashx` |

Record `identifier` as the slug. The response `model` must equal it or end with `/<identifier>`. Before choosing
a provider, list the ZDR endpoints per model with `GET https://openrouter.ai/api/v1/endpoints/zdr` (`provider_name`
and `tag`). The `tag` is the slug for `provider.order`. The provider's own API host is the Orchestrator's to
state. The direct DeepSeek endpoint was **not** in that ZDR list for the Maker model on 2026-10-27.

## The custody inputs: `inputs/custody.json`

Write this file **as events happen** (freeze, approvals, passes, controls), not afterwards. It lives under
`inputs/`, so the close walk skips it. Every path is relative to the job folder unless noted. The emitter computes
every digest from the files themselves, except approval digests, which you copy from what each approver approved.

A complete synthetic example is at `tests/fixtures/custody/job-rejected/inputs/custody.json`. Its shape:

```jsonc
{
  "custody_inputs": "plumbline/custody-inputs/v1",
  "levelClaimed": "CL1",                       // CL2 later: add "spread", run >= 2, a second family
  "files_dir": "custody/files",                // default; the subject = every file here (or list "subject")
  "evidence_dir": "custody/evidence",          // default; evaluator replies + harness logs (names relative to it)
  "bar": {
    "file": "custody/bar.md",                  // the frozen bar text; bar.digest = sha256(this file)
    "frozenAt": "…Z",                          // must be before startedAt; log it live (custody_ledger.py freeze) or it is a hand time
    "author": "…", "publishedAt": null, "dissent": [], "groundTruth": [],
    "dimensions": [{"id": "D1", "plumbline_dimension": "<§5 dimension name>", "criterion": "…",
                    "scale": {"anchors": {"1": "…", "10": "…"}, "threshold": 9, "floor": 1},
                    "failureCondition": "…"}],
    "approvals": [{"role": "buyer", "by": "Steve Moitozo II", "kind": "person", "barDigest": "<hex the Buyer approved>", "at": "…Z", "adopted": null},
                  {"role": "specialist", "by": "<a person, not the orchestrator>", "kind": "person", "barDigest": "<hex>", "at": "…Z", "adopted": null}]   // log each with custody_ledger.py approve; a typed at is a hand time
  },
  "orchestrator": {"name": "…", "kind": "agent", "aliases": []},   // required: approvals are checked against it
  "routing": {"maker": {"via": "openrouter.ai", "provider": "…", "slug": "…", "host": "…", "declaredAt": "…Z"}},
                                               // written by custody_ledger.py pin, one per seat; must match the event log
  "maker": {"name": "…", "kind": "model", "version": "…", "method_file": "custody/method.md",
            "harness_log": "harness-maker-….log",  // default: the one harness-maker*.log in evidence_dir
            "model": {"family": "…", "identifier": "…", "readOnly": false}},   // endpoint: from the log
  "startedAt": "…Z", "producedAt": "…Z",       // leave unset: a typed value is a hand time (refused unless --allow-hand-times); the log supplies it
  "instrument": {"rubric_file": "…", "runner_file": "…"},   // optional when the §5 record pins both hashes
  "evaluators": [{"id": "eval-a", "name": "…", "kind": "model",
                  "harness_log": "harness-eval-….log",   // default: its CL1-15 external entry's evidence_file
                  "model": {"family": "…", "identifier": "…", "readOnly": true}}],
  "passes": {"<pass_id from run.json>": {"evaluator": "eval-a", "run": 1, "batch": "b1",
             "call": "eval_artifact",          // the harness call this pass is; time and endpoint come from it
             "evidence": {"D1": "<file in evidence_dir>"}}},
  "checks": [],                                // readings jobs (no §5 record): custody checks directly,
                                               // with "evidence_file" in place of "evidence"
  "controls": [{"id": "K1", "batch": "b1", "evaluator": "eval-a", "call": "eval_k1", "case_file": "…", "expected": "conforms", "outcome": "…",
                "evidence_file": "…"},
               {"id": "K2", "batch": "b1", "evaluator": "eval-a", "case_file": "…", "expected": "does_not_conform", "outcome": "…"}],
  "violations": {"V1": {"dimension": "D2",     // §5 violations name no dimension: say which bar dimension
                        "remedy": {"text": "<verbatim from the evidence>", "evidence_file": "…"}}},  // optional
  "external": [{"requirement": "CL1-15", "subject": "eval-a", "evidence_file": "<harness log>", "readBy": "…"}],
  "retention": {"location": "…", "public": false},
  "disposition": {"by": "Steve Moitozo II", "at": "…Z", "acknowledgesUnobserved": []},   // log it live (custody_ledger.py dispose); a typed at is a hand time
  "verdict": "accept"                          // readings jobs only; scored jobs take it from the §5 record
}
```

The emitter also accepts an optional top-level `"x-plumbline"` object here. It is copied **deep-equal** into the
record's `predicate["x-plumbline"].inputs`; it never shadows the emitter's own keys (`verdict`, `gaps`, `times`,
`hand_times`, `allowances`, `generations`, `evaluations`, `relays`, `amendments`, `spend`, `schema`), which the
verifier re-derives from the record, ledger and logs.

Rules the emitter enforces:

- A scored check's outcome is `score >= threshold` (CL1-17).
- A pass that is void, or a dimension with no score, becomes `unobserved` with its channel and reason.
- A remedy is kept only if it appears verbatim in the named evidence file.
- If no disposition time is recorded, `at` is the emission time, and the record says so (`x-plumbline.disposition_at_source`).
- Every time, endpoint, approver and revision rule in "Refusals" above, including hand times.

## Logging events live: `kit/custody_ledger.py`

Freeze, approval, provider pins, disposition and the batch's own events (generations, evaluations, amendments,
relays, spend) have no harness log. Stamp each **at the moment it happens**; the tool writes it into
`inputs/custody.json` and appends it to `inputs/custody-events.jsonl`, and the emitter then refuses a ledger value
that differs from the logged one, and a bar that changed after its logged freeze.

Every line any command appends carries `writer: "kit/custody_ledger.py@<sha12>"` (the sha256 of the file that ran)
and `at` (the tool's clock), so a reader can tell a tool stamp from a hand-typed one. Every command appends
**exactly one** line when it succeeds; the earlier lines are never rewritten; a refused call appends nothing and
exits non-zero (2 = usage, 3 = refused), printing a line starting `REFUSED:` on stderr and leaving the ledger and
`custody.json` byte-identical.

Base commands:

```sh
python3 kit/custody_ledger.py freeze  --job-dir J --orchestrator "VizH (Chief of Staff)" --orchestrator-alias VizH
python3 kit/custody_ledger.py approve --job-dir J --role buyer      --by "Steve Moitozo II"
python3 kit/custody_ledger.py approve --job-dir J --role specialist --by "<the Specialist, a person>"
python3 kit/custody_ledger.py pin     --job-dir J --seat maker  --provider … --slug … --host …   # before the Maker starts
python3 kit/custody_ledger.py pin     --job-dir J --seat eval-a --provider … --slug … --host …
python3 kit/custody_ledger.py dispose --job-dir J --by "Steve Moitozo II" [--state given|declined] \
    [--decided-at T --decided-source S] [--words W]
python3 kit/custody_ledger.py show    --job-dir J
```

`approve` records the bar file's sha256 at that moment as the digest approved, and refuses the orchestrator, a
model, or an unmarked agent. Both approvals must be stamped **before the maker's first call**.

New commands (each appends one line, which the emitter reads into `x-plumbline`):

| command | appends | bounds |
|---|---|---|
| `generation open --seat S --prompt FILE` | `event:"generation", action:"open", seat, n, prompt_file, prompt_sha256` | `n` starts at 1 and goes up by 1; a second open while one is open is refused; the prompt's sha256 is computed by the tool |
| `generation close --seat S --n N [--outcome TEXT] [--fix-kind TEXT]` | `event:"generation", action:"close", seat, n, outcome, fix_kind` | a close without a matching open (same n, same seat) is refused |
| `evaluation --batch B --evaluator ID --verdict FILE [--summary FILE] [--iteration N]` | `event:"evaluation", batch, evaluator, verdict_file, verdict_sha256`; with `--summary`, also `summary_file, summary_sha256, started_at, finished_at, summary_writer` | the tool computes the verdict's sha256 and refuses a missing file; with `--summary` it takes `started_at`/`finished_at`/`writer` from the instrument's own stamp and refuses a summary with no stamp |
| `amendment --file F --quote Q --channel C --said-at T` | `event:"amendment", file, file_sha256, quote, channel, said_at` | the tool computes the file's sha256; refuses F inside `custody/`; T before the freeze or after the tool's clock is refused; the quote is stored verbatim |
| `relay --quote Q --from BOT --source-chat C --source-at T` | `event:"relay", kind:"relay", quote, from, source_chat, source_at` | the quote is stored verbatim and marked relay; T is bounded as in `amendment`; the emitter never counts a relay as an approval |
| `spend --spend-ledger L --key-reading R` | `event:"spend", spend_ledger, spend_ledger_sha256, key_reading, key_reading_sha256, ledger_sum_usd, key_delta_usd, total_usd, read_at, last_settle_at` | refuses a reading R with no `read_at`/`writer` stamp, or one read less than 3 min after the last `settle` line; both files' sha256 go in the line |
| `dispose --by NAME --state given\|declined --decided-at T --decided-source S [--words W]` | `event:"dispose", by, state, decided_at, decided_source, words`; `custody.json` `disposition.at = decided_at` | T earlier than the last logged check or later than the tool's clock is refused; T equal to the last check is accepted |

The emitter reads each line into `x-plumbline`: `generations[]`, `evaluations[]`, `relays[]`, `amendments[]` and
`spend`, each with a `source` of `inputs/custody-events.jsonl:<line>`.

## The product harness: `tools/edi/`

The kit's own product harness lives under `tools/edi/`. It is standard library only, and every instrument that
writes a summary stamps `started_at`, `finished_at` (UTC Z, its own clock) and `writer: "tools/edi/<file>@<sha12>"`.

- `tools/edi/or_call.py` — one logged OpenRouter chat call for a seat, in job 1's harness-log shape so
  `kit/custody_history.read_log` can read it. A job spend file (`--job-spend`) gives the job id, bound, reserve,
  spend ledger and price snapshot, with no job hard-coded; the call is refused when
  `total + worst case + reserve >= bound`. `--max-cost X` refuses before sending when the worst case is greater
  than X, and exits 9 after settle when `total_cost` is greater than X. `--init-spend` writes the key-usage
  baseline, and `--spend-status --out R` writes the stamped key/ledger reading that `custody_ledger.py spend`
  records. `--mock-transport DIR` keeps everything off the network for tests. Exit codes: 0 served, 2
  usage/key/job-spend error, 3 HTTP/transport, 4 pin refusal, 5 no generation reply, 6 bound refusal, 8
  `--max-cost` refusal before sending, 9 over the cap after settle.
- `tools/edi/judge_batch.py` — a model-judge batch: one `or_call.py` per item, the order for batch N rotated left
  by `(N-1) mod len`, with `summary.json` carrying the batch and the `order`.
- `tools/edi/fixture_run.py` — copies a fixture tree into a working directory, makes every copied file and
  directory owner-writable whatever the source modes, and writes a summary of paths, sha256 and mode.
- `tools/edi/extract_files.py` — the whole-file reply extractor, with `--check` (verify only) and without it
  (write).

## Running the three jobs

For each job:

1. **Open** the job: `python3 kit/plumbline_job.py open --brief brief.json --job-dir dot-plumbline/jobs/<id> --corpus <e-di@a48a4645>`.
2. **Freeze** the bar: write `custody/bar.md`, then `custody_ledger.py freeze` at that moment. The Buyer and the Specialist (each a person; never the orchestrator) each approve it, stamped with `custody_ledger.py approve` as they do, before any maker call.
3. **Pin** (OpenRouter): the Orchestrator chooses one ZDR provider per model from `GET https://openrouter.ai/api/v1/endpoints/zdr` and declares each seat's pin with `custody_ledger.py pin` **before the Maker starts**. Use the exact model slugs (see "Provider pin and routing request"). Every request body carries `"provider": {"order": ["<pinned slug>"], "allow_fallbacks": false, "zdr": true}`. Log every call in full: the whole request body, the whole response, the `Date` header, and the `/api/v1/generation` reply under `generation`.
4. **Make**: run the maker model and put the artifact in `custody/files/`. Its run file names the artifact the §5 record hashes. Save the maker's harness log (with its `Date` header and response) as `custody/evidence/harness-maker-<model>.log`. Record the maker block; do not type `startedAt`/`producedAt` (the log decides).
5. **Evaluate**: per batch, run the evaluator on the artifact and on a clean and a planted control case.
   - Save each reply into `custody/evidence/`.
   - Save the harness log, one named call per pass and control (`eval_artifact`, `eval_k1`, `eval_k2`), into `custody/evidence/`.
   - Fill `passes` and `controls`, each with its `call`; do not type their times.
   - Write the iteration's `run.json` (kit/emit_record.py's shape) with the scores and verdict.
   - Log the batch's own events with the ledger: `custody_ledger.py generation open/close` around each Maker
     generation, `custody_ledger.py evaluation` for each verdict file (with `--summary` when an instrument wrote
     one), and `custody_ledger.py amendment`/`relay` for anything a person said. `custody_ledger.py spend` after
     the last settle.
6. **Close** at the terminal state. This also writes the custody record and runs the verifier:

   ```sh
   python3 kit/plumbline_job.py close --job-dir dot-plumbline/jobs/<id> --run run-1.json \
     --corpus <e-di@a48a4645> --terminal-state <accepted|needs_owner|rejected> --outcome <same> \
     [--disposition given|declined] [--allow-hand-times] [--custody <custody checkout>]
   ```

   | Terminal state | Close flags |
   |---|---|
   | `accepted` | verdict `accept`, every dimension at or above threshold, `--terminal-state accepted --outcome accepted`. |
   | `rejected` | verdict `reject`, at least one `does_not_conform` dimension with a violation and its locator, `--terminal-state rejected --outcome rejected`. |
   | `needs_owner` | verdict `needs_owner` (e.g. cap reached or a capability gap), `--terminal-state needs_owner --outcome needs_owner --escalation-kind cap_reached`. |

   Across the three records, at least one violation must exist (xlocator).

   `close` runs the emitter, then `kit/plumbline_verify.py` on the new record. If the verifier fails, close exits
   with the verifier's code (3 or 4), prints `NOT CLOSED: Plumbline verify failed (<kind>)`, writes a run-log row
   `close_refused` with the kind, and writes no `closed` row; re-running close after a fix retries. `--custody`
   defaults to `$PLUMBLINE_CUSTODY`. `--allow-hand-times` is passed to the emitter and affects only hand-time
   refusals.

   Emit from a **clean checkout** of the stated revision, with `PLUMBLINE_EXPECT_REVISION=<tree sha>` set.

7. **Re-emit** without a corpus, any time. `custody` runs the emitter, then the verifier, and returns its code:

   ```sh
   python3 kit/plumbline_job.py custody --job-dir dot-plumbline/jobs/<id> [--out-dir DIR] \
     [--expect-revision <tree>] [--allow-hand-times] [--custody <checkout>]
   ```

   Then check the record at both layers, if the custody checkout is present:

   ```sh
   python3 kit/plumbline_verify.py --record dot-plumbline/jobs/<id>/custody/record.custody.json \
     --files dot-plumbline/jobs/<id>/custody/files --evidence dot-plumbline/jobs/<id>/custody/evidence \
     --ledger dot-plumbline/jobs/<id>/inputs/custody-events.jsonl --custody <custody checkout>
   ```

   The standard layer alone (check.py) is:

   ```sh
   python3 custody/checker/check.py dot-plumbline/jobs/<id>/custody/record.custody.json \
     --files dot-plumbline/jobs/<id>/custody/files --evidence dot-plumbline/jobs/<id>/custody/evidence \
     --bar dot-plumbline/jobs/<id>/custody/bar.md
   ```

## Where outputs land

| Output | Path |
|---|---|
| Record | `dot-plumbline/jobs/<id>/custody/record.custody.json`, or `<out-dir>/<job_id>.custody.json` with `--out-dir`. |
| Bar, subject, evidence and controls | `dot-plumbline/jobs/<id>/custody/{bar.md, files/, evidence/, controls/}`. These are the paths for `records[]`: `files` = `…/custody/files`, `evidence` = `…/custody/evidence`, `bar` = `…/custody/bar.md`. |
| Run-log row | Unchanged (`event: closed`); `close_refused` with the kind when the verifier refuses. |

## Packing a stranger bundle

```sh
python3 tools/pack_stranger_bundle.py --job-dir dot-plumbline/jobs/<id> --out <dir>/<id>.zip
```

The zip contains:

| Entry | Contents |
|---|---|
| `record.custody.json` | The record. |
| `bar/<bar file>` | The frozen bar. |
| `files/` | The subject files. |
| `evidence/` | Every evidence file and harness log. |
| `context/` | The method, instrument and control files, the §5 record and the packet. |
| `MANIFEST.sha256` | sha256 manifest, `sha256sum -c` compatible. |
| `README.txt` | The one check command. |

Packing is deterministic. The command prints the zip's sha256 and the in-zip paths:
`record.custody.json`, `files`, `evidence`, `bar/<name>`.

## Drift check

```sh
CUSTODY_DIR=<custody checkout at the pin> python3 tools/build_schemas.py --custody --check --require-upstream
```

- Exits 1 if the checkout moved (commit, or the sha256 of schema/check.py/SPEC.md), if the vendored `schemas/custody/custody-v1.schema.json` is not the pinned bytes, or if `schemas/custody-record.schema.json` is not exactly what the derivation gives (a hand edit).
- Exits 2 with no checkout under `--require-upstream`.
- Re-derive after a deliberate move with `--custody --repin`.
- `tests/validate_schemas.py` part 3 exercises all of this with no corpus, and every refusal above (synthetic
  failure fixtures in `tests/fixtures/custody/failures/`; the emitter runs from a throwaway clean commit of the tree).
