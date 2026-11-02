#!/usr/bin/env bash
# Writes Steve's two ledger approve events for job 2026-10-28-custody-times-ledger-spend. RUN ONLY AFTER Steve Moitozo II
# has himself approved the frozen bar digest below (see OWNER-APPROVAL-RECORD.md). An agent's report is not an approval.
# Usage: APPROVE-apply.sh --dry-run | --apply "<Steve's verbatim words>" "<time EDT>" "<message id>"
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(git -C "$HERE" rev-parse --show-toplevel)"
JOB="dot-plumbline/jobs/2026-10-28-custody-times-ledger-spend"
BAR=72e92dc7580e2447f19dfff66aaac02d8484157a6283dcfdda6c7bb2de7561c6
MAN=acdf764b32bab5e0fa4615590714c49162cbbaecddd00c03c6d8121b59b85d98
cd "$REPO"
[ "$(sha256sum "$JOB/custody/bar.md" | cut -d' ' -f1)" = "$BAR" ] || { echo "bar changed since freeze: STOP"; exit 3; }
[ "$(sha256sum "$JOB/custody/MANIFEST.sha256" | cut -d' ' -f1)" = "$MAN" ] || { echo "manifest changed since freeze: STOP"; exit 3; }
( cd "$JOB/custody" && sha256sum --quiet -c MANIFEST.sha256 ) || { echo "freeze set changed: STOP"; exit 3; }
CMD1=(python3 kit/custody_ledger.py approve --job-dir "$JOB" --role buyer --by "Steve Moitozo II")
CMD2=(python3 kit/custody_ledger.py approve --job-dir "$JOB" --role specialist --by "Steve Moitozo II"
      --adopted-document "Owner sheet items 1-30 (OWNER-APPROVAL.md) + Plumbline DOCTRINE.md v0.1 @ dc61854" --adopted-version "v0.1")
case "${1:-}" in
  --dry-run) echo "would run: ${CMD1[*]@Q}"; echo "would run: ${CMD2[*]@Q}"; echo "bar $BAR, manifest $MAN: unchanged";;
  --apply) [ $# -eq 4 ] || { echo "--apply needs Steve's words, time, message id"; exit 2; }
     "${CMD1[@]}"; "${CMD2[@]}"
     printf -- '- %s (%s), S2, approves the frozen digest: "%s"\n' "$3" "$4" "$2" >> "$JOB/OWNER-APPROVAL-RECORD.md"
     sha256sum "$JOB/inputs/custody-events.jsonl";;
  *) echo "usage: $0 --dry-run | --apply WORDS TIME MSGID"; exit 2;;
esac
