import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OR_CALL = ROOT / "tools" / "edi" / "or_call.py"


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def make_job(td: Path, bound: float = 1.0, reserve: float = 0.0):
    spend = td / "spend" / "ledger.jsonl"
    job = {
        "job_id": "test-job",
        "bound_usd": bound,
        "reserve_usd": reserve,
        "spend_ledger": str(spend),
        "prices": [{
            "model": "test/model",
            "tag": "test/fp8",
            "prompt_usd_per_token": 0.001,
            "completion_usd_per_token": 0.002,
            "max_completion_tokens": 100,
        }],
    }
    write_json(td / "job-spend.json", job)
    return job, td / "job-spend.json"


def make_messages(td: Path) -> None:
    write_json(td / "messages.json", [{"role": "user", "content": "hi"}])


def make_mock(mock: Path, usage: float = 0.0, total_cost: float = 0.01,
              provider: str = "test") -> None:
    mock.mkdir(parents=True, exist_ok=True)
    write_json(mock / "key.json", {
        "status": 200,
        "headers": {},
        "body": {"data": {"usage": usage}},
    })
    write_json(mock / "chat.json", {
        "status": 200,
        "headers": {"Date": "Wed, 01 Jan 2025 00:00:00 GMT"},
        "body": {
            "id": "gen-1",
            "provider": provider,
            "choices": [{"message": {"content": "reply"}}],
            "usage": {"cost": 0.01},
        },
    })
    write_json(mock / "generation.json", {
        "status": 200,
        "headers": {},
        "body": {"data": {"total_cost": total_cost, "provider_name": provider}},
    })


def run_call(td: Path, mock: Path, *extra: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable, str(OR_CALL),
        "--seat", "maker",
        "--log", str(td / "harness-maker.log"),
        "--model", "test/model",
        "--tag", "test/fp8",
        "--pin-provider", "test",
        "--messages", str(td / "messages.json"),
        "--out", str(td / "reply.txt"),
        "--job-spend", str(td / "job-spend.json"),
        "--mock-transport", str(mock),
    ]
    cmd += list(extra)
    return subprocess.run(cmd, capture_output=True, text=True)


class TestOrCallSpend(unittest.TestCase):
    def test_mock_call_writes_job1_log_entry_and_status(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            make_job(td)
            make_messages(td)
            mock = td / "mock"
            make_mock(mock)
            r = run_call(td, mock)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual((td / "reply.txt").read_text(encoding="utf-8"), "reply")

            entries = json.loads((td / "harness-maker.log").read_text(encoding="utf-8"))
            self.assertEqual(len(entries), 1)
            e = entries[0]
            for key in ("call", "seat", "request", "sent_at", "response_status",
                        "response_headers", "response", "received_at", "generation",
                        "generation_status", "generation_fetched_at", "harness", "verdict"):
                self.assertIn(key, e)
            self.assertEqual(e["request"]["headers"]["Authorization"], "Bearer [REDACTED]")
            self.assertTrue(e["verdict"]["ok"])
            self.assertTrue(e["harness"]["name"].endswith("tools/edi/or_call.py"))

            rows = [json.loads(line) for line in
                    (td / "spend" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()]
            self.assertEqual([row["event"] for row in rows], ["reserve", "settle"])

            status = td / "status.json"
            r = subprocess.run([
                sys.executable, str(OR_CALL),
                "--spend-status", "--out", str(status),
                "--job-spend", str(td / "job-spend.json"),
                "--mock-transport", str(mock),
            ], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            st = json.loads(status.read_text(encoding="utf-8"))
            for key in ("read_at", "writer", "job_id", "key_usage_usd", "baseline_usd",
                        "key_delta_usd", "ledger_sum_usd", "total_usd", "last_settle_at"):
                self.assertIn(key, st)
            self.assertTrue(st["writer"].startswith("tools/edi/or_call.py@"))

    def test_key_at_job_limit_refused_before_chat(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            make_job(td)
            make_messages(td)
            mock = td / "mock"
            make_mock(mock, usage=0.0)
            r = subprocess.run([
                sys.executable, str(OR_CALL),
                "--init-spend",
                "--job-spend", str(td / "job-spend.json"),
                "--mock-transport", str(mock),
            ], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            make_mock(mock, usage=5.0)
            r = run_call(td, mock)
            self.assertEqual(r.returncode, 6, r.stderr)
            self.assertFalse((td / "harness-maker.log").exists())
            reqs = [json.loads(line) for line in
                    (mock / "requests.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()]
            self.assertFalse(any(x["method"] == "POST" for x in reqs))

    def test_max_cost_before_send_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            make_job(td)
            make_messages(td)
            mock = td / "mock"
            make_mock(mock)
            r = run_call(td, mock, "--max-cost", "0.0001")
            self.assertEqual(r.returncode, 8, r.stderr)
            self.assertFalse((td / "harness-maker.log").exists())
            self.assertFalse((mock / "requests.jsonl").exists())

    def test_over_cap_after_settle_logs_and_writes_no_reply(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            make_job(td)
            make_messages(td)
            mock = td / "mock"
            make_mock(mock, total_cost=0.9)
            r = run_call(td, mock, "--max-cost", "0.5")
            self.assertEqual(r.returncode, 9, r.stderr)
            self.assertFalse((td / "reply.txt").exists())
            self.assertTrue((td / "harness-maker.log").exists())
            rows = [json.loads(line) for line in
                    (td / "spend" / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()]
            settles = [row for row in rows if row["event"] == "settle"]
            self.assertEqual(len(settles), 1)
            self.assertTrue(settles[0].get("over_cap"))

    def test_job_total_uses_max_of_ledger_and_key_delta(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            job, _ = make_job(td, bound=1.0)
            make_messages(td)
            mock = td / "mock"
            make_mock(mock, usage=0.1)
            ledger = Path(job["spend_ledger"])
            ledger.parent.mkdir(parents=True, exist_ok=True)
            ledger.write_text(json.dumps({
                "event": "settle", "id": "old", "at": "2025-01-01T00:00:00Z",
                "call": "old", "cost_usd": 0.8,
            }) + "\n", encoding="utf-8")
            (ledger.parent / "key-usage-baseline.json").write_text(json.dumps({
                "job": "test-job", "usage": 0.0, "at": "2025-01-01T00:00:00Z",
                "writer": "test",
            }) + "\n", encoding="utf-8")
            r = run_call(td, mock)
            self.assertEqual(r.returncode, 6, r.stderr)
            self.assertFalse((td / "harness-maker.log").exists())
            reqs = [json.loads(line) for line in
                    (mock / "requests.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()]
            self.assertFalse(any(x["method"] == "POST" for x in reqs))

    def test_missing_job_spend_is_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            make_messages(td)
            r = subprocess.run([
                sys.executable, str(OR_CALL),
                "--seat", "maker",
                "--log", str(td / "harness-maker.log"),
                "--model", "test/model",
                "--messages", str(td / "messages.json"),
                "--job-spend", str(td / "missing.json"),
            ], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stderr)


if __name__ == "__main__":
    unittest.main()
