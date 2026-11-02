# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — S1 drivers for job 2026-10-28-custody-times-ledger-spend.
"""Drivers: run the subject's own tools on held-out inputs and record observations (obs). They judge nothing;
judges.py turns each obs into PASS/FAIL. Every driver catches its own errors; an error is an obs, and a judge
FAILs it (a check that cannot run is not a pass). Plants, wrappers and expected values come from the controls
directory as data (controls/plants/*.json, controls/wrappers/*.py.txt, controls/expect.json)."""
from __future__ import annotations

import ast, json, os, re, shutil, stat, subprocess, sys, time, traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L          # noqa: E402
import t4_build as T4    # noqa: E402

LEDGER_EVENTS = {"freeze", "approve-buyer", "approve-specialist", "pin-maker", "pin-eval-m", "relay", "amendment",
                 "generation-open", "generation-close", "evaluation", "spend", "dispose"}


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lines(p):
    p = Path(p)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.is_file() else []


def guarded(fn):
    def w(ctx, *a, **k):
        try:
            return fn(ctx, *a, **k)
        except Exception as e:  # an instrument-side error is an observation, judged FAIL
            return {"error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-3000:]}
    w.__name__ = fn.__name__
    return w


class Ctx:
    def __init__(s, py, subj, base, custody, controls, work, corpus):
        s.py, s.subj, s.base, s.custody = py, Path(subj), Path(base), Path(custody)
        s.C, s.W, s.corpus = Path(controls), Path(work), corpus
        s.expect = L.jl(s.C / "expect.json")
        s.cache = {}
        s.W.mkdir(parents=True, exist_ok=True)

    def plant(s, name):
        return L.jl(s.C / "plants" / f"{name}.json")

    def wrapper(s, name):
        return (s.C / "wrappers" / f"{name}.py.txt").read_text(encoding="utf-8")

    def writer_expect(s, tree=None):
        f = Path(tree or s.subj) / "kit/custody_ledger.py"
        return "kit/custody_ledger.py@" + L.sha12(f) if f.is_file() else None

    def jr(s, dest):
        return L.copytree(s.base / "tests/fixtures/custody/job-rejected", dest)

    def clean(s, dest, name="clean"):
        return L.copytree(s.C / "jobs" / name, dest)


def ledcmd(ctx, J, args, tree=None):
    """One custody_ledger.py call with before/after snapshots of the ledger and inputs/custody.json."""
    tree = Path(tree or ctx.subj)
    led, ci = J / "inputs/custody-events.jsonl", J / "inputs/custody.json"
    b_led = led.read_bytes() if led.is_file() else b""
    b_ci = ci.read_bytes() if ci.is_file() else b""
    k = 2 if args[0] == "generation" else 1
    r = L.run([ctx.py, tree / "kit/custody_ledger.py", *args[:k], "--job-dir", J, *args[k:]], cwd=tree)
    a_led = led.read_bytes() if led.is_file() else b""
    a_ci = ci.read_bytes() if ci.is_file() else b""
    new = a_led[len(b_led):] if a_led.startswith(b_led) else None
    appended = [json.loads(x) for x in new.decode().splitlines() if x.strip()] if new is not None else None
    return {"args": [str(x) for x in args], "rc": r["rc"], "stdout": r["stdout"][-1500:], "stderr": r["stderr"][-1500:],
            "t0": r["t0"], "t1": r["t1"], "refused_text": "REFUSED:" in (r["stdout"] + r["stderr"]),
            "prefix_kept": a_led.startswith(b_led), "appended": appended,
            "ledger_same": a_led == b_led, "custody_same": a_ci == b_ci,
            "custody_after": json.loads(a_ci) if a_ci else None}


# ------------------------------------------------------------------ shared builds
def t4_job(ctx, name="t4", tree=None, extra=(), custody=True):
    key = (name, str(tree))
    if key in ctx.cache:
        return ctx.cache[key]
    tree = Path(tree or ctx.subj)
    oc = tree / "tools/edi/or_call.py"
    work = ctx.W / name
    args = ["--tools", tree, "--or-call", oc, "--work", work, "--controls", ctx.C, "--corpus", ctx.corpus,
            "--python", ctx.py, *extra]
    if custody:
        args += ["--custody", ctx.custody]
    r = L.run([ctx.py, HERE / "t4_build.py", *args], timeout=1800)
    b = L.jl(work / "t4-build.json") if (work / "t4-build.json").is_file() else {"ok": False, "error": r["stderr"][-2000:]}
    b["J"] = str(work / "jobs" / T4.JOB_NAME); b["W"] = str(work)
    ctx.cache[key] = b
    return b


def t4_emitted(ctx):
    """J4: the subject-built T4 job, emitted on a copy with no switch."""
    if "j4" in ctx.cache:
        return ctx.cache["j4"]
    b = t4_job(ctx)
    out = {"build": {k: b.get(k) for k in ("ok", "error")}, "steps": [{k: s[k] for k in ("name", "rc", "t0", "t1")}
                                                                       | {"stderr": s["stderr"][-800:]}
                                                                       for s in b.get("steps", [])]}
    J = Path(b["J"])
    if J.is_dir():
        J2 = L.copytree(J, ctx.W / "j4")
        rec = J2 / "custody/record.custody.json"
        if rec.exists():
            rec.unlink()
        before = L.tree_digest(J2)
        e = L.emit(ctx.py, ctx.subj, J2)
        after = L.tree_digest(J2, exclude=("custody/record.custody.json",))
        out.update({"J": str(J2), "emit": {k: e[k] for k in ("rc", "record_written", "kinds", "hand")} | {"stdout": e["stdout"][-2000:]},
                    "changed": L.diff_digest({k: v for k, v in before.items()}, after)})
        if e["record_written"]:
            out["record"] = L.jl(rec)
            out["check"] = L.check_job(ctx.py, ctx.custody, J2)
        pk = J / "packet.json"
        out["packet_terminal"] = (L.jl(pk).get("terminal_state") if pk.is_file() else None)
        out["ledger"] = lines(J2 / "inputs/custody-events.jsonl")
        out["custody_json"] = L.jl(J2 / "inputs/custody.json")
    ctx.cache["j4"] = out
    return out


def xp(rec):
    return ((rec or {}).get("predicate") or {}).get("x-plumbline") or {}


# ------------------------------------------------------------------ T
@guarded
def d_T1(ctx):
    j4 = t4_emitted(ctx); f1 = f1_seq(ctx)
    exp = ctx.writer_expect()
    rows = []
    lsteps = [s for s in j4["steps"] if s["name"] in LEDGER_EVENTS]
    led = j4.get("ledger") or []
    map_ok = len(lsteps) == len(led) and len(led) > 0
    for s, ln in zip(lsteps, led):
        rows.append({"src": "t4:" + s["name"], "writer": ln.get("writer"), "at": ln.get("at"), "t0": s["t0"], "t1": s["t1"]})
    for c in (f1.get("calls") or []):
        if c.get("rc") == 0 and c.get("appended"):
            for ln in c["appended"]:
                rows.append({"src": "f1:" + c["tag"], "writer": ln.get("writer"), "at": ln.get("at"), "t0": c["t0"], "t1": c["t1"]})
    return {"expect_writer": exp, "map_ok": map_ok, "n_steps": len(lsteps), "n_lines": len(led), "rows": rows}


@guarded
def d_T2T3(ctx):
    cases = {}
    for pid in ("P-T2a", "P-T2b", "P-T2c", "P-T2d"):
        p = ctx.plant(pid)
        J = ctx.clean(ctx.W / "t2" / pid, p.get("base", "clean"))
        for rel, ops in (p.get("jsonl_ops") or {}).items():          # ledger lines (1-based "line")
            f = J / rel; ls = f.read_text(encoding="utf-8").splitlines()
            for op in ops:
                if op["op"] == "line_set":
                    d = json.loads(ls[op["line"] - 1]); d = L.apply_ops(d, op["ops"]); ls[op["line"] - 1] = json.dumps(d, ensure_ascii=False)
                elif op["op"] == "line_append_copy":
                    d = json.loads(ls[op["from"] - 1]); d = L.apply_ops(d, op["ops"]); ls.append(json.dumps(d, ensure_ascii=False))
            f.write_text("\n".join(ls) + "\n", encoding="utf-8")
        if p.get("custody_json"):                                     # whole-file replacement, frozen bytes
            shutil.copyfile(ctx.C / "plants" / p["custody_json"], J / "inputs/custody.json")
        rec = J / "custody/record.custody.json"
        if rec.exists():
            rec.unlink()
        e0 = L.emit(ctx.py, ctx.subj, J)
        c = {"expected": [list(x) for x in p["expect_hand"]], "nosw": {k: e0[k] for k in ("rc", "record_written", "kinds", "hand")},
             "nosw_out": (e0["stdout"] + e0["stderr"])[-1500:]}
        t0 = L.now_iso()
        e1 = L.emit(ctx.py, ctx.subj, J, switch=True)
        t1 = L.now_iso()
        c["sw"] = {k: e1[k] for k in ("rc", "record_written", "kinds")} | {"t0": t0, "t1": t1, "out": (e1["stdout"] + e1["stderr"])[-1500:]}
        if e1["record_written"]:
            r = L.jl(rec); x = xp(r)
            c["sw"]["hand_times"] = x.get("hand_times")
            c["sw"]["allowances"] = x.get("allowances")
            c["sw"]["check"] = L.check_job(ctx.py, ctx.custody, J)
        cases[pid] = c
    J = ctx.jr(ctx.W / "t2" / "overlay-hand-times")
    shutil.copytree(ctx.base / "tests/fixtures/custody/failures/hand-times", J, dirs_exist_ok=True)
    e = L.emit(ctx.py, ctx.subj, J, switch=True)
    return {"cases": cases, "expect_writer": "kit/emit_custody.py@" + L.sha12(ctx.subj / "kit/emit_custody.py"),
            "overlay_sw": {k: e[k] for k in ("rc", "record_written", "kinds")}}


@guarded
def d_T4(ctx):
    j4 = t4_emitted(ctx)
    return {k: j4.get(k) for k in ("build", "steps", "emit", "check", "packet_terminal")} | {
        "hand_times": xp(j4.get("record")).get("hand_times") if j4.get("record") else None}


def _anchor_ok(src):
    return [i for i, l in enumerate(src.splitlines(), 1) if "ref.add(" in l and "is after the job's close" in l]


@guarded
def d_T5(ctx, tree=None):
    tree = Path(tree or ctx.subj)
    src = (tree / "kit/emit_custody.py").read_text(encoding="utf-8")
    hsrc = (tree / "kit/custody_history.py").read_text(encoding="utf-8")
    tol = None
    for n in ast.parse(hsrc).body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TOLERANCE_S" for t in n.targets):
            try:
                tol = ast.literal_eval(n.value)
            except ValueError:
                tol = "non-literal"
    cases = []
    jobs = []
    for ov in sorted(p.name for p in (ctx.base / "tests/fixtures/custody/failures").iterdir() if p.is_dir()):
        jobs.append(("overlay:" + ov, ov))
    for pj in ctx.expect["t5_prior_jobs"]:
        jobs.append(("prior:" + pj, pj))
    for name, ref in jobs:
        def mk(dest):
            if name.startswith("overlay:"):
                J = ctx.jr(dest); shutil.copytree(ctx.base / "tests/fixtures/custody/failures" / ref, J, dirs_exist_ok=True)
            else:
                J = L.copytree(ctx.C / "prior" / ref, dest)
            rec = J / "custody/record.custody.json"
            if rec.exists():
                rec.unlink()
            return J
        d = ctx.W / "t5" / re.sub(r"[^A-Za-z0-9_.-]", "_", name)
        b = L.emit(ctx.py, ctx.base, mk(d / "base"))
        if b["rc"] != 3:
            continue
        n0 = L.emit(ctx.py, tree, mk(d / "nosw"))
        n1 = L.emit(ctx.py, tree, mk(d / "sw"), switch=True)
        cases.append({"case": name, "base": {"rc": b["rc"], "kinds": b["kinds"]}, "nosw": {"rc": n0["rc"], "kinds": n0["kinds"]},
                      "sw": {"rc": n1["rc"], "kinds": n1["kinds"]}})
    return {"tolerance": tol, "anchor_lines": _anchor_ok(src), "cases": cases, "min_cases": ctx.expect["t5_min_cases"]}


@guarded
def d_T6(ctx):
    inst = L.copytree(ctx.base / ctx.expect["t6_prior_instrument"], ctx.W / "t6" / "instrument")
    if L.sha(inst / "ncheck.py") != ctx.expect["t6_ncheck_sha256"]:
        return {"error": "prior instrument ncheck.py is not the pinned bytes"}
    shutil.copyfile(HERE / "t6_subject.py", inst / "subject.py")
    out = ctx.W / "t6" / "out"
    cust = L.copytree(ctx.custody, ctx.W / "t6" / "custody")
    env = {"CONTROLS_MANIFEST": str(ctx.C / "t6" / "MANIFEST.sha256"), "CUSTODY_DIR": str(cust),
           "PATH": str(Path(ctx.py).parent) + os.pathsep + os.environ.get("PATH", ""), "S1_CUSTODY": str(cust)}
    r = L.run(["bash", inst / "run_instrument.sh", "batch", ctx.subj, ctx.C / "t6" / "controls", out], env=env, timeout=3600)
    summ = L.jl(out / "summary.json") if (out / "summary.json").is_file() else None
    runs = []
    for ej in sorted((out / "subject" / "runs").glob("*/emit.json")) if (out / "subject" / "runs").is_dir() else []:
        e = L.jl(ej)
        runs.append({"run": ej.parent.name, "nosw_hand_fields": sorted({h[0] for h in e.get("no_switch", {}).get("hand", [])}),
                     "record_written": e.get("record_written"),
                     "record_hand_fields": sorted({h.get("field") for h in (e.get("hand_times") or []) if isinstance(h, dict)}),
                     "verify_rc": (e.get("verify") or {}).get("rc"), "verify_kinds": (e.get("verify") or {}).get("kinds")})
    return {"rc": r["rc"], "stderr": r["stderr"][-2000:], "summary": summ, "runs": runs, "min_runs": ctx.expect["t6_min_runs"]}


@guarded
def d_T7(ctx, tree=None):
    tree = Path(tree or ctx.subj)
    res = {}
    for sw in (False, True):
        J = ctx.jr(ctx.W / "t7" / ("jr-sw" if sw else "jr"))
        rec = J / "custody/record.custody.json"
        if rec.exists():
            rec.unlink()
        b = L.tree_digest(J)
        e = L.emit(ctx.py, tree, J, switch=sw)
        a = L.tree_digest(J, exclude=("custody/record.custody.json",))
        r = {"rc": e["rc"], "kinds": e["kinds"], "hand": e["hand"], "changed": L.diff_digest(b, a), "written": e["record_written"]}
        if e["record_written"]:
            r["hand_times"] = xp(L.jl(rec)).get("hand_times")
        res["jr-sw" if sw else "jr"] = r
    j4 = t4_emitted(ctx) if tree == ctx.subj else {}
    res["t4_changed"] = j4.get("changed")
    res["log_hand_count"] = ctx.expect["jr_log_hand_count"]
    res["log_sources"] = ctx.expect["jr_log_sources"]
    g2 = ctx.cache.get("g2") or {}
    res["porcelain_after_suite"] = g2.get("subject_porcelain")
    return res


# ------------------------------------------------------------------ F1 (one sequence on a scratch job)
def f1_seq(ctx, tree=None):
    tree = Path(tree or ctx.subj)
    key = ("f1", str(tree))
    if key in ctx.cache:
        return ctx.cache[key]
    out = ctx.cache[key] = _f1_seq(ctx, tree)
    return out


@guarded
def _f1_seq(ctx, tree):
    b = t4_job(ctx, "f1", tree=tree, extra=("--stop-after", "init-spend", "--no-spend"))
    if not b.get("ok"):
        return {"error": "scratch build failed: " + str(b.get("error")), "calls": []}
    J, Wd = Path(b["J"]), Path(b["W"])
    py = ctx.py
    calls = []

    def C(tag, expect, args):
        c = ledcmd(ctx, J, args, tree); c["tag"], c["expect"] = tag, expect; calls.append(c); time.sleep(1.1)
        return c
    fz = lines(J / "inputs/custody-events.jsonl")[0]["at"]
    fzt = L.ptime(fz)
    p1 = J / "inputs/prompt-1.json"; p1.write_text(json.dumps([{"role": "user", "content": "S1 F1 prompt ✓"}]) + "\n")
    p2 = J / "inputs/prompt-2.json"; p2.write_text(json.dumps([{"role": "user", "content": "S1 F1 prompt 2"}]) + "\n")
    C("c.open1", "ok", ["generation", "open", "--seat", "maker", "--prompt", p1])
    C("c.open-again", "refuse", ["generation", "open", "--seat", "maker", "--prompt", p1])
    C("c.close-wrong-n", "refuse", ["generation", "close", "--seat", "maker", "--n", "2", "--outcome", "x", "--fix-kind", "code"])
    C("c.close-wrong-seat", "refuse", ["generation", "close", "--seat", "eval-m", "--n", "1", "--outcome", "x", "--fix-kind", "code"])
    # one mocked maker call so the spend ledger has a settle
    tpl = ctx.C / "t4/mock-templates"; T4.mock_dir(Wd / "mock-f1", tpl, T4.MAKER, "F1 reply")
    oc = [py, tree / "tools/edi/or_call.py", "--job-spend", Wd / "job-spend.json", "--key-file", Wd / "dummy-key"]
    mk = L.run([*oc, "--mock-transport", Wd / "mock-f1", "--seat", "maker", "--log", J / "custody/evidence/harness-maker-f1.log",
                "--model", T4.MAKER["model"], "--ledger", J / "inputs/custody-events.jsonl", "--messages", p1,
                "--out", Wd / "f1-reply.txt", "--call", "maker_f1", "--gen-wait", "0"], cwd=tree)
    C("c.close1", "ok", ["generation", "close", "--seat", "maker", "--n", "1", "--outcome", "F1 outcome", "--fix-kind", "code"])
    C("c.close1-again", "refuse", ["generation", "close", "--seat", "maker", "--n", "1", "--outcome", "x", "--fix-kind", "code"])
    C("c.open2", "ok", ["generation", "open", "--seat", "maker", "--prompt", p2])
    C("c.close2", "ok", ["generation", "close", "--seat", "maker", "--n", "2", "--outcome", "F1 outcome 2", "--fix-kind", "test"])
    vf = J / "custody/evidence/f1-verdict.txt"; vf.write_text("D1 10\n")
    C("d.verdict-missing", "refuse", ["evaluation", "--batch", "b1", "--evaluator", "eval-m", "--verdict",
                                      J / "custody/evidence/no-such.txt", "--iteration", "1"])
    C("d.verdict", "ok", ["evaluation", "--batch", "b1", "--evaluator", "eval-m", "--verdict", vf, "--iteration", "1"])
    s0 = J / "inputs/summary-nostamp.json"; s0.write_text(json.dumps({"verdicts": ["D1 10"]}) + "\n")
    st = {"started_at": iso(datetime.now(timezone.utc) - timedelta(seconds=30)), "finished_at": iso(datetime.now(timezone.utc)),
          "writer": "tools/edi/judge_batch.py@s1f1aaaaaaaa", "verdicts": ["D1 10"]}
    s1 = J / "inputs/summary.json"; s1.write_text(json.dumps(st) + "\n")
    C("d.summary-nostamp", "refuse", ["evaluation", "--batch", "b2", "--evaluator", "eval-m", "--summary", s0, "--iteration", "1"])
    C("d.summary", "ok", ["evaluation", "--batch", "b2", "--evaluator", "eval-m", "--summary", s1, "--iteration", "1"])
    am_in = J / "custody/files/f1-amend.md"; am_in.write_text("inside custody\n")
    am = J / "amendments/f1-amend.md"; am.parent.mkdir(exist_ok=True); am.write_text("# F1 amendment\n")
    q = "F1 Buyer: “D2 means every section” — ✓"
    future = iso(datetime.now(timezone.utc) + timedelta(seconds=600)); early = iso(fzt - timedelta(seconds=60))
    C("e.in-custody", "refuse", ["amendment", "--file", am_in, "--quote", q, "--channel", "f1 msg", "--said-at", fz])
    C("e.early", "refuse", ["amendment", "--file", am, "--quote", q, "--channel", "f1 msg", "--said-at", early])
    C("e.future", "refuse", ["amendment", "--file", am, "--quote", q, "--channel", "f1 msg", "--said-at", future])
    C("e.ok", "ok", ["amendment", "--file", am, "--quote", q, "--channel", "f1 msg", "--said-at", fz])
    rq = "Steve: “Ratified proceed” ✓"
    C("f.early", "refuse", ["relay", "--quote", rq, "--from", "S1 relay", "--source-chat", "f1 chat", "--source-at", early])
    C("f.future", "refuse", ["relay", "--quote", rq, "--from", "S1 relay", "--source-chat", "f1 chat",
                             "--source-at", iso(datetime.now(timezone.utc) + timedelta(seconds=600))])
    C("f.ok", "ok", ["relay", "--quote", rq, "--from", "S1 relay", "--source-chat", "f1 chat", "--source-at", fz])
    # F1g spend: a reading taken now (< 180 s after the settle), one with no stamp, then one after >= 181 s
    sl = J / "spend/spend-ledger.jsonl"
    T4.mock_dir(Wd / "mock-st", tpl, T4.MAKER, "x")
    r1 = J / "spend/reading-early.json"
    L.run([*oc, "--spend-status", "--out", r1, "--mock-transport", Wd / "mock-st"], cwd=tree)
    C("g.early", "refuse", ["spend", "--spend-ledger", sl, "--key-reading", r1])
    r0 = J / "spend/reading-nostamp.json"
    if r1.is_file():
        d = L.jl(r1); d.pop("read_at", None); d.pop("writer", None); L.jw(r0, d)
    else:
        L.jw(r0, {"key_usage_usd": 1.0})
    C("g.nostamp", "refuse", ["spend", "--spend-ledger", sl, "--key-reading", r0])
    settles = [x["at"] for x in lines(sl) if x.get("event") == "settle"]
    if settles:
        wait = 181 - (datetime.now(timezone.utc) - L.ptime(max(settles))).total_seconds()
        if wait > 0:
            time.sleep(wait)
    r2 = J / "spend/reading.json"
    L.run([*oc, "--spend-status", "--out", r2, "--mock-transport", Wd / "mock-st"], cwd=tree)
    C("g.ok", "ok", ["spend", "--spend-ledger", sl, "--key-reading", r2])
    # F1b dispose: last check = latest evaluation-line at / summary finished_at / eval log received_at
    led = lines(J / "inputs/custody-events.jsonl")
    cands = [x.get("at") for x in led if x.get("event") == "evaluation"] + [st["finished_at"]]
    last = max((c for c in cands if c), key=L.ptime)
    C("b.early", "refuse", ["dispose", "--by", "F1 Buyer", "--state", "given", "--decided-at",
                            iso(L.ptime(last) - timedelta(seconds=2)), "--decided-source", "s1 f1"])
    C("b.future", "refuse", ["dispose", "--by", "F1 Buyer", "--state", "given", "--decided-at",
                             iso(datetime.now(timezone.utc) + timedelta(seconds=600)), "--decided-source", "s1 f1"])
    C("b.ok", "ok", ["dispose", "--by", "F1 Buyer", "--state", "given", "--decided-at", last, "--decided-source", "s1 f1"])
    files = {"prompt-1": L.sha(p1), "prompt-2": L.sha(p2), "verdict": L.sha(vf), "amend": L.sha(am),
             "ledger": L.sha(sl) if sl.is_file() else None, "reading": L.sha(r2) if r2.is_file() else None}
    return {"calls": calls, "freeze_at": fz, "last_check": last, "summary_stamp": st, "amend_quote": q, "relay_quote": rq,
            "shas": files, "reading": L.jl(r2) if r2.is_file() else None, "maker_call_rc": mk["rc"],
            "spend_rows": lines(sl)}


@guarded
def d_F1(ctx):
    f = f1_seq(ctx)
    j4 = t4_emitted(ctx)
    pf = ctx.plant("P-F1f")
    J = ctx.clean(ctx.W / "f1f", pf.get("base", "clean"))
    shutil.copyfile(ctx.C / "plants" / pf["ledger_file"], J / "inputs/custody-events.jsonl")
    shutil.copyfile(ctx.C / "plants" / pf["custody_json"], J / "inputs/custody.json")
    rec = J / "custody/record.custody.json"
    if rec.exists():
        rec.unlink()
    e = L.emit(ctx.py, ctx.subj, J)
    return {"seq": f, "t4_dispose": [x for x in (j4.get("ledger") or []) if x.get("event") == "dispose"],
            "t4_record_disposition": ((j4.get("record") or {}).get("predicate") or {}).get("disposition"),
            "p_f1f": {"rc": e["rc"], "kinds": e["kinds"], "written": e["record_written"]}}


@guarded
def d_F1h(ctx):
    j4 = t4_emitted(ctx)
    return {"record_xp": {k: xp(j4.get("record")).get(k) for k in ("generations", "evaluations", "relays", "amendments", "spend")},
            "ledger": j4.get("ledger"), "check": j4.get("check"), "emit_rc": (j4.get("emit") or {}).get("rc")}


# ------------------------------------------------------------------ I1 / F7a / F8 / P1
def _tools(ctx):
    return ctx.subj / "tools/edi"


@guarded
def d_I1(ctx):
    T = _tools(ctx); out = {}
    for f in ("fixture_run.py", "judge_batch.py", "or_call.py"):
        out.setdefault("exists", {})[f] = (T / f).is_file()
    if not all(out["exists"].values()):
        return out
    src = L.copytree(ctx.C / "f7a" / "src", ctx.W / "i1" / "src")
    t0 = L.now_iso(); r = L.run([ctx.py, T / "fixture_run.py", "--src", src, "--work", ctx.W / "i1" / "fr-work",
                                 "--summary", ctx.W / "i1" / "fr.json"], cwd=ctx.subj); t1 = L.now_iso()
    out["fixture_run"] = {"rc": r["rc"], "t0": t0, "t1": t1, "stderr": r["stderr"][-1500:],
                          "out": L.jl(ctx.W / "i1/fr.json") if (ctx.W / "i1/fr.json").is_file() else None,
                          "expect_writer": "tools/edi/fixture_run.py@" + L.sha12(T / "fixture_run.py")}
    jb = ctx.W / "i1" / "jb"; jb.mkdir(parents=True, exist_ok=True)
    items = ctx.expect["i1_items"]
    L.jw(jb / "items.json", items)
    js = _spend_file(ctx, jb, bound=5.0, reserve=0.1)
    out["judge_batch_init"] = _init(ctx, jb, js, 1.0)["rc"]
    T4.mock_dir(jb / "mock", ctx.C / "t4/mock-templates", T4.EVAL, "SCORE 10")
    (jb / "rubric.md").write_text("Score the item 0-10. Reply SCORE <n>.\n")
    t0 = L.now_iso()
    r = L.run([ctx.py, T / "judge_batch.py", "--items", jb / "items.json", "--batch", "2", "--rubric", jb / "rubric.md",
               "--out", jb / "out", "--job-spend", js, "--log", jb / "harness-eval-m.log", "--model", T4.EVAL["model"],
               "--tag", T4.EVAL["tag"], "--pin-provider", T4.EVAL["provider"], "--mock-transport", jb / "mock"], cwd=ctx.subj)
    t1 = L.now_iso()
    out["judge_batch"] = {"rc": r["rc"], "t0": t0, "t1": t1, "stderr": r["stderr"][-1500:],
                          "out": L.jl(jb / "out/summary.json") if (jb / "out/summary.json").is_file() else None,
                          "expect_writer": "tools/edi/judge_batch.py@" + L.sha12(T / "judge_batch.py"),
                          "expect_order": items[1:] + items[:1]}
    return out


def _spend_file(ctx, d, bound, reserve, prices=None, real=False):
    d = Path(d); d.mkdir(parents=True, exist_ok=True)
    js = d / "job-spend.json"
    if not prices:
        prices = [{"model": s["model"], "tag": s["tag"], "prompt_usd_per_token": 1e-7, "completion_usd_per_token": 3e-7,
                   "max_completion_tokens": 131072} for s in (T4.MAKER, T4.EVAL)]
    jid = "s1-" + os.urandom(6).hex()
    L.jw(js, {"job_id": jid, "bound_usd": bound, "reserve_usd": reserve, "spend_ledger": str(d / "spend" / "spend-ledger.jsonl"),
              "prices": prices})
    if not real:
        k = d / "dummy-key"; k.write_text("sk-or-v1-S1-DUMMY-NOT-A-KEY\n"); k.chmod(0o600)
    return js


@guarded
def d_F7a(ctx):
    T = _tools(ctx)
    if not (T / "fixture_run.py").is_file():
        return {"error": "no tools/edi/fixture_run.py"}
    res = {}
    for mode in ("rw", "ro"):
        d = ctx.W / "f7a" / mode
        src = L.copytree(ctx.C / "f7a" / "src", d / "src")
        _restore_modes(ctx, src)
        before = L.tree_digest(src)
        if mode == "ro":
            for p in sorted([src, *src.rglob("*")], key=lambda p: -len(p.parts)):
                os.chmod(p, p.stat().st_mode & ~0o222)
        r = L.run([ctx.py, T / "fixture_run.py", "--src", src, "--work", d / "work", "--summary", d / "out.json"], cwd=ctx.subj)
        after = L.tree_digest(src)
        for p in [src, *src.rglob("*")]:
            os.chmod(p, p.stat().st_mode | 0o700)
        unw = [str(p.relative_to(d / "work")) for p in (d / "work").rglob("*")
               if not p.is_symlink() and not (p.stat().st_mode & stat.S_IWUSR)] if (d / "work").is_dir() else ["<no work dir>"]
        o = L.jl(d / "out.json") if (d / "out.json").is_file() else None
        res[mode] = {"rc": r["rc"], "stderr": r["stderr"][-1200:], "src_changed": L.diff_digest(before, after),
                     "out": o, "unwritable_in_work": unw[:50]}
    return res


def _restore_modes(ctx, src):
    for rel, mode in ctx.expect["f7a_modes"].items():
        os.chmod(src / rel, int(mode, 8))


def _or(ctx, js, key, extra, cwd=None):
    return L.run([ctx.py, _tools(ctx) / "or_call.py", "--job-spend", js, "--key-file", key, *extra], cwd=cwd or ctx.subj)


def _mockcall(ctx, d, js, cap=None, seat=T4.MAKER, tc=0.00001, usage=1.0, n=1):
    tpl = ctx.C / "t4/mock-templates"
    T4.mock_dir(d / "mock", tpl, seat, "S1 F8")
    g = L.jl(d / "mock/generation.json"); g["body"]["data"]["total_cost"] = tc; L.jw(d / "mock/generation.json", g)
    k = L.jl(d / "mock/key.json"); k["body"]["data"]["usage"] = usage; L.jw(d / "mock/key.json", k)
    m = d / "msgs.json"; L.jw(m, [{"role": "user", "content": "S1 F8 guard test"}])
    return [*(["--max-cost", str(cap)] if cap is not None else []), "--mock-transport", d / "mock", "--seat", seat["seat"],
            "--log", d / f"harness-{seat['seat']}-f8.log", "--model", seat["model"], "--tag", seat["tag"],
            "--pin-provider", seat["provider"], "--messages", m, "--out", d / f"reply-{n}.txt", "--call", f"f8_{n}",
            "--gen-wait", "0"]


def _req(d):
    return lines(Path(d) / "mock/requests.jsonl")


def _log(d, seat="maker"):
    p = Path(d) / f"harness-{seat}-f8.log"
    if not p.is_file():
        return []
    try:
        v = json.loads(p.read_text()); return v if isinstance(v, list) else [v]
    except ValueError:
        return ["<unparseable>"]


def _init(ctx, d, js, usage):
    tpl = ctx.C / "t4/mock-templates"; T4.mock_dir(d / "mock-init", tpl, T4.MAKER, "x")
    k = L.jl(d / "mock-init/key.json"); k["body"]["data"]["usage"] = usage; L.jw(d / "mock-init/key.json", k)
    return _or(ctx, js, d / "dummy-key", ["--init-spend", "--mock-transport", d / "mock-init"])


@guarded
def d_F8abc(ctx):
    if not (_tools(ctx) / "or_call.py").is_file():
        return {"error": "no tools/edi/or_call.py"}
    o = {}
    # F8a: key usage already at the bound
    d = ctx.W / "f8/a"; js = _spend_file(ctx, d, 5.0, 0.1); o["a_init"] = _init(ctx, d, js, 1.0)["rc"]
    r = _or(ctx, js, d / "dummy-key", _mockcall(ctx, d, js, usage=6.0))
    o["a"] = {"rc": r["rc"], "posts": [x for x in _req(d) if x["method"] == "POST"], "log": _log(d), "err": r["stderr"][-600:]}
    # F8b: cap below worst case; then a cap that the stated cost exceeds
    d = ctx.W / "f8/b1"; js = _spend_file(ctx, d, 5.0, 0.1); _init(ctx, d, js, 1.0)
    r = _or(ctx, js, d / "dummy-key", _mockcall(ctx, d, js, cap=1e-9))
    o["b1"] = {"rc": r["rc"], "posts": [x for x in _req(d) if x["method"] == "POST"], "log": _log(d)}
    d = ctx.W / "f8/b2"; prices = [{"model": T4.MAKER["model"], "tag": T4.MAKER["tag"], "prompt_usd_per_token": 1e-12,
                                    "completion_usd_per_token": 1e-14, "max_completion_tokens": 131072}]
    js = _spend_file(ctx, d, 5.0, 0.1, prices); _init(ctx, d, js, 1.0)
    r = _or(ctx, js, d / "dummy-key", _mockcall(ctx, d, js, cap=5e-6, tc=1e-5))
    o["b2"] = {"rc": r["rc"], "log": _log(d), "reply_exists": (d / "reply-1.txt").exists(),
               "spend_rows": lines(d / "spend/spend-ledger.jsonl")}
    # F8c: key delta alone; ledger alone; GET before POST; missing spend file; no literal job id; max_tokens
    d = ctx.W / "f8/c1"; js = _spend_file(ctx, d, 5.0, 0.1); _init(ctx, d, js, 1.0)
    r = _or(ctx, js, d / "dummy-key", _mockcall(ctx, d, js, usage=5.95))
    o["c1"] = {"rc": r["rc"], "posts": [x for x in _req(d) if x["method"] == "POST"]}
    d = ctx.W / "f8/c2"
    prices = [{"model": T4.MAKER["model"], "tag": T4.MAKER["tag"], "prompt_usd_per_token": 1e-12,
               "completion_usd_per_token": 1e-14, "max_completion_tokens": 131072}]
    js = _spend_file(ctx, d, 2.5e-5, 0.0, prices); _init(ctx, d, js, 1.0)
    r1 = _or(ctx, js, d / "dummy-key", _mockcall(ctx, d, js, tc=3e-5, n=1))
    r2 = _or(ctx, js, d / "dummy-key", _mockcall(ctx, d, js, tc=3e-5, n=2))
    req = _req(d)
    o["c2"] = {"rc1": r1["rc"], "rc2": r2["rc"], "requests": req, "log": _log(d)}
    d = ctx.W / "f8/c3"; d.mkdir(parents=True, exist_ok=True); (d / "dummy-key").write_text("sk-or-v1-S1-DUMMY\n")
    args = _mockcall(ctx, d, None)
    r = L.run([ctx.py, _tools(ctx) / "or_call.py", "--job-spend", d / "no-such-spend.json", "--key-file", d / "dummy-key", *args],
              cwd=ctx.subj)
    o["c3"] = {"rc": r["rc"], "requests": _req(d)}
    srcs = {str(p.relative_to(ctx.subj)): p.read_text(encoding="utf-8", errors="replace")
            for p in (_tools(ctx)).glob("*.py")}
    o["c_literal"] = sorted(k for k, v in srcs.items() if re.search(r"(JOB_ID|job_id)\s*=\s*[\"']", v))
    lg = _log(ctx.W / "f8/c2")
    def _mt(e):
        b = (e.get("request") or {}).get("body") if isinstance(e, dict) else None
        if isinstance(b, str):
            try:
                b = json.loads(b)
            except ValueError:
                b = None
        return b.get("max_tokens") if isinstance(b, dict) else None
    o["c_max_tokens"] = [_mt(e) for e in lg]
    o["c_jobid"] = L.jl(ctx.W / "f8/c2/job-spend.json")["job_id"]
    o["c_rows"] = lines(ctx.W / "f8/c2/spend/spend-ledger.jsonl")
    o["c_baseline"] = [L.jl(p) for p in (ctx.W / "f8/c2/spend").glob("*baseline*.json")]
    return o


@guarded
def d_P1(ctx):
    T = _tools(ctx)
    o = {"files": {f: (T / f).is_file() for f in ("or_call.py", "fixture_run.py", "judge_batch.py")},
         "tests": sorted(p.name for p in (ctx.subj / "tests").glob("test_edi_*.py"))}
    lg = _log(ctx.W / "f8/c2")
    o["entry_keys"] = sorted(lg[0].keys()) if lg and isinstance(lg[0], dict) else None
    o["job1_keys"] = ctx.expect["job1_log_keys"]
    if lg:
        p = ctx.W / "p1/custody/evidence/harness-maker-p1.log"; p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ctx.W / "f8/c2/harness-maker-f8.log", p)
        r = L.run([ctx.py, "-c", "import sys,json; sys.path.insert(0,'kit'); import custody_history as h; "
                   "v=h.read_log(sys.argv[1]); print(json.dumps({'n': len(v) if hasattr(v,'__len__') else None}))", p],
                  cwd=ctx.subj)
        o["read_log"] = {"rc": r["rc"], "out": r["stdout"][-400:], "err": r["stderr"][-800:]}
    return o


