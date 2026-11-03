"""Conductor alignment bar.

loop(packet, record_dir=..., cwd=...) returns a dict. The packet is
ratified, mode scored, human_seat Owner. artifact.test_cmd is the suite
command. artifact.frozen is one file path that already exists before
loop() is called. artifact.editable is ["src"]. maker.cmd is a list of
strings and maker.handoff is rule12. That command writes {"amount": 0.1}
to the path in PLUMBLINE_COST and makes the suite pass. evaluator.cmd is
a list of strings, evaluator.runs is 2, evaluator.kind is script. It is
not an evaluator_fn and it writes no cost file. bounds are T_accept 1,
T_dim 1, T_reject 0, cap 3. bounds.budget is {"amount": 1, "unit": "USD",
"time_hours_lt": 2}. time_hours_lt is inside budget, next to amount. It is
not a sibling of budget. Every orchestrator holder has tested set to a
non-empty string: the script rounds holder and the model escalations
holder. Two packet fixes, or loop refuses before the cost check.

A maker cost under the budget is not a measurement. A passing suite is
not a measurement. summary["stop"] is "budget unmeasured".
"""

import sys
import tempfile
import unittest
from pathlib import Path

from kit.conductor_loop import loop


class TestConductorAlign(unittest.TestCase):
    def test_budget_unmeasured_when_evaluator_script_writes_no_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp) / "cwd"
            record_dir = Path(tmp) / "record"
            cwd.mkdir()
            record_dir.mkdir()
            src = cwd / "src"
            src.mkdir()

            work_py = src / "work.py"
            suite_py = cwd / "suite.py"
            suite_py.write_text(
                "import sys\n"
                f"sys.path.insert(0, {str(src)!r})\n"
                "import work\n"
                "assert work.ready is True\n"
            )

            maker_py = cwd / "maker.py"
            maker_py.write_text(
                "import json\n"
                "import os\n"
                "import subprocess\n"
                "import sys\n"
                "from pathlib import Path\n"
                "\n"
                "Path(os.environ['PLUMBLINE_COST']).write_text("
                "json.dumps({'amount': 0.1}))\n"
                f"Path({str(work_py)!r}).write_text('ready = True\\n')\n"
                "raise SystemExit(subprocess.call("
                f"[sys.executable, {str(suite_py)!r}]))\n"
            )

            evaluator_py = cwd / "evaluator.py"
            evaluator_py.write_text(
                "print('{\"dimensions\":[{\"name\":\"d\",\"score\":1,\"observation\":\"ok\"}],\"controls\":{\"should_pass\":\"passed\",\"should_fail\":\"failed\"},\"verdict\":\"accept\",\"violations\":[]}')\n"
            )

            packet = {
                "ratified": True,
                "mode": "scored",
                "human_seat": "Owner",
                "artifact": {
                    "test_cmd": [sys.executable, str(suite_py)],
                    "frozen": [str(suite_py)],
                    "editable": ["src"],
                },
                "maker": {
                    "cmd": [sys.executable, str(maker_py)],
                    "handoff": "rule12",
                },
                "evaluator": {
                    "cmd": [sys.executable, str(evaluator_py)],
                    "runs": 2,
                    "kind": "script",
                },
                "bounds": {
                    "T_accept": 1,
                    "T_dim": 1,
                    "T_reject": 0,
                    "cap": 3,
                    "budget": {
                        "amount": 1,
                        "unit": "USD",
                        "time_hours_lt": 2,
                    },
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
                                "tested": "script-rounds-holder",
                            },
                            {
                                "kind": "model",
                                "does": "escalations",
                                "tested": "model-escalations-holder",
                            },
                        ],
                    },
                },
            }
            self.assertNotIn("evaluator_fn", packet)
            self.assertNotIn("command", packet["maker"])
            self.assertNotIn("command", packet["evaluator"])
            self.assertEqual(packet["bounds"]["budget"]["amount"], 1)
            self.assertEqual(packet["bounds"]["budget"]["unit"], "USD")
            self.assertEqual(
                packet["bounds"]["budget"],
                {"amount": 1, "unit": "USD", "time_hours_lt": 2},
            )
            self.assertNotIn("time_hours_lt", packet["bounds"])
            for holder in packet["escalation"]["holders"]["orchestrator"]:
                self.assertIsInstance(holder["tested"], str)
                self.assertNotEqual(holder["tested"], "")
            self.assertTrue(Path(packet["artifact"]["frozen"][0]).is_file())

            summary = loop(packet, record_dir=record_dir, cwd=cwd)

        self.assertIsInstance(summary, dict)
        assert summary["stop"] == "budget unmeasured"
