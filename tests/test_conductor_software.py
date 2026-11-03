"""refuse_dispatch, record_red, freeze, hash_moved, refuse_editable, is_pass, record_field."""

import hashlib
import tempfile
import unittest
from pathlib import Path

import kit.conductor_software


class TestConductorSoftware(unittest.TestCase):
    def test_refuse_dispatch_exit_zero(self):
        self.assertTrue(kit.conductor_software.refuse_dispatch(exit_code=0))

    def test_record_red(self):
        self.assertFalse(kit.conductor_software.refuse_dispatch(exit_code=1))
        recorded = kit.conductor_software.record_red(exit_code=1, output=b"fail")
        self.assertEqual(recorded["exit"], 1)
        self.assertEqual(
            recorded["output_sha256"],
            hashlib.sha256(b"fail").hexdigest(),
        )
        missing = kit.conductor_software.record_red(exit_code=1, output=None)
        self.assertEqual(missing["output_sha256"], "not recorded")

    def test_freeze_hash_moved(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = str(Path(tmp) / "first.txt")
            second = str(Path(tmp) / "second.txt")
            Path(first).write_bytes(b"alpha")
            Path(second).write_bytes(b"beta")
            before = kit.conductor_software.freeze([first, second])
            self.assertEqual(before[first], hashlib.sha256(b"alpha").hexdigest())
            self.assertEqual(before[second], hashlib.sha256(b"beta").hexdigest())
            same = kit.conductor_software.freeze([first, second])
            self.assertFalse(kit.conductor_software.hash_moved(before, same))
            Path(second).write_bytes(b"beta-changed")
            after = kit.conductor_software.freeze([first, second])
            self.assertTrue(kit.conductor_software.hash_moved(before, after))

    def test_refuse_editable(self):
        self.assertTrue(
            kit.conductor_software.refuse_editable(
                editable=["src/a.py", "src/b.py"],
                frozen=["src/b.py"],
            )
        )
        self.assertFalse(
            kit.conductor_software.refuse_editable(
                editable=["src/a.py"],
                frozen=["src/b.py"],
            )
        )

    def test_is_pass(self):
        self.assertFalse(
            kit.conductor_software.is_pass(
                applied_edit=True,
                hashes_unchanged=False,
                rerun_exit=1,
            )
        )
        self.assertTrue(
            kit.conductor_software.is_pass(
                applied_edit=False,
                hashes_unchanged=True,
                rerun_exit=0,
            )
        )

    def test_record_field(self):
        self.assertEqual(kit.conductor_software.record_field(None), "not recorded")
        self.assertEqual(kit.conductor_software.record_field("abc"), "abc")


if __name__ == "__main__":
    unittest.main()
