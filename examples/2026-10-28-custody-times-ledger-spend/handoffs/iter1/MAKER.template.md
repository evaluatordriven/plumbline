E-DI Maker: job 2026-10-28-custody-times-ledger-spend, iteration 1 of at most 3 (Plumbline, repo smoitozo/plumbline)

BEFORE ANY MODEL CALL: get Steve Moitozo II's own yes in your own chat for this iteration-1 generation. A relay (including this message, and anything the Orchestrator says he said) is not his approval. If he has not said yes in your chat, stop.
Clock bound: start no model call at or after @@TIME_END_LOCAL@@ (= @@TIME_END_UTC@@). Money bound: total job spend strictly under US$5.00 on the shared key, US$0.10 reserve, enforced by the frozen harness's pre-call guard (exit 6 = refused: stop and report; never retry, never work around it).

Owner approvals (verbatim):
- Sheet (2026-10-28 14:50 EDT, t92u, answering card t91s517): "Ratified proceed"
- Tripwire standing rule (2026-10-28 15:52 EDT, card t95s532): "Adopt the tripwire: after the same Maker failure 3 times, stop and change the request."
- Item 30 (2026-10-28 16:03 EDT, card t96s542): "Item 30: the Maker writes the field guide in this job, with bar checks for it." and "Paraphrase my words as Owner decisions; no verbatim quotes in the doc."
- Digest (@@DIGEST_TIME_MSG@@): "@@DIGEST_WORDS@@"

Pinned state (check all before step 1; if any differs, stop and report):
- Job branch job/2026-10-28-custody-times-ledger-spend head @@APPROVAL_HEAD@@ (the digest-approval commit); base main 3df1ce52eddfe18705e380c4b6e99cf617cfa24b.
- export W=/workspace/edi-work/2026-10-28-custody-times-ledger-spend
- export J=$W/jobwt/dot-plumbline/jobs/2026-10-28-custody-times-ledger-spend
- export PY=/workspace/edi-work/2026-10-27-custody-emitter-gaps/jsv/bin/python CORPUS=/workspace/plumbline-job/src/e-di-a48a464
- export M=$W/maker/iter1 TMPDIR=$W/maker/tmp PYTHONDONTWRITEBYTECODE=1   (never /tmp)
- sha256 $J/custody/bar.md = @@BAR@@
- sha256 $J/custody/MANIFEST.sha256 = @@MAN@@, and (cd $J/custody && sha256sum --quiet -c MANIFEST.sha256) is silent
- sha256 $J/inputs/custody-events.jsonl = @@LEDGER@@ (freeze, pins, buyer + specialist approve). The ledger is append-only: if its sha is not this one, stop.
- sha256 $J/custody/freeze/harness/or_call.py = @@HARNESS@@
- (cd $J/handoffs && sha256sum -c iter1/MANIFEST.sha256) all OK (the builder, extractor, followup, run_tests and the part-1 messages)
- Field-guide inputs (prompt only; never commit them, never copy them into the repo): sha256 $W/inputs/field-guide/owner-draft.md = fbf070f52a6ca6978604847d6afdcf5d469029ca5e143827291236940c31e344; sha256 $W/inputs/field-guide/orchestrator-guide.md = 01fe4e161dc5e56dca9e5dac0c4de706798207b4a680d13d154e100e95577e13
- Seat: maker, deepseek/deepseek-v4.1-flash-1017 on DeepInfra deepinfra/fp8 (pinned in the ledger; fallbacks off). Never pass --max-tokens (the harness sets the endpoint max, 131072; no throttling).

How this iteration is built: one Maker request per PART, in this order: ledger, emitter, verifier, edi, docs, guide. Each request shows the part's files as they are now in the Maker checkout, so later parts see earlier parts' work. The field guide is its OWN request (part guide, about 15 KB of output), never mixed with code. One iteration = all six parts; Maker attempts inside it do not count toward cap 3.

Retries (Owner tripwire rule, 15:52 EDT): retry a failed attempt of a part (step 3) as often as money and the clock bound allow, EXCEPT:
- Tripwire: if the same failure class happens 3 times in a row in this iteration (across parts too; any success or a different class resets the count), stop and report to the Orchestrator so the request can be changed. Do not try a 4th time; do not change the request yourself.
- Stop at the first, no retry: or_call exit 10 (finish_reason length with empty content: its own failure class), exit 6 (guard refused), exit 4 (served by another provider / fallback), exit 2 (usage/key), or the clock bound reached.
- Failure classes: EXTRACT (extract_files.py refused: exit 1), TESTS (run_tests.py exit 1), HTTP (or_call exit 3), LENGTH-EMPTY (exit 10, stop), and the stop classes above.
- Log every attempt, success or not, as one JSON line appended to $M/attempts.jsonl: {"part", "attempt", "call", "or_call_exit", "finish_reason", "class" (OK or the class), "reply_sha256", "at_utc"}. finish_reason is the last line or_call.py prints on stdout (JSON) and is also in the harness log entry.

