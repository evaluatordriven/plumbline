#!/usr/bin/env bash
# CLOSE apply script, job 2026-10-28-custody-times-ledger-spend. Run ONLY after stage 1 (handoffs/close/import_close.py,
# committed) and the Owner's disposition of the iteration-3 result (EVAL-ITER3-VERDICT.md: batch 3 VALID, 43/43 under
# Amendment 2 -> terminal state accepted). Adapted from 2026-10-28-doctrine-reader-pointer/CLOSE-apply.sh.
#
# What it does:
#   1. Builds the close inputs: inputs/custody.json completion, custody/subject-{1cb410b,c882646,f95e0d3}.sha256 and
#      the three run files (handoffs/close_inputs.py).
#   2. Appends the Owner's dispose line to the ledger (his words, decision time and channel; hand, recorded late).
#   3. Runs `plumbline_job.py close` from a clean worktree of main @ 3df1ce5 with PLUMBLINE_EXPECT_REVISION set
#      (bar: base tooling only). This writes the §5 records, the packet facts, the run-log row and the custody/v1 record.
#   4. Validates the custody record with custody check.py @ 3e3ca58 (OK, 68 controls, 0 violations).
#   5. Runs P5(e) with --record, the leak scan, the key-pattern scan and the __pycache__ check, then ONE local commit.
# No push, no model call, nothing under /tmp. On any failure the job folder and run-log.json are restored to HEAD.
# Usage:
#   CLOSE_DISPOSITION=given|declined CLOSE_WORDS='<Steve verbatim>' CLOSE_DECIDED_AT=2026-10-29THH:MM:SSZ \
#   CLOSE_CHANNEL='<channel / relay path>' CLOSE_LEDGER_SHA=<post-import ledger sha> bash .../CLOSE-apply.sh
# Optional: CLOSE_EXPECT_BRANCH (dry runs on a scratch branch only), CLOSE_NO_COMMIT=1, CLOSE_WORK (scratch dir),
#           CLOSE_CORPUS (a copy of the a48a464 corpus; the checkout itself is read-only).
set -euo pipefail
J="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; R="$(git -C "$J" rev-parse --show-toplevel)"; cd "$J"
JOB=2026-10-28-custody-times-ledger-spend
W="${CLOSE_WORK:-/workspace/edi-work/$JOB/close}"; mkdir -p "$W"
RUNID="close-$(date -u +%Y%m%dT%H%M%SZ)-$$"; export TMPDIR="$W/tmp-$RUNID"; mkdir -p "$TMPDIR"
export PYTHONDONTWRITEBYTECODE=1
EMIT="$W/emitter-3df1ce5-$RUNID"
EMIT_REV=3df1ce52eddfe18705e380c4b6e99cf617cfa24b; EMIT_TREE=230997f1ca9c89ccf035997c4a4db31a0c8ba5fa
CORPUS="${CLOSE_CORPUS:?set CLOSE_CORPUS to a writable copy of /workspace/plumbline-job/src/e-di-a48a464-git (read-only)}"
CUSTODY=/workspace/plumbline-job/src/custody; CHECK_SHA=aaeb7e0532c950ee1736207b0a91ff9d810533fccecdb2c7708312408e5bcd18
CONTROLS=/workspace/job-controls/$JOB
RUNLOG="$R/dot-plumbline/run-log.json"
STARTED=0
cleanup() { [ -d "$EMIT" ] && git -C "$R" worktree remove --force "$EMIT" >/dev/null 2>&1; git -C "$R" worktree prune; rm -rf "$TMPDIR"; }
die() { echo "CLOSE-apply: STOP: $*" >&2
        if [ "$STARTED" = 1 ]; then
          git -C "$R" checkout -q -- "$J" "$RUNLOG" 2>/dev/null || git -C "$R" checkout -q -- "$J"
          git -C "$R" clean -fdq -- "$J"
          echo "  (job folder and run-log.json restored to HEAD; nothing committed)" >&2; fi
        cleanup; exit 1; }
