"""The repository's own hygiene rules, as tests rather than as good intentions.

Two claims that used to be true only while someone remembered them: that every GitHub Action is
pinned by commit (D4.12), and that the versions the README names are the versions the pin holds.
Each checker carries a selftest, and the selftest is asserted here too — a guard nobody has seen
fail is a guard nobody knows works.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import check_action_pins  # noqa: E402
import check_version_claims  # noqa: E402


class EveryActionIsPinnedByCommit(unittest.TestCase):
    def test_this_repository_pins_every_action(self):
        self.assertEqual(check_action_pins.violations(
            (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")), [])

    def test_a_tag_pin_is_refused(self):
        body = "jobs:\n  x:\n    steps:\n      - uses: actions/checkout@v4\n"
        self.assertEqual(len(check_action_pins.violations(body)), 1)

    def test_a_bare_commit_without_its_release_is_refused(self):
        body = "jobs:\n  x:\n    steps:\n      - uses: actions/checkout@%s\n" % ("a" * 40)
        self.assertEqual(len(check_action_pins.violations(body)), 1)

    def test_a_commented_commit_pin_passes(self):
        body = "jobs:\n  x:\n    steps:\n      - uses: actions/checkout@%s # v7\n" % ("a" * 40)
        self.assertEqual(check_action_pins.violations(body), [])


class TheProseAgreesWithThePin(unittest.TestCase):
    def test_this_repository_has_no_version_drift(self):
        self.assertEqual(check_version_claims.violations(REPO), [])

    def test_the_checker_can_fail(self):
        # The selftest plants one mismatch per rule; a green selftest is the proof the rules bite.
        self.assertEqual(check_version_claims.selftest(), 0)


if __name__ == "__main__":
    unittest.main()
