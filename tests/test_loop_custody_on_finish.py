"""Bar for a custody record on a finished loop(). Red until loop() ships one.

This file is the bar. It is frozen. Do not edit it to make it pass.

The omission, Owner 2026-11-05: a finished loop() can ship with no custody
record. Remembering to run plumbline_job.py close afterward is not the fix.
emit_custody.py exit 0 is the only done: the record is written and names no
hard gap. Exit 1, 2, or 3 is not done.

AMENDED, Owner 2026-11-03, ruling "update-test". The claim "the seam is the
emitter, not close" was enforced as `seam exit == a no-document twin's exit`.
That equality held while the seam could supply nothing; it is false by design
now that the seam names the pinned custody document (Job 38), because the
no-document twin is refused (exit 3, kind spec-version) while the seam reaches
the emitter (exit 1 on this fixture, gaps and all). The Owner ruled that the
frozen test does not supersede the filing fix and that this test and its
sibling pins be updated so the approved seam is the law. The property is NOT
relaxed: `test_seam_is_the_emitter_not_close` still fails a private closer and
still fails a seam that emits anything its twin does not.

Out of this bar, named so they are not picked up:
- Do not retrofit job 2026-11-05-loop-started-at-2. It was filed, not closed.
  It has no custody record. This file checks that a run does not create one.
- Do not edit schemas/custody/custody-v1.schema.json or anything under
  schemas/vendor/.
- A run-log row when close's custody step already failed is roadmap item 3(c).
  This file does not score one.

Labels the Architect chose:
- The record path is record_dir/custody/record.custody.json. Same filename
  close writes. loop() has no job id. record_dir is where a finish ships.
  loop() gains no parameter. A new argument the caller must remember is the
  same defect as remembering to close.
- The seam is kit.conductor_loop.emit_custody_for_finish(record_dir, summary).
  It returns the emitter's exit code. loop() calls it once, after the summary
  dict exists and before summary.json or escalation.json is written.
- Not done is kit.conductor_loop.CustodyNotDone, a subclass of Exception, not
  of ValueError. The instance attribute exit_code is 1, 2, or 3. It propagates
  to the caller. summary.json and escalation.json are not written. Round files
  already written are not required to be removed.
- Exit 2 and 3 write nothing. Exit 1 may leave the record the emitter wrote,
  and that record names a hard gap. Neither is a ship.
- A packet refusal is not a finish. The seam is not called. No custody record
  is written.
- The seam calls kit/emit_custody.py. It does not call plumbline_job.py.
  Side-by-side with the emitter, the seam's exit code matches, and the record
  on disk matches, the emitter's on a twin given the SAME document. Naming the
  custody document the job attests is the seam's whole difference from a bare
  emitter run: it supplies `custody_spec` and then adds nothing. A twin given
  no document is refused by the emitter (kind spec-version) and is no longer
  the comparison.

Fixture bounds in this file are copied from the existing loop tests so loop()
can reach accepted, needs_owner, and rejected. They are not this job's
T_accept, T_dim, T_reject, cap, clock, or budget. The Owner has not set those.
This bar did not need them. They stay unset.

Collision, disclosed: tests/test_loop_started_at.py is a frozen prior bar. It
expects loop() to return on these same fixtures. A finish the emitter cannot
record cleanly must not return. This file does not edit that one, and it does
not authorize weakening it.
"""
import inspect
import json
import os
import shutil
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from unittest import mock

from kit.conductor_loop import loop
import kit.conductor_loop as cl

PY = sys.executable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMITTER = os.path.join(ROOT, "kit", "emit_custody.py")
PIN = os.path.join(ROOT, "tools", "pin.json")
PREDICATE_TYPE = "https://evaluatordriven.com/custody/v1"
STATEMENT = "https://in-toto.io/Statement/v1"
FROZEN_JOB = os.path.join(
    ROOT, "dot-plumbline", "jobs", "2026-11-05-loop-started-at-2",
    "custody", "record.custody.json",
)
SEAM = "emit_custody_for_finish"
NOT_DONE = "CustodyNotDone"


