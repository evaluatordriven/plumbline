E-DI Maker: job 2026-10-28-custody-times-ledger-spend, iteration 2 of at most 3 (Plumbline, repo smoitozo/plumbline)

Filled by the Orchestrator 2026-10-29 EDT. Iteration 2 runs under the new clock bound below (Owner go-ahead "Resume", 2026-10-29 06:21 EDT).

BEFORE ANY MODEL CALL: get Steve Moitozo II's own yes in your own chat for this iteration-2 generation. A relay (including this message, and anything the Orchestrator says he said) is not his approval. If he has not said yes in your chat, stop.
Clock bound: start no model call at or after 2026-10-29 14:21 EDT (UTC-4) (= 2026-10-29T18:21:00Z). Arithmetic: Steve's resume go-ahead "Resume" at 2026-10-29 06:21 EDT (10:21Z; seconds not recorded), Grok Bot chat with Chief of Staff (no message id on file), rounded down to the minute = 06:21 EDT, + 8 h = 14:21 EDT (18:21Z). This replaces the iteration-1 bound (2026-10-29 00:34 EDT) by Owner decision (below); the bar's line-48 bound is changed only through the amendment: The new bound is filed as $J/AMENDMENT-1-clock-bound.md (sha256 34855cb83f7c0b9734a146ddaedf57fc98b8b27a54949f37ee7b1b48af05e32f), ledger line 7. Money bound: unchanged: total job spend strictly under US$5.00 on the shared key, US$0.10 reserve, enforced by the frozen harness's pre-call guard (exit 6 = refused: stop and report; never retry, never work around it). Spend before this iteration: US$0.295069 (guard, 2026-10-28 21:40 EDT).

Owner approvals (verbatim):
- Sheet (2026-10-28 14:50 EDT, t92u, answering card t91s517): "Ratified proceed"
- Tripwire standing rule (2026-10-28 15:52 EDT, card t95s532): "Adopt the tripwire: after the same Maker failure 3 times, stop and change the request."
- Item 30 (2026-10-28 16:03 EDT, card t96s542): "Item 30: the Maker writes the field guide in this job, with bar checks for it." and "Paraphrase my words as Owner decisions; no verbatim quotes in the doc."
- Digest (2026-10-28T17:39:00-04:00 = time received by Orchestrator; card answered earlier, exact time not visible (answered between 16:50 EDT, when the card was sent, and 17:39 EDT), card t96s548, Grok Bot chat with Chief of Staff, witnessed): "I approve bar digest 72e92dc7580e2447f19dfff66aaac02d8484157a6283dcfdda6c7bb2de7561c6 with manifest acdf764b32bab5e0fa4615590714c49162cbbaecddd00c03c6d8121b59b85d98 as Buyer and as Specialist adopting Owner sheet items 1-30 OWNER-APPROVAL.md 20d5ff99… + DOCTRINE.md v0.1 @ dc61854, including the 15:52 EDT tripwire, the harness finish_reason changes, item 30, the marker fix and the disclosed corrections; run iterations 1-3 within US$5.00 and by 2026-10-29 00:34 EDT."
- Keep accepted work (2026-10-28, t102u): "The maker should not throw away any work that was completed and acceptable"
- Pause and new clock bound (2026-10-28 21:40 EDT (= 2026-10-29T01:40Z), widget answer in the Grok Bot chat with Chief of Staff, witnessed by the Orchestrator; card id not on file): "Pause tonight. Resume iteration 2 tomorrow with a new 8-hour clock bound; same $5 budget and cap 3."
- Iteration-2 decisions (2026-10-29 06:20 EDT, card t104s583, Grok Bot chat with Chief of Staff, witnessed by the Orchestrator): "G2: use a real e-di checkout at a48a464 for Maker and Evaluator, disclosed as a deviation." and "Mismatches: the Maker makes the ledger accept --summary without --verdict and makes read_log's extra arguments optional; no bar amendment."
- Resume go-ahead (2026-10-29 06:21 EDT (= 10:21Z), Grok Bot chat with Chief of Staff, witnessed by the Orchestrator; no message id on file): "Resume"