# ------------------------------------------------------------------ X1 / V
def _emit_job(ctx, J, sw=False, tree=None):
    rec = J / "custody/record.custody.json"
    if rec.exists():
        rec.unlink()
    e = L.emit(ctx.py, tree or ctx.subj, J, switch=sw)
    out = {"rc": e["rc"], "written": e["record_written"], "kinds": e["kinds"], "out": (e["stdout"] + e["stderr"])[-1500:]}
    if e["record_written"]:
        out["record"] = L.jl(rec); out["check"] = L.check_job(ctx.py, ctx.custody, J)
    return out


def _x1_jobs(ctx):
    if "x1" in ctx.cache:
        return ctx.cache["x1"]
    res = {}
    for name in ("clean", "X1-clean", "P-X1"):
        J = ctx.clean(ctx.W / "x1" / name)
        if name != "clean":
            shutil.copyfile(ctx.C / "plants" / ctx.plant(name)["custody_json"], J / "inputs/custody.json")
        res[name] = _emit_job(ctx, J) | {"J": str(J), "inputs_expected": L.jl(J / "inputs/custody.json").get("x-plumbline")}
    ctx.cache["x1"] = res
    return res


@guarded
def d_X1(ctx):
    r = _x1_jobs(ctx)
    keys = ctx.expect["x1_owned_keys"]
    return {"clean": {k: r["clean"].get(k) for k in ("rc", "written", "check")} | {"owned": {k: xp(r["clean"].get("record")).get(k) for k in keys}},
            "x1": {k: r["X1-clean"].get(k) for k in ("rc", "written", "check", "inputs_expected")}
            | {"inputs": xp(r["X1-clean"].get("record")).get("inputs")},
            "px1": {k: r["P-X1"].get(k) for k in ("rc", "written", "kinds")}
            | {"owned": {k: xp(r["P-X1"].get("record")).get(k) for k in keys}}}


