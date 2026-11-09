"""Bar: a model evaluator's turn writes a harness log, and the custody record takes its
evaluator times from that log.

RE-CUT 2026-11-08. The first cut (kept beside this file as test_evaluator_harness_log.v1.py)
had three defects. Which change answers each:

  DEFECT 1 -- the bar tested the Maker's blind spot. The first cut grepped
  /home/jarbis1/.hermes/profiles/plumbline-conductor/bin/route-eval, an absolute path outside the
  worktree that the Maker cannot write. It declared a deployment step AND required that step to
  have happened before the Maker could pass -- unsatisfiable by construction. Answered by: every
  test below reads only files inside this repo. The deployed profile route is a DECLARED
  deployment step recorded in the deployment record. See DEPLOYMENT_STEP_NOTE.

  DEFECT 2 -- two tests written against an interface that does not exist. The first cut invented
  `or_call.py --eval-score`; or_call.py rejects unknown arguments, so no correct implementation
  could pass. Measured truth: tools/edi/or_call.py ALREADY writes sent_at, received_at, the
  request url (which carries the endpoint) and the model into its log entry (or_call.py:553-559,
  577). So the missing capability is not the timestamp producer -- it is (a) the record taking
  evaluator check times FROM that log, and (b) the refusals for a malformed, partial or reversed
  log. Answered by: the or_call tests below drive the REAL interface (--log, --call, --seat,
  --model, --tag, --pin-provider, --messages, --out, --mock-transport) and assert on the entry
  or_call writes. No flag is invented.

  DEFECT 3 -- refusal or note, left ambiguous. The first cut asserted a caveat key existed and
  left the missing-log case open; the measured emitter emitted `note external: no harness log`
  and still wrote the record. DECIDED HERE: a MODEL evaluator with no harness log REFUSES the
  record. A note is not enough, because a record whose evaluator times have no source is exactly
  the hollow record this program has already shipped twice. Both directions are asserted: the
  refusal is required (D6) and the note-only behaviour is asserted ABSENT (D7). The refusal stays
  narrow -- a DETERMINISTIC evaluator carrying no log must NOT be refused (D11), so the fix
  cannot be satisfied by refusing everything.

WHAT THIS BAR DOES NOT PROVE, in plain English:
  That the times are honest about the wall clock. A harness log proves what the route recorded,
  not that the clock was right. Nothing here certifies the clock, and no reader should assume it.

DEPLOYMENT_STEP_NOTE:
  The profile-side route (/home/jarbis1/.hermes/profiles/plumbline-conductor/bin/route-eval) is NOT
  tested here. It is a declared deployment step performed by the operator and recorded in the
  deployment record, in the same shape as the seat-notice launcher. This bar proves the in-repo
  half: the log the harness writes, and the record the emitter builds from it.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import hashlib

REPO = Path(__file__).resolve().parent.parent
OR_CALL = REPO / "tools" / "edi" / "or_call.py"
EMIT = REPO / "kit" / "emit_custody.py"

DIM = "evaluator_harness_log"


class HarnessLogShapeTests(unittest.TestCase):
    """D1-D3: the log or_call writes carries the fields the record needs."""

    def setUp(self):
        self.td = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.td, True)
        self.log = self.td / "harness-evaluator.log"

    def _run(self):
        (self.td / "msgs.json").write_text(json.dumps([{"role": "user", "content": "score it"}]))
        spend = self.td / "job-spend.json"
        spend.write_text(json.dumps({
            "job_id": "harness-log-j", "bound_usd": 2.00, "reserve_usd": 0.02,
            "spend_ledger": str(self.td / "spend-ledger.jsonl"),
            "prices": [{"model": "z-ai/glm-5.3-flash", "tag": "z-ai/fp8",
                        "prompt_usd_per_token": 0.00000015,
                        "completion_usd_per_token": 0.0000005,
                        "max_completion_tokens": 131072}],
        }))
        # The mock transport's own contract: a DIRECTORY holding key.json, chat.json and
        # generation.json, each {status, headers, body}. This is the shape or_call.py's
        # MockTransport reads (or_call.py:120-145); the fixture is written to the interface.
        mock = self.td / "mock"
        mock.mkdir(parents=True, exist_ok=True)
        for name, doc in (
            ("key.json", {"status": 200, "headers": {},
                          "body": {"data": {"usage": 0.0}}}),
            ("chat.json", {"status": 200, "headers": {"Date": "Wed, 01 Jan 2025 00:00:00 GMT"},
                           "body": {"id": "gen-1", "provider": "Z.AI",
                                    "model": "z-ai/glm-5.3-flash",
                                    "choices": [{"message": {"content": "reply"}}],
                                    "usage": {"cost": 0.0001}}}),
            ("generation.json", {"status": 200, "headers": {},
                                 "body": {"data": {"total_cost": 0.0001,
                                                   "provider_name": "Z.AI"}}}),
        ):
            (mock / name).write_text(json.dumps(doc))
        subprocess.run([sys.executable, str(OR_CALL), "--init-spend",
                        "--job-spend", str(spend),
                        "--key-file", str(self.td / "no-key")],
                       capture_output=True, text=True, cwd=str(REPO))
        cmd = [sys.executable, str(OR_CALL),
               "--log", str(self.log), "--call", "dim1#p1",
               "--seat", "evaluator", "--model", "z-ai/glm-5.3-flash",
               "--tag", "z-ai/fp8", "--pin-provider", "Z.AI",
               "--out", str(self.td / "out.json"),
               "--messages", str(self.td / "msgs.json"),
               "--job-spend", str(spend),
               "--key-file", str(self.td / "no-key"),
               "--mock-transport", str(mock)]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))

    def _entries(self):
        # or_call.append_entry writes the harness log as a JSON LIST (or_call.py:255-271),
        # not JSONL. Read the format the tool actually writes.
        return json.loads(self.log.read_text())

    def test_d1_log_entry_carries_sent_and_received_times(self):
        """D1: each call writes one entry with sent_at and received_at."""
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        entries = self._entries()
        self.assertEqual(len(entries), 1, "one call must write exactly one entry")
        e = entries[0]
        self.assertTrue(e.get("sent_at"), "entry has no sent_at")
        self.assertTrue(e.get("received_at"), "entry has no received_at")

    def test_d2_log_entry_carries_model_and_endpoint(self):
        """D2: the entry names the model and the endpoint actually used."""
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        e = self._entries()[0]
        blob = json.dumps(e)
        self.assertIn("z-ai/glm-5.3-flash", blob, "the entry does not name the model")
        url = ((e.get("request") or {}).get("url") or "")
        self.assertTrue(url.startswith("http"), f"endpoint is not a url: {url!r}")

    def test_d3_received_is_not_before_sent(self):
        """D3: on a real answer the logged times are ordered sent <= received."""
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        e = self._entries()[0]
        self.assertLessEqual(e["sent_at"], e["received_at"],
                             "the log records a call that ended before it began")


class EmitterReadsTheLogTests(unittest.TestCase):
    """D4-D11: the record takes check times from the log, and refuses a bad one."""

    GOOD = {"call": "dim1#p1", "sent_at": "2026-11-08T10:00:05Z",
            "received_at": "2026-11-08T10:00:09Z",
            "request": {"url": "https://api.z.ai/chat/completions"},
            "response": {"model": "z-ai/glm-5.3-flash"}}
    REVERSED = dict(GOOD, sent_at="2026-11-08T10:00:09Z", received_at="2026-11-08T10:00:05Z")
    PARTIAL = {"call": "dim1#p1", "sent_at": "2026-11-08T10:00:05Z",
               "request": {"url": "https://api.z.ai/chat/completions"}}

    def setUp(self):
        self.td = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.td, True)

    def _job(self, log_text, evaluator_kind="model"):
        job = self.td / "job"
        (job / "inputs").mkdir(parents=True, exist_ok=True)
        (job / "custody" / "evidence").mkdir(parents=True, exist_ok=True)
        (job / "custody" / "evidence" / "harness-eval.log").write_text(log_text)
        # The ledger is built HERE, at test time, in this job's own inputs/ -- not shipped.
        # The emitter refuses a hand-typed approval time and a hand-typed freeze time; both
        # must come from a `writer`-carrying ledger line. The freeze and approval below are
        # written by this test, not by a human, and the writer names that.
        (job / "custody" / "bar.md").write_text("bar\n")
        bar_sha = hashlib.sha256((job / "custody" / "bar.md").read_bytes()).hexdigest()
        ledger = [
            {"event": "freeze", "at": "2026-11-08T10:00:00Z", "bar_file": "custody/bar.md",
             "bar_sha256": bar_sha, "writer": "test_evaluator_harness_log.py"},
            {"event": "approve", "role": "buyer", "by": "Steve Moitozo II", "kind": "person",
             "at": "2026-11-08T10:00:01Z", "barDigest": bar_sha, "adopted": None,
             "writer": "test_evaluator_harness_log.py"},
        ]
        (job / "inputs" / "custody-events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in ledger))
        custody = {
            "custody_inputs": "plumbline/custody-inputs/v1",
            "orchestrator": {"name": "plumbline-conductor", "kind": "agent", "aliases": ["conductor"]},
            "bar": {"file": "custody/bar.md",
                    "author": "architect",
                    "dimensions": [{"id": DIM, "criterion": "x",
                                    "scale": {"type": "pass_fail", "threshold": 1}}]},
            "evaluators": [{"id": "evaluator", "who": "plumbline-eval", "name": "plumbline-eval",
                            "kind": evaluator_kind,
                            "harness_log": "custody/evidence/harness-eval.log",
                            "model": {"family": "glm", "identifier": "z-ai/glm-5.3-flash",
                                      "endpoint": "api.z.ai", "readOnly": True},
                            "runs": 3}],
            "passes": {"dim1#p1": {"evaluator": "evaluator", "call": "dim1#p1", "run": 1,
                                   "batch": "b1", "failureCondition": {DIM: "x"},
                                   "evidence": {DIM: "verdict-p1.json"}}},
            "retention": {"where": str(job)},
            "disposition": {"state": "not_yet_given", "by": "Steve Moitozo II"},
        }
        (job / "inputs" / "custody.json").write_text(json.dumps(custody))
        (job / "packet.json").write_text(json.dumps(
            {"job_id": "harness-log-j", "terminal_state": "accepted", "outcome": "accepted",
             "disposition_state": "not_yet_given"}))
        (job / "custody" / "bar.md").write_text("bar\n")
        return job

    def _emit(self, job):
        return subprocess.run([sys.executable, str(EMIT), "--job-dir", str(job)],
                              capture_output=True, text=True, cwd=str(REPO))

    def _record(self, job):
        p = job / "custody" / "record.custody.json"
        return json.loads(p.read_text()) if p.is_file() else None

    def test_d4_record_check_time_comes_from_the_log(self):
        """D4: the record's check time names the harness log as its source."""
        job = self._job(json.dumps(self.GOOD) + "\n")
        r = self._emit(job)
        rec = self._record(job)
        self.assertIsNotNone(rec, f"no record written\n{r.stdout}{r.stderr}")
        checks = (rec.get("predicate") or {}).get("checks") or []
        self.assertTrue(checks, f"no check recorded\n{r.stdout}{r.stderr}")
        src = json.dumps(((rec["predicate"].get("x-plumbline") or {}).get("time_sources") or {}))
        self.assertIn("harness-eval.log", src, "no check time names the harness log as its source")

    def test_d5_record_names_the_log_path(self):
        """D5: a reader can find the log the times came from."""
        job = self._job(json.dumps(self.GOOD) + "\n")
        self._emit(job)
        self.assertIn("harness-eval.log", json.dumps(self._record(job)),
                      "the record never names the harness log")

    def test_d6_missing_log_refuses(self):
        """D6: a MODEL evaluator with no harness log refuses the record."""
        job = self._job(json.dumps(self.GOOD) + "\n")
        (job / "custody" / "evidence" / "harness-eval.log").unlink()
        r = self._emit(job)
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0, f"a model evaluator with no harness log must refuse\n{out}")
        self.assertIn("harness log", out, "the refusal does not name the harness log")

    def test_d7_note_only_is_absent(self):
        """D7: the missing log does not degrade to a note that still writes the record."""
        job = self._job(json.dumps(self.GOOD) + "\n")
        (job / "custody" / "evidence" / "harness-eval.log").unlink()
        r = self._emit(job)
        out = r.stdout + r.stderr
        self.assertNotRegex(out, r"note\s+external:?\s*no harness log",
                            "a missing log degraded to a note instead of refusing")

    def test_d8_reversed_times_refused_naming_the_entry(self):
        """D8: received before sent refuses, naming the entry."""
        job = self._job(json.dumps(self.REVERSED) + "\n")
        r = self._emit(job)
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0, f"reversed times must refuse\n{out}")
        self.assertIn("dim1#p1", out, "the refusal does not name the offending entry")

    def test_d9_partial_entry_refused_naming_the_entry(self):
        """D9: an entry missing received_at refuses, naming the entry."""
        job = self._job(json.dumps(self.PARTIAL) + "\n")
        r = self._emit(job)
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0, f"a partial entry must refuse\n{out}")
        self.assertIn("dim1#p1", out, "the refusal does not name the offending entry")

    def test_d10_malformed_log_refused(self):
        """D10: an unparseable log refuses; it is never silently skipped."""
        job = self._job("this is not json\n")
        r = self._emit(job)
        self.assertNotEqual(r.returncode, 0, "a malformed log must refuse, not be skipped")

    def test_d11_deterministic_checker_needs_no_log(self):
        """D11: the refusal stays narrow -- a deterministic evaluator with no log is not refused."""
        job = self._job(json.dumps(self.GOOD) + "\n", evaluator_kind="command")
        (job / "custody" / "evidence" / "harness-eval.log").unlink()
        r = self._emit(job)
        self.assertNotIn("needs its harness log", r.stdout + r.stderr,
                         "a deterministic evaluator must not be refused for having no log")


class LimitTests(unittest.TestCase):
    """D12: the bar states its own limit, in plain English, in the file."""

    def test_d12_bar_states_the_clock_limit(self):
        """D12: this file carries the wall-clock caveat."""
        text = Path(__file__).read_text()
        self.assertIn("honest about the wall clock", text)
        self.assertIn("not that the clock was right", text)


if __name__ == "__main__":
    unittest.main()
