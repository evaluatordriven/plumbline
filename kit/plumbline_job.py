#!/usr/bin/env python3
"""The two commands a job has. `open` and `close` are the job's own lifecycle, and neither can be skipped.

WHY A WRAPPER RATHER THAN TWO TOOLS AND A HABIT. The emitters fixed the PRODUCTION of readable terms; they did
nothing about the fact that running them is a thing someone must remember to do. That is the same failure one
level up — and it is measurable: four consecutive jobs in a real deployment shipped terms no checker could
read, produced by authors who had already been told to produce machine-readable ones. A tool you must remember
is advice. This is the join: a job folder comes into existence BY the packet emitter, and it ends BY the record
emitter and the close. There is no third path, and no folder without a packet.

WHAT IT ENCODES, THAT INDIVIDUAL TOOLS CANNOT. The folder's own conventions: `packet.json` is the terms, the
`iteration-N-*` files are the records, `inputs/` holds the briefs and run files a reader must not judge as
terms, and `superseded/` holds what a job has replaced. Naming them in one place is what keeps a run file from
being held to the §5 record schema (measured: it was) and a replaced record from blocking a close (measured: it
did).

    plumbline_job.py open  --brief brief.json --job-dir dot-plumbline/jobs/<job-id> [--corpus PATH]
    plumbline_job.py close --job-dir dot-plumbline/jobs/<job-id> --run run.json [--run run2.json] [--corpus PATH]
                           [--terminal-state accepted|needs_owner|rejected [--outcome O]]
    plumbline_job.py custody --job-dir dot-plumbline/jobs/<job-id> [--out-dir DIR]    (no corpus needed)
    plumbline_job.py file --job-dir <ended job dir> [--into dot-plumbline/jobs] [--name NAME] [--backfill]

`open` creates the directory, emits the packet, and files the brief under `inputs/`. If the packet emitter
refuses the brief, THE DIRECTORY IS REMOVED: a job folder that exists without readable terms is the exact
artifact this kit was built to stop. `close` emits a §5 record for every run file, files the run files under
`inputs/`, then runs the close — and if any emitter refuses, nothing closes.

CUSTODY. A close that leaves the packet at a terminal state (accepted / needs_owner / rejected) also writes
`custody/record.custody.json` — a custody/v1 in-toto Statement (kit/emit_custody.py, docs/custody-emission.md)
— from the job's own files plus `inputs/custody.json`. It is written AFTER the close and changes none of the
close's artifacts. If it cannot be written whole, the close stands and the command says so and exits non-zero:
a job is closed by its §5 records; its custody record is a second, public reading of the same facts.
`custody` re-emits it on its own, with no corpus.

VERIFY. Close and custody run `kit/plumbline_verify.py` on the record the emitter just wrote. A verify failure
refuses the close: no `closed` row, a `close_refused` row carrying the failure kind, and the verifier's exit
code. The hand-time allowance is the emitter's switch; the verifier never takes a switch.
"""
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def log_row(job: Path, event: str, extra: dict, override: str | None = None) -> None:
    """Append a row naming this job, at open and at close.

    An audit that enumerates from the index reads a short body SILENTLY — measured by the corpus maintainer
    2026-10-05: 8 job folders on disk, 7 named in the log. A row written by the tool is a fact; a row written
    by a reconciliation someone must remember is a habit. Rows carry `event` so a reader can tell an open from
    a close; the older rows have no `event` and are runs.
    """
    from datetime import datetime, timezone
    path = Path(override).expanduser() if override else job.parent.parent / "run-log.json"
    # READ THE SHAPE THE LOG IS IN. The log is {"note": ..., "runs": [...]} — measured 2026-10-05, twice: my
    # loop check read the top level as rows and reported five folders unnamed that are named, and then this
    # function refused to write because it expected a list. A reader that does not know what it is reading
    # is the defect; both readers now read the log's own key, and refuse loudly if it is missing.
    try:
        doc = json.loads(path.read_text()) if path.is_file() else {"runs": []}
    except Exception as exc:
        print(f"  NOTE: {path} is unreadable ({exc}) — the run-log row was NOT written."); return
    if isinstance(doc, list):
        doc = {"runs": doc}
    if not isinstance(doc, dict) or not isinstance(doc.get("runs"), list):
        print(f"  NOTE: {path} is not recognisable as a run log (no list under `runs`) — the row was NOT "
              f"written. Fix the log first; a job nothing records is how a short body starts."); return
    doc["runs"].append({"job_id": job.name,
                        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "event": event, **extra})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2) + "\n")
        print(f"  run-log: appended the {event} row for {job.name} ({len(doc['runs'])} rows)")
    except OSError as exc:
        print(f"  NOTE: could not write the run-log row ({exc}). The job itself is unaffected, but an audit "
              f"reading the index will not see this job — say so rather than leaving it short.")


