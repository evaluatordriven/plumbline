# INTERFACE: the command lines, file shapes and exit codes the S1 instrument drives (job 2026-10-28-custody-times-ledger-spend)

STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — part of the freeze set; sha256 in ../MANIFEST.sha256. Maker-visible. Referenced from bar.md.

The bar says WHAT must hold. This file pins HOW S1 calls the subject, so that a check scores the behaviour and not a
guess about flag names. Anything not named here is the Maker's choice. Where the bar and this file disagree, the
bar wins and the disagreement is a finding against the bar (filed as an amendment), not a reason to fail a check.
"UTC Z" = `YYYY-MM-DDTHH:MM:SSZ` (fractional seconds allowed). "sha12" = first 12 hex of the sha256 of the file.

## 1. `kit/custody_ledger.py` (T1, F1a–F1h)
Every command takes `--job-dir J` (the job folder holding `inputs/custody-events.jsonl` and `inputs/custody.json`).
Base commands keep their base flags (`freeze`, `approve`, `pin`, `show`, and `dispose --by`).

Every line any command appends carries `"writer": "kit/custody_ledger.py@<sha12>"` (sha12 of the file that ran)
and `"at"`: the tool's UTC Z clock at the append. A **refusal** exits non-zero (2 = usage, 3 = refused), prints a
line starting `REFUSED:` on stderr, and changes neither the ledger nor `custody.json` (byte-identical).

