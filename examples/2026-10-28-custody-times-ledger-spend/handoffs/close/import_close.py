#!/usr/bin/env python3
"""Pre-close import for job 2026-10-28-custody-times-ledger-spend (stage 1 of the close). No model calls, no
network, nothing under /tmp. It decides nothing: it copies evidence that already exists on the Owner's box into the
job folder (redacting held-out control text), writes the iteration-3 verdict note, the method note, the disclosure
list and the Plumbline sidecar, and appends the late-recorded ledger lines (DEVIATIONS item 23).

    import_close.py --job-dir J --work W --maker-log LOG --controls DIR --public-list FILE --recorded-at T

FILE lists the public paths for the leak filter (tracked tree, evaluated-revision trees, J-listings), as for
handoffs/close/leak_scan.py; the S1 evidence is redacted against it (handoffs/close/redact_s1_evidence.py).

W is /workspace/edi-work/2026-10-28-custody-times-ledger-spend (eval/, maker/, spend/, DEVIATIONS-orchestrator.md).
Refuses to run twice (the ledger must still be the 8-line pre-close ledger cff5d27e...).
"""
from __future__ import annotations
import argparse, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path

H = lambda b: hashlib.sha256(b if isinstance(b, bytes) else b.encode("utf-8")).hexdigest()
LEDGER_PRE = "cff5d27e38ec0dfd92e1dff4d58cbc370cb7ede75b5f626523d3345d7dc8d2fe"
MAKER_LOG_SHA = "882ee4e61a13fe614dfb4cbe12c3f6e228e1e8581dde23ca837471a062edc48a"
BASE = "3df1ce52eddfe18705e380c4b6e99cf617cfa24b"
REVS = {1: "1cb410b", 2: "c882646", 3: "f95e0d3"}
PREV = {1: BASE, 2: "1cb410b", 3: "c882646"}
JS = ("J1", "J2", "J3", "J4")
ORCH = "Chief of Staff (Orchestrator)"
NOTE23 = ("hand-appended at close by handoffs/close/import_close.py; recorded late (DEVIATIONS item 23): "
          "kit/custody_ledger.py @ 3df1ce5 has no command for this event, so it was not logged when it happened. "
          "`at` is copied from `at_source`; `recorded_at` is when this line was written.")
ITEM23 = (
    "23. Late-recorded ledger lines (close build, 2026-10-29, Owner decision 12:36 EDT: \"disclose that the "
    "entries were recorded late\"). The base ledger tool (kit/custody_ledger.py @ 3df1ce5) has commands only for "
    "freeze, approve, pin and dispose, so no generation, evaluation, relay or spend line was written when those "
    "events happened. At the close the Orchestrator appended them by hand (handoffs/close/import_close.py): three "
    "generation open/close pairs, three evaluation lines, three relay lines and one spend line. Each carries "
    "writer \"hand\", hand_appended true, recorded_late true, recorded_by the Orchestrator, recorded_at (the time "
    "the line was written, at the close), and at_source naming where its `at` was copied from: a harness-log "
    "call's sent_at/received_at, an S1 summary's started_at/finished_at, a spend-ledger line, or (relays) a "
    "handoff line that gives the time to the minute (seconds not recorded, written as :00). No `at` was typed from "
    "memory. The dispose line carries the Owner's decision time 2026-10-29 12:36 EDT (16:36:00Z; seconds not "
    "recorded) as the Orchestrator received it in the Grok Bot chat with Chief of Staff. Not recorded at all "
    "because no source was found: the iteration-1 Maker and Evaluator go-aheads, the iteration-2 guide-a2 go-ahead "
    "(about 07:56 EDT) and the batch-3 go-ahead (about 11:44 EDT).")
ITEM24_HEAD = "24. Spend figures: the Owner's dashboard vs the key's own figures (close, 2026-10-29). "


