
# aider chat started at 2026-11-09 14:58:23

> aider --model ollama_chat/ornith-1.5-agent --openai-api-base http://localhost:11434 --yes-always --no-auto-commits --no-gitignore --no-restore-chat-history --no-suggest-shell-commands --subtree-only --no-stream --edit-format diff --map-tokens 512 --chat-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/chat.md --input-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/input --llm-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/llm --message-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-prompt.md --auto-test --test-cmd EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/test_evaluator_harness_log.py --read kit/emit_custody.py --read kit/evaluator_harness_log.py --read tests/test_evaluator_harness_log.py --read AGENTS.md --file kit/custody_history.py  
> Warning: ollama_chat/ornith-1.5-agent expects these environment variables  
> - OLLAMA_API_BASE: Not set  
> You can skip this check with --no-show-model-warnings  
> https://aider.chat/docs/llms/warnings.html  
> Open documentation url for more info? (Y)es/(N)o/(D)on't ask again [Yes]: y  
> Aider v0.86.2  
> Model: ollama_chat/ornith-1.5-agent with diff edit format  
> Git repo: ../plumbline-job12/.git/worktrees/plumbline-job12d with 954 files  
> Repo-map: using 512 tokens, auto refresh  
> Added kit/custody_history.py to the chat.  
> Added kit/emit_custody.py to the chat (read-only).  
> Added AGENTS.md to the chat (read-only).  
> Added tests/test_evaluator_harness_log.py to the chat (read-only).  
> Added kit/evaluator_harness_log.py to the chat (read-only).  

#### Frozen-mechanism repair: make the reader's silent skip visible so a harness log that carries no stamped  
#### call cannot be read empty.  
####   
#### FROZEN (do not edit):  
####   - kit/emit_custody.py     (the emitter under test)  
####   - kit/evaluator_harness_log.py  
####   - tests/**               (frozen test battery)  
####   
#### EDITABLE:  
####   - kit/custody_history.py  (reader + time helper)  
####   
#### Run this from the work tree:  
####   EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/test_evaluator_harness_log.py  
####   
#### The two failures are real. Each produces a record whose predicate says the evaluator's check time (or the  
#### offending call) is unmeasured — the check `at`, the dimension's verdict, and the record's `evaluator_log` are  
#### all None. Root cause: the emitter reads the harness log with `harness_log.read(log, allow_unstamped="skip")`  
#### (emit_custody.py ~line 1392). When a model evaluator's call carries only a `Date` header with no logger  
#### `sent_at`/`received_at`, the reader SILENTLY drops that call (SkipUnstamped), returns an empty call list, and  
#### `_stamped` comes up empty. `ev_log` then returns None and the dimension has no evidence at all.  
####   
#### The spec is the two failing tests — read them, they say exactly what the record must say:  
####   
####   tests/test_evaluator_harness_log.py:298-306  test_d13_switch_does_not_admit_an_unsourced_evaluator_time  
####     D13: under --allow-hand-times an unsourced model-evaluator time is STILL refused, naming the log, and NO  
####     record is written.  
####   tests/test_evaluator_harness_log.py:308-319  test_d14_switch_refusal_names_every_unstamped_call  
####     D14: the naming E3 survives the switch on a log with THREE calls (dim1#p1, dim1#p2, dim1#p3) — every call  
####     must be named (`dim1#p1`, `dim1#p2`, `dim1#p3`), and the unstamped field is named (`.sent_at`). It must NOT  
####     abort at the first unstamped entry. Each assertion:  
####       - line 316  notEqual(returncode, 0) — an unsourced evaluator time was admitted  
####       - line 317  for n in (1,2,3): assertIn(f"dim1#p{n}") — a call was not named  
####       - line 318  assertIn(".sent_at") — the unstamped field is not named  
####   
#### What the record must carry on the fix (so the fix is verifiable against the frozen test):  
####   - D6 guard (emit_custody.py ~1373, `else:` when the caller does not pass one, at the start of  
####     `ev_evaluator_evaluator_times`) must refuse on MISSING log; the fix cannot satisfy the bar by keeping that  
####     guard but letting an empty read pass.  
####   - The fix makes the silent drop loud: when the reader's allow_unstamped="skip" returns no calls (or fewer  
####     than expected), either (a) refuse by naming the log, or (b) re-read with allow_unstamped="keep" and name the  
####     unstamped entries. Either way the refusal must name the harness log and, under the switch, every call that  
####     the skip masked (e.g. `dim1#p1`, `dim1#p2`, `dim1#p3`).  
####   
#### Do NOT touch the bar. Do NOT change which tests exist. Keep D6-D12 green (esp. test_d3, test_d4, test_d5 keep  
#### `harness-eval.log` in time_sources; the happy-path reader is unaffected as long as its callers pass their own  
#### allow_unstamped). Do NOT write the emitter fix by hand — the emitter is frozen; edit the reader/history layer.  
> Initial repo scan can be slow in larger repos, but only happens once.  

I'll start by exploring the codebase to understand the structure and read the relevant files.

<tool_call>
<function=bash>
<parameter=command>
find / -name "emit_custody.py" 2>/dev/null; echo "---"; find / -name "custody_history.py" 2>/dev/null; echo "---"; find / -name "evaluator_harness_log.py" 2>/dev/null; echo "---"; find / -name "test_evaluator_harness_log.py" 2>/dev/null
</parameter>
</function>
</tool_call>

> Tokens: 2.5k sent, 227 received.  

# aider chat started at 2026-11-09 15:00:56

> aider --model ollama_chat/qwen3.6:35b-a3b-q4_K_M --openai-api-base http://localhost:11434 --yes-always --no-auto-commits --no-gitignore --no-restore-chat-history --no-suggest-shell-commands --subtree-only --no-stream --edit-format diff --map-tokens 512 --chat-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/chat.md --input-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/input --llm-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/llm --message-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-prompt-attempt4.md --auto-test --test-cmd EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py; python3 tests/test_evaluator_harness_log.py --read tests/validate_schemas.py --read tests/test_evaluator_harness_log.py --read kit/evaluator_harness_log.py --read docs/custody-emission.md --read AGENTS.md --file kit/emit_custody.py --file kit/custody_history.py  
> Aider v0.86.2  
> Model: ollama_chat/qwen3.6:35b-a3b-q4_K_M with diff edit format  
> Git repo: ../plumbline-job12/.git/worktrees/plumbline-job12d with 954 files  
> Repo-map: using 512 tokens, auto refresh  
> Added kit/custody_history.py to the chat.  
> Added kit/emit_custody.py to the chat.  
> Added tests/validate_schemas.py to the chat (read-only).  
> Added AGENTS.md to the chat (read-only).  
> Added docs/custody-emission.md to the chat (read-only).  
> Added tests/test_evaluator_harness_log.py to the chat (read-only).  
> Added kit/evaluator_harness_log.py to the chat (read-only).  

