#!/usr/bin/env python3
"""Log a job's custody events WHEN THEY HAPPEN, so no time in the custody record is typed from memory.

The emitter (kit/emit_custody.py) reads model-call times from harness logs. Three events have no harness log:
the bar's freeze, each approval of the bar, and the Owner's disposition. This tool stamps each with the clock at
the moment it is run, writes it into inputs/custody.json, and appends it to inputs/custody-events.jsonl. The
emitter then refuses a ledger value that differs from the logged one, and refuses the bar if it changed after the
freeze. Run it at the moment the thing happens, not afterwards: a late stamp is a wrong time.

Every line this tool appends carries `writer: "kit/custody_ledger.py@<sha12>"` (the sha256 of the file that ran)
and `at` (the tool's clock), so a reader can tell a tool stamp from a hand-typed one (T1).

    custody_ledger.py freeze  --job-dir J [--bar custody/bar.md] [--orchestrator "Agent name" [--orchestrator-alias A]]
    custody_ledger.py approve --job-dir J --role buyer|specialist --by "Name" [--kind person|agent]
                              [--adopted-document D --adopted-version V]
    custody_ledger.py dispose --job-dir J --by "Name" [--state given|declined]
                              [--decided-at T --decided-source S] [--words W]
    custody_ledger.py pin     --job-dir J --seat maker|<evaluator id> --provider "DeepInfra" --slug deepinfra/fp8
                              --host api.deepinfra.com [--via openrouter.ai]
    custody_ledger.py show    --job-dir J

    custody_ledger.py generation open  --job-dir J --seat S --prompt FILE
    custody_ledger.py generation close --job-dir J --seat S --n N [--outcome TEXT] [--fix-kind TEXT]
    custody_ledger.py evaluation --job-dir J --batch B --evaluator ID [--verdict FILE] [--summary FILE] [--iteration N]
    custody_ledger.py amendment  --job-dir J --file F --quote Q --channel C --said-at T
    custody_ledger.py relay      --job-dir J --quote Q --from BOT --source-chat C --source-at T
    custody_ledger.py spend      --job-dir J --spend-ledger L --key-reading R

`approve` records the digest of the bar file AT THAT MOMENT as the digest approved. It records who approved; it
is not a signature (custody: approvals are records). An approval by the orchestrating agent or a model is refused
here as it is by the emitter.

`pin` declares, BEFORE the seat's first model call, which single upstream provider will serve that seat through
the aggregator: the provider's name as OpenRouter's responses give it (`provider`), the slug the request's
provider.order will carry (`slug`), and the provider's own API host (`host`), which becomes the custody endpoint.
It is refused once the seat's harness log records a call. The emitter refuses the record if any call was served
by, or also tried at, another provider, if the log does not say who served a call, or if the pin was declared
after the first call.

`generation`, `evaluation`, `amendment`, `relay` and `spend` record the batch's own events as they happen, so the
emitter can carry them into `x-plumbline.generations[]`, `evaluations[]`, `amendments[]`, `relays[]` and `spend`
(F1a-F1h). `dispose --decided-at` bounds the Owner's decision between the last logged check and the tool's clock
(F1b). `evaluation` takes `--verdict FILE`; when `--verdict` is omitted the `--summary FILE` (which must carry the
instrument's own `started_at`/`finished_at`/`writer` stamp) also serves as the verdict file. Every refusal,
usage errors included, exits non-zero (2 = usage, 3 = refused), prints a line starting `REFUSED:` on stderr, and
changes neither the ledger nor `custody.json`. Stdlib only.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import custody_history as H          # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def writer_stamp() -> str:
    """`kit/custody_ledger.py@<sha12>` for the file that is running (T1)."""
    try:
        d = sha256(Path(__file__).resolve().read_bytes()).hexdigest()[:12]
    except OSError:
        d = "0" * 12
    return f"kit/custody_ledger.py@{d}"


def relpath(job: Path, p: Path) -> str:
    """A path relative to the job dir when inside it, else absolute (INTERFACE section 1)."""
    try:
        return p.resolve().relative_to(job.resolve()).as_posix()
    except ValueError:
        return str(p.resolve())


def read_events(job: Path) -> list[dict]:
    p = job / "inputs" / "custody-events.jsonl"
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if isinstance(ev, dict):
                out.append(ev)
    return out


def seat_logs(job: Path, ci: dict, seat: str) -> list[Path]:
    """Harness logs that may already hold this seat's calls (named in the inputs, or by the usual file names)."""
    ev = job / ci.get("evidence_dir", "custody/evidence")
    if seat == "maker":
        named, pat = (ci.get("maker") or {}).get("harness_log"), "harness-maker*.log"
    else:
        e = next((x for x in ci.get("evaluators") or [] if str(x.get("id")) == seat), {})
        named = e.get("harness_log") or next((x.get("evidence_file") for x in ci.get("external") or []
                                              if x.get("subject") == seat), None)
        pat = f"harness-{seat}*.log"
    out = [b / named for b in (ev, job) if named and (b / named).is_file()]
    out += sorted(ev.glob(pat)) if ev.is_dir() else []
    return list(dict.fromkeys(out))