def _write(root, name, text):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _holders():
    return {
        "architect": "plumbline-architect",
        "orchestrator": [
            {"holder": "kit.conductor_loop.loop", "kind": "script", "does": "rounds", "tested": "rec#abc"},
            {"holder": "escalation-agent", "kind": "model", "does": "escalations", "tested": "rec#def"},
        ],
    }


def _packet(tmp, maker, suite, **over):
    """Fixture packet. Bounds are copied from the existing loop tests, not set for this job."""
    packet = {
        "ratified": True,
        "mode": "scored",
        "human_seat": "Owner",
        "artifact": {
            "test_cmd": suite,
            "frozen": [os.path.join(tmp, "tests", "t.py")],
            "editable": ["src"],
            "ignore": [".git", "__pycache__"],
        },
        "maker": {"cmd": maker, "handoff": "rule12"},
        "evaluator": {
            "kind": "script",
            "cmd": [PY, "-c", "raise SystemExit(0)"],
            "runs": 2,
            "held_out": [],
        },
        "bounds": {
            "T_accept": 1,
            "T_dim": 1,
            "T_reject": 0,
            "cap": 3,
            "cap_counts": "generations",
            "budget": {"amount": 0, "unit": "USD", "time_hours_lt": 2},
        },
        "escalation": {
            "route": ["Architect", "Owner"],
            "classes": [],
            "holders": _holders(),
        },
    }
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(packet.get(key), dict):
            packet[key].update(value)
        else:
            packet[key] = value
    return packet


