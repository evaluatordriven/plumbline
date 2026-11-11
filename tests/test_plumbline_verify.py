"""The verifier's own tests: every kind it prints, from repo fixtures, plus the clean control and close wiring.

Fixtures: tests/fixtures/custody/verify/. `clean/job` is a small job (a tool-stamped freeze in the ledger and a
matching inputs/custody.json). Each planted case is that job with one different ledger (`hand`, `events`, `relay`)
or one extra §5 record (`shadow`), plus a record written to plant exactly one fault.

The standard layer is a stand-in checker written here (into each test's temporary custody checkout) and pinned by
its own sha256: it refuses unless `--bar` is given, so a verifier that forgets `--bar` cannot pass again, and it
checks the record's subject digests against the files dir, so a planted bad-subject record fails. When
`CUSTODY_DIR` names a real custody checkout, the real-checker fixture `real/` (a record that kit/emit_custody.py
emitted from the job beside it, `real/job/`) is run against that checkout's own `checker/check.py`, and the
`clean/` stub is run there too, to show the checker's failing requirement (CR-1) reaches the verifier's output.

Three more cases run the emitter and the verifier together, building their inputs in a temporary directory from
code (no fixture is added): a failure line always names a file; a job with a logged call cost and no spend-ledger
line verifies; and a startedAt/producedAt typed into inputs/custody.json is a hand time on both sides.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "kit" / "plumbline_verify.py"
FIX = ROOT / "tests" / "fixtures" / "custody" / "verify"
JOB_REJECTED = ROOT / "tests" / "fixtures" / "custody" / "job-rejected"
sys.path.insert(0, str(ROOT / "kit"))
import plumbline_job as J  # noqa: E402
import plumbline_verify as V  # noqa: E402
import custody_history as H  # noqa: E402
import emit_custody as E  # noqa: E402

# A stand-in checker: it refuses unless `--bar` is given (so a verifier that forgets `--bar` cannot pass again),
# and it checks the record's subject digests against the files dir (so a planted bad-subject record fails).
# Written from code, never from a fixture.
STAND_IN_CHECKER = '''#!/usr/bin/env python3
import json, sys
from hashlib import sha256
from pathlib import Path


def arg(name):
    a = sys.argv[1:]
    return a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else None


rec = Path(sys.argv[1])
files = arg("--files")
if not arg("--bar"):
    print("checker: --bar is required", file=sys.stderr)
    sys.exit(2)
doc = json.loads(rec.read_text(encoding="utf-8"))
for s in doc.get("subject") or []:
    name = s.get("name")
    want = (s.get("digest") or {}).get("sha256")
    p = (Path(files) / name) if files else None
    if p is None or not p.is_file():
        print("checker: missing file " + str(name), file=sys.stderr)
        sys.exit(1)
    if sha256(p.read_bytes()).hexdigest() != want:
        print("checker: subject digest mismatch for " + str(name), file=sys.stderr)
        sys.exit(1)
sys.exit(0)
'''


def checkout(tmp: Path, name: str = "checkout", wrong_pin: bool = False) -> Path:
    """A custody checkout holding the stand-in checker, pinned (or, for the exit-2 case, mispinned)."""
    c = tmp / name
    (c / "checker").mkdir(parents=True, exist_ok=True)
    (c / "tools").mkdir(parents=True, exist_ok=True)
    (c / "checker" / "check.py").write_text(STAND_IN_CHECKER, encoding="utf-8")
    pin = "0" * 64 if wrong_pin else sha256((c / "checker" / "check.py").read_bytes()).hexdigest()
    (c / "tools" / "pin.json").write_text(json.dumps({"checker/check.py": pin}) + "\n", encoding="utf-8")
    return c


def ensure_bar(job: Path) -> None:
    """The verifier passes the job's bar to the pinned checker (V1); make sure the named bar file exists."""
    rel = "custody/bar.md"
    cj = job / "inputs" / "custody.json"
    if cj.is_file():
        try:
            rel = ((json.loads(cj.read_text(encoding="utf-8")).get("bar") or {}).get("file")) or rel
        except ValueError:
            pass
    p = Path(rel)
    if not p.is_absolute():
        p = job / p
    if not p.is_file():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# bar\n\nfixture bar for the verifier tests\n", encoding="utf-8")


