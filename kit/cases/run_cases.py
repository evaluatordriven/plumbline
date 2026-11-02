#!/usr/bin/env python3
"""Every check this kit wraps must be shown FAILING before anyone trusts a pass.

Two controls, because the law is mode-dependent: a READINGS packet (this kit job's own, no bar,
no bounds) and a SCORED packet (the discoverability-gate job, which carries a specialist and
bounds). A mutation is only a defect *for the mode it is applied to*, and the first draft of this
file got that wrong twice — it mutated a readings packet in ways readings tolerate and called the
result a miss. The control is what caught it, which is why the control is a case and not a
formality.

    readings control     the kit job packet            -> must pass
    scored control       the gate job packet            -> must pass
    readings + bounds    branch 0: no bar, so no bounds -> must fail
    scored + escalation ""                            -> must fail (the case recorded 2026-09-30:
                                                          the schema is loose, the gate is not)
    scored + evaluator "Owner"                        -> must fail (0028 A)
    either + terminal_state accepted while ratified:false -> must fail (branch 1)
    identity equality    maker and evaluator the same string -> must fail (rule 2 / I14)
    a markdown packet                                 -> NOT-CHECKABLE, and must not read as OK
    a channel output                                  -> NOT-CHECKABLE, named as a channel artifact,
                                                         and must NOT be reported as a failed record
    job-close                                         -> exit 3 on unreadable terms or a failed record,
                                                         exit 0 when the packet is readable and clean
CORPUS-OWNED FIXTURES (v1.20.0): the kit inherits the corpus's pass checks by wrapping its validator, so the
corpus's own red fixtures must fail through the kit for the corpus's own named reasons — and its passing
example must still pass. If the kit ever stops inheriting, these three cases say so.
"""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
READINGS = KIT.parent / "tests" / "fixtures" / "cases" / "readings-control.json"
SCORED = KIT.parent / "tests" / "fixtures" / "cases" / "scored-control.json"
# The corpus: the first argument, else $EDI_CORPUS (tools/edi_corpus.py, the shared D-E resolver). A set value that is
# not a corpus exits 2 naming it. With none, the cases do not run: corpus.run-cases prints SKIP[corpus] and exits 0,
# or FAIL[corpus] and exits 1 under PLUMBLINE_REQUIRE_CORPUS=1.
sys.path.insert(0, str(KIT.parent / "tools"))
import edi_corpus  # noqa: E402

CHECK_ID = "corpus.run-cases"
CORPUS = sys.argv[1] if len(sys.argv) > 1 else None
PACKET_BRIEF = {
    "job_name": "kit-emitter-case", "entry": "A", "instrument_profile": "full",
    "artifact": "a conformant artifact", "buyer": "the Buyer", "maker": "maker-profile",
    "evaluator": "eval-profile", "ratified": True, "mode": "scored",
    "human_seat": "the Owner", "standard_ref": "the standard in force", "specialist": "a specialist",
    "bounds": {"T_accept": 9.5, "T_dim": 9.0, "T_reject": 7.0, "cap": 4, "budget": "5 USD"},
    "k": 3, "x": 10,   # B.1.2's bounds, declared per job — required of every scored brief
    "ground_truth": [{"ref": "GT", "version": "v1", "hardness": "DOCUMENT", "source": "frozen before the job"}],
    "mandate_ref": {"doc": "EDI-MANDATE.md", "version": "short"}, "escalation": "the Owner, on cap-exhaust",
}
EMITTER_RUN = {
    "job_id": "kit-emitter-case", "iteration": 1, "artifact": "iteration-1-artifact.md", "ratified": True,
    "channel_blind": True, "evaluator_identity": "openai/gpt-5.6-terra",
    "instrument": {"version": "v", "rubric_sha256": "a" * 64, "code_sha256": "b" * 64},
    "pass_rule": {"accept": 9.5, "dimension_floor": 9.0, "reject": 7.0, "cap": 4},
    "ground_truth": {"ref": "EA-PRINCIPLES.yaml", "version": "v1.1", "hardness": "DOCUMENT"},
    "mandate_ref": {"doc": "EDI-MANDATE.md", "version": "short-2026-09-24"},
    "dimensions": [{"name": "D1", "score": 10.0, "scale": "1-10", "anchor_note": "a",
                    "observation": "observed", "observation_channel": "engine", "ground_truth_access": "blind_to_gt"}],
    "violations": [], "verdict": "accept",
    "passes": [{"pass_id": "p1", "kind": "scored", "status": "filed", "channel": "deterministic engine",
                "run_ref": "sess-1", "scores": [{"dimension": "D1", "score": 10.0}]}],
    "instance_extensions": [{"name": "x", "label": "instance-specific", "value": "y"}],
}


