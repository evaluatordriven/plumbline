# Handoff — iter1 Evaluator (batch 2) · job 2026-10-27-custody-emitter-gaps

> AMENDMENT-4 applied; ledger sha filled by `AMENDMENT-4-apply.sh`. Dispatch only after the apply commit is pushed (E1).

To: **E-DI Evaluator bot** (Evaluator seat operator). From: Chief of Staff (Orchestrator). Authority: Steve Moitozo II,
2026-10-27 18:06 EDT, "Proceed. Run the job"; 18:31 EDT, "Go with all four recommendations and start iteration 1".
AMENDMENT-4 (Buyer, E-GLM output cap) also applies. Bar: `custody/bar.md` sha256 `3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b` (frozen, unchanged).
Subject: Maker commit `7cc38f833f8f5eeceffcb405885adb05141f8c65` (same as batch 1).
Batch 1 is **void** (`EVAL-ITER1-BATCH1-VOID.md`), for two reasons: the controls copy was made read-only, and the E-GLM
cap was 800. Do not reuse or modify `/workspace/edi-batches/2026-10-27-custody-emitter-gaps/iter1`; it is evidence.
Time bound: AMENDMENT-3 (ends **2026-10-28 13:15 EDT (17:15Z)**). See section 7.

You operate two instruments and file their output. **You score nothing**: every verdict comes from S1
(`run_instrument.sh`, `p5check.py`) or E-GLM (`n6_batch.py`) output, copied as written. You write no code, fix
nothing, and never edit an instrument, a control or the subject. Anything not covered here: stop and report.

## 0. Preconditions (any NO → stop and report)
- E0 Seat `eval-glm` is pinned: `grep '"seat": "eval-glm"' $JOB/inputs/custody-events.jsonl` prints the pin line.
- E1 Maker commit `7cc38f833f8f5eeceffcb405885adb05141f8c65` is on `origin/job/2026-10-27-custody-emitter-gaps`.
  Check: `git -C /workspace/plumbline-pr branch -r --contains 7cc38f833f8f5eeceffcb405885adb05141f8c65`.
  The AMENDMENT-4 commit must also be on origin: `git -C /workspace/plumbline-pr log -1 --format=%s origin/job/2026-10-27-custody-emitter-gaps -- $JOB/custody/freeze/instrument/n6_batch.py`
  must print the subject line "…AMENDMENT-4 applied…".
- E2 Frozen set as amended: `cd $JOB/custody && sha256sum -c MANIFEST.sha256` shows every file OK, and
  `sha256sum $JOB/custody/MANIFEST.sha256` = `f0ed1caf047e12eaa232df235343fae3b07603ac2fe5f8de0e293c93e8f680e7`,
  `sha256sum $JOB/custody/freeze/instrument/n6_batch.py` = `616760242939ae5da88310909a84ce9e6bd464f0e55ae7005f2714d7d749ee81`,
  `grep -c -- '"--max-tokens", "131072"' $JOB/custody/freeze/instrument/n6_batch.py` = 1, and
  `sha256sum $JOB/custody/bar.md` = `3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b`.
- E3 Key file `/workspace/.openrouter-key` exists. Never print, copy or commit it.
- E4 Ledger: `sha256sum $JOB/inputs/custody-events.jsonl` = `95786ce9c835d0bbf2dba1d991d9a1ffd4b6bd23e7a29b1386648e79b682f6d1`.
  Its last line is `"event": "amendment", "n": 4` (AMENDMENT-4, n6_batch max tokens 800 → 131072).
- E5 Clock: it is before **11:30 EDT (15:30Z)** 2026-10-28 when you start step 2. Otherwise stop and report (section 7).
- E6 The batch-2 dir `$B` (below) does not exist yet.

