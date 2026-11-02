# Handoff: iter2 Maker (generation 4) · job 2026-10-27-custody-emitter-gaps

To: **E-DI Maker bot** (Maker operator). From: Chief of Staff (Orchestrator). Authority: Steve Moitozo II, acting as
Buyer, 2026-10-28 07:52 EDT (11:52Z), answer to card `t65s389` in the Chief of Staff chat, verbatim: "As Buyer I amend
the bar to raise the cap from 3 to 4 generations, money cap and time bound unchanged. Draft the gen-4 Maker handoff
with the N1/N3/N6 findings." (AMENDMENT-5-cap.md, sha256 `9f9db9639a0997371846c49043fb20ca45b629a4d555047c387e7ce276bf022e`.)
Bar: `custody/bar.md` sha256 `3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b` (frozen, unchanged).

Why: iteration 1 ended with generation 3 accepted as Maker commit `7cc38f8`, and the Evaluator scored it FAIL on N1,
N3 and N6 (EVAL-ITER1-VERDICT.md). The cap is now 4, so **generation 4 is the last generation**. Its prompt carries the
files as they are at `7cc38f8` and the Evaluator's findings (redacted, from `custody/evidence/eval/iter1-b2/`).

The protocol is the one from generation 3 (handoffs/iter1-maker.md, sections 1–7 and "Generation 3"). The same
harness, model, pin, flags, whole-file protocol, extract_files.py, allow-list and accept rule apply. This sheet is
complete for generation 4, so where it differs from iter1-maker.md, this sheet wins. You are the **operator only**: you
send the frozen prompt through the frozen harness, have extract_files.py write what comes back byte for byte, test,
commit, push and report. You write no code and no prompt words (bar, "Operator rule"). Anything not covered: **stop
and report**.

## 0. Preconditions (check all; any NO → stop and report, send nothing)
- G0 Ledger: `sha256sum $JOB/inputs/custody-events.jsonl` =
  `00dbbff44774db0f441aa0c7f78687ced99e262af56f6a3a4c98a68e7139b5df`. Its second-to-last line is
  `"event": "amendment", "n": 5` (AMENDMENT-5, sha256 `9f9db963…022e`, cap 4), and its last line is
  `"event": "generation", "n": 4, "boundary": "open"` with `"prompt_sha256": "ef2cc81c037ba34471e3d3f7f1c188dc1b5a79ffdaa3e9cae5353759e5d4583c"`.
- G1 `/workspace/plumbline-pr` is clean on `job/2026-10-27-custody-emitter-gaps`. HEAD = origin = the commit that adds
  AMENDMENT-5 (parent `18943a0abec54a72086db64a4d2a0ba61619b820`). `git worktree list` shows no `$SCR`. The code at
  HEAD is the gen-3 Maker commit's code: `git -C "$REPO" merge-base --is-ancestor 7cc38f833f8f5eeceffcb405885adb05141f8c65 HEAD`
  exits 0, and `git -C "$REPO" diff --quiet 7cc38f833f8f5eeceffcb405885adb05141f8c65 HEAD -- kit tools docs tests` exits 0.
- G2 `sha256sum $JOB/custody/freeze/harness/or_call.py` = `55e8981c1b75a30aef551ac0810b0891b7d41df8d32878db9710650d7ba06b38`;
  `(cd $JOB && sha256sum --quiet -c handoffs/iter1/MANIFEST.sha256)` passes; `(cd $JOB/custody && sha256sum --quiet -c MANIFEST.sha256)` passes.
- G3 Prompt: `sha256sum $JOB/handoffs/iter2/maker-messages-gen4.json` =
  `ef2cc81c037ba34471e3d3f7f1c188dc1b5a79ffdaa3e9cae5353759e5d4583c` (rebuild:
  `python3 $JOB/handoffs/build_maker_messages_gen4.py --repo /workspace/plumbline-pr --out /tmp/check4.json && cmp /tmp/check4.json $JOB/handoffs/iter2/maker-messages-gen4.json`).
- G4 `$LOG` holds exactly 10 entries (`maker_iter1_call1..4`, `maker_iter1_gen2_call1..4`, `maker_iter1_gen3_call1..2`).
  Append to it; never rewrite it. `python3 $JOB/handoffs/test_extract_files.py` ends `OK`.
- G5 Key file `/workspace/.openrouter-key` exists. **Never** `cat`, print, copy or commit it; the harness reads it by path.
- G6 Clock: it is before **11:05 EDT (15:05Z)** 2026-10-28 (section 6).

