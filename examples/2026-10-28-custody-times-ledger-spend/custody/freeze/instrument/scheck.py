#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — S1 runner for job 2026-10-28-custody-times-ledger-spend.
"""Run every S1 check (bar.md T/F/I/P/X/V/G) on a subject checkout, then the instrument controls, and write
OUT/evidence/<ID>.json plus OUT/summary.json. The summary carries the runner's own stamp (started_at, finished_at,
writer). A control that comes out wrong makes the batch void (exit 3). Exit 0: all PASS; 1: some FAIL; 3: void.

usage: scheck.py --subject TREE --base TREE --custody CHECKOUT --controls DIR --work DIR --corpus DIR --python PY --out DIR
                 [--only ID,ID] [--no-controls] [--save-obs]
F8d is live only with env S1_LIVE=1 (the shared key, by path; never printed)."""
from __future__ import annotations

import argparse, copy, json, os, re, sys, traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L          # noqa: E402
import drivers as D      # noqa: E402
import judges as JG      # noqa: E402

CHECKS = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "F1a", "F1b", "F1c", "F1d", "F1e", "F1f", "F1g", "F1h", "I1", "F7a",
          "F8a", "F8b", "F8c", "F8d", "P1", "X1", "V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]
V_IDS = {"V1": (["P-V1", "P-V1w"], JG._v1), "V2": (["P-V2a", "P-V2b", "P-V2c", "P-V2d"], JG._v2),
         "V3": (["P-V3a", "P-V3b", "P-V3c", "P-V3d"], None), "V4": (["P-V4a", "P-V4b", "P-V4c"], None), "V6": (["P-V6"], None)}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        return False, [f"judge error {type(e).__name__}: {e}", traceback.format_exc()[-1500:]]


def run_checks(ctx, only):
    want = lambda *ids: any(i in only for i in ids)
    obs, res = {}, {}
    if want("G2", "T7"):
        obs["G2"] = D.d_G2(ctx)
    if want("T1"):
        obs["T1"] = D.d_T1(ctx)
    if want("T2", "T3"):
        obs["T2"] = obs["T3"] = D.d_T2T3(ctx)
    if want("T4"):
        obs["T4"] = D.d_T4(ctx)
    if want("T5"):
        obs["T5"] = D.d_T5(ctx)
    if want("T6"):
        obs["T6"] = D.d_T6(ctx)
    if want("T7"):
        obs["T7"] = D.d_T7(ctx)
    if want("F1a", "F1b", "F1c", "F1d", "F1e", "F1f", "F1g"):
        f = D.d_F1(ctx)
        for k in ("F1a", "F1b", "F1c", "F1d", "F1e", "F1f", "F1g"):
            obs[k] = f
    if want("F1h"):
        obs["F1h"] = D.d_F1h(ctx)
    if want("I1"):
        obs["I1"] = D.d_I1(ctx)
    if want("F7a"):
        obs["F7a"] = D.d_F7a(ctx)
    if want("F8a", "F8b", "F8c"):
        f = D.d_F8abc(ctx)
        for k in ("F8a", "F8b", "F8c"):
            obs[k] = f
    if want("F8d"):
        obs["F8d"] = D.d_F8d(ctx)
    if want("P1"):
        obs["P1"] = D.d_P1(ctx)
    if want("X1"):
        obs["X1"] = D.d_X1(ctx)
    if want("V1", "V2", "V3", "V4", "V5", "V6"):
        v = D.d_V(ctx)
        for k in ("V1", "V2", "V3", "V4", "V6"):
            obs[k] = v
        obs["_V"] = v
    if want("V5"):
        obs["V5"] = D.d_V5(ctx)
    if want("V7"):
        obs["V7"] = D.d_V7(ctx)
    if want("V8"):
        try:
            wt = D.make_wrapped(ctx, "P-V8", "P-V8")
            planted = D.d_V8(ctx, tree=wt)
        except Exception as e:
            planted = {"error": f"P-V8 wrapper: {type(e).__name__}: {e}"}
        obs["V8"] = {"planted": planted, "clean": D.d_V8(ctx)}
    if want("V9", "G1", "G3"):
        g = D.d_V9G(ctx)
        for k in ("V9", "G1", "G3"):
            obs[k] = g
    if want("G4", "G5", "G6", "G7"):
        f = D.d_FG(ctx)
        for k in ("G4", "G5", "G6", "G7"):
            obs[k] = f
    E = ctx.expect
    for cid in CHECKS:
        if cid not in only or cid not in obs:
            continue
        fn, args = judge_args(E, cid, obs, res)
        res[cid] = safe(getattr(JG, fn), *args)
    # T3's V3/V8 tie (disclosure listing): recompute once V3 and V8 are known
    if "T3" in res and "T3" in obs:
        fn, args = judge_args(E, "T3", obs, res)
        res["T3"] = safe(getattr(JG, fn), *args)
    ctx.judged = {cid: judge_args(E, cid, obs, res) for cid in res}
    return obs, res