def corpus_arg(given: str | None) -> str | None:
    return given or os.environ.get("EDI_CORPUS") or None


def call(script: str, args: list[str]) -> int:
    """Run a sibling tool with this interpreter, streaming its report through unchanged."""
    return subprocess.run([sys.executable, str(HERE / script), *args]).returncode


def packet_mode(job: Path) -> str | None:
    try:
        return json.loads((job / "packet.json").read_text()).get("mode")
    except Exception:
        return None


def run_verifier(job: Path, a, record: Path | None = None) -> tuple[int, str]:
    """Run kit/plumbline_verify.py as its own subprocess; return (exit code, first failure kind)."""
    custody = (getattr(a, "custody", None) or os.environ.get("PLUMBLINE_CUSTODY") or "").strip()
    if not custody:
        print("NOT CLOSED: Plumbline verify cannot run: no --custody and no $PLUMBLINE_CUSTODY.")
        return 2, "cannot-run"
    rec = record or (job / "custody" / "record.custody.json")
    args = ["--record", str(rec),
            "--files", str(job / "custody" / "files"),
            "--evidence", str(job / "custody" / "evidence"),
            "--ledger", str(job / "inputs" / "custody-events.jsonl"),
            "--custody", custody]
    rv = subprocess.run([sys.executable, str(HERE / "plumbline_verify.py"), *args],
                        capture_output=True, text=True)
    sys.stdout.write(rv.stdout)
    sys.stderr.write(rv.stderr)
    kind = "verify"
    for line in rv.stdout.splitlines():
        if line.startswith("FAIL "):
            parts = line.split()
            if len(parts) >= 2:
                kind = parts[1]
            break
    return rv.returncode, kind


def drop_filed_rows(job: Path, override: str | None = None) -> None:
    """Remove this job's earlier `filed` rows before writing a new one.

    A re-filing is a correction, not a second event: measured 2026-11-09, re-filing seven jobs appended seven
    duplicate rows and the guard caught it as "job_id named more than once". A row about a folder should
    describe the folder as it stands; two rows describing one folder means a reader must pick.
    """
    path = Path(override).expanduser() if override else job.parent.parent / "run-log.json"
    try:
        doc = json.loads(path.read_text())
    except Exception:
        return
    if not isinstance(doc, dict) or not isinstance(doc.get("runs"), list):
        return
    before = len(doc["runs"])
    doc["runs"] = [r for r in doc["runs"]
                   if not (isinstance(r, dict) and r.get("job_id") == job.name and r.get("event") == "filed")]
    if len(doc["runs"]) != before:
        path.write_text(json.dumps(doc, indent=2) + "\n")


def write_status(job: Path, state: str, **extra) -> None:
    """Write `custody/status.json` — the folder's own statement about whether a record can exist yet.

    WHY A FILE AND NOT AN ABSENCE. Measured 2026-11-09: the Owner opened four filed job folders, found no
    custody record, and nothing inside the folder said whether that was a defect or a job that had not ended.
    An absence cannot tell "not yet" from "missing", and it is the folder a reader opens first — not the
    run-log. So the folder states its own status, and `not_a_record: true` keeps it from being read as one: the
    custody record is the corpus's artifact, and this is the instance's note about it.
    """
    import hashlib
    from datetime import datetime, timezone
    job = Path(job)          # a str here used to die on `job / "custody"` — measured 2026-11-09 from loop()'s
                              # finish path, where the record directory arrives as a string. Coerce, never guess.
    cdir = job / "custody"
    cdir.mkdir(parents=True, exist_ok=True)
    record = cdir / "record.custody.json"
    doc = {
        "schema": "plumbline-instance-custody-status-v1",
        "not_a_record": True,
        "job": job.name,
        "state": state,
        "record": "custody/record.custody.json",
        "record_present": record.is_file(),
        "record_sha256": hashlib.sha256(record.read_bytes()).hexdigest() if record.is_file() else None,
        "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "written_by": "kit/plumbline_job.py",
        **extra,
    }
    (cdir / "status.json").write_text(json.dumps(doc, indent=2) + "\n")