def _vrecs(ctx):
    """Clean records for V: clean frozen job, T4 job, job-rejected with the switch, X1-clean."""
    if "vrecs" in ctx.cache:
        return ctx.cache["vrecs"]
    x = _x1_jobs(ctx)
    j4 = t4_emitted(ctx)
    jr = ctx.jr(ctx.W / "v" / "jr-sw"); e = _emit_job(ctx, jr, sw=True)
    v = {"clean": x["clean"]["J"], "x1": x["X1-clean"]["J"], "t4": j4.get("J"), "jr-sw": str(jr) if e["written"] else None}
    ctx.cache["vrecs"] = v
    return v


def _vrun(ctx, J, rec=None, custody=None, verifier=None, tag="v"):
    oj = ctx.W / "v" / "json" / f"{tag}.json"; oj.parent.mkdir(parents=True, exist_ok=True)
    r = L.verify(ctx.py, ctx.subj, custody or ctx.custody, J, rec=rec, out_json=oj, verifier=verifier)
    return {k: r.get(k) for k in ("rc", "kinds", "failures", "traceback", "error")} | {"out": (r.get("stdout") or "")[-1200:] + (r.get("stderr") or "")[-800:],
                                                                                     "json": r.get("json")}


@guarded
def d_V(ctx):
    vf = ctx.subj / "kit/plumbline_verify.py"
    if not vf.is_file():
        return {"error": "no kit/plumbline_verify.py"}
    V = _vrecs(ctx); o = {"clean": {}}
    for k, J in V.items():
        o["clean"][k] = _vrun(ctx, Path(J), tag="clean-" + k) if J else {"rc": None, "error": "no record"}
    plants = {}
    for pid in ctx.expect["v_plants"]:
        p = ctx.plant(pid); J0 = V.get(p["base"])
        if not J0:
            plants[pid] = {"rc": None, "error": f"base {p['base']} has no record", "expect": p["kind"]}; continue
        J = L.copytree(J0, ctx.W / "v" / "plant" / pid)
        recp = J / "custody/record.custody.json"
        if p.get("record_ops"):
            L.jw(recp, L.apply_ops(L.jl(recp), p["record_ops"]))
        for op in p.get("ledger_ops") or []:
            f = J / "inputs/custody-events.jsonl"; ls = f.read_text().splitlines()
            d = json.loads(ls[op["line"] - 1]); ls[op["line"] - 1] = json.dumps(L.apply_ops(d, op["ops"]), ensure_ascii=False)
            f.write_text("\n".join(ls) + "\n")
        for lop in p.get("log_ops") or []:              # a harness log edited; its digests in the record follow it
            f = J / lop["file"]; v = json.loads(f.read_text(encoding="utf-8"))
            f.write_text(json.dumps(L.apply_ops(v, lop["ops"]), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            new_sha, base = L.sha(f), f.name
            def _rehash(o):
                if isinstance(o, dict):
                    if any(isinstance(x, str) and x.split("/")[-1] == base for x in o.values()) and isinstance(o.get("digest"), dict):
                        o["digest"]["sha256"] = new_sha
                    for x in o.values():
                        _rehash(x)
                elif isinstance(o, list):
                    for x in o:
                        _rehash(x)
            rd = L.jl(recp); _rehash(rd); L.jw(recp, rd)
        cust = None
        if p.get("checker_append"):
            cust = L.copytree(ctx.custody, ctx.W / "v" / "plant" / (pid + "-custody"))
            with open(cust / "checker/check.py", "a") as fh:
                fh.write(p["checker_append"])
        plants[pid] = _vrun(ctx, J, custody=cust, tag=pid) | {"expect": p["kind"], "expect_rc": p.get("rc", 4)}
    o["plants"] = plants
    # V2: legacy job-1 record, schema file
    # job 1's files_dir is the repo root, so the copy is of the base tree (no .git), and the job inside it
    lt = ctx.W / "v" / "legacy-tree"
    if not lt.exists():
        shutil.copytree(ctx.base, lt, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    lj = lt / ctx.expect["v2_legacy_job"]
    o["legacy"] = _vrun(ctx, lj, tag="legacy")
    sp = ctx.subj / "schemas/x-plumbline/x-plumbline-v1.schema.json"
    o["schema"] = L.jl(sp) if sp.is_file() else None
    o["schema_ref_in_records"] = {k: xp(L.jl(Path(J) / "custody/record.custody.json")).get("schema") if J else None for k, J in V.items()}
    return o


@guarded
def d_V5(ctx):
    j4 = t4_emitted(ctx); x = xp(j4.get("record"))
    logs = []
    J = Path(j4["J"]) if j4.get("J") else None
    if J:
        for lg in sorted((J / "custody/evidence").glob("harness-*.log")):
            try:
                v = json.loads(lg.read_text())
            except ValueError:
                continue
            for e in (v if isinstance(v, list) else []):
                g = (e.get("generation") or {}) if isinstance(e, dict) else {}
                g = g.get("data", g) if isinstance(g, dict) else {}
                if isinstance(g, dict) and g.get("total_cost") is not None:
                    logs.append(float(g["total_cost"]))
    return {"spend": x.get("spend"), "log_costs": logs, "ledger_spend": [l for l in (j4.get("ledger") or []) if l.get("event") == "spend"],
            "tol": ctx.expect["spend_tol"]}


@guarded
def d_V7(ctx, verifier=None, tag="v7", job=None):
    J = job or _vrecs(ctx).get("t4")
    vf = Path(verifier) if verifier else ctx.subj / "kit/plumbline_verify.py"
    if not J or not vf.is_file():
        return {"error": "no T4 record or no verifier"}
    J1 = L.copytree(J, ctx.W / tag / "rw")
    b = L.tree_digest(J1); r1 = _vrun(ctx, J1, verifier=vf, tag=tag + "-rw"); a = L.tree_digest(J1)
    J2 = L.copytree(J, ctx.W / tag / "ro")
    for p in sorted([J2, *J2.rglob("*")], key=lambda p: -len(p.parts)):
        os.chmod(p, p.stat().st_mode & ~0o222)
    try:
        r2 = _vrun(ctx, J2, verifier=vf, tag=tag + "-ro")
    finally:
        for p in [J2, *J2.rglob("*")]:
            os.chmod(p, p.stat().st_mode | 0o700)
    imports = []
    for n in ast.walk(ast.parse(vf.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            imports += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            imports += [n.module or ""] + [a.name for a in n.names]
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and "emit_custody" in n.value:
            imports.append("str:" + n.value[:80])
    return {"rw": {"rc": r1["rc"], "failures": r1["failures"]}, "ro": {"rc": r2["rc"], "failures": r2["failures"]},
            "changed": L.diff_digest(b, a), "emit_imports": [i for i in imports if "emit_custody" in i]}


@guarded
def d_V8(ctx, tree=None, tag="v8"):
    """tree: a P-V8 wrapper tree (must be refused) or the subject (clean: J4 closes)."""
    o = {}
    if tree is None:
        j4 = t4_job(ctx)
        cl = [s for s in j4.get("steps", []) if s["name"] == "close"]
        rl = L.jl(Path(j4["W"]) / "run-log.json") if (Path(j4["W"]) / "run-log.json").is_file() else {"runs": []}
        o["clean"] = {"close_rc": cl[0]["rc"] if cl else None, "close_out": (cl[0]["stdout"] + cl[0]["stderr"])[-1500:] if cl else None,
                      "rows": [{k: r.get(k) for k in ("event", "kind", "job_id")} for r in rl.get("runs", [])]}
        return o
    b = t4_job(ctx, tag, tree=tree, extra=("--inject-hand", "--close-switch", "--no-spend"))
    cl = [s for s in b.get("steps", []) if s["name"] == "close"]
    rl = L.jl(Path(b["W"]) / "run-log.json") if (Path(b["W"]) / "run-log.json").is_file() else {"runs": []}
    o["planted"] = {"close_rc": cl[0]["rc"] if cl else None, "close_out": (cl[0]["stdout"] + cl[0]["stderr"])[-2000:] if cl else None,
                    "rows": [{k: r.get(k) for k in ("event", "kind", "job_id")} for r in rl.get("runs", [])],
                    "build_error": b.get("error"), "steps": [s["name"] for s in b.get("steps", [])]}
    if cl:
        r = L.run([ctx.py, Path(tree) / "kit/plumbline_job.py", "custody", "--job-dir", b["J"], "--allow-hand-times",
                   "--custody", ctx.custody], cwd=tree)
        o["planted"]["reemit"] = {"rc": r["rc"], "out": (r["stdout"] + r["stderr"])[-1200:]}
    return o


def make_wrapped(ctx, kind, label):
    """A clean clone of the subject with one kit file wrapped (the wrapper text is controls data)."""
    spec = ctx.expect["wrappers"][kind]
    def mut(d):
        f = d / spec["file"]
        if not f.is_file():
            return
        shutil.move(f, d / spec["orig"])
        f.write_text(ctx.wrapper(kind), encoding="utf-8")
    return L.clean_clone(ctx.subj, ctx.W / "wrapped" / label, mutate=mut, label=label)


@guarded
def d_V9G(ctx):
    names = L.git(ctx.subj, "diff", "--name-status", L.BASE_REV, "HEAD").splitlines()
    tests = {p.name: p.read_text(encoding="utf-8", errors="replace") for p in (ctx.subj / "tests").glob("test_plumbline_verify*.py")}
    newfix = sorted({n.split("\t")[-1].split("/")[3] for n in names if n.split("\t")[-1].startswith("tests/fixtures/custody/")
                     and n[0] == "A" and len(n.split("\t")[-1].split("/")) > 4})
    docs = {f: (ctx.subj / f).read_text(encoding="utf-8", errors="replace") if (ctx.subj / f).is_file() else ""
            for f in ("docs/custody-emission.md", "kit/README.md")}
    prot = {f: (L.sha(ctx.subj / f) if (ctx.subj / f).is_file() else None) for f in ctx.expect["g1_protected"]}
    prot_base = {f: (L.sha(ctx.base / f) if (ctx.base / f).is_file() else None) for f in ctx.expect["g1_protected"]}
    mk = [x for x in L.git(ctx.subj, "log", "--author=E-DI Maker", "--name-only", "--format=", L.BASE_REV + "..HEAD").splitlines() if x.strip()]
    return {"name_status": names, "maker_paths": sorted(set(mk)), "tests": {k: len(v) for k, v in tests.items()},
            "test_kinds": sorted({k for k in ctx.expect["v_kinds"] if any(k in v for v in tests.values())}),
            "new_fixture_dirs": newfix, "doc_text": docs, "protected": prot, "protected_base": prot_base}


@guarded
def d_G2(ctx):
    res = {}
    env = {"EDI_CORPUS": ctx.corpus}
    for side, src in (("base", ctx.base), ("subject", ctx.subj)):
        d = L.clean_clone(src, ctx.W / "g2" / side)
        out = {}
        for t in sorted((d / "tests").glob("*.py")):
            r = L.run([ctx.py, t.relative_to(d)], cwd=d, env=env, timeout=1800)
            out[t.name] = {"rc": r["rc"], "tail": (r["stdout"] + r["stderr"])[-600:]}
        r = L.run([ctx.py, "tools/build_schemas.py", "--check"], cwd=d, env=env)
        out["build_schemas --check"] = {"rc": r["rc"], "tail": (r["stdout"] + r["stderr"])[-600:]}
        res[side] = out
        res[side + "_porcelain"] = L.git(d, "status", "--porcelain")
    ctx.cache["g2"] = {"subject_porcelain": res["subject_porcelain"]}
    base_names = set(res["base"])
    res["new_test_files"] = sorted(set(res["subject"]) - base_names)
    res["new_test_text"] = {n: (ctx.subj / "tests" / n).read_text(encoding="utf-8", errors="replace")[:200000]
                            for n in res["new_test_files"] if (ctx.subj / "tests" / n).is_file()}
    return res


@guarded
def d_F8d(ctx):
    """Live, on the shared key by path (approval item 19), at most US$0.07: (i) a --max-cost refusal; (ii) one small
    settled call. Key usage is read by the subject (--spend-status) and by the instrument itself."""
    if os.environ.get("S1_LIVE") != "1":
        return {"error": "NOT-RUN: live arm off (S1_LIVE != 1)"}
    if not (_tools(ctx) / "or_call.py").is_file():
        return {"error": "no tools/edi/or_call.py"}
    key = Path(os.environ.get("S1_KEY_FILE", "/workspace/.openrouter-key"))
    f = ctx.expect["f8d"]; seat = T4.MAKER
    d = ctx.W / "f8d"; d.mkdir(parents=True, exist_ok=True)
    js = _spend_file(ctx, d, f["bound_usd"], 0.0, f["prices"], real=True)
    o = {"bound_usd": f["bound_usd"], "delta_tol": f["delta_tol"]}
    o["init_rc"] = _or(ctx, js, key, ["--init-spend"])["rc"]
    m = d / "msgs.json"; L.jw(m, [{"role": "user", "content": f["prompt"]}])

    def call(n, cap):
        return ["--max-cost", str(cap), "--seat", seat["seat"], "--log", d / f"harness-{seat['seat']}-f8d-{n}.log",
                "--model", seat["model"], "--tag", seat["tag"], "--pin-provider", seat["provider"], "--messages", m,
                "--out", d / f"reply-{n}.txt", "--call", f"f8d_{n}"]

    def status(n):
        p = d / f"status-{n}.json"; r = _or(ctx, js, key, ["--spend-status", "--out", p])
        return r["rc"], (L.jl(p) if p.is_file() else {})

    # (i) cap below the worst case: refused before sending
    u0 = L.key_usage(key); time.sleep(2)
    r = _or(ctx, js, key, call(1, f["cap_i"]))
    time.sleep(f["wait_i_s"])
    rc_s, st = status(1); u1 = L.key_usage(key)
    o["i"] = {"rc": r["rc"], "cap": f["cap_i"], "log": _log_file(d / f"harness-{seat['seat']}-f8d-1.log"),
              "reply_exists": (d / "reply-1.txt").exists(), "reading_rc": rc_s, "status": st,
              "key_delta": st.get("key_delta_usd"), "inst_before": u0, "inst_after": u1,
              "inst_delta": (u1 - u0) if (u0 is not None and u1 is not None) else None, "err": r["stderr"][-600:]}
    # (ii) a cap above the worst case: logged and settled at or under the cap; read >= 3 min after
    r = _or(ctx, js, key, call(2, f["cap_ii"]))
    t_done = time.time(); time.sleep(f["wait_ii_s"])
    rc_s, st = status(2); u2 = L.key_usage(key)
    rows = lines(d / "spend/spend-ledger.jsonl")
    lst = st.get("last_settle_at"); late = None
    try:
        late = (datetime.fromisoformat(st["read_at"].replace("Z", "+00:00")) -
                datetime.fromisoformat(lst.replace("Z", "+00:00"))).total_seconds() >= 180
    except Exception:
        late = None
    o["ii"] = {"rc": r["rc"], "cap": f["cap_ii"], "log": _log_file(d / f"harness-{seat['seat']}-f8d-2.log"),
               "reply_exists": (d / "reply-2.txt").exists(), "spend_rows": rows, "reading_rc": rc_s, "status": st,
               "reading_after_3min": bool(late) and (time.time() - t_done) >= 180, "inst_after": u2,
               "inst_delta_total": (u2 - u0) if (u0 is not None and u2 is not None) else None, "err": r["stderr"][-600:]}
    return o


def _log_file(p):
    p = Path(p)
    if not p.is_file():
        return []
    try:
        v = json.loads(p.read_text()); return v if isinstance(v, list) else [v]
    except ValueError:
        return ["<unparseable>"]


@guarded
def d_FG(ctx, tree=None):
    """item 30: the field guide at the subject (G4-G7 read this observation; G4 also reads the G1 diff fields)."""
    import judges as _J
    d = Path(tree) if tree else ctx.subj
    p = d / _J.FG["path"]
    raw = p.read_bytes() if p.is_file() else b""
    try:
        text, utf8 = raw.decode("utf-8"), True
    except UnicodeDecodeError:
        text, utf8 = raw.decode("utf-8", "replace"), False
    c2 = ctx if tree is None else _with_subj(ctx, d)
    g = d_V9G(c2)
    return {**({"error": g["error"]} if isinstance(g, dict) and g.get("error") else {}),
            "exists": p.is_file(), "size": len(raw), "utf8": utf8, "sha256": L.sha(p) if p.is_file() else None,
            "text": text, "name_status": g.get("name_status"), "maker_paths": g.get("maker_paths"),
            "protected": g.get("protected"), "protected_base": g.get("protected_base")}


def _with_subj(ctx, d):
    import copy as _c
    c2 = _c.copy(ctx); c2.subj = Path(d); c2.cache = {}
    return c2
