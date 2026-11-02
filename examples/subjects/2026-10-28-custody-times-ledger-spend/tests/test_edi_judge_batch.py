import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGE = ROOT / "tools" / "edi" / "judge_batch.py"


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def make_job(td: Path) -> Path:
    spend = td / "spend" / "ledger.jsonl"
    job = {
        "job_id": "test-job",
        "bound_usd": 2.0,
        "reserve_usd": 0.0,
        "spend_ledger": str(spend),
        "prices": [{
            "model": "test/model",
            "tag": "test/fp8",
            "prompt_usd_per_token": 0.001,
            "completion_usd_per_token": 0.002,
            "max_completion_tokens": 100,
        }],
    }
    path = td / "job-spend.json"
    write_json(path, job)
    return path


def make_mock(mock: Path) -> None:
    mock.mkdir(parents=True, exist_ok=True)
    write_json(mock / "key.json", {
        "status": 200,
        "headers": {},
        "body": {"data": {"usage": 0.0}},
    })
    write_json(mock / "chat.json", {
        "status": 200,
        "headers": {"Date": "Wed, 01 Jan 2025 00:00:00 GMT"},
        "body": {
            "id": "gen-1",
            "provider": "test",
            "choices": [{"message": {"content": "reply"}}],
            "usage": {"cost": 0.01},
        },
    })
    write_json(mock / "generation.json", {
        "status": 200,
        "headers": {},
        "body": {"data": {"total_cost": 0.01, "provider_name": "test"}},
    })


class TestJudgeBatch(unittest.TestCase):
    def test_rotation_order_summary_and_one_call_per_item(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            items = [
                {"id": "a", "text": "one"},
                {"id": "b", "text": "two"},
                {"id": "c", "text": "three"},
            ]
            write_json(td / "items.json", items)
            (td / "rubric.txt").write_text("rubric\n", encoding="utf-8")
            job_spend = make_job(td)
            mock = td / "mock"
            make_mock(mock)
            out = td / "out"
            r = subprocess.run([
                sys.executable, str(JUDGE),
                "--items", str(td / "items.json"),
                "--batch", "2",
                "--rubric", str(td / "rubric.txt"),
                "--out", str(out),
                "--job-spend", str(job_spend),
                "--log", str(td / "harness-judge.log"),
                "--model", "test/model",
                "--tag", "test/fp8",
                "--pin-provider", "test",
                "--mock-transport", str(mock),
            ], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["order"], ["b", "c", "a"])
            self.assertTrue(summary["writer"].startswith("tools/edi/judge_batch.py@"))
            self.assertIn("started_at", summary)
            self.assertIn("finished_at", summary)
            self.assertEqual(len(summary["results"]), 3)
            for result in summary["results"]:
                self.assertEqual(result["exit"], 0)
                self.assertTrue(Path(result["reply_file"]).exists())
            reqs = [json.loads(line) for line in
                    (mock / "requests.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()]
            self.assertEqual(sum(1 for x in reqs if x["method"] == "POST"), 3)


if __name__ == "__main__":
    unittest.main()