def make_job(tmp: Path, ledger: str | None = None, extra: dict | None = None) -> Path:
    """A copy of the clean job, with another ledger folder (a sibling of `clean/` under FIX) and/or extra files."""
    dst = tmp / "job"
    shutil.copytree(FIX / "clean" / "job", dst)
    if ledger:
        shutil.copyfile(FIX / ledger / "ledger.jsonl", dst / "inputs" / "custody-events.jsonl")
    for name, rel in (extra or {}).items():
        src = FIX / rel
        if src.is_file() and not (dst / name).exists():
            shutil.copyfile(src, dst / name)
    ensure_bar(dst)
    return dst


def record(folder: str, name: str) -> Path:
    return FIX / folder / name


def run_verify(rec: Path, job: Path, custody: Path, json_out: Path | None = None):
    cmd = [sys.executable, str(VERIFIER),
           "--record", str(rec),
           "--files", str(job / "custody" / "files"),
           "--evidence", str(job / "custody" / "evidence"),
           "--ledger", str(job / "inputs" / "custody-events.jsonl"),
           "--custody", str(custody)]
    if json_out is not None:
        cmd += ["--json", str(json_out)]
    return subprocess.run(cmd, capture_output=True, text=True)


def kinds(rv) -> list:
    return [ln.split()[1] for ln in rv.stdout.splitlines() if ln.startswith("FAIL ")]


