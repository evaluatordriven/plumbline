# Handoff — iter1 Maker (generation 1) · job 2026-10-27-custody-emitter-gaps

To: **E-DI Maker bot** (Maker operator). From: Chief of Staff (Orchestrator). Authority: Steve Moitozo II,
2026-10-27 18:06 EDT, "Proceed. Run the job"; 18:31 EDT, "Go with all four recommendations and start iteration 1"
(DECISIONS-2026-10-27.md). Bar: `custody/bar.md` sha256 `3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b` (frozen).

You are the **operator only**. The Maker is the model `deepseek/deepseek-v4.1-flash-1017`. You send the frozen prompt
through the frozen harness, apply what comes back **byte for byte**, run the test, commit, push and report. You write
no code, no prompt words and no fixes of your own; you never edit, complete, reorder or reformat a patch (bar,
"Operator rule"). Anything this sheet does not cover: **stop and report**, do not improvise.

## 0. Preconditions (check all; any NO → stop and report, send nothing)
- G0 **Generation boundary — done.** The Orchestrator hand-appended the generation-1 boundary line at
  2026-10-27T22:32:12Z (DECISIONS-2026-10-27.md D2). Check `sha256sum $JOB/inputs/custody-events.jsonl` =
  `2f5e9627a20b3a761328260c4d6ea70348d218c5d03e1948191be2529266ea18` and its last line has `"event": "generation", "n": 1`.
  Differs → stop and report.
- G1 `git -C /workspace/plumbline-pr status --short` is empty and `git -C /workspace/plumbline-pr rev-parse --abbrev-ref HEAD`
  is `job/2026-10-27-custody-emitter-gaps`.
- G2 Frozen harness intact: `sha256sum $JOB/custody/freeze/harness/or_call.py` =
  `55e8981c1b75a30aef551ac0810b0891b7d41df8d32878db9710650d7ba06b38`.
- G3 Prompt intact: `sha256sum $JOB/handoffs/iter1/maker-messages.json` =
  `fbe8215d84559a319bb288fc33bf29be53ab0455b0d2c3fcf7ed6639953b1bd2` (rebuildable: `python3 $JOB/handoffs/build_maker_messages.py --repo /workspace/plumbline-pr --out /tmp/check.json && cmp`).
- G4 Ledger has a `pin` event with `"seat": "maker"` (DeepInfra, `deepinfra/fp8`) and the log
  `$JOB/custody/evidence/harness-maker-deepseek.log` does not exist yet (or has no entries).
- G5 Key file `/workspace/.openrouter-key` exists. **Never** `cat`, print, copy or commit it; the harness reads it by path.

## 1. Fixed names
```bash
REPO=/workspace/plumbline-pr
JOB=$REPO/dot-plumbline/jobs/2026-10-27-custody-emitter-gaps
H=$JOB/custody/freeze/harness/or_call.py
EV=$JOB/custody/evidence                 # harness log + key-usage files (committed)
IT=$EV/maker/iter1                       # per-call messages, replies, patches, apply/test output (committed)
LOG=$EV/harness-maker-deepseek.log       # ONE log for every Maker call of the job (append-only, written by or_call.py)
LEDGER=$JOB/inputs/custody-events.jsonl
SCR=/workspace/edi-maker-iter1           # scratch worktree, outside the repo dir
mkdir -p "$IT"
```
Do not read `/workspace/next-job-controls` or `/workspace/next-job-draft` (held-out controls/fixtures). The prompt
contains none of them.

## 2. Spend check before (P6)
```bash
python3 "$H" --check-key > "$EV/key-usage-maker-iter1-before.json"   # read-only GET /api/v1/key; prints status/limit/usage only
```

## 3. Call k (k = 1, 2, … max 4 per generation)
Call 1 sends `$JOB/handoffs/iter1/maker-messages.json` unchanged (copy it to `$IT/call-1.messages.json`).
```bash
k=1; cp "$JOB/handoffs/iter1/maker-messages.json" "$IT/call-$k.messages.json"
python3 "$H" --seat maker --ledger "$LEDGER" --model deepseek/deepseek-v4.1-flash-1017 \
  --log "$LOG" --call "maker_iter1_call$k" --messages "$IT/call-$k.messages.json" \
  --out "$IT/call-$k.reply.txt" --temperature 0 --max-tokens 24000 \
  > "$IT/call-$k.or_call.stdout" 2> "$IT/call-$k.or_call.stderr"; echo $? > "$IT/call-$k.or_call.exit"
```
or_call exit: `0` ok → step 4. `5` (served by the pin, generation reply missing) → reply is written; continue to
step 4 but report it. `3` (HTTP/transport error, e.g. the 300 s timeout) → re-send the **same** messages file once as
call k+1; a second `3` → stop and report. `4` (REFUSED: wrong provider/fallback) or `1`/`2` (ledger/usage error) →
**stop and report**; do not retry.

