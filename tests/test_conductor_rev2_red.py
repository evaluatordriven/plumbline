"""Red bar: a still-red round-1 record holds the gate reading itself.

The suite stays red, so the Evaluator is not called. The assertion is the
review's: verdict regenerate, one artifact_missed_standard violation, quoting
the rerun exit and the rerun output sha256.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import kit.conductor_loop as cl
from kit.conductor_loop import loop


class TestConductorRev2Red(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            cl, "emit_custody_for_finish",
            lambda record_dir, summary: 0, create=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_round1_record_holds_the_gate_reading(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            cwd = root / "cwd"
            record_dir = root / "records"
            cwd.mkdir()
            record_dir.mkdir()
            self.assertEqual(list(record_dir.iterdir()), [])
            self.assertFalse(record_dir.resolve().is_relative_to(cwd.resolve()))

            (cwd / "src").mkdir()
            (cwd / "frozen.txt").write_text("frozen\n", encoding="utf-8")
            suite = cwd / "suite.py"
            suite.write_text("raise SystemExit(1)\n", encoding="utf-8")
            called = root / "evaluator-called"
            evaluator = cwd / "evaluator.py"
            evaluator.write_text(
                "import json, sys\n"
                "open(%r, 'w').write('called\\n')\n"
                "json.dump({\n"
                "    'verdict': 'accept',\n"
                "    'dimensions': [{'name': 'acceptance', 'score': 1}],\n"
                "    'violations': [],\n"
                "    'controls': {'should_pass': 'passed', 'should_fail': 'failed'},\n"
                "    'cost': 0,\n"
                "}, sys.stdout)\n"
                "sys.stdout.write('\\n')\n" % str(called),
                encoding="utf-8",
            )
            packet = {
                "ratified": True,
                "mode": "scored",
                "human_seat": "Owner",
                "artifact": {
                    "test_cmd": [sys.executable, str(suite)],
                    "frozen": ["frozen.txt"],
                    "editable": ["src"],
                },
                "maker": {
                    "cmd": [
                        sys.executable,
                        "-c",
                        "open('src/work.txt','w').write('artifact\\n')",
                    ],
                    "handoff": "rule12",
                },
                "evaluator": {
                    "runs": 2,
                    "cmd": [sys.executable, str(evaluator)],
                },
                "bounds": {
                    "T_accept": 1,
                    "T_dim": 0,
                    "T_reject": 0,
                    "cap": 2,
                    "budget": {"amount": 0, "unit": "USD", "time_hours_lt": 2},
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
                                "tested": "orchestrator-holder-1",
                            },
                            {
                                "kind": "model",
                                "does": "escalations",
                                "tested": "orchestrator-holder-2",
                            },
                        ],
                    },
                },
            }
            loop(packet, record_dir=str(record_dir), cwd=str(cwd))
            self.assertFalse(called.exists())
            record = json.loads((record_dir / "round-01.json").read_text(encoding="utf-8"))
            reading = record["reading"]
            self.assertEqual(reading.get("verdict"), "regenerate")
            violations = reading.get("violations")
            self.assertIsInstance(violations, list)
            self.assertEqual(len(violations), 1)
            self.assertEqual(violations[0].get("class"), "artifact_missed_standard")
            rerun = record["run"]["rerun"]
            quoted = json.dumps(violations[0])
            self.assertIn(str(rerun["exit"]), quoted)
            self.assertIn(rerun["output_sha256"], quoted)


if __name__ == "__main__":
    unittest.main()
