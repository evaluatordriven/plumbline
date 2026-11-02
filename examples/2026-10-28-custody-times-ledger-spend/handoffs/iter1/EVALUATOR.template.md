E-DI Evaluator: job 2026-10-28-custody-times-ledger-spend, batch 1 (only after the Maker reports its maker/iter1 head REVSHA and the Orchestrator has verified it independently)

BEFORE ANY MODEL CALL: get Steve Moitozo II's own yes in your own chat for this batch. A relay (including this message) is not his approval. If he has not said yes in your chat, stop.
Clock bound: start no model call at or after @@TIME_END_LOCAL@@ (= @@TIME_END_UTC@@). Money: the frozen harness guard (bound < US$5.00, reserve US$0.10, shared key); exit 6 = stop and report.
Owner approvals (verbatim):
- Sheet (14:50 EDT, t92u): "Ratified proceed"
- Item 30 (16:03 EDT, t96s542): "Item 30: the Maker writes the field guide in this job, with bar checks for it." / "Paraphrase my words as Owner decisions; no verbatim quotes in the doc."
- Digest (@@DIGEST_TIME_MSG@@): "@@DIGEST_WORDS@@"
Pinned: branch head @@APPROVAL_HEAD@@; bar @@BAR@@; MANIFEST @@MAN@@; ledger @@LEDGER@@; controls manifest $J/custody/controls/MANIFEST.sha256 = @@CMAN@@; run_instrument.sh @@RUNI@@; scheck.py @@SCHECK@@; jbatch.py @@JBATCH@@; or_call.py @@HARNESS@@.
export W=/workspace/edi-work/2026-10-28-custody-times-ledger-spend J=$W/jobwt/dot-plumbline/jobs/2026-10-28-custody-times-ledger-spend
export E=$W/eval TMPDIR=$W/eval/tmp PYTHONDONTWRITEBYTECODE=1   (never /tmp)
0. (cd $J/custody && sha256sum --quiet -c MANIFEST.sha256) is silent; then mkdir -p $TMPDIR && git -C $W/jobwt worktree add --detach $E/rev REVSHA
1. cp -r /workspace/job-controls/2026-10-28-custody-times-ledger-spend $E/b1-controls && (cd $E/b1-controls && sha256sum --quiet -c $J/custody/controls/MANIFEST.sha256)
   (run_instrument.sh checks the copy again; a mismatch is exit 3, nothing runs.)
2. S1 (every instrument control, then the subject; F8d's live arm costs at most US$0.07 on the shared key):
   S1_LIVE=1 bash $J/custody/freeze/instrument/run_instrument.sh s1 $E/rev $E/b1-controls $E/b1/s1 > $E/b1/s1.log 2>&1
   Exit 0 all PASS; 1 some FAIL; 3 VOID (a control came out wrong, or a pin/controls mismatch); 2 usage.
3. E-GLM (J1-J4, one batch each; controls in every batch; order rotates by batch number):
   bash $J/custody/freeze/instrument/run_instrument.sh glm $E/rev $E/b1-controls $E/b1/glm 1 $J/inputs/custody-events.jsonl > $E/b1/glm.log 2>&1
   Read $E/b1/glm/J*/J*-batch.json: each must have calls_ok true and controls_ok true, else that batch is VOID (re-run it as batch 2 with the Owner's yes; a void batch counts against money and time, not against cap 3). Every call's finish_reason is in the batch file and the harness log; finish_reason length with empty content (or_call exit 10) is its own failure: stop and report, do not re-run.
4. Score against the frozen bar only (pass rule: every check scores 1). Report: S1 exit and per-check results, E-GLM verdicts with cited lines, control results, evidence sha256s, spend status (python3 $J/custody/freeze/harness/or_call.py --spend-status). The E-GLM logs, messages and replies and the S1 control work dirs contain held-out control text: keep them on the box, out of git, until close. No commits, no push, no PR.