def invoke(work: Path, *flags: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(KIT / "plumbline.py"), *flags, "--corpus", CORPUS, str(work)],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def fixture_case(name: str, files: dict, flags: tuple, want: tuple[int, str]) -> bool:
    """A job directory built from literal fixtures, so a shape can be planted rather than described."""
    work = Path(tempfile.mkdtemp()) / "job"
    work.mkdir(parents=True)
    for rel, content in files.items():
        p = work / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content if isinstance(content, str) else json.dumps(content, indent=2))
    code, out = invoke(work, *flags)
    shutil.rmtree(work.parent, ignore_errors=True)
    hit = (code == want[0]) and (want[1] in out)
    print(f"  {'PASS' if hit else 'MISS'}  {name:56s} -> exit {code} (wanted {want[0]}, {want[1]!r})")
    return hit


def case(name: str, base: Path | None, fn, want: tuple[int, str]) -> bool:
    work = Path(tempfile.mkdtemp()) / "job"
    work.mkdir(parents=True)
    if base is None:                                  # the markdown case
        (work / "packet.md").write_text("# Job Packet\n\nprose, not a shape\n")
    else:
        d = json.loads(base.read_text())
        fn(d)
        (work / "packet.json").write_text(json.dumps(d, indent=2))
    code, out = invoke(work)
    shutil.rmtree(work.parent, ignore_errors=True)
    hit = (code == want[0]) and (want[1] in out)
    print(f"  {'PASS' if hit else 'MISS'}  {name:56s} -> {'OK' if code == 0 else 'FAILED':6s} (wanted exit {want[0]}, {want[1]!r})")
    return hit


def corpus_case(name: str, rel: str, want: tuple[int, str]) -> bool:
    """A fixture the CORPUS owns, run through the kit. If the kit ever stops inheriting the corpus's checks,
    these fail — which is the point: the inheritance is the kit's whole design, and it is now asserted."""
    r = subprocess.run([sys.executable, str(KIT / "plumbline.py"), "--corpus", CORPUS,
                        str(Path(CORPUS) / rel)], capture_output=True, text=True)
    hit = (r.returncode == want[0]) and (want[1] in (r.stdout + r.stderr))
    print(f"  {'PASS' if hit else 'MISS'}  {name:56s} -> exit {r.returncode} (wanted {want[0]}, {want[1]!r})")
    return hit


def emitter_case(name: str, mutate, want: tuple[int, str]) -> bool:
    """The emitter must refuse illegal input AND emit records the corpus accepts. Both directions, or the
    emitter is a formatter nobody should trust."""
    run = json.loads(json.dumps(EMITTER_RUN))
    mutate(run)
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        (work / "iteration-1-artifact.md").write_text("# stand-in artifact\n")
        (work / "run.json").write_text(json.dumps(run, indent=2))
        r = subprocess.run([sys.executable, str(KIT / "emit_record.py"), "--run", str(work / "run.json"),
                            "--out-dir", str(work), "--corpus", CORPUS], capture_output=True, text=True)
    hit = (r.returncode == want[0]) and (want[1] in (r.stdout + r.stderr))
    print(f"  {'PASS' if hit else 'MISS'}  {name:56s} -> exit {r.returncode} (wanted {want[0]}, {want[1]!r})")
    return hit


