#!/usr/bin/env python3
"""`dot-plumbline` holds two different things and must not let them be mistaken for one.

WHY THIS EXISTS. Filing was a sentence in a commit message ("file closed jobs in dot-plumbline going forward"),
and a sentence cannot fail. When the first backfill ran, seven of ten folders landed under `jobs/` with no
custody record — and three of those were not jobs at all: their `packet.json` was a route-maker dispatch
(`artifact`/`bounds`/`job`), not a job packet. The repo then said "jobs without records", which was a fact
about the filing, not about the jobs.

THE INVARIANT. A folder under `jobs/` carries a packet with `job_id`. A folder under `runs/` carries a dispatch
packet and is labelled `record_state: evidence`. Every folder has exactly one run-log row and every row names a
folder. And a row's `record_state` is checked against the folder itself:

    custody  -> jobs/<id>/custody/record.custody.json exists
    open     -> no custody record AND no terminal_state (a job that has not ended cannot have one)
    missing  -> no custody record but a terminal_state (filed with --allow-incomplete; the omission is recorded)
    evidence -> lives under runs/

That is deliberately a set comparison, not a count: a count stays green while the names drift apart.
"""
from __future__ import annotations
import hashlib
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "dot-plumbline"
JOBS = ROOT / "jobs"
RUNS = ROOT / "runs"
LOG = ROOT / "run-log.json"


def rows() -> list[dict]:
    return [r for r in json.loads(LOG.read_text())["runs"] if isinstance(r, dict) and r.get("job_id")]


def folders() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for parent in (JOBS, RUNS):
        if parent.is_dir():
            for p in parent.iterdir():
                if p.is_dir():
                    found[p.name] = p
    return found


class DotPlumblineFiling(unittest.TestCase):
    def test_run_log_is_readable_in_the_shape_it_publishes(self):
        self.assertTrue(LOG.is_file(), f"no run log at {LOG}")
        doc = json.loads(LOG.read_text())
        self.assertIsInstance(doc, dict, "the run log is {note, runs}; a bare list is the older shape")
        self.assertIsInstance(doc.get("runs"), list, "no list under `runs` — the rows cannot be enumerated")

    def test_every_row_names_a_folder_and_no_folder_is_unnamed(self):
        named = [r["job_id"] for r in rows()]
        dupes = {j for j in named if named.count(j) > 1}
        self.assertFalse(dupes, f"job_id named more than once in the run log: {sorted(dupes)}")
        have = folders()
        self.assertFalse(sorted(set(named) - set(have)),
                         f"rows name folders under neither jobs/ nor runs/: {sorted(set(named) - set(have))}")
        self.assertFalse(sorted(set(have) - set(named)),
                         f"folders with no run-log row: {sorted(set(have) - set(named))}")

    def test_jobs_carry_a_job_packet_and_runs_do_not(self):
        bad_jobs, bad_runs = [], []
        for name, path in folders().items():
            packet = path / "packet.json"
            if not packet.is_file():
                bad_jobs.append(f"{name} has no packet.json")
                continue
            try:
                doc = json.loads(packet.read_text())
            except Exception as exc:
                bad_jobs.append(f"{name}: unreadable packet ({exc})")
                continue
            is_job = bool(isinstance(doc, dict) and doc.get("job_id"))
            if path.parent == JOBS and not is_job:
                bad_jobs.append(f"{name} is under jobs/ but its packet carries no job_id")
            if path.parent == RUNS and is_job:
                bad_runs.append(f"{name} is under runs/ but its packet carries job_id")
        self.assertFalse(bad_jobs, f"jobs/ must hold job packets: {bad_jobs}")
        self.assertFalse(bad_runs, f"runs/ must hold dispatch packets, not jobs: {bad_runs}")

    def test_each_row_records_the_record_state_the_folder_actually_has(self):
        have, wrong = folders(), []
        for r in rows():
            path = have.get(r["job_id"])
            if path is None:
                continue  # named by test_every_row_names_a_folder...
            state = r.get("record_state")
            record = (path / "custody" / "record.custody.json").is_file()
            terminal = None
            try:
                terminal = json.loads((path / "packet.json").read_text()).get("terminal_state")
            except Exception:
                pass
            if state == "custody" and not record:
                wrong.append(f"{r['job_id']}: row says custody, no record file")
            elif state == "open" and (record or terminal):
                wrong.append(f"{r['job_id']}: row says open, folder has record={record} terminal={terminal!r}")
            elif state == "missing" and (record or not terminal):
                wrong.append(f"{r['job_id']}: row says missing, folder has record={record} terminal={terminal!r}")
            elif state == "evidence" and path.parent != RUNS:
                wrong.append(f"{r['job_id']}: row says evidence, folder is not under runs/")
            elif state not in {"custody", "open", "missing", "evidence"}:
                wrong.append(f"{r['job_id']}: row carries no usable record_state ({state!r})")
        self.assertFalse(wrong, f"record_state does not match the folder: {wrong}")

    def test_a_filed_row_records_a_packet_hash_that_matches_the_filed_packet(self):
        have, mismatched = folders(), []
        for r in rows():
            want = r.get("packet_sha256")
            packet = have.get(r["job_id"], Path("/nonexistent")) / "packet.json"
            if not want or not packet.is_file():
                mismatched.append((r["job_id"], "no hash or no packet"))
                continue
            got = hashlib.sha256(packet.read_bytes()).hexdigest()
            if got != want:
                mismatched.append((r["job_id"], f"log {want[:12]} != packet {got[:12]}"))
        self.assertFalse(mismatched, f"the filed packet is not the one the row recorded: {mismatched}")


if __name__ == "__main__":
    unittest.main()
