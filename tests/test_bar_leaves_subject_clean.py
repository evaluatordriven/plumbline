#!/usr/bin/env python3
"""A bar may not move the subject it measures.

Measured 2026-11-09 (Job 31): the first authoring of `tests/test_validate_audit_root.py` left
`dot-plumbline/audits/census.json` in the work tree it had just measured. A dirty tree makes
`kit/emit_record.py` refuse, so **an instrument could make its own job unclosable** — the
job would have failed on the instrument's residue, not on the artifact. The bar was reworked
to build its fixtures in temporary directories, and this guard locks that property in:

    run the shipped bar in this checkout; `git status --porcelain` must be identical before
    and after.

A control proves the comparison is not vacuous: the same detector, pointed at a repository
where a file is deliberately dropped, must report the difference. A guard nobody has seen
fail is a guard nobody knows works.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BAR = REPO / "tests" / "test_validate_audit_root.py"


def _status(repo: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"], cwd=str(repo), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise AssertionError("git status failed in %s: %s" % (repo, proc.stderr[:400]))
    return [line for line in proc.stdout.splitlines() if line.strip()]


class BarLeavesItsSubjectClean(unittest.TestCase):
    def test_the_shipped_bar_does_not_move_the_tree(self):
        if not BAR.is_file():
            self.skipTest("no shipped bar in this tree")
        before = _status(REPO)
        proc = subprocess.run(
            [sys.executable, str(BAR)], cwd=str(REPO),
            capture_output=True, text=True, timeout=1800,
        )
        after = _status(REPO)
        if proc.returncode != 0:
            self.fail("the shipped bar did not pass, so the property is not yet meaningful:\n%s"
                      % (proc.stdout[-1500:] + proc.stderr[-1500:]))
        self.assertEqual(
            before, after,
            "the bar moved its own subject: %r -> %r. A dirty tree makes the emitter refuse, "
            "so an instrument that writes into the tree it measures can make its own job "
            "unclosable. Build fixtures in temporary directories." % (before, after),
        )

    def test_the_detector_reports_a_moved_tree(self):
        """Control: the same comparison, against a repo something did dirty, must differ."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
            (repo / "kept.txt").write_text("x\n", encoding="utf-8")
            subprocess.run(["git", "add", "kept.txt"], cwd=tmp, check=True)
            subprocess.run(
                ["git", "-c", "user.email=b@example.com", "-c", "user.name=b",
                 "commit", "-q", "-m", "seed"],
                cwd=tmp, check=True,
            )
            before = _status(repo)
            (repo / "residue.json").write_text("{}\n", encoding="utf-8")
            after = _status(repo)
            self.assertEqual(before, [])
            self.assertNotEqual(before, after, "the detector missed an untracked file")


if __name__ == "__main__":
    unittest.main(verbosity=2)