def _scores(score, verdict="accept"):
    return {
        "dimensions": [{"name": "q", "score": score, "observation": "seen"}],
        "violations": [],
        "verdict": verdict,
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _suite(work):
    return [PY, "-c", "import sys; t=open(%r).read(); sys.exit(0 if t.startswith('yes') else 1)" % work]


def _job(tmp):
    _write(tmp, "tests/t.py", "pin\n")
    _write(tmp, "src/w.txt", "no\n")
    _write(tmp, os.path.join("custody", "bar.md"), "bar\n")
    return os.path.join(tmp, "src", "w.txt")


def _maker(work):
    return [PY, "-c", "open(%r,'w').write('yes\\n')" % work]


def _custody(record_dir):
    return os.path.join(record_dir, "custody", "record.custody.json")


def _clean_record():
    return {
        "_type": STATEMENT,
        "predicateType": PREDICATE_TYPE,
        "predicate": {"x-plumbline": {"gaps": []}},
    }


def _gapped_record():
    return {
        "_type": STATEMENT,
        "predicateType": PREDICATE_TYPE,
        "predicate": {"x-plumbline": {"gaps": [
            {"field": "startedAt", "reason": "no source", "hard": True},
        ]}},
    }


def _hard(body):
    gaps = body["predicate"]["x-plumbline"]["gaps"]
    return [row for row in gaps if row.get("hard")]


def _dump(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh)
        fh.write("\n")


def _frozen_bytes():
    if not os.path.isfile(FROZEN_JOB):
        return None
    with open(FROZEN_JOB, "rb") as fh:
        return fh.read()


def _not_done(test):
    exc = getattr(cl, NOT_DONE, None)
    if not isinstance(exc, type) or not issubclass(exc, Exception):
        test.fail("kit.conductor_loop.CustodyNotDone is not bound")
    if issubclass(exc, ValueError):
        test.fail("CustodyNotDone must not be a ValueError; a packet refusal stays a ValueError")
    return exc


def _cases():
    """The three terminal states close writes a custody record for."""
    return (
        ("accepted", "accepted", {"cap": 1}, 1, "accept"),
        ("needs_owner", "cap reached", {"cap": 1}, 0.5, "regenerate"),
        ("rejected", "rejected", {"cap": 1, "T_reject": 0.4}, 0.1, "reject"),
    )


class _Bar(unittest.TestCase):
    def setUp(self):
        self._frozen = _frozen_bytes()

    def tearDown(self):
        self.assertEqual(_frozen_bytes(), self._frozen)


class UnpatchedTests(_Bar):
    def test_a_finish_does_not_ship_without_a_clean_record(self):
        NotDone = getattr(cl, NOT_DONE, None)
        for terminal, stop, bounds, score, verdict in _cases():
            with self.subTest(terminal=terminal):
                tmp = TemporaryDirectory()
                rec_cm = TemporaryDirectory()
                self.addCleanup(tmp.cleanup)
                self.addCleanup(rec_cm.cleanup)
                work = _job(tmp.name)
                packet = _packet(tmp.name, _maker(work), _suite(work))
                packet["bounds"].update(bounds)
                try:
                    summary = loop(
                        packet, record_dir=rec_cm.name, cwd=tmp.name,
                        evaluator_fn=lambda record, cwd, s=score, v=verdict: _scores(s, verdict=v),
                    )
                except Exception as exc:
                    if NotDone is None or not isinstance(exc, NotDone):
                        self.fail("loop() raised %s, not CustodyNotDone: %s" % (type(exc).__name__, exc))
                    self.assertIn(exc.exit_code, (1, 2, 3))
                    self.assertFalse(os.path.exists(os.path.join(rec_cm.name, "summary.json")))
                    self.assertFalse(os.path.exists(os.path.join(rec_cm.name, "escalation.json")))
                    if exc.exit_code in (2, 3):
                        self.assertFalse(os.path.exists(_custody(rec_cm.name)))
                    continue
                path = _custody(rec_cm.name)
                self.assertTrue(os.path.isfile(path), "loop() returned with no custody record")
                body = json.load(open(path, encoding="utf-8"))
                self.assertEqual(body.get("predicateType"), PREDICATE_TYPE)
                self.assertEqual(_hard(body), [])
                self.assertEqual(summary["terminal_state"], terminal)
                self.assertEqual(summary["stop"], stop)
                on_disk = json.load(open(os.path.join(rec_cm.name, "summary.json"), encoding="utf-8"))
                self.assertEqual(on_disk["terminal_state"], terminal)


class SeamTests(_Bar):
    def test_signature_has_no_new_parameter(self):
        self.assertEqual(set(inspect.signature(loop).parameters), {
            "packet", "record_dir", "cwd", "timeout_s", "commit", "evaluator_fn",
        })

    def test_seam_is_the_emitter_not_close(self):
        """The seam names the source; it does not close instead of emitting.

        AMENDED under the Owner's "update-test" ruling. The old form ran the seam and a
        twin on the same directory with NO document and required equal exit codes. Under
        document supply the two differ by design (the bare twin refused for spec-version,
        the seam reaching the emitter), so equal exits measured the supply, not the property.
        It is replaced, not deleted.

        What is held, each a property a private closer cannot satisfy:

        1. SOURCE. The seam's source names the emitter and not the close command.

        2. THE SAME FIXTURE, THE SAME DOCUMENT. The twin is a byte-copy of the job directory
           exactly as it stood BEFORE the seam ran, and it is handed the SAME custody document
           the seam supplies (`inputs/custody.json: custody_spec`, from the pin). Both sides
           therefore reach the emitter's version resolution: the comparison measures the seam's
           behaviour, not whether a version was found. The only field in a record that the job
           directory's name reaches is `x-plumbline.job_id` (the emitter's one path-derived
           value), so each record is compared after that name is rewritten to one placeholder
           (`_sanitise`). Both runs share `$PLUMBLINE_EMIT_NOW`, so the emission clock is the
           same instant and a wall-clock tick is not a difference. Nothing else may differ.

        3. NOT A CLOSER: THE RECORD IS THE EMITTER'S. Where the bare emitter emits (0, or 1
           with named gaps), the seam's exit equals the twin's and its record, name-sanitised,
           is identical to the twin's: the seam supplies the document and adds no behaviour the
           emitter lacks. Where the bare emitter refuses (2 or 3), it writes nothing, the
           pre-existing record — a sentinel the emitter can never write — must survive
           byte-for-byte, and the seam's exit must be a refusal too.

        4. A CLOSER THAT RAN THE EMITTER. A closer that emits and then overwrites the record
           with its own bytes is caught by 3: its bytes are not the twin's. A closer that never
           reaches the emitter is caught by 1 and by the surviving sentinel.

        A plant reddens this: a closer that writes its own record instead of the emitter's bytes
        fails the byte comparison in 3; a closer that never reaches the emitter fails 1 and leaves
        the sentinel test in 3 unsatisfied. A seam that supplies the document and runs the emitter
        is green. The plant and its failure text are recorded in the JOB 38b record.
        """
        fn = getattr(cl, SEAM, None)
        if not callable(fn):
            self.fail("kit.conductor_loop.emit_custody_for_finish is not bound")
        source = inspect.getsource(fn)
        self.assertIn("emit_custody", source)
        self.assertNotIn("plumbline_job", source)
        # A sentinel the emitter never writes: it is not a statement, and it holds no predicate.
        marker = json.dumps({"preexisting": True}, sort_keys=True).encode() + b"\n"
        self.assertNotIn(PREDICATE_TYPE.encode(), marker)
        checkout = _pinned_checkout()
        cases = (
            None,
            {"terminal_state": "open"},
            {"terminal_state": "accepted", "outcome": "accepted"},
        )
        pinned = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        prior = os.environ.get("PLUMBLINE_EMIT_NOW")
        os.environ["PLUMBLINE_EMIT_NOW"] = pinned
        try:
            for packet in cases:
                with self.subTest(packet=packet):
                    with TemporaryDirectory() as root:
                        left = os.path.join(root, "aaaaaaaa")
                        right = os.path.join(root, "aaaaaaab")
                        for side in (left, right):
                            if packet is not None:
                                _dump(os.path.join(side, "packet.json"), packet)
                            _dump(_custody(side), {"preexisting": True})
                            with open(_custody(side), "wb") as fh:
                                fh.write(marker)
                        # 2. The twin is the job dir BEFORE the seam, byte for byte, with its own name.
                        for base, dirs, files in os.walk(left):
                            rel = os.path.relpath(base, left)
                            dest = os.path.join(right, rel) if rel != "." else right
                            os.makedirs(dest, exist_ok=True)
                            for name in files:
                                shutil.copyfile(os.path.join(base, name), os.path.join(dest, name))
                        code = fn(left, {"terminal_state": "accepted", "outcome": "accepted", "stop": "accepted"})
                        # 3. The twin gets the SAME document the seam supplies: emitter against emitter.
                        twin = _emitter(right, checkout)
                        left_bytes = _read(_custody(left))
                        twin_bytes = _read(_custody(right))
                        if twin in (2, 3) or twin_bytes == marker:
                            # The bare emitter refused (2 or 3) and wrote nothing: the sentinel survives,
                            # and the seam did not turn the refusal into a ship.
                            self.assertEqual(left_bytes, marker,
                                             "the seam wrote a record where the bare emitter refuses: it closed")
                            self.assertNotEqual(code, 0,
                                                "the seam returned 0 where the bare emitter refuses")
                        else:
                            # The bare emitter emitted (0, or 1 with named gaps): the seam must be that
                            # emitter, byte for byte, up to the job-directory name the record carries.
                            self.assertEqual(code, twin,
                                             "seam exit %r != the emitter's %r on the same fixture" % (code, twin))
                            self.assertIsNotNone(left_bytes, "the seam wrote no record where the emitter did")
                            self.assertEqual(_sanitise(left_bytes, left), _sanitise(twin_bytes, right),
                                             "the seam's record is not the emitter's on the same fixture")
                            self.assertEqual(
                                (json.loads(left_bytes) if left_bytes else {}).get("predicateType"),
                                PREDICATE_TYPE,
                                "the seam left a record that is not a custody statement")
        finally:
            if prior is None:
                os.environ.pop("PLUMBLINE_EMIT_NOW", None)
            else:
                os.environ["PLUMBLINE_EMIT_NOW"] = prior


class PatchedTests(_Bar):
    def _patch(self, fake):
        return mock.patch.object(cl, SEAM, fake, create=True)

    def test_exit_0_ships_each_terminal_state(self):
        for terminal, stop, bounds, score, verdict in _cases():
            with self.subTest(terminal=terminal):
                seen = {"n": 0}

                def fake(record_dir, summary, terminal=terminal, seen=seen):
                    seen["n"] += 1
                    seen["record_dir"] = record_dir
                    seen["terminal_state"] = summary.get("terminal_state")
                    seen["stop"] = summary.get("stop")
                    self.assertFalse(os.path.exists(os.path.join(record_dir, "summary.json")))
                    self.assertFalse(os.path.exists(os.path.join(record_dir, "escalation.json")))
                    path = _custody(record_dir)
                    _dump(path, _clean_record())
                    seen["bytes"] = open(path, "rb").read()
                    return 0

                with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
                    work = _job(tmp)
                    packet = _packet(tmp, _maker(work), _suite(work))
                    packet["bounds"].update(bounds)
                    with self._patch(fake):
                        summary = loop(
                            packet, record_dir=rec, cwd=tmp,
                            evaluator_fn=lambda record, cwd, s=score, v=verdict: _scores(s, verdict=v),
                        )
                    self.assertEqual(seen["n"], 1, "loop() finished without calling emit_custody_for_finish")
                    self.assertEqual(os.path.realpath(seen["record_dir"]), os.path.realpath(rec))
                    self.assertEqual(seen["terminal_state"], terminal)
                    self.assertEqual(seen["stop"], stop)
                    self.assertEqual(summary["terminal_state"], terminal)
                    self.assertEqual(summary["stop"], stop)
                    path = _custody(rec)
                    self.assertEqual(open(path, "rb").read(), seen["bytes"])
                    body = json.load(open(path, encoding="utf-8"))
                    self.assertEqual(body.get("predicateType"), PREDICATE_TYPE)
                    self.assertEqual(_hard(body), [])
                    self.assertTrue(os.path.isfile(os.path.join(rec, "summary.json")))

    def test_exit_1_is_not_done(self):
        self._not_a_ship(1, write=_gapped_record())

    def test_exit_2_is_not_done(self):
        self._not_a_ship(2, write=None)

    def test_exit_3_is_not_done(self):
        self._not_a_ship(3, write=None)

    def _not_a_ship(self, code, write):
        NotDone = _not_done(self)
        seen = {"n": 0}

        def fake(record_dir, summary):
            seen["n"] += 1
            self.assertFalse(os.path.exists(os.path.join(record_dir, "summary.json")))
            if write is not None:
                _dump(_custody(record_dir), write)
            return code

        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, _maker(work), _suite(work), bounds={"cap": 1})
            with self._patch(fake):
                with self.assertRaises(NotDone) as caught:
                    loop(
                        packet, record_dir=rec, cwd=tmp,
                        evaluator_fn=lambda record, cwd: _scores(1),
                    )
            self.assertEqual(seen["n"], 1, "loop() finished without calling emit_custody_for_finish")
            self.assertEqual(caught.exception.exit_code, code)
            self.assertFalse(os.path.exists(os.path.join(rec, "summary.json")))
            self.assertFalse(os.path.exists(os.path.join(rec, "escalation.json")))
            path = _custody(rec)
            if write is None:
                self.assertFalse(os.path.exists(path))
            else:
                body = json.load(open(path, encoding="utf-8"))
                self.assertNotEqual(_hard(body), [])

    def test_refusal_does_not_call_the_seam(self):
        seen = {"n": 0}

        def fake(record_dir, summary):
            seen["n"] += 1
            return 0

        with TemporaryDirectory() as tmp, TemporaryDirectory() as rec:
            work = _job(tmp)
            packet = _packet(tmp, _maker(work), _suite(work))
            packet["ratified"] = False
            with self._patch(fake):
                with self.assertRaises(ValueError):
                    loop(packet, record_dir=rec, cwd=tmp)
            self.assertEqual(seen["n"], 0)
            self.assertFalse(os.path.exists(os.path.join(rec, "summary.json")))
            self.assertFalse(os.path.exists(_custody(rec)))


