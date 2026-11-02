# Iteration 2, guide redo (part guide, attempt 2), for the E-DI Maker

Job 2026-10-28-custody-times-ledger-spend. Written by the Orchestrator 2026-10-29 (EDT). This addendum sits beside iter2/MAKER.md and changes ONLY the guide part. Everything in MAKER.md still holds (bounds, seat, guard, retries, tripwire, LOST rule, held-out controls, never /tmp, never read/print/copy the key) except where this file says otherwise. Pinned with add_iter1_guide.py in iter2/MANIFEST-guide-redo.sha256.

BEFORE THE MODEL CALL: get Steve Moitozo II's own yes in your own chat for this guide redo. A relay (including this file and anything the Orchestrator says he said) is not his approval. If he has not said yes in your chat, stop. Clock bound unchanged: start no model call at or after 2026-10-29 14:21 EDT (18:21Z).

## Why

Handoff defect (the Orchestrator's, not yours): build_maker_messages.py --part guide never shows the current guide, so guide a1 (9688a0c3) was asked to "keep all of" an iteration-1 guide it was never shown, and it wrote a new guide from the drafts. Owner decision (Steve, 2026-10-29 07:42 EDT, paraphrased): re-request the guide with the iteration-1 guide actually included, and keep the four code parts exactly as they are; keep all the passing parts.

## What stays (NO reset, nothing redone)

- Do NOT reset, rebase, amend or revert anything. Branch maker/custody-times-ledger-spend/iter2 stays as it is: ledger bc8e0fca, emitter b48a4dae, verifier 7c87a94f, docs 6ee2cfb0, and guide a1 9688a0c3 (kept as a reference commit; its guide text is superseded by this redo).
- No code part is redone or touched. The only file this redo may change is docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md (extract_files.py --part guide allows only that path). Part edi is not requested.
- The redo is ONE new commit on top of 9688a0c3.
- The input guide is the iteration-1 guide from 1cb410ba (sha256 7b8214a9ae5f579c232365623ae702e19cf77fb66f70a10e6ed4b2abf884e645), not the 9688a0c3 text. The new guide must keep all accepted iteration-1 content and still fix item G1 (the line-27 story) as FEEDBACK-guide.md says.

## Pinned state (check all before step 1; if any differs, stop and report)

- Everything in MAKER.md "Pinned state" except: the job branch head is the commit that adds this file (its parent is 1ae4cb781b0e707e5cedf42a6ed2a69dbcead3a3, and `git -C $W/jobwt diff --name-only 1ae4cb781b0e707e5cedf42a6ed2a69dbcead3a3 HEAD` lists only handoffs/iter2/GUIDE-REDO.md, handoffs/iter2/add_iter1_guide.py and handoffs/iter2/MANIFEST-guide-redo.sha256), and the $R and harness-log checks below replace MAKER.md's $R and harness-log lines.
- (cd $J/handoffs && sha256sum -c iter1/MANIFEST.sha256 && sha256sum -c iter2/MANIFEST.sha256 && sha256sum -c iter2/MANIFEST-guide-redo.sha256) all OK.
- $R: `git -C $R status --porcelain` is empty; `git -C $R branch --show-current` = maker/custody-times-ledger-spend/iter2; `git -C $R rev-parse HEAD` = 9688a0c3cd98942ba5786af4e5521155d80daad1.
- Code-part harness log is unchanged by this redo (no code call): `sha256sum $J/custody/evidence/harness-maker-deepseek.log` = b04be042d591c4c8e9187783720d04c9f3105193611d1b6cf727b43b1b27001e (4715505 bytes, 10 entries). Its iteration-1 prefix check, corrected (MAKER.md line 33's `head -c 2784309` is wrong): `(head -c 2784306 $J/custody/evidence/harness-maker-deepseek.log; printf '\n]\n') | sha256sum` = 3a58af1edaf200ddf02f3f5cdfc5151b175ee8a1906594f639ca7ed4d572c56d.
- Guide harness log before the call: `sha256sum $M/harness-maker-deepseek-guide.log` = a768fe49c1457ae564ebf294cebd6859db91ae1d2ae09800089b3a438dc89189 (322773 bytes, 1 entry: maker_iter2_guide_a1).
- `ls $M/guide-a2.*` lists nothing.

## Steps (exports as in MAKER.md: W, J, PY, CORPUS, M, TMPDIR=$W/maker/tmp, PYTHONDONTWRITEBYTECODE=1, R)

1. Messages (three commands; the third writes the messages that are sent). Exit non-zero from any = stop and report (not a model failure class).
   python3 $J/handoffs/build_maker_messages.py --part guide --rev $R --out $M/guide-a2.base.messages.json --bar $J/custody/bar.md --interface $J/custody/freeze/INTERFACE.md --fg-owner $W/inputs/field-guide/owner-draft.md --fg-orch $W/inputs/field-guide/orchestrator-guide.md --fg-rules $J/custody/freeze/instrument/fg_rules.json --doctrine $J/custody/freeze/instrument/fixtures/doctrine/DOCTRINE-dc61854.md
   python3 $J/handoffs/iter2/add_iter1_guide.py $M/guide-a2.base.messages.json $R $M/guide-a2.iter1.messages.json
   python3 $J/handoffs/iter2/add_feedback.py $M/guide-a2.iter1.messages.json $J/handoffs/iter2/FEEDBACK-guide.md $M/guide-a2.messages.json
   Expected sha256 (Orchestrator's scratch build, same inputs): guide-a2.base 065a7626222c782e74dd442f868543113899b7640b752554d6fd591ae2cdf0e2 (identical to guide-a1.base), guide-a2.iter1 6cb24578baff0c385714bb165b4ec5903558c0472f7b0cac89a3dc7685abd2e6, guide-a2.messages e3f955f074e463d9df15e05a8b45c7062330f821653b93d291ec7040a4c83d56. If any differs, stop and report.
2. Call: ONE call, MAKER.md step 2b with PART=guide, N=2, LOG=$M/harness-maker-deepseek-guide.log, call id maker_iter2_guide_a2. Same seat, model, pin and guard; never pass --max-tokens; no reasoning/effort limit (no throttling). Run detached exactly as in 2b and poll $M/guide-a2.or_call.exit. Exit rules as in 2b.
3. Extract: MAKER.md step 2c with PART=guide, N=2. Then `git -C $R status --porcelain` must list only docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md; anything else = stop and report (do not commit).
4. Tests: MAKER.md step 2d with PART=guide, N=2 (work dir $TMPDIR/iter2-guide-a2-tests).
5. Commit (author E-DI Maker, committer Steve), on top of 9688a0c3:
   git -C $R add -A && git -C $R -c user.name="Steve Moitozo II" -c user.email=smoitozo@users.noreply.github.com commit --author="E-DI Maker <smoitozo@users.noreply.github.com>" -m "maker iter2 part guide (attempt 2: redo with the iteration-1 guide shown)"
   Then: `git -C $R rev-parse HEAD~1` = 9688a0c3cd98942ba5786af4e5521155d80daad1 and `git -C $R diff --name-only 9688a0c3cd98942ba5786af4e5521155d80daad1 HEAD` = docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md only.
   Append the attempt line to $M/attempts.jsonl (format as MAKER.md; part guide, attempt 2, call maker_iter2_guide_a2).
6. On a failure (EXTRACT, TESTS, HTTP): MAKER.md step 3 applies, with these limits: the reset in step 3 (`git -C $R reset -q --hard HEAD && git -C $R clean -fdq`) only discards the uncommitted attempt and returns to 9688a0c3; never reset to any other commit. Attempt N+1 builds from $M/guide-aN.messages.json as in step 3. Tripwire, stop and LOST rules as in MAKER.md (the iteration-2 count so far: five OK lines, so it starts at zero).
7. After the commit: git -C $R log --format="%H %an <%ae> | %cn <%ce> | %s" 1cb410badbff504ca480b199ae4fe4f37caed893..HEAD > $M/commits.txt (now six lines).
8. Post-call checks:
   - Code-part harness log still sha256 b04be042d591c4c8e9187783720d04c9f3105193611d1b6cf727b43b1b27001e.
   - Guide harness log: the first entry is unchanged: `(head -c 322770 $M/harness-maker-deepseek-guide.log; printf '\n]\n') | sha256sum` = a768fe49c1457ae564ebf294cebd6859db91ae1d2ae09800089b3a438dc89189 (the log is one JSON array rewritten on each call, so the old content minus its closing "\n]\n" stays as the prefix), and the log now has 2 entries, the second with call maker_iter2_guide_a2.
   - Keep check (report, do not gate): `git -C $R diff 1cb410badbff504ca480b199ae4fe4f37caed893 HEAD -- docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md` and list every removed (`-`) line, with a one-line reason each if you know it (FEEDBACK-guide named it), else "not named".
9. Report to the Orchestrator: the new head sha (parent must be 9688a0c3), $M/commits.txt, the guide-a2 attempts.jsonl line(s), reply sha256, generation id and cost from the guide harness log, the three message sha256s from step 1, the tests result, the step-8 checks, and spend status (python3 $J/custody/freeze/harness/or_call.py --spend-status). Do not push, open a PR, score anything, or change anything under $J. Do not commit the guide's messages, reply, log or inputs anywhere.
