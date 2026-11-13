"""Bar: unheld facts are not hard gaps. The real emitter must exit 0.

Owner ruling, verbatim, binding this job:

A finish is certifiable from facts the run held. Unheld facts are not hard
gaps. loop() writes the sources it actually has. The emitter exits 0 on that
record. It does not invent an approval, a buyer, a specialist, retention, or
a harness log. Schemas stay unedited. Both frozen bars stay frozen.

This file is the bar. It is not tests/test_loop_custody_on_finish.py and it
is not tests/test_escalate.py. Those stay frozen. kit/conductor_loop.py stays
frozen: the predecessor bar locks the seam, and the classification change is
not in that file. schemas/custody stays unedited. The hard/soft decision is
Python in kit/emit_custody.py, Gaps.add, default hard=True. The emitter does
not read the schema to decide.

Red while that process, on a copy of what loop() wrote, does not exit 0, or
names a hard gap. A hard gap for a fact the run did not hold is the
classification change the ruling names. Do not clear it by inventing the
fact. A hard gap for a fact the run did hold is a failure to read the source
loop wrote. The oracle strips the seam's record and runs kit/emit_custody.py.
A patched seam that returns 0 does not grade itself.

The oracle commits a throwaway copy of the kit files under test so an
unrelated dirty worktree is not the red. Measured: this worktree's emitter
exits 3 on a revision refusal before it classifies gaps; the clean pin
exits 1 with 21 hard gaps. This file does not commit the user's repo.

Fixture numbers below are not this job's bounds. This seat chose them so
loop() can be called. They are not the escalate job's bounds and not the
predecessor bar's bounds.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from unittest import mock

PY = sys.executable
RECORD_REL = "custody/record.custody.json"
PREDECESSOR = "tests/test_loop_custody_on_finish.py"
PREDECESSOR_SHA = "6264087aad12e020026bf581dabb34051d5577c5c9413baa5ea512545b78c233"
ESCALATE_BAR = "tests/test_escalate.py"
ESCALATE_BAR_SHA = "40eb3d7e3b985974ff3f462b4252c6fc7a65d71848b1431f98f5efe76dd0c7af"
LOOP_PY = "kit/conductor_loop.py"
# Re-pinned 2026-11-09, deliberately, and the reason is the whole point of this pin existing.
# loop() gained the last act of a job: `file_finish()` writes custody/status.json into the job folder and files
# the folder into the instance's dot-plumbline, because `dot-plumbline/jobs` held two jobs while twenty-five had
# run — filing was a sentence in a commit message and every dispatch wrote to /tmp. The seam this bar locks is
# untouched: `emit_custody_for_finish` is still called once, loop()'s signature is still
# (packet, record_dir, cwd, timeout_s, commit, evaluator_fn), a non-zero code is still CustodyNotDone, and the
# record is still written by the emitter rather than by this module. What moved is what happens AFTER a clean
# record. Third re-pin tonight. Previous values: e6b74046… (before PR #30), b35c01c6… (PR #30), now this — the loop now writes
# the final summary into the filed COPY as well, because the copy was taken before the `filing` row existed and
# could not say how it was filed (measured on Job 31's first close).
# This re-pin: loop() now waits for a detached engine's own exit record before it measures the tree — after
# Job 31 record-3 booked a real +16/-6 fix as "no artifact" 56 seconds before the engine wrote it.
# JOB 38 re-pin: the finish seam now names the custody document the job attests — `emit_custody_for_finish`
# reads the custody commit and the version its SPEC.md declares from tools/pin.json, finds a checkout at that
# commit, and writes `inputs/custody.json: custody_spec` — so a kit job that names no document files instead of
# dying on the emitter's `spec-version` refusal. The seam this bar locks is untouched: it is still called once,
# loop()'s signature is unchanged, a non-zero code is still CustodyNotDone, and the record is still written by
# the emitter rather than by this module.
# THE VALUE BELOW MUST COME FROM THE FILE IT PINS. Re-pin it with `sha256sum kit/conductor_loop.py` after this
# job's change is applied; a digest cannot be written from anywhere but the bytes it names, so a typed guess
# here would be the very drift this constant exists to catch.
LOOP_SHA = "bdfaa08bda2d5defba7596d0116f0d9dac4ab818159830427bab9d71b706ef5f"
SCHEMA_ROOTS = ("schemas/custody", "schemas/vendor")
SCHEMA_MANIFEST_SHA = "7182a9740347403960d81799430ead78784cb28c209a22ef728cebc6ee2b8876"
INVENTED_KEYS = ("approvals", "buyer", "specialist", "retention", "harness_log")
DISPOSITIONS = ("given", "not_yet_given", "declined")


def _repo():
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)
    if os.path.isfile(os.path.join(parent, "kit", "conductor_loop.py")):
        return parent
    env = os.environ.get("PLUMBLINE_REPO", "")
    if env and os.path.isfile(os.path.join(env, "kit", "conductor_loop.py")):
        return os.path.realpath(env)
    return parent


REPO = _repo()
sys.path.insert(0, REPO)

from kit.conductor_loop import loop  # noqa: E402
import kit.conductor_loop as cl  # noqa: E402


def _sha_file(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _rel(root, full):
    return os.path.relpath(full, root).replace(os.sep, "/")


def _hash_tree(root):
    out = {}
    if not os.path.isdir(root):
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            out[_rel(root, full)] = _sha_file(full)
    return out


def _schema_manifest(repo):
    paths = []
    for root in SCHEMA_ROOTS:
        base = os.path.join(repo, root)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames.sort()
            for name in sorted(filenames):
                paths.append(_rel(repo, os.path.join(dirpath, name)))
    paths.sort()
    outer = hashlib.sha256()
    for rel in paths:
        digest = _sha_file(os.path.join(repo, rel))
        outer.update(("%s  %s\n" % (digest, rel)).encode("utf-8"))
    return outer.hexdigest(), len(paths)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _copy_except(src, dst, skip_rel):
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            rel = _rel(src, full)
            if rel == skip_rel:
                continue
            target = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(full, target)


def _fixture_packet(work, suite, maker):
    """A packet loop() will run. Bounds here are fixture-only. Not the job's."""
    return {
        "ratified": True,
        "mode": "scored",
        "human_seat": "fixture-human-seat",
        "artifact": {
            "test_cmd": [PY, suite, os.path.join(work, "src", "w.txt")],
            "frozen": [os.path.join(work, "tests", "t.py")],
            "editable": ["src"],
            "ignore": [".git", "__pycache__"],
        },
        "maker": {"cmd": [PY, maker, os.path.join(work, "src", "w.txt")], "handoff": "rule12"},
        "evaluator": {
            "kind": "script",
            "cmd": [PY, "-c", "raise SystemExit('fixture evaluator_fn is the seat')"],
            "runs": 2,
            "held_out": [],
        },
        "bounds": {
            "T_accept": 2,
            "T_dim": 2,
            "T_reject": 1,
            "cap": 1,
            "budget": {"amount": 1, "unit": "USD", "time_hours_lt": 1},
        },
        "escalation": {
            "route": ["Architect", "Owner"],
            "classes": [],
            "holders": {
                "architect": "plumbline-architect",
                "orchestrator": [
                    {
                        "holder": "kit.conductor_loop.loop",
                        "kind": "script",
                        "does": "rounds",
                        "tested": "fixture-not-a-job",
                    },
                    {
                        "holder": "fixture-escalations",
                        "kind": "script",
                        "does": "escalations",
                        "tested": "fixture-not-a-job",
                    },
                ],
            },
        },
    }


