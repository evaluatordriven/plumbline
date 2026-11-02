#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z — E-GLM batch builder for N6, job 2026-10-27-custody-emitter-gaps (author: Chief of Staff (Orchestrator) drafter).
"""One N6 judging batch: the subject code path plus the held-out GLM controls, each sent as its own logged
call with the same rubric, model, params and provider pin, in a seeded random order (the subject unmarked).

  n6_batch.py --rev REV --controls CONTROLS --batch N --out OUT --ledger LEDGER [--dry-run]

Items: subject = REV's kit/emit_custody.py and kit/custody_history.py as a numbered listing;
controls = CONTROLS/glm/G-*.txt (same listing format) with CONTROLS/glm/expected.json.
Order: random.Random("n6-batch-<N>").shuffle over [subject, G-c1, G-p1] (sorted ids first).
Each call: or_call.py --seat eval-glm --model z-ai/glm-5.3-flash --ledger LEDGER (pin z-ai/fp8)
--log OUT/harness-eval-glm-b<N>.log --call n6-b<N>-<k> --temperature 0 --max-tokens 131072.
Writes OUT/N6-batch.json: order, per item {call, id (subject|G-*), messages sha256, reply verdict, LINES,
or_call exit}, control outcomes, and the subject verdict: score 1 iff the subject reads CONFORMS and every
control reads its expected verdict (a planted control must also cite a line in its marked span).
A control miss voids the batch (re-run; counts against budget, not cap). --dry-run builds the messages only.
"""
from __future__ import annotations
import argparse, hashlib, json, random, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = "z-ai/glm-5.3-flash"
FILES = ("kit/emit_custody.py", "kit/custody_history.py")


def listing(files: list[tuple[str, str]]) -> str:
    out = []
    for name, text in files:
        out.append(f"=== FILE {name} ===")
        out += [f"{i:5d}| {ln}" for i, ln in enumerate(text.splitlines(), 1)]
    return "\n".join(out) + "\n"


def parse(reply: str) -> dict:
    v = re.search(r"VERDICT:\s*(CONFORMS|DOES_NOT_CONFORM)", reply or "")
    ln = re.search(r"LINES:\s*(.*)", reply or "")
    lines = re.findall(r"([\w./-]+\.py):(\d+)", ln.group(1)) if ln else []
    return {"verdict": v.group(1) if v else None, "lines": [f"{f}:{n}" for f, n in lines]}


def main() -> int:
    ap = argparse.ArgumentParser()
    for a in ("--rev", "--controls", "--out", "--ledger"):
        ap.add_argument(a, required=True)
    ap.add_argument("--batch", type=int, required=True); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rev, C, out = Path(a.rev), Path(a.controls) / "glm", Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rubric = (HERE / "rubric-N6.md").read_text(encoding="utf-8")
    rubric = rubric.split("-->", 1)[1].lstrip() if rubric.startswith("<!--") else rubric
    exp = json.loads((C / "expected.json").read_text())
    items = {"subject": listing([(f, (rev / f).read_text(encoding="utf-8")) for f in FILES])}
    for cid in sorted(exp):
        items[cid] = (C / f"{cid}.txt").read_text(encoding="utf-8")
    order = sorted(items); random.Random(f"n6-batch-{a.batch}").shuffle(order)
    log = out / f"harness-eval-glm-b{a.batch}.log"
    rows = []
    for k, iid in enumerate(order, 1):
        call = f"n6-b{a.batch}-{k}"
        msgs = [{"role": "user", "content": rubric + items[iid]}]
        mf = out / f"{call}.messages.json"
        mf.write_text(json.dumps(msgs, ensure_ascii=False))
        row = {"call": call, "id": iid, "messages_sha256": hashlib.sha256(mf.read_bytes()).hexdigest()}
        if not a.dry_run:
            rf = out / f"{call}.reply.txt"
            p = subprocess.run([sys.executable, str(HERE.parent / "harness/or_call.py"), "--seat", "eval-glm",
                                "--model", MODEL, "--ledger", a.ledger, "--log", str(log), "--call", call,
                                "--messages", str(mf), "--out", str(rf), "--temperature", "0", "--max-tokens", "131072"],
                               capture_output=True, text=True)
            row["or_call_exit"] = p.returncode
            row.update(parse(rf.read_text(encoding="utf-8") if rf.is_file() else ""))
        rows.append(row)
    res = {"batch": a.batch, "order": order, "items": rows, "log": log.name, "dry_run": a.dry_run}
    if not a.dry_run:
        ctl_ok = True
        for r in rows:
            if r["id"] == "subject":
                continue
            e = exp[r["id"]]
            ok = r.get("verdict") == e["verdict"]
            if ok and e.get("cite"):
                f, lo, hi = e["cite"]["file"], e["cite"]["from"], e["cite"]["to"]
                ok = any(x.split(":")[0].endswith(f) and lo <= int(x.split(":")[1]) <= hi for x in r.get("lines", []))
            r["control_ok"] = ok; ctl_ok &= ok
        subj = next(r for r in rows if r["id"] == "subject")
        res.update({"controls_ok": ctl_ok, "subject_verdict": subj.get("verdict"),
                    "N6": ("void" if not ctl_ok else ("PASS" if subj.get("verdict") == "CONFORMS" else "FAIL"))})
    (out / "N6-batch.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: res[k] for k in res if k != "items"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