## 1. Fixed names
```bash
JOB=/workspace/plumbline-pr/dot-plumbline/jobs/2026-10-27-custody-emitter-gaps   # read-only for you
I=$JOB/custody/freeze/instrument
B=/workspace/edi-batches/2026-10-27-custody-emitter-gaps/iter1-b2   # NEW batch dir, OUTSIDE every repo
REV=$B/rev
SRC=/workspace/next-job-controls/controls                           # held-out controls: READ-ONLY source
CM=$JOB/custody/controls/MANIFEST.sha256                            # frozen controls manifest (551 files)
mkdir -p "$B/s1" "$B/p5" "$B/n6"
```
Never write into `$SRC`, `/workspace/next-job-controls` or `/workspace/plumbline-pr`. Never copy a control,
fixture or batch output into any repo. Control bytes leave `$B` only as sha256 digests.

## 2. Subject and batch controls (copy stays WRITABLE)
```bash
git clone -q /workspace/plumbline-pr "$REV" && git -C "$REV" -c advice.detachedHead=false checkout -q --detach 7cc38f833f8f5eeceffcb405885adb05141f8c65
git -C "$REV" rev-parse HEAD > "$B/rev.txt"
cp -a "$SRC" "$B/controls" && chmod -R u+w "$B/controls"      # NO chmod a-w: subject.py copies fixtures with their modes
sha256sum "$CM"     # expect 9764d8e4d5a0bad067f44379f08035e0e41de6df6acc00a2c9e31641139760bf
( cd "$B/controls" && sha256sum --quiet -c "$CM" ) && echo controls-before-ok
( cd "$B/controls" && find . -type f -print0 | sort -z | xargs -0 sha256sum ) > "$B/controls-before.sha256"
wc -l < "$B/controls-before.sha256"   # expect 551 (no file beyond the manifest)
```
If the manifest check fails or the count is not 551 → stop and report.