def last_check_time(job: Path, ci: dict) -> datetime | None:
    """The latest logged check: evaluator `received_at`, `evaluation` line times, instrument `finished_at` (F1b)."""
    times = []
    for ev in read_events(job):
        if ev.get("event") == "evaluation":
            for k in ("started_at", "finished_at", "at"):
                d = H.parse_ts(ev.get(k))
                if d:
                    times.append(d)
            sf = ev.get("summary_file")
            if sf:
                p = Path(sf)
                if not p.is_absolute():
                    p = job / p
                if p.is_file():
                    try:
                        s = json.loads(p.read_text(encoding="utf-8"))
                        d = H.parse_ts(s.get("finished_at"))
                        if d:
                            times.append(d)
                    except (ValueError, OSError):
                        pass
    for e in ci.get("evaluators") or []:
        seat = str(e.get("id"))
        for log in seat_logs(job, ci, seat):
            ref = H.Refusals()
            for c in H.read_log(log, ref, seat):
                if c.received:
                    times.append(c.received)
    evdir = job / ci.get("evidence_dir", "custody/evidence")
    if evdir.is_dir():
        for p in evdir.rglob("*.json"):
            try:
                s = json.loads(p.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if isinstance(s, dict) and str(s.get("writer", "")).startswith("tools/edi/"):
                d = H.parse_ts(s.get("finished_at"))
                if d:
                    times.append(d)
    return max(times) if times else None


def append_event(job: Path, ev: dict) -> None:
    p = job / "inputs" / "custody-events.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")


def write_custody(job: Path, ci: dict) -> None:
    p = job / "inputs" / "custody.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(ci, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def refuse(msg: str, code: int = 3) -> int:
    print(f"REFUSED: {msg}", file=sys.stderr)
    return code


