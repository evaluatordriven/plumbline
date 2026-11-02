#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — S1 instrument helpers, job 2026-10-28-custody-times-ledger-spend (author: Chief of Staff (Orchestrator) drafter).
"""Shared helpers for the S1 drivers: clean clones, subprocess runs, emitter/check.py/verifier calls, output parsing,
tree digests, record edits (generic JSON ops; the held-out plants are data in CONTROLS, not code here). Stdlib only."""
from __future__ import annotations
import copy, hashlib, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

CHECKPY_SHA = "aaeb7e0532c950ee1736207b0a91ff9d810533fccecdb2c7708312408e5bcd18"
BASE_REV = "3df1ce52eddfe18705e380c4b6e99cf617cfa24b"
GIT_ENV = {"GIT_AUTHOR_NAME": "S1 instrument", "GIT_AUTHOR_EMAIL": "s1@invalid", "GIT_COMMITTER_NAME": "S1 instrument",
           "GIT_COMMITTER_EMAIL": "s1@invalid", "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def ptime(v) -> datetime:
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha12(p) -> str:
    return sha(p)[:12]


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def jw(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def run(cmd, cwd=None, env=None, timeout=3600, input=None) -> dict:
    e = dict(os.environ); e.update(env or {})
    t0 = now_iso()
    try:
        p = subprocess.run([str(c) for c in cmd], cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout, input=input)
        rc, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as x:
        rc, out, err = -9, (x.stdout or b"").decode() if isinstance(x.stdout, bytes) else (x.stdout or ""), "TIMEOUT"
    return {"argv": [str(c) for c in cmd], "cwd": str(cwd) if cwd else None, "rc": rc, "stdout": out, "stderr": err,
            "t0": t0, "t1": now_iso()}


def git(repo, *args, check=True) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env={**os.environ, **GIT_ENV})
    if check and p.returncode:
        raise RuntimeError(f"git {' '.join(args)} in {repo}: {p.stderr.strip()}")
    return p.stdout.strip()


def clean_clone(src, dest, mutate=None, label="mutant") -> Path:
    """A clean git checkout of src's HEAD at dest (the emitter refuses dirty trees). mutate(dest) edits files, then
    the edit is committed so the tree is clean again. Returns dest."""
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(src), str(dest)], check=True, capture_output=True,
                   env={**os.environ, **GIT_ENV})
    head = git(src, "rev-parse", "HEAD")
    git(dest, "-c", "advice.detachedHead=false", "checkout", "-q", head)
    if mutate:
        mutate(dest)
        git(dest, "add", "-A")
        git(dest, "commit", "-q", "-m", f"S1 {label}")
    return dest


def copytree(src, dst):
    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, symlinks=True)
    for p in [dst, *dst.rglob("*")]:
        if not p.is_symlink():
            os.chmod(p, (p.stat().st_mode | 0o700) if p.is_dir() else (p.stat().st_mode | 0o600))
    return dst


def tree_digest(root, exclude=()) -> dict:
    root = Path(root); out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            r = str(p.relative_to(root))
            if r in exclude:
                continue
            out[r] = sha(p)
    return out


def diff_digest(a: dict, b: dict) -> list:
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


KIND = re.compile(r"^\s*\[([a-z][a-z0-9-]*)\]\s", re.M)
HAND = re.compile(r"^\s*\[hand-time\]\s+(\S+)\s+(\S+):(\d+)\s+\(([a-z-]+)\)", re.M)
VFAIL = re.compile(r"^FAIL\s+(\S+)\s+(\S+)\s+(\S+?):(\d+)\s*$", re.M)


def kinds(res: dict) -> list:
    return sorted(set(KIND.findall((res.get("stdout") or "") + "\n" + (res.get("stderr") or ""))))


def hand_lines(res: dict) -> list:
    t = (res.get("stdout") or "") + "\n" + (res.get("stderr") or "")
    return sorted({(f, fl, int(ln), s) for f, fl, ln, s in HAND.findall(t)})


def emit(py, tree, job, switch=False, extra=()) -> dict:
    job = Path(job)
    rec = job / "custody" / "record.custody.json"
    before = rec.read_bytes() if rec.is_file() else None
    r = run([py, Path(tree) / "kit/emit_custody.py", "--job-dir", job, *(["--allow-hand-times"] if switch else []), *extra],
            cwd=tree)
    r["record"] = str(rec)
    r["record_written"] = rec.is_file() and rec.read_bytes() != before
    r["kinds"] = kinds(r)
    r["hand"] = hand_lines(r)
    return r


def checkpy(py, custody, rec, files, ev, bar=None) -> dict:
    cp = Path(custody) / "checker/check.py"
    if sha(cp) != CHECKPY_SHA:
        return {"verdict": None, "error": "check.py not the pin"}
    r = run([py, cp, rec, "--files", files, "--evidence", ev, *(["--bar", bar] if bar else [])])
    try:
        d = json.loads(r["stdout"])
    except ValueError:
        return {"verdict": None, "error": (r["stderr"] or r["stdout"])[-1500:]}
    fails = [k for k, v in (d.get("requirements") or {}).items() if isinstance(v, dict) and v.get("status") == "FAILED"]
    return {"verdict": d.get("verdict"), "levelAchieved": d.get("levelAchieved"), "failed": fails}


