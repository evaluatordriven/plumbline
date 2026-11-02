#!/usr/bin/env python3
"""Pack one custody/v1 record and everything a stranger needs to re-read it into a single zip.

A stranger has the public custody checker (evaluatordriven/custody checker/check.py at the pinned commit) and
this zip — nothing of Plumbline, no corpus, no account. The zip therefore holds:

    record.custody.json        the record, byte for byte as emitted
    bar/<bar file>             the frozen bar the record's bar.digest names
    files/...                  the subject (the artifact files the record's subject names)
    evidence/...               every evaluator evidence file and harness log (checks, controls, external)
    inputs/custody-events.jsonl the live ledger the record's times and provider pins came from
    evidence/<harness log>     every maker/evaluator harness log the record's times or endpoints came from
    context/...                the job files the record digests besides those: maker method, instrument files,
                               control cases, the final §5 record and the packet (for a reader who wants them)
    MANIFEST.sha256            `sha256  path` for every file above (sha256sum -c compatible)
    README.txt                 the one command that re-reads it

The zip is deterministic (sorted entries, fixed timestamps and modes), so packing the same job twice gives the
same sha256. Nothing is fetched and nothing outside the job folder and the record is read.

    pack_stranger_bundle.py --job-dir <job> [--record FILE] --out bundle.zip

Prints the submission's stranger_bundle fields as JSON: zip path, zip sha256, and the in-zip paths of the
record, files, evidence and bar. Exit 0 packed · 1 a file the record names is missing (nothing written).
"""
from __future__ import annotations
import argparse, json, sys, zipfile
from hashlib import sha256
from pathlib import Path

FIXED = (1980, 1, 1, 0, 0, 0)


def h(b: bytes) -> str:
    return sha256(b).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Pack a custody record and its files for a stranger.")
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--record", help="the custody record (default: <job>/custody/record.custody.json)")
    ap.add_argument("--inputs", help="custody inputs (default: <job>/inputs/custody.json)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    job = Path(a.job_dir).expanduser().resolve()
    rec_path = Path(a.record).expanduser() if a.record else job / "custody" / "record.custody.json"
    ci_path = Path(a.inputs).expanduser() if a.inputs else job / "inputs" / "custody.json"
    if not rec_path.is_file():
        print(f"REFUSED: no record at {rec_path} — emit one first (kit/plumbline_job.py custody --job-dir ...) or pass --record"); return 1
    record = json.loads(rec_path.read_text(encoding="utf-8"))
    ci = json.loads(ci_path.read_text(encoding="utf-8")) if ci_path.is_file() else {}
    pred = record["predicate"]
    files_dir = job / ci.get("files_dir", "custody/files")
    ev_dir = job / ci.get("evidence_dir", "custody/evidence")
    entries: dict[str, bytes] = {"record.custody.json": rec_path.read_bytes()}
    missing = []

    def add(arc: str, src: Path):
        if src.is_file():
            entries[arc] = src.read_bytes()
        else:
            missing.append(f"{arc} <- {src}")

    bar_rel = (ci.get("bar") or {}).get("file")
    bar_arc = None
    if bar_rel:
        bar_arc = f"bar/{Path(bar_rel).name}"
        add(bar_arc, job / bar_rel)
    else:
        missing.append("bar file (not named in the custody inputs)")
    for s in record.get("subject") or []:
        add(f"files/{s['name']}", files_dir / s["name"])
    ev_names = set()
    for c in pred.get("checks") or []:
        if c.get("evidence"):
            ev_names.add(c["evidence"]["name"])
    for e in pred.get("external") or []:
        if e.get("evidence"):
            ev_names.add(e["evidence"]["name"])
    for v in pred.get("violations") or []:
        r = (v.get("x-plumbline") or {}).get("remedy")
        if r:
            ev_names.add(r["evidence"]["name"])
    for n in sorted(ev_names):
        add(f"evidence/{n}", ev_dir / n)

    # every maker/evaluator harness log the record's times or endpoints were read from (x-plumbline names them)
    harness = set()
    mkx = (pred.get("maker") or {}).get("x-plumbline") or {}
    if mkx.get("harness_log"):
        harness.add(mkx["harness_log"])
    for e in pred.get("evaluators") or []:
        ex = e.get("x-plumbline") or {}
        if ex.get("harness_log"):
            harness.add(ex["harness_log"])
    for n in sorted(harness):
        src = next((b / n for b in (ev_dir, job) if (b / n).is_file()), None)
        if src is not None:
            entries[f"evidence/{n}"] = src.read_bytes()
        else:
            missing.append(f"harness log {n} (named by the record's x-plumbline)")

    # the live ledger the record's times and provider pins came from (inputs/custody-events.jsonl)
    ev = (pred.get("x-plumbline") or {}).get("events_log")
    if ev and ev.get("name"):
        add(ev["name"], job / ev["name"])

    ctx = [(ci.get("maker") or {}).get("method_file"), *((ci.get("instrument") or {}).get(k) for k in ("rubric_file", "runner_file"))]
    for k in ci.get("controls") or []:
        ctx += [k.get("case_file"), k.get("evidence_file")]
    for e in ci.get("evaluators") or []:
        ctx.append((e.get("script") or {}).get("file"))
    for g in (ci.get("bar") or {}).get("groundTruth") or []:
        ctx.append(g.get("file"))
    xp = pred.get("x-plumbline") or {}
    ctx += [(xp.get("s5_record") or {}).get("name"), "packet.json"]
    for rel in sorted({c for c in ctx if c}):
        add(f"context/{rel}", job / rel)
    if missing:
        print("REFUSED: the bundle would not let a stranger re-read the record; missing:")
        for m in missing:
            print(f"  - {m}")
        return 1

    manifest = "".join(f"{h(entries[k])}  {k}\n" for k in sorted(entries))
    entries["MANIFEST.sha256"] = manifest.encode()
    entries["README.txt"] = (
        "custody/v1 stranger bundle (packed by Plumbline tools/pack_stranger_bundle.py)\n\n"
        "Verify the files:   sha256sum -c MANIFEST.sha256\n"
        "Re-read the record: git clone https://github.com/evaluatordriven/custody && git -C custody checkout "
        "3e3ca58de5631bdc58291564303a2e9d25a8653e\n"
        "                    python3 custody/checker/check.py record.custody.json --files files --evidence evidence"
        + (f" --bar {bar_arc}" if bar_arc else "") + "\n"
        "Re-derive times/endpoints: inputs/custody-events.jsonl is the live ledger; evidence/harness-*.log are the\n"
        "maker and evaluator harness logs named under the record's x-plumbline.\n").encode()
    out = Path(a.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for k in sorted(entries):
            zi = zipfile.ZipInfo(k, FIXED)
            zi.external_attr = 0o644 << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, entries[k])
    print(json.dumps({"zip": str(out), "sha256": h(out.read_bytes()), "record": "record.custody.json",
                      "files": "files", "evidence": "evidence", "bar": bar_arc,
                      "entries": len(entries)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
