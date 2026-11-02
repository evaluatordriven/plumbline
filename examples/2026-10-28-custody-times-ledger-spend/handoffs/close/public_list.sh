#!/usr/bin/env bash
# Build the public-path list for the held-out leak filter (job 2026-10-28-custody-times-ledger-spend close).
# Public = the tracked tree of the repo checkout R, the trees of the base and the three evaluated revisions, and the
# J1-J4 subject listings of each evaluated revision (custody/freeze/instrument/j_listing.py, which needs a checkout
# whose HEAD is the revision: detached worktrees under OUT, removed after). No network, no model call.
# Usage: public_list.sh R OUT   -> writes OUT/public-files.txt
set -euo pipefail
R="$(cd "$1" && pwd)"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"
case "$OUT" in /tmp/*) echo "public_list: nothing under /tmp" >&2; exit 1;; esac
JL="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/custody/freeze/instrument/j_listing.py"
LIST="$OUT/public-files.txt"
# tracked files, less every file the close itself added or changed (they are what is being scanned, so they cannot
# vouch for themselves). The close starts at the parent of the commit that added handoffs/close/import_close.py.
git -C "$R" ls-files | sort > "$OUT/tracked.txt"
ADD=$(git -C "$R" log --diff-filter=A --format=%H -- "dot-plumbline/jobs/2026-10-28-custody-times-ledger-spend/handoffs/close/import_close.py" | tail -1)
[ -n "$ADD" ] || { echo "public_list: close tooling commit not found" >&2; exit 1; }
git -C "$R" diff --name-only "$ADD^" HEAD | sort > "$OUT/close-changed.txt"
comm -23 "$OUT/tracked.txt" "$OUT/close-changed.txt" | sed "s|^|$R/|" > "$LIST"
for REV in 3df1ce5 1cb410b c882646 f95e0d3; do
  D="$OUT/pubrevs/$REV"; rm -rf "$D"; mkdir -p "$D"
  git -C "$R" archive "$REV" | tar -x -C "$D"
  find "$D" -type f >> "$LIST"
done
for REV in 1cb410b c882646 f95e0d3; do
  WT="$OUT/wt-$REV"; git -C "$R" worktree remove --force "$WT" >/dev/null 2>&1 || true
  git -C "$R" worktree add -q --detach "$WT" "$REV"
  for JK in J1 J2 J3 J4; do
    F="$OUT/listing-$REV-$JK.txt"
    python3 "$JL" --check $JK --rev "$WT" --out "$F" >/dev/null
    [ -s "$F" ] && echo "$F" >> "$LIST"
  done
  git -C "$R" worktree remove --force "$WT"
done
git -C "$R" worktree prune
echo "public_list: $(wc -l < "$LIST") paths -> $LIST"
