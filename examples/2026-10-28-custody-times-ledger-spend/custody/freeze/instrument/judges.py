# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — S1 judges for job 2026-10-28-custody-times-ledger-spend.
"""Pure functions obs -> (passed: bool, reasons: list[str]). An obs with "error" FAILs. No I/O here beyond
loading the frozen fg_rules.json (G4-G7) at import, so the obs-pair controls (controls/obs/<ID>.{clean,planted}.json)
exercise exactly the code that scores the subject."""
from __future__ import annotations
from datetime import datetime, timedelta
import json, re
from pathlib import Path

SLACK = timedelta(seconds=5)
SWITCH = "--allow-hand-times"


def T(v):
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def within(at, t0, t1):
    try:
        return T(t0) - SLACK <= T(at) <= T(t1) + SLACK
    except (ValueError, TypeError):
        return False


class R:
    def __init__(s):
        s.why = []

    def need(s, cond, msg):
        if not cond:
            s.why.append(msg)
        return bool(cond)

    def out(s):
        return (not s.why, s.why)


def _err(o):
    if not isinstance(o, dict):
        return ["no observation"]
    if o.get("error"):
        return ["driver: " + str(o["error"])[:400]]
    return None


def _nf(f):
    """A job-relative file name: an absolute or prefixed path is cut back to its inputs/ or custody/ part."""
    f = str(f or "")
    if f.startswith("./"):
        f = f[2:]
    if f.startswith("/") or "/jobs/" in f:
        i = max(f.rfind("/inputs/"), f.rfind("/custody/"))
        if i >= 0:
            f = f[i + 1:]
    return f