def do_open(a) -> int:
    job = Path(a.job_dir).expanduser()
    if (job / "packet.json").is_file():
        print(f"REFUSED: this job is already open — {job}/packet.json exists. A job opens once; a job that "
              f"needs new terms is a new job (a moved rubric is never a correction of an old one, C30).")
        return 1
    if not Path(a.brief).is_file():
        print(f"REFUSED: no brief at {a.brief} — the terms of a job are the one thing a tool must not invent.")
        return 2
    c = corpus_arg(a.corpus)
    if c is None:
        print("REFUSED: no corpus resolved. Set --corpus or $EDI_CORPUS."); return 2

    job.mkdir(parents=True, exist_ok=True)
    code = call("emit_packet.py", ["--brief", a.brief, "--out-dir", str(job), "--corpus", c])
    if code != 0:
        shutil.rmtree(job, ignore_errors=True)
        print(f"\nREFUSED AND UNDONE: the packet emitter refused the brief, so {job} was removed.")
        print("  A job folder that exists without readable terms is the artifact this kit exists to stop.")
        return code

    (job / "inputs").mkdir(exist_ok=True)
    dest = job / "inputs" / "brief.json"
    # A caller that prepared the brief INSIDE the job — which a re-emit does — makes source and destination the
    # same file, and shutil.copy raises SameFileError. Measured 2026-10-06, by running it.
    if Path(a.brief).expanduser().resolve() != dest.resolve():
        shutil.copy(a.brief, dest)
    log_row(job, "opened", {"mode": packet_mode(job), "artifact": json.loads((job / "packet.json").read_text()).get("artifact")},
            a.run_log)
    write_status(job, "open",
                 why="the job has no terminal_state until it closes, and a custody record exists only for an "
                     "ended job. This file says so inside the folder, so a reader does not have to infer it "
                     "from a missing record.")
    print(f"\njob open: {job}")
    print(f"  packet.json  the terms, readable by the gate")
    print(f"  inputs/      the brief (kept, and skipped by the close — an input is not a term)")
    print(f"\nclose it with:  plumbline_job.py close --job-dir {job} --run <run.json>")
    return 0


