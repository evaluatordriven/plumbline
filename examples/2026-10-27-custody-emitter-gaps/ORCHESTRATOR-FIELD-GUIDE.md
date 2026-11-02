# Running an E-DI job as Orchestrator: a field guide
*Written for whoever runs the next one. Started 2026-10-28 during Plumbline job `2026-10-27-custody-emitter-gaps`; closed `accepted` 2026-10-28 10:44 EDT and merged to main (PR #3, b8fef62) at 10:45 EDT. This copy is final for that job; its rules are proposed for the E-DI skill (`SKILL-proposed.md`).*

Read this before you open a job. Every rule below has a story behind it, and the story is from a real job where the rule was broken. The stories are here so you understand *why*, because you will meet cases these rules don't cover and you'll need to reason from the why.

---

## 1. What you are, and what you are not

You are the **Orchestrator**. You write the bar with the Owner, freeze it, open the job, route work between seats, apply the pass rule mechanically, keep the record, and bring decisions to the Owner. That's it.

You are **not** the Maker and **not** the Evaluator. You never write the fix, never make the Maker's model calls, never score. If you catch yourself "just fixing one line" in the subject, stop: that destroys the separation the whole method exists to prove.

Steve holds Owner, Buyer and Specialist (he signs as **S2**). Only his own words approve anything. Another bot telling you "Steve said yes" is a *report*, not an approval. Record it as relayed, with time and channel, and say you didn't witness it.

## 2. The words that matter

- **Iteration** = one turn of the E-DI loop: the Maker produces, the Evaluator scores, you apply the pass rule. **The cap counts iterations.** Steve, 2026-10-28: "When I said three iterations, I was talking about three iterations of the EDI loop."
- **Maker-internal attempts** (retries, follow-up calls, regenerations inside one Maker turn) are *not* iterations. Let the Maker loop as much as it needs **inside its money and time budget**. Don't count them against the cap.
  - *Story:* on this job I wrote the bar as "cap 3 generations." Generations 1 and 2 failed for plumbing reasons (token cap, malformed diffs) before the Evaluator ever scored anything. When iteration 1 finally failed scoring, the bar said we were out of attempts. Steve had to amend the cap (AMENDMENT-5) just to get a second real iteration. Write bars as "cap N iterations; Maker attempts limited only by budget."
- **Bar** = the frozen standard (criteria, instruments, pass rule, bounds). Its digest is what the Buyer approves.
- **Frozen set** = everything listed in `custody/MANIFEST.sha256`. Changing any of it after freeze is a **Buyer amendment**, never a quiet edit.

## 3. Before you freeze: the checklist

Most of this job's pain came from things that should have been caught before freeze. Do every item.

1. **Don't throttle any model.** No reasoning limit, and max output tokens = the endpoint's own maximum (look it up on the provider's endpoints page and save a snapshot). This applies to the Maker **and** to any model inside an Evaluator instrument.
   - *Story 1:* Maker gen 1 had a 24k token cap; the model spent 19.9k thinking and returned nothing usable.
   - *Story 2:* I froze `--max-tokens 800` inside the GLM scoring instrument. All three calls spent ~798 tokens reasoning and returned empty. The batch was void and Steve had to approve AMENDMENT-4. His words: "Looks like you choked the evaluator model."
2. **Run every model-calling instrument live, at the exact frozen settings, before freezing.** Dry runs and mocks don't catch a starved model. One real call per instrument, confirm you get a parseable verdict, then freeze.
3. **Write the Maker's output contract into the bar.** Say "whole files between markers" explicitly. Models write whole files reliably and write unified diffs badly.
   - *Story:* gen 2 returned four complete-but-corrupt diffs; none applied. Gen 3 used whole files via `extract_files.py` and passed the operator's accept rule on call 2. The bar said "patch," which left me interpreting (D6). Don't leave the Owner's intent to interpretation.
4. **State the time bound as a clock time**, e.g. "ends 2026-10-28 13:15 EDT," not "under 10 hours." Then derive every cutoff from it in the handoffs and show the arithmetic.
   - *Story:* I mixed up a call-start cutoff (02:15) with the job's end (which I said was 03:15, but strictly from open was 05:44). Nobody could tell which number was the real limit.
5. **Plan the approval checkpoints against the clock.** Every Maker or Evaluator model run needs Steve's yes in that bot's chat. If he's asleep, the clock keeps running.
   - *Story:* gen 3 waited overnight for a yes, and the job blew its time bound before the call started (AMENDMENT-3). Either schedule runs when Steve is around, or get the yeses up front for a defined sequence.
6. **Enforce spend in the harness, not just in prose.** Ceilings written in a handoff are procedural; nothing stops a runaway call. Put per-call and per-batch caps in the tool (follow-up F8).

## 4. Running the loop

**Maker turn**
- Hand off with exact preconditions: branch head sha, ledger sha, prompt file sha, harness sha, log entry count, clock cutoff. If any doesn't match, the Maker stops. That's a feature.
- Give the Maker the Evaluator's findings from the previous iteration: instrument reasons and the model judge's reply. **Redact anything from held-out controls.** The Maker must never see them.
- When the Maker reports, **verify it yourself** (or have your worker do it): re-extract the files from the raw model reply and confirm they're byte-identical to the commit, check paths against the allow-list, re-run the tests, reconcile spend with key usage. Trust, then verify.

- **When a Maker attempt breaks the tests, run the same tests at the unchanged base commit, in the same environment, before you blame anyone.** If the base passes, the break is in the Maker's files. If the base fails too, it's your setup.
  - *Story:* in gen 5, call 2's files crashed the suite with a `FileNotFoundError`. It was the first run under the new `TMPDIR`, so the environment was a real suspect. The Maker ran one extra test at the unchanged base `b934b48` in a throwaway worktree, with the same `TMPDIR` and venv: 112 of 112 passed. That one run settled it. The crash was the Maker's, the failure text went back to the model, and call 4 was accepted. Record such a base run as a deviation, outside the repo, so it's on file but can't be mistaken for Maker evidence.
- **"The tests pass" tells you the files fit the harness. It doesn't tell you *how* the finding was fixed. Read the diff and say what kind of fix it is.** Don't judge it (that's the Evaluator's job), but write it down plainly in the generation close line so the Owner isn't surprised.
  - *Story:* iteration 2 failed N3 because a repository fixture's custody times were hand-typed, with no ledger line behind them. In gen 5 the Maker added four ledger events to that fixture, carrying the same hand-typed times, and relaxed the emitter's cross-checks so the new events would agree. The emitter still doesn't refuse or flag hand-typed times. The allow-list included `tests/fixtures/custody/`, so this was a legal move, and the easiest one. Whether that meets the bar is the Evaluator's call, but the question "is a fixture-only fix acceptable?" should have been settled in the prompt.
  - Do instead: the allow-list is part of the spec. If the fix has to be in the code, leave fixtures off the allow-list, or say in the prompt that changing a fixture to make a finding go away doesn't count. Decide this with the Owner before the Maker turn, not after.
- **Ask the Maker to quote the Owner's go-ahead word for word in its report.** You need that quote for the close line and the job record, and you didn't see it, because it happened in the Maker's own chat.
  - *Story:* gen 5's report covered calls, costs and deviations in detail, but not Steve's yes. The close line could only say the go-ahead belongs in the Maker's chat and that the Orchestrator didn't witness it.
- **A template copied forward carries its old words. Diff each filled handoff against the previous batch's handoff before you dispatch it.**
  - *Story:* the batch-4 template still said "The batch-3 dir `$B` does not exist yet" in precondition E6. It was harmless, but a newcomer Evaluator could have checked the wrong folder. The filled copy fixes it.

**Evaluator turn**
- Give the Evaluator a **writable** copy of the controls and check integrity with the manifest before and after.
  - *Story:* I made the copy read-only to "protect" it. The scoring harness copies fixtures with their file permissions, so the subject's emitter couldn't write its output, and five checks failed for environmental reasons. Batch 1 was void.
- The batch seal (BATCH-MANIFEST) must not list itself.
- Read key usage at least 2–3 minutes after the last call, or the last call's cost won't show yet.
- When results look weird, **ask "is this the subject or my setup?"** before you apply the pass rule. A void batch is recorded as void with its causes; it is not a score.
- Even in a void batch, look for real signal. In batch 1, N1 and N3 failed on a fixture the setup bug didn't touch. That was a true result and it held in batch 2.
- **The control order rotates per batch, so read which call is the subject from the batch's own `order`. Don't assume a position.**
  - *Story:* in batch 4, `n6/stdout.json` ran in the order [subject, G-c1, G-p1], so the subject was `n6-b4-1`, not `-2` as in an earlier batch. The verdict, the evidence copy and the close inputs all take the subject's call name from `items[].id == "subject"`.
- **To check that the subject prompt was sent verbatim, rebuild it exactly as the harness does, numbered listing included.** A plain file dump will not match byte for byte, even when nothing is wrong.
- **Read key usage well after the last call.** Batch 4 waited 156 s after the last call, and the after-read reconciled to the cent (the fix for F5's under-count).

**When the box itself fails mid-run**
- Your computer can reboot under you. On this job it rebooted at ~08:36 EDT during Maker gen 4, call 3: the call died with no exit file and no log entry, `/tmp` (including the test venv) was wiped, the scratch worktree vanished, and 44 committed files in an unrelated job folder showed as deleted.
- What to do: (1) don't panic or re-run anything yet; (2) check what's actually damaged against git (`git status`, compare HEAD to origin, re-verify ledger and harness shas); (3) restore committed files from git, never from memory; (4) record the lost call as *lost*, with what you know (start time, likely billed cost from key usage) and never invent a log entry for it; (5) resume from the last good state.
- **Never put job work in `/tmp`.** `/tmp` is wiped on reboot. Steve, 2026-10-28: "don't put your work in /tmp."
  - *Story:* our handoffs built the test venv at `/tmp/jsv`, the Maker ran its calls from wrapper scripts in `/tmp`, and follow-up rebuild checks wrote to `/tmp/check*.json`. The reboot took all of it, and the Maker had to rebuild before it could resume.
  - Do instead: put venvs, wrapper scripts, scratch worktrees and any intermediate files under a job folder in `/workspace` (e.g. `/workspace/edi-work/<job_id>/`), which survives reboots. Write that path into every handoff's "Names" section.
  - Commit evidence to the job branch as soon as each step finishes, so a crash can't take it. Uncommitted gen-4 evidence was one reboot away from being lost.
- **Moving your paths out of `/tmp` is not enough; move the tools' temp files too. Set `TMPDIR`.** Python's `tempfile`, `mktemp` and most test suites write to `/tmp` on their own, whatever paths your handoff names.
  - *Story:* after the reboot, the gen-5 handoff moved every named path to `/workspace/edi-work/…`, but nobody told the tests where to put *their* temp files. The Maker caught it during its pre-checks: it created `$W/tmp-maker-gen5`, exported `TMPDIR` to it, and only then ran anything. One test script alone left 32 temp folders there. Without that, they'd all have landed in `/tmp` again.
  - Do instead: every handoff's "Names" section exports `TMPDIR` to a folder under the job's work root, one per seat and per run (`tmp-maker-gen5`, `tmp-eval-b4`). At close, list and clean those folders, and the old `/tmp` leftovers too (gen 4's `/tmp/jsv`, wrapper scripts and `check4.json` were still sitting there during gen 5).
- **Every environment dependency outside the repo goes into the handoff preconditions, with a script to restore it.** If the tests need it and git doesn't hold it, a reboot can take it.
  - *Story:* the test suite reads the E-DI corpus through `tools/pin.json`, at the Mac path `/Users/jarbis/Jarbis-PARAD/5_Devspace/edi`. On this box that path is a root-owned symlink to `/workspace/plumbline-job/src/e-di-a48a464`. No handoff mentioned it. The reboot wiped it, and the tests could not run until the Maker found the cause and recreated it with `sudo ln -s`, after checking the corpus files against the hashes in `tools/pin.json`.
  - Do instead: at job open, list everything the tests and harness touch outside the repo (symlinks, corpora, venvs, CLIs, credentials *by path only*). Write a precondition for each that checks it (e.g. `readlink -f` gives the expected target and the `tools/pin.json` file hashes match). Keep a committed restore script that rebuilds it and then verifies it.
- **Record exact tool and venv versions at job open, so a rebuild can match them.**
  - *Story:* the test venv was rebuilt after the reboot (Python 3.13.5, jsonschema 4.26.0, attrs 26.1.0, jsonschema-specifications 2025.9.1, referencing 0.37.0, rpds-py 2026.9.1). Nothing written at job open said what the original held, so "same as before" could only be assumed, not checked. The identical test output was the only evidence that the rebuild matched.
  - Do instead: at job open, commit an environment record to the job folder: `python --version`, `uv pip freeze` (or `pip freeze`) for each venv, `uv --version`, `git --version`, and the shas of any external corpus. Rebuild from that record with pinned versions (`uv pip install pkg==x.y.z …`), then diff the new freeze against it. Put that diff in the handoff as a precondition.

**Applying the pass rule**
- Mechanical: every dimension must pass. Report what failed, quote the instrument's reason in plain words, and say what it means for the work.
- At the cap, the state is `needs_owner`. Bring Steve the options (amend, reject) with your recommendation and the clock arithmetic for each.

## 5. Records

- The job record lives **in the product repo** beside the code: `dot-plumbline/jobs/<job_id>/` (Doctrine rule 12). Not in scratch.
- The ledger (`inputs/custody-events.jsonl`) is append-only. Every amendment, generation open/close and evaluation verdict gets a line; record the ledger sha after each append and pin it in the next handoff. The ledger tool can't yet write generation, evaluation or amendment lines, so we hand-appended them (F1: add commands).
- Post-freeze amendments go **beside** the frozen set (job root), never inside `custody/`, so the bar digest stays valid and P5 still passes. Each amendment quotes Steve's words verbatim, with time, channel and whether you witnessed it.
- Model-judge logs: commit them **redacted** (requests *and* replies, since replies can quote control code), with the full log's sha alongside. The full log stays outside the repo.
- The OpenRouter key is referenced by path only. Scan for it before every push.
- Git identity: author "E-DI Maker" for Maker commits, committer Steve Moitozo II with his noreply address.

**Preparing the close (a script, not a run)**
- Close is `plumbline_job.py close` from **base main @ ff350e3, a clean checkout** with `PLUMBLINE_EXPECT_REVISION` set (bar: Emitter), not from the branch under test. It needs a corpus at the pin (`/workspace/plumbline-job/src/e-di-a48a464`) and a §5 **run file** per iteration. It writes the §5 record, the packet facts, a run-log row and then the custody record. The run file must live outside `inputs/`, because close copies it in (it would be copied onto itself).
- `custody_ledger.py dispose` stamps **the time the tool runs**, not when Steve decided. To record his decision time, write it into `inputs/custody.json` and a matching `dispose` line by hand. The emitter refuses if the two disagree. Disclose the hand line.
- The ff350e3 emitter has **no pass-through for extra `x-plumbline` fields**, so the bar's spend line and the emitter-limitation note can't go inside the record. Put them in a sidecar (`custody/record.x-plumbline-addendum.json`, which carries the record's sha) and in `separationGaps`. Tell Steve before the close, not after.
- Custody CL1-16: **a script evaluator's script must not be the instrument's runner.** The first dry run failed CL1-16 when `run_instrument.sh` was both S1 and `instrument.runner`. Do instead: the runner is the written procedure that ran the evaluators (here the batch-4 Evaluator handoff), as in the custody-v1-emission precedent.
- Held-out control case files are digested from their **absolute path** on the box. The record carries their sha only; the content never enters the repo. Disclose that a stranger can't re-read them.
- Dry-run the whole close, commit included, on a scratch branch worktree under `/workspace/edi-work`. Test both `given` and `declined`, and check that the pre-checks refuse bad input. Then remove the worktree and delete the branch. The dry run is what found CL1-16.

**After the close and the merge**
- **Take every time floor from the log itself, never from a summary of it.** The close script refuses a decision time earlier than the last check, so that floor has to be the last check's *real* finish.
  - *Story:* I first set the floor to 14:23:43Z from my batch notes. The dry-run record showed G-p1 at 14:24:26Z, which is later than my "last" time. The harness log said n6-b4-3 was received at 14:24:43Z and its generation reply fetched at 14:24:48Z. I moved the floor to 14:24:49Z, the last time in the log, rounded up. With the wrong floor, a decision time in that one minute would have dated Steve's yes before the check it was approving.
- **Have the close ready before the Owner decides, so his yes turns into a record in seconds.** Steve gave disposition at 10:44:00 EDT (card t78s440). `CLOSE-apply.sh` committed the close (067c524) 28 seconds later: record `749b825b…`, check.py OK at CL1, P5(e) PASS. The PR was merged 57 seconds after that. Nothing was improvised at the moment that counted, because every surprise had already happened in the dry run.
- **After the merge, the job branch is finished. Later changes to the job record go on a new branch cut from the merge commit.**
  - *Story:* this guide's final sync came after PR #3 was merged. It went on `job-record/2026-10-27-custody-emitter-gaps-guide`, cut from main b8fef62, and touched only `ORCHESTRATOR-FIELD-GUIDE.md`. Adding commits to the merged job branch would have left them stranded off main.
- **A merge changes the next job's starting point. Re-read the pins before drafting.** After b8fef62, main's emitter is the *fixed* one (gap 1 closed). So the next job's own record can be written by main at the merge commit, and the "ff350e3 + producedAt limitation" disclosure is no longer needed. Check, don't copy, the previous sheet's pins.

## 6. Working with Steve

- He decides; you recommend. Lead with the answer, give your recommendation, and offer real options on a card. Show the clock math when time matters.
- When he gives a principle ("stop choking the model," "cap counts loop iterations"), apply it everywhere it fits, not just where he said it, and write it down here.
- Own your mistakes plainly. "You're right, I froze an 800-token cap" beats explaining.
- Push only on his authority, and cite the message.

## 7. This job's close: done
- [x] Iteration 1 (gen 3, batch 2; batch 1 void): FAIL on N1, N3 and N6 (EVAL-ITER1-VERDICT.md). Iteration 2 (gen 4, batch 3): FAIL on N3 only (EVAL-ITER2-VERDICT.md). Iteration 3 (gen 5, batch 4): PASS on N1–N8, terminal state `accepted` (EVAL-ITER3-VERDICT.md).
- [x] Owner disposition: given, 2026-10-28 10:44 EDT, card t78s440, verbatim: "As Owner I give disposition: accepted. Close job 2026-10-27-custody-emitter-gaps and write its CL1 custody record." Closed by `CLOSE-apply.sh` in commit 067c524. Ledger `708359c6…9bcb`. Merged to main by PR #3 as b8fef62 (10:45 EDT), at Steve's request.
- [x] Spend: US$0.303493375 in model calls, from key usage, reconciled per batch. Grok Bot's own spend can't be verified. Time: inside the 13:15 EDT bound, with about 2.5 h to spare.
- [x] This guide is in the job record (`ORCHESTRATOR-FIELD-GUIDE.md`). Final sync on branch `job-record/2026-10-27-custody-emitter-gaps-guide`, from b8fef62.
- [x] `/tmp` paths moved to `/workspace/edi-work/<job_id>/` in the iteration-3 handoffs, with `TMPDIR` exported there. The runbook version is in `SKILL-proposed.md`.
- [x] Cleanup 2026-10-28 ~10:49 EDT. Removed gen 4's `/tmp` leftovers: `/tmp/jsv` (3.0 MB venv), `/tmp/edi-gen4-{budget,call,write}.sh`, `/tmp/base-test.txt` and `/tmp/check4.json`. Removed the `$W/tmp-*` folders `tmp-amend6`, `tmp-eval-b3`, `tmp-eval-b4`, `tmp-maker-gen5` (39 MB, mostly test temp dirs), `tmp-orch-b4` and `tmp-orch-gen5`. Kept on purpose: the corpus symlink, the venv at `$W/jsv`, the batch dirs, the key file and the empty `$W/tmp`. Gen 5's dangling scratch commits are left to `git gc`; none is on a branch.
- [x] The E-DI skill update is drafted as `/workspace/edi-lessons/SKILL-proposed.md`, from sections 2–5. It is not applied; the Owner decides.

## 8. Carried to next jobs
- **Fixture-only fixes.** Is changing a fixture an acceptable fix for a finding about that fixture? Settle it in the bar and the allow-list before the Maker's first turn (section 4). For the doctrine-pointer job, the proposed answer is no: the allow-list is docs only.
- **The x-plumbline sidecar.** ff350e3 couldn't write spend or limitation notes into the record, so this job used `custody/record.x-plumbline-addendum.json`. Is a sidecar enough for P6 spend? Main @ b8fef62 still has no pass-through, so either adopt the sidecar as the rule or add a pass-through (with the emitter follow-up job).
- **Only the final iteration got a §5 record.** Iterations 1–2 live in EVAL-ITER1/2 and the ledger. Decide whether every iteration gets one.
- **Follow-up job (queued second):** make the emitter refuse or flag hand-entered times (the real N3), plus F1 (ledger commands for generation, evaluation, amendment and dispose-at-decision-time), F7 (fixture modes) and F8 (spend caps enforced in the harness).