def _ln(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return -1


def hset(lst):
    out = set()
    for h in (lst or []):
        if isinstance(h, (list, tuple)) and len(h) >= 4:
            out.add((h[0], _nf(h[1]), _ln(h[2]), h[3]))
        elif isinstance(h, dict):
            out.add((h.get("field"), _nf(h.get("file")), _ln(h.get("line")), h.get("source")))
    return out


def j_T1(o):
    if (e := _err(o)): return False, e
    r = R()
    r.need(o.get("expect_writer"), "no kit/custody_ledger.py")
    r.need(o.get("map_ok"), f"T4 ledger steps {o.get('n_steps')} vs ledger lines {o.get('n_lines')}")
    r.need(any(x["src"].startswith("f1:") for x in o.get("rows", [])), "no F1 command lines to check")
    for x in o.get("rows", []):
        r.need(x.get("writer") == o.get("expect_writer"), f"{x['src']}: writer {x.get('writer')!r} != {o.get('expect_writer')!r}")
        r.need(within(x.get("at"), x["t0"], x["t1"]), f"{x['src']}: at {x.get('at')} outside [{x['t0']}, {x['t1']}] ±5 s")
    return r.out()


def j_T2(o):
    if (e := _err(o)): return False, e
    r = R()
    r.need(len(o.get("cases", {})) == 4, "not all four P-T2 plants ran")
    for pid, c in o.get("cases", {}).items():
        n = c["nosw"]
        r.need(n["rc"] == 3, f"{pid}: no-switch exit {n['rc']} (want 3)")
        r.need(not n["record_written"], f"{pid}: record written without the switch")
        r.need("hand-time" in n["kinds"], f"{pid}: no [hand-time] kind")
        miss = hset(c["expected"]) - hset(n["hand"])
        r.need(not miss, f"{pid}: hand time not named: {sorted(miss)}")
    return r.out()


def j_T3(o, v3=None, v8=None):
    if (e := _err(o)): return False, e
    r = R()
    r.need(len(o.get("cases", {})) == 4, "not all four P-T2 plants ran")
    for pid, c in o.get("cases", {}).items():
        s = c["sw"]
        r.need(s["rc"] == 0 and s["record_written"], f"{pid}: with switch exit {s['rc']}, written {s['record_written']}")
        ck = s.get("check") or {}
        r.need(ck.get("verdict") == "OK" and ck.get("levelAchieved") == "CL1", f"{pid}: check.py {ck}")
        got, want = hset(s.get("hand_times")), hset(c["expected"])
        r.need(got == want, f"{pid}: hand_times {sorted(got)} != expected {sorted(want)}")
        al = ((s.get("allowances") or {}).get("hand_times") or {})
        r.need(al.get("switch") == SWITCH, f"{pid}: allowance switch {al.get('switch')!r}")
        r.need(al.get("writer") == o.get("expect_writer"), f"{pid}: allowance writer {al.get('writer')!r}")
        r.need(within(al.get("at"), s["t0"], s["t1"]), f"{pid}: allowance at {al.get('at')} not the run's clock")
    ov = o.get("overlay_sw") or {}
    r.need(ov.get("rc") == 3 and not ov.get("record_written"), f"failures/hand-times with the switch: exit {ov.get('rc')}, written {ov.get('record_written')}")
    if v3 is not None:
        r.need(v3, "V3 failed (listing would be disclosure only)")
    if v8 is not None:
        r.need(v8, "V8 failed (listing would be disclosure only)")
    return r.out()


def j_T4(o):
    if (e := _err(o)): return False, e
    r = R()
    steps = o.get("steps") or []
    pre = [s for s in steps if s["name"] != "close"]
    bad = [f"{s['name']} rc {s['rc']}" for s in pre if s["rc"] != 0]
    r.need(not bad and any(s["name"] == "dispose" for s in pre), f"build steps failed or incomplete: {bad or [s['name'] for s in steps][-3:]}")
    r.need(o.get("packet_terminal") == "accepted", f"packet terminal_state {o.get('packet_terminal')!r}")
    em = o.get("emit") or {}
    r.need(em.get("rc") == 0 and em.get("record_written"), f"no-switch emit exit {em.get('rc')}; kinds {em.get('kinds')}; hand {em.get('hand')}")
    ck = o.get("check") or {}
    r.need(ck.get("verdict") == "OK" and ck.get("levelAchieved") == "CL1", f"check.py {ck}")
    r.need(o.get("hand_times") == [], f"hand_times {o.get('hand_times')!r} (want [])")
    return r.out()


def j_T5(o):
    if (e := _err(o)): return False, e
    r = R()
    r.need(o.get("tolerance") == 60, f"TOLERANCE_S = {o.get('tolerance')!r}")
    r.need(len(o.get("anchor_lines") or []) == 1, f"after-close refusal line count {len(o.get('anchor_lines') or [])}")
    r.need(len(o.get("cases") or []) >= o.get("min_cases", 1), f"{len(o.get('cases') or [])} base-refusal cases < {o.get('min_cases')}")
    for c in o.get("cases") or []:
        for side in ("nosw", "sw"):
            s = c[side]
            r.need(s["rc"] == 3, f"{c['case']} {side}: exit {s['rc']} (base 3)")
            miss = set(c["base"]["kinds"]) - set(s["kinds"]) - {"hand-time"}
            r.need(not miss, f"{c['case']} {side}: lost base kinds {sorted(miss)}")
    return r.out()


def j_T6(o):
    if (e := _err(o)): return False, e
    r = R()
    s = o.get("summary") or {}
    r.need(o.get("rc") == 0, f"prior procedure exit {o.get('rc')} (controls {s.get('controls')}, mutants {s.get('mutants')})")
    sc = s.get("scores") or {}
    r.need(sc and all(v == 1 for v in sc.values()), f"N verdicts {s.get('subject')}")
    runs = [x for x in o.get("runs") or [] if x.get("record_written")]
    r.need(len(runs) >= o.get("min_runs", 1), f"{len(runs)} records < {o.get('min_runs')}")
    for x in runs:
        miss = set(x["nosw_hand_fields"]) - set(x["record_hand_fields"])
        r.need(not miss, f"{x['run']}: flagged but not in hand_times: {sorted(miss)}")
        r.need(x.get("verify_rc") == 0, f"{x['run']}: verify exit {x.get('verify_rc')} {x.get('verify_kinds')}")
    return r.out()


def j_T7(o):
    if (e := _err(o)): return False, e
    r = R()
    for k in ("jr", "jr-sw"):
        r.need(not (o.get(k) or {}).get("changed"), f"{k}: emitter changed job files {(o.get(k) or {}).get('changed')}")
    r.need(o.get("t4_changed") == [], f"T4 job: emitter changed {o.get('t4_changed')}")
    jr = o.get("jr") or {}
    logh = [h for h in jr.get("hand", []) if "#" in h[0]]
    r.need(jr.get("rc") == 3 and "hand-time" in (jr.get("kinds") or []), f"job-rejected no switch: exit {jr.get('rc')} kinds {jr.get('kinds')}")
    r.need(len(logh) == o.get("log_hand_count"), f"{len(logh)} log hand times flagged (want {o.get('log_hand_count')})")
    r.need(all(h[3] in o.get("log_sources", []) for h in logh), f"log hand sources {sorted({h[3] for h in logh})}")
    sw = o.get("jr-sw") or {}
    r.need(sw.get("written") and hset(logh) <= hset(sw.get("hand_times")), "with the switch the log times are not all in hand_times")
    r.need(o.get("porcelain_after_suite") == "", f"git status after the suite: {o.get('porcelain_after_suite')!r}")
    return r.out()


# ---------------------------------------------------------------- F1
def _calls(o):
    return {c["tag"]: c for c in ((o.get("seq") or {}).get("calls") or [])}


def _refused(c):
    return c is not None and c["rc"] != 0 and c["refused_text"] and c["ledger_same"] and c["custody_same"]


def _ok1(c):
    return c is not None and c["rc"] == 0 and c["prefix_kept"] and c["appended"] is not None and len(c["appended"]) == 1


def _need_calls(r, o, tags):
    cs = _calls(o)
    seq = o.get("seq") or {}
    if seq.get("error"):
        r.need(False, "F1 sequence: " + str(seq["error"])[:300]); return cs
    for t in tags:
        c = cs.get(t)
        if c is None:
            r.need(False, f"{t}: not run"); continue
        if c["expect"] == "ok":
            r.need(_ok1(c), f"{t}: want one appended line, got rc {c['rc']} appended {None if c['appended'] is None else len(c['appended'])}: {(c['stderr'] or c['stdout'])[-200:]}")
        else:
            r.need(_refused(c), f"{t}: want refusal (rc!=0, REFUSED:, files unchanged), got rc {c['rc']} REFUSED {c['refused_text']} ledger_same {c['ledger_same']} custody_same {c['custody_same']}")
    return cs


def _one(c):
    return (c.get("appended") or [{}])[0] if c else {}


def j_F1a(o):
    if (e := _err(o)): return False, e
    r = R(); cs = _calls(o)
    r.need(cs, "no F1 calls")
    _need_calls(r, o, list(cs))
    for t, c in cs.items():
        if c["expect"] == "ok" and not t.startswith("b."):
            r.need(c["custody_same"], f"{t}: custody.json changed")
    for need in ("c.open1", "c.close1", "d.verdict", "e.ok", "f.ok", "g.ok", "b.ok"):
        r.need(need in cs, f"{need} missing")
    return r.out()


def j_F1b(o):
    if (e := _err(o)): return False, e
    r = R(); cs = _need_calls(r, o, ["b.early", "b.future", "b.ok"])
    ln = _one(cs.get("b.ok")); seq = o.get("seq") or {}
    r.need(ln.get("event") == "dispose" and ln.get("decided_at") and ln.get("at") and ln.get("decided_source"), f"dispose line {ln}")
    try:
        r.need(T(ln.get("decided_at")) == T(seq.get("last_check")), f"decided_at {ln.get('decided_at')} != {seq.get('last_check')}")
    except (ValueError, TypeError):
        r.need(False, "decided_at unparseable")
    ca = (cs.get("b.ok") or {}).get("custody_after") or {}
    disp = ca.get("disposition") or {}
    r.need(disp.get("at") and ln.get("decided_at") and T(disp["at"]) == T(ln["decided_at"]), f"custody.json disposition.at {disp.get('at')}")
    r.need(disp.get("by") == "F1 Buyer", f"custody.json disposition.by {disp.get('by')!r}")
    t4 = (o.get("t4_dispose") or [{}])[-1] if o.get("t4_dispose") else {}
    rd = o.get("t4_record_disposition") or {}
    r.need(t4.get("decided_at") and rd.get("at") and T(rd["at"]) == T(t4["decided_at"]),
           f"T4 record disposition.at {rd.get('at')} vs ledger decided_at {t4.get('decided_at')}")
    return r.out()


def j_F1c(o):
    if (e := _err(o)): return False, e
    r = R(); cs = _need_calls(r, o, ["c.open1", "c.open-again", "c.close-wrong-n", "c.close-wrong-seat", "c.close1",
                                     "c.close1-again", "c.open2", "c.close2"])
    sh = (o.get("seq") or {}).get("shas") or {}
    a, b = _one(cs.get("c.open1")), _one(cs.get("c.open2"))
    r.need(a.get("action") == "open" and a.get("n") == 1 and a.get("seat") == "maker", f"open1 line {a}")
    r.need(b.get("n") == 2, f"open2 n {b.get('n')}")
    r.need(a.get("prompt_sha256") == sh.get("prompt-1") and b.get("prompt_sha256") == sh.get("prompt-2"), "prompt_sha256 wrong")
    c = _one(cs.get("c.close1"))
    r.need(c.get("action") == "close" and c.get("n") == 1 and c.get("outcome") == "F1 outcome" and c.get("fix_kind") == "code", f"close1 line {c}")
    return r.out()


def j_F1d(o):
    if (e := _err(o)): return False, e
    r = R(); cs = _need_calls(r, o, ["d.verdict-missing", "d.verdict", "d.summary-nostamp", "d.summary"])
    sh = (o.get("seq") or {}).get("shas") or {}; st = (o.get("seq") or {}).get("summary_stamp") or {}
    v = _one(cs.get("d.verdict"))
    r.need(v.get("event") == "evaluation" and v.get("verdict_sha256") == sh.get("verdict"), f"verdict line {v}")
    s = _one(cs.get("d.summary"))
    r.need(s.get("summary_sha256"), "no summary_sha256")
    for k, kk in (("started_at", "started_at"), ("finished_at", "finished_at"), ("summary_writer", "writer")):
        r.need(s.get(k) == st.get(kk), f"summary {k} {s.get(k)!r} != stamp {st.get(kk)!r}")
    return r.out()


def j_F1e(o):
    if (e := _err(o)): return False, e
    r = R(); cs = _need_calls(r, o, ["e.in-custody", "e.early", "e.future", "e.ok"])
    seq = o.get("seq") or {}; ln = _one(cs.get("e.ok"))
    r.need(ln.get("quote") == seq.get("amend_quote"), "quote not verbatim")
    r.need(ln.get("file_sha256") == (seq.get("shas") or {}).get("amend"), "file_sha256 wrong")
    r.need(ln.get("said_at") and T(ln["said_at"]) == T(seq["freeze_at"]), f"said_at {ln.get('said_at')}")
    return r.out()


def j_F1f(o):
    if (e := _err(o)): return False, e
    r = R(); cs = _need_calls(r, o, ["f.early", "f.future", "f.ok"])
    seq = o.get("seq") or {}; ln = _one(cs.get("f.ok"))
    r.need(ln.get("event") == "relay" and ln.get("kind") == "relay", f"relay line {ln}")
    r.need(ln.get("quote") == seq.get("relay_quote"), "quote not verbatim")
    p = o.get("p_f1f") or {}
    r.need(p.get("rc") == 3 and not p.get("written") and "approval" in (p.get("kinds") or []), f"P-F1f emit {p}")
    return r.out()


def j_F1g(o):
    if (e := _err(o)): return False, e
    r = R(); cs = _need_calls(r, o, ["g.early", "g.nostamp", "g.ok"])
    seq = o.get("seq") or {}; ln = _one(cs.get("g.ok")); rd = seq.get("reading") or {}; sh = seq.get("shas") or {}
    r.need(ln.get("spend_ledger_sha256") == sh.get("ledger") and ln.get("key_reading_sha256") == sh.get("reading"), "spend shas wrong")
    try:
        r.need(abs(float(ln["total_usd"]) - max(float(ln["ledger_sum_usd"]), float(ln["key_delta_usd"]))) < 1e-9, "total_usd != max")
    except (KeyError, TypeError, ValueError):
        r.need(False, f"spend line fields {sorted(ln)}")
    r.need(ln.get("read_at") == rd.get("read_at"), "read_at not copied from the reading")
    return r.out()


def j_F1h(o):
    if (e := _err(o)): return False, e
    r = R(); x = o.get("record_xp") or {}; led = o.get("ledger") or []
    r.need(o.get("emit_rc") == 0, f"T4 emit exit {o.get('emit_rc')}")
    want = {"generations": "generation", "evaluations": "evaluation", "relays": "relay", "amendments": "amendment"}
    for key, ev in want.items():
        rows = [(i, l) for i, l in enumerate(led, 1) if l.get("event") == ev]
        got = x.get(key) or []
        r.need(len(got) == len(rows) and rows, f"{key}: {len(got)} entries for {len(rows)} ledger lines")
        for (i, l), g in zip(rows, got):
            r.need(g.get("source") == f"inputs/custody-events.jsonl:{i}", f"{key} source {g.get('source')!r} (line {i})")
            bad = [k for k, v in l.items() if k != "event" and g.get(k) != v]
            r.need(not bad, f"{key} line {i}: fields differ {bad}")
    sp = x.get("spend") or {}
    r.need(all(k in sp for k in ("calls_sum_usd", "key_delta_usd", "total_usd", "tolerance_usd")) and sp.get("tolerance_usd") == 0.0001, f"spend {sp}")
    ck = o.get("check") or {}
    r.need(ck.get("verdict") == "OK", f"check.py {ck}")
    return r.out()


# ---------------------------------------------------------------- I1 / F7a / F8 / P1
def _stamp_ok(r, name, s, t0, t1, writer):
    if not isinstance(s, dict):
        r.need(False, f"{name}: no summary"); return
    r.need(s.get("writer") == writer, f"{name}: writer {s.get('writer')!r} != {writer!r}")
    r.need(within(s.get("started_at"), t0, t1) and within(s.get("finished_at"), t0, t1), f"{name}: stamp outside the run")
    try:
        r.need(T(s["started_at"]) <= T(s["finished_at"]), f"{name}: started after finished")
    except (KeyError, ValueError, TypeError):
        r.need(False, f"{name}: bad stamp")


def j_I1(o):
    if (e := _err(o)): return False, e
    r = R()
    r.need(all((o.get("exists") or {}).values()) and o.get("exists"), f"tools present {o.get('exists')}")
    for k in ("fixture_run", "judge_batch"):
        x = o.get(k)
        if not x:
            r.need(False, f"{k} not run"); continue
        r.need(x["rc"] == 0, f"{k} exit {x['rc']}: {x['stderr'][-200:]}")
        _stamp_ok(r, k, x.get("out"), x["t0"], x["t1"], x["expect_writer"])
    jb = (o.get("judge_batch") or {})
    s = jb.get("out") or {}
    r.need(s.get("order") == [i["id"] for i in jb.get("expect_order", [])], f"order {s.get('order')}")
    r.need(len(s.get("results") or []) == len(jb.get("expect_order", [])), "results count")
    return r.out()


def j_F7a(o):
    if (e := _err(o)): return False, e
    r = R()
    rw, ro = o.get("rw") or {}, o.get("ro") or {}
    for k, x in (("rw", rw), ("ro", ro)):
        r.need(x.get("rc") == 0, f"{k} exit {x.get('rc')}: {(x.get('stderr') or '')[-200:]}")
        r.need(not x.get("src_changed"), f"{k}: src changed {x.get('src_changed')}")
        r.need(not x.get("unwritable_in_work"), f"{k}: not owner-writable in work {x.get('unwritable_in_work')[:5] if x.get('unwritable_in_work') else ''}")
    strip = lambda s: {k: v for k, v in (s or {}).items() if k not in ("started_at", "finished_at")}
    r.need(rw.get("out") and strip(rw.get("out")) == strip(ro.get("out")), "summaries differ beyond the stamps")
    return r.out()


def _noentry(x):
    return not x.get("posts") and not x.get("log")


def j_F8a(o):
    if (e := _err(o)): return False, e
    r = R(); a = o.get("a") or {}
    r.need(o.get("a_init") == 0, f"--init-spend exit {o.get('a_init')}")
    r.need(a.get("rc") == 6 and _noentry(a), f"at-bound call: exit {a.get('rc')}, posts {len(a.get('posts') or [])}, log {len(a.get('log') or [])}")
    return r.out()


def j_F8b(o):
    if (e := _err(o)): return False, e
    r = R(); b1, b2 = o.get("b1") or {}, o.get("b2") or {}
    r.need(b1.get("rc") == 8 and _noentry(b1), f"--max-cost below worst case: exit {b1.get('rc')}, posts {len(b1.get('posts') or [])}, log {len(b1.get('log') or [])}")
    st = [x for x in b2.get("spend_rows") or [] if x.get("event") == "settle"]
    r.need(b2.get("rc") == 9 and len(b2.get("log") or []) == 1 and not b2.get("reply_exists") and st and st[-1].get("over_cap") is True,
           f"over cap: exit {b2.get('rc')}, log {len(b2.get('log') or [])}, reply {b2.get('reply_exists')}, settle {st[-1:] }")
    return r.out()


def j_F8c(o):
    if (e := _err(o)): return False, e
    r = R(); c1, c2, c3 = o.get("c1") or {}, o.get("c2") or {}, o.get("c3") or {}
    r.need(c1.get("rc") == 6 and not c1.get("posts"), f"key delta alone: exit {c1.get('rc')}")
    r.need(c2.get("rc1") == 0 and c2.get("rc2") == 6, f"ledger alone: exits {c2.get('rc1')}, {c2.get('rc2')}")
    req = c2.get("requests") or []
    ok = True
    for i, q in enumerate(req):
        if q["method"] == "POST" and "/chat/completions" in q["url"]:
            prev = [x for x in req[:i] if x["method"] == "GET" and x["url"].endswith("/key")]
            posts_before = [x for x in req[:i] if x["method"] == "POST" and "/chat/completions" in x["url"]]
            ok = ok and len(prev) > len(posts_before)
    r.need(ok and any(q["method"] == "POST" for q in req), "a chat POST without a fresh GET /api/v1/key before it")
    r.need(sum(1 for q in req if q["method"] == "POST" and "/chat/completions" in q["url"]) == 1, "second call was sent")
    r.need(c3.get("rc") == 2 and not c3.get("requests"), f"missing spend file: exit {c3.get('rc')}, requests {len(c3.get('requests') or [])}")
    r.need(not o.get("c_literal"), f"literal job id in {o.get('c_literal')}")
    rows = o.get("c_rows") or []; jid = o.get("c_jobid")
    r.need(any(x.get("job") == jid or x.get("job_id") == jid for x in rows + (o.get("c_baseline") or [])), "job id not taken from the spend file")
    r.need(o.get("c_max_tokens") and all(m == 131072 for m in o["c_max_tokens"]), f"request max_tokens {o.get('c_max_tokens')}")
    return r.out()


def j_F8d(o):
    if (e := _err(o)): return False, e
    r = R(); i, ii = o.get("i") or {}, o.get("ii") or {}; tol = o.get("delta_tol", 0.002)
    r.need(o.get("init_rc") == 0, f"--init-spend on the real key exit {o.get('init_rc')}")
    r.need(i.get("rc") == 8 and not i.get("log") and not i.get("reply_exists"), f"(i) exit {i.get('rc')}, log {len(i.get('log') or [])}")
    r.need(i.get("reading_rc") == 0 and i.get("key_delta") is not None and abs(float(i["key_delta"])) <= tol,
           f"(i) subject key delta {i.get('key_delta')}")
    r.need(i.get("inst_delta") is not None and abs(float(i["inst_delta"])) <= tol, f"(i) instrument key delta {i.get('inst_delta')}")
    r.need(ii.get("rc") == 0 and len(ii.get("log") or []) == 1 and ii.get("reply_exists"), f"(ii) exit {ii.get('rc')}, log {len(ii.get('log') or [])}")
    st = [x for x in ii.get("spend_rows") or [] if x.get("event") == "settle"]
    r.need(len(st) == 1 and float(st[-1].get("cost_usd", 1e9)) <= float(ii.get("cap", 0)), f"(ii) settle rows {st}")
    r.need(ii.get("reading_rc") == 0 and ii.get("reading_after_3min"), f"(ii) reading rc {ii.get('reading_rc')}, >=3 min {ii.get('reading_after_3min')}")
    r.need(ii.get("inst_delta_total") is not None and float(ii["inst_delta_total"]) <= float(o.get("bound_usd", 0.07)),
           f"(ii) instrument key delta {ii.get('inst_delta_total')} > bound")
    return r.out()


def j_P1(o):
    if (e := _err(o)): return False, e
    r = R()
    r.need(all((o.get("files") or {}).values()), f"tools {o.get('files')}")
    r.need(o.get("tests"), "no tests/test_edi_*.py")
    miss = set(o.get("job1_keys") or []) - set(o.get("entry_keys") or [])
    r.need(o.get("entry_keys") and not miss, f"log entry lacks job 1 keys {sorted(miss)}")
    rl = o.get("read_log") or {}
    r.need(rl.get("rc") == 0, f"custody_history.read_log: {rl}")
    return r.out()


def j_X1(o):
    if (e := _err(o)): return False, e
    r = R(); c, x, p = o.get("clean") or {}, o.get("x1") or {}, o.get("px1") or {}
    r.need(c.get("rc") == 0 and c.get("written"), f"clean emit {c.get('rc')}")
    r.need(x.get("rc") == 0 and x.get("written") and (x.get("check") or {}).get("verdict") == "OK", f"X1 emit {x.get('rc')} check {x.get('check')}")
    r.need(x.get("inputs") == x.get("inputs_expected") and x.get("inputs") is not None, "inputs is not a deep copy")
    refused = p.get("rc") not in (0, None) and not p.get("written")
    same = p.get("rc") == 0 and p.get("owned") == c.get("owned")
    r.need(refused or same, f"P-X1: exit {p.get('rc')}; owned keys {'equal' if p.get('owned') == c.get('owned') else 'differ'}")
    return r.out()


# ---------------------------------------------------------------- V
def _plant(r, o, pid):
    p = (o.get("plants") or {}).get(pid)
    if not p:
        r.need(False, f"{pid} not run"); return
    k = p.get("kinds") or []
    e = p.get("expect")
    # standard first: a standard failure is the only kind; an exit-2 plant names no kind; others must name theirs
    kok = (k == ["standard"]) if e == "standard" else (k == []) if not e else (e in k)
    r.need(p.get("rc") == p.get("expect_rc", 4) and kok and not p.get("traceback"),
           f"{pid}: exit {p.get('rc')} kinds {k} (want exit {p.get('expect_rc', 4)}, kind {e})")


def _clean(r, o, keys=("clean", "t4", "jr-sw", "x1")):
    for k in keys:
        c = (o.get("clean") or {}).get(k) or {}
        r.need(c.get("rc") == 0, f"clean {k}: exit {c.get('rc')} {c.get('kinds')} {c.get('error') or ''}")


def j_V(o, ids, extra=None):
    if (e := _err(o)): return False, e
    r = R(); _clean(r, o)
    for pid in ids:
        _plant(r, o, pid)
    if extra:
        extra(r, o)
    return r.out()


def _v1(r, o):
    js = ((o.get("clean") or {}).get("t4") or {}).get("json") or {}
    r.need(js.get("exit") == 0 and js.get("failures") == [], f"--json {js}")


def _v2(r, o):
    lg = o.get("legacy") or {}
    r.need(lg.get("rc") == 4 and "schema" in (lg.get("kinds") or []) and not lg.get("traceback"), f"legacy: exit {lg.get('rc')} kinds {lg.get('kinds')} tb {lg.get('traceback')}")
    s = o.get("schema") or {}
    r.need(str(s.get("$schema", "")).startswith("https://json-schema.org/draft/2020-12")
           and s.get("$id") == "plumbline/schemas/x-plumbline/x-plumbline-v1.schema.json" and s.get("additionalProperties") is False,
           f"schema file: $schema {s.get('$schema')!r}, $id {s.get('$id')!r}, additionalProperties {s.get('additionalProperties')!r}")
    r.need(all(v == "plumbline/x-plumbline/v1" for v in (o.get("schema_ref_in_records") or {}).values() if v is not None)
           and any(o.get("schema_ref_in_records", {}).values()), f"records' schema key {o.get('schema_ref_in_records')}")


def j_V5(o, v):
    if (e := _err(o)) or (e := _err(v)): return False, e
    r = R(); _clean(r, v)
    for pid in ("P-V5a", "P-V5b"):
        _plant(r, v, pid)
    sp = o.get("spend") or {}; tol = o.get("tol", 0.0001)
    try:
        r.need(abs(float(sp["calls_sum_usd"]) - sum(o.get("log_costs") or [])) <= tol, "calls_sum_usd != sum of log costs")
        r.need(abs(float(sp["total_usd"]) - max(float(sp["calls_sum_usd"]), float(sp["key_delta_usd"]))) <= tol, "total != max")
    except (KeyError, TypeError, ValueError):
        r.need(False, f"spend block {sp}")
    return r.out()


def j_V7(o):
    if (e := _err(o)): return False, e
    r = R()
    r.need(o["rw"]["rc"] == 0 and not o.get("changed"), f"rw run exit {o['rw']['rc']}, changed {o.get('changed')}")
    r.need(o["ro"]["rc"] == o["rw"]["rc"] and o["ro"]["failures"] == o["rw"]["failures"], f"read-only copy: exit {o['ro']['rc']}")
    r.need(not o.get("emit_imports"), f"imports the emitter: {o.get('emit_imports')}")
    return r.out()


def j_V8(o, clean):
    if (e := _err(o)) or (e := _err(clean)): return False, e
    r = R(); p = o.get("planted") or {}; c = clean.get("clean") or {}
    r.need(p.get("close_rc") == 4, f"P-V8 close exit {p.get('close_rc')} ({p.get('build_error')})")
    r.need("NOT CLOSED: Plumbline verify failed (allowance)" in (p.get("close_out") or ""), "no NOT CLOSED line naming allowance")
    rows = p.get("rows") or []
    r.need(any(x.get("event") == "close_refused" and x.get("kind") == "allowance" for x in rows), f"run-log rows {rows}")
    r.need(not any(x.get("event") == "closed" for x in rows), "a closed row was written")
    r.need((p.get("reemit") or {}).get("rc") == 4, f"custody re-emit exit {(p.get('reemit') or {}).get('rc')}")
    crow = c.get("rows") or []
    r.need(c.get("close_rc") == 0 and any(x.get("event") == "closed" for x in crow) and not any(x.get("event") == "close_refused" for x in crow),
           f"clean T4 close exit {c.get('close_rc')} rows {crow}")
    return r.out()


def j_V9(o, kinds):
    if (e := _err(o)): return False, e
    r = R()
    r.need(o.get("tests"), "no tests/test_plumbline_verify*.py")
    miss = set(kinds) - set(o.get("test_kinds") or [])
    r.need(not miss, f"kinds never named in the verifier tests: {sorted(miss)}")
    r.need(o.get("new_fixture_dirs"), "no new fixture folders")
    d = " ".join((o.get("doc_text") or {}).values())
    for t in ("plumbline_verify", "0.0001", "--allow-hand-times"):
        r.need(t in d, f"docs lack {t!r}")
    return r.out()


def j_G1(o, allow):
    import fnmatch
    if (e := _err(o)): return False, e
    r = R()
    for ln in o.get("name_status") or []:
        st, *paths = ln.split("\t")
        for pth in paths:
            rule = allow["edit"] if st[0] == "M" else allow["new"] if st[0] == "A" else []
            if allow.get("job_dir") and pth.startswith(allow["job_dir"]):
                ok = st[0] in "AM"            # the Orchestrator's freeze set and records; Maker commits checked below
            elif pth.startswith("tests/fixtures/custody/") and st[0] == "A":
                ok = len(pth.split("/")) > 4 and not any(pth.startswith(f"tests/fixtures/custody/{b}/") for b in allow["base_fixture_dirs"])
            else:
                ok = any(fnmatch.fnmatch(pth, g) for g in rule)
            r.need(ok, f"{st} {pth} outside the allow-list")
    r.need(o.get("protected") == o.get("protected_base"), "a protected file changed")
    own = allow.get("job_dir")
    bad = [x for x in o.get("maker_paths") or [] if own and x.startswith(own)]
    r.need(not bad, f"Maker commits touch the job's own folder: {bad[:5]}")
    return r.out()


def j_G2(o, parts):
    if (e := _err(o)): return False, e
    r = R(); b, s = o.get("base") or {}, o.get("subject") or {}
    for n, x in b.items():
        r.need(n in s and s[n]["rc"] == x["rc"] == 0, f"{n}: subject exit {s.get(n, {}).get('rc')} vs base {x['rc']} (both must be 0)")
    for n in o.get("new_test_files") or []:
        r.need(s[n]["rc"] == 0, f"new test {n} exit {s[n]['rc']}")
    txt = o.get("new_test_text") or {}
    for part, words in parts.items():
        r.need(any(any(w in t for w in words) for t in txt.values()), f"no new test file covers part {part}")
    return r.out()


def j_G3(o, terms):
    if (e := _err(o)): return False, e
    r = R(); d = o.get("doc_text") or {}
    for f, ts in terms.items():
        for t in ts:
            r.need(t in d.get(f, ""), f"{f} lacks {t!r}")
    return r.out()


# ---------------------------------------------------------------- item 30: the field guide (G4-G7)
FG = json.loads((Path(__file__).resolve().parent / "fg_rules.json").read_text(encoding="utf-8"))


def fg_norm(t):
    t = t.lower()
    for a, b in (("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'), ("\u2013", "-"), ("\u2014", "-")):
        t = t.replace(a, b)
    t = re.sub(r"[*_`\\]", "", t)
    return re.sub(r"\s+", " ", t)


def fg_letters(t):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", fg_norm(t))).strip()


def j_G4(o, allow):
    if (e := _err(o)): return False, e
    r = R(); p = FG["path"]
    r.need(o.get("exists"), f"{p} missing at the subject")
    r.need(f"A\t{p}" in (o.get("name_status") or []), f"{p} is not a new file in the diff (A)")
    r.need((o.get("size") or 0) > 0 and o.get("utf8", False), f"{p} empty or not UTF-8")
    ok, why = j_G1(o, allow)
    r.need(ok, "diff touches paths outside the allow-list: " + "; ".join(why[:4]))
    return r.out()


def j_G5(o):
    if (e := _err(o)): return False, e
    r = R(); s = FG["status"]
    head = (o.get("text") or "").splitlines()[: s["within_first_lines"]]
    hit = [ln for ln in head if all(w in fg_norm(ln) for w in s["line_must_contain_all"])]
    r.need(bool(hit), f"no status line in the first {s['within_first_lines']} lines containing {s['line_must_contain_all']}")
    return r.out()


def j_G6(o):
    if (e := _err(o)): return False, e
    r = R(); t = fg_norm(o.get("text") or "")
    for g, conj in FG["groups"].items():
        miss = [alts for alts in conj if not any(fg_norm(a) in t for a in alts)]
        r.need(not miss, f"{g}: lacks {' / '.join(miss[0])!r}" if miss else "")
    r.need(any(re.match(FG["carried_forward_heading"], fg_norm(ln)) for ln in (o.get("text") or "").splitlines()),
           "no 'carried forward' heading")
    return r.out()


def j_G7(o):
    if (e := _err(o)): return False, e
    r = R(); raw = o.get("text") or ""; t = fg_norm(raw); tl = " " + fg_letters(raw) + " "
    r.need(o.get("exists"), f"{FG['path']} missing at the subject (nothing to scan)")
    for rx in FG["deny_regex"]:
        m = re.search(rx, raw, flags=re.I)
        if m:
            r.need(False, f"leak: deny pattern {rx!r} matched {m.group(0)[:40]!r} at line {raw[:m.start()].count(chr(10)) + 1}")
        elif (m2 := re.search(rx, t, flags=re.I)):
            r.need(False, f"leak: deny pattern {rx!r} matched {m2.group(0)[:40]!r} after normalization")
    for ph in FG["deny_phrases"]:
        n = fg_letters(ph)
        r.need(" " + n + " " not in tl, f"leak: denied verbatim phrase {ph[:50]!r}")
    return r.out()
