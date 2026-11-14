# The seat bridge: `kit/seat_bridge.py`

`loop()` runs its Maker and its Evaluator as commands (`maker.cmd`, `evaluator.cmd`). A bot seat is not a
command. `kit/seat_bridge.py` stands in for both: it writes the seat's request as a file under the job's
`record_dir`, blocks until the seat's answer file arrives, and hands the answer back to `loop()` the way a
command would. It is the Orchestrator's delivery instrument, not a seat: it does not score, decide, send or
call anything. Python standard library only.

The interface is fixed by job 2026-11-13-kit-bridge (bar.md section 3); this page explains how to wire it.

## 1. Wiring a job

**The packet.** Both seats use the same file, from the repo `loop()` runs in:

```json
"maker":     {"cmd": ["python3", "kit/seat_bridge.py", "maker"], "handoff": "rule12"},
"evaluator": {"kind": "model", "cmd": ["python3", "kit/seat_bridge.py", "evaluator"], "runs": 2,
              "held_out": ["<held-out files>"]}
```

`--poll S` (a positive number of seconds; default 1.0) sets how often the bridge looks at the answer file.
`evaluator.runs` must be an int of at least 2: `loop()` refuses fewer, and two readings that differ stop the job.

**The rounds holder.** `loop()` needs exactly one `holders.orchestrator` entry that holds the rounds as a
script, and every entry needs `tested`:

```json
{"holder": "loop() (the kit's rounds function)", "kind": "script", "does": "rounds",
 "tested": "job 2026-11-13-kit-bridge acceptance record (tests/test_seat_bridge_acceptance.py L01-L05): <path>, sha256 <sha>"}
```

L01 holds two rounds to `accepted` through the bridge; L02-L05 are its planted stops (`evaluator split`,
`timeout`, `budget unmeasured`, `cap reached`). Cite the record that job's acceptance filed, by path and sha256.

**The driver.** `loop()` has no CLI. A short per-job driver, kept in the job folder, imports `loop` from the
kit's loop module (named in kit/bots/orchestrator.md, "Rounds" row) and calls it:

```python
summary = loop("/jobs/<job>/packet.json",
               record_dir="/jobs/<job>/record",   # outside the repo, empty at start
               cwd="/work/<job>/repo",             # the repo the Maker edits and the bridge runs in
               timeout_s=8 * 3600)                 # sized to one bot turn, not to a command
```

`timeout_s` bounds every command of a turn: the RED run, `maker.cmd` (that is, the whole Maker bot turn the
bridge waits on), the wait after it, the rerun and each Evaluator run. Size it to the longest bot turn you
will allow; the default of 600 s would cut most bot turns off. The job clock (`bounds.budget.time_hours_lt`)
still applies on top: each command is bounded by the smaller of `timeout_s` and the clock left, so set the clock
to cover `cap` rounds of one Maker turn plus `runs` Evaluator turns.

## 2. What the bridge does

`R` is the directory of `PLUMBLINE_COST`, which is `record_dir`. Every file the bridge writes is under `R`,
written to a temporary name in the same directory and then renamed over the target (`os.replace`). It writes
nothing under the repo, so `loop()`'s snapshot of the tree sees only the Maker's edits.

**`maker`** (one Maker turn), with `PLUMBLINE_FINDINGS` and `PLUMBLINE_COST` from `loop()`:

1. Reads the findings; `N` is its `round`. A missing or unreadable input, or an `N` that disagrees with the
   `cost-NN-maker.json` name, exits 2 with one line on stderr and writes no dispatch file.
2. Moves an earlier turn's `R/aider-exit.json` to `R/bridge/aider-exit-stale-NN.json` (bytes unchanged; never
   deleted).
3. Writes `R/bridge/maker-request-NN.json` (`kind` `maker_request`, `round`, `findings`, `findings_sha256`, `cwd`,
   `exit_file`, `written_at`), then `R/aider-dispatch.json` (`round`, `request`, `request_sha256`, `exit_file`).