def job_paths(job) -> dict:
    job = Path(job)
    ci = jl(job / "inputs/custody.json") if (job / "inputs/custody.json").is_file() else {}
    return {"files": job / ci.get("files_dir", "custody/files"), "evidence": job / ci.get("evidence_dir", "custody/evidence"),
            "bar": job / ((ci.get("bar") or {}).get("file") or "custody/bar.md"), "ledger": job / "inputs/custody-events.jsonl",
            "record": job / "custody/record.custody.json"}


def check_job(py, custody, job, rec=None) -> dict:
    p = job_paths(job)
    return checkpy(py, custody, rec or p["record"], p["files"], p["evidence"], p["bar"] if p["bar"].is_file() else None)


def verify(py, tree, custody, job, rec=None, out_json=None, verifier=None) -> dict:
    p = job_paths(job)
    vf = Path(verifier) if verifier else Path(tree) / "kit/plumbline_verify.py"
    if not vf.is_file():
        return {"rc": None, "error": "no kit/plumbline_verify.py", "failures": [], "kinds": []}
    out_json = Path(out_json) if out_json else None
    r = run([py, vf, "--record", rec or p["record"], "--files", p["files"], "--evidence", p["evidence"], "--ledger",
             p["ledger"], "--custody", custody, *(["--json", out_json] if out_json else [])], cwd=tree)
    r["failures"] = [{"kind": k, "field": f, "file": fl, "line": int(ln)} for k, f, fl, ln in VFAIL.findall(r["stdout"])]
    r["kinds"] = sorted({x["kind"] for x in r["failures"]})
    r["traceback"] = "Traceback (most recent call last)" in (r["stdout"] + r["stderr"])
    if out_json and out_json.is_file():
        try:
            r["json"] = jl(out_json)
        except ValueError:
            r["json"] = None
    return r


# ---------------------------------------------------------------- generic JSON edits (plants are data)
def _walk(obj, path, create=False):
    for k in path[:-1]:
        if isinstance(obj, list):
            obj = obj[int(k)]
        else:
            if create and k not in obj:
                obj[k] = {}
            obj = obj[k]
    return obj, path[-1]


def get(obj, path):
    for k in path:
        obj = obj[int(k)] if isinstance(obj, list) else obj[k]
    return obj


def apply_ops(doc, ops):
    """ops: set/del/add/append/remove_where/copy (see controls README). Returns a new document."""
    d = copy.deepcopy(doc)
    for op in ops:
        o = op["op"]
        if o == "set":
            parent, k = _walk(d, op["path"], create=True)
            parent[int(k) if isinstance(parent, list) else k] = copy.deepcopy(op["value"])
        elif o == "del":
            parent, k = _walk(d, op["path"])
            if isinstance(parent, list):
                parent.pop(int(k))
            else:
                parent.pop(k, None)
        elif o == "add":
            parent, k = _walk(d, op["path"])
            parent[k] = round(float(parent[k]) + float(op["delta"]), 10)
        elif o == "set_from":
            parent, k = _walk(d, op["path"], create=True)
            v = get(d, op["from"])
            parent[k] = round(float(v) + float(op["delta"]), 10) if "delta" in op else copy.deepcopy(v)
        elif o == "append":
            get(d, op["path"]).append(copy.deepcopy(op["value"]))
        elif o == "append_copy":
            item = copy.deepcopy(get(d, op["from"]))
            for kk, src in (op.get("overrides_from") or {}).items():
                item[kk] = copy.deepcopy(get(d, src))
            item.update(copy.deepcopy(op.get("overrides") or {}))
            get(d, op["path"]).append(item)
        elif o == "remove_where":
            lst = get(d, op["path"]); n = op.get("count", 1); keep = []
            for it in lst:
                if n and all((it.get(a) in b) if isinstance(b, list) else (it.get(a) == b) for a, b in op["match"].items()):
                    n -= 1; continue
                keep.append(it)
            lst[:] = keep
        elif o == "copy_over":   # copy every key of one object over another
            src = get(d, op["from"]); dst = get(d, op["path"])
            for kk in op.get("keys") or list(src):
                if kk in src:
                    dst[kk] = copy.deepcopy(src[kk])
        else:
            raise ValueError(f"unknown op {o}")
    return d


def stamp() -> dict:
    return {"writer": "freeze/instrument/" + Path(sys.argv[0]).name + "@" + sha12(sys.argv[0]), "started_at": now_iso()}


# ---------------------------------------------------------------- the instrument's own key reading (F8d)
def key_usage(key_file) -> float | None:
    """GET https://openrouter.ai/api/v1/key (free) with the key read from its file by path. Nothing is printed or
    written: the key lives only in this function's request header. Returns data.usage or None."""
    import urllib.request
    try:
        k = Path(key_file).read_text(encoding="utf-8").strip()
        req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer " + k})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return float(json.loads(resp.read())["data"]["usage"])
    except Exception:
        return None