def _read(path):
    """The file's bytes, or None when it is absent."""
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        return fh.read()


def _sanitise(body, job):
    """`body` with the job directory's name rewritten to one placeholder.

    The emitter's record carries the job directory's basename in exactly one place —
    `predicate.x-plumbline.job_id` (the only path-derived value it writes; see
    kit/emit_custody.py, `job_id = packet.get("job_id") or job.name`). Rewriting that
    basename, and the absolute job path should one ever appear, lets the seam's record and
    the twin's be compared byte for byte while naming exactly which bytes are allowed to
    differ: the job's own name, and nothing else.
    """
    if body is None:
        return None
    name = os.path.basename(os.path.abspath(job)).encode()
    body = body.replace(os.path.abspath(job).encode(), b"<JOB>")
    if name:
        body = body.replace(b'"' + name + b'"', b'"<JOB>"')
    return body


def _pinned_checkout():
    """The custody checkout the seam attests: `$PLUMBLINE_CUSTODY`, else `<repo>/custody`, at the pin's commit.

    This is the document the seam supplies as `inputs/custody.json: custody_spec` (from
    tools/pin.json, the field kit/emit_custody.py reads). A twin given the SAME document is the
    comparison that measures the seam against the emitter rather than against the supply: both
    reach the emitter's version resolution, so a difference in the record is a difference in
    behaviour, not in whether a version was found. Returns None when no checkout at the pin's
    commit is present, in which case the twin is a bare run and the seam's supply is the only
    difference — the refuse branch below.
    """
    try:
        with open(PIN, encoding="utf-8") as fh:
            commit = json.load(fh)["custody"]["commit"]
    except (OSError, ValueError, KeyError):
        return None
    candidates = []
    env = (os.environ.get("PLUMBLINE_CUSTODY") or "").strip()
    if env:
        candidates.append(env)
    candidates.append(os.path.join(os.path.dirname(ROOT), "custody"))
    candidates.append(os.path.join(ROOT, "custody"))
    for candidate in candidates:
        checkout = os.path.abspath(os.path.expanduser(candidate))
        if not os.path.isfile(os.path.join(checkout, "SPEC.md")):
            continue
        proc = subprocess.run(["git", "-C", checkout, "rev-parse", "HEAD"],
                              capture_output=True, text=True)
        if proc.returncode == 0 and (proc.stdout or "").strip() == commit:
            return checkout
    return None


def _emitter(job, checkout=None):
    """Run kit/emit_custody.py over `job` exactly as a bare run would: `--job-dir`, no other flag.

    When `checkout` is given the twin is handed the SAME custody document the seam supplies, by
    writing `inputs/custody.json: custody_spec` — the field the emitter already reads — so the
    comparison is emitter against emitter on one fixture. The test pins `$PLUMBLINE_EMIT_NOW`
    so the emission clock is not a difference; the only bytes allowed to differ
    between the two records are the job's own name (see `_sanitise`). When it is not, the twin
    is a bare run: it is given no document, so whether it emits or refuses is the emitter's own
    answer on that directory.
    """
    if checkout is not None:
        _dump(os.path.join(job, "inputs", "custody.json"), {"custody_spec": checkout})
    proc = subprocess.run(
        [PY, EMITTER, "--job-dir", str(job)],
        capture_output=True, text=True,
    )
    return proc.returncode


if __name__ == "__main__":
    unittest.main()
