#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-27T21:53:35Z — S1 instrument, job 2026-10-27-custody-emitter-gaps (author: Chief of Staff (Orchestrator) drafter).
"""S1 checks N1-N5, N7, N8 (bar.md). Each prints one JSON object {check, verdict PASS|FAIL, why[], ...} and
exits 0 on PASS, 1 on FAIL, 2 on usage error. Inputs are files only: a job folder, the record it got, the
emitter's exit/output (emit.json), check.py's output (check.json), a stranger bundle zip.

  ncheck.py n1 --job J --record R
  ncheck.py n2 --job J --record R                     (fixture F-maker-10min: Δ must be 600 s)
  ncheck.py n3 --job J --record R
  ncheck.py n4 --job J --emit EMIT.json [--record R] [--check CHECK.json]
  ncheck.py n5 --job J --emit EMIT.json --record R --check CHECK.json
  ncheck.py n7 --job J --record R --bundle Z
  ncheck.py n8 --bundle Z                             (stranger: env -i, empty HOME, anonymous clone of custody)

emit.json = {"exit": int, "stdout": str, "stderr": str, "record_written": bool}.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import derive as D  # noqa: E402

CUSTODY_URL = "https://github.com/evaluatordriven/custody.git"
CUSTODY_PIN = "3e3ca58de5631bdc58291564303a2e9d25a8653e"
CHECKPY_SHA = "aaeb7e0532c950ee1736207b0a91ff9d810533fccecdb2c7708312408e5bcd18"
FLAG = "generation-reply-missing"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def jl(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def inputs(job: Path) -> dict:
    p = job / "inputs" / "custody.json"
    return jl(p) if p.is_file() else {}


def ev_dir(job: Path) -> Path:
    return job / inputs(job).get("evidence_dir", "custody/evidence")


def named_logs(job: Path) -> dict:
    ci = inputs(job)
    out = {"maker": (ci.get("maker") or {}).get("harness_log")}
    for e in ci.get("evaluators") or []:
        out[e["id"]] = e.get("harness_log")
    return {k: v for k, v in out.items() if v}


def ledger(job: Path) -> Path:
    return job / "inputs" / "custody-events.jsonl"


def result(check: str, why: list[str], **kw) -> dict:
    return {"check": check, "verdict": "FAIL" if why else "PASS", "why": why, **kw}


# ---------------------------------------------------------------- N1 / N2
def n1(job: Path, rec: dict) -> dict:
    """Amendment 1: startedAt = or_call.py `sent_at` of the first Maker call, producedAt = `received_at` of the
    last, read from the maker harness log. Equal times only when the log's send and receive are equal."""
    d = D.derive(rec, [ev_dir(job)], ledger(job), named_logs(job))
    r = D.recorded(rec)
    why = []
    if not d.get("maker_log"):
        why.append("no maker harness log: nothing to derive the times from")
    elif d["events"] == 0:
        why.append("the maker harness log has no call entries")
    elif d.get("missing_logger_times"):
        why.append(f"maker call(s) without the logger's sent_at/received_at: {d['missing_logger_times']}")
    for k, src in (("startedAt", "sent_at of the first maker call"), ("producedAt", "received_at of the last maker call")):
        if not D.same_instant(r[k], d[k]):
            why.append(f"{k}: record {r[k]!r} != {src} {d[k]!r}")
    if r["startedAt"] and D.same_instant(r["startedAt"], r["producedAt"]) and not D.same_instant(d["startedAt"], d["producedAt"]):
        why.append(f"startedAt == producedAt but the log's send {d['startedAt']!r} != receive {d['producedAt']!r}")
    return result("N1", why, record=r, derived={k: d.get(k) for k in ("maker_log", "events", "missing_logger_times", "startedAt", "producedAt")})


def n2(job: Path, rec: dict) -> dict:
    out = n1(job, rec)
    r = out["record"]
    why = list(out["why"])
    s, p = D.parse_iso(r["startedAt"]), D.parse_iso(r["producedAt"])
    delta = (p - s).total_seconds() if s and p else None
    if delta != 600:
        why.append(f"producedAt - startedAt = {delta} s, not 600 s")
    return result("N2", why, delta_s=delta, n1=out)


