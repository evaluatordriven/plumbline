"""Red bar: the round record reading is the evaluator's, and carries it."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import kit.conductor_loop as cl
from kit.conductor_loop import loop


def _readings_under(obj, found):
    if isinstance(obj, dict):
        reading = obj.get("reading")
        if isinstance(reading, dict):
            found.append(reading)
        for value in obj.values():
            _readings_under(value, found)
    elif isinstance(obj, list):
        for value in obj:
            _readings_under(value, found)


def _round_reading(result, record_dir):
    found = []
    _readings_under(result, found)
    root = Path(record_dir)
    if root.exists():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            _readings_under(payload, found)
    for reading in reversed(found):
        if reading.get("from") == "evaluator":
            return reading
    return found[-1] if found else {}


class TestConductorRev2(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(
            cl, "emit_custody_for_finish",
            lambda record_dir, summary: 0, create=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_scored_round_reading_from_evaluator(self):
        with tempfile.TemporaryDirectory() as raw:
            cwd = Path(raw) / "cwd"
            record_dir = Path(raw) / "records"
            cwd.mkdir()
            record_dir.mkdir()
            (cwd / "src").mkdir()
            (cwd / "frozen.txt").write_text("frozen\n", encoding="utf-8")
            suite = cwd / "suite.py"
            suite.write_text(
                "import sys\n"
                "from pathlib import Path\n"
                "sys.exit(0 if Path('src/marker').exists() else 1)\n",
                encoding="utf-8",
            )
            evaluator = cwd / "evaluator.py"
            evaluator.write_text(
                "import json, sys\n"
                "json.dump({\n"
                "    'verdict': 'accept',\n"
                "    'dimensions': [{'name': 'acceptance', 'score': 1, 'observation': 'seen'}],\n"
                "    'violations': [],\n"
                "    'controls': {'should_pass': 'passed', 'should_fail': 'failed'},\n"
                "    'cost': 0,\n"
                "}, sys.stdout)\n"
                "sys.stdout.write('\\n')\n",
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
                    "cmd": [sys.executable, "-c", "from pathlib import Path; p = Path('src/marker'); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('ok', encoding='utf-8'); raise SystemExit(0)"],
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
            result = loop(packet, record_dir=str(record_dir), cwd=str(cwd))
            reading = _round_reading(result, record_dir)
            self.assertEqual(
                (
                    reading.get("from"),
                    "dimensions" in reading,
                    "violations" in reading,
                    "verdict" in reading,
                ),
                ("evaluator", True, True, True),
            )