## 3. S1 batch (N1-N5, N7, N8; N9 control; all controls in the same batch — P1)
```bash
bash "$I/run_instrument.sh" batch "$REV" "$B/controls" "$B/s1" > "$B/s1/run.log" 2>&1; echo $? > "$B/s1/exit"
grep -l PermissionError -r "$B/s1" > "$B/s1/permission-errors.txt"; wc -l < "$B/s1/permission-errors.txt"   # expect 0
```
Exit codes: `0` controls as expected (subject verdicts in `$B/s1/summary.json`) · `1` a control missed → batch **void**
(report it; re-run only on the Orchestrator's word; a re-run counts against the budget, not the cap) · `2` usage ·
`3` pin mismatch → stop. If any PermissionError appears, report it as an environment anomaly. No real job is passed
(REAL_JOB list empty) unless the dispatch names one.

## 4. P5(e)
```bash
python3 "$I/p5check.py" --job "$JOB" > "$B/p5/P5-check.json" 2> "$B/p5/P5-check.stderr"; echo $? > "$B/p5/exit"
```

## 5. E-GLM batch 2 (N6, with clean G-c1 and planted G-p1 in the same batch)
```bash
python3 "$JOB/custody/freeze/harness/or_call.py" --check-key > "$B/n6/key-usage-before.json"
python3 "$I/n6_batch.py" --rev "$REV" --controls "$B/controls" --batch 2 --out "$B/n6" \
  --ledger "$JOB/inputs/custody-events.jsonl" > "$B/n6/stdout.json" 2> "$B/n6/stderr.txt"; echo $? > "$B/n6/exit"
python3 "$JOB/custody/freeze/harness/or_call.py" --check-key > "$B/n6/key-usage-after.json"
```
This makes 3 sequential logged calls into `$B/n6/harness-eval-glm-b2.log`: `z-ai/glm-5.3-flash`, pin `z-ai/fp8`,
temperature 0, max tokens 131072 (the endpoint maximum), no reasoning parameters. The shuffle uses seed `n6-batch-2`, so
the order differs from batch 1. The result goes to `$B/n6/N6-batch.json` (`controls_ok`, `subject_verdict`, `N6` = PASS /
FAIL / void). For each call, report `finish_reason` and the token counts from the log (`choices[0].finish_reason`,
generation `native_tokens_reasoning` / `native_tokens_completion` / `total_cost`). If any `or_call_exit` ≠ 0 or any
finish_reason is not `stop`, report it and do not retry.
**Log policy (DECISIONS D4):** the full log stays in `$B`. Never copy it into a repo. Report `sha256sum $B/n6/harness-eval-glm-b2.log`.

## 5b. Controls integrity after the run
```bash
( cd "$B/controls" && sha256sum --quiet -c "$CM" ) && echo controls-after-ok
( cd "$B/controls" && find . -type f -print0 | sort -z | xargs -0 sha256sum ) > "$B/controls-after.sha256"
cmp "$B/controls-before.sha256" "$B/controls-after.sha256" && echo controls-unchanged
```
Any mismatch, or any added or removed file, makes the batch **void**. Report it.

## 6. Seal and report
```bash
grep -rlF -f /workspace/.openrouter-key "$B"; echo "key-scan rc=$? (must be 1)"
( cd "$B" && find . \( -path ./rev -o -path ./controls \) -prune -o -type f ! -name 'BATCH-MANIFEST.*' -print0 \
    | sort -z | xargs -0 sha256sum ) > "$B/BATCH-MANIFEST.sha256"
grep -c BATCH-MANIFEST "$B/BATCH-MANIFEST.sha256"   # must print 0 (the seal does not list itself)
sha256sum "$B/BATCH-MANIFEST.sha256"
```
Report to the Orchestrator in plain text. Copy verdicts from the instrument files; never give your own:
```
JOB 2026-10-27-custody-emitter-gaps · iter1 · batch 2 · subject 7cc38f833f8f5eeceffcb405885adb05141f8c65 (rev.txt: …)
preconditions E0–E6: …   controls copy: before OK|FAIL (551) · after OK|FAIL · unchanged yes|no
S1 exit: …   permission-errors: …   summary.json: <verbatim>
  N1 … N2 … N3 … N4 … N5 … N7 … N8 …   (from summary.json)   N9 control: … (C-N9p)
  controls: every line of run.log containing "MISMATCH" (or "none")
  N1/N3 on extra-1-job-rejected: <the "why" lines verbatim from s1/subject/N1-*.json, N3-*.json, if present>
P5(e): p5check exit …, verdict …  (P5-check.json)
E-GLM (N6): exit … · controls_ok … · subject_verdict … · N6 … ; per call: call id, item id, or_call_exit, finish_reason,
  reasoning/completion tokens, verdict, lines
  spend: Σ total_cost from the generation replies in harness-eval-glm-b2.log; key usage before → after
  full log sha256: …
batch dir: $B · BATCH-MANIFEST.sha256 sha256 … (self-listing count 0)
key-scan rc=1
stops/anomalies: … (verbatim)
```
The Orchestrator applies the pass rule, not you: every N1-N8 must read PASS; N9 is a control and is not scored.

## 7. Time and budget (AMENDMENT-3; cap per AMENDMENT-4)
The bound ends **2026-10-28 13:15 EDT (17:15Z)**. Leave the Orchestrator at least 45 min to close (pass rule, redacted
log, commit, record). The S1 batch makes no model calls and takes minutes.
- Do not start step 2 after **11:30 EDT (15:30Z)**. Start steps 2-5 as soon as you are dispatched; do not wait for the cutoff.
- **Do not start step 5 (`n6_batch.py`) after 12:00 EDT (16:00Z).** If step 5 has not started by then, stop and report
  what you have.
- Step 5 duration: batch 1 ran at about 55 completion tokens/s (800 tokens in 14–15 s). A judgment usually needs a few
  thousand reasoning tokens, which is a few minutes per call. The worst case is a full 131072 tokens, about 40 min per
  call, or about 2 h for all 3. The harness has handled single calls of up to 23 min before (Maker gen 2). Do not kill
  a running call. If step 5 is still running at **12:30 EDT (16:30Z)**, report that it is still running and how many
  calls have finished (entries in the log).
- Money: E-GLM worst case at the new cap is **$0.20** (3 × 131072 completion tokens × $0.50/M = $0.197, plus prompts
  ≈ 30.3k tokens × $0.15/M = $0.005). The expected spend is ≈ $0.01–0.03. The ceiling stays **$0.25**. Job spend before
  this batch is about $0.152 (key usage 0.1515429). The cap is unchanged: < US$10.