# ---------------------------------------------------------------- N3
ISO_RE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)")
RFC_RE = re.compile(r"[A-Z][a-z]{2}, \d{1,2} [A-Z][a-z]{2} \d{4} \d\d:\d\d:\d\d GMT")
EPOCH_RE = re.compile(r"(?<![\d.])(1\d{9})(?:\.\d+)?(?![\d])")


def line_times(line: str) -> set[str]:
    out = set()
    for m in ISO_RE.findall(line):
        t = D.parse_iso(m)
        if t:
            out.add(D.iso(t))
    for m in RFC_RE.findall(line):
        out.add(D.iso(parsedate_to_datetime(m)))
    for m in EPOCH_RE.findall(line):
        out.add(D.iso(datetime.fromtimestamp(int(m), timezone.utc)))
    return out


def time_fields(pred: dict) -> list[tuple[str, str]]:
    """(JSON pointer, value) of every time field bar N3 names."""
    out = []
    bar = pred.get("bar") or {}
    out.append(("/bar/frozenAt", bar.get("frozenAt")))
    for i, a in enumerate(bar.get("approvals") or []):
        out.append((f"/bar/approvals/{i}/at", a.get("at")))
    out += [("/startedAt", pred.get("startedAt")), ("/producedAt", pred.get("producedAt"))]
    for i, c in enumerate(pred.get("checks") or []):
        out.append((f"/checks/{i}/at", c.get("at")))
    out.append(("/disposition/at", (pred.get("disposition") or {}).get("at")))
    return out


def resolve(job: Path, f: str) -> Path | None:
    for p in (job / f, ev_dir(job) / Path(f).name, job / "inputs" / Path(f).name):
        if p.is_file():
            return p
    return None


SOURCE_KEYS = ("timeSources", "time_sources", "times")
FLAG_KEYS = ("flags", "gaps", "warnings")


def norm_ptr(k: str) -> str:
    """'/checks/0/at', 'checks[0].at', 'checks.0.at', 'predicate.startedAt', 'frozenAt' -> RFC 6901 pointer."""
    k = str(k).strip()
    k = re.sub(r"^(/?predicate[./])", "", k)
    parts = [x for x in re.split(r"[./\[\]]+", k) if x]
    if parts and parts[0] in ("frozenAt", "approvals"):
        parts = ["bar"] + parts
    return "/" + "/".join(parts)


def parse_src(v):
    if isinstance(v, dict):
        f = next((v[k] for k in ("file", "name", "path", "log") if isinstance(v.get(k), str)), None)
        ln = next((v[k] for k in ("line", "lineno", "line_number") if isinstance(v.get(k), int)), None)
        return {"file": f, "line": ln} if f and ln else None
    if isinstance(v, str):
        m = re.match(r"^(.+?)(?::|#L| line )(\d+)$", v.strip())
        return {"file": m.group(1), "line": int(m.group(2))} if m else None
    return None


def source_map(pred: dict) -> tuple[dict, list[str]]:
    """Field pointer -> {file, line}, read from x-plumbline.timeSources | time_sources | times (first wins)."""
    xpl = pred.get("x-plumbline") or {}
    out, used = {}, []
    for key in SOURCE_KEYS:
        m = xpl.get(key)
        if not isinstance(m, dict):
            continue
        for k, v in m.items():
            s = parse_src(v)
            if s and norm_ptr(k) not in out:
                out[norm_ptr(k)] = s
                if key not in used:
                    used.append(key)
    return out, used