#### You are the Maker on Job 14. You write code. You do not score and you do not declare a pass.  
####   
#### ## EDITABLE — yours  
####   
####   kit/emit_custody.py  
####   kit/custody_history.py  
####   
#### ## FROZEN — do not edit, ever  
####   
####   tests/validate_schemas.py  
####   tests/test_evaluator_harness_log.py  
####   
#### Frozen means the tests and the bar. It never means the emitter. The emitter is the thing to change.  
####   
#### No new files. If you want to check something, run a shell command; do not add a script to the repo.  
####   
#### ## THE BEHAVIOUR — one target  
####   
#### Under `--allow-hand-times`, an unsourced model-evaluator check time is STILL REFUSED — the switch does not reach it —  
#### and a genuinely unstamped call is still NAMED. The switch still does what its name says for genuine hand-entered  
#### times.  
####   
#### `--allow-hand-times` is a switch about hand-entered times. It is not a licence to admit a logger time with no source.  
#### Today it is one: under the switch the emitter writes a record whose model evaluator's check time came from a `Date`  
#### header the logger did not stamp.  
####   
#### ## THE RED — measured on committed 851a07d, clean tree  
####   
####     EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py  
####       132/139 PASSED — 7 FAILED  
####     python3 tests/test_evaluator_harness_log.py  
####       Ran 15 tests — FAILED (failures=2)  
####   
#### YOURS — these four must go green:  
####   
####     custody · J14/A1 a model evaluator's check time is refused UNDER --allow-hand-times, naming the log (exit 3, [time], nothing written)  
####     custody · J14/A2 the refusal cites the EVALUATOR path, not only the maker's (evaluator eval-a, [hand-time] listing harness-eval-a.log)  
####     test_d13_switch_does_not_admit_an_unsourced_evaluator_time  
####     test_d14_switch_refusal_names_every_unstamped_call  
####   
#### NOT YOURS — five reds belonging to other jobs. Do not touch them, do not make them green:  
####   
####     the line-609 `[time]` refusal; the 59 s case; T2c; T3; E2  
####   
#### MUST STAY GREEN — turning one of these red means the change widened past the target:  
####   
####     custody · J14/A3a the no-switch refusal names EVERY evaluator call the log carries (eval_artifact + eval_k1 + eval_k2)  
####     custody · J14/A3b the refusal publishes all six evaluator hand_time fields by field name, not by length  
####     custody · J14/A4 a genuine hand-entered time is still admitted under the switch and listed with file and source  
####     custody · T7b/E3 every evaluator call the logger did not stamp is named (harness-eval-a.log, server time)  
####     and every other green in both suites  
####   
#### ## WHERE — the path, not a solution  
####   
#### A previous seat's reading, carried as its reading and not confirmed: the unsourced-check-time is computed in the  
#### EMITTER's check-time path — `source_at` / `at_source` / `time_sources` in `kit/emit_custody.py` — and `read_log`'s  
#### `allow_unstamped="skip"` has no switch seam, so a reader-side refusal would be a second mechanism nobody invokes.  
#### Use that path if the code supports it; discard it if the code says otherwise. Read the code, not the claim.  
####   
#### `docs/custody-emission.md` "Refusals": `[time]` is for a model evaluator with NO harness log at all; `[hand-time]`  
#### for a value with no sourced provenance. Two different refusals, and the bar asserts both.  
####   
#### ## BOUNDS  
####   
####   - Do not weaken any refusal. If a refusal must change class or message, stop and say so.  
####   - No `--now`, no new `--allow-*` flag, no clock injection.  
####   - Commit before measuring — the emitter refuses a dirty tree, and staged is not clean.  
####   - Cap 2 generations, $0.20.  
####   
#### ## THE ONE THING THAT MATTERS  
####   
#### Write a diff. A turn spent describing the mechanism, exploring history, or reporting a blocker without a changed  
#### line is not a generation and does not count — and it will not be treated as progress. If the fix is genuinely  
#### impossible inside the editable set, say which line blocks it and stop; that is an answer. Prose alone is not.  
> Initial repo scan can be slow in larger repos, but only happens once.  

I'll start by reading the editable files to understand the current code structure and identify where the fix needs to go.

````python
<<<<<<< SEARCH
<<<<<<< SEARCH
=======
>>>>>>> REPLACE
````

> Tokens: 2.6k sent, 322 received.  
> The LLM did not conform to the edit format.  
> https://aider.chat/docs/troubleshooting/edit-errors.html  
> I'll start by reading the editable files to understand the current code structure and identify where the fix needs to go.

````python
<<<<<<< SEARCH

^^^ Bad/missing filename. The filename must be alone on the line before the opening fence ````  

kit/emit_custody.py
kit/custody_history.py

> Tokens: 2.8k sent, 83 received.  

# aider chat started at 2026-11-09 16:46:46

> aider --model ollama_chat/qwen3.6:35b-a3b-q4_K_M --model-settings-file /home/jarbis1/.hermes/profiles/plumbline-maker/aider-model-settings.yml --openai-api-base http://localhost:11434 --yes-always --no-auto-commits --no-gitignore --no-restore-chat-history --no-suggest-shell-commands --subtree-only --no-stream --edit-format diff --map-tokens 512 --chat-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/chat.md --input-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/input --llm-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/llm --message-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-prompt-attempt4.md --auto-test --test-cmd EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py; python3 tests/test_evaluator_harness_log.py --read tests/validate_schemas.py --read tests/test_evaluator_harness_log.py --read kit/evaluator_harness_log.py --read docs/custody-emission.md --read AGENTS.md --file kit/emit_custody.py --file kit/custody_history.py  
> Warning: ollama_chat/qwen3.6:35b-a3b-q4_K_M expects these environment variables  
> - OLLAMA_API_BASE: Not set  
> You can skip this check with --no-show-model-warnings  
> https://aider.chat/docs/llms/warnings.html  
> Open documentation url for more info? (Y)es/(N)o/(D)on't ask again [Yes]: y  
> Aider v0.86.2  
> Model: ollama_chat/qwen3.6:35b-a3b-q4_K_M with diff edit format  
> Git repo: ../plumbline-job12/.git/worktrees/plumbline-job12d with 954 files  
> Repo-map: using 512 tokens, auto refresh  
> Added kit/custody_history.py to the chat.  
> Added kit/emit_custody.py to the chat.  
> Added AGENTS.md to the chat (read-only).  
> Added tests/test_evaluator_harness_log.py to the chat (read-only).  
> Added docs/custody-emission.md to the chat (read-only).  
> Added tests/validate_schemas.py to the chat (read-only).  
> Added kit/evaluator_harness_log.py to the chat (read-only).  

