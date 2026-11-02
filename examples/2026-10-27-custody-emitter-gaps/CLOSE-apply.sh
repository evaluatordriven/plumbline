#!/usr/bin/env bash
# CLOSE apply script. PENDING THE OWNER'S DISPOSITION. Run ONLY after Steve gives or declines his disposition of
# the iteration-3 PASS (EVAL-ITER3-VERDICT.md: terminal state accepted).
#
# What it does:
#   1. Builds the close inputs: inputs/custody.json completion, custody/subject-c7db5b0.sha256 and the
#      iteration-3 run file (handoffs/close_inputs.py).
#   2. Appends the Owner's dispose line to the ledger (his words, decision time and channel).
#   3. Runs `plumbline_job.py close` from a clean base-main worktree @ ff350e3 with PLUMBLINE_EXPECT_REVISION set
#      (bar: Emitter). This writes the §5 record, the packet facts, the run-log row and the custody/v1 record.
#   4. Validates the custody record with custody check.py @ 3e3ca58 and writes the x-plumbline addendum.
#   5. Runs P5(e), the key scan and the __pycache__ check, then makes ONE local commit as Steve.
# No push, no model call, nothing under /tmp (scratch is under /workspace/edi-work). On any failure the job folder
# and run-log.json are restored to HEAD.
# Usage (from anywhere):
#   CLOSE_DISPOSITION=given|declined CLOSE_WORDS='"<Steve verbatim>"' CLOSE_DECIDED_AT=2026-10-28THH:MM:SSZ \
#   CLOSE_CHANNEL='<channel / relay path>' bash dot-plumbline/jobs/2026-10-27-custody-emitter-gaps/CLOSE-apply.sh
# Optional: CLOSE_LEDGER_SHA (default: the ledger sha after the iteration-3 evaluation line),
#   CLOSE_EXPECT_BRANCH (dry runs on a scratch branch only), CLOSE_NO_COMMIT=1 (dry run: stop before the commit and leave the result in place).
set -euo pipefail
J="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; R="$(git -C "$J" rev-parse --show-toplevel)"; cd "$J"
W=/workspace/edi-work/2026-10-27-custody-emitter-gaps; mkdir -p "$W"
RUNID="close-$(date -u +%Y%m%dT%H%M%SZ)-$$"; export TMPDIR="$W/tmp-$RUNID"; mkdir -p "$TMPDIR"
export PYTHONDONTWRITEBYTECODE=1
EMIT="$W/emitter-ff350e3-$RUNID"
EMIT_REV=ff350e36dc04ea6baf898acd909787fcc7c1b6d4; EMIT_TREE=4abcfa08f84d3b34849ad64bcfc281415772ffc1
CORPUS=/workspace/plumbline-job/src/e-di-a48a464
CUSTODY=/workspace/plumbline-job/src/custody; CHECK_SHA=aaeb7e0532c950ee1736207b0a91ff9d810533fccecdb2c7708312408e5bcd18
CONTROLS=/workspace/next-job-controls/controls
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
case "$CLOSE_DISPOSITION" in given|declined) ;; *) die "CLOSE_DISPOSITION must be given or declined";; esac
[[ "$CLOSE_DECIDED_AT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || die "CLOSE_DECIDED_AT not YYYY-MM-DDTHH:MM:SSZ"
case "$CLOSE_WORDS$CLOSE_CHANNEL" in *"{{"*) die "words/channel contain a placeholder";; esac
sha() { sha256sum "$1" | cut -d' ' -f1; }
MAN=custody/MANIFEST.sha256; BAR=custody/bar.md; LED=inputs/custody-events.jsonl
MAN_SHA=f0ed1caf047e12eaa232df235343fae3b07603ac2fe5f8de0e293c93e8f680e7
BAR_SHA=3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b
CTL_MAN_SHA=9764d8e4d5a0bad067f44379f08035e0e41de6df6acc00a2c9e31641139760bf
LED_OLD="${CLOSE_LEDGER_SHA:-0391a5416ea9256720873f2749b4ae622b65715d25a3c2505cf0494d1b94ae25}"
SUBJECT_REV=c7db5b0
LAST_CHECK=2026-10-28T14:24:49Z   # last batch-4 E-GLM log time (n6-b4-3 generation_fetched_at, rounded up); the decision cannot precede it

# ---- pre-checks: change nothing unless every one holds ----
[ "$(git -C "$R" rev-parse --abbrev-ref HEAD)" = "${CLOSE_EXPECT_BRANCH:-job/2026-10-27-custody-emitter-gaps}" ] || die "not on the job branch"
[ -z "$(git -C "$R" status --porcelain -- "$J" "$RUNLOG")" ] || die "job folder or run-log.json has uncommitted changes"
[ "$(sha $MAN)" = $MAN_SHA ] || die "custody/MANIFEST.sha256 is not the frozen manifest"
[ "$(sha $BAR)" = $BAR_SHA ] || die "bar.md digest changed"
( cd custody && sha256sum --quiet -c MANIFEST.sha256 ) || die "frozen set does not match its manifest"
[ "$(sha custody/controls/MANIFEST.sha256)" = $CTL_MAN_SHA ] || die "custody/controls/MANIFEST.sha256 is not the frozen controls manifest"
( cd "$CONTROLS" && sha256sum --quiet -c "$J/custody/controls/MANIFEST.sha256" ) || die "held-out controls do not match the frozen controls manifest"
[ "$(sha $LED)" = "$LED_OLD" ] || die "ledger is not ${LED_OLD:0:8}… (something was appended; set CLOSE_LEDGER_SHA after review)"
tail -1 $LED | grep -q '"event": "evaluation", "iteration": 3' || die "last ledger line is not the iteration-3 evaluation"
grep -q 'terminal state.*accepted' EVAL-ITER3-VERDICT.md || die "EVAL-ITER3-VERDICT.md does not record terminal state accepted"
git -C "$R" diff --quiet $SUBJECT_REV HEAD -- kit tools docs tests || die "code at HEAD is not the evaluated subject $SUBJECT_REV"
[ "$(python3 -c 'import json;print(json.load(open("packet.json")).get("terminal_state"))')" = None ] || die "packet already has a terminal_state (closed?)"
[ -f "$CORPUS/tools/validate_job_packet.py" ] || die "corpus at the pin not found: $CORPUS"
[ "$(sha "$CUSTODY/checker/check.py")" = $CHECK_SHA ] || die "custody check.py is not the 3e3ca58 checker"
python3 - "$CLOSE_DECIDED_AT" "$LAST_CHECK" <<'PY' || die "CLOSE_DECIDED_AT is before the last check or in the future"
import sys; from datetime import datetime, timezone
P = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
d = P(sys.argv[1]); assert P(sys.argv[2]) <= d <= datetime.now(timezone.utc)
PY

# ---- 0. the emitter: a clean checkout of base main @ ff350e3 ----
git -C "$R" worktree add -q --detach "$EMIT" $EMIT_REV || die "could not create the ff350e3 worktree"
[ "$(git -C "$EMIT" rev-parse HEAD^{tree})" = $EMIT_TREE ] || die "emitter worktree tree is not $EMIT_TREE"
[ -z "$(git -C "$EMIT" status --porcelain)" ] || die "emitter worktree is not clean"

STARTED=1; trap 'die "unexpected error (line $LINENO)"' ERR

# ---- 1. close inputs ----
RUN="$TMPDIR/run-3.json"
python3 handoffs/close_inputs.py --job-dir "$J" --run-out "$RUN" --controls-dir "$CONTROLS"

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
      "subject": "iteration 3, batch 4: PASS, terminal state accepted (EVAL-ITER3-VERDICT.md)",
      "recorded_by": "Chief of Staff (Orchestrator)", "recorded_at": E["NOW"],
      "note": "hand-appended by CLOSE-apply.sh. kit/custody_ledger.py dispose stamps the run time, not the Owner's "
              "decision time, so the line carries the decision time as received (disclosed in separationGaps)"}
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write(json.dumps(ev, ensure_ascii=False) + "\n")
PY

