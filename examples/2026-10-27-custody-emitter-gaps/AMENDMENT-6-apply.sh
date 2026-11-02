#!/usr/bin/env bash
# AMENDMENT-6 apply script — PENDING APPROVAL. Run ONLY after Steve approves AMENDMENT-6 (cap = 3 E-DI iterations) as Buyer.
# Fills AMENDMENT-6-cap.md, appends the ledger amendment n=6 line and the generation n=5 open line, runs P5(e),
# fills the gen-5 Maker handoff (Steve's words, ledger sha), regenerates handoffs/iter1/MANIFEST.sha256, and makes ONE
# local commit as Steve. No frozen file is touched. No push, no model call. No /tmp (scratch under /workspace/edi-work).
# Usage (from anywhere):
#   A6_WORDS='"<Steve verbatim>"' A6_DECIDED_AT=2026-10-28THH:MM:SSZ A6_CHANNEL='<channel / relay path>' \
#     bash dot-plumbline/jobs/2026-10-27-custody-emitter-gaps/AMENDMENT-6-apply.sh
set -euo pipefail
J="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; R="$(git -C "$J" rev-parse --show-toplevel)"; cd "$J"
W=/workspace/edi-work/2026-10-27-custody-emitter-gaps; mkdir -p "$W"; export TMPDIR="$W/tmp-amend6"; mkdir -p "$TMPDIR"
export PYTHONDONTWRITEBYTECODE=1
STARTED=0
die() { echo "AMENDMENT-6-apply: STOP: $*" >&2
        if [ "$STARTED" = 1 ]; then git -C "$R" checkout -q -- "$J" && rm -f "$J/P5-CHECK-amend6-gen5.json" && echo "  (job folder restored to HEAD; nothing committed)" >&2; fi
        exit 1; }
: "${A6_WORDS:?set A6_WORDS (Steve verbatim)}" "${A6_DECIDED_AT:?set A6_DECIDED_AT (UTC Z)}" "${A6_CHANNEL:?set A6_CHANNEL}"
[[ "$A6_DECIDED_AT" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] || die "A6_DECIDED_AT not YYYY-MM-DDTHH:MM:SSZ"
case "$A6_WORDS$A6_CHANNEL" in *"{{"*) die "words/channel contain a placeholder";; esac
sha() { sha256sum "$1" | cut -d' ' -f1; }
MAN=custody/MANIFEST.sha256; BAR=custody/bar.md; LED=inputs/custody-events.jsonl
DOC=AMENDMENT-6-cap.md; H=handoffs/iter3-maker.md; PROMPT=handoffs/iter3/maker-messages-gen5.json
MAN_SHA=f0ed1caf047e12eaa232df235343fae3b07603ac2fe5f8de0e293c93e8f680e7
BAR_SHA=3ced9bc04bfa2ae329bd57aff2197b9c49a3544f48cec2ccf8ce6469f22a970b
LED_OLD=7e28317a7f20c0a65da27d5843be2fc6aab1b3e07146af8cd341c2e202207641
PROMPT_SHA=d188cb80871fa959c43af2cde5588cc4ab8319eba00606ca212878f3662b0caa
BASE5=73863fb00c72239de0f0c2def4f68d1c6dfd902b

# ---- pre-checks: change nothing unless every one holds ----
[ "$(git -C "$R" rev-parse --abbrev-ref HEAD)" = job/2026-10-27-custody-emitter-gaps ] || die "not on the job branch"
[ -z "$(git -C "$R" status --porcelain -- "$J")" ] || die "job folder has uncommitted changes"
[ "$(sha $MAN)" = $MAN_SHA ] || die "custody/MANIFEST.sha256 is not the frozen manifest (as amended by A4)"
[ "$(sha $BAR)" = $BAR_SHA ] || die "bar.md digest changed"
( cd custody && sha256sum --quiet -c MANIFEST.sha256 ) || die "frozen set does not match its manifest"
[ "$(sha $LED)" = $LED_OLD ] || die "ledger is not ${LED_OLD:0:8}… (something was appended since the draft)"
tail -1 $LED | grep -q '"event": "evaluation", "iteration": 2, "batch": 3' || die "last ledger line is not the iteration-2 evaluation"
grep -q 'STATUS: PENDING APPROVAL' $DOC || die "$DOC is not pending"
grep -q '{{LEDGER_SHA_AFTER_A6}}' $H || die "$H has no ledger placeholder"
[ "$(sha $PROMPT)" = $PROMPT_SHA ] || die "gen-5 prompt sha changed"
python3 handoffs/build_maker_messages_gen5.py --repo "$R" --out "$W/check5-apply.json" && cmp -s "$W/check5-apply.json" $PROMPT || die "gen-5 prompt does not rebuild byte for byte"
git -C "$R" merge-base --is-ancestor $BASE5 HEAD && git -C "$R" diff --quiet $BASE5 HEAD -- kit tools docs tests || die "code at HEAD is not the gen-4 Maker commit's"
( cd "$J" && sha256sum --quiet -c handoffs/iter1/MANIFEST.sha256 ) || die "handoffs manifest does not verify"