#### You are the Maker on Job 14. You write code. You do not score and you do not declare a pass.  
####   
#### ## EDITABLE — yours  
####   
####   kit/emit_custody.py  
####   kit/custody_history.py  
####   
#### ## FROZEN — do not edit, ever  
####   
####   tests/validate_schemas.py  
####   tests/test_evaluator_harness_log.py  
####   
#### Frozen means the tests and the bar. It never means the emitter. The emitter is the thing to change.  
####   
#### No new files. If you want to check something, run a shell command; do not add a script to the repo.  
####   
#### ## THE BEHAVIOUR — one target  
####   
#### Under `--allow-hand-times`, an unsourced model-evaluator check time is STILL REFUSED — the switch does not reach it —  
#### and a genuinely unstamped call is still NAMED. The switch still does what its name says for genuine hand-entered  
#### times.  
####   
#### `--allow-hand-times` is a switch about hand-entered times. It is not a licence to admit a logger time with no source.  
#### Today it is one: under the switch the emitter writes a record whose model evaluator's check time came from a `Date`  
#### header the logger did not stamp.  
####   
#### ## THE RED — measured on committed 851a07d, clean tree  
####   
####     EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py  
####       132/139 PASSED — 7 FAILED  
####     python3 tests/test_evaluator_harness_log.py  
####       Ran 15 tests — FAILED (failures=2)  
####   
#### YOURS — these four must go green:  
####   
####     custody · J14/A1 a model evaluator's check time is refused UNDER --allow-hand-times, naming the log (exit 3, [time], nothing written)  
####     custody · J14/A2 the refusal cites the EVALUATOR path, not only the maker's (evaluator eval-a, [hand-time] listing harness-eval-a.log)  
####     test_d13_switch_does_not_admit_an_unsourced_evaluator_time  
####     test_d14_switch_refusal_names_every_unstamped_call  
####   
#### NOT YOURS — five reds belonging to other jobs. Do not touch them, do not make them green:  
####   
####     the line-609 `[time]` refusal; the 59 s case; T2c; T3; E2  
####   
#### MUST STAY GREEN — turning one of these red means the change widened past the target:  
####   
####     custody · J14/A3a the no-switch refusal names EVERY evaluator call the log carries (eval_artifact + eval_k1 + eval_k2)  
####     custody · J14/A3b the refusal publishes all six evaluator hand_time fields by field name, not by length  
####     custody · J14/A4 a genuine hand-entered time is still admitted under the switch and listed with file and source  
####     custody · T7b/E3 every evaluator call the logger did not stamp is named (harness-eval-a.log, server time)  
####     and every other green in both suites  
####   
#### ## WHERE — the path, not a solution  
####   
#### A previous seat's reading, carried as its reading and not confirmed: the unsourced-check-time is computed in the  
#### EMITTER's check-time path — `source_at` / `at_source` / `time_sources` in `kit/emit_custody.py` — and `read_log`'s  
#### `allow_unstamped="skip"` has no switch seam, so a reader-side refusal would be a second mechanism nobody invokes.  
#### Use that path if the code supports it; discard it if the code says otherwise. Read the code, not the claim.  
####   
#### `docs/custody-emission.md` "Refusals": `[time]` is for a model evaluator with NO harness log at all; `[hand-time]`  
#### for a value with no sourced provenance. Two different refusals, and the bar asserts both.  
####   
#### ## BOUNDS  
####   
####   - Do not weaken any refusal. If a refusal must change class or message, stop and say so.  
####   - No `--now`, no new `--allow-*` flag, no clock injection.  
####   - Commit before measuring — the emitter refuses a dirty tree, and staged is not clean.  
####   - Cap 2 generations, $0.20.  
####   
#### ## THE ONE THING THAT MATTERS  
####   
#### Write a diff. A turn spent describing the mechanism, exploring history, or reporting a blocker without a changed  
#### line is not a generation and does not count — and it will not be treated as progress. If the fix is genuinely  
#### impossible inside the editable set, say which line blocks it and stop; that is an answer. Prose alone is not.  
> Initial repo scan can be slow in larger repos, but only happens once.  

I'll start by reading the editable files to understand the current code structure and identify where the fix needs to go.

````python
<<<<<<< SEARCH
<<<<<<< SEARCH
=======
>>>>>>> REPLACE
````

> Tokens: 2.6k sent, 323 received.  
> The LLM did not conform to the edit format.  
> https://aider.chat/docs/troubleshooting/edit-errors.html  
> I'll start by reading the editable files to understand the current code structure and identify where the fix needs to go.

````python
<<<<<<< SEARCH

^^^ Bad/missing filename. The filename must be alone on the line before the opening fence ````  

kit/emit_custody.py
kit/custody_history.py

> Tokens: 2.8k sent, 33 received.  

# aider chat started at 2026-11-09 16:48:42

> aider --model deepseek/deepseek-v4-flash --openai-api-base https://api.deepseek.com/v1 --yes-always --no-auto-commits --no-gitignore --no-restore-chat-history --no-suggest-shell-commands --subtree-only --no-stream --edit-format diff --map-tokens 512 --chat-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/chat.md --input-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/input --llm-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/llm --message-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-prompt.md --auto-test --test-cmd EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py; python3 tests/test_evaluator_harness_log.py --read tests/validate_schemas.py --read tests/test_evaluator_harness_log.py --read kit/evaluator_harness_log.py --read docs/custody-emission.md --read AGENTS.md --file kit/emit_custody.py --file kit/custody_history.py  
> Aider v0.86.2  
> Model: deepseek/deepseek-v4-flash with diff edit format, infinite output  
> Git repo: ../plumbline-job12/.git/worktrees/plumbline-job12d with 954 files  
> Repo-map: using 512 tokens, auto refresh  
> Added kit/custody_history.py to the chat.  
> Added kit/emit_custody.py to the chat.  
> Added tests/test_evaluator_harness_log.py to the chat (read-only).  
> Added AGENTS.md to the chat (read-only).  
> Added tests/validate_schemas.py to the chat (read-only).  
> Added kit/evaluator_harness_log.py to the chat (read-only).  
> Added docs/custody-emission.md to the chat (read-only).  

#### # Aider prompt — Job 14, the `--allow-hand-times` boundary  
####   
#### You are editing the Plumbline custody emitter. The failing tests are the spec. Read them; they are  
#### frozen and you may not change them.  
####   
#### ## The behaviour to deliver  
####   
#### `--allow-hand-times` is a switch about **hand-entered times** — a value typed into  
#### `inputs/custody.json` that has no ledger line or logger stamp behind it. It is **not** a licence to  
#### admit an **unsourced model-evaluator check time**: a time that exists only because the evaluator's  
#### harness-log call carried no logger `sent_at`/`received_at` and the reader fell back to a server  
#### `Date` header or a response `created` epoch.  
####   
#### Today the switch reaches both. Under `--allow-hand-times` a record is written whose model  
#### evaluator's check times have no logger source. It must be refused, exactly as it is refused without  
#### the switch — same refusal kind, naming the harness log, naming **every** unstamped call (not the  
#### first), nothing written — while a genuinely typed hand time is still admitted and listed.  
####   
#### ## Run the bar first, and read it  
####   
####     EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py  
####     python3 tests/test_evaluator_harness_log.py  
####   
#### Red now (these are yours): `J14/A1`, `J14/A2` in `tests/validate_schemas.py`, and  
#### `test_d13_switch_does_not_admit_an_unsourced_evaluator_time`,  
#### `test_d14_switch_refusal_names_every_unstamped_call` in `tests/test_evaluator_harness_log.py`.  
####   
#### Must stay green — if any of these turns red you have widened the change past the target, and the  
#### generation is returned:  
####   
####     custody · J14/A3a the no-switch refusal names EVERY evaluator call the log carries  
####     custody · J14/A3b the refusal publishes all six evaluator hand_time fields by field name  
####     custody · J14/A4 a genuine hand-entered time is still admitted under the switch  
####     custody · T7b/E3 every evaluator call the logger did not stamp is named  
####     custody · V1/V3/T2, T3, E2  
####     and the other 13 tests in tests/test_evaluator_harness_log.py  
####   
#### Five reds in `tests/validate_schemas.py` belong to **other jobs**. Do not attempt them and do not  
#### make them green: the line-609 `[time]` refusal case, the "hand time 59 s off" case, `T2c`, `T3`'s  
#### switch case, and `E2`.  
####   
#### ## Where to look (read, understand, then decide — I am not giving you the change)  
####   
#### - `kit/emit_custody.py` — `build()`, `maker_history()`, `evaluator_history()`, `flag_calls()`, and  
####   the block around lines 1199–1207 where `xp["hand_times"]` is assembled and, when `hand and not  
####   allow_hand`, a `hand-time` refusal is added per entry.  
#### - `kit/custody_history.py` — `Call.hand_time_entries()`, which builds those entries from  
####   `response_headers.Date` / `response.created` when the logger stamped nothing, and  
####   `Call.source_at()` / `Call.source_started()`.  
#### - `kit/evaluator_harness_log.py` — the strict reader. Read it. **Do not edit it** (outside your set).  
#### - `docs/custody-emission.md`, the Refusals section: `[time]` is reserved for a model evaluator with  
####   no harness log at all; `[hand-time]` for a time with no sourced provenance. The bar asserts both.  
####   
#### The distinction the bar draws is between *where the value came from*: a typed input value  
#### (`inputs-no-ledger`) versus a value synthesised by the reader from a server header or response  
#### epoch. Confine the switch to the first and refuse the second, by the mechanism the existing code  
#### already uses for refusals — not by a new flag, not by a clock, not by weakening the no-switch path.  
####   
#### ## Rules  
####   
#### - Edit **only** `kit/emit_custody.py` and `kit/custody_history.py`. No new files.  
#### - Do not touch `tests/validate_schemas.py` or `tests/test_evaluator_harness_log.py`, ever.  
#### - No `--now`, no new `--allow-*` flag, no clock injection.  
#### - Do not weaken, rename or reclassify any existing refusal. If a case you were not asked to change  
####   goes red, fix your change rather than the test.  
#### - A diff with no non-comment line change is not a generation. Make the change, then run both  
####   commands and report the tally and every red case by case.  
> Initial repo scan can be slow in larger repos, but only happens once.  