def do_close(a) -> int:
    job = Path(a.job_dir).expanduser()
    if not (job / "packet.json").is_file():
        print(f"REFUSED: {job} has no packet.json. An unopened job cannot be closed — close what open made.")
        return 2
    c = corpus_arg(a.corpus)
    if c is None:
        print("REFUSED: no corpus resolved. Set --corpus or $EDI_CORPUS."); return 2
    runs = [Path(r).expanduser() for r in a.run]
    if not runs:
        # A readings job files no §5 record — its record IS the reading — so --run is optional. But the
        # converse would be a hole: a SCORED job closing with no record at all. Measured by reading this
        # wrapper after writing it, which is the only way that hole was ever going to be found.
        packet = json.loads((job / "packet.json").read_text())
        if packet.get("mode") == "scored":
            print("REFUSED: this is a scored job and no --run was given. A scored job files at least one §5 "
                  "record; a close without one would make a missing reading look like a closed job.")
            return 2
        print("  no --run given: this job's packet is not `mode: scored`, so the close proceeds on the packet. "
              "The reading itself is the record.")
    missing = [str(r) for r in runs if not r.is_file()]
    if missing:
        print(f"REFUSED: run file(s) not found: {', '.join(missing)}"); return 2

    (job / "inputs").mkdir(exist_ok=True)
    for r in runs:
        code = call("emit_record.py", ["--run", str(r), "--out-dir", str(job), "--corpus", c])
        if code != 0:
            print(f"\nNOT CLOSED: the record emitter refused {r.name}. A close on a refused record would make "
                  f"the refusal invisible, which is the failure this wrapper exists to prevent.")
            return code
        shutil.copy(r, job / "inputs" / r.name)

    print("\nclose:")
    code = call("plumbline.py", ["--job-close", "--record-close", "--corpus", c, str(job)])
    # THE END-OF-JOB FACTS, written before the close so the close records them in one packet. Validated
    # against the corpus gate, and rolled back whole if the packet stops reading — a fact written into a
    # packet the law can no longer read is worse than the fact being absent.
    packet_path = job / "packet.json"
    before = packet_path.read_text()
    doc0 = json.loads(before)
    if a.disposition in ("given", "declined"):
        doc0["disposition"] = a.disposition if a.disposition == "declined" else (a.disposition_note or "given")
        doc0["disposition_state"] = a.disposition
    else:
        doc0["disposition_state"] = "not_yet_given"
    if a.terminal_state:                       # the job's end state, as the Orchestrator rules it — never inferred
        doc0["terminal_state"] = a.terminal_state
        if a.outcome:
            doc0["outcome"] = a.outcome
    extra = {}
    if a.billed_reroll:
        extra["billed_reroll"] = True
    if a.escalation_kind:
        extra["escalation_kind"] = a.escalation_kind
    if a.misalignment_iteration:
        extra["misalignment"] = {"found_at_iteration": a.misalignment_iteration,
                                 **({"spend_usd": a.misalignment_spend} if a.misalignment_spend is not None else {}),
                                 **({"note": a.misalignment_note} if a.misalignment_note else {})}
    if extra or True:
        doc0["close"] = {**(doc0.get("close") or {}), **extra}
    packet_path.write_text(json.dumps(doc0, indent=2) + "\n")
    gate = Path(c) / "tools" / "validate_job_packet.py"
    rv = subprocess.run([sys.executable, str(gate), str(packet_path)], capture_output=True, text=True)
    if rv.returncode != 0:
        packet_path.write_text(before)
        print("REFUSED: writing the end-of-job facts made the packet unreadable — nothing kept:")
        print("  " + (rv.stdout + rv.stderr).strip().replace("\n", "\n  ")[:300])
        return rv.returncode
    print(f"  packet: disposition_state={doc0['disposition_state']}"
          + (f" · billed_reroll={extra['billed_reroll']}" if extra.get("billed_reroll") else "")
          + (f" · misalignment at iteration {a.misalignment_iteration}" if extra.get("misalignment") else ""))

    if code == 0:
        doc = json.loads((job / "packet.json").read_text())
        # THE STATE, NEVER THE ABSENCE. An accepted artifact with no disposition is a COMPLETE record: the
        # Owner's act simply has not happened yet. A reader that stores null here later reads it as zero and
        # manufactures the non-conformance it reports (corpus maintainer, 2026-10-05).
        disp = doc.get("disposition")
        if isinstance(disp, dict):
            state = disp.get("state") or "given"
        elif disp in (None, {}, []):
            state = "not_yet_given"
        else:
            state = "given"
        if doc.get("terminal_state") in TERMINALS:
            print("\ncustody:")
            cargs = ["--job-dir", str(job)]
            if getattr(a, "allow_hand_times", False):
                cargs.append("--allow-hand-times")
            cc = call("emit_custody.py", cargs)
            if cc != 0:
                why = ("the refusals above name the fact the record would have misstated (fix its source: the harness "
                       "log, inputs/custody.json, inputs/custody-events.jsonl, or the emitter checkout)") if cc == 3 \
                    else "the gaps above name what inputs/custody.json must supply"
                print(f"\nCLOSED, BUT THE CUSTODY RECORD IS {'INCOMPLETE' if cc == 1 else 'NOT WRITTEN'}: {why}; "
                      f"re-emit with `plumbline_job.py custody`.")
                return cc
            vc, kind = run_verifier(job, a)
            if vc != 0:
                print(f"NOT CLOSED: Plumbline verify failed ({kind})")
                log_row(job, "close_refused", {"kind": kind, "exit": vc}, a.run_log)
                return vc
        log_row(job, "closed", {"mode": doc.get("mode"), "outcome": doc.get("outcome"),
                                "disposition_state": state}, a.run_log)
        terminal = doc.get("terminal_state")
        if (job / "custody" / "record.custody.json").is_file():
            write_status(job, "custody", terminal_state=terminal,
                         why="the job ended and its custody record was written; this file names it.")
        elif terminal in TERMINALS:
            write_status(job, "missing", terminal_state=terminal,
                         why="the job reached a terminal state but the record was NOT written — re-emit with "
                             "`plumbline_job.py custody`. This state is a defect, not a stage.")
        else:
            write_status(job, "open", terminal_state=terminal,
                         why="the close left the packet without a terminal state, so no custody record can "
                             "exist yet.")
        print(f"\njob closed: {job}")
        if doc.get("terminal_state") not in TERMINALS:
            print(f"  (no custody record: the packet's terminal_state is {doc.get('terminal_state')!r}, not terminal)")
    return code


