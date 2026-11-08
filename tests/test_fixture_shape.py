"""Fixture-shape bar for tests/fixtures/custody/.

THE THREE RULES THIS BAR ENFORCES, in plain English:

1. A check that needs unstamped harness calls must FAIL LOUDLY if handed a stamped fixture.
   The D6/D7 refusal only happens when a model evaluator's harness log carries NO logger
   sent_at/received_at. If a test that checks that refusal is silently given a log that HAS
   those times, the condition under test disappears and the test reports a result about
   nothing. This bar makes that impossible to do by accident: the refusal fixture is required
   to have raw server-time-only logs, and the emit fixture is required to have logger-stamped
   logs, and they are two different directories.

2. No assertion is weakened to reach green. If the meaning of a check here genuinely changes,
   the old assertion, the new assertion, the ruling and the date must be recorded as
   `standard_moved` in the job record. This rule lives in the bar's docstring because it is a
   process rule; the tests below do not let a maintainer "soften" the fixture-shape contract
   without renaming or recording the move.

3. Every committed fixture must represent a LEGAL job:
     - a `dispose` event carries both `by` and `state`;
     - every ledger line carries a truthful `writer` (`tool` where a tool wrote it, `hand`
       only where a person wrote it, and never absent);
     - harness logs carry logger times only where the fixture's README says a logger wrote them.

WHAT THIS BAR DOES NOT PROVE, in plain English:

A fixture is a story about a job, not a job. These checks prove the fixture set is shaped so
that tests of the emitter can exercise legal and illegal jobs; they do not prove that any real
job's ledger is truthful about who wrote it.

CHOSEN REPAIR and why the other is worse here:

Chosen: (a) split the fixture set into fixtures that each represent ONE legal job.
   - tests/fixtures/custody/job-rejected/ stays the raw, server-time-only refusal fixture.
   - tests/fixtures/custody/job-emitted/ is added as a fully logger-stamped, emit-able job.

Why (b) is worse here: separating checks by what they measure works only if every check is
handed the right derived copy. The failure that produced this job came from exactly such a
helper: one copy function stamped every log, and three checks that existed to test an UNSTAMPED
call lost their condition while still reporting a result. Re-deriving stamped vs. raw copies
at test time in /tmp hides the condition in helper code; a reader cannot see what each fixture
is for without running Python, and a one-line helper mistake silently destroys the bar. Two
committed fixture directories make the shape visible in `ls` and in git diff.

BASE and STACKING:

Cut from the tip of feat/evaluator-harness-log (09c2072), NOT main: on main the emitter still
notes instead of refusing, so this fixture work would be unmeasurable there. This job stacks on
PR 22; the two merge together or not at all. The bar below records "graded against
feat/evaluator-harness-log@09c2072" so the record is not ambiguous.

FAILURES THAT ARE NOT THIS JOB'S, so a reader can distinguish them:

- `alignment · the pin still matches the corpus on disk` fails because the corpus on disk has
  moved to 3ea9e3fc0f812e5b. That is the corpus re-pin, a separate named follow-up.
- `alignment · the vendored schemas and fixture battery are the corpus's bytes` fails for the
  same reason (corpus moved). Also the re-pin job.
- `validate_audit` is reported separately and fails on local tmp records that CI does not have;
  it is not counted in the suite tally and is not this job.

FILES THE REPAIR WILL NEED, because a wrong list is a defect this program has recorded:
  - tests/validate_schemas.py
  - tests/fixtures/custody/job-rejected/README.md
  - tests/fixtures/custody/job-rejected/packet.json
  - tests/fixtures/custody/job-rejected/inputs/custody.json
  - tests/fixtures/custody/job-rejected/inputs/custody-events.jsonl
  - tests/fixtures/custody/job-rejected/inputs/run-1.json
  - tests/fixtures/custody/job-rejected/custody/bar.md
  - tests/fixtures/custody/job-rejected/custody/method.md
  - tests/fixtures/custody/job-rejected/custody/controls/K1-clean.md
  - tests/fixtures/custody/job-rejected/custody/controls/K2-planted.md
  - tests/fixtures/custody/job-rejected/custody/evidence/control-K1.txt
  - tests/fixtures/custody/job-rejected/custody/evidence/control-K2.txt
  - tests/fixtures/custody/job-rejected/custody/evidence/harness-eval-a.log
  - tests/fixtures/custody/job-rejected/custody/evidence/harness-maker-fixture.log
  - tests/fixtures/custody/job-rejected/custody/evidence/pass-a-D1.txt
  - tests/fixtures/custody/job-rejected/custody/evidence/pass-a-D2.txt
  - tests/fixtures/custody/job-rejected/custody/instrument/rubric.md
  - tests/fixtures/custody/job-rejected/custody/instrument/runner.py
  - tests/fixtures/custody/job-rejected/iteration-1-eval-record.json
  - tests/fixtures/custody/job-rejected/passes/pass-a.json
  - tests/fixtures/custody/job-emitted/README.md
  - tests/fixtures/custody/job-emitted/packet.json
  - tests/fixtures/custody/job-emitted/inputs/custody.json
  - tests/fixtures/custody/job-emitted/inputs/custody-events.jsonl
  - tests/fixtures/custody/job-emitted/inputs/run-1.json
  - tests/fixtures/custody/job-emitted/custody/bar.md
  - tests/fixtures/custody/job-emitted/custody/method.md
  - tests/fixtures/custody/job-emitted/custody/controls/K1-clean.md
  - tests/fixtures/custody/job-emitted/custody/controls/K2-planted.md
  - tests/fixtures/custody/job-emitted/custody/evidence/control-K1.txt
  - tests/fixtures/custody/job-emitted/custody/evidence/control-K2.txt
  - tests/fixtures/custody/job-emitted/custody/evidence/harness-eval-a.log
  - tests/fixtures/custody/job-emitted/custody/evidence/harness-maker-fixture.log
  - tests/fixtures/custody/job-emitted/custody/evidence/pass-a-D1.txt
  - tests/fixtures/custody/job-emitted/custody/evidence/pass-a-D2.txt
  - tests/fixtures/custody/job-emitted/custody/instrument/rubric.md
  - tests/fixtures/custody/job-emitted/custody/instrument/runner.py
  - tests/fixtures/custody/job-emitted/iteration-1-eval-record.json
  - tests/fixtures/custody/job-emitted/passes/pass-a.json
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIX_DIR = REPO / "tests" / "fixtures" / "custody"
REFUSAL_NAME = "job-rejected"
EMIT_NAME = "job-emitted"
BASE_COMMIT = "09c2072"
BRANCH = "feat/evaluator-harness-log"

# Seats that write harness logs. A model-seat log must either carry NO logger times
# (the refusal fixture) or BOTH sent_at and received_at on every call (the emit fixture).
# Deterministic/script seats are not covered by this rule.
MODEL_SEATS = {"evaluator", "maker"}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    out = []
    if not path.is_file():
        return out
    for n, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not ln.strip():
            continue
        try:
            out.append(json.loads(ln))
        except ValueError as exc:
            raise AssertionError(f"{path}:{n} is not valid JSON: {exc}") from None
    return out


def _harness_calls(path: Path) -> list[dict]:
    """Calls from a harness log (JSON list, single object, or JSON Lines)."""
    if not path.is_file():
        raise AssertionError(f"harness log missing: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except ValueError:
        items = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
    else:
        items = doc if isinstance(doc, list) else [doc]
    return [it for it in items if isinstance(it, dict) and "request" in it]


def _clean_checkout(dest: Path) -> Path:
    """A throwaway clean commit of this working tree, so emit_custody.py can run."""
    dest.mkdir(parents=True, exist_ok=True)
    g = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-co", "--exclude-standard", "-z"],
        capture_output=True, text=True,
    )
    names = [n for n in g.stdout.split("\0") if n] if g.returncode == 0 else []
    if not names:
        raise AssertionError("could not list files for a clean checkout")
    for n in names:
        src = REPO / n
        if src.is_file():
            (dest / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / n)
    git = ["git", "-C", str(dest), "-c", "user.name=test", "-c", "user.email=test@localhost",
           "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "clean checkout for fixture-shape bar"]):
        subprocess.run(git + args, capture_output=True, check=True)
    return dest


def _run_emit(job: Path, checkout: Path, extra: tuple[str, ...] = ()) -> tuple[int, str]:
    cmd = [sys.executable, str(checkout / "kit" / "emit_custody.py"),
           "--job-dir", str(job), *extra]
    raw_env = subprocess.check_output(["env"]).decode().splitlines()
    env = {}
    for ln in raw_env:
        if "=" in ln:
            k, v = ln.split("=", 1)
            env[k] = v
    clean = {k: v for k, v in env.items() if k != "CUSTODY_DIR"}
    r = subprocess.run(cmd, cwd=str(checkout), capture_output=True, text=True, env=clean)
    return r.returncode, r.stdout + r.stderr


class FixtureShapeBar(unittest.TestCase):
    """Shape checks for every fixture under tests/fixtures/custody/."""

    @classmethod
    def setUpClass(cls):
        cls.td = Path(tempfile.mkdtemp(prefix="plumbline-fixture-shape-"))
        cls.checkout = _clean_checkout(cls.td / "tree-clean")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.td, ignore_errors=True)

    def _fixture_jobs(self) -> dict[str, Path]:
        """Every top-level fixture directory that looks like a job."""
        jobs = {}
        for d in sorted(FIX_DIR.iterdir()):
            if not d.is_dir():
                continue
            if (d / "packet.json").is_file() and (d / "inputs" / "custody.json").is_file():
                jobs[d.name] = d
        return jobs

    def _ledger_lines(self, job: Path) -> list[dict]:
        return _read_jsonl(job / "inputs" / "custody-events.jsonl")

    def _harness_logs(self, job: Path) -> dict[str, Path]:
        ev_dir = job / "custody" / "evidence"
        logs = {}
        for p in ev_dir.glob("harness-*.log"):
            logs[p.name] = p
        return logs

    def test_01_branch_and_base_are_recorded(self):
        """The bar records what it was graded against, so the record cannot be ambiguous."""
        text = Path(__file__).read_text(encoding="utf-8")
        self.assertIn(BRANCH, text)
        self.assertIn(BASE_COMMIT, text)

    def test_02_ledger_lines_declare_a_writer(self):
        """Every ledger line must declare a writer: tool, hand, or a tool identifier."""
        for name, job in self._fixture_jobs().items():
            with self.subTest(fixture=name):
                for n, e in enumerate(self._ledger_lines(job), 1):
                    w = e.get("writer")
                    self.assertIsInstance(w, str, f"{name}/inputs/custody-events.jsonl:{n} has no writer")
                    self.assertTrue(w, f"{name}/inputs/custody-events.jsonl:{n} writer is empty")

    def test_03_dispose_lines_name_who_and_what(self):
        """A dispose event is not a legal dispose unless it names by and state."""
        for name, job in self._fixture_jobs().items():
            with self.subTest(fixture=name):
                for n, e in enumerate(self._ledger_lines(job), 1):
                    if e.get("event") != "dispose":
                        continue
                    self.assertIsInstance(e.get("by"), str,
                                        f"{name}/inputs/custody-events.jsonl:{n} dispose has no `by`")
                    self.assertIsInstance(e.get("state"), str,
                                        f"{name}/inputs/custody-events.jsonl:{n} dispose has no `state`")
                    self.assertTrue(e["by"], f"{name}/inputs/custody-events.jsonl:{n} dispose.by is empty")
                    self.assertIn(e["state"], {"given", "declined"},
                                  f"{name}/inputs/custody-events.jsonl:{n} dispose.state is unexpected")

    def test_04_no_ledger_line_claims_hand_without_reason(self):
        """In committed fixtures, `writer: hand` is not used; fixtures are tool-written stories."""
        for name, job in self._fixture_jobs().items():
            with self.subTest(fixture=name):
                for n, e in enumerate(self._ledger_lines(job), 1):
                    w = e.get("writer")
                    if w == "hand":
                        self.fail(f"{name}/inputs/custody-events.jsonl:{n} uses writer:hand in a committed fixture")

    def test_05_refusal_fixture_logs_carry_no_logger_times(self):
        """job-rejected exists to test D6/D7: a model evaluator with no logger times refuses.
        Its harness logs must therefore carry only server times."""
        jobs = self._fixture_jobs()
        self.assertIn(REFUSAL_NAME, jobs, f"the refusal fixture {REFUSAL_NAME!r} must exist")
        job = jobs[REFUSAL_NAME]
        logs = self._harness_logs(job)
        self.assertTrue(logs, f"{REFUSAL_NAME} has no harness logs")
        for log_name, log_path in logs.items():
            calls = _harness_calls(log_path)
            self.assertTrue(calls, f"{log_name} has no calls")
            with self.subTest(fixture=REFUSAL_NAME, log=log_name):
                for c in calls:
                    self.assertNotIn("sent_at", c,
                                     f"{log_name} call {c.get('call')} carries a logger sent_at")
                    self.assertNotIn("received_at", c,
                                     f"{log_name} call {c.get('call')} carries a logger received_at")

    def test_06_emit_fixture_exists(self):
        """A separate emit fixture is required so no single fixture is asked to be both."""
        jobs = self._fixture_jobs()
        self.assertIn(EMIT_NAME, jobs,
                      f"the emit fixture {EMIT_NAME!r} must exist as a separate directory")

    def test_07_emit_fixture_logs_carry_logger_times(self):
        """job-emitted exists for tests that need a record: every model-seat call must carry
        both sent_at and received_at from the logger."""
        jobs = self._fixture_jobs()
        if EMIT_NAME not in jobs:
            self.skipTest(f"{EMIT_NAME!r} does not exist yet")
        job = jobs[EMIT_NAME]
        logs = self._harness_logs(job)
        self.assertTrue(logs, f"{EMIT_NAME} has no harness logs")
        for log_name, log_path in logs.items():
            calls = _harness_calls(log_path)
            self.assertTrue(calls, f"{log_name} has no calls")
            with self.subTest(fixture=EMIT_NAME, log=log_name):
                for c in calls:
                    self.assertIn("sent_at", c,
                                  f"{log_name} call {c.get('call')} is missing logger sent_at")
                    self.assertIn("received_at", c,
                                  f"{log_name} call {c.get('call')} is missing logger received_at")

    def test_08_emit_fixture_can_produce_a_record(self):
        """The emit fixture must actually emit; if it does not, the shape is still wrong."""
        jobs = self._fixture_jobs()
        if EMIT_NAME not in jobs:
            self.skipTest(f"{EMIT_NAME!r} does not exist yet")
        emit_job = self._fixture_jobs()[EMIT_NAME]
        out_path = self.td / "emit-record.custody.json"
        rc, out = _run_emit(emit_job, self.checkout, ("--out", str(out_path), "--allow-hand-times"))
        self.assertEqual(rc, 0, f"{EMIT_NAME} did not emit a record:\n{out}")
        self.assertTrue(out_path.is_file(), "no record was written")

    def test_09_refusal_fixture_refuses_a_model_evaluator_with_no_harness_log(self):
        """D6/D7: deleting the evaluator log from the refusal fixture must refuse, naming the log.
        This is the positive proof that the refusal fixture is fit for its purpose."""
        jobs = self._fixture_jobs()
        if REFUSAL_NAME not in jobs:
            self.skipTest(f"{REFUSAL_NAME!r} does not exist")
        job = self.td / "refusal-test"
        shutil.copytree(jobs[REFUSAL_NAME], job)
        eval_log = job / "custody" / "evidence" / "harness-eval-a.log"
        self.assertTrue(eval_log.is_file(), "refusal fixture has no evaluator log")
        eval_log.unlink()
        out_path = self.td / "refusal-test.custody.json"
        rc, out = _run_emit(job, self.checkout, ("--out", str(out_path)))
        self.assertNotEqual(rc, 0, "a model evaluator with no harness log must refuse the record")
        self.assertIn("harness", out, "the refusal does not name the harness log")
        self.assertFalse(out_path.exists(), "a refusal must write no record")

    def test_10_stamping_the_refusal_fixture_breaks_the_refusal_check(self):
        """Rule 1 as a positive demonstration: if you stamp the refusal fixture's log, the same
        refusal test no longer refuses for the missing-logger-times reason. This is why a
        single fixture cannot serve both purposes."""
        jobs = self._fixture_jobs()
        if REFUSAL_NAME not in jobs:
            self.skipTest(f"{REFUSAL_NAME!r} does not exist")
        job = self.td / "stamped-test"
        shutil.copytree(jobs[REFUSAL_NAME], job)
        for log_path in (job / "custody" / "evidence").glob("harness-*.log"):
            calls = _harness_calls(log_path)
            for c in calls:
                at = None
                if isinstance(c.get("response"), dict) and isinstance(c["response"].get("created"), (int, float)):
                    from datetime import datetime, timezone
                    at = datetime.fromtimestamp(c["response"]["created"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                else:
                    hdrs = c.get("response_headers") or c.get("headers") or {}
                    d = hdrs.get("Date") or hdrs.get("date")
                    if d:
                        from email.utils import parsedate_to_datetime
                        from datetime import timezone
                        at = parsedate_to_datetime(d).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if at:
                    c["sent_at"] = at
                    c["received_at"] = at
            text = json.dumps(calls, indent=2) + "\n"
            log_path.write_text(text, encoding="utf-8")
        out_path = self.td / "stamped-test.custody.json"
        rc, out = _run_emit(job, self.checkout, ("--out", str(out_path), "--allow-hand-times"))
        # A stamped refusal fixture must NOT refuse for the missing-logger-times condition.
        # (It may still refuse for other fixture reasons; we only check the logger-time reason.)
        self.assertFalse(rc != 0 and "harness log" in out and "sent_at" in out,
                         "stamping the refusal fixture still refused for missing logger times; "
                         "no single fixture can serve both purposes")


if __name__ == "__main__":
    unittest.main()