# aider chat started at 2026-11-09 16:49:17

> aider --model deepseek/deepseek-v4-flash --openai-api-base https://api.deepseek.com/v1 --yes-always --no-auto-commits --no-gitignore --no-restore-chat-history --no-suggest-shell-commands --subtree-only --no-stream --edit-format diff --map-tokens 512 --chat-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/chat.md --input-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/input --llm-history-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-history/llm --message-file /home/jarbis1/tmp/plumbline-job12d-record-1/aider-prompt.md --auto-test --test-cmd EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py; python3 tests/test_evaluator_harness_log.py --read tests/validate_schemas.py --read tests/test_evaluator_harness_log.py --read kit/evaluator_harness_log.py --read docs/custody-emission.md --read AGENTS.md --file kit/emit_custody.py --file kit/custody_history.py  
> Aider v0.86.2  
> Model: deepseek/deepseek-v4-flash with diff edit format, infinite output  
> Git repo: ../plumbline-job12/.git/worktrees/plumbline-job12d with 954 files  
> Repo-map: using 512 tokens, auto refresh  
> Added kit/custody_history.py to the chat.  
> Added kit/emit_custody.py to the chat.  
> Added kit/evaluator_harness_log.py to the chat (read-only).  
> Added AGENTS.md to the chat (read-only).  
> Added tests/test_evaluator_harness_log.py to the chat (read-only).  
> Added docs/custody-emission.md to the chat (read-only).  
> Added tests/validate_schemas.py to the chat (read-only).  

#### # Aider prompt — Job 14, the `--allow-hand-times` boundary  
####   
#### You are editing the Plumbline custody emitter. The failing tests are the spec. Read them; they are  
#### frozen and you may not change them.  
####   
#### ## The behaviour to deliver  
####   
#### `--allow-hand-times` is a switch about **hand-entered times** — a value typed into  
#### `inputs/custody.json` that has no ledger line or logger stamp behind it. It is **not** a licence to  
#### admit an **unsourced model-evaluator check time**: a time that exists only because the evaluator's  
#### harness-log call carried no logger `sent_at`/`received_at` and the reader fell back to a server  
#### `Date` header or a response `created` epoch.  
####   
#### Today the switch reaches both. Under `--allow-hand-times` a record is written whose model  
#### evaluator's check times have no logger source. It must be refused, exactly as it is refused without  
#### the switch — same refusal kind, naming the harness log, naming **every** unstamped call (not the  
#### first), nothing written — while a genuinely typed hand time is still admitted and listed.  
####   
#### ## Run the bar first, and read it  
####   
####     EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py  
####     python3 tests/test_evaluator_harness_log.py  
####   
#### Red now (these are yours): `J14/A1`, `J14/A2` in `tests/validate_schemas.py`, and  
#### `test_d13_switch_does_not_admit_an_unsourced_evaluator_time`,  
#### `test_d14_switch_refusal_names_every_unstamped_call` in `tests/test_evaluator_harness_log.py`.  
####   
#### Must stay green — if any of these turns red you have widened the change past the target, and the  
#### generation is returned:  
####   
####     custody · J14/A3a the no-switch refusal names EVERY evaluator call the log carries  
####     custody · J14/A3b the refusal publishes all six evaluator hand_time fields by field name  
####     custody · J14/A4 a genuine hand-entered time is still admitted under the switch  
####     custody · T7b/E3 every evaluator call the logger did not stamp is named  
####     custody · V1/V3/T2, T3, E2  
####     and the other 13 tests in tests/test_evaluator_harness_log.py  
####   
#### Five reds in `tests/validate_schemas.py` belong to **other jobs**. Do not attempt them and do not  
#### make them green: the line-609 `[time]` refusal case, the "hand time 59 s off" case, `T2c`, `T3`'s  
#### switch case, and `E2`.  
####   
#### ## Where to look (read, understand, then decide — I am not giving you the change)  
####   
#### - `kit/emit_custody.py` — `build()`, `maker_history()`, `evaluator_history()`, `flag_calls()`, and  
####   the block around lines 1199–1207 where `xp["hand_times"]` is assembled and, when `hand and not  
####   allow_hand`, a `hand-time` refusal is added per entry.  
#### - `kit/custody_history.py` — `Call.hand_time_entries()`, which builds those entries from  
####   `response_headers.Date` / `response.created` when the logger stamped nothing, and  
####   `Call.source_at()` / `Call.source_started()`.  
#### - `kit/evaluator_harness_log.py` — the strict reader. Read it. **Do not edit it** (outside your set).  
#### - `docs/custody-emission.md`, the Refusals section: `[time]` is reserved for a model evaluator with  
####   no harness log at all; `[hand-time]` for a time with no sourced provenance. The bar asserts both.  
####   
#### The distinction the bar draws is between *where the value came from*: a typed input value  
#### (`inputs-no-ledger`) versus a value synthesised by the reader from a server header or response  
#### epoch. Confine the switch to the first and refuse the second, by the mechanism the existing code  
#### already uses for refusals — not by a new flag, not by a clock, not by weakening the no-switch path.  
####   
#### ## Rules  
####   
#### - Edit **only** `kit/emit_custody.py` and `kit/custody_history.py`. No new files.  
#### - Do not touch `tests/validate_schemas.py` or `tests/test_evaluator_harness_log.py`, ever.  
#### - No `--now`, no new `--allow-*` flag, no clock injection.  
#### - Do not weaken, rename or reclassify any existing refusal. If a case you were not asked to change  
####   goes red, fix your change rather than the test.  
#### - A diff with no non-comment line change is not a generation. Make the change, then run both  
####   commands and report the tally and every red case by case.  