: "${CLOSE_DISPOSITION:?set CLOSE_DISPOSITION (given|declined)}" "${CLOSE_WORDS:?set CLOSE_WORDS (Steve verbatim)}"
: "${CLOSE_DECIDED_AT:?set CLOSE_DECIDED_AT (UTC Z)}" "${CLOSE_CHANNEL:?set CLOSE_CHANNEL}"
: "${CLOSE_LEDGER_SHA:?set CLOSE_LEDGER_SHA (the post-import ledger sha, after review)}"
case "$CLOSE_DISPOSITION" in given|declined) ;; *) die "CLOSE_DISPOSITION must be given or declined";; esac
[[ "$CLOSE_DECIDED_AT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || die "CLOSE_DECIDED_AT not YYYY-MM-DDTHH:MM:SSZ"
case "$CLOSE_WORDS$CLOSE_CHANNEL" in *"{{"*|*"<"*">"*) die "words/channel contain a placeholder";; esac
case "$W$TMPDIR$CORPUS" in /tmp/*|*:/tmp/*) die "nothing under /tmp";; esac
sha() { sha256sum "$1" | cut -d' ' -f1; }
MAN=custody/MANIFEST.sha256; BAR=custody/bar.md; LED=inputs/custody-events.jsonl
MAN_SHA=acdf764b32bab5e0fa4615590714c49162cbbaecddd00c03c6d8121b59b85d98
BAR_SHA=72e92dc7580e2447f19dfff66aaac02d8484157a6283dcfdda6c7bb2de7561c6
CTL_MAN_SHA=fe03346b4b62240ec461f3feedc89ae28b6d96fc177e967852566cec1a655ccf
LED_OLD="$CLOSE_LEDGER_SHA"
SUBJECT_REV=f95e0d3ae5798e4f7ea6e9304ff9babfe99bf783
LAST_CHECK=2026-10-29T16:23:54Z   # last spend-ledger settle; the decision cannot precede it

# ---- pre-checks: change nothing unless every one holds ----
[ "$(git -C "$R" rev-parse --abbrev-ref HEAD)" = "${CLOSE_EXPECT_BRANCH:-job/$JOB}" ] || die "not on the job branch"
[ -z "$(git -C "$R" status --porcelain -- "$J" "$RUNLOG")" ] || die "job folder or run-log.json has uncommitted changes"
[ "$(sha $MAN)" = $MAN_SHA ] || die "custody/MANIFEST.sha256 is not the frozen manifest"
[ "$(sha $BAR)" = $BAR_SHA ] || die "bar.md digest changed"
( cd custody && sha256sum --quiet -c MANIFEST.sha256 ) || die "frozen set does not match its manifest"
[ "$(sha custody/controls/MANIFEST.sha256)" = $CTL_MAN_SHA ] || die "custody/controls/MANIFEST.sha256 is not the frozen controls manifest"
( cd "$CONTROLS" && sha256sum --quiet -c "$J/custody/controls/MANIFEST.sha256" ) || die "held-out controls do not match the frozen controls manifest"
[ "$(sha $LED)" = "$LED_OLD" ] || die "ledger is not ${LED_OLD:0:8}…"
tail -1 $LED | grep -q '^{"event": "spend"' || die "last ledger line is not the close spend line"
grep -q '"event": "evaluation", "iteration": 3, "batch": 3' $LED || die "no iteration-3 batch-3 evaluation line"
[ "$(grep -c '"recorded_late": true' $LED)" = "$(( $(wc -l < $LED) - 8 ))" ] || die "a post-amendment ledger line is not marked recorded_late"
grep -qF 'Batch: VALID (no control wrong). Every check T1-J4 scores 1 under Amendment 2: 43/43 -> terminal state accepted.' EVAL-ITER3-VERDICT.md || die "EVAL-ITER3-VERDICT.md is not the batch-3 PASS"
grep -q '^23\. Late-recorded ledger lines' custody/DISCLOSURES.md || die "DISCLOSURES.md has no item 23"
grep -q '^24\. Spend figures' custody/DISCLOSURES.md || die "DISCLOSURES.md has no item 24"
git ls-files --error-unmatch custody/evidence/spend-status-close.json >/dev/null 2>&1 || die "custody/evidence/spend-status-close.json (the P6 key-usage read) is not committed"
python3 -c 'import json,sys; s=json.load(open("custody/x-plumbline.json"))["spend"]; sys.exit(0 if s["reconciled"] is True else 1)' || die "x-plumbline spend is not reconciled"
git -C "$R" merge-base --is-ancestor $SUBJECT_REV HEAD || die "the evaluated rev $SUBJECT_REV is not on this branch"
[ -z "$(git -C "$R" diff --name-only $SUBJECT_REV HEAD -- . ':!dot-plumbline/jobs/'"$JOB" ':!dot-plumbline/run-log.json')" ] || die "HEAD differs from the evaluated rev outside this job folder and run-log.json"
[ "$(python3 -c 'import json;print(json.load(open("packet.json")).get("terminal_state"))')" = None ] || die "packet already has a terminal_state (closed?)"
[ -f "$CORPUS/tools/validate_job_packet.py" ] || die "corpus not found: $CORPUS"
[ "$(sha "$CUSTODY/checker/check.py")" = $CHECK_SHA ] || die "custody check.py is not the 3e3ca58 checker"
python3 - "$CLOSE_DECIDED_AT" "$LAST_CHECK" <<'PY' || die "CLOSE_DECIDED_AT is before the last check or in the future"
import sys; from datetime import datetime, timezone
P = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
d = P(sys.argv[1]); assert P(sys.argv[2]) <= d <= datetime.now(timezone.utc)
PY
MLOG_SHA=$(sha custody/evidence/harness-maker-deepseek.log)
CPATH_BEFORE="$TMPDIR/cpath-before.txt"; ( grep -rlF "$CONTROLS" "$J" || true ) | sort > "$CPATH_BEFORE"

# ---- 0. the emitter: a clean checkout of main @ 3df1ce5 ----
git -C "$R" worktree add -q --detach "$EMIT" $EMIT_REV || die "could not create the 3df1ce5 worktree"
[ "$(git -C "$EMIT" rev-parse HEAD^{tree})" = $EMIT_TREE ] || die "emitter worktree tree is not $EMIT_TREE"
[ -z "$(git -C "$EMIT" status --porcelain)" ] || die "emitter worktree is not clean"

STARTED=1; trap 'die "unexpected error (line $LINENO)"' ERR

# ---- 1. close inputs ----
python3 handoffs/close_inputs.py --job-dir "$J" --run-dir "$TMPDIR/runs" --controls-dir "$CONTROLS"

# ---- 2. the Owner's disposition: inputs/custody.json + one dispose line in the ledger ----
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
NOW="$NOW" python3 - "$LED" inputs/custody.json <<'PY'
import json, os, sys
E = os.environ
ci = json.load(open(sys.argv[2], encoding="utf-8"))
ci["disposition"] = {**(ci.get("disposition") or {}), "by": "Steve Moitozo II", "at": E["CLOSE_DECIDED_AT"],
                     "acknowledgesUnobserved": []}
open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(ci, indent=2, ensure_ascii=False) + "\n")
ev = {"event": "dispose", "by": "Steve Moitozo II", "at": E["CLOSE_DECIDED_AT"], "role": "owner",
      "state": E["CLOSE_DISPOSITION"], "words": E["CLOSE_WORDS"], "channel": E["CLOSE_CHANNEL"],
      "subject": "iteration 3, batch 3: 43/43 under Amendment 2, terminal state accepted (EVAL-ITER3-VERDICT.md)",
      "writer": "hand", "hand_appended": True, "recorded_late": True,
      "recorded_by": "Chief of Staff (Orchestrator)", "recorded_at": E["NOW"],
      "at_source": "the Owner's decision as relayed to the Orchestrator, 2026-10-29 12:36 EDT (minute only; seconds not recorded)",
      "note": "hand-appended by CLOSE-apply.sh; recorded late (DEVIATIONS item 23). kit/custody_ledger.py dispose stamps "
              "the run time, not the Owner's decision time, so the line carries the decision time as received"}
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write(json.dumps(ev, ensure_ascii=False) + "\n")
PY

# ---- 3. the close, from the 3df1ce5 emitter ----
RUNS=(); for i in 1 2 3; do RUNS+=(--run "$TMPDIR/runs/run-$i.json"); done
set +e
PLUMBLINE_EXPECT_REVISION=$EMIT_TREE EDI_CORPUS="$CORPUS" python3 "$EMIT/kit/plumbline_job.py" close \
  --job-dir "$J" "${RUNS[@]}" --corpus "$CORPUS" --terminal-state accepted --outcome accepted \
  --disposition "$CLOSE_DISPOSITION" --disposition-note "$CLOSE_WORDS" 2>&1 | tee "$TMPDIR/close.out"
CODE=${PIPESTATUS[0]}; set -e
echo "CLOSE-apply: plumbline_job.py close exit $CODE"
[ "$CODE" = 0 ] || die "plumbline_job.py close exited $CODE (see output above)"
REC=custody/record.custody.json
[ -f "$REC" ] || die "no custody record written"
[ "$(sha custody/evidence/harness-maker-deepseek.log)" = "$MLOG_SHA" ] || die "the close rewrote the Maker log"

# ---- 4. validate the custody record (custody check.py @ 3e3ca58) ----
CHECK_CMD=(python3 "$CUSTODY/checker/check.py" custody/record.custody.json --files ../../.. --evidence custody/evidence --bar custody/bar.md)
printf '%s\n' "# run from the job folder; checker = custody check.py @ 3e3ca58 (sha256 $CHECK_SHA)" \
  "python3 <custody@3e3ca58>/checker/check.py custody/record.custody.json --files ../../.. --evidence custody/evidence --bar custody/bar.md" > custody/CHECK-COMMAND.txt
set +e; "${CHECK_CMD[@]}" > custody/CHECK-OUTPUT.json; CC=$?; set -e
echo "CLOSE-apply: check.py exit $CC"
[ "$CC" = 0 ] || { cat custody/CHECK-OUTPUT.json >&2; die "custody check.py exit $CC (not OK)"; }
python3 - custody/CHECK-OUTPUT.json "$REC" <<'PY' || die "record check summary not as required (OK, 68 controls, 0 violations)"
import json, sys
o = json.load(open(sys.argv[1])); r = json.load(open(sys.argv[2]))
txt = json.dumps(o)
assert '"FAIL"' not in txt and '"MISSING"' not in txt, "a requirement is not OK"
p = r.get("predicate", r)
ctl = p.get("controls") or []
assert len(ctl) == 68, f"{len(ctl)} controls in the record"
viol = p.get("violations", [])
assert not viol, viol
print(f"  record check: OK; {len(ctl)} controls; {len(viol)} violations")
PY
REC_SHA=$(sha $REC)

# ---- 5. P5(e), scans, commit (local only) ----
python3 custody/freeze/instrument/p5check.py --job "$PWD" --record "$REC" > P5-CHECK-close.json || die "P5(e) FAIL after close (P5-CHECK-close.json)"
[ "$(python3 -c 'import json;print(json.load(open("P5-CHECK-close.json"))["verdict"])')" = PASS ] || die "P5(e) verdict not PASS"
bash handoffs/close/public_list.sh "$R" "$TMPDIR/public" >/dev/null || die "could not build the public list"
mapfile -t NEW < <( { git -C "$J" status --porcelain --untracked-files=all -- . | cut -c4-
                      git -C "$R" diff --name-only --diff-filter=AM $SUBJECT_REV HEAD -- "$J"; } \
                    | sed "s|^dot-plumbline/jobs/$JOB/||" | sort -u ; echo "$RUNLOG")   # stage-1 files too
python3 handoffs/close/leak_scan.py --controls "$CONTROLS" --public-list "$TMPDIR/public/public-files.txt" \
  --allow handoffs/close/leak-allow.json "${NEW[@]}" \
  || { [ -n "${CLOSE_LEAK_KEEP:-}" ] && mkdir -p "$CLOSE_LEAK_KEEP" && cp custody/record.custody.json packet.json record.json "$CLOSE_LEAK_KEEP"/ 2>/dev/null
       die "held-out control text in a close output"; }
if grep -rlE 'sk-or-v1-[0-9a-f]{20,}' "$J" "$RUNLOG" >/dev/null; then die "key-pattern scan hit, nothing committed"; fi
[ -z "$(find "$J" -name __pycache__ -print -quit)" ] || die "__pycache__ in the job folder"
( grep -rlF "$CONTROLS" "$J" || true ) | sort | comm -13 "$CPATH_BEFORE" - \
  | grep -vxF -e "$J/inputs/custody.json" -e "$J/custody/record.custody.json" -e "$J/packet.json" -e "$J/record.json" && die "a held-out control path appeared in an unexpected file" || true
LED_NEW=$(sha $LED)
if [ "${CLOSE_NO_COMMIT:-0}" = 1 ]; then
  git -C "$J" status --porcelain --untracked-files=all -- . "$RUNLOG" > "$W/dryrun-status.txt"
  ( cd "$R" && git status --porcelain --untracked-files=all -- "$J" "$RUNLOG" | cut -c4- | while read -r f; do [ -f "$f" ] && sha256sum "$f"; done ) > "$W/dryrun-files.sha256"
  echo "DRY RUN: not committed. record $REC_SHA · ledger $LED_NEW (file list: $W/dryrun-files.sha256)"; trap - ERR; cleanup; exit 0; fi
SPEND_TOTAL=$(python3 -c 'import json; print(json.load(open("custody/x-plumbline.json"))["spend"]["total_usd"])')
git -C "$R" add -A -- "$J" "$RUNLOG"
git -C "$R" -c user.name="Steve Moitozo II" -c user.email="smoitozo@users.noreply.github.com" commit -q \
  -m "job $JOB: closed accepted, disposition $CLOSE_DISPOSITION (Owner)" \
  -m "Decided $CLOSE_DECIDED_AT via $CLOSE_CHANNEL. Iteration 3 (batch 3) 43/43 under Amendment 2 -> accepted; iterations 1 and 2 regenerate. §5 records + custody/v1 (CL1) record emitted by base main 3df1ce5 (tree $EMIT_TREE); check.py @ 3e3ca58 OK, 68 controls, 0 violations. record $REC_SHA; ledger $LED_NEW (lines 9 on hand-appended, recorded late: disclosure 23). bar.md unchanged $BAR_SHA; frozen manifest unchanged $MAN_SHA. P5(e) PASS (P5-CHECK-close.json). Spend (P6, key-usage read custody/evidence/spend-status-close.json): total US\$$SPEND_TOTAL, reconciled with the key; Owner dashboard figure not reconciled (disclosure 24). Hand times, relays: custody/x-plumbline.json. Disclosures 1-24 (1-23 accepted 13:15 EDT): custody/DISCLOSURES.md."
trap - ERR; cleanup
echo "CLOSED. commit $(git -C "$R" rev-parse HEAD)"
echo "record $REC_SHA"; echo "ledger $LED_NEW"; echo "P5(e) PASS"