4. Blocks until `R/aider-exit.json` holds the record for this request (below), then writes the cost file from the
   record's `cost_usd` and exits 0 if the record's `exit` is 0, else 1.

**`evaluator`** (one Evaluator run), with `PLUMBLINE_TURN` and `PLUMBLINE_COST` (`cost-NN-eval-I.json`):

1. Reads the turn; `N` is its `round`, `I` the run index in the cost file name. A disagreement or an unreadable
   input exits 2 with one line on stderr and writes nothing.
2. Writes `R/bridge/eval-request-NN-I.json` (`kind` `eval_request`, `round`, `run`, `turn`, `turn_sha256`,
   `reading_file`, `written_at`).
3. Blocks until `R/bridge/eval-reading-NN-I.json` is the reading for this request, writes the cost file from
   `bridge.cost_usd`, prints the reading file's bytes to stdout (nothing else on stdout or stderr) and exits 0.

Every step is a line in `R/bridge/log.jsonl` (`at`, `event`, `pid` and the step's fields).

## 3. What the Orchestrator does

The bridge only writes and reads files. The E-DI Orchestrator, watching `R`:

1. **Watches** for a new `R/aider-dispatch.json` (a Maker turn) and new `R/bridge/eval-request-*.json` files (one
   per Evaluator run).
2. **Checks the built message** before delivery: the C39 held-out check (no held-out file's bytes or sha256 in
   what the seat is sent), and for a Maker turn after round 1 the rule-12 handoff check
   (`check_best_artifact_handoff.py`; the message carries the best artifact named in `findings.best` byte for
   byte; kit/bots/orchestrator.md L41).
3. **Delivers** the request file (its path and sha256, and its content) to the E-DI Maker or the E-DI Evaluator.
4. Checks each seat's declared `cost_usd` against the provider's ledger for any paid call the seat made.

## 4. What each seat writes, and how

Both seats write one JSON object by **atomic rename**: write a temporary file in the same directory (for
example `<name>.part`), then rename it to the final name. A half-written file under the final name is waited
on, not taken, but a rename means the bridge never sees one.

**The Maker** works in the request's `cwd`, inside the packet's editable paths, and when it is done writes
`R/aider-exit.json` (the request's `exit_file`):

```json
{"round": 1, "request_sha256": "<request_sha256 from aider-dispatch.json>", "exit": 0, "cost_usd": 0}
```

`exit` is an int (0 = finished; anything else = the turn failed). Write it only after the last edit: `loop()`
measures the tree as soon as the bridge returns.

**The Evaluator** writes `reading_file` from its request: the reading `loop()` expects (`dimensions`
[{`name`, `score`, `observation`}], `controls` {`should_pass`: `passed`, `should_fail`: `failed`}, `verdict`,
`violations`) plus a `bridge` object naming the request:

```json
{"dimensions": [...], "controls": {...}, "verdict": "accept", "violations": [],
 "bridge": {"round": 1, "run": 0, "request_sha256": "<sha256 of the request file's bytes>", "cost_usd": 0}}
```

A record or reading that names another round, run or request is logged and ignored; the bridge keeps waiting.

**`cost_usd`** is the US$ the seat spent on paid calls for that turn: `0` for Grok Bot usage alone, the real
figure for any paid call. The bridge writes it to `PLUMBLINE_COST` as `{"amount": cost_usd, "unit": "USD",
...}` only when it is a finite number of 0 or more and not a bool. It never defaults it: a missing figure must
reach `loop()` as missing, because with a budget above 0 `loop()` stops a round whose spend it cannot measure
(`budget unmeasured`), and a default of 0 would turn an unmeasured spend into a measured zero.

## 5. What each stop looks like

| What happens | The bridge | `loop()` stops with |
|---|---|---|
| The Maker never writes its exit record | blocks until `loop()` kills it at `timeout_s` | `timeout` (`clock` if the job clock, not `timeout_s`, was the bound) |
| The Evaluator never writes its reading | blocks until killed at `timeout_s` | `evaluator failed` (a timed-out run) |
| The two Evaluator runs differ in verdict or a score | prints each reading as written | `evaluator split` |
| The Maker declares no `cost_usd` and the budget is above 0 | writes no cost file | `budget unmeasured` |
| An Evaluator run declares no `cost_usd` and the budget is above 0 | writes no cost file | `budget unmeasured` |
| A declared cost above 0 when the budget is 0 | writes the figure | `budget` |
| The Maker's record says `exit` other than 0 | exits 1 | `maker failed` |

## 6. Limits

* **Not a sandbox.** The bridge does not confine a seat. `loop()` detects edits outside the editable set and an
  Evaluator that changes the tree; it does not prevent them.
* **The seat's declared cost is trusted.** The bridge passes on what the seat wrote. The Orchestrator checks it
  against the provider's ledger.
* **One uid.** Every agent on the box runs as the same user, so file permissions do not separate the seats or
  protect `R` from them.
* **One `loop()` per `record_dir`.** `aider-dispatch.json` and `aider-exit.json` are fixed names per record dir,
  not per round, and the log is rewritten by one process at a time. Two loops on one record dir would collide.
* **Polling.** The bridge looks at the answer file every `--poll` seconds; there is no file watcher.

## 7. Decisions where bar.md section 3 is silent

Each is the smallest choice that works.

1. **Exit codes.** Bad input or a write failure under `R`: exit 2 with one line on stderr. A Maker record with a
   non-zero `exit`: exit 1. A matched record with `exit` 0, or a printed reading: exit 0.
2. **`--poll` default** is 1.0 s. A value that is not a finite number above 0 is refused by the argument parser
   (exit 2).
3. **`R` must already exist** (`loop()` creates it). The bridge creates only `R/bridge/`.
4. **Integer `round`.** A findings or turn object that is not a JSON object with an integer `round` (not a bool) is
   an unreadable input. A cost file name whose `NN` or `I` does not parse (`cost-NN-maker.json`,
   `cost-NN-eval-I.json`, digits only) is refused the same way.
5. **The evaluator refuses before writing anything**, request file included.
6. **Refusals are logged** to `R/bridge/log.jsonl` only when `R/bridge/` already exists; a refusal never creates
   it. The one-line reason always goes to stderr.
7. **An unwritable `R`** fails at the first write (creating `R/bridge/` or the log), before any request or
   dispatch file, with exit 2 and one line.
8. **The stale exit record** goes to `R/bridge/aider-exit-stale-NN.json`, or `...-NN-k.json` (k = 1, 2, ...) if
   that name is taken, by `os.rename` (same file system, bytes unchanged).
9. **The log is appended by rewriting it**: the old bytes plus the new line, to a temporary name, then
   `os.replace`, so the log too is written atomically. `loop()` runs one command at a time per record dir.
10. **Ignored answers are logged once** per distinct content (by sha256), not on every poll.
11. **A valid exit record** needs `round` = N and `exit` as ints (not bools) and `request_sha256` equal to the
    request's. A valid reading needs `bridge.round` = N and `bridge.run` = I as ints and `bridge.request_sha256`
    equal to the request's. A record or reading that fails this keeps the bridge waiting.
12. **`cost_usd` must be finite**: `Infinity` and `NaN` (which Python's JSON reader accepts) write no cost file.
13. **The cost file** holds `amount`, `unit` `"USD"`, `source` (the exit record or reading path), `source_sha256`
    and `written_at`. `loop()` reads only `amount`.
14. **Request files** are pretty-printed JSON with sorted keys and a final newline; `request_sha256` is the
    sha256 of exactly those bytes. A request file for the same round (and run) is replaced if it already exists.
15. **`written_at`** is local time with its UTC offset, to the second (`2026-11-14T15:30:00-05:00`).
16. **An evaluator reading file left from before** is not moved: it cannot match the new request's sha256, so it
    is ignored until the seat replaces it.