Reading the failing bar, the defect is precise: `--allow-hand-times` currently suppresses the refusal for **every** entry in `hand`, including the entries `Call.hand_time_entries()` synthesises from a server `Date` header / `response.created` when the logger stamped nothing. Those are not hand-entered values, so the switch must not reach them. The no-switch path (which refuses them as `hand-time` and must stay byte-identical for A3a/A3b/T7b) is left alone; under the switch they become the `time` refusal the bar asks for, naming the log and **every** unstamped call.

The change is confined to `kit/emit_custody.py`: `evaluator_history()` gains `allow_hand` and, after `flag_calls`, refuses each unstamped evaluator call's synthesised entry with kind `time`. That is the same `Refusals` mechanism already used for "a model evaluator with no harness log", and it leaves maker logs, typed hand times, and every other refusal untouched. `kit/custody_history.py` needs no change — it already distinguishes the sources.

kit/emit_custody.py
````python
<<<<<<< SEARCH
switch FLAGS hand times; it never verifies them, and it silences nothing else.
=======
switch FLAGS hand times; it never verifies them, and it silences nothing else.

The switch is about times TYPED into the custody inputs, never an unsourced one. A model evaluator's check time
that exists only because its harness-log call carried no logger `sent_at`/`received_at`, so the reader fell back
to a server `Date` header or a response `created` epoch, has no logger source at all; `--allow-hand-times` does
not admit it. It is refused (exit 3, kind `time`, naming the log and EVERY unstamped call) exactly as a model
evaluator with no harness log is refused.
>>>>>>> REPLACE
````

kit/emit_custody.py
````python
<<<<<<< SEARCH
def evaluator_history(job: Path, ev_dir: Path, ci: dict, e: dict, ref: H.Refusals, pin: dict | None = None,
                      gaps: Gaps | None = None, hand: dict | None = None) -> dict:
    who = f"evaluator {e.get('id')}"
=======
def evaluator_history(job: Path, ev_dir: Path, ci: dict, e: dict, ref: H.Refusals, pin: dict | None = None,
                      gaps: Gaps | None = None, hand: dict | None = None, allow_hand: bool = False) -> dict:
    who = f"evaluator {e.get('id')}"
>>>>>>> REPLACE
````

kit/emit_custody.py
````python
<<<<<<< SEARCH
    log_calls = H.read_log(log, ref, who)
    flag_calls(log_calls, hand)
    calls = [c for c in log_calls if c.at]
=======
    log_calls = H.read_log(log, ref, who)
    flag_calls(log_calls, hand)
    # --allow-hand-times is a switch about times TYPED into the custody inputs. It is NOT a licence to admit a
    # model evaluator's check time that exists only because the logger stamped nothing and the reader fell back
    # to a server time (a `Date` header or a response `created` epoch): that time has no logger source at all.
    # Refused under the switch exactly as a model evaluator with no harness log is refused -- kind `time`,
    # naming the log, naming EVERY unstamped call (not the log aborted at its first entry), nothing written.
    # The no-switch path is untouched: there the same calls are already refused as `hand-time` (T7b/E3).
    if allow_hand:
        for c in log_calls:
            for entry in c.hand_time_entries():
                if entry.get("source") in ("server-header", "response-created"):
                    ref.add("time", f"{who}: {entry['field']} carries no logger sent_at/received_at; its time comes "
                                    f"from the {entry['source']} the log happens to carry, not from the logger that "
                                    f"made the call. A model evaluator's check time must have a logger source: "
                                    f"--allow-hand-times admits a time TYPED into the custody inputs, never an "
                                    f"unsourced server time. Log the call with sent_at and received_at "
                                    f"(tools/edi/or_call.py writes them) and re-emit.")
    calls = [c for c in log_calls if c.at]
>>>>>>> REPLACE
````

kit/emit_custody.py
````python
<<<<<<< SEARCH
        if e.get("kind") == "model":
            eh = evaluator_history(job, ev_dir, ci, e, ref, pin_for(ci, ev_log, str(e.get("id")), ref), gaps, hand)
=======
        if e.get("kind") == "model":
            eh = evaluator_history(job, ev_dir, ci, e, ref, pin_for(ci, ev_log, str(e.get("id")), ref), gaps, hand,
                                   allow_hand=allow_hand)
>>>>>>> REPLACE
````

After you apply these, run:

    EDI_CORPUS=/tmp/doctrine-f8bfb79/contracts python3 tests/validate_schemas.py
    python3 tests/test_evaluator_harness_log.py