# ---------------------------------------------------------------- instrument controls (tree mutants)
def _sub(path, pat, rep):
    def m(d):
        f = d / path; s = f.read_text(encoding="utf-8"); n = re.subn(pat, rep, s, flags=re.M)
        f.write_text(n[0], encoding="utf-8"); m.applied = n[1]
    m.applied = 0
    return m


def run_controls(ctx, ids):
    out = {}
    W = ctx.W / "controls"; W.mkdir(parents=True, exist_ok=True)
    def rec(cid, want, ok, why, **kw):
        out[cid] = {"want": want, "got": "PASS" if ok else "FAIL", "right": (ok if want == "PASS" else not ok), "why": why[:8], **kw}
    def sig_rec(cid, ok, why, sig, **kw):
        # a planted control is right only if it FAILs AND names its own planted defect (signature), so a subject that
        # fails the check for another reason cannot make the control look right by accident
        hit = any(sig in w for w in why)
        out[cid] = {"want": "FAIL", "got": "PASS" if ok else "FAIL", "right": (not ok) and hit, "signature": sig,
                    "signature_seen": hit, "why": [w for w in why if sig in w][:2] + why[:6], **kw}
    # T5 stand-in: a clone of BASE whose emitter accepts --allow-hand-times and ignores it (nothing else changes), so
    # base kinds are kept with and without the switch: the T5 judge must PASS it, and FAIL each single mutation of it.
    t5s = W / "C-T5s"
    def standin(d):
        f = d / "kit/emit_custody.py"; t = f.read_text(encoding="utf-8")
        anchor = '    ap.add_argument("--job-dir", required=True)\n'
        if t.count(anchor) != 1:
            raise RuntimeError("T5 stand-in anchor not found once")
        f.write_text(t.replace(anchor, anchor + '    ap.add_argument("--allow-hand-times", action="store_true")  # S1 stand-in\n'),
                     encoding="utf-8")
    if any(c in ids for c in ("C-T5c", "C-T5p1", "C-T5p2")):
        L.clean_clone(ctx.base, t5s, mutate=standin, label="C-T5s")
    if "C-T5c" in ids:
        o = D.d_T5(ctx, tree=t5s); ok, why = safe(JG.j_T5, o)
        rec("C-T5c", "PASS", ok, why, cases=len(o.get("cases") or []))
    for cid, path, pat, rep, sig in (("C-T5p1", "kit/custody_history.py", r"^TOLERANCE_S\s*=\s*60\b", "TOLERANCE_S = 600", "TOLERANCE_S = 600"),
                                     ("C-T5p2", "kit/emit_custody.py", r"ref\.add\((\"order\", f\"\{n\} \{H\.iso\(t\)\} is after the job's close)",
                                      r"(lambda *a: None)(\1", "after-close refusal line count 0")):
        if cid not in ids:
            continue
        mut = _sub(path, pat, rep)
        try:
            t = L.clean_clone(t5s, W / cid, mutate=mut, label=cid)
            o = D.d_T5(ctx, tree=t); ok, why = safe(JG.j_T5, o)
        except Exception as e:
            ok, why = False, [f"{type(e).__name__}: {e}"]
        sig_rec(cid, ok, why, sig, mutation_applied=mut.applied)
    if "C-T7p" in ids:
        try:
            t = D.make_wrapped(ctx, "C-T7p", "C-T7p")
            o = D.d_T7(ctx, tree=t)
            o = {**o, "t4_changed": [], "porcelain_after_suite": ""}   # neutral: the FAIL must come from the jr runs
            ok, why = safe(JG.j_T7, o)
        except Exception as e:
            ok, why = False, [f"{type(e).__name__}: {e}"]
        sig_rec("C-T7p", ok, why, "emitter changed job files")
    # V7 stand-in verifier (controls data): reads the inputs, writes nothing, exit 0. Clean must PASS; wrapped with the
    # C-V7p wrapper (writes <record>.verified) must FAIL naming the change.
    if "C-V7c" in ids or "C-V7p" in ids:
        vs = W / "C-V7s"; vs.mkdir(parents=True, exist_ok=True)
        (vs / "plumbline_verify.py").write_text(ctx.wrapper("C-V7s"), encoding="utf-8")
        vp = W / "C-V7p"; vp.mkdir(parents=True, exist_ok=True)
        (vp / "_s1_orig_plumbline_verify.py").write_text(ctx.wrapper("C-V7s"), encoding="utf-8")
        (vp / "plumbline_verify.py").write_text(ctx.wrapper("C-V7p"), encoding="utf-8")
        cj = L.copytree(ctx.C / "jobs/clean", W / "C-V7-job")   # held-out clean job: subject-independent
        if "C-V7c" in ids:
            o = D.d_V7(ctx, verifier=vs / "plumbline_verify.py", tag="ctl-v7c", job=cj); ok, why = safe(JG.j_V7, o)
            rec("C-V7c", "PASS", ok, why)
        if "C-V7p" in ids:
            o = D.d_V7(ctx, verifier=vp / "plumbline_verify.py", tag="ctl-v7p", job=cj); ok, why = safe(JG.j_V7, o)
            sig_rec("C-V7p", ok, why, ".verified")
    if "C-G1p" in ids:
        def m(d):
            with open(d / "tools/pin.json", "ab") as fh:
                fh.write(b" ")
        try:
            t = L.clean_clone(ctx.subj, W / "C-G1p", mutate=m, label="C-G1p")
            c2 = copy.copy(ctx); c2.subj = t; c2.cache = {}
            ok, why = safe(JG.j_G1, D.d_V9G(c2), ctx.expect["g1_allow"])
        except Exception as e:
            ok, why = False, [f"{type(e).__name__}: {e}"]
        sig_rec("C-G1p", ok, why, "tools/pin.json outside the allow-list")
    # item 30 (G4-G7): base clones carrying a held-out guide text (controls/fg/), committed; clean must PASS all four,
    # each planted one must FAIL its own check naming its defect
    fgc = ctx.expect.get("fg_controls") or {}
    if fgc and any(c.startswith("C-G4") or c[:4] in ("C-G5", "C-G6", "C-G7") for c in ids):
        P = JG.FG["path"]
        def put(src, dst):
            def m(d):
                (d / dst).parent.mkdir(parents=True, exist_ok=True)
                (d / dst).write_bytes((ctx.C / src).read_bytes())
            return m
        def fg_obs(cid, src, dst=P):
            try:
                t = L.clean_clone(ctx.base, W / cid, mutate=put(src, dst), label=cid)
                return D.d_FG(ctx, tree=t)
            except Exception as e:
                return {"error": f"{type(e).__name__}: {e}"}
        if any(c.endswith("c") and c[:4] in ("C-G4", "C-G5", "C-G6", "C-G7") for c in ids):
            oc = fg_obs("C-G-clean", fgc["clean"])
            for cid, fn, args in (("C-G4c", JG.j_G4, [ctx.expect["g1_allow"]]), ("C-G5c", JG.j_G5, []),
                                  ("C-G6c", JG.j_G6, []), ("C-G7c", JG.j_G7, [])):
                if cid in ids:
                    ok, why = safe(fn, oc, *args); rec(cid, "PASS", ok, why)
        for cid, fn, args, sig in (("C-G4p", JG.j_G4, [ctx.expect["g1_allow"]], "missing at the subject"),
                                   ("C-G5p", JG.j_G5, [], "no status line"),
                                   ("C-G6p", JG.j_G6, [], "B1-tripwire"),
                                   ("C-G7p", JG.j_G7, [], "leak:")):
            if cid not in ids:
                continue
            spec = fgc[cid]
            op = fg_obs(cid, *spec) if isinstance(spec, list) else fg_obs(cid, spec)
            ok, why = safe(fn, op, *args); sig_rec(cid, ok, why, sig)
    # judge-level obs pairs (controls/obs/<ID>.{clean,planted}.json): the frozen judge must score them as labelled
    od = ctx.C / "obs"
    if od.is_dir():
        for p in sorted(od.glob("*.json")):
            cid, lab = p.name[:-5].rsplit(".", 1)
            o = L.jl(p); ok, why = judge_one(ctx, cid, o)
            rec(f"OBS-{cid}.{lab}", "PASS" if lab == "clean" else "FAIL", ok, why)
    return out


