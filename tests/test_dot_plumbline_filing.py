#!/usr/bin/env python3
"""The repo's job record must agree with itself: every run-log row names a folder, every folder is a job.

WHY THIS EXISTS. `dot-plumbline/jobs/` held two jobs on 2026-11-09 while Jobs 3-25 lived only in scratch
record directories. Nothing failed, because nothing checked — filing was a sentence in a commit message
("file closed jobs in dot-plumbline going forward") and a sentence cannot fail. The census that followed read
the `examples/` fixtures instead, found the same two jobs twice, and reported a premise the repo could not
support. A guard nobody has seen fail is a guard nobody knows works, so this one states the two directions
separately and names the job on each side.

THE INVARIANT. `set(rows.job_id) == set(directories)`, each directory carries `packet.json`, and no job_id
appears twice. That is deliberately weaker than "every job ever run is filed" — this file cannot see a job
directory it was never given — and stronger than a count, which stays green while the names drift apart.
"""
from __future__ import annotations
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JOBS = REPO / "dot-plumbline" / "jobs"
LOG = REPO / "dot-plumbline" / "run-log.json"


class DotPlumblineFiling(unittest.TestCase):
    def test_run_log_is_readable_in_the_shape_it_publishes(self):
        self.assertTrue(LOG.is_file(), f"no run log at {LOG}")
        doc = json.loads(LOG.read_text())
        self.assertIsInstance(doc, dict, "the run log is {note, runs}; a bare list is the older shape")
        self.assertIsInstance(doc.get("runs"), list, "no list under `runs` — the rows cannot be enumerated")

    def test_every_row_names_a_folder_and_no_folder_is_unnamed(self):
        doc = json.loads(LOG.read_text())
        rows = [r for r in doc["runs"] if isinstance(r, dict) and r.get("job_id")]
        dirs = {p.name for p in JOBS.iterdir() if p.is_dir()} if JOBS.is_dir() else set()
        named = [r["job_id"] for r in rows]
        dupes = {j for j in named if named.count(j) > 1}
        self.assertFalse(dupes, f"job_id named more than once in the run log: {sorted(dupes)}")
        missing = sorted({j for j in named} - dirs)
        self.assertFalse(missing, f"rows name folders that do not exist under dot-plumbline/jobs: {missing}")
        unnamed = sorted(dirs - set(named))
        self.assertFalse(unnamed, f"folders under dot-plumbline/jobs with no run-log row: {unnamed}")

    def test_every_filed_folder_carries_its_packet(self):
        if not JOBS.is_dir():
            self.skipTest("no dot-plumbline/jobs directory")
        naked = sorted(p.name for p in JOBS.iterdir() if p.is_dir() and not (p / "packet.json").is_file())
        self.assertFalse(naked, f"filed folders without packet.json — a job folder is created BY its packet: {naked}")

    def test_a_filed_row_records_a_packet_hash_that_matches_the_filed_packet(self):
        import hashlib
        doc = json.loads(LOG.read_text())
        mismatched = []
        for r in doc["runs"]:
            if not isinstance(r, dict) or r.get("event") != "filed":
                continue
            want = r.get("packet_sha256")
            packet = JOBS / r["job_id"] / "packet.json"
            if not want or not packet.is_file():
                mismatched.append((r["job_id"], "no hash or no packet"))
                continue
            got = hashlib.sha256(packet.read_bytes()).hexdigest()
            if got != want:
                mismatched.append((r["job_id"], f"log {want[:12]} != packet {got[:12]}"))
        self.assertFalse(mismatched, f"the filed packet is not the one the row recorded: {mismatched}")


if __name__ == "__main__":
    unittest.main()