# ---- 1. fill the amendment record ----
STARTED=1; trap 'die "unexpected error (line $LINENO)"' ERR
python3 - "$DOC" <<'PY'
import os, sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
s = s.replace("{{A6_WORDS}}", os.environ["A6_WORDS"]).replace("{{A6_DECIDED_AT}}", os.environ["A6_DECIDED_AT"]) \
     .replace("{{A6_CHANNEL}}", os.environ["A6_CHANNEL"])
old = s[s.index("> **STATUS: PENDING APPROVAL.**"):s.index("\n\n|")]
s = s.replace(old, "> **STATUS: APPLIED** by `AMENDMENT-6-apply.sh` after the Buyer's approval below.")
assert "{{" not in s; open(p, "w", encoding="utf-8").write(s)
PY
DOC_SHA=$(sha $DOC)

# ---- 2. ledger lines: amendment n=6, generation n=5 open ----
AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
AT="$AT" DOC_SHA="$DOC_SHA" DOC="$DOC" BASE5="$BASE5" PROMPT_SHA="$PROMPT_SHA" BAR_SHA="$BAR_SHA" python3 - "$LED" <<'PY'
import json, os, sys
E = os.environ
am = {"event": "amendment", "n": 6, "at": os.environ["AT"], "by": "Steve Moitozo II (S2)", "role": "buyer",
      "decided_at": os.environ["A6_DECIDED_AT"], "file": E["DOC"], "sha256": os.environ["DOC_SHA"],
      "terms": {"cap": 3, "cap_counts": "e-di iterations", "previous": {"cap": 4, "cap_counts": "generations", "by": "AMENDMENT-5"},
                "iteration": "one Maker turn (one generation) + one Evaluator scoring; a void batch does not count",
                "iterations": {"1": {"generations": [1, 2, 3], "batch": 2, "verdict": "fail"},
                               "2": {"generations": [4], "batch": 3, "verdict": "fail"},
                               "3": {"generations": [5], "batch": 4}},
                "maker_calls_per_generation": "no count limit; bounded by per_call and per_generation ceilings, job money cap and the handoff's call cutoffs",
                "per_call_ceiling_usd": 0.25, "per_generation_ceiling_usd": 1.00,
                "call_cutoffs": {"no_call_starts_after": "2026-10-28T15:05:00Z", "final_call_by": "2026-10-28T15:30:00Z"},
                "money_cap": "unchanged (< US$10)", "time_bound_end": "unchanged (2026-10-28T17:15:00Z, AMENDMENT-3)",
                "bar_sha256": "unchanged " + E["BAR_SHA"],
                "basis": "Steve, 2026-10-28T12:08Z, Chief of Staff chat t66u (verbatim in " + E["DOC"] + ")"},
      "recorded_by": "Chief of Staff (Orchestrator)",
      "note": "hand-appended by AMENDMENT-6-apply.sh (DECISIONS-2026-10-27.md D2 practice): post-freeze Buyer amendment restating the cap as 3 E-DI iterations; supersedes AMENDMENT-5's cap and its 4-calls-per-generation limit; frozen set unchanged; lifts iteration 2's needs_owner (cap_reached) so generation 5 (iteration 3, the last) can open"}
gen = {"event": "generation", "n": 5, "boundary": "open", "at": os.environ["AT"], "by": "Chief of Staff (Orchestrator)",
       "seat": "maker", "iteration": 3, "base_commit": E["BASE5"], "prompt_sha256": E["PROMPT_SHA"],
       "note": "hand-appended by AMENDMENT-6-apply.sh: kit/custody_ledger.py has no generation command (DECISIONS-2026-10-27.md D2, FOLLOW-UPS F1); cap 3 E-DI iterations per AMENDMENT-6, iteration 3 is the last; whole-file output protocol (D6), handoffs/iter3/maker-messages-gen5.json (built by handoffs/build_maker_messages_gen5.py: files at 73863fb, job-rejected fixture inputs, the Evaluator's iteration-2 N3 finding); no call-count limit within $0.25/call and $1.00/generation; flags --max-tokens 131072 --gen-tries 12 --gen-wait 20 (handoffs/iter3-maker.md)"}