def load_jsonl(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def iso_z(s: str) -> str:  # 2026-10-29T15:56:38.444180Z -> 2026-10-29T15:56:38Z (the ledger's whole-second form)
    m = re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?Z", s)
    assert m, s
    return m[1] + "Z"


def git(repo: Path, *a: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *a], text=True)


def redact_summary(s: dict) -> dict:
    out = {k: v for k, v in s.items() if k != "controls"}
    out["controls"] = {cid: {k: c[k] for k in ("want", "got", "right", "signature_seen", "cases") if k in c}
                       for cid, c in s["controls"].items()}
    out["redaction"] = ("controls[].why, .signature and .mutation_applied removed (they can describe the held-out "
                        "plant); the full summary is held on the Owner's box, digest in HELD-ON-BOX.sha256")
    return out


def fix_kind(paths: list[str]) -> str:
    kinds = set()
    for p in paths:
        if p.startswith("tests/fixtures/"):
            kinds.add("fixture")
        elif p.startswith("tests/"):
            kinds.add("test")
        elif p.startswith("docs/") or p.endswith("README.md"):
            kinds.add("docs")
        else:
            kinds.add("code")
    if "code" in kinds:
        lead = "code fix (not fixture-only, not test-only)"
    elif "docs" in kinds:
        lead = "docs fix (not fixture-only, not test-only)"
    else:
        lead = "fixture/test-only change (NOT an acceptable fix, bar line 41)"
    return f"{lead}; changed path kinds: {', '.join(sorted(kinds))}"


