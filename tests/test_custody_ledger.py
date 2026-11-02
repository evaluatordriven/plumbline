import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "kit"))
import custody_ledger as L  # noqa: E402
import custody_history as H  # noqa: E402

# 2026-01-01T00:00:00Z, the epoch of the response `created` times the log fixtures carry.
CREATED = 1767225600


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.job = Path(self.tmp.name) / "job"
        (self.job / "inputs").mkdir(parents=True)
        self.ci = {"custody_inputs": "plumbline/custody-inputs/v1", "bar": {}}
        self.write_ci()
        self.events = self.job / "inputs" / "custody-events.jsonl"
        self.events.touch()
        self.bar = self.job / "custody" / "bar.md"
        self.bar.parent.mkdir()
        self.bar.write_text("bar\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def write_ci(self):
        (self.job / "inputs" / "custody.json").write_text(
            json.dumps(self.ci, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def read_events(self):
        return [json.loads(x) for x in self.events.read_text(encoding="utf-8").splitlines() if x.strip()]

    def run_cmd(self, *args):
        return L.main(list(args))

    def run_capture(self, *args):
        """Run a command, catching argparse's SystemExit, and return (code, stderr text)."""
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                code = L.main(list(args))
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 2
        return code, err.getvalue()

    def test_writer_stamp_on_every_line(self):
        self.assertEqual(self.run_cmd("freeze", "--job-dir", str(self.job)), 0)
        ev = self.read_events()[-1]
        sha12 = sha256((ROOT / "kit" / "custody_ledger.py").read_bytes()).hexdigest()[:12]
        self.assertEqual(ev["writer"], f"kit/custody_ledger.py@{sha12}")
        self.assertIn("at", ev)
        # base dispose also carries it
        self.assertEqual(self.run_cmd("dispose", "--job-dir", str(self.job), "--by", "Owner"), 0)
        ev = self.read_events()[-1]
        self.assertEqual(ev["writer"], f"kit/custody_ledger.py@{sha12}")

    def test_generation_open_close(self):
        self.assertEqual(self.run_cmd("freeze", "--job-dir", str(self.job)), 0)
        prompt = self.job / "prompt.md"
        prompt.write_text("prompt\n", encoding="utf-8")
        before = self.events.read_bytes()
        self.assertEqual(self.run_cmd("generation", "open", "--job-dir", str(self.job),
                                      "--seat", "maker", "--prompt", str(prompt)), 0)
        after = self.events.read_bytes()
        self.assertTrue(after.startswith(before))
        self.assertEqual(len(self.read_events()), 2)
        ev = self.read_events()[-1]
        self.assertEqual(ev["action"], "open")
        self.assertEqual(ev["n"], 1)
        self.assertEqual(ev["prompt_sha256"], sha256(prompt.read_bytes()).hexdigest())
        # second open refused, nothing appended
        before = self.events.read_bytes()
        self.assertNotEqual(self.run_cmd("generation", "open", "--job-dir", str(self.job),
                                         "--seat", "maker", "--prompt", str(prompt)), 0)
        self.assertEqual(self.events.read_bytes(), before)
        # close
        self.assertEqual(self.run_cmd("generation", "close", "--job-dir", str(self.job),
                                      "--seat", "maker", "--n", "1"), 0)
        self.assertEqual(self.read_events()[-1]["action"], "close")
        # close again refused
        before = self.events.read_bytes()
        self.assertNotEqual(self.run_cmd("generation", "close", "--job-dir", str(self.job),
                                         "--seat", "maker", "--n", "1"), 0)
        self.assertEqual(self.events.read_bytes(), before)
        # next open n=2
        self.assertEqual(self.run_cmd("generation", "open", "--job-dir", str(self.job),
                                      "--seat", "maker", "--prompt", str(prompt)), 0)
        self.assertEqual(self.read_events()[-1]["n"], 2)

    def test_evaluation_sha_and_summary(self):
        verdict = self.job / "verdict.txt"
        verdict.write_text("v\n", encoding="utf-8")
        self.assertEqual(self.run_cmd("evaluation", "--job-dir", str(self.job), "--batch", "B1",
                                      "--evaluator", "e1", "--verdict", str(verdict)), 0)
        ev = self.read_events()[-1]
        self.assertEqual(ev["verdict_sha256"], sha256(verdict.read_bytes()).hexdigest())
        # missing verdict refused
        before = self.events.read_bytes()
        self.assertNotEqual(self.run_cmd("evaluation", "--job-dir", str(self.job), "--batch", "B1",
                                         "--evaluator", "e1", "--verdict", str(self.job / "nope")), 0)
        self.assertEqual(self.events.read_bytes(), before)
        # summary with stamp
        summary = self.job / "summary.json"
        summary.write_text(json.dumps({
            "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:01:00Z",
            "writer": "tools/edi/x@abc",
        }), encoding="utf-8")
        self.assertEqual(self.run_cmd("evaluation", "--job-dir", str(self.job), "--batch", "B2",
                                      "--evaluator", "e1", "--verdict", str(verdict),
                                      "--summary", str(summary)), 0)
        ev = self.read_events()[-1]
        self.assertEqual(ev["summary_writer"], "tools/edi/x@abc")
        self.assertEqual(ev["started_at"], "2026-01-01T00:00:00Z")
        # summary without stamp refused
        bad = self.job / "bad.json"
        bad.write_text("{}", encoding="utf-8")
        before = self.events.read_bytes()
        self.assertNotEqual(self.run_cmd("evaluation", "--job-dir", str(self.job), "--batch", "B3",
                                         "--evaluator", "e1", "--verdict", str(verdict),
                                         "--summary", str(bad)), 0)
        self.assertEqual(self.events.read_bytes(), before)

    def test_evaluation_summary_without_verdict(self):
        """L1(a): `evaluation --summary FILE` with no --verdict appends the stamped line (F1d)."""
        summary = self.job / "summary.json"
        summary.write_text(json.dumps({
            "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:01:00Z",
            "writer": "tools/edi/x@abc",
        }), encoding="utf-8")
        before = self.events.read_bytes()
        self.assertEqual(self.run_cmd("evaluation", "--job-dir", str(self.job), "--batch", "B1",
                                      "--evaluator", "e1", "--summary", str(summary)), 0)
        after = self.events.read_bytes()
        self.assertTrue(after.startswith(before))
        ev = self.read_events()[-1]
        sha = sha256(summary.read_bytes()).hexdigest()
        self.assertEqual(ev["event"], "evaluation")
        self.assertEqual(ev["verdict_file"], "summary.json")
        self.assertEqual(ev["verdict_sha256"], sha)
        self.assertEqual(ev["summary_file"], "summary.json")
        self.assertEqual(ev["summary_sha256"], sha)
        self.assertEqual(ev["summary_writer"], "tools/edi/x@abc")
        self.assertEqual(ev["started_at"], "2026-01-01T00:00:00Z")
        self.assertEqual(ev["finished_at"], "2026-01-01T00:01:00Z")
        self.assertEqual(ev["writer"], L.writer_stamp())
        # a summary with no stamp is refused with a REFUSED: line, and nothing is appended
        bad = self.job / "bad.json"
        bad.write_text(json.dumps({"started_at": "2026-01-01T00:00:00Z"}), encoding="utf-8")
        before = self.events.read_bytes()
        code, err = self.run_capture("evaluation", "--job-dir", str(self.job), "--batch", "B2",
                                     "--evaluator", "e1", "--summary", str(bad))
        self.assertEqual(code, 3, err)
        self.assertTrue(any(ln.startswith("REFUSED:") for ln in err.splitlines()), err)
        self.assertEqual(self.events.read_bytes(), before)

    def test_usage_errors_refuse_with_refused_line(self):
        """L1(b): every usage error, argparse errors included, exits 2 with a `REFUSED:` line, writing nothing."""
        before_ev = self.events.read_bytes()
        before_ci = (self.job / "inputs" / "custody.json").read_bytes()
        cases = [
            ["nonsense", "--job-dir", str(self.job)],
            ["freeze"],
            ["generation", "close", "--job-dir", str(self.job), "--seat", "maker", "--n", "x"],
            ["evaluation", "--job-dir", str(self.job), "--batch", "B1"],
            ["evaluation", "--job-dir", str(self.job), "--batch", "B1", "--evaluator", "e1"],
            ["dispose", "--job-dir", str(self.job)],
        ]
        for args in cases:
            code, err = self.run_capture(*args)
            self.assertEqual(code, 2, (args, err))
            self.assertTrue(any(ln.startswith("REFUSED:") for ln in err.splitlines()), (args, err))
            self.assertEqual(self.events.read_bytes(), before_ev, args)
            self.assertEqual((self.job / "inputs" / "custody.json").read_bytes(), before_ci, args)

    def test_amendment_bounds(self):
        self.assertEqual(self.run_cmd("freeze", "--job-dir", str(self.job)), 0)
        frozen = self.read_events()[-1]["at"]
        amend = self.job / "amend.md"
        amend.write_text("a\n", encoding="utf-8")
        now = datetime.now(timezone.utc)
        # before freeze
        before = self.events.read_bytes()
        self.assertNotEqual(self.run_cmd("amendment", "--job-dir", str(self.job), "--file", str(amend),
                                         "--quote", "q", "--channel", "c",
                                         "--said-at", iso(now - timedelta(days=1))), 0)
        self.assertEqual(self.events.read_bytes(), before)
        # after now
        self.assertNotEqual(self.run_cmd("amendment", "--job-dir", str(self.job), "--file", str(amend),
                                         "--quote", "q", "--channel", "c",
                                         "--said-at", iso(now + timedelta(days=1))), 0)
        # inside custody
        inside = self.job / "custody" / "amend.md"
        inside.write_text("a\n", encoding="utf-8")
        self.assertNotEqual(self.run_cmd("amendment", "--job-dir", str(self.job), "--file", str(inside),
                                         "--quote", "q", "--channel", "c", "--said-at", frozen), 0)
        # accepted at the freeze bound
        self.assertEqual(self.run_cmd("amendment", "--job-dir", str(self.job), "--file", str(amend),
                                      "--quote", "q", "--channel", "c", "--said-at", frozen), 0)
        ev = self.read_events()[-1]
        self.assertEqual(ev["quote"], "q")
        self.assertEqual(ev["file_sha256"], sha256(amend.read_bytes()).hexdigest())

    def test_relay_bounds_and_verbatim(self):
        self.assertEqual(self.run_cmd("freeze", "--job-dir", str(self.job)), 0)
        frozen = self.read_events()[-1]["at"]
        now = datetime.now(timezone.utc)
        before = self.events.read_bytes()
        self.assertNotEqual(self.run_cmd("relay", "--job-dir", str(self.job), "--quote", "q",
                                         "--from", "BOT", "--source-chat", "c",
                                         "--source-at", iso(now - timedelta(days=1))), 0)
        self.assertEqual(self.events.read_bytes(), before)
        self.assertNotEqual(self.run_cmd("relay", "--job-dir", str(self.job), "--quote", "q",
                                         "--from", "BOT", "--source-chat", "c",
                                         "--source-at", iso(now + timedelta(days=1))), 0)
        self.assertEqual(self.run_cmd("relay", "--job-dir", str(self.job), "--quote", " q ",
                                      "--from", "BOT", "--source-chat", "c",
                                      "--source-at", frozen), 0)
        ev = self.read_events()[-1]
        self.assertEqual(ev["quote"], " q ")
        self.assertEqual(ev["kind"], "relay")

    def test_spend_bounds_and_stamp(self):
        now = datetime.now(timezone.utc)
        settle_at = iso(now - timedelta(minutes=10))
        ledger = self.job / "spend.jsonl"
        ledger.write_text(json.dumps({"event": "settle", "at": settle_at, "cost_usd": 0.01}) + "\n",
                          encoding="utf-8")
        reading = self.job / "reading.json"
        # 1 min after settle: refused
        reading.write_text(json.dumps({
            "read_at": iso(now - timedelta(minutes=9)),
            "writer": "tools/edi/or_call.py@abc",
            "key_delta_usd": 0.02,
        }), encoding="utf-8")
        before = self.events.read_bytes()
        self.assertNotEqual(self.run_cmd("spend", "--job-dir", str(self.job), "--spend-ledger", str(ledger),
                                         "--key-reading", str(reading)), 0)
        self.assertEqual(self.events.read_bytes(), before)
        # 4 min after settle: accepted
        reading.write_text(json.dumps({
            "read_at": iso(now - timedelta(minutes=6)),
            "writer": "tools/edi/or_call.py@abc",
            "key_delta_usd": 0.02,
        }), encoding="utf-8")
        self.assertEqual(self.run_cmd("spend", "--job-dir", str(self.job), "--spend-ledger", str(ledger),
                                      "--key-reading", str(reading)), 0)
        ev = self.read_events()[-1]
        self.assertEqual(ev["ledger_sum_usd"], 0.01)
        self.assertEqual(ev["key_delta_usd"], 0.02)
        self.assertEqual(ev["total_usd"], 0.02)
        self.assertEqual(ev["spend_ledger_sha256"], sha256(ledger.read_bytes()).hexdigest())
        # no stamp refused
        reading.write_text(json.dumps({"read_at": iso(now - timedelta(minutes=5))}), encoding="utf-8")
        before = self.events.read_bytes()
        self.assertNotEqual(self.run_cmd("spend", "--job-dir", str(self.job), "--spend-ledger", str(ledger),
                                         "--key-reading", str(reading)), 0)
        self.assertEqual(self.events.read_bytes(), before)

    def test_dispose_bounds(self):
        now = datetime.now(timezone.utc)
        last = now - timedelta(minutes=10)
        self.events.write_text(json.dumps({
            "event": "evaluation", "batch": "B", "evaluator": "e1",
            "verdict_file": "v", "verdict_sha256": "0" * 64,
            "started_at": iso(last), "finished_at": iso(last), "at": iso(last),
            "writer": "kit/custody_ledger.py@abc",
        }) + "\n", encoding="utf-8")
        before = self.events.read_bytes()
        self.assertNotEqual(self.run_cmd("dispose", "--job-dir", str(self.job), "--by", "Owner",
                                         "--state", "given",
                                         "--decided-at", iso(last - timedelta(seconds=1)),
                                         "--decided-source", "chat"), 0)
        self.assertEqual(self.events.read_bytes(), before)
        self.assertNotEqual(self.run_cmd("dispose", "--job-dir", str(self.job), "--by", "Owner",
                                         "--state", "given",
                                         "--decided-at", iso(now + timedelta(days=1)),
                                         "--decided-source", "chat"), 0)
        self.assertEqual(self.run_cmd("dispose", "--job-dir", str(self.job), "--by", "Owner",
                                      "--state", "given",
                                      "--decided-at", iso(last),
                                      "--decided-source", "chat"), 0)
        ev = self.read_events()[-1]
        self.assertEqual(ev["decided_at"], iso(last))
        self.assertEqual(ev["decided_source"], "chat")
        ci = json.loads((self.job / "inputs" / "custody.json").read_text(encoding="utf-8"))
        self.assertEqual(ci["disposition"]["at"], iso(last))
        self.assertEqual(ci["disposition"]["state"], "given")

    def test_tolerance_unchanged(self):
        self.assertEqual(H.TOLERANCE_S, 60)

    def test_fill_logger_times_does_not_write(self):
        log = self.job / "harness.log"
        content = json.dumps({
            "call": "c1",
            "request": {"url": "https://openrouter.ai/api/v1/chat/completions"},
            "response": {"created": CREATED},
            "response_headers": {"Date": "Thu, 01 Jan 2026 00:00:00 GMT"},
        }) + "\n"
        log.write_text(content, encoding="utf-8")
        before = log.read_bytes()
        self.assertFalse(H.fill_logger_times(log))
        self.assertEqual(log.read_bytes(), before)

    def test_hand_time_entries_for_missing_logger_times(self):
        log = self.job / "harness.log"
        content = json.dumps({
            "call": "c1",
            "request": {"url": "https://openrouter.ai/api/v1/chat/completions"},
            "response": {"created": CREATED},
            "response_headers": {"Date": "Thu, 01 Jan 2026 00:00:00 GMT"},
        }) + "\n"
        log.write_text(content, encoding="utf-8")
        ref = H.Refusals()
        calls = H.read_log(log, ref, "maker")
        self.assertEqual(len(calls), 1)
        entries = calls[0].hand_time_entries()
        fields = {e["field"]: e for e in entries}
        self.assertIn("harness.log#c1.sent_at", fields)
        self.assertIn("harness.log#c1.received_at", fields)
        self.assertEqual(fields["harness.log#c1.sent_at"]["source"], "response-created")
        self.assertEqual(fields["harness.log#c1.received_at"]["source"], "server-header")
        self.assertEqual(fields["harness.log#c1.sent_at"]["file"], "harness.log")

    def test_read_log_accepts_path_alone(self):
        """L2 (P1): read_log(path) reads the calls without a Refusals or a who."""
        log = self.job / "harness.log"
        log.write_text(json.dumps({
            "call": "c1",
            "request": {"url": "https://api.deepinfra.com/v1/openai/chat/completions"},
            "sent_at": "2026-01-01T00:00:00Z",
            "received_at": "2026-01-01T00:00:05Z",
            "response": {"created": CREATED},
        }) + "\n", encoding="utf-8")
        calls = H.read_log(log)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "c1")
        self.assertEqual(H.iso(calls[0].received), "2026-01-01T00:00:05Z")
        # an unreadable log still returns [] rather than raising
        self.assertEqual(H.read_log(self.job / "missing.log"), [])

    def test_read_log_accepts_str_path(self):
        """P1: a frozen caller passes the log path as a string; read_log accepts a str as well as a Path."""
        log = self.job / "harness.log"
        log.write_text(json.dumps({
            "call": "c1",
            "request": {"url": "https://api.deepinfra.com/v1/openai/chat/completions"},
            "sent_at": "2026-01-01T00:00:00Z",
            "received_at": "2026-01-01T00:00:05Z",
            "response": {"created": CREATED},
        }) + "\n", encoding="utf-8")
        calls = H.read_log(str(log))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "c1")
        self.assertEqual(H.iso(calls[0].received), "2026-01-01T00:00:05Z")
        # a string path that does not exist still returns [] rather than raising
        self.assertEqual(H.read_log(str(self.job / "missing.log")), [])


if __name__ == "__main__":
    unittest.main()