with open(sys.argv[1], "a", encoding="utf-8") as f:
    f.write(json.dumps(am) + "\n"); f.write(json.dumps(gen) + "\n")
PY
LED_NEW=$(sha $LED)

# ---- 3. P5(e) ----
python3 custody/freeze/instrument/p5check.py --job "$PWD" > P5-CHECK-amend6-gen5.json || die "P5(e) FAIL after apply — see P5-CHECK-amend6-gen5.json; do not dispatch generation 5"
[ "$(python3 -c 'import json;print(json.load(open("P5-CHECK-amend6-gen5.json"))["verdict"])')" = PASS ] || die "P5(e) verdict not PASS"

# ---- 4. gen-5 handoff + handoffs manifest ----
python3 - "$H" "$LED_NEW" <<'PY'
import os, sys
p, led = sys.argv[1], sys.argv[2]; s = open(p, encoding="utf-8").read()
a = s.index("> **DO NOT DISPATCH"); b = s.index("(G1).\n", a) + len("(G1).\n")
s = s[:a] + "> AMENDMENT-6 applied; Steve's words and the ledger sha filled by `AMENDMENT-6-apply.sh`. Dispatch only after the apply\n> commit is on origin (G1).\n" + s[b:]
s = s.replace("{{LEDGER_SHA_AFTER_A6}}", led).replace("{{A6_WORDS}}", os.environ["A6_WORDS"]) \
     .replace("{{A6_DECIDED_AT}}", os.environ["A6_DECIDED_AT"]).replace("{{A6_CHANNEL}}", os.environ["A6_CHANNEL"])
assert "{{" not in s; open(p, "w", encoding="utf-8").write(s)
PY
sha256sum handoffs/iter1-maker.md handoffs/iter1-evaluator.md handoffs/iter1-evaluator-b2.md handoffs/build_maker_messages.py \
  handoffs/extract_patch.py handoffs/extract_files.py handoffs/test_extract_files.py handoffs/followup_messages.py \
  handoffs/iter1/maker-messages.json handoffs/iter1/maker-messages-gen3.json handoffs/iter1/README.md \
  handoffs/redact_glm_log.py handoffs/build_maker_messages_gen4.py handoffs/iter2-maker.md \
  handoffs/iter2-evaluator-b3.TEMPLATE.md handoffs/iter2/maker-messages-gen4.json handoffs/iter2/README.md \
  handoffs/iter2-evaluator-b3.md handoffs/build_maker_messages_gen5.py handoffs/iter3-maker.md \
  handoffs/iter3-evaluator-b4.TEMPLATE.md handoffs/iter3/maker-messages-gen5.json handoffs/iter3/README.md > handoffs/iter1/MANIFEST.sha256

# ---- 5. scans + commit (local only) ----
if grep -rlF -f /workspace/.openrouter-key "$J" >/dev/null; then die "key scan hit — nothing committed"; fi
[ -z "$(find "$J" -name __pycache__ -newer "$DOC" -print -quit)" ] || die "__pycache__ written in the job folder"
git -C "$R" add -- "$J/$DOC" "$J/$LED" "$J/P5-CHECK-amend6-gen5.json" "$J/$H" "$J/handoffs/iter1/MANIFEST.sha256"
git -C "$R" -c user.name="Steve Moitozo II" -c user.email="smoitozo@users.noreply.github.com" commit -q \
  -m "job 2026-10-27-custody-emitter-gaps: AMENDMENT-6 applied (Buyer) — cap 3 E-DI iterations; generation 5 opens" \
  -m "Decided $A6_DECIDED_AT. Ledger amendment n 6 and generation n 5 open at $AT (base $BASE5, prompt $PROMPT_SHA). bar.md unchanged $BAR_SHA; frozen manifest unchanged $MAN_SHA. P5(e) PASS (P5-CHECK-amend6-gen5.json). Not pushed."
echo "APPLIED. commit $(git -C "$R" rev-parse HEAD)"
echo "ledger      $LED_NEW"; echo "AMENDMENT-6 $DOC_SHA"; echo "gen5 handoff $(sha $H)"
echo "handoffs MANIFEST $(sha handoffs/iter1/MANIFEST.sha256)"; echo "prompt      $PROMPT_SHA"
echo "P5(e) PASS"
