#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — E-GLM batch runner (J1, J2, J3, J4), job 2026-10-28-custody-times-ledger-spend (author: Chief of Staff (Orchestrator) drafter).
"""One E-GLM reading batch for J1, J2, J3 or J4: the subject plus that check's held-out controls, each sent as its own
logged call with the same rubric, model, params and provider pin, in a per-batch seeded order (subject unmarked).

  jbatch.py --check J1|J2|J3|J4 --rev REV --controls CONTROLS --batch N --out OUT
            (--ledger LEDGER | --tag z-ai/fp8 --pin-provider Z.AI) [--harness OR_CALL] [--only ID[,ID]] [--dry-run]

Items: subject = j_listing.py --check <J> of REV; controls = CONTROLS/glm/<J>/<id>/listing.txt with
CONTROLS/glm/expected.json[<J>]. Order: random.Random("<J>-batch-<N>").shuffle(sorted ids incl. "subject").
Each call: or_call.py --seat E-GLM --model z-ai/glm-5.3-flash, temperature 0, max_tokens = endpoint max (131072,
enforced by or_call.py), no reasoning limit, --log OUT/harness-E-GLM-<J>-b<N>.log --call <J>-b<N>-<k>,
--gen-tries 12 --gen-wait 20. or_call.py's job spend guard applies to every call; every log entry carries
finish_reason. One try per item: no re-send inside a batch (a re-run is a new batch number).
Writes OUT/<J>-batch.json (order; per item: call, id, messages sha256, or_call exit, finish_reason, verdict, LINES,
control_ok) and OUT/<J>-<call>.json per item (the evidence file the bar names).
Result: <J> PASS iff every control reads its expected verdict (a planted control must also cite a line within
WINDOW lines of its planted line) and the subject reads CONFORMS; FAIL if the controls are right and the subject
does not read CONFORMS; void if any control misses or any call did not return a reply (or_call exit != 0 and != 5).
--only (live test before freeze) sends only the named ids; --dry-run builds the messages only.
"""
from __future__ import annotations
import argparse, hashlib, json, random, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
from j_listing import listing  # noqa: E402

MODEL, SEAT, WINDOW = "z-ai/glm-5.3-flash", "E-GLM", 2
# J3 (G-faithful) reads the guide against the pinned doctrine, copied verbatim under fixtures/doctrine/ (CC BY 4.0; third-party bytes, so no FROZEN-BUILD header)
DOCTRINE = HERE / "fixtures" / "doctrine" / "DOCTRINE-dc61854.md"
DOCTRINE_SHA256 = "c9b45567f27738ca33662162e44fec121b1e840f34522fd9eb64e8fd3d49d6ed"


def parse(reply: str) -> dict:
    v = re.findall(r"VERDICT:\s*\**\s*(CONFORMS|DOES_NOT_CONFORM)", reply or "")
    ln = re.search(r"LINES:\s*(.*)", reply or "")
    lines = re.findall(r"([\w./-]+\.(?:py|md)):(\d+)", ln.group(1)) if ln else []
    return {"verdict": v[-1] if v and len(set(v)) == 1 else None, "lines": [f"{f}:{n}" for f, n in lines]}


