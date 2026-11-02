#!/usr/bin/env bash
# STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z — S1 instrument, job 2026-10-27-custody-emitter-gaps (author: Chief of Staff (Orchestrator) drafter).
# S1 = this script + ncheck.py derive.py subject.py mutate.py p5check.py (stdlib python3, git). Needs nothing from the
# E-DI corpus, ~/.hermes or any credential. One batch per Maker generation; every batch runs all three parts.
#
#   run_instrument.sh batch REV CONTROLS OUT [REAL_JOB ...]
#       REV       checkout of the Maker's revision of smoitozo/plumbline (the subject)
#       CONTROLS  the batch's copy of the controls (held out; see controls/README.md)
#       OUT       evidence dir: OUT/controls/*.json, OUT/subject/N*.json, OUT/mutants/M-*.json, OUT/summary.json
#   run_instrument.sh controls CONTROLS OUT       controls only (instrument self-test)
#
# Env: CUSTODY_DIR  custody checkout (default: anonymous clone of the PUBLIC repo at the pin into a temp dir)
#      CONTROLS_MANIFEST  frozen sha256 list of the controls (default: ../../controls/MANIFEST.sha256 beside the
#                   freeze set); CONTROLS must match it byte for byte before anything runs (else exit 3).
# Exit: 0 every control as expected (subject verdicts are in summary.json, PASS or FAIL) · 1 a control missed
#       (batch void: re-run, counts against budget, not cap) · 2 usage · 3 pin mismatch.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
CUSTODY_URL="https://github.com/evaluatordriven/custody.git"
CUSTODY_PIN="3e3ca58de5631bdc58291564303a2e9d25a8653e"
SCHEMA_SHA="ad03af92b47eaa8079f1d2a8e759daa91148aac6f39d8935c22a92ba10199f9f"
CHECKPY_SHA="aaeb7e0532c950ee1736207b0a91ff9d810533fccecdb2c7708312408e5bcd18"
NC="python3 $HERE/ncheck.py"
note() { printf '%s\n' "$*"; }
sha()  { sha256sum "$1" | cut -d' ' -f1; }

pin_custody() {
  if [ -z "${CUSTODY_DIR:-}" ]; then
    CUSTODY_DIR="$(mktemp -d)/custody"
    GIT_TERMINAL_PROMPT=0 git -c credential.helper= clone -q "$CUSTODY_URL" "$CUSTODY_DIR" || { note "cannot clone $CUSTODY_URL"; exit 3; }
  fi
  ( cd "$CUSTODY_DIR" && git -c advice.detachedHead=false checkout -q "$CUSTODY_PIN" 2>/dev/null )
  [ "$(cd "$CUSTODY_DIR" && git rev-parse HEAD)" = "$CUSTODY_PIN" ] || { note "I0 custody not at pin"; exit 3; }
  [ "$(sha "$CUSTODY_DIR/schema/custody-v1.schema.json")" = "$SCHEMA_SHA" ] || { note "I0 schema digest differs"; exit 3; }
  [ "$(sha "$CUSTODY_DIR/checker/check.py")" = "$CHECKPY_SHA" ] || { note "I0 check.py digest differs"; exit 3; }
  CHECK="$CUSTODY_DIR/checker/check.py"
}

# run one N check; $1 evidence file, rest = ncheck args. Prints verdict.
nrun() { local ev="$1"; shift; $NC "$@" >"$ev" 2>"$ev.stderr"; python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1]))["verdict"])
except Exception: print("ERROR")' "$ev"; }

verify_controls() {  # $1 controls dir: every frozen file present with its frozen sha256
  local mf="${CONTROLS_MANIFEST:-$HERE/../../controls/MANIFEST.sha256}"
  [ -f "$mf" ] || { note "I0 no controls manifest at $mf"; exit 3; }
  ( cd "$1" && sha256sum --quiet -c "$mf" ) || { note "I0 controls differ from the frozen manifest"; exit 3; }
  note "== controls verified against $(basename "$mf") (sha256 $(sha "$mf"))"
}