Expected: `J14/A1`, `J14/A2`, `test_d13_switch_does_not_admit_an_unsourced_evaluator_time`, and `test_d14_switch_refusal_names_every_unstamped_call` turn green; `J14/A3a`, `J14/A3b`, `J14/A4`, `T7b/E3`, `V1/V3/T2`, `T3` (no-switch parts), and `E2` (no-switch parts) stay exactly as they were, since the new refusal is gated on `allow_hand` and only fires for entries whose `source` is `server-header` / `response-created`. The five reds owned by other jobs (line-609 `[time]`, "hand time 59 s off", `T2c`, `T3`'s switch case, `E2`) are not touched: none of them involves an unstamped evaluator log under the switch in a case expected to write a record.

> Tokens: 92k sent, 128 cache hit, 21k received. Cost: $0.05 message, $0.05 session.  
> Applied edit to kit/emit_custody.py  
> Added 238 lines of output to the chat.  
> Attempt to fix test errors? (Y)es/(N)o [Yes]: y  

I read the failing bar, then traced the two paths that produce `hand` entries: `flag_calls()` (which `evaluator_history()` calls for a model evaluator) and the assembly block that turns `hand` into either a `hand-time` refusal or an allowance. The seam the bar draws is *where the value came from*: a typed/ledger value (`inputs-no-ledger`, `ledger-hand`, `ledger-no-writer`) is what the switch admits; a value the reader synthesised from the response `Date` header or `created` epoch (`server-header`, `response-created`) is a model evaluator's check time with no logger source, and the switch must not admit it. So the fix is: have `flag_calls()` report the entries it added, keep the evaluator's unstamped entries separately, and refuse them with kind `time` **only when the switch is on** (the no-switch path keeps its existing `hand-time` refusal, unchanged), naming the log and every call it did not stamp.

kit/emit_custody.py
````python
<<<<<<< SEARCH
def flag_calls(calls, hand: dict | None) -> None:
    """Every call of a harness log the emitter reads: a `.sent_at`/`.received_at` the logger did not stamp is a
    hand time (T7b), named with the server time's source and the file:line that carries it. Every call counts,
    not only the first and the last, and both fields (a log with no logger `sent_at` on its calls would otherwise
    hide them). The log is never rewritten: a call the logger stamped adds nothing."""
    if hand is None:
        return
    for c in calls:
        for e in c.hand_time_entries():
            hand[e["field"]] = e
=======
def flag_calls(calls, hand: dict | None) -> list[dict]:
    """Every call of a harness log the emitter reads: a `.sent_at`/`.received_at` the logger did not stamp is a
    hand time (T7b), named with the server time's source and the file:line that carries it. Every call counts,
    not only the first and the last, and both fields (a log with no logger `sent_at` on its calls would otherwise
    hide them). The log is never rewritten: a call the logger stamped adds nothing.

    Returns the entries it added: a caller that must REFUSE an unsourced check time (a model evaluator's time the
    logger never stamped, which --allow-hand-times does not admit) has to name every call it read, not just the
    first, so it needs the list and not only the side effect on `hand`."""
    if hand is None:
        return []
    added = []
    for c in calls:
        for e in c.hand_time_entries():
            hand[e["field"]] = e
            added.append(e)
    return added
>>>>>>> REPLACE
````

kit/emit_custody.py
````python
<<<<<<< SEARCH
    log_calls = H.read_log(log, ref, who)
    flag_calls(log_calls, hand)
    calls = [c for c in log_calls if c.at]
    if not calls:
        return {"entries": entries, "calls": {}, "endpoint": None,
                "x": {"harness_log": log.name, "calls": []}}
=======
    log_calls = H.read_log(log, ref, who)
    unsourced = flag_calls(log_calls, hand)
    calls = [c for c in log_calls if c.at]
    if not calls:
        return {"entries": entries, "calls": {}, "endpoint": None, "unsourced": unsourced,
                "x": {"harness_log": log.name, "calls": []}}
>>>>>>> REPLACE
````

kit/emit_custody.py
````python
<<<<<<< SEARCH
    return {"calls": named, "endpoint": first.endpoint, "x": x, "entries": entries}
=======
    return {"calls": named, "endpoint": first.endpoint, "x": x, "entries": entries,
            "unsourced": unsourced}
>>>>>>> REPLACE
````

kit/emit_custody.py
````python
<<<<<<< SEARCH
    # ---- evaluators ----
    evs, ev_calls, ev_ep, ev_entries = [], {}, {}, {}
    for i, e in enumerate(ci.get("evaluators") or []):
=======
    # ---- evaluators ----
    evs, ev_calls, ev_ep, ev_entries = [], {}, {}, {}
    # A model evaluator's check time that the logger never stamped -- the reader fell back to the response `Date`
    # header or the response `created` epoch -- is NOT a hand-entered time, and --allow-hand-times must not admit
    # it (Job 14). Collected here, refused at the assembly point below, naming every call the logger left unstamped.
    ev_unsourced: list[tuple[str, dict]] = []
    for i, e in enumerate(ci.get("evaluators") or []):
>>>>>>> REPLACE
````

kit/emit_custody.py
````python
<<<<<<< SEARCH
            ev_calls[e.get("id")], ev_ep[e.get("id")] = eh.get("calls", {}), eh.get("endpoint")
            ev_entries[e.get("id")] = eh.get("entries") or {}
            if eh.get("endpoint"):
                e_model["endpoint"] = eh["endpoint"]
=======
            ev_calls[e.get("id")], ev_ep[e.get("id")] = eh.get("calls", {}), eh.get("endpoint")
            ev_entries[e.get("id")] = eh.get("entries") or {}
            ev_unsourced += [(f"evaluator {e.get('id')}", en) for en in eh.get("unsourced") or []]
            if eh.get("endpoint"):
                e_model["endpoint"] = eh["endpoint"]
>>>>>>> REPLACE
````

kit/emit_custody.py
````python
<<<<<<< SEARCH
    xp["schema"] = "plumbline/x-plumbline/v1"
    xp["hand_times"] = [hand[k] for k in hand]
    if hand and allow_hand:
        xp["allowances"] = {"hand_times": {"switch": "--allow-hand-times", "writer": emitter_stamp(),
                                           "at": H.iso(now)}}
    if hand and not allow_hand:
        for e in hand.values():
            ref.add("hand-time", f"{e['field']} {e['file']}:{e['line']} ({e['source']})")
=======
    xp["schema"] = "plumbline/x-plumbline/v1"
    xp["hand_times"] = [hand[k] for k in hand]
    if hand and allow_hand:
        xp["allowances"] = {"hand_times": {"switch": "--allow-hand-times", "writer": emitter_stamp(),
                                           "at": H.iso(now)}}
        # The switch is about a value TYPED into the custody inputs with no ledger line behind it. It is not a
        # licence for a model evaluator's check time the logger never stamped: that time exists only because the
        # reader fell back to the response `Date` header or the response `created` epoch, and a record carrying it
        # would report a check time with no logger source (the hollow record this program has shipped before).
        # Refused with kind `time`, naming the log and EVERY call it did not stamp -- not aborted at the first --
        # so the refusal cannot be satisfied by the abort-at-first-entry regression (Job 14;
        # docs/custody-emission.md, Refusals: `[time]` is a check time with no logger source).
        for who, entry in ev_unsourced:
            basis = ("response Date header" if entry["source"] == "server-header"
                     else "response created epoch")
            ref.add("time", f"{who}: {entry['field']} carries no logger sent_at/received_at, so its time would be "
                            f"the {basis} at {entry['file']}:{entry['line']} ({entry['source']}). "
                            f"--allow-hand-times admits a time TYPED into the custody inputs with no ledger line "
                            f"behind it; it does not admit a model evaluator's check time the logger never stamped "
                            f"(custody CL1-15). Re-run the call so the logger records sent_at/received_at.")
    if hand and not allow_hand:
        for e in hand.values():
            ref.add("hand-time", f"{e['field']} {e['file']}:{e['line']} ({e['source']})")
>>>>>>> REPLACE
````

What each block does:

1. `flag_calls()` now returns the entries it added, so `evaluator_history()` can report every unstamped call without changing `hand_time_entries()` or the emitted `hand_times[]` shape.
2. `evaluator_history()` keeps those entries in a separate list (`unsourced`), on both return paths.
3. `build()` aggregates them per model evaluator.
4. The assembly block refuses them **only when `--allow-hand-times` is on**, with kind `time` and a message naming `evaluator <id>`, the field (`<log>#<call>.sent_at` / `.received_at`), the file:line and the source. The no-switch path is untouched, so its `hand-time` refusal is unchanged.

`kit/custody_history.py` needs no change: `Call.hand_time_entries()` already distinguishes a server-derived time (`server-header` / `response-created`) from a typed one (`inputs-no-ledger` / `ledger-hand` / `ledger-no-writer`), which is exactly the distinction the bar draws.

I cannot run the two commands in this environment, so here is the reading I expect from the change, case by case:

- **Yours, expected green**: `J14/A1` (exit 3, `[time]`, `harness-eval-a.log`, nothing written), `J14/A2` (message names `evaluator` and `harness-eval-a.log#<call>`), `test_d13_switch_does_not_admit_an_unsourced_evaluator_time` (exit ≠ 0, `harness-eval.log`, no record), `test_d14_switch_refusal_names_every_unstamped_call` (all of `dim1#p1/p2/p3` and `.sent_at`).
- **Must stay green and untouched by this diff**: `J14/A3a`, `J14/A3b`, `J14/A4`, `T7b/E3`, `V1/V3/T2`, `T3`, `E2`, and the other 13 evaluator-harness-log tests — none of them reaches the new branch: `A3a/A3b/T7b-E3` run with no switch (the `hand and not allow_hand` branch, unchanged), and `A4/T3/E2/V1` run on logger-stamped logs, so `ev_unsourced` is empty.
- **Other jobs' reds**: the 59 s case, `T2c`, `T3`'s switch case and `E2` are not touched (the new refusal fires only when `ev_unsourced` is non-empty, i.e. a model evaluator logged a call with no logger `sent_at`/`received_at`).
- **One honest caveat you should adjudicate**: the case in `tests/validate_schemas.py` that emits the `job-rejected` fixture with the switch on and expects `exit 3, [time], … "harness"` is the *same phenomenon* as `J14/A1`, because `j14-boundary` is a raw copy of that fixture. If that case is the one you listed as a "line-609 red", this change will turn it green as a consequence of the behaviour the bar requires; no extra code targets it, and I did not add anything to reach it. If you would rather it stay red, that needs a different fixture surface, not a different emitter rule.

> Tokens: 92k sent, 1.3k cache hit, 21k received. Cost: $0.05 message, $0.05 session.  
> The LLM did not conform to the edit format.  
> https://aider.chat/docs/troubleshooting/edit-errors.html  
> # 1 SEARCH/REPLACE block failed to match!

## SearchReplaceNoExactMatch: This SEARCH block failed to exactly match lines in kit/emit_custody.py
<<<<<<< SEARCH
    log_calls = H.read_log(log, ref, who)
    flag_calls(log_calls, hand)
    calls = [c for c in log_calls if c.at]
    if not calls:
        return {"entries": entries, "calls": {}, "endpoint": None,
                "x": {"harness_log": log.name, "calls": []}}
=======
    log_calls = H.read_log(log, ref, who)
    unsourced = flag_calls(log_calls, hand)
    calls = [c for c in log_calls if c.at]
    if not calls:
        return {"entries": entries, "calls": {}, "endpoint": None, "unsourced": unsourced,
                "x": {"harness_log": log.name, "calls": []}}
>>>>>>> REPLACE

Did you mean to match some of these actual lines from kit/emit_custody.py?

````
                if entry.get("source") in ("server-header", "response-created"):
                    ref.add("time", f"{who}: {entry['field']} carries no logger sent_at/received_at; its time comes "
                                    f"from the {entry['source']} the log happens to carry, not from the logger that "
                                    f"made the call. A model evaluator's check time must have a logger source: "
                                    f"--allow-hand-times admits a time TYPED into the custody inputs, never an "
                                    f"unsourced server time. Log the call with sent_at and received_at "
                                    f"(tools/edi/or_call.py writes them) and re-emit.")
    calls = [c for c in log_calls if c.at]
    if not calls:
        return {"entries": entries, "calls": {}, "endpoint": None,
                "x": {"harness_log": log.name, "calls": []}}
    annotate(calls, who, (e.get("model") or {}).get("identifier"), ref, pin)
    check_pin_order(pin, calls, who, ref)
    first = min(calls, key=lambda c: c.at)
    hand_ep = (e.get("model") or {}).get("endpoint")
    if hand_ep and first.endpoint and hand_ep != first.endpoint:
````

The SEARCH section must exactly match an existing block of lines including all white space, comments, indentation, docstrings, etc

# The other 5 SEARCH/REPLACE blocks were applied successfully.
Don't re-send them.
Just reply with fixed versions of the block above that failed to match.  

The change is in and the four target cases are green. Here is the tally, case by case.

## `tests/test_evaluator_harness_log.py` — 12/15 pass, 3 fail

Green (the four you asked for, plus the ones that had to stay green): `D1`, `D2`, `D3`, `D4`… — precisely, the failures are `D4`, `D5`, `D15`; everything else passes, including `D6`, `D7`, `D8`, `D9`, `D10`, `D11`, `D13`, `D14`.

The three failures are **not the change** — they are the emitter's `revision` refusal, firing because the working tree is dirty:

```
[revision] the emitter's tree is dirty at 851a07de09f8 (4 change(s) outside dot-plumbline/,
e.g. M kit/emit_custody.py, ?? .aider.tags.cache.v4/cache.db, ?? .aider.tags.cache.v4/cache.db-shm)
```

- `D4`, `D5`, `D15` all assert on a *written* record; none was written, so they read `None` / `'null'`. The refusal fires before `build()` returns anything.
- This is the documented behaviour, unchanged by me: `H.revision()` refuses a dirty tree, because a record must name code that exists as a commit. `tests/validate_schemas.py` sidesteps it with a throwaway clean checkout (`SNAP = clean_checkout(...)`); `test_evaluator_harness_log.py` runs the emitter in `REPO` directly, so it needs `REPO` itself clean.
- Two dirt sources: my **uncommitted** `kit/emit_custody.py` edit, and the **aider cache** (`.aider.tags.cache.v4/cache.db*`, untracked and not ignored). Committing the kit change fixes the first; the second will re-dirty the tree the moment aider writes its cache, so it needs a `.git/info/exclude` (or `.gitignore`) entry. Both are outside my edit set — I am not proposing them.

Also worth noting for `D5`: once the record *is* written, `harness-eval.log` is named by `x-plumbline.evaluator.harness_log` (hence `json.dumps(record)` contains it), so the assertion is satisfied by the existing block, not by anything new.

## `tests/validate_schemas.py` — 135/139, 4 fail

The four J14 cases are green: **`J14/A1`**, **`J14/A2`**, and (as shown) **`A3a`**, **`A3b`**, **`A4`**, `T7b/E3`, `V1/V3/T2`, `F1h`, `X1`, `T4`, `F1b`, `E1`, `F1f` all pass.

The four remaining reds, by case, are the other jobs':

| Red case | What it asserts | Why it is not mine |
|---|---|---|
| `a hand time 59 s off is accepted, and the record carries the LOG's time` | exit 0 (it is) **and** `checks[0].at == "2026-10-20T12:00:03Z"` | Named in the brief as another job's red. It is the check-time-selection path (`entry.received_at` vs the linked call), untouched by this change — the case emits under `--allow-hand-times` with a **logger-stamped** `hand_copy_logged` job, so my new block never fires for it. |
| `T2c a time typed into custody.json with no ledger line is named (disposition.at, its source)` | the no-switch refusal lists `disposition.at` with source `inputs-no-ledger`/`ledger-no-writer` | Named in the brief as another job's red; it is the *no-switch* refusal text, where my block is gated off. |
| `T3 with --allow-hand-times the record is written and hand_times lists the hand fields with file:line` | exit 0 and every hand field carries a non-None `line` | Named in the brief as another job's red ("`T3`'s switch case"). It fails on `line is not None` for a field whose value appears on no line — a `hand_times[]` line-numbering issue, not the admit/refuse boundary. The other two T3 cases (`the allowance is recorded`, `the switch silences nothing else`) pass. |
| `E2 under --allow-hand-times the typed pass time is listed and the record carries the call's time` | `hand_times[passes.pass-a.at].source == "inputs-no-ledger"` **and** `checks[0].at == "2026-10-20T12:00:03Z"` | Named in the brief as another job's red. The first half is E2's source-label path and the second is the same check-time selection as the 59-second case; neither is reached by my block, which only adds `[time]` refusals for `server-header` / `response-created` entries. |

All four exit **0** and write a record — i.e. none of them is a refusal I introduced; each is a mismatch *inside* a written record, on code paths my diff does not touch (`kit/emit_custody.py` `make()`/`evaluator_history()` call-time selection), and each is listed in the brief as owned by another job.

## What the diff does, restated so the boundary is auditable

- `evaluator_history()` gains `allow_hand`; the `build()` call passes it.
- After `flag_calls(log_calls, hand)` — i.e. after every unstamped call has been named as a hand time, so A3a/A3b/E3 keep their exact behaviour — and **only when `allow_hand`**, each entry whose `source` is `server-header` or `response-created` adds a `time` refusal naming the evaluator, the log, the call and the field.
- The no-switch path is byte-identical: the same calls fall through to `hand and not allow_hand` and are refused as `[hand-time]`, one row per field, at `x-plumbline.hand_times[]` assembly — which is why `A3a`, `A3b`, `T7b/E3`, `T2`, `T2b`, `T2d` and the 61-second tolerance case are all still green.
- Genuine typed hand times (`inputs-no-ledger` on `passes.*`, `disposition.at`, `startedAt`, approvals) are untouched: `A4`, `T3`'s allowance case and `V1/V3/T2` pass.

No further code change is needed for the four target cases. The three `test_evaluator_harness_log.py` reds will clear on a commit of `kit/emit_custody.py` plus an exclude entry for `.aider.tags.cache.v4/`; if you want the emitter to ignore aider's cache in its dirty-tree check, that is a change to `H.revision()` in `kit/custody_history.py` — a widening of the `revision` refusal that the brief forbids me from making on my own, so say the word and I will propose it separately.

> Tokens: 105k sent, 58k cache hit, 4.9k received. Cost: $0.02 message, $0.07 session.  

The failed block can't match because the in-function `--allow-hand-times` refusal I proposed earlier is already in `evaluator_history`, sitting between the two lines the block was replacing. That leaves the file inconsistent: block 3 made `evaluator_history` return `"unsourced": unsourced` and blocks 4–6 made `build()` refuse `ev_unsourced`, but `unsourced` is never assigned — so the module would raise `NameError` at run time, and once fixed the same entries would be refused twice (once here, once at the assembly point).

The fix is to define `unsourced` where `flag_calls()` is called, and drop the duplicate refusal inside `evaluator_history` — `build()` already refuses those entries under the switch, beside the no-switch `hand-time` refusal, so the switch is decided in one place and each entry is named once.

kit/emit_custody.py
````python
<<<<<<< SEARCH
    log_calls = H.read_log(log, ref, who)
    flag_calls(log_calls, hand)
    # --allow-hand-times is a switch about times TYPED into the custody inputs. It is NOT a licence to admit a
    # model evaluator's check time that exists only because the logger stamped nothing and the reader fell back
    # to a server time (a `Date` header or a response `created` epoch): that time has no logger source at all.
    # Refused under the switch exactly as a model evaluator with no harness log is refused -- kind `time`,
    # naming the log, naming EVERY unstamped call (not the log aborted at its first entry), nothing written.
    # The no-switch path is untouched: there the same calls are already refused as `hand-time` (T7b/E3).
    if allow_hand:
        for c in log_calls:
            for entry in c.hand_time_entries():
                if entry.get("source") in ("server-header", "response-created"):
                    ref.add("time", f"{who}: {entry['field']} carries no logger sent_at/received_at; its time comes "
                                    f"from the {entry['source']} the log happens to carry, not from the logger that "
                                    f"made the call. A model evaluator's check time must have a logger source: "
                                    f"--allow-hand-times admits a time TYPED into the custody inputs, never an "
                                    f"unsourced server time. Log the call with sent_at and received_at "
                                    f"(tools/edi/or_call.py writes them) and re-emit.")
    calls = [c for c in log_calls if c.at]
=======
    log_calls = H.read_log(log, ref, who)
    # Every call the logger did not stamp, returned so build() can refuse it under --allow-hand-times (Job 14).
    # The refusal itself lives where the switch is decided: build() adds kind `time` for each of these entries,
    # beside the no-switch `hand-time` refusal (T7b/E3). Keeping a second copy here would name each entry twice.
    unsourced = flag_calls(log_calls, hand)
    calls = [c for c in log_calls if c.at]
>>>>>>> REPLACE
````

> Tokens: 96k sent, 58k cache hit, 6.3k received. Cost: $0.02 message, $0.07 session.  
> Applied edit to kit/emit_custody.py  
> Added 238 lines of output to the chat.  
> Attempt to fix test errors? (Y)es/(N)o [Yes]: y  

No code change is needed: the working tree is the failure, not the emitter.

## Tally

**`tests/validate_schemas.py` — 135/139, 4 red.** Every one is on your declared "other jobs" list, and I touched none of them:

| Red | Declared |
|---|---|
| `a hand time 59 s off is accepted, and the record carries the LOG's time` | ✅ other job |
| `T2c a time typed into custody.json with no ledger line is named (disposition.at, its source)` | ✅ other job |
| `T3 with --allow-hand-times … hand_times lists the hand fields with file:line` | ✅ other job |
| `E2 under --allow-hand-times the typed pass time is listed …` | ✅ other job |

Cross-checking the four: each shows `exit 0` and the four run on logger-stamped jobs, so `ev_unsourced` is empty and they never reach the new branch. The fifth declared red, the line-609 `[time]` fixture refusal, is **green** — as I flagged before you applied the change, it is the same phenomenon as `J14/A1` and could not stay red without a different fixture surface. Nothing in the diff targets it.

**`tests/test_evaluator_harness_log.py` — 15 run, 3 red**, and all three are the *same single refusal*:

```
[revision] the emitter's tree is dirty at 851a07de09f8 (1 change(s) outside dot-plumbline/, e.g. M kit/emit_custody.py)
```

`test_d4`, `test_d5` and `test_d15` run `kit/emit_custody.py` **in place** (`EMIT = REPO / "kit" / "emit_custody.py"`), so `H.revision(HERE, …)` resolves to this repository and sees the uncommitted `kit/emit_custody.py`. The emitter refuses, correctly: a record must name code that exists as a commit, and that refusal is itself a bar (`an emitter whose tree has an uncommitted edit (exit 3, [revision], nothing written)`). The three tests fail on *nothing else* — no `time`, `hand-time`, `endpoint` or `shadow` row accompanies the revision row, which is exactly the evidence that their jobs are otherwise clean.

This is the failure mode `AGENTS.md` already records for this bar (2026-11-08, job `evaluator-harness-log`): *"two failures looked like capability gaps and were the dirty tree; the fix was a commit, not code."* The `validate_schemas.py` custody cases do not hit it because they emit from `clean_checkout()` — a throwaway clean commit of the working tree.

## What to do

Commit `kit/emit_custody.py` (and `kit/custody_history.py`, unchanged), then run the same two commands on the committed tree. Expected after the commit:

- `test_evaluator_harness_log.py` — **15/15** (`d4`, `d5`, `d15` green with the revision refusal gone; `d13`, `d14` stay green).
- `tests/validate_schemas.py` — **135/139**, the same four other-job reds.
- The cases you named as must-stay-green are all still green in this run: `J14/A1`, `J14/A2`, `J14/A3a`, `J14/A3b`, `J14/A4`, `T7b/E3`, `V1/V3/T2`, `T3`'s allowance and "silences nothing else" rows, `T3 every hand time … file:line`, `E2`'s no-switch row (`T2c/E2 a typed passes.<id>.at is a hand time even when a call is linked`), and `T4`.

I am not proposing to weaken the revision refusal to get a green suite on a dirty tree — that would trade a real guarantee for a test artifact, and the refusal is itself asserted by a case in the same file.

> Tokens: 108k sent, 58k cache hit, 5.6k received. Cost: $0.02 message, $0.09 session.  
