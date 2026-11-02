# Handoff — iter1 Evaluator (batch 1) · job 2026-10-27-custody-emitter-gaps

To: **E-DI Evaluator bot** (Evaluator seat operator). From: Chief of Staff (Orchestrator). Authority: Steve Moitozo II,
2026-10-27 18:06 EDT, "Proceed. Run the job"; 18:31 EDT, "Go with all four recommendations and start iteration 1". Bar: `custody/bar.md` sha256 `3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b` (frozen).
**Filled** by the Orchestrator on 2026-10-28 (06:56 EDT) from the Maker's gen-3 report, which the Orchestrator re-verified.
Subject: Maker commit `7cc38f833f8f5eeceffcb405885adb05141f8c65` (generation 3, call 2, accepted by the Maker; ledger `generation n 3 close` 2026-10-28T10:55:53Z).
Time bound: AMENDMENT-3-time-bound.md (sha256 `f4babace8aa01666339c2411bdf9068db43c7c414ee3884f6e3bec1b085acb68`). The bound ends
**2026-10-28 13:15 EDT (17:15Z)**. See section 7 for the cutoffs.

You operate two instruments and file their output. **You score nothing**: every verdict comes from S1
(`run_instrument.sh`, `p5check.py`) or E-GLM (`n6_batch.py`) output, copied as written. You write no code, fix
nothing, and never edit an instrument, a control or the subject. Anything not covered here: stop and report.

## 0. Preconditions (any NO → stop and report)
- E0 **E-GLM seat name — resolved.** Ledger now also pins seat `eval-glm` (Z.AI, `z-ai/fp8`, `api.z.ai`, via
  openrouter.ai, 2026-10-27T22:32:11Z; DECISIONS-2026-10-27.md D1), so frozen `n6_batch.py --seat eval-glm --ledger` resolves.
  Check: `grep '"seat": "eval-glm"' $JOB/inputs/custody-events.jsonl` prints that pin line.
- E1 Maker commit `7cc38f833f8f5eeceffcb405885adb05141f8c65` is on `origin/job/2026-10-27-custody-emitter-gaps` (`git -C /workspace/plumbline-pr branch -r --contains 7cc38f833f8f5eeceffcb405885adb05141f8c65`).
- E2 Frozen instruments intact: `cd $JOB/custody && sha256sum -c MANIFEST.sha256` all OK.
- E3 Key file `/workspace/.openrouter-key` exists; never print, copy or commit it.
- E4 Ledger: `sha256sum $JOB/inputs/custody-events.jsonl` = `4b03278bbc5908a303ef444ee94129100b5fab3d17edf9397eba97f6ee0990b3`.
  Its last line is `"event": "generation", "n": 3, "boundary": "close", "outcome": "accepted"` with `"maker_sha": "7cc38f833f8f5eeceffcb405885adb05141f8c65"`.
- E5 Clock: it is before **11:30 EDT (15:30Z)** 2026-10-28 when you start step 2. Otherwise stop and report (section 7).

## 1. Fixed names
```bash
JOB=/workspace/plumbline-pr/dot-plumbline/jobs/2026-10-27-custody-emitter-gaps   # read-only for you
I=$JOB/custody/freeze/instrument
B=/workspace/edi-batches/2026-10-27-custody-emitter-gaps/iter1   # batch dir, OUTSIDE every repo
REV=$B/rev                                                       # checkout of the subject
SRC=/workspace/next-job-controls/controls                        # held-out controls: READ-ONLY source
mkdir -p "$B/s1" "$B/p5" "$B/n6"
```
Never write into `$SRC`, `/workspace/next-job-controls` or `/workspace/plumbline-pr`. Never copy a control,
fixture or batch output into any repo; control bytes leave `$B` only by sha256.

## 2. Subject and batch controls
```bash
git clone -q /workspace/plumbline-pr "$REV" && git -C "$REV" -c advice.detachedHead=false checkout -q --detach 7cc38f833f8f5eeceffcb405885adb05141f8c65
git -C "$REV" rev-parse HEAD > "$B/rev.txt"
cp -a "$SRC" "$B/controls" && chmod -R a-w "$B/controls"
( cd "$B/controls" && sha256sum --quiet -c "$JOB/custody/controls/MANIFEST.sha256" ) && echo controls-ok
# expected controls manifest sha256: 9764d8e4d5a0bad067f44379f08035e0e41de6df6acc00a2c9e31641139760bf
```

