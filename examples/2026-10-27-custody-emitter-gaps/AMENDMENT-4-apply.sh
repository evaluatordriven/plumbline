#!/usr/bin/env bash
# AMENDMENT-4 apply script — PENDING APPROVAL. Run ONLY after Steve approves AMENDMENT-4 as Buyer.
# Makes the frozen-file edit (n6_batch.py max-tokens 800 -> 131072), regenerates custody/MANIFEST.sha256,
# fills AMENDMENT-4-n6-max-tokens.md, appends the ledger amendment line, runs P5(e), fills the batch-2 handoff's
# ledger sha, regenerates handoffs/iter1/MANIFEST.sha256, and makes ONE local commit as Steve. No push, no model call.
# Usage (from anywhere):
#   A4_WORDS='"<Steve verbatim>"' A4_DECIDED_AT=2026-10-28THH:MM:SSZ A4_CHANNEL='<channel / relay path>' \
#     bash dot-plumbline/jobs/2026-10-27-custody-emitter-gaps/AMENDMENT-4-apply.sh
set -euo pipefail
J="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; R="$(git -C "$J" rev-parse --show-toplevel)"; cd "$J"
STARTED=0
die() { echo "AMENDMENT-4-apply: STOP: $*" >&2
        if [ "$STARTED" = 1 ]; then git -C "$R" checkout -q -- "$J" && rm -f "$J/P5-CHECK-amend4.json" && echo "  (job folder restored to HEAD; nothing committed)" >&2; fi
        exit 1; }