# ---- 3. the close, from the ff350e3 emitter ----
set +e
PLUMBLINE_EXPECT_REVISION=$EMIT_TREE EDI_CORPUS="$CORPUS" python3 "$EMIT/kit/plumbline_job.py" close \
  --job-dir "$J" --run "$RUN" --corpus "$CORPUS" --terminal-state accepted --outcome accepted \
  --disposition "$CLOSE_DISPOSITION" --disposition-note "$CLOSE_WORDS" 2>&1 | tee "$TMPDIR/close.out"
CODE=${PIPESTATUS[0]}; set -e
[ "$CODE" = 0 ] || die "plumbline_job.py close exited $CODE (see output above)"
REC=custody/record.custody.json
[ -f "$REC" ] || die "no custody record written"

# ---- 4. validate the custody record (custody check.py @ 3e3ca58) + x-plumbline addendum ----
CHECK_CMD=(python3 "$CUSTODY/checker/check.py" custody/record.custody.json --files ../../.. --evidence custody/evidence --bar custody/bar.md)
printf '%s\n' "# run from the job folder; checker = custody check.py @ 3e3ca58 (sha256 $CHECK_SHA)" \
  "python3 <custody@3e3ca58>/checker/check.py custody/record.custody.json --files ../../.. --evidence custody/evidence --bar custody/bar.md" > custody/CHECK-COMMAND.txt
