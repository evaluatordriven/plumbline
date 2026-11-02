#!/usr/bin/env python3
"""Redact and merge one batch's E-GLM harness logs (job 2026-10-28-custody-times-ledger-spend close). No model calls.
Adapted from 2026-10-28-doctrine-reader-pointer/handoffs/close/redact_glm_log.py.

This job ran E-GLM as four checks (J1-J4), one harness log and one batch file each:
  <glm-dir>/Jk/harness-E-GLM-Jk-b<N>.log and <glm-dir>/Jk/Jk-batch.json.
The base emitter reads one harness log per evaluator, so the four logs are merged into one list, in sent_at order,
each entry unchanged except: for every call whose batch item is a held-out control (G-*), each request message
content is replaced by `[REDACTED held-out control <id> sha256 <digest of glm/Jk/<id>/listing.txt>] (message content
sha256 <x>)`, and the reply's content / reasoning / reasoning_details[].text|summary by `[REDACTED reply to held-out
control <id>; field sha256 <x>]`. Subject calls are kept verbatim.

Also writes, into --evidence-out: each Jk-batch.json with the control items' `lines` removed (their sha256 and
verdicts kept), and each subject call's reply text. Writes OUT and OUT.full.sha256 (the four full logs, by digest).
Usage: redact_glm_log.py --glm-dir DIR --batch N --controls CONTROLS_DIR --out OUT --evidence-out DIR
"""
import argparse, hashlib, json, sys
from pathlib import Path

H = lambda b: hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()
CHECKS = ("J1", "J2", "J3", "J4")


def main() -> int:
    ap = argparse.ArgumentParser()
    for k in ("--glm-dir", "--batch", "--controls", "--out", "--evidence-out"):
        ap.add_argument(k, required=True)
    a = ap.parse_args()
    G, C, EO = Path(a.glm_dir), Path(a.controls), Path(a.evidence_out)
    EO.mkdir(parents=True, exist_ok=True)
    merged, full, redacted, subj = [], [], [], {}
    for j in CHECKS:
        logp = G / j / f"harness-E-GLM-{j}-b{a.batch}.log"
        raw = logp.read_bytes()
        full.append(f"{H(raw)}  {logp.name}")
        batch = json.loads((G / j / f"{j}-batch.json").read_text(encoding="utf-8"))
        ids = {it["call"]: it["id"] for it in batch["items"]}
        for e in json.loads(raw):
            cid = ids.get(e["call"])
            if cid is None:
                print(f"call {e['call']} not in {j}-batch.json", file=sys.stderr); return 2
            if cid.startswith("G-"):
                dig = H((C / "glm" / j / cid / "listing.txt").read_bytes())
                for m in e["request"]["body"]["messages"]:
                    m["content"] = f"[REDACTED held-out control {cid} sha256 {dig}] (message content sha256 {H(m['content'])})"
                for c in (e.get("response") or {}).get("choices") or []:
                    msg = c.get("message") or {}
                    for f in ("content", "reasoning"):
                        if msg.get(f) is not None:
                            msg[f] = f"[REDACTED reply to held-out control {cid}; field sha256 {H(msg[f])}]"
                    for d in msg.get("reasoning_details") or []:
                        for f in ("text", "summary"):
                            if isinstance(d.get(f), str):
                                d[f] = f"[REDACTED reply to held-out control {cid}; field sha256 {H(d[f])}]"
                redacted.append(e["call"])
            merged.append(e)
        for it in batch["items"]:
            if it["id"].startswith("G-"):
                it.pop("lines", None)
                it["lines_removed"] = "held-out control: line numbers would locate the planted edit"
            else:
                rp = G / j / f"{it['call']}.reply.txt"
                (EO / rp.name).write_bytes(rp.read_bytes())
                subj[j] = it["call"]
        (EO / f"{j}-batch.json").write_text(json.dumps(batch, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    merged.sort(key=lambda e: e["sent_at"])
    if len({e["call"] for e in merged}) != len(merged):
        print("duplicate call names across the J logs", file=sys.stderr); return 2
    text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
    Path(a.out).write_text(text, encoding="utf-8")
    Path(a.out + ".full.sha256").write_text(
        f"# full (unredacted) E-GLM harness logs of batch {a.batch}, held on the Owner's box; merged and redacted "
        f"into {Path(a.out).name} by handoffs/close/redact_glm_log.py\n" + "\n".join(full) + "\n", encoding="utf-8")
    print(json.dumps({"out": a.out, "out_sha256": H(text), "calls": len(merged), "redacted_calls": sorted(redacted),
                      "subject_calls": subj}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