## 1. Fixed names
```bash
REPO=/workspace/plumbline-pr
JOB=$REPO/dot-plumbline/jobs/2026-10-27-custody-emitter-gaps
H=$JOB/custody/freeze/harness/or_call.py
EV=$JOB/custody/evidence
IT=$EV/maker/iter2-gen4                  # gen-4 call files; the iter1 folders are not touched
LOG=$EV/harness-maker-deepseek.log       # the ONE Maker log of the job (append-only, written by or_call.py)
LEDGER=$JOB/inputs/custody-events.jsonl
SCR=/workspace/edi-maker-iter2           # scratch worktree, outside the repo dir
X=$JOB/handoffs/extract_files.py
mkdir -p "$IT"
```
Do not read `/workspace/next-job-controls` or `/workspace/next-job-draft` (held-out controls and fixtures). The
prompt contains none of them.

## 2. Spend check before (P6)
```bash
python3 "$H" --check-key > "$EV/key-usage-maker-iter2-gen4-before.json"   # once, before call 1
```

## 3. Call k (k = 1..4)
Calls are `maker_iter2_gen4_call$k`. Call 1 sends the prompt unchanged:
`k=1; cp "$JOB/handoffs/iter2/maker-messages-gen4.json" "$IT/call-1.messages.json"`.
```bash
python3 "$H" --seat maker --ledger "$LEDGER" --model deepseek/deepseek-v4.1-flash-1017 \
  --log "$LOG" --call "maker_iter2_gen4_call$k" --messages "$IT/call-$k.messages.json" \
  --out "$IT/call-$k.reply.txt" --temperature 0 --max-tokens 131072 --gen-tries 12 --gen-wait 20 \
  > "$IT/call-$k.or_call.stdout" 2> "$IT/call-$k.or_call.stderr"; echo $? > "$IT/call-$k.or_call.exit"
```
Send no reasoning or effort parameter (the harness has none). Do not kill a running call. The pin is DeepInfra
`deepinfra/fp8` (ledger `pin` event, seat `maker`).
or_call exit: `0` ok → step 4. `5` (served by the pin, generation reply missing) → the reply is written; continue to
step 4 but report it. `3` (HTTP/transport error) → re-send the **same** messages file once as call k+1; a second `3`
→ stop and report. `4` (REFUSED: wrong provider or fallback) or `1`/`2` (ledger or usage error) → **stop and report**;
do not retry.

## 4. Write files exactly as returned, test, commit
```bash
git -C "$REPO" worktree add --detach "$SCR" HEAD
python3 "$X" "$IT/call-$k.reply.txt" "$SCR" --list "$IT/call-$k.files.txt" > "$IT/call-$k.extract.txt" 2>&1
echo $? > "$IT/call-$k.extract.exit"
git -C "$SCR" add -A && git -C "$SCR" status --short > "$IT/call-$k.changed.txt"
git -C "$SCR" diff --cached > "$IT/call-$k.written.diff"        # record of what was written (evidence only; never applied)
GIT_AUTHOR_NAME="E-DI Maker" GIT_AUTHOR_EMAIL="e-di-maker@users.noreply.github.com" \
  git -C "$SCR" -c user.name="Steve Moitozo II" -c user.email="smoitozo@users.noreply.github.com" \
  commit -q -m "iter2 gen4: Maker files from maker_iter2_gen4_call$k, written verbatim by extract_files.py (deepseek/deepseek-v4.1-flash-1017 via deepinfra/fp8)"
cd "$SCR" && /tmp/jsv/bin/python tests/validate_schemas.py > "$IT/call-$k.test.txt" 2>&1; echo $? > "$IT/call-$k.test.exit"
```
- Only `extract_files.py` writes the Maker's files. Do not edit, merge, complete, re-indent or re-encode them, and do
  not add or strip newlines. It writes all files or none.
- **Accepted** means all of the following:
  - extract exit 0;
  - every path in `changed.txt` is one of `kit/emit_custody.py kit/custody_history.py kit/custody_ledger.py
    tools/pack_stranger_bundle.py docs/custody-emission.md` or under `tests/fixtures/custody/`;
  - `changed.txt` is not empty;
  - test exit 0 with `ALL … CASES BEHAVED AS DESIGNED` (112 at the base, or more if fixtures were added), and none failing.
  If accepted → step 5.