: "${A4_WORDS:?set A4_WORDS (Steve verbatim)}" "${A4_DECIDED_AT:?set A4_DECIDED_AT (UTC Z)}" "${A4_CHANNEL:?set A4_CHANNEL}"
[[ "$A4_DECIDED_AT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || die "A4_DECIDED_AT not YYYY-MM-DDTHH:MM:SSZ"
sha() { sha256sum "$1" | cut -d' ' -f1; }
N6=custody/freeze/instrument/n6_batch.py; MAN=custody/MANIFEST.sha256; BAR=custody/bar.md; LED=inputs/custody-events.jsonl
DOC=AMENDMENT-4-n6-max-tokens.md; H=handoffs/iter1-evaluator-b2.md; P=AMENDMENT-4-n6_batch.patch
N6_OLD=965f6d9098462160e68716ae1ec3256dee896357700c3cc1ae9dad0b629859bd; N6_NEW=616760242939ae5da88310909a84ce9e6bd464f0e55ae7005f2714d7d749ee81
MAN_OLD=2e9a77fb60a57bdfe889ab7075734c71e62eb67696a7f678a082d8007937dcdd; MAN_NEW=f0ed1caf047e12eaa232df235343fae3b07603ac2fe5f8de0e293c93e8f680e7
BAR_SHA=3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b; LED_OLD=4b03278bbc5908a303ef444ee94129100b5fab3d17edf9397eba97f6ee0990b3
PATCH_SHA=1c91d6158dda43337d159fb0548b1b5bf15722cfe937d40eabbfb983f84dc269
SNAP=AMENDMENT-4-glm-endpoints-2026-10-28T112909Z.json; SNAP_SHA=fb14ed6c1daaf949a99db3e9aeffd4cd35c394c418c835fa3bf851d10dde8a46

# ---- pre-checks: change nothing unless every one holds ----
[ "$(git -C "$R" rev-parse --abbrev-ref HEAD)" = job/2026-10-27-custody-emitter-gaps ] || die "not on the job branch"
[ -z "$(git -C "$R" status --porcelain -- "$J")" ] || die "job folder has uncommitted changes"
[ "$(sha $N6)" = $N6_OLD ] || die "n6_batch.py is not the frozen bytes"
[ "$(sha $MAN)" = $MAN_OLD ] || die "custody/MANIFEST.sha256 is not the frozen manifest"
[ "$(sha $BAR)" = $BAR_SHA ] || die "bar.md digest changed"
[ "$(sha $LED)" = $LED_OLD ] || die "ledger is not 4b03278b… (something was appended since the draft)"
[ "$(sha $P)" = $PATCH_SHA ] && [ "$(sha $SNAP)" = $SNAP_SHA ] || die "patch or endpoint snapshot changed"
grep -q 'STATUS: PENDING APPROVAL' $DOC || die "$DOC is not pending"
grep -q '{{LEDGER_SHA_AFTER_A4}}' $H || die "$H has no ledger placeholder"
( cd custody && sha256sum --quiet -c MANIFEST.sha256 ) || die "frozen set does not match its manifest"
git -C "$R" apply --check "$J/$P" || die "patch does not apply"

# ---- 1. frozen edit + manifest ----
STARTED=1; trap 'die "unexpected error (line $LINENO)"' ERR
git -C "$R" apply "$J/$P"
[ "$(sha $N6)" = $N6_NEW ] || die "patched n6_batch.py sha mismatch"
sed -i "s#^$N6_OLD  freeze/instrument/n6_batch.py\$#$N6_NEW  freeze/instrument/n6_batch.py#" $MAN
[ "$(sha $MAN)" = $MAN_NEW ] || die "new manifest sha mismatch"
( cd custody && sha256sum --quiet -c MANIFEST.sha256 ) || die "manifest check failed after edit"
[ "$(sha $BAR)" = $BAR_SHA ] || die "bar.md changed"

# ---- 2. fill the amendment record ----
python3 - "$DOC" <<'PY'
import os, sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
s = s.replace("{{A4_WORDS}}", os.environ["A4_WORDS"]).replace("{{A4_DECIDED_AT}}", os.environ["A4_DECIDED_AT"]) \
     .replace("{{A4_CHANNEL}}", os.environ["A4_CHANNEL"])
old = s[s.index("> **STATUS: PENDING APPROVAL.**"):s.index("\n\n|")]
s = s.replace(old, "> **STATUS: APPLIED** by `AMENDMENT-4-apply.sh` after the Buyer's approval below.")
assert "{{" not in s; open(p, "w", encoding="utf-8").write(s)
PY
DOC_SHA=$(sha $DOC)

# ---- 3. ledger line ----
AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
AT="$AT" DOC_SHA="$DOC_SHA" python3 - "$LED" <<PY
import json, os, sys
ev = {"event": "amendment", "n": 4, "at": os.environ["AT"], "by": "Steve Moitozo II (S2)", "role": "buyer",
      "decided_at": os.environ["A4_DECIDED_AT"], "file": "$DOC", "sha256": os.environ["DOC_SHA"],
      "terms": {"n6_batch_max_tokens": {"from": 800, "to": 131072},
                "n6_batch_sha256": {"from": "$N6_OLD", "to": "$N6_NEW"},
                "manifest_sha256": {"from": "$MAN_OLD", "to": "$MAN_NEW"},
                "bar_sha256": "unchanged $BAR_SHA",
                "source": {"url": "https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints",
                           "fetched_at": "2026-10-28T11:29:09Z", "snapshot": "$SNAP", "snapshot_sha256": "$SNAP_SHA",
                           "endpoint": "z-ai/fp8", "max_completion_tokens": 131072}},
      "recorded_by": "Chief of Staff (Orchestrator)",
      "note": "hand-appended by AMENDMENT-4-apply.sh (same practice as amendment 3, DECISIONS-2026-10-27.md D2): post-freeze Buyer amendment of one frozen instrument value; E-GLM batch 1 void (EVAL-ITER1-BATCH1-VOID.md); no reasoning params; FROZEN-BUILD header of n6_batch.py unchanged"}
open(sys.argv[1], "a", encoding="utf-8").write(json.dumps(ev) + "\n")
PY
LED_NEW=$(sha $LED)

# ---- 4. P5(e) ----
python3 custody/freeze/instrument/p5check.py --job "$PWD" > P5-CHECK-amend4.json || die "P5(e) FAIL after apply — see P5-CHECK-amend4.json; do not dispatch batch 2"

# ---- 5. batch-2 handoff + handoffs manifest ----
python3 - "$H" "$LED_NEW" <<'PY'
import sys
p, led = sys.argv[1], sys.argv[2]; s = open(p, encoding="utf-8").read()
a = s.index("> **DO NOT DISPATCH"); b = s.index("\n\n", a)
s = s[:a] + "> AMENDMENT-4 applied; ledger sha filled by `AMENDMENT-4-apply.sh`. Dispatch only after the apply commit is pushed (E1)." + s[b:]
s = s.replace("{{LEDGER_SHA_AFTER_A4}}", led)
assert "{{" not in s; open(p, "w", encoding="utf-8").write(s)
PY
sha256sum handoffs/iter1-maker.md handoffs/iter1-evaluator.md handoffs/iter1-evaluator-b2.md handoffs/build_maker_messages.py \
  handoffs/extract_patch.py handoffs/extract_files.py handoffs/test_extract_files.py handoffs/followup_messages.py \
  handoffs/iter1/maker-messages.json handoffs/iter1/maker-messages-gen3.json handoffs/iter1/README.md > handoffs/iter1/MANIFEST.sha256

# ---- 6. key scan + commit (local only) ----
if grep -rlF -f /workspace/.openrouter-key "$J" >/dev/null; then die "key scan hit — nothing committed"; fi
git -C "$R" add -- "$J/$N6" "$J/$MAN" "$J/$DOC" "$J/$LED" "$J/P5-CHECK-amend4.json" "$J/$H" "$J/handoffs/iter1/MANIFEST.sha256"
git -C "$R" -c user.name="Steve Moitozo II" -c user.email="smoitozo@users.noreply.github.com" commit -q \
  -m "job 2026-10-27-custody-emitter-gaps: AMENDMENT-4 applied (Buyer) — n6_batch.py max-tokens 800 -> 131072" \
  -m "n6_batch.py $N6_OLD -> $N6_NEW; custody/MANIFEST.sha256 $MAN_OLD -> $MAN_NEW; bar.md unchanged $BAR_SHA. Decided $A4_DECIDED_AT; ledger amendment n 4 at $AT; P5(e) PASS (P5-CHECK-amend4.json). Not pushed."
echo "APPLIED. commit $(git -C "$R" rev-parse HEAD)"
echo "n6_batch.py $N6_NEW"; echo "MANIFEST    $MAN_NEW"; echo "bar.md      $(sha $BAR)"
echo "ledger      $LED_NEW"; echo "AMENDMENT-4 $DOC_SHA"; echo "b2 handoff  $(sha $H)"; echo "handoffs MANIFEST $(sha handoffs/iter1/MANIFEST.sha256)"
echo "P5(e) $(python3 -c 'import json;print(json.load(open("P5-CHECK-amend4.json"))["verdict"])')"
