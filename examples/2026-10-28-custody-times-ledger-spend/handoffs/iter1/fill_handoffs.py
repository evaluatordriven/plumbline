#!/usr/bin/env python3
"""Fill the iteration-1 MAKER.md / EVALUATOR.md from their templates, AFTER Steve's digest approval is in the ledger.

Refuses (exit 3) unless: the freeze set verifies; the ledger's freeze event carries the frozen bar sha; and the ledger has
an approve event for role buyer AND role specialist, by Steve Moitozo II, kind person, with barDigest = that sha.
Every value is read from the committed job folder at the approval commit (no value is typed in), except the digest
words/time/message id, which come from Steve's own message and must equal the line APPROVE-apply.sh appended.
Usage: fill_handoffs.py --repo JOBWT --words W --time T --msgid M
"""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
JOB = "dot-plumbline/jobs/2026-10-28-custody-times-ledger-spend"
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def die(m): print("fill_handoffs: " + m + ": STOP", file=sys.stderr); sys.exit(3)
a = argparse.ArgumentParser(); a.add_argument("--repo", required=True)
for k in ("words", "time", "msgid"): a.add_argument("--" + k, required=True)
a = a.parse_args(); R = Path(a.repo); J = R / JOB
if subprocess.run(["git", "-C", str(R), "status", "--porcelain", "--", JOB], capture_output=True, text=True).stdout.strip():
    die("job folder has uncommitted changes (commit the approval first)")
if subprocess.run(["sha256sum", "--quiet", "-c", "MANIFEST.sha256"], cwd=J / "custody").returncode: die("freeze set changed")
bar = sha(J / "custody/bar.md")
ev = [json.loads(l) for l in (J / "inputs/custody-events.jsonl").read_text().splitlines() if l.strip()]
fz = [e for e in ev if e.get("event") == "freeze"]
if len(fz) != 1 or fz[0].get("bar_sha256") != bar: die("ledger freeze event does not carry the frozen bar sha")
for role in ("buyer", "specialist"):
    if not any(e.get("event") == "approve" and e.get("role") == role and e.get("by") == "Steve Moitozo II"
               and e.get("kind") == "person" and e.get("barDigest") == bar for e in ev):
        die(f"no {role} approve event by Steve Moitozo II for bar {bar}")
rec = (J / "OWNER-APPROVAL-RECORD.md").read_text()
line = f'- {a.time} ({a.msgid}), S2, approves the frozen digest: "{a.words}"'
if line not in rec: die("the digest words/time/message id are not the line APPROVE-apply.sh recorded")
import re
m = re.search(r"^time_end: (\S+Z) = (.+?); no model call", (J / "custody/bounds").read_text(), re.M)
if not m: die("custody/bounds has no time_end line")
b = {"time_end_utc": m.group(1), "time_end_local": m.group(2)}
I = J / "custody/freeze/instrument"
vals = {"TIME_END_LOCAL": b["time_end_local"], "TIME_END_UTC": b["time_end_utc"],
        "DIGEST_TIME_MSG": f"{a.time}, {a.msgid}", "DIGEST_WORDS": a.words,
        "APPROVAL_HEAD": subprocess.run(["git", "-C", str(R), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
        "BAR": bar, "MAN": sha(J / "custody/MANIFEST.sha256"), "LEDGER": sha(J / "inputs/custody-events.jsonl"),
        "HARNESS": sha(J / "custody/freeze/harness/or_call.py"), "CMAN": sha(J / "custody/controls/MANIFEST.sha256"),
        "RUNI": sha(I / "run_instrument.sh"), "SCHECK": sha(I / "scheck.py"), "JBATCH": sha(I / "jbatch.py")}
for name in ("MAKER", "EVALUATOR"):
    t = (HERE / f"{name}.template.md").read_text()
    for k, v in vals.items(): t = t.replace(f"@@{k}@@", v)
    if "@@" in t: die(f"{name}: unfilled placeholder")
    (HERE / f"{name}.md").write_text(t); print(name + ".md", sha(HERE / f"{name}.md"))