## 4. Apply unchanged, test, commit (in a scratch worktree)
```bash
python3 "$JOB/handoffs/extract_patch.py" "$IT/call-$k.reply.txt" "$IT/call-$k.patch" > "$IT/call-$k.extract.txt" 2>&1
git -C "$REPO" worktree add --detach "$SCR" HEAD
cd "$SCR" && git apply --check "$IT/call-$k.patch" > "$IT/call-$k.apply.txt" 2>&1 && git apply "$IT/call-$k.patch" >> "$IT/call-$k.apply.txt" 2>&1
git -C "$SCR" status --short > "$IT/call-$k.changed.txt"   # must list only kit/, tools/, docs/, tests/fixtures/custody/ paths
git -C "$SCR" add -A && GIT_AUTHOR_NAME="E-DI Maker" GIT_AUTHOR_EMAIL="e-di-maker@users.noreply.github.com" \
  git -C "$SCR" -c user.name="Steve Moitozo II" -c user.email="smoitozo@users.noreply.github.com" \
  commit -q -m "iter1: Maker patch from maker_iter1_call$k, applied verbatim (deepseek/deepseek-v4.1-flash-1017 via deepinfra/fp8)"
cd "$SCR" && /tmp/jsv/bin/python tests/validate_schemas.py > "$IT/call-$k.test.txt" 2>&1; echo $? > "$IT/call-$k.test.exit"
```
- Use plain `git apply` only: no `--3way`, `--reject`, `--recount`, `-C`, whitespace options or hand edits.
- **Accepted** = extract exit 0, apply exit 0, only allowed paths changed, test exit 0 (last line
  `ALL 112 CASES BEHAVED AS DESIGNED`, or more cases if the patch added fixtures, with none failing). → step 5.
- **Not accepted** (no diff block / apply fails / a path outside `kit/emit_custody.py kit/custody_history.py
  kit/custody_ledger.py tools/pack_stranger_bundle.py docs/custody-emission.md tests/fixtures/custody/**` / test fails;
  custody_history.py is in scope per DECISIONS D3):
  record it, then remove the scratch tree (`git -C "$REPO" worktree remove --force "$SCR"`) and send it back:
  ```bash
  # FAILURE file = the failing step's output verbatim, headed by the step name, e.g.:
  { echo "step: git apply --check"; cat "$IT/call-$k.apply.txt"; } > "$IT/call-$k.failure.txt"   # or extract / changed-paths / tests/validate_schemas.py
  python3 "$JOB/handoffs/followup_messages.py" "$IT/call-$k.messages.json" "$IT/call-$k.reply.txt" \
    "$IT/call-$k.failure.txt" "$IT/call-$((k+1)).messages.json"
  k=$((k+1))   # then step 3 with this messages file (do NOT cp the original again)
  ```
  After 4 calls without an accepted patch: stop and report (generation 1 failed; the Orchestrator decides).

## 5. Land on the job branch, evidence, push
```bash
SHA=$(git -C "$SCR" rev-parse HEAD)
git -C "$REPO" merge --ff-only "$SHA"            # job branch now carries the verbatim patch commit
git -C "$REPO" worktree remove --force "$SCR"
python3 "$H" --check-key > "$EV/key-usage-maker-iter1-after.json"
grep -rlF -f /workspace/.openrouter-key "$JOB"; echo "key-scan rc=$? (must be 1)"   # rc 0 → STOP, do not commit
git -C "$REPO" add "$JOB/custody/evidence"
GIT_AUTHOR_NAME="E-DI Maker" GIT_AUTHOR_EMAIL="e-di-maker@users.noreply.github.com" \
  git -C "$REPO" -c user.name="Steve Moitozo II" -c user.email="smoitozo@users.noreply.github.com" \
  commit -q -m "iter1: Maker harness log, call files, apply/test output, key usage before/after"
git -C "$REPO" push origin job/2026-10-27-custody-emitter-gaps
```
No PR, no merge to main, no tags. Do not run S1, the controls, n6_batch or any evaluator step.