Pinned state (check all before step 1; if any differs, stop and report):
- Job branch job/2026-10-28-custody-times-ledger-spend: its head's parent is 51b7cfa2709eece8338c8b05d54847259ee605b2 (amendment 1), and `git -C $W/jobwt diff --name-only 51b7cfa2709eece8338c8b05d54847259ee605b2 HEAD` lists only the iteration-2 handoff files (handoffs/iter2/MAKER.md, handoffs/iter2/EVALUATOR.md, handoffs/iter2/MANIFEST.sha256, handoffs/iter2/add_feedback.py, handoffs/iter2/FEEDBACK-{ledger,emitter,verifier,docs,guide}.md); base main 3df1ce52eddfe18705e380c4b6e99cf617cfa24b.
- export W=/workspace/edi-work/2026-10-28-custody-times-ledger-spend
- export J=$W/jobwt/dot-plumbline/jobs/2026-10-28-custody-times-ledger-spend
- export PY=/workspace/edi-work/2026-10-27-custody-emitter-gaps/jsv/bin/python
- export CORPUS=/workspace/plumbline-job/src/e-di-a48a464-git   (NEW in iteration 2, Owner decision 06:20 EDT above, disclosed as a deviation: a real git checkout of private repo smoitozo/e-di, detached at a48a4645aaa29947fdc17168d26c69c849941580; check `git -C $CORPUS rev-parse HEAD` = a48a4645aaa29947fdc17168d26c69c849941580 and `git -C $CORPUS status --porcelain` is empty. The iteration-1 folder /workspace/plumbline-job/src/e-di-a48a464 has the same files but no .git, so `tools/build_schemas.py --check` read the enclosing repo and reported DRIFT on base and subject alike. Never write to $CORPUS.)
- export M=$W/maker/iter2
- export TMPDIR=$W/maker/tmp
- export PYTHONDONTWRITEBYTECODE=1   (never /tmp)
- export R=$W/maker/rev
- sha256 $J/custody/bar.md = 72e92dc7580e2447f19dfff66aaac02d8484157a6283dcfdda6c7bb2de7561c6
- sha256 $J/custody/MANIFEST.sha256 = acdf764b32bab5e0fa4615590714c49162cbbaecddd00c03c6d8121b59b85d98, and (cd $J/custody && sha256sum --quiet -c MANIFEST.sha256) is silent
- sha256 $J/inputs/custody-events.jsonl = 506ee1be1c5a00016b095948b92a275155c583408cb62ad8d1548cc69a32a8df (7 lines: the 6 freeze/pin/approve lines, then amendment 1, hand-appended by the Orchestrator 2026-10-29T10:23:51Z; the first 6 lines are unchanged: `head -n 6 $J/inputs/custody-events.jsonl | sha256sum` = 3746e9e4bf6d9b830a217857757b6c068966a4f663c7e4ea596260c8aeab4b24). The ledger is append-only.
- sha256 $J/custody/freeze/harness/or_call.py = d2b320398a8de7a240de30cf9ea3ee54aa5fed8a2d1bc2a616b75fba9713d574
- (cd $J/handoffs && sha256sum -c iter1/MANIFEST.sha256 && sha256sum -c iter2/MANIFEST.sha256) all OK (builder, extractor, followup, run_tests; add_feedback.py and the five FEEDBACK files)
- The harness log is append-only: `head -c 2784309 $J/custody/evidence/harness-maker-deepseek.log | sha256sum` = 3a58af1edaf200ddf02f3f5cdfc5151b175ee8a1906594f639ca7ed4d572c56d (iteration-1 entries, untouched)
- sha256 $W/handoffs/iter2-base/base-results.json = 78fa9036ca269083eff05ec705c6ba836987d19c63c1d2207e188dbb806a42c0 (NEW in iteration 2: the base 3df1ce5 re-run by the Orchestrator with --corpus $CORPUS; every base run is rc 0, including `build_schemas --check`, which was rc 1 (DRIFT) under the iteration-1 corpus folder. Use this file, not $W/maker/iter1/base-results.json; do not re-run base tests)
- Maker checkout $R: `git -C $R status --porcelain` is empty and `git -C $R rev-parse HEAD` = 1cb410badbff504ca480b199ae4fe4f37caed893 (iteration-1 head: ledger 0f6ff3d, emitter 18ae8ee, verifier 8b1aa53, edi f3e846f, docs 6a82f2a, guide 1cb410b). `git -C $W/jobwt rev-parse --verify -q refs/heads/maker/custody-times-ledger-spend/iter2` prints nothing (the name is free).
- Field-guide inputs (prompt only; never commit them, never copy them into the repo): sha256 $W/inputs/field-guide/owner-draft.md = fbf070f52a6ca6978604847d6afdcf5d469029ca5e143827291236940c31e344; sha256 $W/inputs/field-guide/orchestrator-guide.md = 01fe4e161dc5e56dca9e5dac0c4de706798207b4a680d13d154e100e95577e13
- Seat: maker, deepseek/deepseek-v4.1-flash-1017 on DeepInfra deepinfra/fp8 (pinned in the ledger; fallbacks off). Never pass --max-tokens (the harness sets the endpoint max, 131072; no throttling) and no reasoning or effort limit (the harness never sends one; do not add one).
- Held-out controls: never read /workspace/job-controls/2026-10-28-custody-times-ledger-spend, and never put any control, planted case or Evaluator evidence in a Maker prompt. Build messages only with build_maker_messages.py and add_feedback.py (neither reads them) or followup_messages.py. Never read $W/eval.

