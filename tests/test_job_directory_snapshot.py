"""Job 10 RE-CUT — acceptance snapshots the job directory (D-A).

Plain-English assertion: when a Plumbline job reaches ``accepted``, ``loop()`` copies
the entire record directory into a content-addressed archive, records the method
and identifier, and writes that fact into the custody/v1 record, so a later reader
can recover the accepted bytes with one mechanical command.

Written: 2026-11-09, after the Owner ruled that the custody emitter must not gain
a caller-settable ``--now`` clock to buy a deterministic test.

Limit: the snapshot proves the accepted tree WAS recoverable from the moment of
acceptance; it does not prove the job was honest, nor that the record is a correct
reading of the job. Existing accepted jobs are not retro-fitted.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tree_hashes(path: Path, exclude: set[str] | None = None) -> dict[str, str]:
    """SHA-256 of every regular file under ``path`` except paths matching ``exclude``."""
    out: dict[str, str] = {}
    exclude_set = set(exclude or [])
    for p in path.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(path).as_posix()
        if any(part in exclude_set for part in Path(rel).parts):
            continue
        out[rel] = _sha256_bytes(p.read_bytes())
    return out


def _clean_copy(tmp: Path) -> Path:
    """A disposable, committed copy of the repository so the emitter runs from a clean tree."""
    repo = tmp / "repo"
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
    )
    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    git = [
        "git", "-C", str(repo),
        "-c", "user.name=test",
        "-c", "user.email=test@localhost",
        "-c", "commit.gpgsign=false",
    ]
    subprocess.run(git + ["init", "-q"], check=True, capture_output=True)
    subprocess.run(git + ["add", "-A"], check=True, capture_output=True)
    subprocess.run(git + ["commit", "-qm", "clean copy for snapshot tests"], check=True, capture_output=True)
    return repo


def _write_job_files(work: Path) -> None:
    (work / "tests").mkdir(parents=True, exist_ok=True)
    (work / "tests" / "t.py").write_text("pin\n", encoding="utf-8")
    (work / "src").mkdir(parents=True, exist_ok=True)
    (work / "src" / "w.txt").write_text("no\n", encoding="utf-8")


def _holders() -> dict[str, Any]:
    return {
        "architect": "plumbline-architect",
        "orchestrator": [
            {"holder": "kit.conductor_loop.loop", "kind": "script", "does": "rounds", "tested": "rec#abc"},
            {"holder": "escalation-agent", "kind": "model", "does": "escalations", "tested": "rec#def"},
        ],
    }


def _evaluator_script(work: Path) -> list[str]:
    script = work / "eval.py"
    script.write_text(
        "import json, os\n"
        "turn = json.loads(os.environ['PLUMBLINE_TURN'])\n"
        "out = {\n"
        "    'dimensions': [{'name': 'q', 'score': 10, 'observation': 'seen'}],\n"
        "    'violations': [],\n"
        "    'verdict': 'accept',\n"
        "    'controls': {'should_pass': 'passed', 'should_fail': 'failed'},\n"
        "}\n"
        "print(json.dumps(out))\n",
        encoding="utf-8",
    )
    return [PY, str(script)]


def _packet(work: Path) -> dict[str, Any]:
    src_file = str(work / "src" / "w.txt")
    return {
        "ratified": True,
        "mode": "scored",
        "human_seat": "Owner",
        "artifact": {
            "test_cmd": [
                PY, "-c",
                "import sys; t=open(%r, 'r').read(); sys.exit(0 if t.startswith('yes') else 1)" % src_file,
            ],
            "frozen": [str(work / "tests" / "t.py")],
            "editable": ["src"],
            "ignore": [".git", "__pycache__"],
        },
        "maker": {
            "cmd": [PY, "-c", "open(%r, 'w').write('yes\\n')" % src_file],
            "handoff": "rule12",
        },
        "evaluator": {
            "kind": "script",
            "cmd": _evaluator_script(work),
            "runs": 2,
            "held_out": [],
        },
        "bounds": {
            "T_accept": 1,
            "T_dim": 1,
            "T_reject": 0,
            "cap": 1,
            "cap_counts": "generations",
            "budget": {"amount": 0, "unit": "USD", "time_hours_lt": 2},
        },
        "escalation": {
            "route": ["Architect", "Owner"],
            "classes": [],
            "holders": _holders(),
        },
    }


def _run_loop(clean_root: Path, work: Path, rec: Path, packet: dict[str, Any]) -> None:
    packet_path = work / "packet.json"
    packet_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    code = (
        "import os, sys\n"
        "sys.path.insert(0, %r)\n"
        "from kit.conductor_loop import loop\n"
        "import json\n"
        "os.makedirs(%r, exist_ok=True)\n"
        "loop(json.load(open(%r, encoding='utf-8')), record_dir=%r, cwd=%r)\n" % (
            str(clean_root), str(rec), str(packet_path), str(rec), str(work),
        )
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(clean_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [PY, "-c", code],
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(
            "loop() failed: rc=%s\nstdout=%s\nstderr=%s"
            % (proc.returncode, proc.stdout, proc.stderr)
        )


def _run_emit(clean_root: Path, job: Path, out: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(clean_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [PY, str(clean_root / "kit" / "emit_custody.py"), "--job-dir", str(job), "--out", str(out)],
        env=env,
        capture_output=True,
        text=True,
    )


def _accept(clean_root: Path):
    """Run one accepted job and return ``(workdir, record_dir, record)``."""
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "work"
        rec = Path(td) / "rec"
        work.mkdir(parents=True)
        rec.mkdir(parents=True)
        _write_job_files(work)
        _run_loop(clean_root, work, rec, _packet(work))
        record_path = rec / "custody" / "record.custody.json"
        if not record_path.is_file():
            raise AssertionError("loop() returned with no custody record at %s" % record_path)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        return work, rec, record


class JobDirectorySnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._copy_tmp = tempfile.TemporaryDirectory()
        cls.COPY = _clean_copy(Path(cls._copy_tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._copy_tmp.cleanup()

    def _snapshot_block(self, record: dict) -> dict:
        xp = record.get("predicate", {}).get("x-plumbline", {})
        snap = xp.get("snapshot")
        if not isinstance(snap, dict):
            raise AssertionError("record has no x-plumbline.snapshot block")
        return snap

    def _drop_time_fields(self, body: dict) -> dict:
        """Return a deep copy without producedAt or emitted-at fields."""
        copied = json.loads(json.dumps(body))
        pred = copied["predicate"]
        pred.pop("producedAt", None)
        xp = pred["x-plumbline"]
        xp.pop("emittedAt", None)
        xp.pop("times", None)
        xp.pop("time_sources", None)
        xp.pop("timeSources", None)
        return copied

    def test_01_accepted_record_contains_snapshot_block(self):
        """PRIMARY: the custody record names a snapshot with method and identifier."""
        _work, _rec, record = _accept(self.COPY)
        snap = self._snapshot_block(record)
        self.assertEqual(snap.get("method"), "tar.gz")
        self.assertRegex(snap.get("sha256", ""), r"^[0-9a-f]{64}$")
        self.assertIn("path", snap)
        self.assertFalse(Path(snap["path"]).is_absolute())
        self.assertIn("recover_command", snap)
        self.assertIn(snap["path"], snap["recover_command"])

    def test_02_snapshot_file_exists_and_matches_recorded_identifier(self):
        """The identifier in the record is the digest of the snapshot file on disk."""
        _work, rec, record = _accept(self.COPY)
        snap = self._snapshot_block(record)
        arc = rec / snap["path"]
        self.assertTrue(arc.is_file(), "snapshot archive missing: %s" % arc)
        self.assertEqual(_sha256_bytes(arc.read_bytes()), snap["sha256"])

    def test_03_recovered_tree_hashes_match_the_manifest(self):
        """PRIMARY: one mechanical command recovers the tree, and every file matches the snapshot digest."""
        _work, rec, record = _accept(self.COPY)
        snap = self._snapshot_block(record)
        arc = rec / snap["path"]
        manifest_path = rec / snap["manifest"]
        self.assertTrue(manifest_path.is_file(), "snapshot manifest missing: %s" % manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIsInstance(manifest.get("files"), dict)
        with tempfile.TemporaryDirectory() as td:
            recovered = Path(td) / "recovered"
            recovered.mkdir()
            # The recover command must be a single mechanical shell command.
            # GNU tar, not `python3 -m tarfile`: the latter exists from Python 3.12 and this repo's CI runs 3.11,
            # so a bar green on this host would be red in CI for a reason unrelated to the capability.
            proc = subprocess.run(
                ["tar", "-xzf", str(arc), "-C", str(recovered)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            expected = manifest["files"]
            actual = _tree_hashes(recovered)
            self.assertEqual(set(actual), set(expected), "recovered tree does not match snapshot path set")
            for rel, digest in expected.items():
                self.assertEqual(
                    actual[rel], digest,
                    "recovered file %s does not match snapshot digest" % rel,
                )

    def test_04_snapshot_is_a_copy_not_a_truncation(self):
        """Acceptance writes a copy; the original editable tree survives unchanged."""
        work, rec, record = _accept(self.COPY)
        snap = self._snapshot_block(record)
        # The original artifact is still there, not consumed.
        self.assertEqual((work / "src" / "w.txt").read_text().strip(), "yes")
        # The archive does not include its own custody record (a snapshot cannot contain the record about it).
        with tarfile.open(rec / snap["path"], "r:*") as tar:
            members = [m.name for m in tar.getmembers()]
        self.assertNotIn("custody/record.custody.json", members)

    def test_05_recovered_tree_re_emits_identical_record_except_produced_at(self):
        """SECONDARY: re-emitting from the recovered tree reproduces every field except producedAt."""
        _work, rec, record = _accept(self.COPY)
        snap = self._snapshot_block(record)
        arc = rec / snap["path"]
        with tempfile.TemporaryDirectory() as td:
            recovered = Path(td) / "recovered"
            recovered.mkdir()
            with tarfile.open(arc, "r:*") as tar:
                tar.extractall(recovered)
            out2 = recovered / "custody" / "record.custody.json"
            proc = _run_emit(self.COPY, recovered, out2)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            rec2 = json.loads(out2.read_text(encoding="utf-8"))
            a = self._drop_time_fields(record)
            b = self._drop_time_fields(rec2)
            self.assertEqual(a, b)

    def test_06_drifted_unsnapshotted_job_refuses_and_names_snapshot(self):
        """NEGATIVE: a missing snapshot on a drifted accepted job refuses, naming the missing snapshot."""
        _work, rec, record = _accept(self.COPY)
        snap = self._snapshot_block(record)
        (rec / snap["path"]).unlink(missing_ok=True)
        (rec / snap["manifest"]).unlink(missing_ok=True)
        # The presence of custody/record.custody.json is itself post-acceptance drift.
        out2 = rec / "record-again.custody.json"
        proc = _run_emit(self.COPY, rec, out2)
        combined = proc.stdout + proc.stderr
        self.assertNotEqual(proc.returncode, 0, combined)
        self.assertIn("snapshot", combined.lower())
        self.assertFalse(out2.exists())


if __name__ == "__main__":
    unittest.main()
