"""Bar for the re-cut freeze job: freeze is conditional on custody intent.

Owner ruling for this job: loop() may freeze the custody bar only for a
custody-bearing job, and the presence of ``record_dir/inputs/custody.json`` is
itself the custody-bearing signal.  A job that prepares that file is declaring
that it expects a custody/v1 record.  Because a custody record needs a frozen
bar, a custody-bearing job must either name its bar or supply the convention
file ``<cwd>/custody/bar.md``; if it does neither, freeze_bar() fails closed
before the Maker command runs.

A job is therefore custody-bearing when any of the following is true:
  (a) ``record_dir/inputs/custody.json`` exists;
  (b) the convention file ``<cwd>/custody/bar.md`` exists.

For a custody-bearing job, the bar to freeze is chosen in this order:
  1. ``bar.file`` from ``record_dir/inputs/custody.json`` if it names a
     non-empty relative path;
  2. otherwise, the convention file ``<cwd>/custody/bar.md``.

If a signal names or selects a bar and that bar cannot be read, or the ledger
tool refuses the freeze, freeze_bar() raises before the Maker runs and no
custody record is produced.  If a job prepared neither signal, freeze_bar()
does nothing and loop() proceeds without a custody record.

The existing tests/test_loop_freeze.py covers the original unconditional rule
that "no bar means no run".  That rule is superseded by the conditional rule
above; tests/test_loop_freeze.py::LoopFreezeTests::test_unwritable_freeze_fails_closed
is marked superseded there.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PY = sys.executable
ROOT = Path(__file__).resolve().parent.parent
LEDGER_REL = "inputs/custody-events.jsonl"
LEDGER_PY = "kit/custody_ledger.py"
BAR_REL = "custody/bar.md"

sys.path.insert(0, str(ROOT))
from kit.conductor_loop import freeze_bar  # noqa: E402
import kit.conductor_loop as cl  # noqa: E402


def _sha_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _writer_stamp():
    digest = _sha_file(ROOT / LEDGER_PY)[:12]
    return f"kit/custody_ledger.py@{digest}"


def _events(path):
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


def _freezes(events):
    return [ev for ev in events if isinstance(ev, dict) and ev.get("event") == "freeze"]


class ConditionalFreezeTests(unittest.TestCase):
    def test_no_custody_inputs_and_no_convention_bar_skips_freeze(self):
        """A plain loop() caller that prepares no custody inputs must not fail."""
        with TemporaryDirectory() as work, TemporaryDirectory() as record:
            freeze_bar(record, work)
            self.assertFalse(os.path.exists(os.path.join(record, LEDGER_REL)))
            self.assertFalse(os.path.exists(os.path.join(record, "inputs", "custody.json")))

    def test_declared_bar_file_is_frozen(self):
        """bar.file in record_dir/inputs/custody.json is authoritative."""
        bar_bytes = b"declared bar\n"
        bar_rel = "bars/special.md"
        bar_sha = hashlib.sha256(bar_bytes).hexdigest()

        with TemporaryDirectory() as work, TemporaryDirectory() as record:
            # The source of the bar is in the workspace (cwd).
            source = os.path.join(work, bar_rel)
            os.makedirs(os.path.dirname(source), exist_ok=True)
            with open(source, "wb") as handle:
                handle.write(bar_bytes)

            # The job declares the bar relative to the job directory.
            inputs_dir = os.path.join(record, "inputs")
            os.makedirs(inputs_dir, exist_ok=True)
            with open(os.path.join(inputs_dir, "custody.json"), "w", encoding="utf-8") as handle:
                json.dump({"bar": {"file": bar_rel}}, handle)

            freeze_bar(record, work)

            # The bar was copied into the job directory and frozen.
            dest = os.path.join(record, bar_rel)
            self.assertTrue(os.path.isfile(dest), "declared bar was not copied into the job directory")
            self.assertEqual(_sha_file(dest), bar_sha)

            events_path = os.path.join(record, LEDGER_REL)
            freezes = _freezes(_events(events_path))
            self.assertEqual(len(freezes), 1, "expected exactly one freeze event")
            ev = freezes[0]
            self.assertEqual(ev.get("bar_file"), bar_rel)
            self.assertEqual(ev.get("bar_sha256"), bar_sha)
            self.assertNotEqual(ev.get("writer"), "hand")
            self.assertTrue(str(ev.get("writer", "")).startswith("kit/custody_ledger.py@"))

    def test_declared_bar_missing_fails_closed(self):
        """A custody-bearing job with a missing declared bar must not dispatch."""
        with TemporaryDirectory() as work, TemporaryDirectory() as record:
            inputs_dir = os.path.join(record, "inputs")
            os.makedirs(inputs_dir, exist_ok=True)
            with open(os.path.join(inputs_dir, "custody.json"), "w", encoding="utf-8") as handle:
                json.dump({"bar": {"file": "missing.md"}}, handle)

            with self.assertRaises(RuntimeError) as caught:
                freeze_bar(record, work)
            self.assertIn("missing.md", str(caught.exception))
            self.assertFalse(os.path.exists(os.path.join(record, LEDGER_REL)))

    def test_custody_inputs_without_bar_file_and_no_convention_fails_closed(self):
        """A custody-bearing job that names no bar and has no convention bar fails closed."""
        with TemporaryDirectory() as work, TemporaryDirectory() as record:
            inputs_dir = os.path.join(record, "inputs")
            os.makedirs(inputs_dir, exist_ok=True)
            with open(os.path.join(inputs_dir, "custody.json"), "w", encoding="utf-8") as handle:
                json.dump({}, handle)

            self.assertFalse(os.path.isfile(os.path.join(work, BAR_REL)))

            with self.assertRaises(RuntimeError) as caught:
                freeze_bar(record, work)
            message = str(caught.exception)
            # The failure names that no bar was found; the Maker must not run.
            self.assertTrue(
                "bar" in message.lower() or "custody" in message.lower(),
                "failure message did not name the missing bar: %r" % message,
            )
            self.assertFalse(os.path.exists(os.path.join(record, LEDGER_REL)))

    def test_custody_inputs_without_bar_file_uses_convention(self):
        """A custody-bearing job with no bar.file falls back to the convention bar."""
        bar_bytes = b"convention bar\n"
        bar_sha = hashlib.sha256(bar_bytes).hexdigest()

        with TemporaryDirectory() as work, TemporaryDirectory() as record:
            inputs_dir = os.path.join(record, "inputs")
            os.makedirs(inputs_dir, exist_ok=True)
            with open(os.path.join(inputs_dir, "custody.json"), "w", encoding="utf-8") as handle:
                json.dump({}, handle)

            source = os.path.join(work, BAR_REL)
            os.makedirs(os.path.dirname(source), exist_ok=True)
            with open(source, "wb") as handle:
                handle.write(bar_bytes)

            freeze_bar(record, work)

            dest = os.path.join(record, BAR_REL)
            self.assertTrue(os.path.isfile(dest), "convention bar was not copied into the job directory")
            self.assertEqual(_sha_file(dest), bar_sha)

            freezes = _freezes(_events(os.path.join(record, LEDGER_REL)))
            self.assertEqual(len(freezes), 1)
            self.assertEqual(freezes[0].get("bar_file"), BAR_REL)
            self.assertEqual(freezes[0].get("bar_sha256"), bar_sha)

    def test_convention_bar_still_freezes(self):
        """When no custody.json exists and the convention bar is present, freeze it."""
        bar_bytes = b"convention bar\n"
        bar_sha = hashlib.sha256(bar_bytes).hexdigest()

        with TemporaryDirectory() as work, TemporaryDirectory() as record:
            source = os.path.join(work, BAR_REL)
            os.makedirs(os.path.dirname(source), exist_ok=True)
            with open(source, "wb") as handle:
                handle.write(bar_bytes)

            freeze_bar(record, work)

            dest = os.path.join(record, BAR_REL)
            self.assertTrue(os.path.isfile(dest))
            self.assertEqual(_sha_file(dest), bar_sha)

            freezes = _freezes(_events(os.path.join(record, LEDGER_REL)))
            self.assertEqual(len(freezes), 1)
            self.assertEqual(freezes[0].get("bar_file"), BAR_REL)
            self.assertEqual(freezes[0].get("bar_sha256"), bar_sha)


if __name__ == "__main__":
    unittest.main()