def rubric(check: str) -> str:
    t = (HERE / f"rubric-{check}.md").read_text(encoding="utf-8")
    t = t.split("-->", 1)[1].lstrip() if t.startswith("<!--") else t
    if "{{DOCTRINE}}" in t:
        b = DOCTRINE.read_bytes()
        if hashlib.sha256(b).hexdigest() != DOCTRINE_SHA256:
            raise SystemExit("jbatch: doctrine copy does not match its pin; nothing sent")
        t = t.replace("{{DOCTRINE}}", b.decode("utf-8"))
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    for x in ("--check", "--rev", "--controls", "--out", "--batch"):
        ap.add_argument(x, required=True)
    ap.add_argument("--ledger"); ap.add_argument("--tag"); ap.add_argument("--pin-provider")
    ap.add_argument("--harness", default=str(HERE.parent / "harness" / "or_call.py"))
    ap.add_argument("--only"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    J = a.check
    if J not in ("J1", "J2", "J3", "J4"):
        ap.error("--check J1|J2|J3|J4")
    if not a.dry_run and not (a.ledger or (a.tag and a.pin_provider)):
        ap.error("--ledger or --tag + --pin-provider")
    C, out = Path(a.controls) / "glm", Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    exp = json.loads((C / "expected.json").read_text())[J]
    items = {"subject": listing(J, a.rev)}
    for cid in sorted(exp):
        items[cid] = (C / J / cid / "listing.txt").read_text(encoding="utf-8")
    order = sorted(items); random.Random(f"{J}-batch-{a.batch}").shuffle(order)
    if a.only:
        keep = a.only.split(","); order = [i for i in order if i in keep]
    log = out / f"harness-{SEAT}-{J}-b{a.batch}.log"
    pin = ["--ledger", a.ledger] if a.ledger else ["--tag", a.tag, "--pin-provider", a.pin_provider]
    rub, rows = rubric(J), []
    for k, iid in enumerate(order, 1):
        call = f"{J}-b{a.batch}-{k}"
        mf = out / f"{call}.messages.json"
        mf.write_text(json.dumps([{"role": "user", "content": rub + items[iid]}], ensure_ascii=False))
        row = {"call": call, "id": iid, "messages_sha256": hashlib.sha256(mf.read_bytes()).hexdigest()}
        if not a.dry_run:
            rf = out / f"{call}.reply.txt"
            p = subprocess.run([sys.executable, a.harness, "--seat", SEAT, "--model", MODEL, *pin, "--log", str(log),
                                "--call", call, "--messages", str(mf), "--out", str(rf), "--temperature", "0",
                                "--gen-tries", "12", "--gen-wait", "20"], capture_output=True, text=True)
            row["or_call_exit"] = p.returncode
            row["or_call_stderr"] = p.stderr[-2000:]
            try:
                row["finish_reason"] = json.loads(p.stdout.strip().splitlines()[-1]).get("finish_reason")
            except Exception:
                row["finish_reason"] = None
            if row["finish_reason"] is None and log.is_file():
                # exits 5 and 10 print no stdout line; the harness log entry for this call carries finish_reason
                try:
                    hit = [e for e in json.loads(log.read_text()) if e.get("call") == call]
                    row["finish_reason"] = hit[-1].get("finish_reason") if hit else None
                except Exception:
                    pass
            row["reply_sha256"] = hashlib.sha256(rf.read_bytes()).hexdigest() if rf.is_file() else None
            row.update(parse(rf.read_text(encoding="utf-8") if rf.is_file() else ""))
        rows.append(row)
    res = {"check": J, "batch": a.batch, "order": order, "items": rows, "log": log.name, "dry_run": a.dry_run,
           "window": WINDOW}
    if not a.dry_run:
        ctl_ok, calls_ok = True, all(r["or_call_exit"] in (0, 5) for r in rows)
        for r in rows:
            if r["id"] == "subject":
                continue
            e = exp[r["id"]]
            ok = r.get("verdict") == e["verdict"]
            if ok and e.get("cite"):
                f, want = e["cite"]["file"], e["cite"]["lines"]
                ok = any(x.rsplit(":", 1)[0] == f and any(abs(int(x.rsplit(":", 1)[1]) - w) <= WINDOW for w in want)
                         for x in r.get("lines", []))
            r["control_ok"] = ok; ctl_ok &= ok
        subj = next((r for r in rows if r["id"] == "subject"), None)
        res.update({"controls_ok": ctl_ok, "calls_ok": calls_ok})
        if subj is not None:
            res["subject_verdict"] = subj.get("verdict")
            res[J] = ("void" if not (ctl_ok and calls_ok) else
                      ("PASS" if subj.get("verdict") == "CONFORMS" else "FAIL"))
        for r in rows:
            (out / f"{J}-{r['call']}.json").write_text(json.dumps({"check": J, "batch": a.batch, **r}, indent=1) + "\n")
    (out / f"{J}-batch.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: res[k] for k in res if k != "items"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