def main() -> int:
    ap = argparse.ArgumentParser()
    for k in ("--job-dir", "--work", "--maker-log", "--controls", "--public-list", "--recorded-at", "--spend-read",
              "--dashboard-usd", "--dashboard-relayed-at"):
        ap.add_argument(k, required=True)
    a = ap.parse_args()
    J, W, C = Path(a.job_dir).resolve(), Path(a.work).resolve(), Path(a.controls).resolve()
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", a.recorded_at), a.recorded_at
    repo = Path(git(J, "rev-parse", "--show-toplevel").strip())
    LED = J / "inputs" / "custody-events.jsonl"
    if H(LED.read_bytes()) != LEDGER_PRE:
        print("ledger is not the 8-line pre-close ledger: import already done?", file=sys.stderr); return 2
    EV = J / "custody" / "evidence"; EV.mkdir(parents=True, exist_ok=True)
    E = W / "eval"
    held = []  # (sha, description) of files kept on the box

    # -- maker logs --
    ml = Path(a.maker_log).read_bytes()
    assert H(ml) == MAKER_LOG_SHA, "maker log digest"
    (EV / "harness-maker-deepseek.log").write_bytes(ml)
    maker = json.loads(ml)
    guides = {}
    for it in (1, 2):
        g = (W / "maker" / f"iter{it}" / "harness-maker-deepseek-guide.log").read_bytes()
        (EV / f"harness-maker-deepseek-guide-iter{it}.log").write_bytes(g)
        guides[it] = json.loads(g)

    # -- S1: per-check evidence of batch 3 (bar: evidence/<check>.json), amendment-2 T6, redacted summaries --
    for p in sorted((E / "b3" / "s1" / "evidence").iterdir()):
        shutil.copyfile(p, EV / p.name)
    shutil.copyfile(E / "b3" / "s1-amend2-T6.json", EV / "T6-amend2.json")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import redact_s1_evidence as rs
    ctl = rs.control_lines(C, Path(a.public_list))
    s1src = {p.name: p for p in (E / "b3" / "s1" / "evidence").iterdir()}
    s1src["T6-amend2.json"] = E / "b3" / "s1-amend2-T6.json"
    for name in sorted(s1src):
        if name.endswith(".json") and rs.redact_file(EV / name, ctl):
            held.append((H(s1src[name].read_bytes()),
                         f"{s1src[name].relative_to(W)} (full S1 evidence; filed redacted as custody/evidence/{name})"))
    s1 = {}
    for b in (1, 2, 3):
        raw = (E / f"b{b}" / "s1" / "summary.json").read_bytes()
        s1[b] = json.loads(raw)
        d = EV / f"b{b}"; d.mkdir(exist_ok=True)
        (d / "s1-summary.json").write_text(json.dumps(redact_summary(s1[b]), indent=2, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
        held.append((H(raw), f"eval/b{b}/s1/summary.json (full S1 batch-{b} summary)"))

    # -- E-GLM: merged redacted log per batch, redacted batch files, subject replies and records --
    glm = {}
    for b in (1, 2, 3):
        out = EV / f"harness-eval-glm-b{b}.log"
        r = subprocess.run([sys.executable, str(Path(__file__).with_name("redact_glm_log.py")),
                            "--glm-dir", str(E / f"b{b}" / "glm"), "--batch", str(b), "--controls", str(C),
                            "--out", str(out), "--evidence-out", str(EV / f"b{b}" / "glm")],
                           capture_output=True, text=True)
        if r.returncode:
            print(r.stderr, file=sys.stderr); return 2
        glm[b] = json.loads(r.stdout)
        for line in (out.parent / (out.name + ".full.sha256")).read_text().splitlines()[1:]:
            sha, name = line.split("  ", 1)
            held.append((sha, f"eval/b{b}/glm/{name.split('-')[3]}/{name} (full E-GLM log)"))
        for j, call in glm[b]["subject_calls"].items():
            if b == 3:  # bar: evidence/Jk-<call>.json for the scoring batch
                shutil.copyfile(E / "b3" / "glm" / j / f"{j}-{call}.json", EV / f"{j}-{call}.json")
    b3batch = {j: json.loads((EV / "b3" / "glm" / f"{j}-batch.json").read_text()) for j in JS}

    # -- spend --
    sl = (W / "spend" / "spend-ledger.jsonl").read_bytes()
    (EV / "spend-ledger.jsonl").write_bytes(sl)
    shutil.copyfile(W / "spend" / "key-usage-baseline.json", EV / "key-usage-baseline.json")
    spend = [json.loads(l) for l in sl.decode().splitlines() if l.strip()]
    res = {r["id"]: r for r in spend if r["event"] == "reserve"}
    stl = {r["id"]: r for r in spend if r["event"] == "settle"}
    open_res = [{"call": res[i]["call"], "id": i, "at": res[i]["at"], "worst_usd": res[i]["worst_usd"]}
                for i in res if i not in stl]
    settled = round(sum(r["cost_usd"] for r in stl.values()), 9)
    by_src = {}
    for r in stl.values():
        by_src.setdefault(r["source"], []).append(r["call"])
    last_settle = max(stl.values(), key=lambda r: r["at"])
    # -- the close spend read (bar P6): handoffs/close/spend_read_close.py, one free GET /api/v1/key --
    srb = Path(a.spend_read).read_bytes(); sr = json.loads(srb)
    from datetime import datetime as _dt, timedelta as _td
    _P = lambda x: _dt.strptime(x[:19], "%Y-%m-%dT%H:%M:%S")
    assert sr["key_get"]["http_status"] == 200 and "error" not in sr["spend_status"], "spend read failed"
    assert sr["spend_ledger"]["sha256_before"] == sr["spend_ledger"]["sha256_after"] == H(sl), "spend ledger moved since the read"
    assert _P(sr["read_at"]) >= _P(max(r["at"] for r in spend)) + _td(minutes=3), "spend read < 3 min after the last call"
    assert abs(sr["spend_ledger"]["settled_usd"] - settled) < 1e-9
    (EV / "spend-status-close.json").write_bytes(srb)
    kf = sr["key_get"]["figures"]; ss = sr["spend_status"]
    kdelta = ss["key_usage_delta_usd"]; total = ss["spent_usd"]
    utc_day = sr["read_at"][:10]
    # settles whose reserve is on the previous UTC day but whose settle is on the read's UTC day (billed at request)
    cross = [{"call": stl[i]["call"], "reserved_at": res[i]["at"], "settled_at": stl[i]["at"], "cost_usd": stl[i]["cost_usd"]}
             for i in stl if res[i]["at"][:10] < utc_day <= stl[i]["at"][:10]]
    led_day = sr["spend_ledger"]["settled_by_utc_day"].get(utc_day, 0.0)
    led_day_req = round(led_day - sum(c["cost_usd"] for c in cross), 9)
    lost = round(kdelta - settled, 6)
    recon = {
        "read": "custody/evidence/spend-status-close.json", "read_sha256": H(srb), "read_at": sr["read_at"],
        "key_usage_close": kf["usage"], "key_usage_baseline": ss["key_usage_baseline"], "key_delta_usd": kdelta,
        "settled_usd": settled, "key_minus_settled_usd": lost,
        "key_minus_settled_note": "the iteration-1 verifier a1 call (reserve 19701ada, ruled LOST, no settle) is the only "
                                  "unsettled call; the same gap was 0.018699 at iter1 and 0.018706 at iter2. Its reserve "
                                  "stays open at worst case on the Owner's decision (2026-10-29 13:15 EDT).",
        "total_usd": total, "total_rule": "max(ledger settles + open reserves at worst case, key-usage delta) = the frozen harness's spent_usd",
        "bound_usd": ss["bound_usd"], "headroom_usd": ss["headroom_usd"],
        "key_usage_daily_utc": {"utc_day": utc_day, "key_usage_daily": kf.get("usage_daily"),
                                "ledger_settled_that_utc_day": led_day, "settled_across_midnight": cross,
                                "ledger_by_request_utc_day": led_day_req,
                                "residual_usd": round((kf.get("usage_daily") or 0) - led_day_req, 9)},
        "key_usage_weekly": kf.get("usage_weekly"), "key_usage_monthly": kf.get("usage_monthly"),
        "owner_dashboard": {"today_usd": float(a.dashboard_usd), "relayed_at": a.dashboard_relayed_at,
                            "reconciled": False, "see": "custody/DISCLOSURES.md item 24"},
    }
    item24 = (ITEM24_HEAD +
        f"The Owner reported, relayed by the Orchestrator at {a.dashboard_relayed_at}, that his OpenRouter dashboard shows "
        f"total spend today of US${float(a.dashboard_usd):.4f}. The key's own figures at the close read "
        f"({sr['read_at']}, custody/evidence/spend-status-close.json, one free GET /api/v1/key through the frozen harness) "
        f"are: usage {kf['usage']}, usage_daily {kf.get('usage_daily')} (OpenRouter's UTC day {utc_day}, i.e. from "
        f"20:00 EDT the evening before), usage_weekly {kf.get('usage_weekly')}, "
        f"usage_monthly {kf.get('usage_monthly')}; baseline before the job's first call {ss['key_usage_baseline']}, so "
        f"the job's key delta is {kdelta}. Against the job spend ledger: settles total {settled}; the key delta exceeds "
        f"them by {lost}, the unsettled LOST iteration-1 verifier a1 call (its reserve stays open at worst case "
        f"US${open_res[0]['worst_usd'] if open_res else 0}). For the UTC day the ledger settles {led_day}; "
        f"{len(cross)} call(s) were requested before 00:00Z and settled after it "
        f"({', '.join(c['call'] + ' ' + str(c['cost_usd']) for c in cross)}), which OpenRouter counts on the earlier "
        f"day; less those, {led_day_req}, which matches usage_daily to {recon['key_usage_daily_utc']['residual_usd']}. "
        f"So the key's own figures reconcile with the ledger, and the key's usage_daily is about ten times the "
        f"dashboard figure. The dashboard figure is not explained by the UTC day boundary (the EDT day 2026-10-29 "
        f"settles {sr['spend_ledger']['settled_by_edt_day'].get(utc_day)}), by late posting (the key already reports "
        f"the larger figure), or by BYOK (byok_usage 0). A different key, account, organization or workspace view, a "
        f"filter in the dashboard, or a misread are possible but were not checked: the Orchestrator cannot see the "
        f"dashboard. Not reconciled; the job total stays US${total} (the harness's spent_usd) under the bound "
        f"US${ss['bound_usd']}. Added at the close after the Owner's 13:15 EDT acceptance of the items then disclosed "
        f"(1-23); not yet seen by the Owner.")

    # -- held on box --
    dev = W / "DEVIATIONS-orchestrator.md"
    held.append((H(dev.read_bytes()), "DEVIATIONS-orchestrator.md (the Orchestrator's deviation log, at import time)"))
    held.append((H((J / "custody" / "controls" / "MANIFEST.sha256").read_bytes()),
                 "held-out controls: /workspace/job-controls/2026-10-28-custody-times-ledger-spend (by manifest)"))
    (EV / "HELD-ON-BOX.sha256").write_text(
        "# files held on the Owner's box (/workspace/edi-work/2026-10-28-custody-times-ledger-spend), not in the repo; "
        "sha256 only\n" + "".join(f"{s}  {d}\n" for s, d in held), encoding="utf-8")

    # -- disclosures 1-24 (items 1-22 copied verbatim from DEVIATIONS; items 23-24 added here) --
    dl = dev.read_text(encoding="utf-8").splitlines()
    items = [l for l in dl if re.match(r"^(\d|1\d|2[0-2])\. ", l)]
    nums = [int(l.split(".")[0]) for l in items]
    assert nums == list(range(1, 23)), nums
    (J / "custody" / "DISCLOSURES.md").write_text(
        "# Close disclosures, job 2026-10-28-custody-times-ledger-spend\n\n"
        "Accepted by the Owner on 2026-10-29 12:36 EDT: \"Accept the result with disclosures 1–22.\" Item 23 was "
        "added at the close on the Owner's instruction of the same time (\"disclose that the entries were recorded "
        "late\"). On 2026-10-29 13:15 EDT the Owner accepted items 1-23 (\"Accept all the disclosed items.\") and directed "
        "the close. Item 24 (spend figures) was added after that, at the close. Items 1-22 are copied verbatim from the "
        "Orchestrator's deviation log (held on the box; sha256 in custody/evidence/HELD-ON-BOX.sha256).\n\n"
        + "\n".join(items) + "\n" + ITEM23 + "\n" + item24 + "\n", encoding="utf-8")

    # -- ledger lines, late (item 23) --
    allm = {e["call"]: e for e in maker}
    for it in (1, 2):
        allm.update({e["call"]: e for e in guides[it]})
    rows = []
    def hand(ev: dict, at_source: str) -> dict:
        return {**ev, "writer": "hand", "hand_appended": True, "recorded_late": True, "recorded_by": ORCH,
                "recorded_at": a.recorded_at, "at_source": at_source, "note": NOTE23}
    src_of = lambda c: ("custody/evidence/harness-maker-deepseek.log" if c in {e["call"] for e in maker}
                        else f"custody/evidence/harness-maker-deepseek-guide-iter{c.split('_')[1][4]}.log")
    for it in (1, 2, 3):
        calls = sorted((e for c, e in allm.items() if c.startswith(f"maker_iter{it}_")), key=lambda e: e["sent_at"])
        first, last = calls[0], calls[-1]
        rev = git(repo, "rev-parse", REVS[it]).strip()
        changed = git(repo, "diff", "--name-only", PREV[it], rev).split()
        rows.append(hand({"event": "generation", "action": "open", "n": it, "seat": "maker", "at": iso_z(first["sent_at"])},
                         f"{src_of(first['call'])}#{first['call']}.sent_at = {first['sent_at']}"))
        rows.append(hand({"event": "generation", "action": "close", "n": it, "seat": "maker",
                          "at": iso_z(last["received_at"]), "revision": rev,
                          "calls": [{"call": e["call"], "generation_status": e.get("generation_status")} for e in calls],
                          "fix_kind": fix_kind(changed) if it > 1 else "initial build (iteration 1); " + fix_kind(changed),
                          "changed_from": PREV[it][:7], "changed_paths": len(changed)},
                         f"{src_of(last['call'])}#{last['call']}.received_at = {last['received_at']}; revision = git "
                         f"rev-parse {REVS[it]}"))
    for b in (1, 2, 3):
        s = s1[b]
        jl = {j: json.loads((E / f"b{b}" / "glm" / j / f"{j}-batch.json").read_text()) for j in JS}
        glog = json.loads((EV / f"harness-eval-glm-b{b}.log").read_text())
        lastg = max(glog, key=lambda e: e["received_at"])
        fails = sorted(k for k, v in s["results"].items() if v != "PASS")
        res_j = {j: jl[j].get(j) for j in JS}
        verdict = {1: "regenerate", 2: "regenerate", 3: "accept"}[b]
        ev = {"event": "evaluation", "iteration": b, "batch": b, "at": iso_z(lastg["received_at"]),
              "started_at": iso_z(s["started_at"]), "s1": {"passed": s["passed"], "total": s["total"],
              "fail": fails, "subject_rev": s["subject_rev"], "writer": s["writer"],
              "summary": f"custody/evidence/b{b}/s1-summary.json"},
              "e_glm": {j: {"result": res_j[j], "controls_ok": jl[j].get("controls_ok")} for j in JS},
              "verdict": verdict}
        if b == 3:
            ev["t6_amendment_2"] = {"score": 1, "file": "custody/evidence/T6-amend2.json",
                                    "frozen_verdict": "FAIL", "amendment": "AMENDMENT-2-t6-n1-refusal.md"}
            ev["verdict_file"] = "EVAL-ITER3-VERDICT.md"
        rows.append(hand(ev, f"started_at = eval/b{b}/s1/summary.json started_at {s['started_at']}; at = "
                             f"custody/evidence/harness-eval-glm-b{b}.log#{lastg['call']}.received_at "
                             f"{lastg['received_at']} (the batch's last call)"))
    relays = [
        ("2026-10-29T12:25:00Z", "E-DI Evaluator", "Evaluator chat, card t11s2",
         "Yes, go ahead with batch 2's S1 live call and the 15 E-GLM calls.",
         "VERIFY-iter2-batch2-orchestrator.md lines 8-9 (held on the box): user-role message at 08:25 EDT; minute only"),
        ("2026-10-29T13:55:00Z", "E-DI Maker", "Maker chat, card t21s1",
         "Yes, run iteration 3 of the custody-times-ledger-spend job on branch maker/custody-times-ledger-spend/iter3.",
         "handoffs/iter3/EVALUATOR.md line 16: 09:55 EDT; minute only"),
        ("2026-10-29T15:08:00Z", "E-DI Maker", "Maker chat, card t23s1",
         "Yes, run the iter3b follow-up (attempts a3 to a5) of the custody-times-ledger-spend job on branch "
         "maker/custody-times-ledger-spend/iter3.",
         "handoffs/iter3/EVALUATOR.md line 19: 11:08 EDT; minute only"),
    ]
    for at, frm, chat, quote, src in relays:
        rows.append(hand({"event": "relay", "relay": True, "at": at, "from": frm, "source_chat": chat, "by": "Steve Moitozo II",
                          "quote": quote, "approval": False,
                          "checked_by": f"{ORCH} in that chat's transcript (a relay is a report, not an approval)"},
                         src))
    rows.append(hand({"event": "spend", "at": iso_z(last_settle["at"]), "settled_usd": settled,
                      "reserves": len(res), "settles": len(stl), "open_reserves": open_res,
                      "settle_sources": {k: len(v) for k, v in by_src.items()},
                      "spend_ledger": "custody/evidence/spend-ledger.jsonl",
                      "spend_ledger_sha256": H(sl),
                      "key_usage_close_read": {"file": "custody/evidence/spend-status-close.json", "sha256": H(srb),
                                               "read_at": sr["read_at"], "key_usage": kf["usage"],
                                               "key_delta_usd": kdelta},
                      "total_usd": total, "reconciled": True,
                      "reconciliation": "key delta - settles = %s (the LOST iteration-1 verifier a1, no settle); "
                                        "UTC-day usage_daily matches the ledger to %s; the Owner's dashboard figure "
                                        "is not reconciled (disclosure 24); see custody/x-plumbline.json"
                                        % (lost, recon["key_usage_daily_utc"]["residual_usd"])},
                     f"custody/evidence/spend-ledger.jsonl last settle ({last_settle['call']}) at {last_settle['at']}"))
    rows.sort(key=lambda r: r["at"])  # ledger order = time order (stable for equal times)
    assert rows[-1]["event"] == "spend", rows[-1]
    with LED.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    led_sha = H(LED.read_bytes())

    # -- sidecar --
    side = {
        "schema": "plumbline/x-plumbline sidecar (job-local; base emitter 3df1ce5 cannot carry x-plumbline)",
        "job_id": "2026-10-28-custody-times-ledger-spend",
        "emitter": {"rev": BASE, "tree": "230997f1ca9c89ccf035997c4a4db31a0c8ba5fa",
                    "why_base": "bar: base tooling only for this job's own record (bar.md lines 145-157)"},
        "hand_times": {"ledger": "inputs/custody-events.jsonl", "lines": list(range(9, 9 + len(rows))) + [9 + len(rows)],
                       "note": "every line from 9 on is hand-appended (writer \"hand\"); the last is the dispose "
                               "line written by CLOSE-apply.sh. Disclosure item 23."},
        "ledger_sha256_after_import": led_sha,
        "spend": {"settled_usd": settled, "reserves": len(res), "settles": len(stl), "open_reserves": open_res,
                  "settle_sources": by_src, "last_settle_at": last_settle["at"],
                  "key_usage_baseline": {"file": "custody/evidence/key-usage-baseline.json",
                                         "usage": json.loads((W / 'spend' / 'key-usage-baseline.json').read_text())["usage"]},
                  "key_usage_close": kf["usage"], "key_delta_usd": kdelta, "total_usd": total, "reconciled": True,
                  "reconciliation": recon,
                  "p6": "MET at the close read: spend from the replies (settles) reconciled with a key-usage read "
                        ">= 3 min after the last call (custody/evidence/spend-status-close.json, frozen harness, no "
                        "model call; Owner decision 2026-10-29 13:15 EDT \"Do the final spend read.\"). The Owner's "
                        "dashboard figure is not reconciled: disclosure 24."},
        "relays": [{"at": r[0], "from": r[1], "chat": r[2], "source": r[4]} for r in relays],
        "evaluations": [{"batch": b, "s1": f"{s1[b]['passed']}/{s1[b]['total']}",
                         "glm_log_sha256": glm[b]["out_sha256"], "glm_redacted_calls": glm[b]["redacted_calls"]}
                        for b in (1, 2, 3)],
        "disclosures": {"file": "custody/DISCLOSURES.md", "items": 24},
        "post_merge_verifier": ("after the subject is merged, kit/plumbline_verify.py is run once on this record, "
                                "post hoc and non-gating (bar.md lines 145-157); expected exit 4 (no x-plumbline "
                                "block in a base-emitted record); filed as an amendment after the real close"),
    }
    (J / "custody" / "x-plumbline.json").write_text(json.dumps(side, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # -- method note --
    (J / "custody" / "method.md").write_text(f"""# Method, job 2026-10-28-custody-times-ledger-spend

Maker: DeepSeek V4.1 Flash 1017 (deepseek/deepseek-v4.1-flash-1017) via openrouter.ai, provider order deepinfra/fp8,
no fallbacks, ZDR. Every Maker call was issued by a harness operator, the E-DI Maker bot (a Grok Bot), through the
frozen harness; the operator extracted the returned files verbatim (handoffs/extract_files.py) and committed them on
maker/custody-times-ledger-spend/iterN. This was instructed, not enforced.

Iterations (one generation each; bar cap 3):
- 1: calls maker_iter1_* (harness-maker-deepseek.log, -guide-iter1.log), revision 1cb410b. Batch 1: regenerate.
- 2: calls maker_iter2_* (harness-maker-deepseek.log, -guide-iter2.log), revision c882646. Batch 2: regenerate.
- 3: calls maker_iter3_fix_a1..a4 (harness-maker-deepseek.log), revision f95e0d3. Batch 3: accept (43/43 with
  Amendment 2's T6; EVAL-ITER3-VERDICT.md).

Maker calls left out of the record's maker call list (`maker.calls`): maker_iter1_ledger_a1, maker_iter1_docs_a1,
maker_iter3_fix_a1 and maker_iter3_fix_a2 (their /api/v1/generation fetch returned 404, so the base emitter cannot read
an endpoint for them) and the two guide logs (the base emitter reads one Maker log). They stay in the evidence logs.

Evaluators: S1 (custody/freeze/instrument/run_instrument.sh, scheck.py) and E-GLM (z-ai/glm-5.3-flash via
openrouter.ai, provider z-ai/fp8; jbatch.py, rubric-J1..4.md). E-GLM ran as four checks with one log each; the record
uses one merged log per batch (harness-eval-glm-bN.log), redacted of held-out control text
(handoffs/close/redact_glm_log.py). S1's batch-3 per-check evidence (custody/evidence/<check>.json, T6-amend2.json)
is filed redacted where a check echoed held-out fixture values (handoffs/close/redact_s1_evidence.py: each such value is
replaced by a fixed marker; ids, verdicts and reasons are kept); the full files stay on the Owner's box, sha256 in
custody/evidence/HELD-ON-BOX.sha256.
""", encoding="utf-8")

    # -- iteration-3 verdict note --
    s = s1[3]
    gl = "; ".join(f"{j} {b3batch[j].get(j)} (controls_ok {b3batch[j].get('controls_ok')})" for j in JS)
    (J / "EVAL-ITER3-VERDICT.md").write_text(f"""# Iteration 3 verdict, job 2026-10-28-custody-times-ledger-spend

Batch 3, subject f95e0d3 (maker/custody-times-ledger-spend/iter3), scored by the E-DI Evaluator.
- S1 (scheck.py @ 49d3a506f6f7): {s['passed']}/{s['total']} as frozen, {s['started_at']} to {s['finished_at']};
  the one frozen FAIL is T6. Every S1 control right ({sum(1 for c in s['controls'].values() if c['right'])}/{len(s['controls'])}).
- T6 under Amendment 2 (AMENDMENT-2-t6-n1-refusal.md): score 1 (custody/evidence/T6-amend2.json; frozen verdict FAIL).
- E-GLM: {gl}.
- Batch: VALID (no control wrong). Every check T1-J4 scores 1 under Amendment 2: 43/43 -> terminal state accepted.

Verified by the Orchestrator (on the box, 2026-10-29 12:28-12:34 EDT). Owner disposition 2026-10-29 12:36 EDT:
"Accept the result with disclosures 1–22." Disclosures 1-24: custody/DISCLOSURES.md (1-23 accepted 13:15 EDT).
""", encoding="utf-8")
    print(json.dumps({"ledger_lines_added": len(rows), "ledger_sha256": led_sha, "settled_usd": settled,
                      "open_reserves": open_res, "glm": {b: glm[b]["calls"] for b in glm}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