def packet_control() -> bool:
    """CONTROL for the packet emitter: a clean brief must produce a packet the corpus gate accepts."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        w = Path(td); (w / "brief.json").write_text(json.dumps(PACKET_BRIEF, indent=2))
        r = subprocess.run([sys.executable, str(KIT / "emit_packet.py"), "--brief", str(w / "brief.json"),
                            "--out-dir", str(w), "--corpus", CORPUS], capture_output=True, text=True)
        hit = r.returncode == 0 and "OK (schema-verified)" in (r.stdout + r.stderr) and (w / "packet.json").is_file()
    print(f"  {'PASS' if hit else 'MISS'}  CONTROL: a clean brief emits a packet the gate accepts")
    return hit


def kind_cases() -> list[bool]:
    """evaluator.kind (Contracts §4, v1.26.0): a string evaluator emits with a NOTE; an object with a kind passes
    through unchanged and without the NOTE; a kind outside person/model/script is REFUSED by the corpus gate."""
    import tempfile
    out = []
    for label, ev, want_rc, want_note, want_kind in (
        ("a string evaluator emits, with the evaluator.kind NOTE", "eval-profile", 0, True, None),
        ("an evaluator with kind script passes through, no NOTE", {"name": "eval-profile", "kind": "script"}, 0, False, "script"),
        ("an evaluator with kind robot is refused by the corpus gate", {"name": "eval-profile", "kind": "robot"}, 1, None, None),
    ):
        with tempfile.TemporaryDirectory() as td:
            w = Path(td); brief = json.loads(json.dumps(PACKET_BRIEF)); brief["evaluator"] = ev
            (w / "brief.json").write_text(json.dumps(brief, indent=2))
            r = subprocess.run([sys.executable, str(KIT / "emit_packet.py"), "--brief", str(w / "brief.json"),
                                "--out-dir", str(w), "--corpus", CORPUS], capture_output=True, text=True)
            text = r.stdout + r.stderr
            hit = (r.returncode == 0) == (want_rc == 0)
            if want_note is not None:
                hit = hit and (("NOTE evaluator.kind" in text) == want_note)
            if want_kind:
                pk = w / "packet.json"
                hit = hit and pk.is_file() and json.loads(pk.read_text()).get("evaluator", {}).get("kind") == want_kind
        print(f"  {'PASS' if hit else 'MISS'}  {label}  -> exit {r.returncode}")
        out.append(hit)
    return out


def population_case() -> bool:
    """THE CONTROL, held by case. The corpus struck the clause and kept the practice ("an enumeration carries
    a control in the same batch"), and their changelog records MY zero-file short body as the evidence. Practice
    that is not tested is the same advice the clause was."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = Path(td); job = td / "jobs" / "pop"
        brief = json.loads(json.dumps(PACKET_BRIEF)); brief["job_name"] = "pop"
        (td / "brief.json").write_text(json.dumps(brief, indent=2))
        o = subprocess.run([sys.executable, str(KIT / "plumbline_job.py"), "open", "--brief", str(td / "brief.json"),
                            "--job-dir", str(job), "--corpus", CORPUS], capture_output=True, text=True)
        (job / "iteration-1-artifact.md").write_text("# artifact\n\nobserved\n")
        run = json.loads(json.dumps(EMITTER_RUN)); run["job_id"] = "pop"
        (td / "run.json").write_text(json.dumps(run, indent=2))
        cl = subprocess.run([sys.executable, str(KIT / "plumbline_job.py"), "close", "--job-dir", str(job),
                             "--run", str(td / "run.json"), "--corpus", CORPUS], capture_output=True, text=True)
        r1 = subprocess.run([sys.executable, str(KIT / "plumbline.py"), "--job-close", "--corpus", CORPUS, str(job)],
                            capture_output=True, text=True)
        states_population = "POPULATION" in r1.stdout
        closes = r1.returncode == 0
        (job / "iteration-1-artifact.md").unlink()
        r2 = subprocess.run([sys.executable, str(KIT / "plumbline.py"), "--job-close", "--corpus", CORPUS, str(job)],
                            capture_output=True, text=True)
        refuses = r2.returncode == 3 and "not beside it" in (r2.stdout + r2.stderr)
        if not (states_population and closes):
            print("        why — open:", o.returncode, "close:", cl.returncode)
            for _l in (cl.stdout + cl.stderr).strip().splitlines()[-4:]:
                print("        close | " + _l.strip()[:120])
            for _l in (r1.stdout + r1.stderr).strip().splitlines()[-4:]:
                print("        jc    | " + _l.strip()[:120])
        print(f"  {'PASS' if states_population and closes else 'MISS'}  the reader states its population")
        print(f"  {'PASS' if refuses else 'MISS'}  a record whose artifact is missing does NOT close")
    return states_population and closes and refuses


def ask2_case() -> bool:
    """Ask 2's fields: a bound-less scored brief is refused, and the end-of-job facts WRITE — a field with no
    writer is how four quantities went blank in the first place."""
    import tempfile
    ok = True
    # (a) the emitter refuses a scored brief with no k/x — B.1.2 declares both per job
    brief = json.loads(json.dumps(PACKET_BRIEF)); brief.pop("k"); brief.pop("x")
    with tempfile.TemporaryDirectory() as td:
        w = Path(td); (w / "brief.json").write_text(json.dumps(brief, indent=2))
        r = subprocess.run([sys.executable, str(KIT / "emit_packet.py"), "--brief", str(w / "brief.json"),
                            "--out-dir", str(w), "--corpus", CORPUS], capture_output=True, text=True)
    hit = r.returncode == 1 and "B.1.2" in (r.stdout + r.stderr)
    print(f"  {'PASS' if hit else 'MISS'}  a scored brief with no k/x is refused (B.1.2 declares both per job)")
    ok = ok and hit

    # (b) the end-of-job facts actually land in the packet — through the REAL path, because a scored job
    # refuses to close without a record and my first version of this case forgot that.
    with tempfile.TemporaryDirectory() as td:
        w = Path(td); job = w / "jobs" / "ask2"
        (w / "brief.json").write_text(json.dumps(PACKET_BRIEF, indent=2))
        subprocess.run([sys.executable, str(KIT / "plumbline_job.py"), "open", "--brief", str(w / "brief.json"),
                        "--job-dir", str(job), "--corpus", CORPUS], capture_output=True, text=True)
        (job / "iteration-1-artifact.md").write_text("# artifact\n\nobserved\n")
        run = json.loads(json.dumps(EMITTER_RUN)); run["artifact"] = "iteration-1-artifact.md"
        (w / "run.json").write_text(json.dumps(run, indent=2))
        r = subprocess.run([sys.executable, str(KIT / "plumbline_job.py"), "close", "--job-dir", str(job),
                            "--corpus", CORPUS, "--run", str(w / "run.json"),
                            "--disposition", "given", "--disposition-note", "shipped",
                            "--billed-reroll", "--misalignment-iteration", "2", "--misalignment-spend", "1.25"],
                           capture_output=True, text=True)
        doc = json.loads((job / "packet.json").read_text())
        close = doc.get("close") or {}
        wrote = (r.returncode == 0 and doc.get("disposition_state") == "given" and doc.get("disposition") == "shipped"
                 and close.get("billed_reroll") is True
                 and (close.get("misalignment") or {}).get("found_at_iteration") == 2
                 and (close.get("misalignment") or {}).get("spend_usd") == 1.25)
        notgiven = None
        if wrote:
            subprocess.run([sys.executable, str(KIT / "plumbline_job.py"), "close", "--job-dir", str(job),
                            "--corpus", CORPUS, "--run", str(w / "run.json")], capture_output=True, text=True)
            notgiven = json.loads((job / "packet.json").read_text()).get("disposition_state")
        print(f"  {'PASS' if wrote else 'MISS'}  the close writes disposition (given), billed_reroll and the misalignment fact")
        print(f"  {'PASS' if notgiven == 'not_yet_given' else 'MISS'}  ...and a close with no disposition records "
              f"NOT YET GIVEN, never the absence of one (got {notgiven!r})")
        ok = ok and wrote and notgiven == "not_yet_given"
    return ok


def c36_case() -> bool:
    """C36's two new red fixtures must fail through the kit's own path, permanently."""
    ok = True
    for name, needle in (("bad-evaluator-record-regenerate-without-violation", "regenerate"),
                         ("bad-evaluator-record-below-floor-unnamed", "below")):
        fx = Path(CORPUS) / f"schemas/fixtures/{name}.json"
        if not fx.is_file():
            print(f"  MISS  the corpus's {name} fixture is absent"); ok = False; continue
        r = subprocess.run([sys.executable, str(KIT / "plumbline.py"), "--corpus", CORPUS, str(fx)],
                           capture_output=True, text=True)
        hit = r.returncode == 1 and "FAILED" in (r.stdout + r.stderr)
        print(f"  {'PASS' if hit else 'MISS'}  C36 fixture {name[:44]:44s} fails through the kit")
        ok = ok and hit
    return ok


def c35_case() -> bool:
    """C35's inheritance must be PERMANENT, not a one-time observation. The corpus shipped a red fixture with
    the rule; the kit gets it failing through its own path, so a future kit edit that stops inheriting it
    breaks a case rather than quietly becoming a second ruler."""
    fx = Path(CORPUS) / "schemas/fixtures/bad-evaluator-record-unattributable-pass.json"
    if not fx.is_file():
        print("  MISS  the corpus's C35 fixture is absent — the inheritance cannot be proven")
        return False
    r = subprocess.run([sys.executable, str(KIT / "plumbline.py"), "--corpus", CORPUS, str(fx)],
                       capture_output=True, text=True)
    out = r.stdout + r.stderr
    hit = (r.returncode == 1 and "FAILED" in out
           and ("not attributable" in out or "zero" in out))
    print(f"  {'PASS' if hit else 'MISS'}  C35's red fixture fails through the kit (zero is not one)")
    return hit


def wrapper_case() -> bool:
    """Two commands make a job that closes — and a refused brief leaves NO directory behind, because a job
    folder that exists without readable terms is the artifact this kit was built to stop."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "brief.json").write_text(json.dumps(PACKET_BRIEF, indent=2))
        bad = json.loads(json.dumps(PACKET_BRIEF)); bad.pop("buyer")
        (td / "bad.json").write_text(json.dumps(bad, indent=2))
        ghost = td / "jobs" / "ghost"
        r0 = subprocess.run([sys.executable, str(KIT / "plumbline_job.py"), "open", "--brief", str(td / "bad.json"),
                             "--job-dir", str(ghost), "--corpus", CORPUS], capture_output=True, text=True)
        no_dir = r0.returncode != 0 and not ghost.exists()

        job = td / "jobs" / "job-1"
        r1 = subprocess.run([sys.executable, str(KIT / "plumbline_job.py"), "open", "--brief", str(td / "brief.json"),
                             "--job-dir", str(job), "--corpus", CORPUS], capture_output=True, text=True)
        (job / "iteration-1-artifact.md").write_text("# artifact\n\nobserved\n")
        run = json.loads(json.dumps(EMITTER_RUN)); run["artifact"] = "iteration-1-artifact.md"
        (td / "run.json").write_text(json.dumps(run, indent=2))
        r2 = subprocess.run([sys.executable, str(KIT / "plumbline_job.py"), "close", "--job-dir", str(job),
                             "--run", str(td / "run.json"), "--corpus", CORPUS], capture_output=True, text=True)
        packed = json.loads((job / "packet.json").read_text()) if (job / "packet.json").is_file() else {}
        closes = r1.returncode == 0 and r2.returncode == 0 and packed.get("close", {}).get("verdict") == "CLOSEABLE"
        print(f"  {'PASS' if no_dir else 'MISS'}  a refused brief leaves NO job directory behind")
        print(f"  {'PASS' if closes else 'MISS'}  open then close produces a job that closes, with the close in the packet")
    return no_dir and closes


def close_record_case() -> bool:
    """A close that skipped files must say so WHERE A LATER READER WILL FIND IT, not only on stdout — and a
    close record asserts a close, so a job that did not close gets nothing written."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        job = Path(td) / "job"; job.mkdir()
        (job / "brief.json").write_text(json.dumps(PACKET_BRIEF, indent=2))     # emit a lawful packet first
        subprocess.run([sys.executable, str(KIT / "emit_packet.py"), "--brief", str(job / "brief.json"),
                        "--out-dir", str(job), "--corpus", CORPUS], capture_output=True, text=True)
        (job / "brief.json").unlink()
        (job / "superseded").mkdir(); (job / "superseded/old-record.json").write_text('{"x": 1}')
        r = subprocess.run([sys.executable, str(KIT / "plumbline.py"), "--job-close", "--record-close",
                            "--corpus", CORPUS, str(job)], capture_output=True, text=True)
        packed = json.loads((job / "packet.json").read_text()).get("close") if (job / "packet.json").is_file() else None
        records = bool(packed and packed.get("skipped", {}).get("superseded") == 1
                       and "superseded/old-record.json" in packed.get("skipped_files", {}).get("superseded", [])
                       and packed.get("kit_revision") and packed.get("counts"))
        print(f"  {'PASS' if records and r.returncode == 0 else 'MISS'}  a close records its verdict, counts and "
              f"EVERY skipped file into the packet")

        # ...and it must not record a close that did not happen
        bad = Path(td) / "bad"; bad.mkdir(); (bad / "packet.md").write_text("# prose terms")
        r2 = subprocess.run([sys.executable, str(KIT / "plumbline.py"), "--job-close", "--record-close",
                             "--corpus", CORPUS, str(bad)], capture_output=True, text=True)
        clean = r2.returncode == 3 and not (bad / "packet.json").exists() and "did not close" in (r2.stdout + r2.stderr)
        print(f"  {'PASS' if clean else 'MISS'}  a job that did not close gets NO close record written")

        # ...and without the flag the kit stays a reader
        r3 = subprocess.run([sys.executable, str(KIT / "plumbline.py"), "--job-close",
                             "--corpus", CORPUS, str(job)], capture_output=True, text=True)
        inert = r3.returncode == 0 and "note:" in (r3.stdout + r3.stderr)
    hit = records and clean and inert
    return hit


def skip_case() -> bool:
    """`superseded/` is skipped BY NAME and COUNTED: a replaced record must not block a close, and a skip
    nobody can see would be a hiding place — moving a failing record there must not be a way to close."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        job = Path(td) / "job"; (job / "superseded").mkdir(parents=True)
        (job / "superseded/iteration-1-eval-record.json").write_text(json.dumps(
            {"job_id": "x", "dimensions": [], "passes": [], "verdict": "accept"}))
        r = subprocess.run([sys.executable, str(KIT / "plumbline.py"), "--job-close", "--corpus", CORPUS, str(job)],
                           capture_output=True, text=True)
        out = r.stdout + r.stderr
        named = "SKIPPED" in out and "superseded/" in out
        not_blocking = "superseded/iteration-1-eval-record.json" not in "\n".join(
            l for l in out.splitlines() if "FAILED" in l)
    hit = named and not_blocking and r.returncode == 3      # still refuses: there is no packet.json
    print(f"  {'PASS' if hit else 'MISS'}  a replaced record in superseded/ is skipped, named, and not a blocker")
    return hit


def packet_case(name: str, mutate, want: tuple[int, str]) -> bool:
    """The PACKET emitter: refuse illegal terms, and emit a packet the gate accepts. Both directions."""
    brief = json.loads(json.dumps(PACKET_BRIEF))
    mutate(brief)
    with tempfile.TemporaryDirectory() as td:
        w = Path(td)
        (w / "brief.json").write_text(json.dumps(brief, indent=2))
        r = subprocess.run([sys.executable, str(KIT / "emit_packet.py"), "--brief", str(w / "brief.json"),
                            "--out-dir", str(w), "--corpus", CORPUS], capture_output=True, text=True)
    hit = (r.returncode == want[0]) and (want[1] in (r.stdout + r.stderr))
    print(f"  {'PASS' if hit else 'MISS'}  {name:56s} -> exit {r.returncode} (wanted {want[0]}, {want[1]!r})")
    return hit


def missing_path_case() -> bool:
    """A path that does not exist is an IO error (exit 2), not an "unclassified" verdict.

    Found by the second machine on first contact: it passed a relative path that did not resolve,
    and the kit answered "unclassified" — a label that hides the real cause and reads like a
    finding about the artifact."""
    r = subprocess.run([sys.executable, str(KIT / "plumbline.py"), "--corpus", CORPUS,
                        "no/such/path/at/all"],
                       capture_output=True, text=True)
    hit = (r.returncode == 2) and ("no such path" in (r.stdout + r.stderr))
    print(f"  {'PASS' if hit else 'MISS'}  {'a missing path is an IO error, not a verdict':56s} -> "
          f"exit {r.returncode} (wanted 2, 'no such path')")
    return hit


def main() -> int:
    global CORPUS
    resolved, required = edi_corpus.resolve_or_exit(CORPUS, ("tools/validate_job_packet.py",), hermes=False)
    if resolved is None:
        failed = edi_corpus.not_run(CHECK_ID, required, edi_corpus.NO_CORPUS_ENV)
        print("usage: run_cases.py [<corpus-path>]   (default: $EDI_CORPUS)")
        return 1 if failed else 0
    CORPUS = str(resolved.path)
    print(f"planted defects — two controls, six mutations, and the job-close gate (corpus: {CORPUS})")
    r = [case("CONTROL (readings): the kit job packet must pass", READINGS, lambda d: None, (0, "0 failed")),
         case("CONTROL (scored): the gate job packet must pass", SCORED, lambda d: None, (0, "0 failed")),
         case("readings packet + bounds (branch 0)", READINGS,
              lambda d: d.update({"bounds": {"T_accept": 9, "T_dim": 6, "T_reject": 2, "cap": 1}}),
              (1, "FAILED")),
         case('scored packet + escalation ""', SCORED, lambda d: d.update({"escalation": ""}), (1, "FAILED")),
         case('scored packet + evaluator "Owner"', SCORED, lambda d: d.update({"evaluator": "Owner"}), (1, "FAILED")),
         case("ratified:false reaching accepted", READINGS,
              lambda d: d.update({"ratified": False, "terminal_state": "accepted", "outcome": "accepted"}),
              (1, "FAILED")),
         case("Maker identity = Evaluator identity", READINGS,
              lambda d: d.update({"maker": "same-party", "evaluator": "same-party"}), (1, "FAILED")),
         # exit 1, not 0: a job whose only artifact is a markdown packet has nothing checkable in it,
         # and the kit's own rule (README, and the summary line it prints) is that not-checkable is not
         # a pass. This case originally asserted exit 0 — it encoded the old, inconsistent behaviour.
         case("a markdown packet is not-checkable, not fine", None, None, (1, "NOT-CHECKABLE")),
         # ---- the 2026-10-05 findings, both planted ----
         # A CHANNEL OUTPUT is not a §5 record. Routing on the word "dimensions" alone reported it as a
         # FAILED record, which is a false positive in a checker whose whole value is that its FAILED
         # means something. It must be named as a channel output AND must not block a close.
         fixture_case("a channel output is named as one, not failed as a record",
                      {"packet.json": json.loads(READINGS.read_text()),
                       "channel-out.json": {"iteration": 1, "pass": 1, "channel": "deterministic",
                                            "dimensions": {"D1": {"score": 10.0, "name": "x"}}}},
                      (), (0, "channel output")),
         # The trigger that was missing: a job may not close on terms nothing can read. The check for
         # markdown packets existed since the second machine ran it; nothing ran it at job close, which
         # is why four jobs opened after that review shipped unreadable terms anyway.
         fixture_case("job-close CONTROL: a readable packet with clean rows is closeable",
                      {"packet.json": json.loads(READINGS.read_text())}, ("--job-close",), (0, "CLOSEABLE")),
         fixture_case("job-close: packet.md alone is NOT closeable",
                      {"packet.md": "# Job Packet\n\nprose, not a shape\n"},
                      ("--job-close",), (3, "NOT CLOSEABLE")),
         fixture_case("job-close: a failing §5-shaped record blocks the close",
                      {"packet.json": json.loads(READINGS.read_text()),
                       "iteration-1-eval-record.json": {"dimensions": [], "pass_rule": "mean>=9.5 AND min>=9.0",
                                                        "violations": [], "verdict": "accept",
                                                        "instrument_in_force": "sha", "ratified": True}},
                      ("--job-close",), (3, "NOT CLOSEABLE")),
         # ---- v1.20.0 (proposal 0050 as amended): the pass checks the kit inherits by wrapping ----
         corpus_case("CONTROL: the corpus's passing record example passes through the kit",
                     "schemas/fixtures/evaluator-record-example.json", (0, "0 failed")),
         corpus_case("a record naming an unfiled pass fails — evidence not filed",
                     "schemas/fixtures/bad-evaluator-record-unfiled-pass.json", (1, "not filed")),
         corpus_case("a pass whose kind disagrees with its filed pass fails",
                     "schemas/fixtures/bad-evaluator-record-pass-disagreement.json", (1, "disagrees")),
         # ---- the emitter (kit/emit_record.py): refuses illegal input, emits what the corpus accepts ----
         emitter_case("the emitter refuses a violation class rule 4 does not have",
                      lambda r: r["violations"].append({"id": "V1", "class": "coherence", "observation": "x"}),
                      (1, "not one of rule 4")),
         emitter_case("the emitter refuses a void pass carrying scores",
                      lambda r: r["passes"][0].update({"status": "void", "void_cause": "no reading",
                                                       "scores": [{"dimension": "D1", "score": 1}]}),
                      (1, "may not carry scores")),
         emitter_case("the emitter refuses a scored pass with no observed dimension",
                      lambda r: r["passes"][0].update({"scores": []}), (1, "must carry the dimension")),
         emitter_case("CONTROL: a clean run emits a record the corpus accepts",
                      lambda r: None, (0, "OK")),
         packet_control(),
         # C36's two refusals, at the point of writing
         emitter_case("C36: the emitter refuses a regenerate with no violation",
                      lambda r: r.__setitem__("verdict", "regenerate"), (1, "not an iteration")),
         emitter_case("C36: the emitter refuses a below-floor dimension with no violation naming it",
                      lambda r: r["dimensions"][0].__setitem__("score", 8.0), (1, "no violation naming it")),
         emitter_case("CONTROL: a regenerate WITH a violation naming the below-floor dimension is emitted",
                      lambda r: (r.__setitem__("verdict", "regenerate"),
                                 r["dimensions"][0].__setitem__("score", 8.0),
                                 r.__setitem__("violations", [{"id": "V1", "class": "frame_at_fault",
                                                                "observation": "the frame demanded more than the bar allows",
                                                                "dimension": r["dimensions"][0]["name"]}])),
                      (0, "OK")),
         packet_case("the emitter refuses readings mode carrying bounds",
                      lambda r: r.__setitem__("mode", "readings"), (1, "must not supply bounds")),
         packet_case("the emitter refuses entry B with no reads_before_freeze",
                      lambda r: r.__setitem__("entry", "B"), (1, "reads_before_freeze")),
         packet_case("the emitter refuses the Maker grading its own work",
                      lambda r: r.__setitem__("evaluator", "maker-profile"), (1, "same party")),
         skip_case(),
         close_record_case(),
         wrapper_case(),
         c35_case(),
         c36_case(),
         ask2_case(),
         population_case(),
         *kind_cases(),
         missing_path_case()]
    print(f"\n  {sum(r)}/{len(r)} cases behaved as required")
    edi_corpus.ran(CHECK_ID, all(r))
    return 0 if all(r) else 1


if __name__ == "__main__":
    sys.exit(main())
