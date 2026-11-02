# tools/edi

Product-harness helpers for E-DI jobs.  They are ordinary command-line tools:
standard library only, no network except `or_call.py`, and every instrument that
writes a summary stamps `started_at`, `finished_at` (UTC Z, its own clock) and
`writer: "tools/edi/<file>@<sha12>"`.

## `or_call.py`

One logged OpenRouter chat call for a seat.  It keeps the job-1 harness log shape
(`call`, `seat`, `request`, `sent_at`, `response_status`, `response_headers`,
`response`, `received_at`, `generation`, `generation_status`,
`generation_fetched_at`, `harness`, `verdict`), so `kit/custody_history.read_log`
can read it.

Required job spend file for calls, `--init-spend` and `--spend-status`:

```json
{
  "job_id": "job-id",
  "bound_usd": 2.0,
  "reserve_usd": 0.05,
  "spend_ledger": "/path/to/spend-ledger.jsonl",
  "prices": [
    {"model": "model", "tag": "provider/fp8",
     "prompt_usd_per_token": 0.0000001,
     "completion_usd_per_token": 0.0000003,
     "max_completion_tokens": 131072}
  ]
}
```

The job total is `max(spend-ledger sum, key-usage delta)`.  It is read with a
free `GET /api/v1/key` before every call, and the call is refused when
`total + worst case + reserve >= bound`.  `max_tokens` is always the endpoint
maximum; a different `--max-tokens` is refused.  There is no throttling and no
reasoning-limit parameter.

Useful flags:

- `--init-spend`: write `key-usage-baseline.json` beside the spend ledger once.
- `--spend-status --out R`: write the stamped key/ledger reading.
- `--max-cost X`: refuse before sending when the worst case is greater than X;
  if the settled cost is greater than X, exit 9, mark the settle line
  `over_cap`, and write no reply.
- `--mock-transport DIR`: no network.  Replies come from `DIR/key.json`,
  `DIR/chat.json` and `DIR/generation.json`; requests are recorded in
  `DIR/requests.jsonl` with no headers or key material.

Exit codes: 0 logged and served by the pin; 2 usage/key/job-spend error;
3 HTTP or transport error; 4 provider-pin refusal; 5 no generation reply;
6 job-spend bound refusal; 8 `--max-cost` refusal before sending; 9 over the cap
after settle.

## `judge_batch.py`

Runs one `or_call.py` per item in a rotated order.  The order for batch N is the
item list rotated left by `(N-1) mod len`.  It writes `DIR/summary.json` with
`started_at`, `finished_at`, `writer`, `batch`, `order` (ids) and `results`
(`{id, call, exit, reply_file}`).

## `fixture_run.py`

Copies a fixture tree into a working directory and makes every copied file
owner-writable and every copied directory owner-writable and searchable, even
when the source is read-only.  It writes a summary with `started_at`,
`finished_at`, `writer` and `files` (`{path, sha256, mode}`).  Two runs from the
same contents differ only in the two timestamps.

## `extract_files.py`

The whole-file reply extractor.  `extract_files.py REPLY.txt TARGET_DIR` writes
the blocks; `--check` validates only; `--list OUT.txt` records the written paths.
It validates every block before writing anything and never normalizes file
bytes.