def n3(job: Path, rec: dict) -> dict:
    pred = rec.get("predicate", rec)
    srcs, used = source_map(pred)
    why, rows = [], []
    if not srcs:
        return result("N3", ["no time field names a {file, line} source in x-plumbline (timeSources | time_sources | times)"],
                      fields=[p for p, _ in time_fields(pred)])
    for ptr, val in time_fields(pred):
        row = {"field": ptr, "value": val}
        s = srcs.get(ptr)
        if val is None:
            rows.append({**row, "verdict": "n/a (field absent)"}); continue
        if not s:
            why.append(f"{ptr} = {val}: no {{file, line}} source in x-plumbline"); rows.append(row); continue
        f = resolve(job, s["file"])
        base = Path(s["file"]).name
        if f is None or not (base == "custody-events.jsonl" or base.startswith("harness-")):
            why.append(f"{ptr}: source file {s['file']!r} is not a ledger or harness log in the job"); rows.append(row); continue
        lines = f.read_text(encoding="utf-8").splitlines()
        if not 1 <= s["line"] <= len(lines):
            why.append(f"{ptr}: {s['file']} has no line {s['line']}"); rows.append(row); continue
        have = line_times(lines[s["line"] - 1])
        want = D.iso(D.parse_iso(val)) if D.parse_iso(val) else val
        ok = want in have
        if not ok:
            why.append(f"{ptr} = {val}: {s['file']}:{s['line']} carries {sorted(have) or 'no time'}")
        rows.append({**row, "source": s, "line_text": lines[s["line"] - 1].strip()[:200], "verdict": "PASS" if ok else "FAIL"})
    return result("N3", why, source_keys=used, fields=rows)


# ---------------------------------------------------------------- N4 / N5
def null_calls(job: Path) -> list[dict]:
    """Model-evaluator calls whose /api/v1/generation reply is missing or null, with the pass/control they serve."""
    ci = inputs(job)
    by_call = {}
    for pid, p in (ci.get("passes") or {}).items():
        by_call[(p.get("evaluator"), p.get("call"))] = pid
    for k in ci.get("controls") or []:
        by_call[(k.get("evaluator"), k.get("call"))] = k.get("id")
    out = []
    for e in ci.get("evaluators") or []:
        if e.get("kind") != "model":
            continue
        lg = D.find_seat_log([ev_dir(job)], e["id"], e.get("harness_log"))
        if not lg:
            continue
        for c in D.load_log(lg):
            if not isinstance(c.get("generation"), dict):
                out.append({"evaluator": e["id"], "call": c.get("call"), "log": lg.name,
                            "pass": by_call.get((e["id"], c.get("call")))})
    return out


def endpoint_problems(job: Path, rec: dict) -> tuple[list[str], dict]:
    d = D.derive(rec, [ev_dir(job)], ledger(job), named_logs(job))
    r = D.recorded(rec)
    why = []
    for seat, ep in r["endpoints"].items():
        want = (d["endpoints"].get(seat) or {}).get("endpoint")
        if want is None:
            why.append(f"{seat}: endpoint {ep!r} written but no generation reply evidences the pinned provider "
                       f"({(d['endpoints'].get(seat) or {}).get('why')})")
        elif ep != want:
            why.append(f"{seat}: endpoint {ep!r} is not the host of the provider the replies name ({want!r})")
    return why, d


def flags(rec: dict) -> list[str]:
    """Every x-plumbline flags | gaps | warnings entry that is about a missing /generation reply, as text."""
    xpl = rec.get("predicate", rec).get("x-plumbline") or {}
    out = []
    for key in FLAG_KEYS:
        for f in xpl.get(key) or []:
            t = f if isinstance(f, str) else json.dumps(f, sort_keys=True)
            if "generation" in t.lower():
                out.append(t)
    return out


def flag_names(fl: list[str], n: dict) -> bool:
    """An entry names the null pass: its pass/control id as a whole token, or its call name."""
    pid, call = n.get("pass"), n.get("call")
    return any((pid and re.search(rf"(?<![\w-]){re.escape(pid)}(?![\w-])", t)) or (call and call in t) for t in fl)


