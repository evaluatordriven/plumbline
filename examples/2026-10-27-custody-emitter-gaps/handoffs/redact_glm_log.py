#!/usr/bin/env python3
"""Redact an E-GLM harness log per DECISIONS D4 (job 2026-10-27-custody-emitter-gaps). No model calls.

For every logged call whose item (from N6-batch.json) is a held-out control (G-*): each request message content is
replaced by `[REDACTED held-out control <id> sha256 <digest of controls/glm/<id>.txt>] (message content sha256 <x>)`,
and the reply's content / reasoning / reasoning_details[].text by `[REDACTED reply to held-out control <id>; field
sha256 <x>]` (a reply may quote control code; stricter than D4's letter). The subject call is kept verbatim after a
check that no control line (>= 25 chars, bar the public `=== FILE <path> ===` headers) occurs in it. Writes OUT and OUT.full.sha256 (sha256 of the unredacted log).
Usage: redact_glm_log.py --log FULL.log --batch-json N6-batch.json --controls CONTROLS_DIR --out OUT
"""
import argparse, hashlib, json, sys
from pathlib import Path

H = lambda b: hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    for k in ("--log", "--batch-json", "--controls", "--out"):
        ap.add_argument(k, required=True)
    a = ap.parse_args()
    raw = Path(a.log).read_bytes()
    log = json.loads(raw)
    ids = {it["call"]: it["id"] for it in json.loads(Path(a.batch_json).read_text())["items"]}
    ctl = {}
    for p in sorted((Path(a.controls) / "glm").glob("G-*.txt")):
        ctl[p.stem] = (H(p.read_bytes()), [l.strip() for l in p.read_text().splitlines() if len(l.strip()) >= 25 and not l.startswith("=== FILE ")])
    for e in log:
        cid = ids.get(e["call"])
        if cid is None:
            print(f"call {e['call']} not in N6-batch.json", file=sys.stderr); return 2
        if cid.startswith("G-"):
            for m in e["request"]["body"]["messages"]:
                m["content"] = f"[REDACTED held-out control {cid} sha256 {ctl[cid][0]}] (message content sha256 {H(m['content'])})"
            for c in (e.get("response") or {}).get("choices") or []:
                msg = c.get("message") or {}
                for f in ("content", "reasoning"):
                    if msg.get(f) is not None:
                        msg[f] = f"[REDACTED reply to held-out control {cid}; field sha256 {H(msg[f])}]"
                for d in msg.get("reasoning_details") or []:
                    if d.get("text") is not None:
                        d["text"] = f"[REDACTED reply to held-out control {cid}; field sha256 {H(d['text'])}]"
    text = json.dumps(log, indent=2, ensure_ascii=False) + "\n"
    leaks = [(k, l[:40]) for k, (_, lines) in ctl.items() for l in lines if l in text]
    if leaks:
        print(f"control text still present after redaction: {leaks[:5]}", file=sys.stderr); return 3
    Path(a.out).write_text(text, encoding="utf-8")
    Path(a.out + ".full.sha256").write_text(f"{H(raw)}  {Path(a.log).name}\n", encoding="utf-8")
    print(json.dumps({"out": a.out, "out_sha256": H(text), "full_sha256": H(raw),
                      "redacted_calls": sorted(c for c, i in ids.items() if i.startswith("G-"))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
