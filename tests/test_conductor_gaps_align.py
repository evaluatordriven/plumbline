"""Bar for two conductor gaps. Red until the loop on disk closes them."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kit.conductor_loop import loop

SEPARATION_GAP = (
    "Architect proposed packet not recorded after seeing drafts "
    "(D3.Architect vs Contracts §4.2); Owner ratification required"
)


def _write(path, body):
    path.write_text(body, encoding="utf-8")


def _evaluator_script(verdict, score):
    line = json.dumps(
        {
            "verdict": verdict,
            "dimensions": [{"name": "d", "score": score, "observation": "ok"}],
            "controls": {"should_pass": "passed", "should_fail": "failed"},
            "violations": [],
        }
    )
    return (
        "import sys\n"
        "sys.stdout.write(%r)\n"
        "sys.stdout.write('\\n')\n"
        "sys.exit(0)\n"
    ) % line


def _packet(suite, maker, evaluator, frozen, bounds):
    py = sys.executable
    return {
        "ratified": True,
        "mode": "scored",
        "human_seat": "Owner",
        "artifact": {
            "test_cmd": [py, suite],
            "frozen": [frozen],
            "editable": ["src"],
        },
        "maker": {
            "cmd": [py, maker],
            "handoff": "rule12",
        },
        "evaluator": {
            "cmd": [py, evaluator],
            "kind": "script",
            "runs": 2,
        },
        "escalation": {
            "route": ["Architect", "Owner"],
            "classes": [],
            "holders": {
                "architect": "E-DI Architect (agent)",
                "orchestrator": [
                    {
                        "kind": "script",
                        "does": "rounds",
                        "holder": "kit.conductor_loop.loop",
                        "tested": "rounds-holder-tested",
                    },
                    {
                        "kind": "model",
                        "does": "escalations",
                        "holder": "E-DI Orchestrator (model)",
                        "tested": "escalations-holder-tested",
                    },
                ],
            },
        },
        "bounds": bounds,
    }


class TestConductorGapsAlign(unittest.TestCase):
    def test_separation_gap_sentence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            record = root / "record"
            work.mkdir()
            (work / "src").mkdir()
            frozen = work / "frozen.txt"
            _write(frozen, "frozen\n")
            suite = work / "suite.py"
            maker = work / "maker.py"
            evaluator = work / "evaluator.py"
            _write(
                suite,
                "import os\n"
                "import sys\n"
                "sys.exit(0 if os.path.exists('src/marker') else 1)\n",
            )
            _write(
                maker,
                "import json\n"
                "import os\n"
                "import sys\n"
                "with open(os.environ['PLUMBLINE_COST'], 'w', encoding='utf-8') as fh:\n"
                "    json.dump({'amount': 0}, fh)\n"
                "os.makedirs('src', exist_ok=True)\n"
                "with open('src/marker', 'w', encoding='utf-8') as fh:\n"
                "    fh.write('1')\n"
                "sys.exit(0)\n",
            )
            _write(evaluator, _evaluator_script("regenerate", 0.5))
            packet = _packet(
                str(suite),
                str(maker),
                str(evaluator),
                str(frozen),
                {
                    "T_accept": 1,
                    "T_dim": 0,
                    "T_reject": 0,
                    "cap": 1,
                    "budget": {
                        "amount": 0,
                        "unit": "USD",
                        "time_hours_lt": 24.0,
                    },
                },
            )
            summary = loop(packet, record_dir=str(record), cwd=str(work))
            self.assertIsInstance(summary, dict)
            self.assertEqual(summary["terminal_state"], "needs_owner")
            self.assertIn(SEPARATION_GAP, summary["separation_gaps"])

    def test_clock_binds_while_the_round_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work = root / "work"
            record = root / "record"
            work.mkdir()
            (work / "src").mkdir()
            frozen = work / "frozen.txt"
            _write(frozen, "frozen\n")
            suite = work / "suite.py"
            maker = work / "maker.py"
            evaluator = work / "evaluator.py"
            _write(
                suite,
                "import os\n"
                "import sys\n"
                "import time\n"
                "time.sleep(3)\n"
                "sys.exit(0 if os.path.exists('src/marker') else 1)\n",
            )
            _write(
                maker,
                "import json\n"
                "import os\n"
                "import sys\n"
                "import time\n"
                "time.sleep(3)\n"
                "with open(os.environ['PLUMBLINE_COST'], 'w', encoding='utf-8') as fh:\n"
                "    json.dump({'amount': 0}, fh)\n"
                "os.makedirs('src', exist_ok=True)\n"
                "with open('src/marker', 'w', encoding='utf-8') as fh:\n"
                "    fh.write('1')\n"
                "sys.exit(0)\n",
            )
            _write(evaluator, _evaluator_script("accept", 1))
            packet = _packet(
                str(suite),
                str(maker),
                str(evaluator),
                str(frozen),
                {
                    "T_accept": 1,
                    "T_dim": 0,
                    "T_reject": 0,
                    "cap": 3,
                    "budget": {
                        "amount": 0,
                        "unit": "USD",
                        "time_hours_lt": 8 / 3600.0,
                    },
                },
            )
            summary = loop(
                packet,
                record_dir=str(record),
                cwd=str(work),
                timeout_s=30,
            )
            self.assertIsInstance(summary, dict)
            self.assertEqual(summary["stop"], "clock")


if __name__ == "__main__":
    unittest.main()