def clean_emitter_tree(tmp: Path) -> Path:
    """A throwaway clean git checkout of kit/: the emitter records its own revision and refuses a dirty tree."""
    d = tmp / "emitter-tree"
    (d / "kit").mkdir(parents=True)
    for name in ("emit_custody.py", "custody_history.py", "custody_ledger.py"):
        shutil.copy2(ROOT / "kit" / name, d / "kit" / name)
    # With bytecode on (PYTHONDONTWRITEBYTECODE unset), running the emitter writes kit/__pycache__/ into this tree,
    # and the emitter then refuses it as dirty. The repo's own .gitignore does not reach this throwaway tree, so the
    # tree carries its own: the tree stays clean whether or not bytecode is written.
    (d / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    base = ["git", "-C", str(d), "-c", "user.name=test", "-c", "user.email=test@localhost",
            "-c", "commit.gpgsign=false"]
    subprocess.run(base + ["init", "-q"], capture_output=True, check=True)
    subprocess.run(base + ["add", "-A"], capture_output=True, check=True)
    subprocess.run(base + ["commit", "-qm", "clean checkout for the emitter"], capture_output=True, check=True)
    return d


def run_emit(job: Path, out: Path, tree: Path, allow_hand: bool = True):
    # These fixtures are plumbline jobs, not custody checkouts, so the version is stated explicitly:
    # since Job 34 the emitter resolves specVersion from the document it attests or refuses (exit 3).
    cmd = [sys.executable, str(tree / "kit" / "emit_custody.py"), "--job-dir", str(job), "--out", str(out),
           "--spec-version", "0.9.8"]
    if allow_hand:
        cmd.append("--allow-hand-times")
    return subprocess.run(cmd, capture_output=True, text=True)


def copy_job(tmp: Path, name: str = "job") -> Path:
    dst = tmp / name
    shutil.copytree(JOB_REJECTED, dst)
    return dst


def set_generation_cost(log: Path, value: float) -> None:
    """Set `generation.data.total_cost` on the log's calls (the maker log is one JSON object)."""
    text = log.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
        array = isinstance(doc, list)
        items = doc if array else [doc]
    except ValueError:
        items, array = [json.loads(ln) for ln in text.splitlines() if ln.strip()], False
    for c in items:
        gen = c.get("generation") if isinstance(c, dict) else None
        if isinstance(gen, dict):
            data = gen.get("data") if isinstance(gen.get("data"), dict) else gen
            if isinstance(data, dict):
                data["total_cost"] = value
    log.write_text((json.dumps(items, indent=2) + "\n") if array
                   else "".join(json.dumps(c) + "\n" for c in items), encoding="utf-8")


class VerifierKindTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def job(self, ledger=None, extra=None):
        return make_job(self.tmp, ledger, extra)

    def custody(self, name: str = "checkout", wrong_pin: bool = False):
        return checkout(self.tmp, name, wrong_pin)

    def test_clean_record_passes_both_layers(self):
        rv = run_verify(record("clean", "record.custody.json"), self.job(), self.custody())
        self.assertEqual(rv.returncode, 0, rv.stdout + rv.stderr)
        self.assertEqual(kinds(rv), [])

    def test_standard_failure_exits_3(self):
        rv = run_verify(record("clean", "record-bad-subject.json"), self.job(), self.custody())
        self.assertEqual(rv.returncode, 3, rv.stdout + rv.stderr)
        self.assertEqual(kinds(rv), ["standard"])

    def test_wrong_checker_bytes_exit_2(self):
        rv = run_verify(record("clean", "record.custody.json"), self.job(),
                        self.custody("bad-checkout", wrong_pin=True))
        self.assertEqual(rv.returncode, 2, rv.stdout + rv.stderr)
        # an exit-2 line must not be a `FAIL <kind>` line (those are for exits 3 and 4)
        self.assertEqual(kinds(rv), [])
        self.assertIn("NOT CHECKABLE", rv.stdout)

    def test_schema_failures(self):
        job = self.job()
        co = self.custody()
        for name in ("record-no-block.json", "record-hand-times-string.json",
                     "record-unknown-key.json", "record-v0.json"):
            with self.subTest(name=name):
                rv = run_verify(record("clean", name), job, co)
                self.assertEqual(rv.returncode, 4, rv.stdout + rv.stderr)
                self.assertIn("schema", kinds(rv))

    def test_allowance_missing(self):
        rv = run_verify(record("hand", "record-no-allowance.json"), self.job(ledger="hand"), self.custody())
        self.assertEqual(rv.returncode, 4, rv.stdout + rv.stderr)
        self.assertEqual(kinds(rv)[0], "allowance")

    def test_allowance_present_passes(self):
        rv = run_verify(record("hand", "record-allowance.json"), self.job(ledger="hand"), self.custody())
        self.assertEqual(rv.returncode, 0, rv.stdout + rv.stderr)
        self.assertEqual(kinds(rv), [])

    def test_hand_time_unflagged(self):
        rv = run_verify(record("hand", "record-unflagged.json"), self.job(ledger="hand"), self.custody())
        self.assertEqual(rv.returncode, 4, rv.stdout + rv.stderr)
        self.assertEqual(kinds(rv)[0], "hand-time-unflagged")

    def test_flag_without_source(self):
        rv = run_verify(record("clean", "record-flag-without-source.json"), self.job(), self.custody())
        self.assertEqual(rv.returncode, 4, rv.stdout + rv.stderr)
        self.assertEqual(kinds(rv)[0], "flag-without-source")

    def test_events_missing_generation(self):
        rv = run_verify(record("events", "record-missing-generation.json"),
                        self.job(ledger="events"), self.custody())
        self.assertEqual(rv.returncode, 4, rv.stdout + rv.stderr)
        self.assertIn("events", kinds(rv))

    def test_relay_as_approval(self):
        rv = run_verify(record("relay", "record.json"), self.job(ledger="relay"), self.custody())
        self.assertEqual(rv.returncode, 4, rv.stdout + rv.stderr)
        self.assertIn("relay-as-approval", kinds(rv))

    def test_spend_off_by_a_cent(self):
        rv = run_verify(record("clean", "record-spend-off.json"), self.job(), self.custody())
        self.assertEqual(rv.returncode, 4, rv.stdout + rv.stderr)
        self.assertEqual(kinds(rv)[0], "spend")

    def test_shadowed_inputs(self):
        job = self.job(extra={"iteration-1-eval-record.json": "shadow/iteration-1-eval-record.json"})
        rv = run_verify(record("shadow", "record.json"), job, self.custody())
        self.assertEqual(rv.returncode, 4, rv.stdout + rv.stderr)
        self.assertIn("shadow", kinds(rv))

    def test_json_out_lists_failures(self):
        out = self.tmp / "verify.json"
        rv = run_verify(record("hand", "record-no-allowance.json"), self.job(ledger="hand"),
                        self.custody(), json_out=out)
        self.assertEqual(rv.returncode, 4)
        doc = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(doc["exit"], 4)
        self.assertEqual(doc["failures"][0]["kind"], "allowance")

    def test_run_writes_nothing(self):
        job = self.job(ledger="hand")
        co = self.custody()
        rec = self.tmp / "record.json"
        rec.write_bytes(record("hand", "record-allowance.json").read_bytes())
        before = {str(p): sha256(p.read_bytes()).hexdigest() for p in [rec, *job.rglob("*")] if p.is_file()}
        rv = run_verify(rec, job, co)
        after = {str(p): sha256(p.read_bytes()).hexdigest() for p in [rec, *job.rglob("*")] if p.is_file()}
        self.assertEqual(rv.returncode, 0, rv.stdout + rv.stderr)
        self.assertEqual(before, after)

    def test_verifier_does_not_reference_the_emitter(self):
        text = VERIFIER.read_text(encoding="utf-8")
        self.assertNotIn("emit_custody", text)
        self.assertNotIn("import emit", text)
        self.assertEqual(V.SCHEMA_VERSION, "plumbline/x-plumbline/v1")

    def test_call_cost_prefers_generation_total(self):
        """V5: the sum uses the generation reply's data.total_cost, else the chat reply's usage.cost."""
        raw = {"request": {"url": "https://openrouter.ai/api/v1/chat/completions"},
               "response": {"usage": {"cost": 0.05}},
               "generation": {"data": {"total_cost": 0.07}}}
        c = H.Call("harness.log", 0, raw, [])
        self.assertAlmostEqual(E.call_cost(c), 0.07)
        self.assertAlmostEqual(V.call_cost(c), 0.07)
        raw2 = {"request": {"url": "https://openrouter.ai/api/v1/chat/completions"},
                "response": {"usage": {"cost": 0.05}},
                "generation": None}
        c2 = H.Call("harness.log", 0, raw2, [])
        self.assertAlmostEqual(E.call_cost(c2), 0.05)
        self.assertAlmostEqual(V.call_cost(c2), 0.05)

    def test_checker_needs_bar(self):
        """Item 7: the stand-in refuses without --bar, so the verifier must pass it."""
        co = self.custody()
        rv = subprocess.run([sys.executable, str(co / "checker" / "check.py"), str(self.tmp / "nope.json")],
                            capture_output=True, text=True)
        self.assertNotEqual(rv.returncode, 0)

    def test_standard_failure_names_the_checker_reason(self):
        """P2: the FAIL line stays, and the checker's own reason follows it (never a `FAIL <kind>` line)."""
        rv = run_verify(record("clean", "record-bad-subject.json"), self.job(), self.custody())
        self.assertEqual(rv.returncode, 3, rv.stdout + rv.stderr)
        self.assertEqual(kinds(rv), ["standard"])
        lines = rv.stdout.splitlines()
        self.assertTrue(lines[0].startswith("FAIL standard record "), rv.stdout)
        self.assertIn("  checker: checker: subject digest mismatch for artifact.txt", lines[1:])

    def test_checker_reasons_lists_failed_requirements(self):
        """P2: one line per requirement the custody checker reports FAILED; NOT-CHECKABLE ones give none."""
        report = {"verdict": "FAILED", "requirements": {
            "CR-1": {"status": "FAILED", "detail": "subject must be non-empty"},
            "CR-2": {"status": "NOT-CHECKABLE", "detail": "blocked (CR-1)"},
            "CL1-3": {"status": "FAILED", "detail": "two\n  lines"},
            "CL1-4": {"status": "OK", "detail": ""}}}
        rv = subprocess.CompletedProcess([], 1, json.dumps(report), "")
        self.assertEqual(V.checker_reasons(rv),
                         ["CR-1 FAILED: subject must be non-empty", "CL1-3 FAILED: two lines"])
        self.assertEqual(V.checker_reasons(subprocess.CompletedProcess([], 1, "", "boom\n")), ["checker: boom"])

    @unittest.skipUnless(os.environ.get("CUSTODY_DIR")
                         and (Path(os.environ.get("CUSTODY_DIR", "")) / "checker" / "check.py").is_file(),
                         "CUSTODY_DIR does not name a custody checkout")
    def test_clean_against_real_checker(self):
        # P1: the `real/` fixture passes the real checker, called directly and through the verifier.
        # `real/record.custody.json` was emitted by kit/emit_custody.py (Plumbline 9369219, clean tree) from
        # `real/job/`, a copy of the synthetic job-rejected fixture; see real/README.md. The test uses the
        # fixture's own job as it is in the tree (bar file included), not the shared `clean/` job or its helpers.
        # (No docstring: `unittest -v` then prints this test's name on its `... ok` line.)
        custody = Path(os.environ["CUSTODY_DIR"])
        real = FIX / "real"
        job = real / "job"
        rec = real / "record.custody.json"
        bar = V.bar_path(job, job / "inputs" / "custody.json")
        self.assertTrue(bar.is_file(), bar)
        direct = subprocess.run([sys.executable, str(custody / "checker" / "check.py"), str(rec),
                                 "--files", str(job / "custody" / "files"),
                                 "--evidence", str(job / "custody" / "evidence"), "--bar", str(bar)],
                                capture_output=True, text=True)
        self.assertEqual(direct.returncode, 0, direct.stdout + direct.stderr)
        self.assertEqual(json.loads(direct.stdout)["verdict"], "OK")
        # Every subject is a file of the job, by name and sha256.
        doc = json.loads(rec.read_text(encoding="utf-8"))
        self.assertTrue(doc["subject"])
        for s in doc["subject"]:
            f = job / "custody" / "files" / s["name"]
            self.assertEqual(sha256(f.read_bytes()).hexdigest(), s["digest"]["sha256"], s["name"])
        rv = run_verify(rec, job, custody)
        self.assertEqual(rv.returncode, 0, rv.stdout + rv.stderr)
        self.assertEqual(kinds(rv), [])

    @unittest.skipUnless(os.environ.get("CUSTODY_DIR")
                         and (Path(os.environ.get("CUSTODY_DIR", "")) / "checker" / "check.py").is_file(),
                         "CUSTODY_DIR does not name a custody checkout")
    def test_stub_against_real_checker_names_cr1(self):
        """P2 with the real checker: the `clean/` stub (empty subject) fails CR-1, and the verifier says so."""
        rv = run_verify(record("clean", "record.custody.json"), self.job(), Path(os.environ["CUSTODY_DIR"]))
        self.assertEqual(rv.returncode, 3, rv.stdout + rv.stderr)
        self.assertEqual(kinds(rv), ["standard"])
        self.assertIn("  CR-1 FAILED: subject must be non-empty, each with a name and a sha256 digest",
                      rv.stdout.splitlines())


class FailureLineTests(unittest.TestCase):
    """V intro: every failure line names kind, field and a non-empty FILE:LINE (item 1)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _case(self, folder: Path, rec: Path):
        """Run one record against its folder's job: the clean job, that folder's ledger if it has one, and any
        other file the folder carries (the shadow case's §5 record)."""
        tmp = self.tmp / f"{folder.name}-{rec.stem}"
        tmp.mkdir(parents=True, exist_ok=True)
        ledger = folder / "ledger.jsonl"
        extra = {p.name: p.relative_to(FIX).as_posix() for p in folder.iterdir()
                 if p.is_file() and p.name != "ledger.jsonl" and not p.name.startswith("record")}
        job = make_job(tmp, folder.name if ledger.is_file() else None, extra)
        return run_verify(rec, job, checkout(tmp))

    def test_every_fail_line_names_a_file(self):
        seen = 0
        for folder in sorted(p for p in FIX.iterdir() if p.is_dir()):
            for rec in sorted(folder.glob("record*.json")):
                with self.subTest(folder=folder.name, record=rec.name):
                    rv = self._case(folder, rec)
                    self.assertIn(rv.returncode, (0, 3, 4), rv.stdout + rv.stderr)
                    self.assertNotIn("Traceback", rv.stderr)
                    for ln in rv.stdout.splitlines():
                        if not ln.startswith("FAIL "):
                            continue
                        seen += 1
                        tok = ln.split()[-1]
                        file, sep, line = tok.rpartition(":")
                        self.assertTrue(sep and file and line.isdigit(), (rec.name, ln))
        self.assertGreater(seen, 0)

    def test_allowance_finding_names_the_record(self):
        job = make_job(self.tmp, "hand")
        rec = record("hand", "record-no-allowance.json")
        rv = run_verify(rec, job, checkout(self.tmp))
        self.assertEqual(rv.returncode, 4, rv.stdout + rv.stderr)
        line = next((ln for ln in rv.stdout.splitlines()
                     if ln.startswith("FAIL allowance x-plumbline.allowances.hand_times ")), None)
        self.assertIsNotNone(line, rv.stdout)
        file, sep, digits = line.split()[-1].rpartition(":")
        self.assertEqual(file, str(rec))
        self.assertTrue(sep and digits.isdigit())


class SpendWithoutSpendLineTests(unittest.TestCase):
    """V5: the spend block is checked against the logs; a missing spend-ledger line is not a failure (item 2)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_cost_with_no_spend_line_verifies(self):
        tree = clean_emitter_tree(self.tmp)
        job = copy_job(self.tmp)
        log = job / "custody" / "evidence" / "harness-maker-fixture.log"
        self.assertTrue(log.is_file())
        set_generation_cost(log, 0.0012)
        ledger = job / "inputs" / "custody-events.jsonl"
        rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines() if x.strip()] \
            if ledger.is_file() else []
        self.assertFalse(any(e.get("event") == "spend" for e in rows))
        out = self.tmp / "rec.json"
        rv = run_emit(job, out, tree)
        self.assertEqual(rv.returncode, 0, rv.stdout + rv.stderr)
        rec = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(rec["predicate"]["x-plumbline"]["spend"],
                         {"calls_sum_usd": 0.0012, "key_delta_usd": 0.0, "total_usd": 0.0012,
                          "tolerance_usd": 0.0001, "source": None})
        v = run_verify(out, job, checkout(self.tmp))
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        self.assertNotIn("FAIL ", v.stdout)


class TypedStartedProducedTests(unittest.TestCase):
    """V3: a startedAt/producedAt typed into inputs/custody.json is a hand time on both sides (item 3)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_typed_started_at_and_produced_at_are_hand_times(self):
        tree = clean_emitter_tree(self.tmp)
        job = copy_job(self.tmp)
        ci = json.loads((job / "inputs" / "custody.json").read_text(encoding="utf-8"))
        self.assertTrue(ci.get("startedAt") and ci.get("producedAt"))
        out = self.tmp / "rec.json"
        rv = run_emit(job, out, tree, allow_hand=True)
        self.assertEqual(rv.returncode, 0, rv.stdout + rv.stderr)
        rec = json.loads(out.read_text(encoding="utf-8"))
        xp = rec["predicate"]["x-plumbline"]
        ht = {e["field"]: e for e in xp["hand_times"]}
        for field in ("startedAt", "producedAt"):
            self.assertIn(field, ht)
            self.assertEqual(ht[field]["file"], "inputs/custody.json")
            self.assertIsInstance(ht[field]["line"], int)
            self.assertGreater(ht[field]["line"], 0)
            self.assertEqual(ht[field]["source"], "inputs-no-ledger")
        hand = V.hand_time_set(job, job / "inputs" / "custody-events.jsonl",
                               job / "inputs" / "custody.json", rec, job / "custody" / "evidence")
        vh = {e["field"]: e for e in hand}
        for field in ("startedAt", "producedAt"):
            self.assertIn(field, vh)
            self.assertEqual(V.hand_key(vh[field]), V.hand_key(ht[field]))
        v = run_verify(out, job, checkout(self.tmp))
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
        self.assertNotIn("flag-without-source", v.stdout)
        self.assertNotIn("shadow", v.stdout)

    def test_without_the_switch_the_refusal_names_them(self):
        tree = clean_emitter_tree(self.tmp)
        job = copy_job(self.tmp)
        out = self.tmp / "rec.json"
        rv = run_emit(job, out, tree, allow_hand=False)
        self.assertEqual(rv.returncode, 3, rv.stdout + rv.stderr)
        self.assertIn("REFUSED (history)", rv.stdout)
        self.assertIn("[hand-time] startedAt", rv.stdout)
        self.assertIn("[hand-time] producedAt", rv.stdout)
        self.assertFalse(out.exists())


class CloseWiringTests(unittest.TestCase):
    """V8: close runs the verifier after the emitter and refuses on its failure (no `closed` row)."""

    def _close(self, tmp: Path, verify):
        job = tmp / "job"
        (job / "inputs").mkdir(parents=True)
        (job / "packet.json").write_text(json.dumps({
            "job_id": "verify-close", "mode": "readings", "terminal_state": "accepted",
            "disposition_state": "given"}) + "\n", encoding="utf-8")
        corpus = tmp / "corpus"
        (corpus / "tools").mkdir(parents=True)
        (corpus / "tools" / "validate_job_packet.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        run_log = tmp / "run-log.json"
        a = argparse.Namespace(
            job_dir=str(job), corpus=str(corpus), run=[], disposition=None, disposition_note=None,
            billed_reroll=False, escalation_kind=None, misalignment_iteration=None,
            misalignment_spend=None, misalignment_note=None, terminal_state=None, outcome=None,
            allow_hand_times=True, custody=str(tmp), run_log=str(run_log))
        orig_call, orig_verify = J.call, J.run_verifier
        J.call = lambda script, args: 0
        J.run_verifier = lambda job_dir, args, record=None: verify
        try:
            rc = J.do_close(a)
        finally:
            J.call, J.run_verifier = orig_call, orig_verify
        rows = json.loads(run_log.read_text(encoding="utf-8"))["runs"] if run_log.is_file() else []
        return rc, rows

    def test_close_refuses_on_verify_failure(self):
        with tempfile.TemporaryDirectory() as td:
            rc, rows = self._close(Path(td), (4, "schema"))
            self.assertEqual(rc, 4)
            self.assertEqual([r["event"] for r in rows], ["close_refused"])
            self.assertEqual(rows[0]["kind"], "schema")

    def test_close_writes_closed_on_success(self):
        with tempfile.TemporaryDirectory() as td:
            rc, rows = self._close(Path(td), (0, "verify"))
            self.assertEqual(rc, 0)
            self.assertEqual([r["event"] for r in rows], ["closed"])


if __name__ == "__main__":
    unittest.main()