## 3. S1 batch (N1-N5, N7, N8; N9 control; all controls in the same batch — P1)
```bash
bash "$I/run_instrument.sh" batch "$REV" "$B/controls" "$B/s1" > "$B/s1/run.log" 2>&1; echo $? > "$B/s1/exit"
```
Exit `0` controls as expected (subject verdicts in `$B/s1/summary.json`) · `1` a control missed → batch **void**
(report; re-run only on the Orchestrator's word; counts against budget, not cap) · `2` usage · `3` pin mismatch → stop.
No real job is passed in batch 1 (REAL_JOB list empty) unless the dispatch names one.

## 4. P5(e)
```bash
python3 "$I/p5check.py" --job "$JOB" > "$B/p5/P5-check.json" 2> "$B/p5/P5-check.stderr"; echo $? > "$B/p5/exit"
```

## 5. E-GLM batch 1 (N6, with clean G-c1 and planted G-p1 in the same batch)
```bash
python3 "$JOB/custody/freeze/harness/or_call.py" --check-key > "$B/n6/key-usage-before.json"
python3 "$I/n6_batch.py" --rev "$REV" --controls "$B/controls" --batch 1 --out "$B/n6" \
  --ledger "$JOB/inputs/custody-events.jsonl" > "$B/n6/stdout.json" 2> "$B/n6/stderr.txt"; echo $? > "$B/n6/exit"
python3 "$JOB/custody/freeze/harness/or_call.py" --check-key > "$B/n6/key-usage-after.json"
```
Makes 3 logged calls (`z-ai/glm-5.3-flash`, pin `z-ai/fp8`, temperature 0, max 800 tokens) into
`$B/n6/harness-eval-glm-b1.log`; result `$B/n6/N6-batch.json` (`controls_ok`, `subject_verdict`, `N6` = PASS / FAIL / void).
Any `or_call_exit` ≠ 0 in the items → report it; do not retry on your own. Expected spend ≈ $0.02 (ceiling $0.25).
The log holds the control texts. **Log policy (DECISIONS D4):** the full log stays in `$B` (under
/workspace/edi-batches/); never copy it into a repo. At close the Orchestrator commits a redacted copy (each held-out
control text replaced by `[REDACTED held-out control <id> sha256 <digest>]`) plus the sha256 of the full log.
Report `sha256sum $B/n6/harness-eval-glm-b1.log` so that digest is fixed at batch time.

## 6. Seal and report
```bash
grep -rlF -f /workspace/.openrouter-key "$B"; echo "key-scan rc=$? (must be 1)"
( cd "$B" && find . -path ./rev -prune -o -path ./controls -prune -o -type f -print0 | sort -z | xargs -0 sha256sum ) > "$B/BATCH-MANIFEST.sha256"
sha256sum "$B/BATCH-MANIFEST.sha256"
```
Report to the Orchestrator (plain text; verdicts copied from instrument files, never your own):
```
JOB 2026-10-27-custody-emitter-gaps · iter1 · batch 1 · subject 7cc38f833f8f5eeceffcb405885adb05141f8c65 (rev.txt: …)
controls copy: manifest check OK|FAIL
S1 exit: …            summary.json: <verbatim>
  N1 … N2 … N3 … N4 … N5 … N7 … N8 …   (from summary.json)   N9 control: … (C-N9p)
  controls: every line of run.log containing "MISMATCH" (or "none")
P5(e): p5check exit …, verdict …  (P5-check.json)
E-GLM (N6): exit … · controls_ok … · subject_verdict … · N6 … ; per call: call id, item id, or_call_exit, verdict, lines
  spend: Σ total_cost from the generation replies in harness-eval-glm-b1.log; key usage before → after
  full log sha256: …
batch dir: $B · BATCH-MANIFEST.sha256 sha256 …
key-scan rc=1
stops/anomalies: … (verbatim)
```
Pass rule is applied by the Orchestrator, not by you: every N1-N8 must read PASS; N9 is a control, not scored.

## 7. Time and budget (AMENDMENT-3)
The bound ends **2026-10-28 13:15 EDT (17:15Z)**. Leave the Orchestrator at least 45 min to close: pass rule, redacted log,
commit, record. The S1 batch makes no model calls, and its earlier dry runs and discrimination runs took minutes.
Step 5 makes 3 sequential E-GLM calls (max 800 tokens each). Allow up to 10 min each: or_call reads time out at 300 s,
plus generation retries.
- Do not start step 2 after **11:30 EDT (15:30Z)**.
- **Do not start step 5 (`n6_batch.py`, which starts the E-GLM calls) after 12:00 EDT (16:00Z).** If step 5 has not
  started by then, stop and report what you have.
- Do not kill a running call. If a call is still running at 12:30 EDT (16:30Z), report that it is still running.
- Money: expected E-GLM spend is ≈ $0.02 (ceiling $0.25). Job spend so far is $0.1463695 (key usage). The cap is
  unchanged: < US$10.
