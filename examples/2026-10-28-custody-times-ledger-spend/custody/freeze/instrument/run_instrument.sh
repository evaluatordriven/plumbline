#!/usr/bin/env bash
# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — instrument entry point, job 2026-10-28-custody-times-ledger-spend (author: Chief of Staff (Orchestrator) drafter).
# S1 = scheck.py + lib.py + drivers.py + judges.py + t4_build.py + t6_subject.py (frozen venv python, git).
# E-GLM = jbatch.py + j_listing.py + rubric-J1..J4.md (+ fixtures/doctrine/ for J3), calls through ../harness/or_call.py (spend guard).
#
#   run_instrument.sh s1  REV CONTROLS OUT [--only ID,ID]    one S1 batch: every instrument control, then the subject
#   run_instrument.sh glm REV CONTROLS OUT BATCH LEDGER       one E-GLM batch each for J1, J2, J3, J4 (pin from LEDGER)
#
# CONTROLS = the batch's copy of the held-out controls; it must match CONTROLS_MANIFEST (default
# ../../controls/MANIFEST.sha256 beside the freeze set) byte for byte before anything runs (else exit 3).
# Env: TMPDIR must be set and must not be under /tmp (job rule). PY = frozen venv python (default the jsv venv).
#      S1_LIVE=1 turns on F8d's live arm (shared key by path; never printed). BASE/CUSTODY/CORPUS default below.
# Exit (s1): scheck's code: 0 all PASS · 1 some FAIL · 3 void (a control missed, or controls/pin mismatch) · 2 usage.
# Exit (glm): 0 all four batches ran (verdicts in OUT/J*/J*-batch.json; "void" there = re-run) · 2 usage · 3 mismatch.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
BASEREV=3df1ce52eddfe18705e380c4b6e99cf617cfa24b
PY="${PY:-/workspace/edi-work/2026-10-27-custody-emitter-gaps/jsv/bin/python}"
BASE="${S1_BASE:-/workspace/edi-work/2026-10-28-custody-times-ledger-spend/base}"
CUSTODY="${S1_CUSTODY:-/workspace/plumbline-job/src/custody}"
CORPUS="${S1_CORPUS:-/workspace/plumbline-job/src/e-di-a48a464}"
export PYTHONDONTWRITEBYTECODE=1
note() { printf '%s\n' "$*"; }
sha()  { sha256sum "$1" | cut -d' ' -f1; }
case "${TMPDIR:-}" in ""|/tmp|/tmp/*) note "set TMPDIR to a job work dir (not /tmp)"; exit 2;; esac
mkdir -p "$TMPDIR"

verify_controls() {
  local mf="${CONTROLS_MANIFEST:-$HERE/../../controls/MANIFEST.sha256}"
  [ -f "$mf" ] || { note "I0 no controls manifest at $mf"; exit 3; }
  ( cd "$1" && sha256sum --quiet -c "$mf" ) || { note "I0 controls differ from the frozen manifest"; exit 3; }
  note "== controls verified against $(basename "$mf") (sha256 $(sha "$mf"))"
}
need_base() {
  git -C "$1" cat-file -e "$BASEREV^{commit}" 2>/dev/null || { note "base $BASEREV not in $1"; exit 3; }
  [ "$(git -C "$BASE" rev-parse HEAD)" = "$BASEREV" ] || { note "base checkout $BASE is not $BASEREV"; exit 3; }
}

case "${1:-}" in
  s1)
    [ $# -ge 4 ] || { note "usage: run_instrument.sh s1 REV CONTROLS OUT [--only ID,ID]"; exit 2; }
    REV="$(cd "$2" && pwd)"; C="$(cd "$3" && pwd)"; O="$4"; shift 4; mkdir -p "$O"
    need_base "$REV"; verify_controls "$C"
    "$PY" "$HERE/scheck.py" --subject "$REV" --base "$BASE" --custody "$CUSTODY" --controls "$C" \
      --work "$O/work" --corpus "$CORPUS" --python "$PY" --out "$O" "$@"
    rc=$?; note "== S1 exit $rc"; exit $rc ;;
  glm)
    [ $# -eq 6 ] || { note "usage: run_instrument.sh glm REV CONTROLS OUT BATCH LEDGER"; exit 2; }
    REV="$(cd "$2" && pwd)"; C="$(cd "$3" && pwd)"; O="$4"; B="$5"; LG="$6"; mkdir -p "$O"
    need_base "$REV"; verify_controls "$C"
    for J in J1 J2 J3 J4; do
      python3 "$HERE/jbatch.py" --check "$J" --rev "$REV" --controls "$C" --batch "$B" --out "$O/$J" --ledger "$LG" \
        || { note "jbatch $J failed"; exit 3; }
    done; exit 0 ;;
  *) note "usage: run_instrument.sh s1 REV CONTROLS OUT [--only ID,ID] | glm REV CONTROLS OUT BATCH LEDGER"; exit 2 ;;
esac