How this iteration is built: iteration 2 starts from the iteration-1 head and KEEPS all of it (Owner rule t102u). Only five parts are re-requested, in this order: ledger, emitter, verifier, docs, guide. Part edi passed and is NOT requested again. Each request shows the part's files as they are now in $R (so it shows the iteration-1 work and every earlier iteration-2 part), plus that part's FEEDBACK file appended verbatim by add_feedback.py. The field guide stays its OWN request (part guide). One iteration = these five parts; Maker attempts inside it do not count toward cap 3. Any part whose attempt you cannot finish leaves its iteration-1 commit in place (never revert an iteration-1 commit).

Retries (Owner tripwire rule, 15:52 EDT): retry a failed attempt of a part (step 3) as often as money and the clock bound allow, EXCEPT:
- Tripwire: if the same failure class happens 3 times in a row in this iteration (across parts too; any success or a different class resets the count), stop and report to the Orchestrator so the request can be changed. Do not try a 4th time; do not change the request yourself.
- Stop at the first, no retry: or_call exit 10 (finish_reason length with empty content: its own failure class; stop and report so the Orchestrator can resize the request; do not resize it yourself), exit 6 (guard refused), exit 4 (served by another provider / fallback), exit 2 (usage/key), or the clock bound reached.
- LOST (no exit file, no reply, no harness-log entry, e.g. the turn was cut off): log a LOST line; it is not a failure class and does not count toward the tripwire. Re-send as the next attempt with byte-identical messages only after Steve's own yes in your chat. Two LOST in a row = stop and report.
- Failure classes: EXTRACT (extract_files.py refused: exit 1), TESTS (run_tests.py exit 1), HTTP (or_call exit 3), LENGTH-EMPTY (exit 10, stop), and the stop classes above.
- Log every attempt, success or not, as one JSON line appended to $M/attempts.jsonl: {"part", "attempt", "call", "or_call_exit", "finish_reason", "class" (OK, LOST or the class), "reply_sha256", "at_utc"}. finish_reason is the last line or_call.py prints on stdout (JSON) and is also in the harness log entry.

Steps (never read, print or copy the key; never use /tmp):
1. mkdir -p $M $TMPDIR && git -C $R switch -c maker/custody-times-ledger-spend/iter2 1cb410badbff504ca480b199ae4fe4f37caed893
   (the iteration-1 branch maker/custody-times-ledger-spend/iter1 stays at 1cb410b, untouched)