TERMINALS = ("accepted", "needs_owner", "rejected")


def _is_finish(doc) -> bool:
    """True when the packet is a finish a loop() wrote, not a job and not a dispatch.

    A finish carries a terminal state — ``loop()`` writes it at the top level as
    ``terminal_state`` and again, in the record's own vocabulary, as ``terminalState`` —
    and usually the nested ``finish``/``summary`` the emitter reads. Such a folder is the
    EVIDENCE of a run whose packet names no ``job_id``, so it belongs under ``runs/``:
    under ``jobs/`` a folder without an id is a job no reader can name, and refusing it
    loses the only trace of a finish that ran in a scratch directory.

    The ``job_id`` test is first on purpose. A folder that DOES carry an id is a job
    whatever else it carries, and it is not this function's to reclassify.
    """
    if not isinstance(doc, dict) or doc.get("job_id"):
        return False
    for key in ("terminal_state", "terminalState"):
        value = doc.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return isinstance(doc.get("finish"), dict) or isinstance(doc.get("summary"), dict)


def do_file(a) -> int:
    """Copy an ended job — or a run's working directory — into `dot-plumbline/`, and record which it is.

    WHY THIS IS A COMMAND AND NOT A HABIT. `dot-plumbline/jobs/` held two jobs on 2026-11-09 while Jobs 3-25
    lived only in scratch record directories, because a commit that said "file closed jobs in dot-plumbline
    going forward" asked a person to remember. The repo's own record stopped growing, and a later census read
    the `examples/` fixtures instead — the same jobs twice — and reported a premise the repo could not support.

    WHY IT CLASSIFIES BEFORE IT COPIES. Measured 2026-11-09, on the first backfill: seven of ten folders filed
    under `jobs/` carried no custody record, and three of those were not jobs at all — their `packet.json` was a
    route-maker dispatch (`artifact`/`bounds`/`job`), not a job packet. A folder is a JOB only when its packet
    carries `job_id`; anything else is a RUN, and a run belongs in `runs/` where nothing will read it as a
    closed job with a missing record. Filing the two as one thing is how "no custody record" becomes a fact
    about the repo rather than a fact about the folder.
    """
    import hashlib
    src = Path(a.job_dir).expanduser().resolve()
    packet_src = src / "packet.json"
    if not packet_src.is_file():
        print(f"NOT FILED: {src} carries no packet.json. A folder without one is a probe or an aborted run — "
              f"filing it would put noise in the permanent record.")
        return 2
    try:
        doc = json.loads(packet_src.read_text())
    except Exception as exc:
        print(f"NOT FILED: {packet_src} is unreadable ({exc}). Terms nothing can read are not filed.")
        return 2
    if not isinstance(doc, dict):
        print(f"NOT FILED: {packet_src} is not an object; a job's terms are a packet, not a list.")
        return 2
    if doc.get("job_id"):
        kind = "job"
    elif {"artifact", "bounds", "job"} <= set(doc) or ("job" in doc and ("target" in doc or "maker_cmd" in doc)):
        kind = "run"
    elif _is_finish(doc):
        # A finish descriptor from loop() whose ratified packet carries no `job_id`. It is EVIDENCE of a run,
        # not a job. Filed under `jobs/` it would be the pair `test_jobs_carry_a_job_packet_and_runs_do_not`
        # refuses — measured 2026-11-12 (Job 38c), and again as Job 38d's `jobs/tmp3oudgzx8`. Filed under
        # `runs/` nothing reads it as a closed job, and the record of a finish that ran in a scratch directory
        # survives that directory (Owner ruling, 2026-11-12: an id-less finish must reach the instance record;
        # vanishing is not one of the honest readings). No id is minted here and the packet is not edited: the
        # folder keeps its own name, which is what filing a folder has always done.
        kind = "run"
    else:
        print(f"NOT FILED: {packet_src} is neither a job packet (no `job_id`) nor a dispatch packet "
              f"(`artifact`/`bounds`/`job`, or a brief with `job` + `target`), and it is not a finish either; "
              f"a folder nothing classifies cannot be filed without making a reader guess what it is.")
        return 2
    root = Path(a.into).expanduser().resolve() if a.into else (HERE.parent / "dot-plumbline").resolve()
    into = root / ("jobs" if kind == "job" else "runs")
    # THE NAME IS THE JOB'S, NEVER THE SCRATCH DIRECTORY'S. A finish runs in a temporary record directory —
    # `tmp3oudgzx8` and the like — and copying that basename into `jobs/` files a job under a name no reader
    # can use. Measured 2026-11-12 (Job 38d): one accepted finish over a packet with no `job_id` left
    # `jobs/tmp3oudgzx8` behind, and a packet that carried a real id still landed under the scratch name.
    # The caller that knows the job's identity passes it in (`--name`); a folder a person made, or one a
    # caller files with no name, keeps its own name, which is what filing has always done. The name must be
    # a single component: a `job_id` holding a path separator is refused rather than written outside `jobs/`.
    wanted = str(getattr(a, "name", None) or "").strip()
    name = wanted or src.name
    if name in ("", ".", "..") or name != os.path.basename(name) or os.sep in name:
        print(f"NOT FILED: {name!r} is not a single folder name, so there is no destination under "
              f"{'jobs' if kind == 'job' else 'runs'}/ that a reader could use. Writing it would either be "
              f"ambiguous or land outside the filing directory.")
        return 2
    dest = into / name
    if src == dest.resolve():
        print(f"NOT FILED: {src} is already the filed folder. A filing that copies onto itself destroys the "
              f"source; there is nothing to do.")
        return 2
    # The record state is decided from the folder, before anything is copied, and travels in the row.
    terminal = doc.get("terminal_state") if kind == "job" else None
    has_record = (src / "custody" / "record.custody.json").is_file()
    if kind == "run":
        record_state = "evidence"
    elif has_record:
        record_state = "custody"
    elif terminal:
        record_state = "missing"
    else:
        record_state = "open"
    if record_state == "missing" and not a.allow_incomplete:
        print(f"NOT FILED: {src} is a CLOSED job (terminal_state={terminal!r}) with no "
              f"custody/record.custody.json. A closed job without its record is the omission the Owner named; "
              f"pass --allow-incomplete to file it with `record_state: missing` written into the row, and the "
              f"reason recorded rather than implied.")
        return 1
    if dest.exists() and not a.force:
        print(f"NOT FILED: {dest} already exists. Re-filing over a record replaces the only copy of what was "
              f"filed; pass --force only when the source is known to be the same job, later.")
        return 1
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".aider*")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=ignore)
    if kind == "job":
        write_status(dest, "custody" if has_record else ("missing" if terminal else "open"),
                     terminal_state=terminal, filed_from=str(src),
                     why="state read from the filed folder itself at the moment of filing: a custody record is "
                         "present only when the job had ended and the emitter wrote one.")
    files = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    extra = {
        "kind": kind,
        "record_state": record_state,
        "kit_close": False,
        "source": str(src),
        "files": len(files),
        "packet_sha256": hashlib.sha256((dest / "packet.json").read_bytes()).hexdigest(),
    }
    if terminal:
        extra["terminal_state"] = terminal
    if a.backfill:
        extra["unfiled_backfill"] = True
    if kind == "job" and doc.get("job_id") and doc["job_id"] != dest.name:
        extra["packet_job_id"] = doc["job_id"]
    drop_filed_rows(dest, a.run_log)
    log_row(dest, "filed", extra, a.run_log)
    print(f"filed ({kind}/{record_state}): {dest}  ({len(files)} files, "
          f"packet sha256 {extra['packet_sha256'][:12]})")
    return 0