def judge_args(E, cid, obs, res):
    """The judge and its exact arguments for one check (also saved by --save-obs, so obs pairs replay exactly)."""
    o = obs[cid]
    if cid in V_IDS:
        ids, extra = V_IDS[cid]; return "j_V", [o, ids, extra]
    if cid == "V5":
        return "j_V5", [o, obs.get("_V") or {"error": "V not run"}]
    if cid == "V8":
        return "j_V8", [o["planted"], o["clean"]]
    if cid in ("V9", "G1", "G2", "G3"):
        return "j_" + cid, [o, {"V9": E["v_kinds"], "G1": E["g1_allow"], "G2": E["g2_parts"], "G3": E["g3_terms"]}[cid]]
    if cid == "G4":
        return "j_G4", [o, E["g1_allow"]]
    if cid == "T3":
        return "j_T3", [o, res["V3"][0] if "V3" in res else None, res["V8"][0] if "V8" in res else None]
    return "j_" + cid, [o]


def judge_one(ctx, cid, o):
    """o: {"judge": "j_X", "args": [...]} as saved by --save-obs (judged_args)."""
    if o.get("judge") != "j_" + cid.split("-")[0] and not (cid in V_IDS and o.get("judge") == "j_V"):
        return False, [f"obs pair judge {o.get('judge')} does not match {cid}"]
    dec = lambda x: getattr(JG, x["$fn"]) if isinstance(x, dict) and set(x) == {"$fn"} else x
    return safe(getattr(JG, o["judge"]), *[dec(x) for x in o["args"]])