2. For each PART in ledger emitter verifier docs guide, starting with attempt N=1:
   a. Messages, attempt 1 (two commands; the second writes the messages that are sent):
      python3 $J/handoffs/build_maker_messages.py --part PART --rev $R --out $M/PART-a1.base.messages.json --bar $J/custody/bar.md --interface $J/custody/freeze/INTERFACE.md
      and for PART=guide add: --fg-owner $W/inputs/field-guide/owner-draft.md --fg-orch $W/inputs/field-guide/orchestrator-guide.md --fg-rules $J/custody/freeze/instrument/fg_rules.json --doctrine $J/custody/freeze/instrument/fixtures/doctrine/DOCTRINE-dc61854.md
      python3 $J/handoffs/iter2/add_feedback.py $M/PART-a1.base.messages.json $J/handoffs/iter2/FEEDBACK-PART.md $M/PART-a1.messages.json
      Exit non-zero from either = stop and report (not a model failure class).
   b. Call, run DETACHED so a turn cut-off cannot kill it (LOG = $J/custody/evidence/harness-maker-deepseek.log for code parts; for PART=guide LOG = $M/harness-maker-deepseek-guide.log, kept on the box only because its request carries the prompt-only inputs):
      setsid nohup sh -c 'python3 $J/custody/freeze/harness/or_call.py --seat maker --model deepseek/deepseek-v4.1-flash-1017 --ledger $J/inputs/custody-events.jsonl --log LOG --messages $M/PART-aN.messages.json --out $M/PART-aN.reply.txt --call maker_iter2_PART_aN > $M/PART-aN.stdout 2> $M/PART-aN.stderr; echo $? > $M/PART-aN.or_call.exit' > /dev/null 2>&1 &
      Wait for $M/PART-aN.or_call.exit (poll the file; do not sleep in /tmp). Exit 0 ok; 5 = served by the pin but no generation stats: reply usable, continue, flag it in the report; 3 HTTP: class HTTP, retry (step 3); 2/4/6/10: stop and report.
   c. WRITE THE FILES (this is the step that writes; no --check):
      python3 $J/handoffs/extract_files.py $M/PART-aN.reply.txt $R --part PART --list $M/PART-aN.files.txt > $M/PART-aN.extract.txt 2>&1; echo $? > $M/PART-aN.extract.exit
      then: git -C $R status --porcelain && git -C $R diff --stat   (record both in $M/PART-aN.extract.txt)
      Exit 1 = class EXTRACT (nothing was written): go to step 3 with the extractor's output as the failure text.
   d. Test: python3 $J/handoffs/run_tests.py $R --py $PY --corpus $CORPUS --work $TMPDIR/iter2-PART-aN-tests --out $M/PART-aN.tests.json --base $W/handoffs/iter2-base/base-results.json > $M/PART-aN.tests.txt 2>&1; echo $? > $M/PART-aN.tests.exit
      Exit 1 = class TESTS: go to step 3 with $M/PART-aN.tests.txt as the failure text.
   e. Commit the part (author E-DI Maker, committer Steve):
      git -C $R add -A && git -C $R -c user.name="Steve Moitozo II" -c user.email=smoitozo@users.noreply.github.com commit --author="E-DI Maker <smoitozo@users.noreply.github.com>" -m "maker iter2 part PART (attempt N)"
      Append the OK line to $M/attempts.jsonl and go on to the next part.
3. On a failure (EXTRACT, TESTS or HTTP): append the attempt line; apply the tripwire and stop rules above. Otherwise:
   git -C $R reset -q --hard HEAD && git -C $R clean -fdq   (back to the part's starting commit, which keeps every earlier commit; the Maker checkout only)
   For EXTRACT/TESTS: write the failure text to $M/PART-aN.failure.txt, then python3 $J/handoffs/followup_messages.py $M/PART-aN.messages.json $M/PART-aN.reply.txt $M/PART-aN.failure.txt $M/PART-a(N+1).messages.json
   For HTTP: cp $M/PART-aN.messages.json $M/PART-a(N+1).messages.json   (unchanged)
   Repeat step 2b with N+1 (same model, provider, clock bound and guard).
4. After the guide part: git -C $R log --format="%H %an <%ae> | %cn <%ce> | %s" 1cb410badbff504ca480b199ae4fe4f37caed893..HEAD > $M/commits.txt
5. Report to the Orchestrator: the maker/custody-times-ledger-spend/iter2 head sha, the per-part commits, $M/attempts.jsonl (every attempt with finish_reason), reply sha256s, generation ids and cost from the harness logs, files written per part, spend status (python3 $J/custody/freeze/harness/or_call.py --spend-status). Do not push, open a PR, score anything, or change anything under $J except appending to the harness log via or_call.py. Do not commit the guide's messages, reply, log or inputs anywhere.
