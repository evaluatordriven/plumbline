#!/usr/bin/env python3
"""The deployment conformance kit — one entry point, standard library only.

WHY THIS EXISTS
---------------
Measured 2026-10-02 on the first external deployment: five checkers exist in the E-DI
corpus and none of them could reach a deployment. The checkers were never the problem —
they are stdlib-only and run on a bare python3. The gap was that nothing told a
deployment which command to run, against which file, or what the exit code meant.

WHAT IT DOES NOT DO
-------------------
It does not re-implement any check. Re-implementing would create a second ruler, and the
corpus's own rule is that the check which can override the Evaluator IS the Evaluator.
This wraps `tools/*.py` in the corpus checkout and reports their exit codes.

THREE VERDICTS, NEVER TWO
-------------------------
  OK             the corpus checker ran and passed
  FAILED         the corpus checker ran and rejected the artifact
  NOT-CHECKABLE  no checker applies, or the artifact is in a shape no checker can read
A record that cannot be checked is NOT a record that passed. Deployment one's records
were not-checkable, and a two-verdict kit would have reported that as silence.

CORPUS RESOLUTION (explicit first, then the doctrine's own rule, then refuse)
  1. --corpus PATH             explicit; always wins
  2. $EDI_CORPUS               the edi-loop plugin's first rule ("" counts as unset)
  3. plugins.edi-loop.corpus in $HERMES_HOME/config.yaml or ~/.hermes/config.yaml
                               the plugin's second rule (read with PyYAML; a config that
                               cannot be read is reported, never ignored silently)
  4. otherwise: refuse, naming all three. Never guess a corpus path — a wrong guess
     produces a silent stale reading, which is the failure the convention names.
  A rule that is SET but does not name a corpus is a usage error (exit 2) naming the path;
  it never falls through to the next rule. The rules live in tools/edi_corpus.py, shared with
  tools/build_schemas.py and the test suites; a resolved corpus prints `corpus source: <rule>`.
  --doctor with no corpus reports `corpus NOT RESOLVED` and exits 0 (a preflight, not a check);
  with PLUMBLINE_REQUIRE_CORPUS=1 it exits 1.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys

__version__ = "0.1.0"  # Plumbline release; keep in step with CHANGELOG.md, gate/plugin.yaml and the skill

# The §5 record is recognised by the SHAPE the corpus requires, not by one convenient key.
# Measured 2026-10-05: routing on "dimensions" alone sent a CHANNEL OUTPUT (dimensions as an object
# keyed by dimension id, no pass_rule, no violations) into the §5 record validator, where it failed
# for being what it is. That is a false FAILED, and a checker that cries wolf is a checker people
# learn to ignore — so routing is by shape, and a channel output is named as one.
S5_REQUIRED = {"dimensions", "pass_rule", "violations", "verdict", "ground_truth_ref",
               "ground_truth_version", "ground_truth_hardness", "mandate_ref",
               "instrument_in_force", "evaluator_identity", "channel_blind", "ratified"}
from pathlib import Path

CHECKERS = {
    "packet": "tools/validate_job_packet.py",
    "record": "tools/validate_evaluator_record.py",
    "role_separation": "tools/check_role_separation.py",
    "terminal_state": "tools/check_terminal_state.py",
    "handoff": "tools/check_best_artifact_handoff.py",
}
OK, FAILED, NOT_CHECKABLE = "OK", "FAILED", "NOT-CHECKABLE"


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import edi_corpus  # noqa: E402  (tools/edi_corpus.py: the shared D-E resolver)

REPO = Path(__file__).resolve().parent.parent


def resolve_corpus(explicit: str | None) -> tuple[Path | None, bool]:
    """(corpus, required). A set rule that is not a corpus exits 2 naming it; never falls through."""
    corpus, required = edi_corpus.resolve_or_exit(explicit, ("tools/validate_job_packet.py",))
    return (corpus.path if corpus else None), required


def validation_strength() -> tuple[bool, str]:
    """Which level of the corpus gate will run under THIS interpreter?

    validate_job_packet.py states it itself (its docstring, lines 6-7): the stdlib structural
    check is the CI gate, and "if jsonschema is installed, Draft 2020-12 runs as well; a packet
    must pass both". Measured 2026-10-02: the same packet, with an invalid enum, returned OK
    under python3.9 without jsonschema and FAILED under python3.11 with jsonschema 4.26 — the
    same word, two different laws. So an OK from the weak path must never be shown as an OK.
    """
    try:
        import jsonschema  # type: ignore  # noqa: F401
        import importlib.metadata as md
        return True, f"strong — jsonschema {md.version('jsonschema')}: the schema pass runs too"
    except Exception:
        return False, ("WEAK — jsonschema is not importable here, so only the stdlib structural "
                       "check runs. It accepts what the schema forbids. Results are not a verdict.")
def run(checker: str, corpus: Path, args: list[str]) -> tuple[str, str]:
    script = corpus / CHECKERS[checker]
    if not script.is_file():
        return NOT_CHECKABLE, f"checker absent from this corpus: {CHECKERS[checker]}"
    r = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True, timeout=120,
                       cwd=str(corpus))   # never inherit the caller's cwd: a checker must answer
                                          # the same way wherever it is called from
    out = (r.stdout + r.stderr).strip().splitlines()
    tail = out[-1] if out else ""
    if r.returncode == 0:
        return OK, tail
    if r.returncode == 2:                       # usage error, not a verdict
        return NOT_CHECKABLE, f"checker refused the invocation (exit 2): {tail}"
    return FAILED, tail


# `custody/` holds a job's custody/v1 record and the files it digests (kit/emit_custody.py): a public re-reading
# of the job, written AFTER the close, in custody's shape rather than the corpus's. It is not terms or a §5
# record, so it is skipped and counted like `inputs/`; tools/build_schemas.py --custody and the custody checker
# are what read it.
SKIP_DIRS = ("superseded", "inputs", "custody")

# Filled by the walk and consumed by the close. A skip that lives only in stdout dies with the terminal.
SKIPPED_SEEN: dict[str, int] = {}
SKIPPED_FILES: dict[str, list[str]] = {}


def classify(path: Path) -> str:
    if path.is_dir():
        return "job_dir"
    if path.name == "packet.md":
        return "markdown_packet"
    if path.suffix == ".json":
        try:
            d = json.loads(path.read_text())
        except Exception:
            return "unparseable_json"
        if isinstance(d, dict):
            if "entry" in d and "mode" in d:
                return "packet"
            present = S5_REQUIRED & set(d)
            if len(present) >= 4:
                return "record"
            if ("channel" in d or isinstance(d.get("dimensions"), dict)
                    or any(isinstance(k, str) and re.fullmatch(r"D\d+", k) for k in d)):
                return "channel_output"
            # A filename that CLAIMS the §5 shape is held to it: a file named as a record and not
            # shaped like one is the defect this kit exists to report. Naming it is a claim.
            if re.search(r"eval-record|§5|s5\b", path.name):
                return "record"
            # A channel output carries per-dimension observations, not a verdict: an array of
            # dimension objects with scores is the engine's own vector.
            dims = d.get("dimensions")
            if isinstance(dims, list) and dims and all(isinstance(x, dict) and "score" in x for x in dims):
                return "channel_output"
        return "unknown_json"
    return "unknown"


def kit_revision() -> str:
    """The kit's own revision, so a close record says which reader produced it. Unknown is a value."""
    try:
        import subprocess
        return subprocess.run(["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def record_close(job: Path, corpus: Path, counts: dict) -> int:
    """Write the close into the job's own packet, then PROVE the packet still reads.

    The packet is the job's terms document and the corpus already puts the job's end in it (terminal_state,
    outcome). What the corpus does not model is what the close did not read — so the close says so, and the
    packet either still passes the gate with it or the write is rolled back unchanged.
    """
    from datetime import datetime, timezone
    packet = job / "packet.json"
    if not packet.is_file():
        print("  cannot record the close: this job has no packet.json"); return 1
    before = packet.read_text()
    doc = json.loads(before)
    # MERGE, never replace: the wrapper writes the end-of-job facts (billed reroll, the misalignment, the
    # escalation kind) into `close` before this runs, and a replace would silently delete them.
    doc["close"] = {**(doc.get("close") or {}), "verdict": "CLOSEABLE",
                    "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "kit_revision": kit_revision(), "counts": dict(counts),
                    "skipped": dict(SKIPPED_SEEN), "skipped_files": {k: list(v) for k, v in SKIPPED_FILES.items()}}
    packet.write_text(json.dumps(doc, indent=2) + "\n")
    verdict, detail = run("packet", corpus, [str(packet)])
    if verdict != OK:
        packet.write_text(before)
        print(f"  the close was NOT recorded: with it written, the packet fails the gate ({detail[:70]})")
        print("  packet.json is byte-identical to what it was. Declare `close` in the instance layer first.")
        return 1
    total = sum(SKIPPED_SEEN.values())
    print(f"  close recorded in packet.json — verdict, date, revision, counts, and {total} skipped file(s) named")
    return 0


def artifact_checks(judged: list[Path], job: Path) -> list[tuple[str, str, str]]:
    """A record that names an artifact must have it beside it, hashing to what was recorded.

    The instance's own `artifact_ref` carries "<path> sha256 <hash>", so this is deterministic for records the
    kit's emitter wrote, and honestly not-checkable for records it did not — which is reported rather than
    assumed either way. A record whose subject is missing is the sibling of C34's "evidence not filed".
    """
    out: list[tuple[str, str, str]] = []
    for f in judged:
        if classify(f) != "record":
            continue
        try:
            doc = json.loads(f.read_text())
        except Exception:
            continue
        refs = [e.get("value") for e in (doc.get("instance_extensions") or [])
                if isinstance(e, dict) and e.get("name") == "artifact_ref"]
        if not refs:
            out.append((str(f.relative_to(job)), NOT_CHECKABLE,
                        "the record names no artifact (no `artifact_ref` extension) — nothing here can say "
                        "whether the thing it judged exists"))
            continue
        for ref in refs:
            rel, sep, digest = str(ref).partition(" sha256 ")
            target = (f.parent / rel).resolve()
            if not target.is_file():
                out.append((str(f.relative_to(job)), FAILED,
                            f"names an artifact that is not beside it: {rel} — the sibling of C34's "
                            f"\"evidence not filed\", one level up"))
            elif sep and digest and __import__("hashlib").sha256(target.read_bytes()).hexdigest() != digest.strip():
                out.append((str(f.relative_to(job)), FAILED,
                            f"the artifact beside it is not the one judged: {rel} does not hash to {digest[:16]}…"))
    return out


def check_one(path: Path, corpus: Path) -> list[tuple[str, str, str]]:
    """Return [(subject, verdict, detail)]."""
    kind = classify(path)
    if kind == "job_dir":
        results, saw_packet = [], False
        skipped: dict[str, int] = {}
        for sub in sorted(path.rglob("*")):
            rel = sub.relative_to(path)
            # HISTORY AND INPUTS ARE NOT THE JOB'S CURRENT TERMS. `superseded/` holds records the job has
            # already replaced; `inputs/` holds the briefs and run files the emitters read. Holding them to the
            # current bar would block a close on work that has been replaced — and, worse, would make moving a
            # failing record into `superseded/` a way to close. So they are skipped AND COUNTED, and the skip is
            # printed: a skip nobody can see is a hiding place, which is the defect this kit exists to report.
            if any(part in SKIP_DIRS for part in rel.parts[:-1]):
                d = rel.parts[0]
                skipped[d] = skipped.get(d, 0) + 1
                SKIPPED_SEEN[d] = SKIPPED_SEEN.get(d, 0) + 1
                SKIPPED_FILES.setdefault(d, []).append(str(rel))
                continue
            if sub.is_file() and sub.suffix == ".json":
                results += check_one(sub, corpus)
                saw_packet = saw_packet or classify(sub) == "packet"
        for d, n in sorted(skipped.items()):
            print(f"  SKIPPED        {d}/ — {n} file(s): history and inputs, not current terms "
                  f"(skipped by name, and counted)")
        # THE POPULATION, beside what was judged. "An enumeration carries a control in the same batch": a
        # reader that reports only what it found cannot show what it missed. Measured 2026-10-05 — mine was a
        # pattern that matched zero files and returned an empty body, and a printed 0 would have been visibly
        # wrong; it is recorded in the corpus's own changelog as the evidence for keeping this as practice.
        present = [f for f in sorted(path.rglob("*")) if f.is_file()
                   and not any(part in SKIP_DIRS for part in f.relative_to(path).parts[:-1])]
        judged = [f for f in present if f.suffix == ".json"]
        unjudged = [f for f in present if f.suffix != ".json"]
        print(f"  POPULATION     {len(present)} file(s) present · {len(judged)} judged · "
              f"{sum(skipped.values())} skipped by name · {len(unjudged)} not judged by shape "
              f"(no checker applies to {', '.join(sorted({f.suffix for f in unjudged})) or 'nothing'})")
        results += artifact_checks(judged, path)
        if not saw_packet:
            md = sorted(path.glob("packet.md"))
            detail = ("no packet.json in this job — the corpus gate cannot read a markdown packet"
                      if md else "no packet.json in this job")
            results.insert(0, (f"{path.name}/packet", NOT_CHECKABLE, detail))
        return results
    if kind == "markdown_packet":
        return [(str(path), NOT_CHECKABLE,
                 "markdown packet: the corpus gate parses JSON and exits on this. "
                 "An instance shape is legitimate only when it is labelled as one.")]
    if kind == "unparseable_json":
        return [(str(path), NOT_CHECKABLE, "not valid JSON — nothing can be checked")]
    if kind == "channel_output":
        return [(str(path), NOT_CHECKABLE,
                 "channel output: a channel artifact, not a §5 record — the corpus declares no shape "
                 "for it, so there is nothing to check it against (reported, not skipped)")]
    if kind == "unknown_json":
        return [(str(path), NOT_CHECKABLE, "no checker applies to this shape (reported, not skipped)")]
    if kind == "packet":
        res = [(str(path), *run("packet", corpus, [str(path)]))]
        verdict, detail = run("role_separation", corpus, ["--packet", str(path)])
        res.append((f"{path.name} [role separation]", verdict, detail))
        return res
    if kind == "record":
        return [(str(path), *run("record", corpus, [str(path)]))]
    return [(str(path), NOT_CHECKABLE, "unclassified")]


def pin_line(corpus: Path | None) -> str:
    """The corpus pin is Plumbline's tools/pin.json (the corpus does not carry one)."""
    pin_file = REPO / "tools" / "pin.json"
    try:
        pinned = json.loads(pin_file.read_text(encoding="utf-8"))["commit"]
    except Exception as e:  # noqa: BLE001
        return f"unreadable: {pin_file} ({type(e).__name__})"
    line = f"{pinned[:12]}  (tools/pin.json)"
    if corpus:
        try:
            head = subprocess.run(["git", "-C", str(corpus), "rev-parse", "HEAD"], capture_output=True,
                                  text=True, timeout=30).stdout.strip()
        except Exception:  # noqa: BLE001
            head = ""
        line += (f"; corpus HEAD {head[:12]} {'matches' if head == pinned else 'DIFFERS — tools/build_schemas.py --check'}"
                 if head else "; corpus HEAD not readable (not a git checkout)")
    return line


def doctor(corpus: Path | None, required: bool = False) -> int:
    print("plumbline kit — preflight")
    print(f"  python           {sys.version.split()[0]}  ({sys.executable})")
    print(f"  corpus           {corpus if corpus else 'NOT RESOLVED'}")
    if not corpus:
        print("                   set --corpus PATH, or $EDI_CORPUS, or plugins.edi-loop.corpus")
        print("                   in ~/.hermes/config.yaml. Refusing to guess.")
        print(f"  corpus pin       {pin_line(None)}")
        if required:
            print(f"  result           corpus NOT RESOLVED — {edi_corpus.REQUIRE_VAR}=1 requires it: exit 1")
            return 1
        print("  result           corpus NOT RESOLVED — a preflight report, not a failure: exit 0 "
              f"(set {edi_corpus.REQUIRE_VAR}=1 to make it one)")
        return 0
    for name, rel in CHECKERS.items():
        mark = "present" if (corpus / rel).is_file() else "ABSENT "
        print(f"  {name:16s} {mark}  {rel}")
    strong, why = validation_strength()
    print(f"  schema pass      {why}")
    print(f"  corpus pin       {pin_line(corpus)}")
    plug = Path.home() / ".hermes" / "plugins"
    installed = [d.parent.name for d in plug.glob("*/plugin.yaml")
                 if "edi-loop" in d.read_text(errors="ignore")] if plug.is_dir() else []
    print(f"  plugin           {'present: ' + ', '.join(installed) if installed else 'absent'}"
          f"  — not required: the checkers above are the law")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Check a deployment's records with the corpus's own checkers.")
    ap.add_argument("--version", action="version", version=f"plumbline {__version__}")
    ap.add_argument("paths", nargs="*", help="files or job directories to check")
    ap.add_argument("--corpus", help="path to the E-DI corpus checkout (wins over every other rule)")
    ap.add_argument("--doctor", action="store_true", help="report the environment and where the corpus resolved from")
    ap.add_argument("--record-close", action="store_true",
                    help="with --job-close: write the close into the job's packet.json (verdict, date, kit "
                         "revision, counts, and every file the close SKIPPED). A close record asserts a close, "
                         "so a job that did not close gets nothing written.")
    ap.add_argument("--job-close", action="store_true",
                    help="may this job close? A job may not close on a failed record or on terms no checker "
                         "can read. Exit 3 when it may not, so a script or a hook can gate on it.")
    a = ap.parse_args()
    corpus, required = resolve_corpus(a.corpus)
    if a.doctor or not a.paths:
        return doctor(corpus, required)
    if corpus is None:
        print("REFUSED: no corpus checkout resolved — cannot check anything.")
        print("  set --corpus PATH, or $EDI_CORPUS, or plugins.edi-loop.corpus in ~/.hermes/config.yaml.")
        return 1
    rows, failed = [], False
    for p in a.paths:
        q = Path(p).expanduser()
        if not q.exists():
            print(f"no such path: {q}", file=sys.stderr)
            print(f"  given as {p!r} from {Path.cwd()}", file=sys.stderr)
            print("  a path that does not exist is an IO error, not a verdict: exit 2, like the "
                  "corpus's own tools", file=sys.stderr)
            return 2
        rows += check_one(q, corpus)
    strong, why = validation_strength()
    width = min(max((len(s) for s, _, _ in rows), default=10), 58)
    for subject, verdict, detail in rows:
        shown = subject if len(subject) <= width else "..." + subject[-(width - 3):]
        mark = verdict if (strong or verdict != OK) else "OK*"
        print(f"  {mark:14s} {shown:{width}s}  {detail[:100]}")
        failed = failed or verdict == FAILED
    counts = {v: sum(1 for _, x, _ in rows if x == v) for v in (OK, FAILED, NOT_CHECKABLE)}
    print(f"\n  {counts[OK]} ok · {counts[FAILED]} failed · {counts[NOT_CHECKABLE]} not-checkable")
    print("  not-checkable is not a pass: a record no checker can read is a finding.")
    checked = counts[OK] + counts[FAILED]
    if a.job_close:
        reasons = []
        for p in a.paths:
            q = Path(p).expanduser()
            if q.is_dir() and not any(classify(s) == "packet" for s in q.rglob("*.json")):
                md = (" (packet.md present: convert it, the gate parses JSON)"
                      if (q / "packet.md").exists() else "")
                reasons.append(f"{q.name}: no machine-readable packet{md}")
        reasons += [f"{s}: {d}" for s, v, d in rows if v == FAILED]
        if reasons:
            print("\n  job-close: NOT CLOSEABLE")
            for r in reasons:
                print(f"    - {r}")
            print("  exit 3 — a job may not close on a failed record or on terms nothing can read.")
            if a.record_close:
                print("  nothing was written: a close record asserts a close, and this job did not close.")
            return 3
        print("\n  job-close: CLOSEABLE — the packet is readable and every record a checker can read passed.")
        if a.record_close:
            return record_close(Path(a.paths[0]).expanduser(), corpus, counts)
        if SKIPPED_SEEN:
            print(f"  note: {sum(SKIPPED_SEEN.values())} file(s) were skipped by name "
                  f"({', '.join(sorted(SKIPPED_SEEN))}) — use --record-close to put that in the packet")
        return 0
    if not strong and counts[OK]:
        print("  DEGRADED: the OK* rows above come from the weak path only, so they are not a verdict —")
        print(f"            {why}")
        return 1
    if failed or checked == 0:
        if checked == 0:
            print("  nothing could be checked: that is not a pass.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