## 6. Budget
Price (ZDR snapshot): $0.098/M prompt, $0.294/M completion → one call ≈ 40k prompt + ≤24k completion ≈ **$0.01**.
Per-call ceiling **$0.25** (`total_cost` in the generation reply); generation-1 ceiling **$1.00** across all calls.
Either exceeded → stop and report. Job budget is < US$10 and < 10 h from the first Maker call (bar).

## 7. Report back to the Orchestrator (plain text)
1. Patch commit sha (`$SHA`) and evidence commit sha; pushed yes/no (`git ls-remote origin job/2026-10-27-custody-emitter-gaps`).
2. Per call: call id, or_call exit, `served_by`, generation id, `total_cost`, `tokens_prompt` / `tokens_completion`
   (from the generation reply in the log), sent_at / received_at; extract / apply / test result.
3. Paths: `$LOG`, `$IT/`, both key-usage files; key usage before → after (delta vs summed `total_cost`).
4. Any stop condition hit, verbatim error text. Never include the key.

---

# Generation 2 (supersedes the numbers above where they differ) — opened 2026-10-28T00:31:49Z (20:31:49 EDT)

Why: generation 1 failed (GEN1-FAILURE.md): `--max-tokens 24000` left only 4096 tokens after reasoning, so no diff
block came back. Steve, 20:30 EDT: "My instinct it to advise the Maker to stop choking the model. Let it work".
**No frozen file changes**: same harness (or_call.py `55e8981c…6b38`), same prompt (`fbe8215d…1bd2`), same apply
protocol. Only command flags change.

## Preconditions (replace G0, G1, G4)
- G0′ `sha256sum $JOB/inputs/custody-events.jsonl` = `359a2fa3a81e6dcd763eed77b664f41c023012b73e54911d8e748045046a5933`;
  its last line is `"event": "generation", "n": 2, "boundary": "open"`.
- G1′ `/workspace/plumbline-pr` clean on `job/2026-10-27-custody-emitter-gaps`, HEAD = the Orchestrator's gen-2 commit
  (it carries the gen-1 evidence) and equal to origin.
- G4′ `$LOG` holds exactly the 4 gen-1 entries (`maker_iter1_call1..4`); you append to it (never rewrite it).
- G2, G3, G5 unchanged.

## Names
```bash
IT=$EV/maker/iter1-gen2      # gen-2 call files (gen-1 files in $EV/maker/iter1 are not touched)
mkdir -p "$IT"
```
Calls are `maker_iter1_gen2_call$k`, k = 1..4; call 1 sends `$JOB/handoffs/iter1/maker-messages.json` unchanged.

## Call command (replaces step 3's)
```bash
python3 "$H" --check-key > "$EV/key-usage-maker-iter1-gen2-before.json"     # once, before call 1
python3 "$H" --seat maker --ledger "$LEDGER" --model deepseek/deepseek-v4.1-flash-1017 \
  --log "$LOG" --call "maker_iter1_gen2_call$k" --messages "$IT/call-$k.messages.json" \
  --out "$IT/call-$k.reply.txt" --temperature 0 --max-tokens 131072 --gen-tries 12 --gen-wait 20 \
  > "$IT/call-$k.or_call.stdout" 2> "$IT/call-$k.or_call.stderr"; echo $? > "$IT/call-$k.or_call.exit"
```
- `--max-tokens 131072` = the pinned endpoint's `max_completion_tokens` (OpenRouter
  `/api/v1/models/deepseek/deepseek-v4.1-flash-1017/endpoints`, tag `deepinfra/fp8`, read 2026-10-27 20:3x EDT;
  context 1,048,576, prompt ≤ ~50k tokens, so it fits). No reasoning or effort parameter is sent (the frozen harness
  has none; the model default — reasoning on, effort high — applies).
- `--gen-tries 12 --gen-wait 20`: waits up to ~3.7 min for `/api/v1/generation` (gen 1 gave up after ~25 s, 404).
- Expect long calls: gen 1 ran 6–10 min for 24k tokens (~40–60 tok/s); a call that uses the full 131k may run
  ~40–55 min. Do not kill a running call. or_call's 300 s is a socket-read timeout, not a total one; gen 1's calls
  outlived it because OpenRouter keeps the connection alive while the model works.