class RefusingParser(argparse.ArgumentParser):
    """argparse's own usage errors exit 2 with a `REFUSED:` line, like every other refusal (F1a, INTERFACE 1)."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"REFUSED: {message}", file=sys.stderr)
        raise SystemExit(2)


def main(argv=None) -> int:
    ap = RefusingParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    for n in ("freeze", "approve", "dispose", "pin", "show"):
        s = sub.add_parser(n)
        s.add_argument("--job-dir", required=True)
        if n == "freeze":
            s.add_argument("--bar", default=None, help="bar file, relative to the job (default: the ledger's, else custody/bar.md)")
            s.add_argument("--orchestrator", help="the orchestrating agent's name, as approvals would name it")
            s.add_argument("--orchestrator-alias", action="append", default=[])
        if n in ("approve", "dispose"):
            s.add_argument("--by", required=True)
        if n == "pin":
            s.add_argument("--seat", required=True, help="maker, or an evaluator's id")
            s.add_argument("--provider", required=True, help="provider name as OpenRouter's response `provider` gives it")
            s.add_argument("--slug", required=True, help="the provider slug the requests' provider.order carries")
            s.add_argument("--host", required=True, help="the provider's own API host (the custody endpoint)")
            s.add_argument("--via", default="openrouter.ai")
        if n == "approve":
            s.add_argument("--role", required=True, choices=("buyer", "specialist"))
            s.add_argument("--kind", default="person", choices=("person", "agent"))
            s.add_argument("--adopted-document")
            s.add_argument("--adopted-version")
        if n == "dispose":
            s.add_argument("--state", choices=("given", "declined"))
            s.add_argument("--decided-at")
            s.add_argument("--decided-source")
            s.add_argument("--words")

    g = sub.add_parser("generation")
    g.add_argument("action", choices=("open", "close"))
    g.add_argument("--job-dir", required=True)
    g.add_argument("--seat", required=True)
    g.add_argument("--prompt")
    g.add_argument("--n", type=int)
    g.add_argument("--outcome")
    g.add_argument("--fix-kind")

    ev = sub.add_parser("evaluation")
    ev.add_argument("--job-dir", required=True)
    ev.add_argument("--batch", required=True)
    ev.add_argument("--evaluator", required=True)
    ev.add_argument("--verdict", help="the verdict file; may be omitted when --summary is given "
                                      "(the summary is then also the verdict)")
    ev.add_argument("--summary")
    ev.add_argument("--iteration")

    am = sub.add_parser("amendment")
    am.add_argument("--job-dir", required=True)
    am.add_argument("--file", required=True)
    am.add_argument("--quote", required=True)
    am.add_argument("--channel", required=True)
    am.add_argument("--said-at", required=True)

    rl = sub.add_parser("relay")
    rl.add_argument("--job-dir", required=True)
    rl.add_argument("--quote", required=True)
    rl.add_argument("--from", dest="from_", required=True)
    rl.add_argument("--source-chat", required=True)
    rl.add_argument("--source-at", required=True)

    sp = sub.add_parser("spend")
    sp.add_argument("--job-dir", required=True)
    sp.add_argument("--spend-ledger", required=True)
    sp.add_argument("--key-reading", required=True)

    a = ap.parse_args(argv)
    job = Path(a.job_dir).expanduser().resolve()
    ledger_p, events_p = job / "inputs" / "custody.json", job / "inputs" / "custody-events.jsonl"
    try:
        ci = (json.loads(ledger_p.read_text(encoding="utf-8")) if ledger_p.is_file()
              else {"custody_inputs": "plumbline/custody-inputs/v1"})
    except (ValueError, OSError) as exc:
        return refuse(f"cannot read {ledger_p} ({exc})", 2)
    if not isinstance(ci, dict):
        return refuse(f"{ledger_p} does not hold a JSON object", 2)
    if a.cmd == "show":
        print(events_p.read_text(encoding="utf-8") if events_p.is_file() else "(no events logged)", end="")
        return 0

    bar = ci.setdefault("bar", {})
    t = now()
    ci_changed = a.cmd in ("freeze", "approve", "pin", "dispose")

    if a.cmd == "freeze":
        rel = a.bar or bar.get("file") or "custody/bar.md"
        if not (job / rel).is_file():
            return refuse(f"no bar file at {job / rel}", 2)
        if bar.get("frozenAt"):
            return refuse(f"the bar was already frozen at {bar['frozenAt']}; a bar is frozen once", 2)
        d = sha256((job / rel).read_bytes()).hexdigest()
        bar.update({"file": rel, "frozenAt": t})
        if a.orchestrator:
            ci["orchestrator"] = {"name": a.orchestrator, "kind": "agent", "aliases": a.orchestrator_alias}
        ev = {"event": "freeze", "at": t, "bar_file": rel, "bar_sha256": d}

    elif a.cmd == "approve":
        if not bar.get("frozenAt") or not (job / str(bar.get("file"))).is_file():
            return refuse("freeze the bar first (custody_ledger.py freeze); an approval names a frozen bar", 2)
        adopted = None
        if a.adopted_document or a.adopted_version:
            adopted = {"document": a.adopted_document, "version": a.adopted_version}
        appr = {"role": a.role, "by": a.by, "kind": a.kind,
                "barDigest": sha256((job / bar["file"]).read_bytes()).hexdigest(), "at": t, "adopted": adopted}
        ref = H.Refusals()
        pk = job / "packet.json"
        H.check_approval(appr, 0, ci, json.loads(pk.read_text(encoding="utf-8")) if pk.is_file() else {}, ref)
        if ref:
            for _, m in ref.rows:
                print(f"REFUSED: {m}")
            return 3
        bar["approvals"] = [x for x in bar.get("approvals") or [] if x.get("role") != a.role] + [appr]
        ev = {"event": "approve", **{k: appr[k] for k in ("role", "by", "kind", "at", "barDigest", "adopted")}}

    elif a.cmd == "pin":
        host, via = a.host.strip().lower(), a.via.strip().lower()
        if not H.HOST.match(host) or host in H.AGGREGATORS:
            return refuse(f"{a.host!r} is not an upstream provider's host name (the aggregator is --via)", 2)
        if via not in H.AGGREGATORS:
            return refuse(f"--via {a.via!r} is not a known aggregator ({', '.join(sorted(H.AGGREGATORS))}); "
                          f"a call made straight to a provider needs no pin", 2)
        for log in seat_logs(job, ci, a.seat):
            calls = H.read_log(log, H.Refusals(), a.seat)
            if calls:
                return refuse(f"{log.name} already records {len(calls)} call(s) for {a.seat}; a pin declared "
                              f"after the seat's first call is not a pin. Declare it before the seat starts.", 3)
        pin = {"via": via, "provider": a.provider, "slug": a.slug, "host": host, "declaredAt": t}
        ci.setdefault("routing", {})[a.seat] = pin
        ev = {"event": "pin", "seat": a.seat, **{k: pin[k] for k in ("via", "provider", "slug", "host")}, "at": t}

    elif a.cmd == "dispose":
        if a.decided_at:
            dt = H.parse_ts(a.decided_at)
            if dt is None:
                return refuse(f"--decided-at {a.decided_at!r} is not RFC 3339 UTC (...Z)", 2)
            if not a.decided_source:
                return refuse("--decided-at requires --decided-source", 2)
            last = last_check_time(job, ci)
            if last and dt < last:
                return refuse(f"decided_at {a.decided_at} is before the last logged check at {H.iso(last)}", 3)
            if dt > H.parse_ts(t):
                return refuse(f"decided_at {a.decided_at} is after the tool's clock {t}", 3)
            decided_at = a.decided_at
        else:
            decided_at = t
        disp = {**(ci.get("disposition") or {}), "by": a.by, "at": decided_at}
        if a.state:
            disp["state"] = a.state
        if a.words:
            disp["words"] = a.words
        ci["disposition"] = disp
        ev = {"event": "dispose", "by": a.by, "at": t}
        if a.decided_at:
            ev.update({"decided_at": a.decided_at, "decided_source": a.decided_source})
        if a.state:
            ev["state"] = a.state
        if a.words:
            ev["words"] = a.words

    elif a.cmd == "generation":
        events = read_events(job)
        seat_events = [x for x in events if x.get("event") == "generation" and x.get("seat") == a.seat]
        opens = {}
        last_action = None
        for x in seat_events:
            n = x.get("n")
            if x.get("action") == "open":
                opens[n] = False
                last_action = ("open", n)
            elif x.get("action") == "close":
                if n in opens:
                    opens[n] = True
                last_action = ("close", n)
        if a.action == "open":
            if not a.prompt:
                return refuse("generation open requires --prompt FILE", 2)
            if last_action and last_action[0] == "open":
                return refuse(f"generation {last_action[1]} for {a.seat} is still open; close it first", 3)
            n = max(opens) + 1 if opens else 1
            p = Path(a.prompt)
            if not p.is_absolute():
                p = job / p
            if not p.is_file():
                return refuse(f"no prompt file at {p}", 2)
            d = sha256(p.read_bytes()).hexdigest()
            ev = {"event": "generation", "action": "open", "seat": a.seat, "n": n,
                  "prompt_file": relpath(job, p), "prompt_sha256": d, "at": t}
        else:
            if a.n is None:
                return refuse("generation close requires --n N", 2)
            if a.n not in opens:
                return refuse(f"no open generation {a.n} for {a.seat}", 3)
            if opens[a.n]:
                return refuse(f"generation {a.n} for {a.seat} is already closed", 3)
            ev = {"event": "generation", "action": "close", "seat": a.seat, "n": a.n,
                  "outcome": a.outcome, "fix_kind": a.fix_kind, "at": t}

    elif a.cmd == "evaluation":
        target = a.verdict or a.summary
        if not target:
            return refuse("evaluation requires --verdict FILE (or --summary FILE to serve as the verdict)", 2)
        p = Path(target)
        if not p.is_absolute():
            p = job / p
        if not p.is_file():
            return refuse(f"no {'verdict' if a.verdict else 'summary'} file at {p}", 2)
        vsha = sha256(p.read_bytes()).hexdigest()
        ev = {"event": "evaluation", "batch": a.batch, "evaluator": a.evaluator,
              "verdict_file": relpath(job, p), "verdict_sha256": vsha, "at": t}
        if a.iteration is not None:
            ev["iteration"] = a.iteration
        if a.summary:
            sp = Path(a.summary)
            if not sp.is_absolute():
                sp = job / sp
            if not sp.is_file():
                return refuse(f"no summary file at {sp}", 2)
            try:
                s = json.loads(sp.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                return refuse(f"summary {sp} is not JSON ({exc})", 2)
            for k in ("started_at", "finished_at", "writer"):
                if not s.get(k):
                    return refuse(f"summary {sp} has no {k} stamp; an instrument summary must stamp itself", 3)
            ev.update({"summary_file": relpath(job, sp), "summary_sha256": sha256(sp.read_bytes()).hexdigest(),
                       "started_at": s["started_at"], "finished_at": s["finished_at"],
                       "summary_writer": s["writer"]})

    elif a.cmd == "amendment":
        p = Path(a.file)
        if not p.is_absolute():
            p = job / p
        if not p.is_file():
            return refuse(f"no amendment file at {p}", 2)
        custody_dir = (job / "custody").resolve()
        try:
            p.resolve().relative_to(custody_dir)
            return refuse(f"amendment file {p} is inside custody/; amendments go beside the frozen set", 3)
        except ValueError:
            pass
        said = H.parse_ts(a.said_at)
        if said is None:
            return refuse(f"--said-at {a.said_at!r} is not RFC 3339 UTC (...Z)", 2)
        frozen = H.parse_ts((ci.get("bar") or {}).get("frozenAt"))
        if frozen and said < frozen:
            return refuse(f"--said-at {a.said_at} is before the freeze at {ci['bar']['frozenAt']}", 3)
        if said > H.parse_ts(t):
            return refuse(f"--said-at {a.said_at} is after the tool's clock {t}", 3)
        ev = {"event": "amendment", "file": relpath(job, p), "file_sha256": sha256(p.read_bytes()).hexdigest(),
              "quote": a.quote, "channel": a.channel, "said_at": a.said_at, "at": t}

    elif a.cmd == "relay":
        said = H.parse_ts(a.source_at)
        if said is None:
            return refuse(f"--source-at {a.source_at!r} is not RFC 3339 UTC (...Z)", 2)
        frozen = H.parse_ts((ci.get("bar") or {}).get("frozenAt"))
        if frozen and said < frozen:
            return refuse(f"--source-at {a.source_at} is before the freeze at {ci['bar']['frozenAt']}", 3)
        if said > H.parse_ts(t):
            return refuse(f"--source-at {a.source_at} is after the tool's clock {t}", 3)
        ev = {"event": "relay", "kind": "relay", "quote": a.quote, "from": a.from_,
              "source_chat": a.source_chat, "source_at": a.source_at, "at": t}

    elif a.cmd == "spend":
        lp = Path(a.spend_ledger)
        if not lp.is_absolute():
            lp = job / lp
        rp = Path(a.key_reading)
        if not rp.is_absolute():
            rp = job / rp
        if not lp.is_file():
            return refuse(f"no spend ledger at {lp}", 2)
        if not rp.is_file():
            return refuse(f"no key reading at {rp}", 2)
        try:
            r = json.loads(rp.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            return refuse(f"key reading {rp} is not JSON ({exc})", 2)
        if not r.get("read_at") or not r.get("writer"):
            return refuse(f"key reading {rp} has no read_at/writer stamp; run tools/edi/or_call.py --spend-status", 3)
        read_at = H.parse_ts(r["read_at"])
        if read_at is None:
            return refuse(f"key reading read_at {r['read_at']!r} is not RFC 3339 UTC", 2)
        ledger_sum = 0.0
        last_settle = None
        try:
            for line in lp.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                x = json.loads(line)
                if x.get("event") == "settle":
                    ledger_sum += float(x.get("cost_usd") or 0)
                    d = H.parse_ts(x.get("at"))
                    if d and (last_settle is None or d > last_settle):
                        last_settle = d
        except (ValueError, OSError) as exc:
            return refuse(f"spend ledger {lp} is not JSON Lines ({exc})", 2)
        if last_settle and (read_at - last_settle).total_seconds() < 180:
            return refuse(f"key reading at {r['read_at']} is less than 3 min after the last settle at "
                          f"{H.iso(last_settle)}; read the key again later", 3)
        key_delta = float(r.get("key_delta_usd") or 0)
        total = max(ledger_sum, key_delta)
        ev = {"event": "spend", "spend_ledger": relpath(job, lp),
              "spend_ledger_sha256": sha256(lp.read_bytes()).hexdigest(),
              "key_reading": relpath(job, rp), "key_reading_sha256": sha256(rp.read_bytes()).hexdigest(),
              "ledger_sum_usd": ledger_sum, "key_delta_usd": key_delta, "total_usd": total,
              "read_at": r["read_at"], "last_settle_at": H.iso(last_settle) if last_settle else None, "at": t}

    else:
        return refuse(f"unknown command {a.cmd!r}", 2)

    ev["writer"] = writer_stamp()
    if ci_changed:
        write_custody(job, ci)
    append_event(job, ev)
    extra = ""
    if a.cmd == "approve":
        extra = f" ({ev.get('role')} by {ev.get('by')})"
    elif a.cmd == "pin":
        extra = f" ({a.seat} -> {a.provider} [{a.slug}] at {ev['host']} via {ev['via']})"
    print(f"logged {ev['event']} at {t}{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