def _old_judge_one(ctx, cid, o):
    E = ctx.expect
    if cid in V_IDS:
        return safe(JG.j_V, o, *V_IDS[cid])
    if cid == "V5":
        return safe(JG.j_V5, o["o"], o["v"])
    if cid == "V8":
        return safe(JG.j_V8, o["planted"], o["clean"])
    if cid in ("V9", "G1", "G2", "G3"):
        arg = {"V9": E["v_kinds"], "G1": E["g1_allow"], "G2": E["g2_parts"], "G3": E["g3_terms"]}[cid]
        return safe(getattr(JG, "j_" + cid), o, arg)
    return safe(getattr(JG, "j_" + cid), o)


def main():
    ap = argparse.ArgumentParser()
    for a in ("subject", "base", "custody", "controls", "work", "corpus", "python", "out"):
        ap.add_argument("--" + a, required=True)
    ap.add_argument("--only"); ap.add_argument("--no-controls", action="store_true"); ap.add_argument("--save-obs", action="store_true")
    a = ap.parse_args()
    started = now()
    ctx = D.Ctx(a.python, a.subject, a.base, a.custody, a.controls, a.work, a.corpus)
    only = a.only.split(",") if a.only else CHECKS
    out = Path(a.out); ev = out / "evidence"; ev.mkdir(parents=True, exist_ok=True)
    obs, res = run_checks(ctx, only)
    for cid, (ok, why) in res.items():
        L.jw(ev / f"{cid}.json", {"id": cid, "verdict": "PASS" if ok else "FAIL", "reasons": why, "obs": obs.get(cid)})
    if "T5" in obs and isinstance(obs["T5"], dict):
        (ev / "T5-listing.txt").write_text("".join(
            f"{c['case']}: base {c['base']['kinds']} | no switch exit {c['nosw']['rc']} {c['nosw']['kinds']} | "
            f"switch exit {c['sw']['rc']} {c['sw']['kinds']}\n" for c in obs["T5"].get("cases") or []))
    ctl = {} if a.no_controls else run_controls(ctx, ctx.expect.get("instrument_controls", []))
    void = [k for k, v in ctl.items() if not v["right"]]
    summ = {"job": "2026-10-28-custody-times-ledger-spend", "instrument": "S1",
            "writer": "scheck.py@" + L.sha12(Path(__file__)), "started_at": started,
            "subject": str(a.subject), "subject_rev": L.git(Path(a.subject), "rev-parse", "HEAD") if (Path(a.subject) / ".git").exists() else None,
            "base_rev": L.BASE_REV, "controls_manifest_sha256": L.sha(Path(a.controls) / "MANIFEST.sha256"),
            "live_f8d": os.environ.get("S1_LIVE") == "1",
            "results": {k: ("PASS" if v[0] else "FAIL") for k, v in res.items()},
            "passed": sum(1 for v in res.values() if v[0]), "total": len(res),
            "controls": ctl, "controls_run": not a.no_controls, "void": bool(void), "void_because": void}
    summ["finished_at"] = now()
    L.jw(out / "summary.json", summ)
    if a.save_obs:
        enc = lambda x: {"$fn": x.__name__} if callable(x) else x
        L.jw(out / "obs.json", {k: {"judge": fn, "args": [enc(x) for x in args], "verdict": "PASS" if res[k][0] else "FAIL"}
                                for k, (fn, args) in ctx.judged.items()})
    print(json.dumps({k: summ[k] for k in ("passed", "total", "void", "void_because", "results")}))
    sys.exit(3 if void else 0 if all(v[0] for v in res.values()) and len(res) == len(only) else 1)


if __name__ == "__main__":
    main()