- Exit handling, steps 4–5 (apply verbatim in the scratch worktree, test, ff-merge, evidence commit, push), the
  allowed paths (incl. kit/custody_history.py, DECISIONS D3) and the report are as above, with `$IT` as set here and
  the after-read written to `$EV/key-usage-maker-iter1-gen2-after.json` **at least 2 min after the last call**
  (gen 1's counter lagged by one call).

## Budget and time (replace step 6)
Worst case per call ≈ 131072 × $0.294/M + 50k × $0.098/M ≈ **$0.044**; per-call ceiling $0.25; generation-2
ceiling $1.00. Job clock started at the first Maker call, 2026-10-27 19:44:48 EDT; the bar's limit is < 10 h. If
another call could not finish before **2026-10-28 03:15 EDT**, do not start it: stop and report.

---

# Generation 3 — whole files (supersedes Generation 2 and steps 3–4 above where they differ) — opened 2026-10-28T02:23:56Z (22:23:56 EDT 2026-10-27); reissued 2026-10-28 after AMENDMENT-3 (time bound)

**Reissue (AMENDMENT-3-time-bound.md, sha256 `f4babace8aa01666339c2411bdf9068db43c7c414ee3884f6e3bec1b085acb68`).**
Steve, as Buyer, relayed via the E-DI Maker bot at 06:21 EDT 2026-10-28: "A: amend the bar as Buyer to extend the
time bound so gen 3 can run, money cap unchanged." The time bound now ends 13:15 EDT (17:15Z), and no call may start
after **12:15 EDT (16:15Z)** on 2026-10-28. Only the ledger sha, the branch head and the cutoff changed below.

Why: generation 2 failed (GEN2-FAILURE.md). All 4 replies were complete diffs, and none applied. Steve, 22:20 EDT:
"Commit the gen-2 evidence, then run gen 3 with the model returning whole files that the Maker writes exactly as
returned" (DECISIONS D6). The harness (or_call.py `55e8981c…6b38`), the bar, and every MANIFEST-listed file are
unchanged. The changes are a new prompt (whole-file OUTPUT CONTRACT), extract_files.py in place of extract_patch.py +
`git apply`, and new followup wording.

## Preconditions (replace G0–G4; G5 unchanged)
- G0″ `sha256sum $JOB/inputs/custody-events.jsonl` = `7a1a212fa9175953629dbebeb89468788e1ca88b3244a80fda0541d771547202`;
  its second-to-last line is `"event": "generation", "n": 3, "boundary": "open"`, and its last line is
  `"event": "amendment", "n": 3` (AMENDMENT-3, sha256 `f4babace…cb68`).
- G1″ `/workspace/plumbline-pr` is clean on `job/2026-10-27-custody-emitter-gaps`. HEAD = origin = the commit that
  adds AMENDMENT-3 (parent `430b9c3e51659fee45a8f0f025a01bb26a63e608`). `git worktree list` shows no `$SCR`.
- G2″ `sha256sum $JOB/custody/freeze/harness/or_call.py` = `55e8981c1b75a30aef551ac0810b0891b7d41df8d32878db9710650d7ba06b38`, and
  `(cd $JOB && sha256sum --quiet -c handoffs/iter1/MANIFEST.sha256)` passes.
- G3″ Prompt: `sha256sum $JOB/handoffs/iter1/maker-messages-gen3.json` =
  `10193b5c0ca09d3194829268047584439a559397519aa28e1fb5177c2275bb57` (rebuild:
  `python3 $JOB/handoffs/build_maker_messages.py --repo /workspace/plumbline-pr --out /tmp/check.json && cmp /tmp/check.json $JOB/handoffs/iter1/maker-messages-gen3.json`).
- G4″ `$LOG` holds exactly 8 entries (`maker_iter1_call1..4`, `maker_iter1_gen2_call1..4`). Append to it; never
  rewrite it. `python3 $JOB/handoffs/test_extract_files.py` ends `OK`.

## Names
```bash
IT=$EV/maker/iter1-gen3      # gen-3 call files; gen-1/gen-2 folders are not touched
mkdir -p "$IT"
X=$JOB/handoffs/extract_files.py
```
Calls are `maker_iter1_gen3_call$k`, k = 1..4. Call 1 sends `$JOB/handoffs/iter1/maker-messages-gen3.json` unchanged:
`cp "$JOB/handoffs/iter1/maker-messages-gen3.json" "$IT/call-1.messages.json"`.

## Call (same flags as gen 2)
```bash
python3 "$H" --check-key > "$EV/key-usage-maker-iter1-gen3-before.json"     # once, before call 1
python3 "$H" --seat maker --ledger "$LEDGER" --model deepseek/deepseek-v4.1-flash-1017 \
  --log "$LOG" --call "maker_iter1_gen3_call$k" --messages "$IT/call-$k.messages.json" \
  --out "$IT/call-$k.reply.txt" --temperature 0 --max-tokens 131072 --gen-tries 12 --gen-wait 20 \
  > "$IT/call-$k.or_call.stdout" 2> "$IT/call-$k.or_call.stderr"; echo $? > "$IT/call-$k.or_call.exit"
```
Send no reasoning or effort parameter (the harness has none). or_call exit handling is the same as in step 3 above.
Do not kill a running call.

## Write files exactly as returned, test, commit (replaces step 4)
```bash
git -C "$REPO" worktree add --detach "$SCR" HEAD
python3 "$X" "$IT/call-$k.reply.txt" "$SCR" --list "$IT/call-$k.files.txt" > "$IT/call-$k.extract.txt" 2>&1
echo $? > "$IT/call-$k.extract.exit"
git -C "$SCR" add -A && git -C "$SCR" status --short > "$IT/call-$k.changed.txt"
git -C "$SCR" diff --cached > "$IT/call-$k.written.diff"        # record of what was written (evidence only; never applied)
GIT_AUTHOR_NAME="E-DI Maker" GIT_AUTHOR_EMAIL="e-di-maker@users.noreply.github.com" \
  git -C "$SCR" -c user.name="Steve Moitozo II" -c user.email="smoitozo@users.noreply.github.com" \
  commit -q -m "iter1 gen3: Maker files from maker_iter1_gen3_call$k, written verbatim by extract_files.py (deepseek/deepseek-v4.1-flash-1017 via deepinfra/fp8)"
cd "$SCR" && /tmp/jsv/bin/python tests/validate_schemas.py > "$IT/call-$k.test.txt" 2>&1; echo $? > "$IT/call-$k.test.exit"
```
- Only `extract_files.py` writes the Maker's files. Do not edit, merge, complete, re-indent or re-encode them, and do
  not add or strip newlines. It writes all files or none.
- **Accepted** means all of the following:
  - extract exit 0;
  - every path in `changed.txt` is one of `kit/emit_custody.py kit/custody_history.py kit/custody_ledger.py
    tools/pack_stranger_bundle.py docs/custody-emission.md` or under `tests/fixtures/custody/`;
  - `changed.txt` is not empty;
  - test exit 0 with `ALL … CASES BEHAVED AS DESIGNED`, and none failing.
  If accepted, go to step 5 (ff-merge, evidence, push) with `$IT` as set here. Name the after-read file
  `$EV/key-usage-maker-iter1-gen3-after.json`, and take it at least 2 min after the last call.
- **Not accepted:** if extract exits non-zero, use `{ echo "step: extract_files.py"; cat "$IT/call-$k.extract.txt"; }`.
  If the tests fail, use `{ echo "step: tests/validate_schemas.py"; cat "$IT/call-$k.test.txt"; }`. If
  `changed.txt` is empty, use `step: changed-paths` + `"no file changed"`. Write whichever applies to
  `$IT/call-$k.failure.txt`. Then remove the scratch tree (`git -C "$REPO" worktree remove --force "$SCR"`), run
  `followup_messages.py` exactly as in step 4 (it now asks for the complete set of files again), and make call k+1.
- **Stop rule:** after 4 calls with no accepted result, generation 3 has failed. Stop and report. Generation 3 is the
  bar's last generation (cap 3).

## Budget and time
Each follow-up carries the previous reply (whole files), so the prompt grows by up to ~35k tokens per call. The worst
case per call is about 131072 × $0.294/M + 200k × $0.098/M ≈ **$0.06**. Ceilings: $0.25 per call and $1.00 for
generation 3. The job's Maker spend is $0.107969 so far. The job clock started at 19:44:48 EDT on 2026-10-27, and gen-2
calls took 12–23 min each. AMENDMENT-3 moves the time bound to **2026-10-28 13:15 EDT (17:15Z)**. Do not start a
call that could not finish by then. Allow 60 min per call: **if it is after 12:15 EDT (16:15Z), do not start another
call.** Stop and report. The money cap is unchanged (< US$10).
