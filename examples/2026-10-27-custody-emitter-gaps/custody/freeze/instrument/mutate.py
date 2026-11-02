#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z — S1 instrument, job 2026-10-27-custody-emitter-gaps (author: Chief of Staff (Orchestrator) drafter).
"""Deterministic mutations that build the planted controls (bar.md "S1 instrument", controls/README.md).
Every op reads one artifact and writes a new one; nothing is changed in place. JSON records are written with
indent=2, keys in source order, trailing newline; zips are rebuilt sorted, timestamps 1980-01-01, mode 0644,
with MANIFEST.sha256 regenerated (pack_stranger_bundle.py's conventions).

  mutate.py produced-eq-started --record R --out O          producedAt := startedAt   (M-N2p, C-N2p, M-N1p, C-N1p2)
  mutate.py logger-times --record R --job J --out O        startedAt/producedAt := the maker harness log's
        sent_at of the first call / received_at of the last call, whole seconds (what N1 requires)   (C-N1c)
  mutate.py endpoint --record R --seat S --host H --out O   one model seat's endpoint := H            (C-N5p2)
  mutate.py time-sources --record R --job J --out O [--misdirect PTR]
        add x-plumbline.timeSources: for each time field the first ledger line, else harness-log line,
        carrying the same instant; --misdirect PTR points PTR at the first maker call's Date line instead (C-N3p)
  mutate.py flag-null --record R --job J --out O
        for each null /generation reply: drop the seat's CL1-15 external[] entry, add x-plumbline.flags
        {flag: generation-reply-missing, pass, call}                                                (C-N4c-b)
  mutate.py bundle-add --zip Z --out O --add INZIP=PATH ...                                          (C-N9c)
  mutate.py bundle-drop --zip Z --out O --name BASENAME ...   (drops every entry with that basename) (C-N9p, M-N9p)
"""
from __future__ import annotations
import argparse, hashlib, json, sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import derive as D  # noqa: E402
import ncheck as N  # noqa: E402

FIXED = (1980, 1, 1, 0, 0, 0)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(obj, p):
    Path(p).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def xp(rec):
    return rec["predicate"].setdefault("x-plumbline", {})


def op_logger_times(a):
    r = load(a.record); job = Path(a.job)
    mlog = D.find_seat_log([N.ev_dir(job)], "maker", N.named_logs(job).get("maker"))
    t = D.maker_times(mlog)
    if not (t["startedAt"] and t["producedAt"]):
        print(f"no logger times in {mlog}: {t}", file=sys.stderr); return 1
    r["predicate"]["startedAt"], r["predicate"]["producedAt"] = t["startedAt"], t["producedAt"]; dump(r, a.out)


def op_produced_eq_started(a):
    r = load(a.record); r["predicate"]["producedAt"] = r["predicate"]["startedAt"]; dump(r, a.out)


def op_endpoint(a):
    r = load(a.record); p = r["predicate"]
    seat = p["maker"] if a.seat == "maker" else next(e for e in p["evaluators"] if e["id"] == a.seat)
    seat["model"]["endpoint"] = a.host; dump(r, a.out)


def candidates(job: Path) -> list[Path]:
    ev = N.ev_dir(job)
    return [N.ledger(job)] + sorted(ev.glob("harness-*.log"))


def first_line(files, val):
    want = D.iso(D.parse_iso(val))
    for f in files:
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if want in N.line_times(ln):
                return f, i
    return None


def op_time_sources(a):
    r = load(a.record); job = Path(a.job); files = [f for f in candidates(job) if f.is_file()]
    src = {}
    for ptr, val in N.time_fields(r["predicate"]):
        if val is None:
            continue
        hit = first_line(files, val)
        if hit is None:
            print(f"no line carries {ptr} = {val}", file=sys.stderr); return 1
        src[ptr] = {"file": str(hit[0].relative_to(job)), "line": hit[1]}
    if a.misdirect:
        mlog = D.find_seat_log([N.ev_dir(job)], "maker", N.named_logs(job).get("maker"))
        lines = mlog.read_text(encoding="utf-8").splitlines()
        i = next(i for i, ln in enumerate(lines, 1) if '"Date"' in ln)
        src[a.misdirect] = {"file": str(mlog.relative_to(job)), "line": i}
    xp(r)["timeSources"] = src; dump(r, a.out); return 0


def op_flag_null(a):
    r = load(a.record); job = Path(a.job); nulls = N.null_calls(job)
    seats = {n["evaluator"] for n in nulls}
    p = r["predicate"]
    p["external"] = [e for e in p.get("external") or [] if not (e.get("subject") in seats and e.get("requirement") == "CL1-15")]
    fl = xp(r).setdefault("flags", [])
    for n in nulls:
        fl.append({"flag": N.FLAG, "pass": n["pass"], "call": f"{n['log']}#{n['call']}"})
    dump(r, a.out)


def rebuild(entries: dict[str, bytes], out: Path):
    entries = {k: v for k, v in entries.items() if k != "MANIFEST.sha256"}
    man = "".join(f"{hashlib.sha256(entries[k]).hexdigest()}  {k}\n" for k in sorted(entries))
    entries["MANIFEST.sha256"] = man.encode()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for k in sorted(entries):
            zi = zipfile.ZipInfo(k, FIXED); zi.external_attr = 0o644 << 16; zi.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zi, entries[k])


def read_zip(z):
    with zipfile.ZipFile(z) as zf:
        return {n: zf.read(n) for n in zf.namelist() if not n.endswith("/")}


def op_bundle_add(a):
    e = read_zip(a.zip)
    for spec in a.add:
        k, _, p = spec.partition("="); e[k] = Path(p).read_bytes()
    rebuild(e, Path(a.out))


def op_bundle_drop(a):
    e = {k: v for k, v in read_zip(a.zip).items() if Path(k).name not in set(a.name)}
    rebuild(e, Path(a.out))


def main(argv=None):
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="op", required=True)
    for name in ("produced-eq-started", "logger-times", "endpoint", "time-sources", "flag-null"):
        s = sp.add_parser(name); s.add_argument("--record", required=True); s.add_argument("--out", required=True)
        if name == "endpoint":
            s.add_argument("--seat", required=True); s.add_argument("--host", required=True)
        if name in ("time-sources", "flag-null", "logger-times"):
            s.add_argument("--job", required=True)
        if name == "time-sources":
            s.add_argument("--misdirect")
    for name in ("bundle-add", "bundle-drop"):
        s = sp.add_parser(name); s.add_argument("--zip", required=True); s.add_argument("--out", required=True)
        if name == "bundle-add":
            s.add_argument("--add", nargs="+", required=True)
        else:
            s.add_argument("--name", nargs="+", required=True)
    a = ap.parse_args(argv)
    return {"produced-eq-started": op_produced_eq_started, "logger-times": op_logger_times, "endpoint": op_endpoint, "time-sources": op_time_sources,
            "flag-null": op_flag_null, "bundle-add": op_bundle_add, "bundle-drop": op_bundle_drop}[a.op](a) or 0


if __name__ == "__main__":
    sys.exit(main())