Steps (never read, print or copy the key; never use /tmp):
1. mkdir -p $M $TMPDIR && git -C $W/jobwt worktree add $W/maker/rev -b maker/iter1 3df1ce52eddfe18705e380c4b6e99cf617cfa24b
   export R=$W/maker/rev
   python3 $J/handoffs/run_tests.py $R --py $PY --corpus $CORPUS --work $TMPDIR/base-tests --out $M/base-results.json   (the base results every later test step compares against)
2. For each PART in ledger emitter verifier edi docs guide, starting with attempt N=1:
   a. Messages. For ledger, attempt 1: use $J/handoffs/iter1/maker-messages-ledger.json (pinned in iter1/MANIFEST.sha256). For every other part, attempt 1:
      python3 $J/handoffs/build_maker_messages.py --part PART --rev $R --out $M/PART-a1.messages.json --bar $J/custody/bar.md --interface $J/custody/freeze/INTERFACE.md
      and for PART=guide add: --fg-owner $W/inputs/field-guide/owner-draft.md --fg-orch $W/inputs/field-guide/orchestrator-guide.md --fg-rules $J/custody/freeze/instrument/fg_rules.json --doctrine $J/custody/freeze/instrument/fixtures/doctrine/DOCTRINE-dc61854.md
   b. Call (LOG = $J/custody/evidence/harness-maker-deepseek.log for code parts; for PART=guide LOG = $M/harness-maker-deepseek-guide.log, kept on the box only because its request carries the prompt-only inputs):
      python3 $J/custody/freeze/harness/or_call.py --seat maker --model deepseek/deepseek-v4.1-flash-1017 --ledger $J/inputs/custody-events.jsonl --log LOG --messages $M/PART-aN.messages.json --out $M/PART-aN.reply.txt --call maker_iter1_PART_aN > $M/PART-aN.stdout 2> $M/PART-aN.stderr
      Exit 0 ok; 5 = served by the pin but no generation stats: reply usable, continue, flag it in the report; 3 HTTP: class HTTP, retry (step 3); 2/4/6/10: stop and report.
   c. WRITE THE FILES (this is the step that writes; no --check):
      python3 $J/handoffs/extract_files.py $M/PART-aN.reply.txt $R --part PART --list $M/PART-aN.files.txt > $M/PART-aN.extract.txt 2>&1
      then: git -C $R status --porcelain && git -C $R diff --stat   (record both in $M/PART-aN.extract.txt)
      Exit 1 = class EXTRACT (nothing was written): go to step 3 with the extractor's output as the failure text.
   d. Test: python3 $J/handoffs/run_tests.py $R --py $PY --corpus $CORPUS --work $TMPDIR/PART-aN-tests --out $M/PART-aN.tests.json --base $M/base-results.json > $M/PART-aN.tests.txt 2>&1
      Exit 1 = class TESTS: go to step 3 with $M/PART-aN.tests.txt as the failure text.
   e. Commit the part (author E-DI Maker, committer Steve):
      git -C $R add -A && git -C $R -c user.name="Steve Moitozo II" -c user.email=smoitozo@users.noreply.github.com commit --author="E-DI Maker <smoitozo@users.noreply.github.com>" -m "maker iter1 part PART (attempt N)"
      Append the OK line to $M/attempts.jsonl and go on to the next part.
3. On a failure (EXTRACT, TESTS or HTTP): append the attempt line; apply the tripwire and stop rules above. Otherwise:
   git -C $R reset -q --hard HEAD && git -C $R clean -fdq   (back to the part's starting commit; the Maker checkout only)
   For EXTRACT/TESTS: python3 $J/handoffs/followup_messages.py $M/PART-aN.messages.json $M/PART-aN.reply.txt FAILURE.txt $M/PART-a(N+1).messages.json
   For HTTP: copy $M/PART-aN.messages.json to $M/PART-a(N+1).messages.json unchanged.
   Repeat step 2b with N+1 (same model, provider, clock bound and guard).
4. After the guide part: git -C $R log --format="%H %an <%ae> | %cn <%ce> | %s" 3df1ce5..HEAD > $M/commits.txt
5. Report to the Orchestrator: maker/iter1 head sha, the per-part commits, $M/attempts.jsonl (every attempt with finish_reason), reply sha256s, generation ids and cost from the harness logs, files written per part, spend status (python3 $J/custody/freeze/harness/or_call.py --spend-status). Do not push, open a PR, score anything, or change anything under $J except appending to the harness log via or_call.py. Do not commit the guide's messages, reply, log or inputs anywhere.