def do_custody(a) -> int:
    """Emit (or re-emit) the custody/v1 record for a job that has ended. Reads only the job's own files."""
    job = Path(a.job_dir).expanduser()
    args = ["--job-dir", a.job_dir]
    if a.out_dir:
        args += ["--out-dir", a.out_dir]
    if a.inputs:
        args += ["--inputs", a.inputs]
    if a.expect_revision:
        args += ["--expect-revision", a.expect_revision]
    if getattr(a, "allow_hand_times", False):
        args.append("--allow-hand-times")
    code = call("emit_custody.py", args)
    if code != 0:
        return code
    rec = None
    if a.out_dir:
        try:
            packet = json.loads((job / "packet.json").read_text())
            job_id = packet.get("job_id") or job.name
        except Exception:
            job_id = job.name
        rec = Path(a.out_dir).expanduser() / f"{job_id}.custody.json"
    vc, kind = run_verifier(job, a, rec)
    if vc != 0:
        print(f"NOT CLOSED: Plumbline verify failed ({kind})")
    return vc


def main() -> int:
    ap = argparse.ArgumentParser(description="A job's two commands: open and close. Neither is skippable.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open", help="create the job folder BY emitting its packet; nothing else creates one")
    o.add_argument("--brief", required=True)
    o.add_argument("--job-dir", required=True)
    o.add_argument("--corpus")
    o.add_argument("--run-log", help="override the run-log path (default: ../../run-log.json from the job dir)")
    c = sub.add_parser("close", help="emit a §5 record for every run, then close and record the close")
    c.add_argument("--job-dir", required=True)
    c.add_argument("--disposition", choices=["given", "declined"], help="the Owner's disposition, when there "
                   "is one. Absent means NOT YET GIVEN and is recorded as such — never as the absence of a "
                   "disposition, which a reader would otherwise count as zero")
    c.add_argument("--disposition-note", help="what the Owner did, in his words (the corpus field is free text)")
    c.add_argument("--billed-reroll", action="store_true", help="the Contracts' own fact: a regeneration was "
                   "tasked with a violation the Maker could not act on")
    c.add_argument("--escalation-kind", choices=["capability_gap", "cap_reached", "below_floor", "other"])
    c.add_argument("--misalignment-iteration", type=int, help="O2's fact: the iteration where the run diverged")
    c.add_argument("--misalignment-spend", type=float, help="the spend at that point, in USD")
    c.add_argument("--misalignment-note")
    c.add_argument("--run", action="append", default=[], help="the run file for one iteration (required when "
                                                             "the packet's mode is `scored`; a readings job "
                                                             "files no §5 record)")
    c.add_argument("--terminal-state", choices=list(TERMINALS), help="the job's end state; when given (or "
                   "already in the packet) the close also writes the custody/v1 record")
    c.add_argument("--outcome", help="the packet outcome to record with --terminal-state (corpus vocabulary)")
    c.add_argument("--allow-hand-times", action="store_true",
                   help="pass the hand-time allowance to the emitter; the verifier still enforces the flags")
    c.add_argument("--custody", help="the custody checker checkout (default: $PLUMBLINE_CUSTODY)")
    c.add_argument("--corpus")
    c.add_argument("--run-log", help="override the run-log path (default: ../../run-log.json from the job dir)")
    k = sub.add_parser("custody", help="write the custody/v1 record of an ended job (no corpus needed)")
    k.add_argument("--job-dir", required=True)
    k.add_argument("--out-dir", help="write <out-dir>/<job_id>.custody.json instead of <job>/custody/")
    k.add_argument("--inputs", help="custody inputs (default: <job>/inputs/custody.json)")
    k.add_argument("--expect-revision", help="the emitter revision (commit or tree) the record must be written by")
    k.add_argument("--allow-hand-times", action="store_true",
                   help="pass the hand-time allowance to the emitter; the verifier still enforces the flags")
    k.add_argument("--custody", help="the custody checker checkout (default: $PLUMBLINE_CUSTODY)")
    f = sub.add_parser("file", help="copy an ended job into dot-plumbline/jobs/ and record the filing")
    f.add_argument("--job-dir", required=True, help="the ended job's folder (must carry packet.json)")
    f.add_argument("--into", help="the dot-plumbline directory (default: <repo>/dot-plumbline); the kit picks "
                   "`jobs/` for a job packet and `runs/` for a dispatch packet")
    f.add_argument("--name", help="the folder to file as (default: the source directory's name). loop() passes "
                   "the packet's own job_id here, so a finish is filed under its id and never under the "
                   "temporary record directory it ran in")
    f.add_argument("--run-log", help="override the run-log path (default: <into>/run-log.json)")
    f.add_argument("--backfill", action="store_true",
                   help="mark the row `unfiled_backfill: true` — for a job that ended before filing was a command")
    f.add_argument("--allow-incomplete", action="store_true",
                   help="file a CLOSED job that carries no custody record, with `record_state: missing` in the "
                        "row. The omission is then recorded rather than implied")
    f.add_argument("--force", action="store_true",
                   help="replace an existing filed folder; only when the source is known to be the same job, later")
    a = ap.parse_args()
    return {"open": do_open, "close": do_close, "custody": do_custody, "file": do_file}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