| command | appends one line with (besides `writer`, `at`) | custody.json |
|---|---|---|
| `generation open --seat S --prompt FILE` | `event:"generation", action:"open", seat, n, prompt_file, prompt_sha256` | unchanged |
| `generation close --seat S --n N [--outcome TEXT] [--fix-kind TEXT]` | `event:"generation", action:"close", seat, n, outcome, fix_kind` | unchanged |
| `evaluation --batch B --evaluator ID --verdict FILE [--summary FILE] [--iteration N]` | `event:"evaluation", batch, evaluator, verdict_file, verdict_sha256`; with `--summary`: `summary_file, summary_sha256, started_at, finished_at, summary_writer` (copied from the summary's own stamp) | unchanged |
| `amendment --file F --quote Q --channel C --said-at T` | `event:"amendment", file, file_sha256, quote, channel, said_at` | unchanged |
| `relay --quote Q --from BOT --source-chat C --source-at T` | `event:"relay", kind:"relay", quote, from, source_chat, source_at` | unchanged |
| `spend --spend-ledger L --key-reading R` | `event:"spend", spend_ledger, spend_ledger_sha256, key_reading, key_reading_sha256, ledger_sum_usd, key_delta_usd, total_usd, read_at, last_settle_at` | unchanged |
| `dispose --by NAME --state given\|declined --decided-at T --decided-source S [--words W]` | `event:"dispose", by, state, decided_at, decided_source, words` | `disposition.by`, `disposition.at = decided_at` |

File paths in lines are stored relative to the job dir when they are inside it, else absolute. Bounds (F1b, F1e, F1f,
F1g) are as the bar states; T equal to a bound is accepted. `generation` numbering is per seat.

## 2. `kit/emit_custody.py` (T2–T7, F1h, X1)
Base flags unchanged, plus `--allow-hand-times`.
- **Hand-time refusal** (no switch): exit 3, nothing written, stderr carries the base `REFUSED (history)` header and
  one line per hand time: `  [hand-time] <field> <file>:<line> (<source>)`.
- **Field names** (used in the refusal lines, in `hand_times[].field`, and by the verifier):
  `bar.frozenAt`, `bar.approvals[<i>].at`, `routing.<seat>.declaredAt`, `disposition.at`, `startedAt`,
  `producedAt`, `passes.<id>.at`, `controls[<id>].at`, `<log file name>#<call or index>.sent_at` and `.received_at`.
- **Sources**: `ledger-hand` (`writer:"hand"`), `ledger-no-writer`, `inputs-no-ledger` (typed into custody.json, no
  ledger line behind it), `server-header` (a log time taken from the response `Date`), `response-created` (from the
  response `created`). `<file>:<line>` is the 1-based line that carries the value: the ledger line, the custody.json
  line (the file is indent-2 JSON, one key per line), or the harness-log line holding the server time used.
  `<i>` is the 0-based index in `bar.approvals`; `<file>` is relative to the job dir. When a later ledger line
  sets the same field as an earlier one, the later line's value, line and source are the ones used and reported.
- A pass or control with no typed `at` gets its time from a tool: a model pass from its `call`'s logger
  `received_at`; a script pass from the `finished_at` of the `evaluation` line for its batch and evaluator.
  `startedAt`/`producedAt` with no typed value come from the Maker log's logger times.
- **`x-plumbline`** (predicate level), keys: `schema` (`"plumbline/x-plumbline/v1"`), `hand_times[]`
  (`{field, file, line, source}`), `allowances` (`hand_times: {switch:"--allow-hand-times", writer:
  "kit/emit_custody.py@<sha12>", at}` only when the switch was given and the set is non-empty), `generations[]`,
  `evaluations[]`, `relays[]`, `amendments[]` (each the ledger line's fields plus `source:
  "inputs/custody-events.jsonl:<line>"`), `spend` (`calls_sum_usd, key_delta_usd, total_usd, tolerance_usd: 0.0001,
  source`), `inputs` (a deep copy of `inputs/custody.json`'s `x-plumbline` object, when there is one).
- The emitter never writes any file under the job dir other than the record it is asked to write (T7).

## 3. `kit/plumbline_verify.py` (V1–V9)
As in the bar: `--record R --files F --evidence E --ledger L --custody <checkout> [--json OUT]`; the job's
`custody.json` is the file `custody.json` beside L. Exits 0/3/4/2: 0 = all checks pass; 3 = the standard check.py
is not OK (kind `standard`, nothing else is checked); 4 = check.py is OK and any other kind fails; 2 = cannot run
(usage, a missing input, or a checker whose `check.py` sha256 is not the pin). Each failure is printed as one stdout line
`FAIL <kind> <field> <file>:<line>`; `--json OUT` writes `{"exit": N, "failures": [{"kind","field","file","line"}]}`.
Kinds: `standard`, `schema`, `allowance`, `hand-time-unflagged`, `flag-without-source`, `events`,
`relay-as-approval`, `spend`, `shadow`. The spend ledger and key reading are the files named in the ledger's
`spend` line (relative to the job dir when relative).

## 4. `kit/plumbline_job.py` (V8)
`close` and `custody` accept `--allow-hand-times` (passed to the emitter) and `--custody <checkout>` (default: env
`PLUMBLINE_CUSTODY`). Both run `kit/emit_custody.py` and then `kit/plumbline_verify.py` **as subprocesses of those
files** (as base runs the emitter). If the verifier cannot run, close fails with its exit code. The run-log row on
refusal is `{"event":"close_refused","kind":<first failure kind>, ...}`.

## 5. `tools/edi/` (F7a, F8a–F8d, I1, P1)
**`or_call.py`**: job 1's harness flags (`--seat --log --model --tag --pin-provider | --ledger, --messages --out
--call --max-tokens --temperature --key-file --base-url`), plus:
- `--job-spend FILE` (required for every call and for `--init-spend` / `--spend-status`): JSON
  `{job_id, bound_usd, reserve_usd, spend_ledger, prices: [{model, tag, prompt_usd_per_token,
  completion_usd_per_token, max_completion_tokens}]}`. Missing or invalid → exit 2, nothing sent.
- `--init-spend`: writes `key-usage-baseline.json` beside `spend_ledger` (`{job, usage, at, writer}`).
- `--spend-status --out R`: writes R = `{read_at, writer, job_id, key_usage_usd, baseline_usd, key_delta_usd,
  ledger_sum_usd, total_usd, last_settle_at}`.
- Spend-ledger lines are job 1's harness's: `{"event": "reserve", "id", "at", "job", "seat", ..., "worst_usd"}` before
  sending and `{"event": "settle", "id", "at", "call", ..., "cost_usd"}` after (plus `"over_cap": true` for exit 9).
- `--max-cost X`: refused before sending if the worst case > X; over-cap after settle if `total_cost` > X.
- `--mock-transport DIR`: nothing goes on the network. Replies come from `DIR/key.json`, `DIR/chat.json`,
  `DIR/generation.json`, each `{"status": N, "headers": {...}, "body": <JSON>}`; every request is appended to
  `DIR/requests.jsonl` as `{"method", "url", "at"}` (real openrouter.ai URLs; no headers, no key).
- Exits: job 1's 0/2/3/4/5, plus `6` refused by the job bound (nothing sent, no log entry), `8` refused by
  `--max-cost` before sending (nothing sent, no log entry), `9` over the cap after settle (logged, settle line
  `"over_cap": true`, no `--out`).
- Log entries carry every key job 1's harness writes (`harness.name` may say `tools/edi/or_call.py`).

**`fixture_run.py --src DIR --work DIR --summary FILE`**: copies src into work (every copied file `u+rw`, dirs
`u+rwx`, whatever src's modes), and writes the summary `{started_at, finished_at, writer, files: [{path, sha256,
mode}]}` (paths relative to work, mode as an octal string). Two runs differ only in `started_at`/`finished_at`.

**`judge_batch.py --items ITEMS.json --batch N --rubric FILE --out DIR --job-spend F --log L --model M (--tag T
--pin-provider P | --ledger LED) [--mock-transport D]`**: ITEMS.json is a list of `{id, text}`; the order for batch N
is the list rotated left by `(N-1) mod len`. One `or_call.py` call per item. Writes `DIR/summary.json` `{started_at,
finished_at, writer, batch, order: [ids], results: [{id, call, exit, reply_file}]}`.

**`extract_files.py`**: the whole-file reply extractor (job 1's format), with `--check` (verify only) and without it
(write).

Every summary-writing instrument stamps `started_at`, `finished_at` (UTC Z, its own clock) and
`writer: "tools/edi/<file>@<sha12>"` (I1).

## 6. Anchors S1's mutation controls rely on (keep these lines' form)
- `kit/custody_history.py` keeps a module-level line `TOLERANCE_S = 60` (C-T5p1 rewrites it to 600).
- `kit/emit_custody.py` keeps the "after the close" refusal in `check_order` as one line containing both
  `ref.add(` and the text `is after the job's close` (C-T5p2 disables that line).
- C-T7p, C-V7p and P-V8 wrap whole files (`kit/emit_custody.py`, `kit/plumbline_verify.py`) and need no anchor.
A missing anchor makes that control unbuildable, which voids the batch (bar: a control that comes out wrong).
