# Handoff: iter3 Maker (generation 5) · job 2026-10-27-custody-emitter-gaps

> AMENDMENT-6 applied; Steve's words and the ledger sha filled by `AMENDMENT-6-apply.sh`. Dispatch only after the apply
> commit is on origin (G1).
> **No job work in `/tmp`** (Steve's standing rule, 2026-10-28): every scratch, venv, temp and rebuild path is under
> `/workspace/edi-work/2026-10-27-custody-emitter-gaps/`.

To: **E-DI Maker bot** (Maker operator). From: Chief of Staff (Orchestrator). Authority: Steve Moitozo II, acting as
Buyer, 2026-10-28T13:32:00Z, Chief of Staff chat, card t73s419, verbatim: "As Buyer I amend the cap to 3 E-DI iterations, with Maker attempts limited only by budget; money cap and time bound unchanged. Run iteration 3 on the N3 finding." (AMENDMENT-6-cap.md: the cap is 3 E-DI iterations,
and the Maker's turn has no call-count limit within its budget).
Bar: `custody/bar.md` sha256 `3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b` (frozen, unchanged).

**Why this generation.** Iteration 2 (generation 4, Maker commit `73863fb`) was scored FAIL on **N3 only**
(EVAL-ITER2-VERDICT.md, batch 3). Every other dimension passed, including N6 (CONFORMS). Generation 5 is iteration 3,
the **last E-DI iteration**. Its prompt carries:
- the files as they are at `73863fb`;
- the two inputs of the repository fixture `tests/fixtures/custody/job-rejected`;
- the Evaluator's findings, from `custody/evidence/eval/iter2-b3/`.

**The N3 finding in plain terms.** The one failing run is the repository's own synthetic fixture
`tests/fixtures/custody/job-rejected`. Its ledger holds only a `pin` event. The bar's frozen-at time, both approval
times and the disposition time exist only as hand-entered values in its `inputs/custody.json`. The record cites that
file as their source, and N3 accepts only a ledger or harness-log line.

**Protocol.** It is generation 4's (handoffs/iter2-maker.md): the same harness, model, pin, flags, whole-file protocol,
extract_files.py, allow-list and accept rule. There are two changes:
- **No call-count limit.** You may keep calling within the money and time rules of section 6.
- **No `/tmp`.** Scratch, venv and temp paths move to `/workspace/edi-work/…`.

This sheet is complete for generation 5; where it differs from iter2-maker.md, this sheet wins.

**Your role.** You are the **operator only**: you send the frozen prompt through the frozen harness, have
extract_files.py write what comes back byte for byte, test, commit, push and report. You write no code and no prompt
words (bar, "Operator rule"). Anything not covered here: **stop and report**.

## 0. Preconditions (check all; any NO → stop and report, send nothing)
- **G0 Ledger.**
  - `sha256sum $JOB/inputs/custody-events.jsonl` = `23d5f98bba659aa43376697075b28705b18ce31081d142600740d35916b7a161`.
  - Its second-to-last line is `"event": "amendment", "n": 6` (AMENDMENT-6, cap 3 E-DI iterations).
  - Its last line is `"event": "generation", "n": 5, "boundary": "open"` with
    `"prompt_sha256": "d188cb80871fa959c43af2cde5588cc4ab8319eba00606ca212878f3662b0caa"`.
- **G1 Repo.**
  - `/workspace/plumbline-pr` is clean on `job/2026-10-27-custody-emitter-gaps`.
  - HEAD = origin = the commit made by `AMENDMENT-6-apply.sh` (subject starts
    `job 2026-10-27-custody-emitter-gaps: AMENDMENT-6 applied`).
  - `git worktree list` shows no `$SCR`.
  - The code at HEAD is the gen-4 Maker commit's code: both of these exit 0:
    - `git -C "$REPO" merge-base --is-ancestor 73863fb00c72239de0f0c2def4f68d1c6dfd902b HEAD`
    - `git -C "$REPO" diff --quiet 73863fb00c72239de0f0c2def4f68d1c6dfd902b HEAD -- kit tools docs tests`
- **G2 Frozen files.** All three must hold:
  - `sha256sum $JOB/custody/freeze/harness/or_call.py` = `55e8981c1b75a30aef551ac0810b0891b7d41df8d32878db9710650d7ba06b38`;
  - `(cd $JOB && sha256sum --quiet -c handoffs/iter1/MANIFEST.sha256)` passes;
  - `(cd $JOB/custody && sha256sum --quiet -c MANIFEST.sha256)` passes.
- **G3 Prompt.** `sha256sum $JOB/handoffs/iter3/maker-messages-gen5.json` =
  `d188cb80871fa959c43af2cde5588cc4ab8319eba00606ca212878f3662b0caa`. Rebuild and compare:
  `python3 $JOB/handoffs/build_maker_messages_gen5.py --repo /workspace/plumbline-pr --out $W/check5.json && cmp $W/check5.json $JOB/handoffs/iter3/maker-messages-gen5.json`.
- **G4 Log and extractor.**
  - `$LOG` holds exactly 13 entries: `maker_iter1_call1..4`, `maker_iter1_gen2_call1..4`, `maker_iter1_gen3_call1..2`,
    and `maker_iter2_gen4_call1`, `_call2`, `_call4` (gen 4's call 3 was lost in the reboot and has no entry).
    Count them with `grep -o '"call": "maker_[a-z0-9_]*"' "$LOG" | sort -u | wc -l`. Append to the log; never rewrite it.
  - `python3 $JOB/handoffs/test_extract_files.py` ends `OK`.
- **G5 Key.** The key file `/workspace/.openrouter-key` exists. **Never** `cat`, print, copy or commit it; the harness
  reads it by path.
- **G6 Clock.** It is before **11:05 EDT (15:05Z)** 2026-10-28 (section 6).
- **G7 Environment outside the repo.** A reboot at ~08:36 EDT wiped it once. Check all three:
  - `readlink -f /Users/jarbis/Jarbis-PARAD/5_Devspace/edi` prints `/workspace/plumbline-job/src/e-di-a48a464`.
  - `python3 -c 'import json,hashlib;p=json.load(open("/workspace/plumbline-pr/tools/pin.json"));b=[f for f,h in p["files"].items() if hashlib.sha256(open(p["corpus"]+"/"+f,"rb").read()).hexdigest()!=h];print("pin-ok" if not b else b)'`
    prints `pin-ok`.
  - `$W/jsv/bin/python -c 'import jsonschema, sys; print(sys.version.split()[0])'` prints `3.13.5`. This is the test
    venv: jsonschema 4.26.0, built with uv.
  If any of these is missing or wrong, stop and report. Do not recreate it yourself.

## 1. Fixed names
```bash
REPO=/workspace/plumbline-pr
JOB=$REPO/dot-plumbline/jobs/2026-10-27-custody-emitter-gaps
H=$JOB/custody/freeze/harness/or_call.py
EV=$JOB/custody/evidence
IT=$EV/maker/iter3-gen5                  # gen-5 call files; earlier folders are not touched
LOG=$EV/harness-maker-deepseek.log       # the ONE Maker log of the job (append-only, written by or_call.py)
LEDGER=$JOB/inputs/custody-events.jsonl
W=/workspace/edi-work/2026-10-27-custody-emitter-gaps   # job scratch root (never /tmp)
SCR=$W/maker-iter3-gen5                  # scratch worktree, outside the repo dir
PY=$W/jsv/bin/python                     # test venv (G7)
X=$JOB/handoffs/extract_files.py
export TMPDIR=$W/tmp-maker-gen5          # temp files land here, not /tmp
mkdir -p "$IT" "$TMPDIR"
```
Do not read `/workspace/next-job-controls` or `/workspace/next-job-draft` (held-out controls and fixtures). The
prompt contains none of them.

## 2. Spend check before (P6)
```bash
python3 "$H" --check-key > "$EV/key-usage-maker-iter3-gen5-before.json"   # once, before call 1
```

## 3. Call k (k = 1, 2, …; no count limit, section 6 governs)
Calls are named `maker_iter3_gen5_call$k`. Call 1 sends the prompt unchanged:
`k=1; cp "$JOB/handoffs/iter3/maker-messages-gen5.json" "$IT/call-1.messages.json"`.
Before **every** call, apply the start rules of section 6 and write the check to `$IT/call-$k.precheck.txt`. Record the
clock, Σ `total_cost` so far, and `wc -c` of the messages file.
```bash
python3 "$H" --seat maker --ledger "$LEDGER" --model deepseek/deepseek-v4.1-flash-1017 \
  --log "$LOG" --call "maker_iter3_gen5_call$k" --messages "$IT/call-$k.messages.json" \
  --out "$IT/call-$k.reply.txt" --temperature 0 --max-tokens 131072 --gen-tries 12 --gen-wait 20 \
  > "$IT/call-$k.or_call.stdout" 2> "$IT/call-$k.or_call.stderr"; echo $? > "$IT/call-$k.or_call.exit"
```
Send no reasoning or effort parameter (the harness has none). Do not kill a running call. The pin is DeepInfra
`deepinfra/fp8` (the ledger `pin` event for seat `maker`).

What to do on each or_call exit code:
- **`0`** (ok): go to step 4.
- **`5`** (served by the pin, generation reply missing): the reply is written. Continue to step 4, but report it.
- **`3`** (HTTP or transport error): re-send the **same** messages file as call k+1. Two `3`s in a row: stop and report.
- **`4`** (REFUSED: wrong provider or fallback), or **`1`** / **`2`** (ledger or usage error): **stop and report**.
  Do not retry.

**Lost call** (the box restarts or the process dies with no exit file and no log entry for the call):
- Write `$IT/call-$k.lost.txt` with the approximate send time, the cause and the messages sha256. Fabricate nothing.
- Re-send the same messages file as call k+1, if section 6 allows.

## 4. Write files exactly as returned, test, commit
```bash
git -C "$REPO" worktree add --detach "$SCR" HEAD
python3 "$X" "$IT/call-$k.reply.txt" "$SCR" --list "$IT/call-$k.files.txt" > "$IT/call-$k.extract.txt" 2>&1
echo $? > "$IT/call-$k.extract.exit"
git -C "$SCR" add -A && git -C "$SCR" status --short > "$IT/call-$k.changed.txt"
git -C "$SCR" diff --cached > "$IT/call-$k.written.diff"        # record of what was written (evidence only; never applied)
GIT_AUTHOR_NAME="E-DI Maker" GIT_AUTHOR_EMAIL="e-di-maker@users.noreply.github.com" \
  git -C "$SCR" -c user.name="Steve Moitozo II" -c user.email="smoitozo@users.noreply.github.com" \
  commit -q -m "iter3 gen5: Maker files from maker_iter3_gen5_call$k, written verbatim by extract_files.py (deepseek/deepseek-v4.1-flash-1017 via deepinfra/fp8)"
( cd "$SCR" && "$PY" tests/validate_schemas.py ) > "$IT/call-$k.test.txt" 2>&1; echo $? > "$IT/call-$k.test.exit"
```
- Only `extract_files.py` writes the Maker's files. Do not edit, merge, complete, re-indent or re-encode them, and do
  not add or strip newlines. It writes all files or none.
- **Accepted** means all of these hold:
  - extract exit 0;
  - `changed.txt` is not empty, and every path in it is one of `kit/emit_custody.py kit/custody_history.py
    kit/custody_ledger.py tools/pack_stranger_bundle.py docs/custody-emission.md` or is under `tests/fixtures/custody/`;
  - test exit 0 with `ALL … CASES BEHAVED AS DESIGNED` (112 at the base, or more if fixtures were added) and none
    failing.
  If accepted, go to step 5.
- **Not accepted.** Write the matching failure text to `$IT/call-$k.failure.txt`:
  - extract exit non-zero: `{ echo "step: extract_files.py"; cat "$IT/call-$k.extract.txt"; }`
  - tests failed: `{ echo "step: tests/validate_schemas.py"; cat "$IT/call-$k.test.txt"; }`
  - `changed.txt` empty: `step: changed-paths` + `"no file changed"`
  - a path outside the allow-list: `{ echo "step: changed-paths"; cat "$IT/call-$k.changed.txt"; }`

  Then remove the scratch tree and send the failure back, if section 6 allows:
  ```bash
  git -C "$REPO" worktree remove --force "$SCR"
  python3 "$JOB/handoffs/followup_messages.py" "$IT/call-$k.messages.json" "$IT/call-$k.reply.txt" \
    "$IT/call-$k.failure.txt" "$IT/call-$((k+1)).messages.json"
  k=$((k+1))   # then step 3 with this messages file (do NOT cp the original again)
  ```
- **Stop rule.** Generation 5 has failed when section 6 forbids the next call and nothing has been accepted. Stop,
  commit and push the evidence, and report. Generation 5 is the last generation (iteration 3 of 3, AMENDMENT-6).

## 5. Land on the job branch, evidence, push
```bash
SHA=$(git -C "$SCR" rev-parse HEAD)
git -C "$REPO" merge --ff-only "$SHA"            # job branch now carries the verbatim Maker commit
git -C "$REPO" worktree remove --force "$SCR"
python3 "$H" --check-key > "$EV/key-usage-maker-iter3-gen5-after.json"   # at least 2 min after the last call (F5)
grep -rlF -f /workspace/.openrouter-key "$JOB"; echo "key-scan rc=$? (must be 1)"   # rc 0 → STOP, do not commit
git -C "$REPO" add "$JOB/custody/evidence"
GIT_AUTHOR_NAME="E-DI Maker" GIT_AUTHOR_EMAIL="e-di-maker@users.noreply.github.com" \
  git -C "$REPO" -c user.name="Steve Moitozo II" -c user.email="smoitozo@users.noreply.github.com" \
  commit -q -m "iter3 gen5: Maker harness log, call files, extract/test output, key usage before/after"
git -C "$REPO" push origin job/2026-10-27-custody-emitter-gaps
```
If generation 5 fails, still commit and push the evidence: use the same commands without the merge, then report.
No PR, no merge to main, no tags. Do not run S1, the controls, n6_batch or any evaluator step.

## 6. Budget and time: the start rules for every call
**Prices.** The `deepinfra/fp8` endpoint read $0.14/M prompt tokens and $0.42/M completion tokens at 2026-10-28
09:23 EDT. Context is 1,048,576 tokens and max completion is 131,072.
- Call 1's prompt is about 175 KB, roughly 45k tokens.
- Each follow-up carries every previous reply (whole files) plus the failure text, so it grows by about 35k tokens per
  call. The worst case adds 131k.
- The worst case for one call with a prompt of P tokens is 131072 × $0.42/M + P × $0.14/M. That is about $0.06 at
  45k tokens and about $0.14 at 600k.

**Start rules.** Start call k only if all of these hold. If any fails, do not start it; generation 5 has failed
unless a call was already accepted.
1. **Generation spend.** Σ `total_cost` of the gen-5 calls so far, from the generation replies in `$LOG`, is
   **≤ $0.85**. This keeps the generation under **$1.00** even if the next call is a worst case. If a call's generation
   reply is null, count that call at $0.15.
2. **Per call.** No gen-5 call so far has a `total_cost` over **$0.25**. If one has, stop and report.
3. **Prompt size.** `wc -c "$IT/call-$k.messages.json"` is **≤ 2,400,000 bytes** (about 600k tokens). This keeps the
   prompt plus 131,072 output tokens inside the context, and a worst-case call near $0.14.
4. **Clock.** See the time rules below.

The job cap is unchanged: < US$10. Spend so far is key usage $0.253801479, about $0.2545 once batch 3's last call posts.

**Time.** The bound ends **2026-10-28 13:15 EDT (17:15Z)** (AMENDMENT-3). The Orchestrator needs 45 min to close, so
the evaluation (batch 4) must end by **12:30 EDT (16:30Z)**. The Evaluator must start by **12:10 EDT (16:10Z)**, so
step 5 must be pushed and reported by about 12:05 EDT. Maker calls have taken 5–26 min each; allow about 5 min more
for extract, tests and commit.
- **Normal cutoff: no call starts after 11:05 EDT (15:05Z).**
- **Exception, final call only.** After 11:05, you may start a call only if:
  - the previous call failed (or was lost);
  - you will make no further call, whatever this one returns;
  - the money rules above hold.

  Its hard cutoff is **11:30 EDT (15:30Z)**: 12:10 − 5 (evidence commit, push and report) − 5 (extract, tests,
  commit) − 26 (the longest call seen) = 11:34, less a 4-min margin. **Never start a call after 11:30 EDT.**
- If a call is still running at 12:05 EDT (16:05Z), do not kill it. Report that it is running.

Start as soon as you are dispatched; do not wait for a cutoff.

## 7. Report back to the Orchestrator (plain text)
1. Maker commit sha (`$SHA`) and evidence commit sha. Pushed yes/no (`git ls-remote origin job/2026-10-27-custody-emitter-gaps`).
2. For each call:
   - call id, or_call exit, `served_by`, generation id;
   - `total_cost`, `tokens_prompt` / `tokens_completion` (from the generation reply in the log);
   - `sent_at` / `received_at`;
   - messages bytes;
   - extract result, changed paths, and the test result (last line).
   Also give the running Σ `total_cost`.
3. Paths: `$LOG` (entry count), `$IT/`, both key-usage files. Give key usage before → after, and the delta against
   the summed `total_cost`.
4. Any stop condition hit, with the error text verbatim. Never include the key.
