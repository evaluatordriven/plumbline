"""Bar for Job 1: the predecessor fixture pin is reproduced.

Job 1 prepares the fixture that will make the freeze build visible.
On main without the freeze build the existing loop suites stay green,
so this bar uses the Architect's pin target instead of an observable failure.
The pin target is the sha256 of tests/test_loop_custody_on_finish.py after
_job() plants custody/bar.md and tests/test_loop_custody_sources.py after
_prepare() plants the same file.  Because the sources bar also keeps a frozen
predecessor-sha check, it must be updated to the same pin target.

This file is the bar. It is frozen. Do not edit it to make it pass.
"""
import hashlib
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREDECESSOR = os.path.join(ROOT, "tests", "test_loop_custody_on_finish.py")
PREDECESSOR_SHA = "049808b1125a3bca69033da95790a45b2383782d9057c27bd547c87688438e7d"
SOURCES = os.path.join(ROOT, "tests", "test_loop_custody_sources.py")

# Exact source substrings the Maker must produce.  The text argument here is a
# Python string literal that writes the two characters backslash-n, so the
# assertion string keeps a literal "\n" in the source code.
PRE_JOB_FIXTURE = (
    '''_write(tmp, os.path.join("custody", "bar.md"), "bar\\n")'''
)
SRC_FIXTURE = (
    '''_write(os.path.join(work, "custody", "bar.md"), "bar\\n")'''
)


class JobOneFixturePin(unittest.TestCase):
    def test_predecessor_hashes_to_pin_target(self):
        self.assertTrue(os.path.isfile(PREDECESSOR), "predecessor bar is absent")
        with open(PREDECESSOR, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(
            digest,
            PREDECESSOR_SHA,
            "predecessor SHA256 does not match the Architect's pin target",
        )

    def test_predecessor__job_plants_bar_fixture(self):
        with open(PREDECESSOR, encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn(
            PRE_JOB_FIXTURE,
            source,
            "_job() must plant custody/bar.md with the pinned content",
        )

    def test_sources_prepare_plants_bar_fixture(self):
        with open(SOURCES, encoding="utf-8") as fh:
            source = fh.read()
        self.assertIn(
            SRC_FIXTURE,
            source,
            "_prepare() must plant custody/bar.md in the sources bar too",
        )

    def test_successor_bar_tracks_the_moved_predecessor_pin(self):
        with open(SOURCES, encoding="utf-8") as fh:
            source = fh.read()
        match = re.search(r'PREDECESSOR_SHA\s*=\s*"(.+?)"', source)
        if match is None:
            self.fail("sources bar must declare PREDECESSOR_SHA")
        self.assertEqual(
            match.group(1),
            PREDECESSOR_SHA,
            "sources bar's PREDECESSOR_SHA must follow the moved pin target",
        )


if __name__ == "__main__":
    unittest.main()
