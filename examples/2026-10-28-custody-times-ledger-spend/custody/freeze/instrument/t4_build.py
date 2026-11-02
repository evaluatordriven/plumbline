#!/usr/bin/env python3
# STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — S1 T4 builder, job 2026-10-28-custody-times-ledger-spend (author: Chief of Staff (Orchestrator) drafter).
"""T4 builder (S1, job 2026-10-28-custody-times-ledger-spend). Builds a job ONLY with tools, at the moment it runs:
plumbline_job.py open -> custody_ledger.py freeze/approve/pin -> [generation open] -> tools/edi/or_call.py (mocked
transport) maker call -> [generation close] -> evaluator calls -> [evaluation] -> [spend] -> dispose ->
plumbline_job.py close. Subject mode also logs a relay and an amendment (both bounded at the freeze time) and, at
least 181 s after the last settle line, an `or_call.py --spend-status` key reading and a `spend` line.
No time is typed anywhere: inputs/custody.json carries no time field; every time comes from a ledger line, a
logger time in a harness log, or the packet close.

  t4_build.py --tools CHECKOUT --or-call PATH --work DIR --controls C --corpus CORPUS [--mode subject|base-proto]
              [--custody CHECKOUT] [--python PY] [--stop-after STEP] [--inject-hand] [--close-switch] [--no-spend]

--stop-after STEP: stop (ok true) after the named step (scratch jobs for F1 drivers). --inject-hand: after the maker
call, type `startedAt` into inputs/custody.json equal to the maker log's logger sent_at (a hand time: no ledger line).
--close-switch: pass --allow-hand-times to close. --no-spend: skip the spend wait and line (faster scratch builds).

--mode base-proto (pre-freeze prototype on base 3df1ce5): base has no generation/evaluation commands and no
dispose --decided-at, so those steps are skipped and `dispose --by` is used. --mode subject (batch time): every step.
Writes DIR/t4-build.json: {started_at, finished_at, writer, mode, steps: [{name, argv, rc, stdout, stderr, t0, t1}], ok}.
Stops at the first step that fails (ok false). Stdlib only.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
JOB_NAME = "2026-10-28-s1-t4-tool-built"
MAKER = {"seat": "maker", "model": "deepseek/deepseek-v4.1-flash-1017", "tag": "deepinfra/fp8",
         "provider": "DeepInfra", "host": "api.deepinfra.com"}
EVAL = {"seat": "eval-m", "model": "z-ai/glm-5.3-flash", "tag": "z-ai/fp8", "provider": "Z.AI", "host": "api.z.ai"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Run:
    def __init__(s, out, env):
        s.out, s.env, s.steps = out, env, []

    stop_after = None

    def __call__(s, name, argv, cwd=None):
        t0 = now()
        r = subprocess.run([str(x) for x in argv], cwd=cwd, env=s.env, capture_output=True, text=True)
        s.steps.append({"name": name, "argv": [str(x) for x in argv], "rc": r.returncode,
                        "stdout": r.stdout[-4000:], "stderr": r.stderr[-4000:], "t0": t0, "t1": now()})
        if r.returncode != 0:
            raise SystemExit(f"step {name} rc {r.returncode}")
        time.sleep(1.2)   # tool times are whole seconds; a real job's steps are seconds apart, and so are these
        if name == s.stop_after:
            raise Stop(name)
        return r


class Stop(Exception):
    pass


def ledger_lines(J):
    p = J / "inputs" / "custody-events.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def mock_dir(d: Path, tpl: Path, who: dict, content: str):
    d.mkdir(parents=True, exist_ok=True)
    chat = json.loads((tpl / "chat-deepinfra.json").read_text())
    gen = json.loads((tpl / "generation-deepinfra.json").read_text())
    b = chat["body"]
    t = int(datetime.now(timezone.utc).timestamp())
    gid = f"gen-{t}-s1t4{who['seat']}"
    b.update({"id": gid, "created": t, "model": who["model"], "provider": who["provider"]})
    b["choices"][0]["message"]["content"] = content
    b["choices"][0]["message"].pop("reasoning", None); b["choices"][0]["message"].pop("reasoning_details", None)
    b["openrouter_metadata"]["requested"] = who["model"]
    b["openrouter_metadata"]["summary"] = f"available=1, selected={who['provider']}"
    b["openrouter_metadata"]["endpoints"]["available"] = [{"provider": who["provider"], "model": who["model"], "selected": True}]
    chat["headers"]["Date"] = "NOW"
    g = gen["data"]
    g.update({"id": gid, "model": who["model"], "provider_name": who["provider"], "total_cost": 0.00001,
              "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")})
    g["provider_responses"] = [{**g["provider_responses"][0], "provider_name": who["provider"],
                                "model_permaslug": who["model"]}]
    (d / "chat.json").write_text(json.dumps(chat))
    (d / "generation.json").write_text(json.dumps({"status": 200, "headers": {"Date": "NOW"}, "body": gen}))
    (d / "key.json").write_text(json.dumps({"status": 200, "headers": {"Date": "NOW"},
                                            "body": {"data": {"usage": 1.0, "limit": None}}}))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", required=True); ap.add_argument("--or-call", required=True)
    ap.add_argument("--work", required=True); ap.add_argument("--controls", required=True)
    ap.add_argument("--corpus", required=True); ap.add_argument("--custody")
    ap.add_argument("--mode", choices=["subject", "base-proto"], default="subject")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--stop-after"); ap.add_argument("--inject-hand", action="store_true")
    ap.add_argument("--close-switch", action="store_true"); ap.add_argument("--no-spend", action="store_true")
    a = ap.parse_args(argv)
    started = now()
    tools, C, W = Path(a.tools).resolve(), Path(a.controls).resolve(), Path(a.work).resolve()
    if W.exists():
        shutil.rmtree(W)
    W.mkdir(parents=True)
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if a.custody:
        env["PLUMBLINE_CUSTODY"] = a.custody
    run = Run(W, env); run.stop_after = a.stop_after
    py, K = a.python, tools / "kit"
    J = W / "jobs" / JOB_NAME
    src = C / "t4" / "template"            # held-out template: bar, method, brief, run file, evidence, custody.json
    ok, err = False, None
    try:
        brief = json.loads((src / "brief.json").read_text()); brief["job_id"] = JOB_NAME
        (W / "brief.json").write_text(json.dumps(brief, indent=2) + "\n")
        runlog = W / "run-log.json"
        run("open", [py, K / "plumbline_job.py", "open", "--brief", W / "brief.json", "--job-dir", J,
                     "--corpus", a.corpus, "--run-log", runlog])
        shutil.copytree(src / "custody", J / "custody", copy_function=shutil.copyfile)
        (J / "inputs").mkdir(exist_ok=True)
        shutil.copyfile(src / "custody.json", J / "inputs" / "custody.json")
        L = ["--job-dir", J]
        run("freeze", [py, K / "custody_ledger.py", "freeze", *L, "--bar", "custody/bar.md",
                       "--orchestrator", "S1 T4 builder"])
        run("approve-buyer", [py, K / "custody_ledger.py", "approve", *L, "--role", "buyer", "--by", "T4 Buyer"])
        run("approve-specialist", [py, K / "custody_ledger.py", "approve", *L, "--role", "specialist",
                                   "--by", "T4 Specialist"])
        for s in (MAKER, EVAL):
            run(f"pin-{s['seat']}", [py, K / "custody_ledger.py", "pin", *L, "--seat", s["seat"], "--provider",
                                     s["provider"], "--slug", s["tag"], "--host", s["host"]])
        js = W / "job-spend.json"; (J / "spend").mkdir()
        js.write_text(json.dumps({"job_id": JOB_NAME, "bound_usd": 5.0, "reserve_usd": 0.1,
                                  "spend_ledger": str(J / "spend" / "spend-ledger.jsonl"),
                                  "prices": [{"model": s["model"], "tag": s["tag"], "prompt_usd_per_token": 1e-7,
                                              "completion_usd_per_token": 3e-7, "max_completion_tokens": 131072}
                                             for s in (MAKER, EVAL)]}) + "\n")
        dummy = W / "dummy-key"; dummy.write_text("sk-or-v1-S1-T4-DUMMY-NOT-A-KEY\n"); dummy.chmod(0o600)
        tpl = C / "t4" / "mock-templates"
        mock_dir(W / "mock-init", tpl, MAKER, "x")
        oc = [py, a.or_call, "--job-spend", js, "--key-file", dummy]
        run("init-spend", [*oc, "--init-spend", "--mock-transport", W / "mock-init"])
        ev = J / "custody" / "evidence"
        if a.mode == "subject":
            fz = ledger_lines(J)[0]["at"]
            run("relay", [py, K / "custody_ledger.py", "relay", *L, "--quote", "Steve: \u201cRatified proceed\u201d \u2014 go \u2713",
                          "--from", "S1 T4 relay bot", "--source-chat", "t4-chat msg r1", "--source-at", fz])
            am = J / "amendments" / "amendment-1.md"; am.parent.mkdir(exist_ok=True)
            am.write_text("# Amendment 1 (S1 T4)\nThe Buyer clarified D2's wording.\n")
            run("amendment", [py, K / "custody_ledger.py", "amendment", *L, "--file", am, "--quote",
                              "T4 Buyer: \u201cD2 means every named section\u201d", "--channel", "t4-chat msg a1",
                              "--said-at", fz])
        msgs = J / "inputs" / "maker-messages.json"   # inside the job: the generation line names it relatively
        msgs.write_text(json.dumps([{"role": "user", "content": "Write custody/files/artifact.md."}]))
        if a.mode == "subject":
            run("generation-open", [py, K / "custody_ledger.py", "generation", "open", *L, "--seat", "maker",
                                    "--prompt", msgs])
        mock_dir(W / "mock-maker", tpl, MAKER, (src / "custody" / "files" / "artifact.md").read_text())
        run("maker-call", [*oc, "--mock-transport", W / "mock-maker", "--seat", "maker", "--log",
                           ev / "harness-maker-t4.log", "--model", MAKER["model"], "--ledger",
                           J / "inputs" / "custody-events.jsonl", "--messages", msgs, "--out", W / "maker-reply.txt",
                           "--call", "maker_1", "--gen-wait", "0"])
        if a.inject_hand:
            ci = json.loads((J / "inputs" / "custody.json").read_text())
            ci["startedAt"] = json.loads((ev / "harness-maker-t4.log").read_text())[0]["sent_at"]
            (J / "inputs" / "custody.json").write_text(json.dumps(ci, indent=2, ensure_ascii=False) + "\n")
        if a.mode == "subject":
            run("generation-close", [py, K / "custody_ledger.py", "generation", "close", *L, "--seat", "maker",
                                     "--n", "1", "--outcome", "artifact written", "--fix-kind", "artifact"])
        for call, reply in (("eval_artifact", "D1 10 D2 10"), ("eval_k1", "CONFORMS"), ("eval_k2", "DOES_NOT_CONFORM D2")):
            m = W / f"msgs-{call}.json"; m.write_text(json.dumps([{"role": "user", "content": f"Judge {call}."}]))
            mock_dir(W / f"mock-{call}", tpl, EVAL, reply)
            run(f"eval-{call}", [*oc, "--mock-transport", W / f"mock-{call}", "--seat", "eval-m", "--log",
                                 ev / "harness-eval-m.log", "--model", EVAL["model"], "--ledger",
                                 J / "inputs" / "custody-events.jsonl", "--messages", m, "--out",
                                 W / f"reply-{call}.txt", "--call", call, "--gen-wait", "0", "--temperature", "0"])
        if a.mode == "subject":
            run("evaluation", [py, K / "custody_ledger.py", "evaluation", *L, "--batch", "b1", "--evaluator",
                               "eval-m", "--verdict", J / "custody" / "evidence" / "pass-a-D2.txt", "--iteration", "1"])
            evline = [x for x in ledger_lines(J) if x.get("event") == "evaluation"][-1]
            cands = [json.loads((ev / "harness-eval-m.log").read_text())[-1]["received_at"], evline["at"]]
            cands += [evline[k] for k in ("finished_at",) if evline.get(k)]
            last = max(cands, key=lambda v: datetime.fromisoformat(v.replace("Z", "+00:00")))
            if not a.no_spend:
                sl = J / "spend" / "spend-ledger.jsonl"
                settles = [json.loads(x)["at"] for x in sl.read_text().splitlines() if '"settle"' in x]
                t_last = datetime.fromisoformat(max(settles).replace("Z", "+00:00"))
                wait = 181 - (datetime.now(timezone.utc) - t_last).total_seconds()
                if wait > 0:
                    time.sleep(wait)
                mock_dir(W / "mock-status", tpl, MAKER, "x")
                kr = J / "spend" / "key-reading.json"
                run("spend-status", [*oc, "--spend-status", "--out", kr, "--mock-transport", W / "mock-status"])
                run("spend", [py, K / "custody_ledger.py", "spend", *L, "--spend-ledger", sl, "--key-reading", kr])
            run("dispose", [py, K / "custody_ledger.py", "dispose", *L, "--by", "T4 Buyer", "--state", "given",
                            "--decided-at", last, "--decided-source", "harness-eval-m.log#eval_k2 received_at"])
        else:
            run("dispose", [py, K / "custody_ledger.py", "dispose", *L, "--by", "T4 Buyer"])
        rf = W / "run-1.json"
        r = json.loads((src / "run-1.json").read_text()); r["job_id"] = JOB_NAME
        rf.write_text(json.dumps(r, indent=2) + "\n")
        close = [py, K / "plumbline_job.py", "close", "--job-dir", J, "--run", rf, "--terminal-state", "accepted",
                 "--outcome", "accepted", "--disposition", "given", "--disposition-note", "T4 Buyer: accepted",
                 "--corpus", a.corpus, "--run-log", runlog]
        if a.mode == "subject" and a.custody:
            close += ["--custody", a.custody]
        if a.close_switch:
            close += ["--allow-hand-times"]
        run("close", close)
        ok = True
    except Stop:
        ok = True
    except SystemExit as e:
        err = str(e)
    out = {"started_at": started, "finished_at": now(), "writer": f"freeze/instrument/t4_build.py@{sha(HERE)[:12]}", "mode": a.mode,
           "job_dir": str(J), "steps": run.steps, "ok": ok, "error": err}
    (W / "t4-build.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({"ok": ok, "error": err, "job_dir": str(J)}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