set +e; "${CHECK_CMD[@]}" > custody/CHECK-OUTPUT.json; CC=$?; set -e
[ "$CC" = 0 ] || { python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));[print(" ",k,v["status"],v["detail"]) for k,v in d.get("requirements",d).items() if isinstance(v,dict) and v.get("status")!="OK"]' custody/CHECK-OUTPUT.json || true; die "custody check.py exit $CC (not OK)"; }
REC_SHA=$(sha $REC)
REC_SHA="$REC_SHA" python3 - custody/record.x-plumbline-addendum.json <<'PY'
import json, os, sys
a = {"record": "custody/record.custody.json", "record_sha256": os.environ["REC_SHA"],
     "why": "The ff350e3 emitter that the bar requires has no pass-through for x-plumbline fields, so the bar's P6 "
            "spend and the Emitter limitation are written here, beside the record, and are not in it.",
     "x-plumbline": {
       "spend": {"model_calls_usd": 0.303493375, "basis": "OpenRouter key usage after batch 4 "
                 "(custody/evidence/eval/iter3-b4/n6--key-usage-after.json), the job's only key; EVAL-ITER3-VERDICT.md",
                 "grokbot_usd": None, "grokbot_note": "Grok Bot spend (Orchestrator, Maker operator, Evaluator bot) is "
                 "not visible to the job and is declared unverifiable."},
       "emitter": {"revision": "ff350e3", "tree": "4abcfa08f84d3b34849ad64bcfc281415772ffc1",
                   "limitation": "Known limitation: that emitter has gap 1 (producedAt), which this job repairs."}}}
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(a, indent=2) + "\n")
PY

# ---- 5. P5(e), scans, commit (local only) ----
python3 custody/freeze/instrument/p5check.py --job "$PWD" > P5-CHECK-close.json || die "P5(e) FAIL after close (P5-CHECK-close.json)"
[ "$(python3 -c 'import json;print(json.load(open("P5-CHECK-close.json"))["verdict"])')" = PASS ] || die "P5(e) verdict not PASS"
if grep -rlF -f /workspace/.openrouter-key "$J" "$RUNLOG" >/dev/null; then die "key scan hit, nothing committed"; fi
[ -z "$(find "$J" -name __pycache__ -newer CLOSE-apply.sh -print -quit)" ] || die "__pycache__ written in the job folder"
if grep -rlF "$CONTROLS" "$J" --exclude=CLOSE-apply.sh --exclude=close_inputs.py --exclude=custody.json \
     --exclude=record.custody.json --exclude='*.md' >/dev/null; then die "a held-out control path leaked into a file it should not be in"; fi
LED_NEW=$(sha $LED)
if [ "${CLOSE_NO_COMMIT:-0}" = 1 ]; then
  echo "DRY RUN: not committed. record $REC_SHA · ledger $LED_NEW"; trap - ERR; cleanup; exit 0; fi
git -C "$R" add -A -- "$J" "$RUNLOG"
git -C "$R" -c user.name="Steve Moitozo II" -c user.email="smoitozo@users.noreply.github.com" commit -q \
  -m "job 2026-10-27-custody-emitter-gaps: closed accepted, disposition $CLOSE_DISPOSITION (Owner)" \
  -m "Decided $CLOSE_DECIDED_AT via $CLOSE_CHANNEL. Iteration 3 (batch 4) PASS -> accepted. §5 record + custody/v1 record emitted by base main ff350e3 (tree $EMIT_TREE); check.py @ 3e3ca58 OK. record $REC_SHA; ledger $LED_NEW. bar.md unchanged $BAR_SHA; frozen manifest unchanged $MAN_SHA. P5(e) PASS (P5-CHECK-close.json). Not pushed."
trap - ERR; cleanup
echo "CLOSED. commit $(git -C "$R" rev-parse HEAD)"
echo "record $REC_SHA"; echo "ledger $LED_NEW"; echo "P5(e) PASS"
