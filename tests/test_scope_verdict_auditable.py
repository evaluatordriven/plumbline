#!/usr/bin/env python3
"""A scope verdict must not depend on the caller's directory, and must name its paths.

Two defects measured together on 2026-11-10 (Job 32, record-4):

1. `outside_editable()` resolved the EDITABLE entries against this process's
   directory, while the CHANGED entries are already absolute. Job 32 declared
   `["schemas/instance-extensions.json"]`, the Maker changed exactly that file, and
   the gate reported it outside the set — because the loop had been started from a
   directory that was not the tree.
2. The round record carried `reason: "edit outside editable"` and named no path. Two
   parties spent an hour trying to work out whether the Maker had wandered or the
   check had mis-resolved, and neither could tell from the record.

So: the resolution takes the tree explicitly, and every judged path is recorded.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from kit import conductor_run, conductor_software  # noqa: E402


def _tree(editable_rel: str = "schemas/instance-extensions.json") -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    target = root / editable_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}\n", encoding="utf-8")
    (root / "bar.py").write_text(
        "import sys, pathlib\n"
        "p = pathlib.Path('schemas/instance-extensions.json')\n"
        "sys.exit(0 if 'time_hours_lt' in p.read_text() else 1)\n",
        encoding="utf-8",
    )
    return tmp


class TheScopeCheckTakesTheRoot(unittest.TestCase):
    def test_relative_editable_resolves_against_the_tree_not_the_caller(self):
        with _tree() as root:
            change = os.path.join(root, "schemas/instance-extensions.json")
            self.assertEqual(
                conductor_software.outside_editable(
                    [change], ["schemas/instance-extensions.json"], root
                ),
                [],
                "a change inside the declared set must not be reported outside it",
            )

    def test_without_the_root_the_old_answer_is_what_we_measured(self):
        """Control: proves the parameter is what fixes it, not a coincidence."""
        with _tree() as root:
            change = os.path.join(root, "schemas/instance-extensions.json")
            self.assertNotEqual(
                conductor_software.outside_editable([change], ["schemas/instance-extensions.json"]),
                [],
                "without the tree the answer depends on this process's directory; "
                "if this ever returns [], the defect is unreproducible and this test is stale",
            )


class TheTurnRecordsWhatItJudged(unittest.TestCase):
    def test_gate_accepts_an_edit_inside_the_set(self):
        with _tree() as root:
            change = os.path.join(root, "schemas/instance-extensions.json")
            verdict = conductor_software.gate(
                frozen={},
                after={},
                editable=["schemas/instance-extensions.json"],
                red_exit=1,
                red_output=b"red",
                rerun_exit=0,
                maker_exit=0,
                changes=[change],
                root=root,
            )
            self.assertEqual(verdict["reason"], conductor_software.OK)

    def test_run_records_the_paths_it_judged(self):
        with _tree() as root:
            maker = "printf '{\"time_hours_lt\": 2}\\n' > schemas/instance-extensions.json"
            result = conductor_run.run(
                cwd=root,
                test_cmd=[sys.executable, "bar.py"],
                maker_cmd=["sh", "-c", maker],
                editable=["schemas/instance-extensions.json"],
                freeze_paths=["bar.py"],
                commit=None,
                timeout_s=120,
            )
            self.assertEqual(result["reason"], conductor_software.OK, result)
            self.assertIn("schemas/instance-extensions.json", result["changes"])
            self.assertEqual(result["editable"], ["schemas/instance-extensions.json"])




class ABarLeavesNoBytecodeBehind(unittest.TestCase):
    """Measured 2026-11-10, Job 32 record-6: the bar's own imports wrote two .pyc files
    into the tree, outside the editable set, and a correct repair read as `tampered`."""

    def test_the_bars_bytecode_is_not_judged_as_the_makers_edit(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "lib").mkdir()
        (root / "lib" / "__init__.py").write_text("", encoding="utf-8")
        (root / "lib" / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "subject.json").write_text("{}\n", encoding="utf-8")
        (root / "bar.py").write_text(
            "import sys, pathlib\n"
            "from lib import helper\n"
            "body = pathlib.Path('subject.json').read_text()\n"
            "sys.exit(0 if (helper.VALUE == 1 and 'x' in body) else 1)\n",
            encoding="utf-8",
        )
        maker = "printf '{\"x\": 1}\\n' > subject.json"
        result = conductor_run.run(
            cwd=str(root),
            test_cmd=[sys.executable, "bar.py"],
            maker_cmd=["sh", "-c", maker],
            editable=["subject.json"],
            freeze_paths=["bar.py", "lib/helper.py"],
            commit=None,
            timeout_s=120,
        )
        self.assertEqual(result["reason"], conductor_software.OK, result)
        self.assertEqual(result["changes"], ["subject.json"], result["changes"])
        self.assertEqual(list(root.rglob("*.pyc")), [], "the bar wrote bytecode into its subject")


if __name__ == "__main__":
    unittest.main(verbosity=2)