def n4(job: Path, emit: dict, rec: dict | None, chk: dict | None) -> dict:
    nulls = null_calls(job)
    why = []
    if not nulls:
        return result("N4", ["fixture has no null /generation reply: wrong fixture"], nulls=nulls)
    out_text = (emit.get("stdout") or "") + "\n" + (emit.get("stderr") or "")
    names = {n["pass"] for n in nulls if n["pass"]} | {n["call"] for n in nulls if n["call"]}
    mode = None
    if emit.get("exit") not in (0, 1):
        mode = "a (refusal)"
        if rec is not None or emit.get("record_written"):
            why.append("non-zero exit but a record was written")
        if not any(nm and nm in out_text for nm in names):
            why.append(f"refusal does not name the pass/call with the missing reply ({sorted(names)})")
    else:
        mode = "b (NOT-CHECKABLE + flag)"
        if rec is None:
            why.append(f"exit {emit.get('exit')} but no record")
        else:
            st = (((chk or {}).get("requirements") or {}).get("CL1-15") or {}).get("status")
            if st != "NOT-CHECKABLE":
                why.append(f"check.py CL1-15 is {st!r}, not NOT-CHECKABLE")
            fl = flags(rec)
            for n in nulls:
                if not flag_names(fl, n):
                    why.append(f"no x-plumbline flag about the missing generation reply naming {n['pass']!r} "
                               f"({n['log']}#{n['call']})")
            epw, _ = endpoint_problems(job, rec)
            why += epw
    return result("N4", why, mode=mode, exit=emit.get("exit"), nulls=nulls,
                  check_CL1_15=(((chk or {}).get("requirements") or {}).get("CL1-15") if chk else None))


def n5(job: Path, emit: dict, rec: dict | None, chk: dict | None) -> dict:
    why = []
    if null_calls(job):
        why.append("fixture has a null /generation reply: wrong fixture")
    if emit.get("exit") != 0 or rec is None:
        why.append(f"emitter exit {emit.get('exit')} / record {'present' if rec else 'absent'}: N4's procedure did not pass")
        return result("N5", why, exit=emit.get("exit"))
    if (chk or {}).get("verdict") != "OK":
        why.append(f"check.py verdict {(chk or {}).get('verdict')!r}, not OK")
    st = (((chk or {}).get("requirements") or {}).get("CL1-15") or {}).get("status")
    if st != "OK":
        why.append(f"check.py CL1-15 {st!r}, not OK")
    if flags(rec):
        why.append("an x-plumbline flag about a missing generation reply is set although every reply is present")
    epw, d = endpoint_problems(job, rec)
    why += epw
    return result("N5", why, exit=emit.get("exit"), endpoints={"recorded": D.recorded(rec)["endpoints"],
                  "from_replies": {k: v.get("endpoint") for k, v in d["endpoints"].items()}})


# ---------------------------------------------------------------- N7
def zip_index(z: Path) -> dict[str, str]:
    with zipfile.ZipFile(z) as zf:
        return {n: hashlib.sha256(zf.read(n)).hexdigest() for n in zf.namelist() if not n.endswith("/")}


def n7(job: Path, rec_path: Path, z: Path) -> dict:
    rec = jl(rec_path)
    pred = rec["predicate"]
    ci = inputs(job)
    idx = zip_index(z)
    by_base: dict[str, set] = {}
    for n, h in idx.items():
        by_base.setdefault(Path(n).name, set()).add(h)
    need = [("record", "record.custody.json", sha(rec_path))]
    bar = (ci.get("bar") or {}).get("file")
    need.append(("bar", Path(bar).name if bar else "<bar not named>", sha(job / bar) if bar and (job / bar).is_file() else None))
    fdir = job / ci.get("files_dir", "custody/files")
    for s in rec.get("subject") or []:
        need.append(("subject", s["name"], sha(fdir / s["name"]) if (fdir / s["name"]).is_file() else None))
    evd = ev_dir(job)
    for c in pred.get("checks") or []:
        if c.get("evidence"):
            need.append(("checks[].evidence", c["evidence"]["name"], c["evidence"].get("sha256")))
    for e in pred.get("external") or []:
        if e.get("evidence"):
            need.append(("external[].evidence", e["evidence"]["name"], e["evidence"].get("sha256")))
    need.append(("ledger", "custody-events.jsonl", sha(ledger(job)) if ledger(job).is_file() else None))
    for lg in sorted(evd.glob("harness-*.log")):
        need.append(("harness log", lg.name, sha(lg)))
    rows, why = [], []
    for kind, name, h in need:
        have = by_base.get(name, set())
        ok = bool(have) and (h is None or h in have)
        if not ok:
            why.append(f"{kind} {name} {'missing from' if not have else 'differs in'} the bundle")
        rows.append({"kind": kind, "name": name, "sha256": h, "in_bundle": ok})
    return result("N7", why, required=rows, listing=sorted(idx), zip_sha256=sha(z))