- **Not accepted:** if extract exits non-zero, use `{ echo "step: extract_files.py"; cat "$IT/call-$k.extract.txt"; }`.
  If the tests fail, use `{ echo "step: tests/validate_schemas.py"; cat "$IT/call-$k.test.txt"; }`. If `changed.txt`
  is empty, use `step: changed-paths` + `"no file changed"`. If a path is outside the allow-list, use
  `{ echo "step: changed-paths"; cat "$IT/call-$k.changed.txt"; }`. Write whichever applies to `$IT/call-$k.failure.txt`.
  Then remove the scratch tree and send it back, if the clock allows (section 6):
  ```bash
  git -C "$REPO" worktree remove --force "$SCR"
  python3 "$JOB/handoffs/followup_messages.py" "$IT/call-$k.messages.json" "$IT/call-$k.reply.txt" \
    "$IT/call-$k.failure.txt" "$IT/call-$((k+1)).messages.json"
  k=$((k+1))   # then step 3 with this messages file (do NOT cp the original again)
  ```
- **Stop rule:** after 4 calls with no accepted result, or when section 6 forbids the next call, generation 4 has
  failed. Stop and report. Generation 4 is the last generation (cap 4, AMENDMENT-5); there is no generation 5.

## 5. Land on the job branch, evidence, push
```bash
SHA=$(git -C "$SCR" rev-parse HEAD)
git -C "$REPO" merge --ff-only "$SHA"            # job branch now carries the verbatim Maker commit
git -C "$REPO" worktree remove --force "$SCR"
python3 "$H" --check-key > "$EV/key-usage-maker-iter2-gen4-after.json"   # at least 2 min after the last call
grep -rlF -f /workspace/.openrouter-key "$JOB"; echo "key-scan rc=$? (must be 1)"   # rc 0 → STOP, do not commit
git -C "$REPO" add "$JOB/custody/evidence"
GIT_AUTHOR_NAME="E-DI Maker" GIT_AUTHOR_EMAIL="e-di-maker@users.noreply.github.com" \
  git -C "$REPO" -c user.name="Steve Moitozo II" -c user.email="smoitozo@users.noreply.github.com" \
  commit -q -m "iter2 gen4: Maker harness log, call files, extract/test output, key usage before/after"
git -C "$REPO" push origin job/2026-10-27-custody-emitter-gaps
```
On a failed generation, still commit and push the evidence (same commands without the merge), then report.
No PR, no merge to main, no tags. Do not run S1, the controls, n6_batch or any evaluator step.

## 6. Budget and time
- **Money.** Each follow-up carries the previous reply (whole files), so the prompt grows by up to ~35k tokens per
  call. Call 1's prompt is about 38k tokens. The worst case per call is about 131072 × $0.294/M + 200k × $0.098/M ≈
  **$0.06**. Ceilings: **$0.25** per call (`total_cost` in the generation reply) and **$1.00** for generation 4. Either
  exceeded → stop and report. Maker spend so far is $0.146370 (gens 1–3), and key usage was $0.16043365 after
  iteration 1's evaluation. The job cap is unchanged: < US$10.
- **Time.** The bound ends **2026-10-28 13:15 EDT (17:15Z)** (AMENDMENT-3, unchanged by AMENDMENT-5). The Orchestrator
  needs 45 min to close, so the evaluation must end by **12:30 EDT (16:30Z)**. The Evaluator must start by
  **12:10 EDT (16:10Z)**, so step 5 must be pushed and reported by about 12:05 EDT. Maker calls have taken 5–26 min
  each; allow about 5 min more for extract, tests and commit.
  - **Normal cutoff: do not start any call after 11:05 EDT (15:05Z).** At 11:05, a 26-min call plus 5 min ends by
    11:36, which still leaves time for one follow-up.
  - **Exception, last call only:** after 11:05, you may start a call only if it is the only call still needed: the
    previous call failed, and you will make no further call whatever this one returns. Its hard cutoff is
    **11:30 EDT (15:30Z)**: 12:10 − 5 (evidence commit, push and report) − 5 (extract, tests, commit) − 26 (longest
    call seen) = 11:34, less a 4-min margin. Never start a call after 11:30 EDT.
  - When you cannot start the next call under these rules, generation 4 has failed: commit and push the evidence and
    report.
  - If a call is still running at 12:05 EDT (16:05Z), do not kill it. Report that it is running.
  Start as soon as you are dispatched; do not wait for a cutoff.

## 7. Report back to the Orchestrator (plain text)
1. Maker commit sha (`$SHA`) and evidence commit sha; pushed yes/no (`git ls-remote origin job/2026-10-27-custody-emitter-gaps`).
2. Per call: call id, or_call exit, `served_by`, generation id, `total_cost`, `tokens_prompt` / `tokens_completion`
   (from the generation reply in the log), `sent_at` / `received_at`; extract / changed paths / test result (last line).
3. Paths: `$LOG` (entry count), `$IT/`, both key-usage files; key usage before → after (delta vs summed `total_cost`).
4. Any stop condition hit, with the error text verbatim. Never include the key.