def _scores():
    return {
        "dimensions": [{"name": "q", "score": 2, "observation": "seen"}],
        "violations": [],
        "verdict": "accept",
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _prepare(work):
    _write(os.path.join(work, "tests", "t.py"), "pin\n")
    _write(os.path.join(work, "src", "w.txt"), "no\n")
    _write(os.path.join(work, "custody", "bar.md"), "bar\n")
    suite = _write(
        os.path.join(work, "suite.py"),
        "import pathlib, sys\n"
        "text = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')\n"
        "sys.exit(0 if text.startswith('yes') else 1)\n",
    )
    maker = _write(
        os.path.join(work, "maker.py"),
        "import json, os, pathlib, sys\n"
        "pathlib.Path(sys.argv[1]).write_text('yes\\n', encoding='utf-8')\n"
        "cost = os.environ.get('PLUMBLINE_COST')\n"
        "if cost:\n"
        "    pathlib.Path(cost).write_text(json.dumps({'amount': 0}) + '\\n', encoding='utf-8')\n",
    )
    return suite, maker


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _instant(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _packet_of(job):
    path = os.path.join(job, "packet.json")
    if not os.path.isfile(path):
        return {}
    body = _load(path)
    return body if isinstance(body, dict) else {}


def _rounds(job):
    out = []
    if not os.path.isdir(job):
        return out
    for name in sorted(os.listdir(job)):
        if name.startswith("round-") and name.endswith(".json"):
            body = _load(os.path.join(job, name))
            if isinstance(body, dict):
                out.append(body)
    return out


def _held(field, job, packet):
    """True when this finish's files hold a source for the gap field.

    producedAt is the finish's ended_at. This seat chose that mapping. The
    run writes ended_at, not a separate producedAt.
    """
    if field == "subject" or field.startswith("subject["):
        return any("/editable/" in rel for rel in _hash_tree(job))
    if field == "startedAt":
        return _instant(packet.get("started_at") or packet.get("startedAt")) is not None
    if field == "producedAt":
        return _instant(packet.get("ended_at") or packet.get("endedAt") or packet.get("producedAt")) is not None
    if field == "evaluators" or field.startswith("evaluators"):
        if any(isinstance(row.get("evaluator"), list) and row.get("evaluator") for row in _rounds(job)):
            return True
        return isinstance(packet.get("evaluator"), dict) and bool(packet.get("evaluator"))
    if field == "checks" or field.startswith("checks"):
        for row in _rounds(job):
            reading = row.get("reading") if isinstance(row.get("reading"), dict) else {}
            if reading.get("dimensions"):
                return True
            for ev in row.get("evaluator") or []:
                parsed = ev.get("parsed") if isinstance(ev, dict) else None
                if isinstance(parsed, dict) and parsed.get("dimensions"):
                    return True
        return False
    if field in ("instrument.rubric", "instrument.runner"):
        return packet.get("standard_ref") not in (None, "", {}, [])
    if field.startswith("maker."):
        maker = packet.get("maker") if isinstance(packet.get("maker"), dict) else {}
        return bool(maker.get(field.split(".", 1)[1]))
    if field == "disposition.state":
        return packet.get("disposition_state") in DISPOSITIONS
    return False


def _invented(value, path="$"):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in INVENTED_KEYS and item not in (None, "", [], {}):
                found.append("%s.%s" % (path, key))
            found.extend(_invented(item, "%s.%s" % (path, key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_invented(item, "%s[%d]" % (path, index)))
    return found


def _harness_logs(rels):
    out = []
    for rel in rels:
        base = os.path.basename(rel)
        if base.startswith("harness") and base.endswith(".log"):
            out.append(rel)
    return out


def _editable_digests(job):
    found = {}
    for rel, digest in _hash_tree(job).items():
        if "/editable/" in "/%s" % rel and os.path.isfile(os.path.join(job, rel)):
            found[digest] = rel
    return found


def _content_failures(job, body, before):
    failures = []
    if not isinstance(body, dict):
        return ["emitter wrote no record"]
    packet = _packet_of(job)
    pred = body.get("predicate") if isinstance(body.get("predicate"), dict) else {}
    xp = pred.get("x-plumbline") if isinstance(pred.get("x-plumbline"), dict) else {}
    gaps = xp.get("gaps") if isinstance(xp.get("gaps"), list) else []
    hard = [row for row in gaps if isinstance(row, dict) and row.get("hard")]
    unheld = []
    unread = []
    for row in hard:
        field = row.get("field")
        if _held(str(field), job, packet):
            unread.append(str(field))
        else:
            unheld.append(str(field))
    if unheld:
        failures.append(
            "classification: %d hard gap(s) for facts the run did not hold: %s. "
            "The Owner ruled unheld facts are not hard gaps. Do not invent them."
            % (len(unheld), ", ".join(unheld))
        )
    if unread:
        failures.append(
            "held fact not read: %s. The run wrote a source. Do not invent a different fact."
            % ", ".join(unread)
        )
    if hard and not unheld and not unread:
        failures.append("%d hard gap(s)" % len(hard))
    editable = _editable_digests(job)
    subject = body.get("subject")
    if editable:
        if not isinstance(subject, list) or not subject:
            failures.append("subject names no artifact the run held under round-*/editable/")
        else:
            digests = []
            for item in subject:
                digest = (item.get("digest") or {}).get("sha256") if isinstance(item, dict) else None
                if isinstance(digest, str):
                    digests.append(digest)
            if not any(digest in editable for digest in digests):
                failures.append("subject digest is not an editable file the run wrote")
    started = _instant(packet.get("started_at") or packet.get("startedAt"))
    produced = _instant(packet.get("ended_at") or packet.get("endedAt") or packet.get("producedAt"))
    if started is not None and _instant(pred.get("startedAt")) != started:
        failures.append("startedAt is not the instant packet started_at held")
    if produced is not None and _instant(pred.get("producedAt")) != produced:
        failures.append("producedAt is not the instant packet ended_at held")
    invented = _invented(pred)
    if invented:
        failures.append("record names a fact the run did not hold: %s" % ", ".join(invented))
    maker = pred.get("maker") if isinstance(pred.get("maker"), dict) else {}
    packet_maker = packet.get("maker") if isinstance(packet.get("maker"), dict) else {}
    for key in ("name", "kind", "version"):
        value = maker.get(key)
        if value not in (None, "") and value != packet_maker.get(key):
            failures.append("maker.%s %r is not a value the packet held" % (key, value))
    by = (pred.get("disposition") or {}).get("by") if isinstance(pred.get("disposition"), dict) else None
    if by not in (None, "") and not packet.get("disposition_state"):
        failures.append("disposition.by %r was not held" % by)
    for key in ("rubric", "runner"):
        block = (pred.get("instrument") or {}).get(key) if isinstance(pred.get("instrument"), dict) else None
        pin = block.get("sha256") if isinstance(block, dict) else None
        if isinstance(pin, str) and pin not in before.values() and pin not in _hash_tree(job).values():
            failures.append("instrument.%s %s matches no file the run wrote" % (key, pin[:12]))
    logs = _harness_logs(before)
    if logs:
        failures.append("run wrote a harness log the fixture did not hold: %s" % ", ".join(logs))
    return failures


def _git(repo, args):
    return subprocess.run(
        ["git", "-c", "user.email=bar@local", "-c", "user.name=bar", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def _oracle_emitter(repo, keep):
    """A clean throwaway commit of the kit files under test. Not the user's repo."""
    root = TemporaryDirectory()
    keep.append(root)
    kit = os.path.join(root.name, "kit")
    os.makedirs(kit)
    for name in ("emit_custody.py", "custody_history.py"):
        shutil.copy2(os.path.join(repo, "kit", name), os.path.join(kit, name))
    init = _git(root.name, ["init"])
    if init.returncode != 0:
        raise RuntimeError(init.stderr or init.stdout)
    add = _git(root.name, ["add", "kit"])
    if add.returncode != 0:
        raise RuntimeError(add.stderr or add.stdout)
    commit = _git(root.name, ["commit", "-m", "oracle"])
    if commit.returncode != 0:
        raise RuntimeError(commit.stderr or commit.stdout)
    return os.path.join(kit, "emit_custody.py")


def certify(record_dir, repo, keep):
    """Run the real emitter on a copy of what loop() wrote. Ignore the seam's record."""
    with TemporaryDirectory() as fresh:
        _copy_except(record_dir, fresh, RECORD_REL)
        before = _hash_tree(fresh)
        emitter = _oracle_emitter(repo, keep)
        proc = subprocess.run(
            [PY, emitter, "--job-dir", fresh, "--spec-version", "0.9.8"],
            capture_output=True,
            text=True,
        )
        record_path = os.path.join(fresh, RECORD_REL)
        body = _load(record_path) if os.path.isfile(record_path) else None
        failures = []
        if proc.returncode != 0:
            failures.append("kit/emit_custody.py exit %s" % proc.returncode)
        failures.extend(_content_failures(fresh, body, before))
        return {
            "certified": not failures,
            "failures": failures,
            "exit": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "body": body,
        }


class LoopCustodySources(unittest.TestCase):
    def setUp(self):
        self._temps = []

    def tearDown(self):
        for temp in self._temps:
            temp.cleanup()

    def _dirs(self):
        work = TemporaryDirectory()
        record = TemporaryDirectory()
        self._temps.extend([work, record])
        return work.name, record.name

    def _run(self, record, work, seam=None):
        suite, maker = _prepare(work)
        packet = _fixture_packet(work, suite, maker)
        if seam is not None:
            patcher = mock.patch.object(cl, "emit_custody_for_finish", seam)
            patcher.start()
            self.addCleanup(patcher.stop)
        try:
            return loop(packet, record_dir=record, cwd=work, timeout_s=30, evaluator_fn=lambda turn, root: _scores())
        except cl.CustodyNotDone:
            return None
        except ValueError as exc:
            self.fail("packet refusal, seam not reached: %s" % exc)

    def test_frozen_files_stay(self):
        path = os.path.join(REPO, PREDECESSOR)
        self.assertTrue(os.path.isfile(path), "predecessor bar is absent")
        self.assertEqual(_sha_file(path), PREDECESSOR_SHA)
        escalate = os.path.join(REPO, ESCALATE_BAR)
        if os.path.isfile(escalate):
            self.assertEqual(_sha_file(escalate), ESCALATE_BAR_SHA)
        loop_py = os.path.join(REPO, LOOP_PY)
        self.assertTrue(os.path.isfile(loop_py), "kit/conductor_loop.py is absent")
        self.assertEqual(_sha_file(loop_py), LOOP_SHA)
        manifest, count = _schema_manifest(REPO)
        self.assertEqual(count, 49)
        self.assertEqual(manifest, SCHEMA_MANIFEST_SHA)

    def test_seam_record_is_not_the_oracle(self):
        work, record = self._dirs()
        marker = "invented-buyer-not-held"

        def seam(record_dir, summary):
            body = {
                "_type": "https://in-toto.io/Statement/v1",
                "subject": [],
                "predicateType": "https://evaluatordriven.com/custody/v1",
                "predicate": {
                    "buyer": marker,
                    "x-plumbline": {"gaps": []},
                },
            }
            _write(os.path.join(record_dir, RECORD_REL), json.dumps(body))
            return 0

        self._run(record, work, seam=seam)
        result = certify(record, REPO, self._temps)
        text = json.dumps(result.get("body"))
        self.assertNotIn(marker, text, "certify graded the seam's record")

    def test_loop_finish_is_certifiable_without_inventing_unheld_facts(self):
        work, record = self._dirs()
        self._run(record, work)
        self.assertTrue(os.path.isfile(os.path.join(record, "packet.json")), "loop() wrote no packet.json")
        result = certify(record, REPO, self._temps)
        if result["certified"]:
            return
        tail = (result["stdout"] or "") + (result["stderr"] or "")
        self.fail(
            "not certifiable\n%s\n--- emitter ---" % "\n".join(result["failures"])
            + "\n"
            + tail[-6000:]
        )


if __name__ == "__main__":
    unittest.main()