# ---------------------------------------------------------------- N8 (stranger)
def n8(z: Path) -> dict:
    d = Path(tempfile.mkdtemp(prefix="stranger-"))
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(d), "GIT_TERMINAL_PROMPT": "0",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"}
    tr, why = [], []

    def run(cmd, cwd=d):
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
        tr.append({"cmd": cmd, "exit": p.returncode, "stdout": p.stdout[-4000:], "stderr": p.stderr[-2000:]})
        return p
    try:
        shutil.copy(z, d / "bundle.zip")
        shutil.copy(HERE / "derive.py", d / "derive.py")
        if run(["python3", "-m", "zipfile", "-e", "bundle.zip", "bundle"]).returncode:
            return result("N8", ["bundle does not unzip"], transcript=tr)
        if run(["git", "-c", "credential.helper=", "clone", "-q", CUSTODY_URL, "custody"]).returncode or \
           run(["git", "-c", "advice.detachedHead=false", "checkout", "-q", CUSTODY_PIN], cwd=d / "custody").returncode:
            return result("N8", ["cannot anonymously clone public custody at the pin"], transcript=tr)
        if sha(d / "custody/checker/check.py") != CHECKPY_SHA:
            return result("N8", ["check.py digest differs from the pin"], transcript=tr)
        b = d / "bundle"
        bars = sorted((b / "bar").glob("*")) if (b / "bar").is_dir() else []
        cmd = ["python3", "custody/checker/check.py", "bundle/record.custody.json", "--files", "bundle/files",
               "--evidence", "bundle/evidence"] + (["--bar", f"bundle/bar/{bars[0].name}"] if len(bars) == 1 else [])
        p = run(cmd)
        try:
            chk = json.loads(p.stdout)
        except ValueError:
            chk = {}
        if chk.get("verdict") != "OK":
            why.append(f"stranger check.py verdict {chk.get('verdict')!r}, not OK")
        p = run(["python3", "derive.py", "bundle/record.custody.json", "bundle"])
        dv = json.loads(p.stdout) if p.returncode == 0 else {}
        der, recd = dv.get("derived") or {}, dv.get("recorded") or {}
        if not dv.get("ledgers_found"):
            why.append("no inputs/custody-events.jsonl in the bundle: endpoints cannot be re-derived")
        for k in ("startedAt", "producedAt"):
            if not D.same_instant(der.get(k), recd.get(k)):
                why.append(f"{k}: re-derived {der.get(k)!r} vs record {recd.get(k)!r}")
        for seat, ep in (recd.get("endpoints") or {}).items():
            got = ((der.get("endpoints") or {}).get(seat) or {})
            if got.get("endpoint") != ep:
                why.append(f"{seat} endpoint: re-derived {got.get('endpoint')!r} ({got.get('why')}) vs record {ep!r}")
        return result("N8", why, checkpy={"verdict": chk.get("verdict"), "levelAchieved": chk.get("levelAchieved")},
                      derived=der, recorded=recd, transcript=tr)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("check", choices=["n1", "n2", "n3", "n4", "n5", "n7", "n8"])
    ap.add_argument("--job"); ap.add_argument("--record"); ap.add_argument("--emit")
    ap.add_argument("--check-json", "--check", dest="check_json"); ap.add_argument("--bundle")
    a = ap.parse_args(argv)
    job = Path(a.job) if a.job else None
    rec = jl(a.record) if a.record and Path(a.record).is_file() else None
    if a.check in ("n1", "n2", "n3"):
        if not (job and rec):
            print("need --job and --record", file=sys.stderr); return 2
        out = {"n1": n1, "n2": n2, "n3": n3}[a.check](job, rec)
    elif a.check in ("n4", "n5"):
        if not (job and a.emit):
            print("need --job and --emit", file=sys.stderr); return 2
        chk = jl(a.check_json) if a.check_json and Path(a.check_json).is_file() else None
        out = (n4 if a.check == "n4" else n5)(job, jl(a.emit), rec, chk)
    elif a.check == "n7":
        out = n7(job, Path(a.record), Path(a.bundle))
    else:
        out = n8(Path(a.bundle))
    print(json.dumps(out, indent=1))
    return 0 if out["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