controls() {  # $1 controls dir, $2 out
  local C="$1" O="$2/controls" bad=0 n rec d id chk want got s lc args; mkdir -p "$O"
  note "== C1 checker controls (custody's own fixtures @ pin): check.py must return each expected verdict"
  for rec in "$C"/checker/cases/*.json; do
    n="$(basename "$rec" .json)"
    python3 "$CHECK" "$rec" --files "$C/checker/files" --evidence "$C/checker/evidence" --bar "$C/checker/files/bar.md" >"$O/C1-$n.json" 2>&1
    if python3 - "$O/C1-$n.json" "$C/checker/expected.json" "$n" <<'PYX'
import json,sys
r=json.load(open(sys.argv[1])); e=json.load(open(sys.argv[2]))["cases"][sys.argv[3]]
fails=[k for k,v in (r.get("requirements") or {}).items() if v.get("status")=="FAILED"]
ok = r["verdict"]==e["verdict"] and r["levelAchieved"]==e["levelAchieved"] and r["routing"]==e["routing"] and (e["fails"] is None or e["fails"] in fails)
print(f'  C1 {sys.argv[3]:<44} expect {e["verdict"]:<13} got {r["verdict"]:<13} {"ok" if ok else "MISMATCH"}')
sys.exit(0 if ok else 1)
PYX
    then :; else bad=1; fi
  done
  note "== record-level controls: each clean control PASSes, each planted control FAILs, its named check(s)"
  for d in "$C"/record-level/*/; do
    d="${d%/}"; id="$(basename "$d")"
    for chk in $(python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))["expect"]))' "$d/CONTROL.json"); do
      want="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["expect"][sys.argv[2]])' "$d/CONTROL.json" "$chk")"
      args=(--job "$d/job")
      [ -f "$d/record.custody.json" ] && args+=(--record "$d/record.custody.json")
      [ -f "$d/emit.json" ] && args+=(--emit "$d/emit.json")
      [ -f "$d/check.json" ] && args+=(--check "$d/check.json")
      [ -f "$d/bundle.zip" ] && args+=(--bundle "$d/bundle.zip")
      lc="$(echo "$chk" | tr N n)"
      [ "$lc" = n8 ] && args=(--bundle "$d/bundle.zip")
      got="$(nrun "$O/$id-$chk.json" "$lc" "${args[@]}")"
      [ "$got" = "$want" ] && s=ok || { s=MISMATCH; bad=1; }
      printf '  %-8s %-3s expect %-4s got %-5s %s\n' "$id" "$chk" "$want" "$got" "$s"
    done
  done
  note "== P5(e) controls (amendment 2): p5check.py on each synthetic job folder"
  for d in "$C"/p5/*/; do
    d="${d%/}"; id="$(basename "$d")"
    want="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["expect"]["P5e"])' "$d/CONTROL.json")"
    python3 "$HERE/p5check.py" --job "$d" --record "$d/record.custody.json" >"$O/$id-P5e.json" 2>"$O/$id-P5e.json.stderr"
    got="$(python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1]))["verdict"])
except Exception: print("ERROR")' "$O/$id-P5e.json")"
    [ "$got" = "$want" ] && s=ok || { s=MISMATCH; bad=1; }
    printf '  %-8s %-3s expect %-4s got %-5s %s\n' "$id" "P5e" "$want" "$got" "$s"
  done
  return $bad
}

subject() {  # $1 rev, $2 fixtures, $3 out, rest real jobs
  local R="$1" F="$2" O="$3/subject"; shift 3; mkdir -p "$O/runs"
  note "== subject: $(git -C "$R" rev-parse HEAD) on the held-out fixtures"
  for f in F-genreply-full F-genreply-null F-maker-10min F-single-call; do
    python3 "$HERE/subject.py" --rev "$R" --fixture "$F/$f" --checkpy "$CHECK" --out "$O/runs/$f" >/dev/null
  done
  local i=0
  for j in "$R"/tests/fixtures/custody/*/ "$@"; do
    [ -f "${j%/}/inputs/custody.json" ] || continue; i=$((i+1))
    python3 "$HERE/subject.py" --rev "$R" --fixture "${j%/}" --checkpy "$CHECK" --out "$O/runs/extra-$i-$(basename "${j%/}")" >/dev/null
  done
  local r="$O/runs" v
  # N1: every run that wrote a record
  local n1=PASS
  for d in "$r"/*/; do d="${d%/}"; [ -f "$d/record.custody.json" ] || continue
    v="$(nrun "$O/N1-$(basename "$d").json" n1 --job "$d/job" --record "$d/record.custody.json")"; [ "$v" = PASS ] || n1=FAIL
    printf '  N1 on %-34s %s\n' "$(basename "$d")" "$v"
  done; echo "N1 $n1" >"$O/verdicts"
  m="$r/F-maker-10min"; full="$r/F-genreply-full"; null="$r/F-genreply-null"
  echo "N2 $(nrun "$O/N2.json" n2 --job "$m/job" --record "$m/record.custody.json")" >>"$O/verdicts"
  local n3=PASS
  for d in "$r"/*/; do d="${d%/}"; [ -f "$d/record.custody.json" ] || continue
    v="$(nrun "$O/N3-$(basename "$d").json" n3 --job "$d/job" --record "$d/record.custody.json")"; [ "$v" = PASS ] || n3=FAIL
  done; echo "N3 $n3" >>"$O/verdicts"
  echo "N4 $(nrun "$O/N4.json" n4 --job "$null/job" --emit "$null/emit.json" --record "$null/record.custody.json" --check "$null/check.json")" >>"$O/verdicts"
  echo "N5 $(nrun "$O/N5.json" n5 --job "$full/job" --emit "$full/emit.json" --record "$full/record.custody.json" --check "$full/check.json")" >>"$O/verdicts"
  local n7=PASS n8=PASS
  for d in "$m" "$full"; do b="$(basename "$d")"
    [ "$(nrun "$O/N7-$b.json" n7 --job "$d/job" --record "$d/record.custody.json" --bundle "$d/bundle.zip")" = PASS ] || n7=FAIL
    [ "$(nrun "$O/N8-$b.json" n8 --bundle "$d/bundle.zip")" = PASS ] || n8=FAIL
  done; echo "N7 $n7" >>"$O/verdicts"; echo "N8 $n8" >>"$O/verdicts"
  sed 's/^/  /' "$O/verdicts"
}

