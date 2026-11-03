"""The frozen dict is the only representation of the frozen set."""

import inspect
import unittest

from kit.conductor_software import gate

_RECORD = {"dispatched", "reason", "red", "hashes_unchanged", "passed"}
_PATH = "tests/t.py"
_HASH = "a" * 64


class TestConductorGate(unittest.TestCase):
    def test_red_exit_zero_is_not_dispatched(self):
        frozen = {_PATH: _HASH}
        result = gate(frozen, dict(frozen), [], 0, b"fail", 0)
        self.assertEqual(set(result), _RECORD)
        self.assertFalse(result["dispatched"])
        self.assertEqual(result["reason"], "no RED")
        self.assertFalse(result["passed"])

    def test_frozen_path_in_editable_is_refused(self):
        # The frozen dict names the suite. There is no second list to empty.
        frozen = {_PATH: _HASH}
        result = gate(frozen, dict(frozen), [_PATH], 1, b"fail", 0)
        self.assertEqual(set(result), _RECORD)
        self.assertFalse(result["dispatched"])
        self.assertEqual(result["reason"], "frozen test is editable")
        self.assertFalse(result["passed"])

    def test_unchanged_freeze_after_red_passes(self):
        frozen = {_PATH: _HASH}
        result = gate(frozen, dict(frozen), [], 1, b"fail", 0)
        self.assertEqual(set(result), _RECORD)
        self.assertTrue(result["dispatched"])
        self.assertTrue(result["hashes_unchanged"])
        self.assertTrue(result["passed"])

    def test_moved_freeze_voids_the_turn(self):
        frozen = {_PATH: _HASH}
        after = {_PATH: "b" * 64}
        result = gate(frozen, after, [], 1, b"fail", 0)
        self.assertEqual(set(result), _RECORD)
        self.assertFalse(result["hashes_unchanged"])
        self.assertFalse(result["passed"])

    def test_missing_red_output_is_not_recorded(self):
        frozen = {_PATH: _HASH}
        result = gate(frozen, dict(frozen), [], 1, None, 0)
        self.assertEqual(set(result), _RECORD)
        self.assertEqual(result["red"]["output_sha256"], "not recorded")

    def test_signature_has_no_frozen_paths(self):
        self.assertNotIn("frozen_paths", inspect.signature(gate).parameters)
        frozen = {_PATH: _HASH}
        result = gate(frozen, dict(frozen), [], 1, b"fail", 0)
        self.assertEqual(set(result), _RECORD)


if __name__ == "__main__":
    unittest.main()