mutants() {  # $1 out (after subject): post-Maker planted controls, each must FAIL its check(s)
  local O="$1/mutants" r="$1/subject/runs" bad=0 M="python3 $HERE/mutate.py" m full null k v v7 v8 ck; mkdir -p "$O"
  note "== mutants of the subject's own outputs (planted; must FAIL)"
  m="$r/F-maker-10min"; full="$r/F-genreply-full"; null="$r/F-genreply-null"
  if [ -f "$m/record.custody.json" ]; then
    $M produced-eq-started --record "$m/record.custody.json" --out "$O/M-N2p.record.json"
    for k in n1 n2; do v="$(nrun "$O/M-N2p-$k.json" $k --job "$m/job" --record "$O/M-N2p.record.json")"
      [ "$v" = FAIL ] || bad=1; printf '  M-N2p  %s expect FAIL got %s\n' "$k" "$v"; done
  else note "  M-N2p  not buildable: subject wrote no record on F-maker-10min (N1/N2 already FAIL)"; fi
  local one="$r/F-single-call"
  if [ -f "$one/record.custody.json" ]; then
    $M produced-eq-started --record "$one/record.custody.json" --out "$O/M-N1p.record.json"
    v="$(nrun "$O/M-N1p-n1.json" n1 --job "$one/job" --record "$O/M-N1p.record.json")"
    [ "$v" = FAIL ] || bad=1; printf '  M-N1p  n1 expect FAIL got %s\n' "$v"
  else note "  M-N1p  not buildable: subject wrote no record on F-single-call (N1 already FAILs)"; fi
  if [ -f "$full/record.custody.json" ]; then
    cp "$full/emit.json" "$O/M-N5p.emit.json"; cp "$full/record.custody.json" "$O/M-N5p.record.json"; cp "$full/check.json" "$O/M-N5p.check.json"
    v="$(nrun "$O/M-N5p-n4.json" n4 --job "$null/job" --emit "$O/M-N5p.emit.json" --record "$O/M-N5p.record.json" --check "$O/M-N5p.check.json")"
    [ "$v" = FAIL ] || bad=1; printf '  M-N5p  n4 expect FAIL got %s\n' "$v"
  else note "  M-N5p  not buildable: subject wrote no record on F-genreply-full (N5 already FAILs)"; fi
  if [ -f "$m/bundle.zip" ]; then
    $M bundle-drop --zip "$m/bundle.zip" --out "$O/M-N9p.bundle.zip" --name custody-events.jsonl
    v7="$(nrun "$O/M-N9p-n7.json" n7 --job "$m/job" --record "$m/record.custody.json" --bundle "$O/M-N9p.bundle.zip")"
    v8="$(nrun "$O/M-N9p-n8.json" n8 --bundle "$O/M-N9p.bundle.zip")"
    ck="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["checkpy"]["verdict"])' "$O/M-N9p-n8.json" 2>/dev/null)"
    [ "$v7" = FAIL ] && [ "$v8" = FAIL ] || bad=1
    printf '  M-N9p  n7 expect FAIL got %s · n8 expect FAIL got %s · check.py %s (N9: expect OK)\n' "$v7" "$v8" "$ck"
  else note "  M-N9p  not buildable: no subject bundle (N7/N8 already FAIL)"; fi
  ( cd "$O" && sha256sum -- M-* >SHA256SUMS )
  return $bad
}

summary() {  # $1 out, $2 controls-ok, $3 mutants-ok
  python3 - "$1" "$2" "$3" <<'PY'
import json,sys,pathlib
o=pathlib.Path(sys.argv[1]); v={}
f=o/"subject/verdicts"
if f.is_file():
    v=dict(l.split() for l in f.read_text().splitlines() if l.strip())
s={"controls":"as expected" if sys.argv[2]=="0" else "MISMATCH (batch void)",
   "mutants":"as expected" if sys.argv[3]=="0" else ("MISMATCH (batch void)" if sys.argv[3]=="1" else "not run"),
   "subject":v,"scores":{k:(1 if x=="PASS" else 0) for k,x in v.items()}}
(o/"summary.json").write_text(json.dumps(s,indent=1)+"\n"); print(json.dumps(s))
PY
}

case "${1:-}" in
  controls) [ $# -eq 3 ] || { sed -n 2,16p "$0"; exit 2; }
            verify_controls "$2"; pin_custody; controls "$2" "$3"; c=$?; summary "$3" $c 2; exit $c ;;
  batch)    [ $# -ge 4 ] || { sed -n 2,16p "$0"; exit 2; }
            R="$2" C="$3" O="$4"; shift 4; verify_controls "$C"; pin_custody
            controls "$C" "$O"; c=$?
            subject "$R" "$C/fixtures" "$O" "$@"
            mutants "$O"; m=$?
            summary "$O" $c $m; [ $c = 0 ] && [ $m = 0 ]; exit $? ;;
  *) sed -n 2,16p "$0"; exit 2 ;;
esac
