"""Bar tests for job 2026-11-04-held-out-failopen: `_held_out` in kit/conductor_loop.py.

Written by the Architect; revised after the E-DI Evaluator's pre-freeze review and re-check
(ARCHITECT-RESPONSE-evaluator-review.md, ARCHITECT-RESPONSE-evaluator-recheck.md).
Job ratified by the Owner 2026-11-04 09:47 EST (relayed by the Chief of Staff); not frozen.
Red at evaluatordriven/plumbline 61683373a4cd1fff64fc1a766c21aca6cdfcc16e.
Drop-in path in the repository: tests/test_held_out_failopen.py (stdlib unittest; pytest also collects it).

Fault 1 (primary, fails OPEN): a held-out path that cannot be opened is skipped with `continue`, so the check
returns False and loop() records {"result": "pass"} for a check it never made (Contracts v1.27.0 §4.2, C39).
Fault 2 (secondary, fails CLOSED): any non-blank held-out line found anywhere in the text counts as a leak, so a
pretty-printed JSON held-out file's lone "{" or "}" line matches every JSON message.

Every fixture string below is synthetic, invented for these tests. None is held-out material of any job:
an expected value in the Maker's own repository is not held-out (Contracts §4.2 definition).

Interface pinned by the bar (ratified DECISIONS D2, D3, D4):
  * `_held_out(text, paths) -> bool` keeps its meaning: True = a held-out item was found in `text`.
  * A path that cannot be opened and read raises an exception (any subclass of Exception) whose message
    names the path. It never returns False, and never returns True (that would record a leak that did not happen).
    "Names the path" = contains the path as given, its absolute form, or its resolved (realpath) form.
  * loop() turns that into a stop named EXPECTED_STOP, terminal state needs_owner AND outcome needs_owner (D2;
    not no_observation), before any Maker dispatch
    in that round; the round record's `held_out` entry keeps `method` and `by`, has `result` "fail", and names
    the path. A start-of-run refusal ("packet refused", problems naming the path) is also accepted for the
    case where the path is already unreadable before round 1 (DECISIONS D3).
  * Structural lines (no alphanumeric character, e.g. "{", "},", "],") are not leak evidence; every line with an
    alphanumeric character still is, however short (D4: no length floor).

Row map (bar.md): K1 missing; K2 directory; K3 unopenable file, two real tests, no mock (a: symlink loop, ELOOP,
any uid; b: mode-000 file, EACCES, non-root runner); neither may be skipped; K4 missing after a readable path; K5 missing at start (loop); K6 lost mid-run
(loop); K7 stop declared, needs_owner/needs_owner; K8 pretty vs unrelated pretty JSON (incl. "},"/"]," lines);
K9 pretty vs compact JSON; K10 pretty held + clean run accepted (loop); G1 the nine still-a-leak / empty-list guards (incl.
1-, 2- and 3-character held lines: no length floor).
A skipped test scores 0 (bar.md §2); nothing in this file skips. Collected tests: exactly 20 (bar.md G7).
No test patches open/io/os: every unopenable fixture is a real OS-level error.
"""
import hashlib
import json
import os
import stat
import sys
import unittest
from tempfile import TemporaryDirectory

from kit import conductor_loop
from kit.conductor_loop import _held_out, loop

PY = sys.executable

# Stop name, terminal state and outcome ratified by the Owner (DECISIONS D2, 2026-11-04 09:47 EST).
EXPECTED_STOP = "held-out unreadable"
EXPECTED_TERMINAL = "needs_owner"
EXPECTED_OUTCOME = "needs_owner"
LEAK_STOP = "held-out leak"

# Synthetic held-out fixture: pretty-printed JSON whose structural lines include bare "{" / "}" / "[" and
# comma-trailed "}," / "],", plus one invented secret value.
SYNTH_SECRET = "PLUMBLINE-SYNTHETIC-CANARY-7f3e-QUOKKA-ZEBRA"
SYNTH_HELD_JSON = json.dumps({
    "case": "synthetic-fixture-only",
    "expected": [{"answer": SYNTH_SECRET}, {"answer_b": "synthetic-second-answer"}],
    "meta": {"origin": "synthetic-meta-origin"},
    "tail": "synthetic-tail-value",
}, indent=2) + "\n"
SYNTH_HELD_LINE = "synthetic held line: " + SYNTH_SECRET
SYNTH_SHORT_SECRET = "q7Z"  # a short alphanumeric held line: still a leak (D4 rejects a length floor)
SYNTH_TWO_CHAR_SECRET = "k9"  # 2 characters: catches a length floor of 3
SYNTH_ONE_CHAR_SECRET = "Q"  # 1 character: catches any length floor above 1


def _forms(path):
    """The accepted ways of naming a path: as given, absolute, resolved (bar.md §2, A2/Q3)."""
    return {path, os.path.abspath(path), os.path.realpath(path)}


def _names_path(path, text):
    return any(form in text for form in _forms(path))


def _write(root, name, text):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _packet(tmp, maker, suite, held):
    return {
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
            "held_out": list(held),
        },
        "bounds": {
            "T_accept": 1,
            "T_dim": 1,
            "T_reject": 0,
            "cap": 2,
            "cap_counts": "generations",
            "budget": {"amount": 0, "unit": "USD", "lt": False, "time_hours_lt": 2},
        },
        "escalation": {
            "route": ["Architect", "Owner"],
            "classes": [],
            "holders": {
                "architect": "E-DI Architect (agent)",
                "orchestrator": [
                    {"holder": "kit.conductor_loop.loop", "kind": "script", "does": "rounds", "tested": "rec#abc"},
                    {"holder": "escalation-agent", "kind": "model", "does": "escalations", "tested": "rec#def"},
                ],
            },
        },
    }


def _scores(score, verdict, violations=None):
    return {
        "dimensions": [{"name": "q", "score": score, "observation": "seen"}],
        "violations": violations or [],
        "verdict": verdict,
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _job(tmp, log_dir):
    """A one-file subject; the Maker writes 'yes' (suite passes) and appends one line per dispatch to a log."""
    _write(tmp, "tests/t.py", "pin\n")
    work = _write(tmp, "src/w.txt", "no\n")
    log = os.path.join(log_dir, "maker-dispatches.log")
    maker = [PY, "-c", (
        "import time; open(%r,'w').write('yes\\n'+str(time.time())); open(%r,'a').write('ran\\n')"
    ) % (work, log)]
    suite = [PY, "-c", "import sys; t=open(%r).read(); sys.exit(0 if t.startswith('yes') else 1)" % work]
    return maker, suite, log


def _dispatches(log):
    return len(open(log).read().splitlines()) if os.path.exists(log) else 0


def _round(rec, number):
    return json.load(open(os.path.join(rec, "round-%02d.json" % number)))


class HeldOutFailsClosedUnit(unittest.TestCase):
    """K1-K4: an unopenable held-out path is never read as 'no leak'."""

    def _assert_fails_closed(self, path, others=()):
        paths = list(others) + [path]
        try:
            got = _held_out("unrelated outgoing text", paths)
        except Exception as exc:  # the pinned form: raise, naming the path
            self.assertTrue(_names_path(path, str(exc)),
                            "the exception must name the unreadable path %s: %r" % (path, str(exc)))
            return
        self.fail("fail-open: _held_out returned %r for an unopenable held-out path %s" % (got, path))

    def test_missing_path_fails_closed(self):
        with TemporaryDirectory() as held:
            self._assert_fails_closed(os.path.join(held, "no-such-control.txt"))

    def test_directory_path_fails_closed(self):
        with TemporaryDirectory() as held:
            sub = os.path.join(held, "a-directory")
            os.makedirs(sub)
            self._assert_fails_closed(sub)

    def test_symlink_loop_fails_closed(self):
        """K3a (real OS error, any uid, no mock): a held-out path that is a symlink loop (a -> b, b -> a). Every
        open of it raises OSError (ELOOP), for root as well; no patching, so any way of opening the file is real."""
        with TemporaryDirectory() as held:
            path = os.path.join(held, "loop-a.txt")
            other = os.path.join(held, "loop-b.txt")
            os.symlink(other, path)
            os.symlink(path, other)
            # instrument self-check: the fixture really is unopenable on this filesystem
            with self.assertRaises(OSError, msg="instrument: a symlink loop opened on this filesystem"):
                os.close(os.open(path, os.O_RDONLY))
            self._assert_fails_closed(path)

    def test_unreadable_file_fails_closed(self):
        """K3b (real filesystem, real EACCES): a mode-000 file. Never skipped: as root the check cannot be observed,
        so the test FAILS with an instrument message (bar.md §2: the runner must not be root; a root run is an
        instrument failure, not scored, re-run as non-root: Owner ruling 2026-11-04 10:09 EST)."""
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.fail("instrument: runner is root, so a mode-000 file is readable and K3 cannot be observed; "
                      "bar.md §2 requires a non-root runner (record uid)")
        with TemporaryDirectory() as held:
            path = _write(held, "locked.txt", SYNTH_HELD_LINE + "\n")
            os.chmod(path, 0)
            try:
                self._assert_fails_closed(path)
            finally:
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)

    def test_missing_path_after_a_clean_readable_path_fails_closed(self):
        with TemporaryDirectory() as held:
            ok = _write(held, "readable.txt", SYNTH_HELD_LINE + "\n")
            self._assert_fails_closed(os.path.join(held, "gone.txt"), others=[ok])


class HeldOutPrettyJsonUnit(unittest.TestCase):
    """K8-K9: structural JSON lines are not a leak. G1: real leaks still found."""

    def test_pretty_json_held_file_vs_unrelated_pretty_json_text(self):
        with TemporaryDirectory() as held:
            path = _write(held, "control.json", SYNTH_HELD_JSON)
            text = json.dumps({
                "round": 1,
                "defects": [{"id": "V1", "observation": "unrelated"}, {"id": "V2", "observation": "other"}],
                "notes": {"by": "synthetic-evaluator"},
                "done": True,
            }, indent=2)
            held_lines = SYNTH_HELD_JSON.splitlines()
            # fixture self-check: comma-trailed structural lines are present in both and shared verbatim
            for structural in ("    },", "  ],", "  },"):
                self.assertIn(structural, held_lines)
                self.assertIn(structural, text.splitlines())
            # fixture self-check: the short-line guard probes are not lines of the pretty fixtures (no false positive)
            for probe in (SYNTH_ONE_CHAR_SECRET, SYNTH_TWO_CHAR_SECRET, SYNTH_SHORT_SECRET):
                self.assertNotIn(probe, [line.strip() for line in held_lines])
            self.assertIs(_held_out(text, [path]), False)

    def test_pretty_json_held_file_vs_compact_findings_text(self):
        with TemporaryDirectory() as held:
            path = _write(held, "control.json", SYNTH_HELD_JSON)
            text = json.dumps({"round": 1, "cap": 2, "best": None, "defects": [], "solutions": []})
            self.assertIs(_held_out(text, [path]), False)

    def test_verbatim_held_line_is_still_a_leak(self):
        with TemporaryDirectory() as held:
            path = _write(held, "control.txt", SYNTH_HELD_LINE + "\n")
            self.assertIs(_held_out("prefix " + SYNTH_HELD_LINE + " suffix", [path]), True)

    def test_held_file_sha256_is_still_a_leak(self):
        with TemporaryDirectory() as held:
            path = _write(held, "control.json", SYNTH_HELD_JSON)
            digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
            self.assertIs(_held_out("see " + digest, [path]), True)

    def test_secret_line_of_a_pretty_json_held_file_is_still_a_leak(self):
        with TemporaryDirectory() as held:
            path = _write(held, "control.json", SYNTH_HELD_JSON)
            secret_line = [line for line in SYNTH_HELD_JSON.splitlines() if SYNTH_SECRET in line][0]
            self.assertIs(_held_out("quoted: " + secret_line, [path]), True)

    def test_short_alphanumeric_held_line_is_still_a_leak(self):
        with TemporaryDirectory() as held:
            path = _write(held, "control.txt", SYNTH_SHORT_SECRET + "\n")
            self.assertIs(_held_out('{"note": "' + SYNTH_SHORT_SECRET + '"}', [path]), True)

    def test_two_character_alphanumeric_held_line_is_still_a_leak(self):
        with TemporaryDirectory() as held:
            path = _write(held, "control.txt", SYNTH_TWO_CHAR_SECRET + "\n")
            self.assertIs(_held_out('{"note": "' + SYNTH_TWO_CHAR_SECRET + '"}', [path]), True)

    def test_one_character_alphanumeric_held_line_is_still_a_leak(self):
        with TemporaryDirectory() as held:
            path = _write(held, "control.txt", SYNTH_ONE_CHAR_SECRET + "\n")
            self.assertIs(_held_out('{"note": "' + SYNTH_ONE_CHAR_SECRET + '"}', [path]), True)

    def test_secret_line_in_a_file_with_an_undecodable_byte_is_still_a_leak(self):
        with TemporaryDirectory() as held:
            path = os.path.join(held, "control.bin")
            with open(path, "wb") as fh:
                fh.write(b"\xff\xfe synthetic non-utf8 prefix\n" + SYNTH_HELD_LINE.encode("utf-8") + b"\n")
            self.assertIs(_held_out("prefix " + SYNTH_HELD_LINE + " suffix", [path]), True)

    def test_no_held_out_paths_is_no_leak(self):
        self.assertIs(_held_out("anything at all {", []), False)


class HeldOutLoop(unittest.TestCase):
    """K5, K6, K10 and G1: loop() records the fail-closed stop, method and result (Contracts §4.2), and stops
    false positives."""

    def test_missing_held_out_path_at_start_dispatches_nothing(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as held, TemporaryDirectory() as logs, \
                TemporaryDirectory() as rec:
            maker, suite, log = _job(tmp, logs)
            missing = os.path.join(held, "absent-control.txt")
            packet = _packet(tmp, maker, suite, [missing])
            try:
                summary = loop(packet, record_dir=rec, cwd=tmp,
                               evaluator_fn=lambda record, cwd: _scores(1, "accept"))
            except ValueError as exc:  # accepted form 1: packet refused before any command
                self.assertEqual(_dispatches(log), 0)
                body = json.load(open(os.path.join(rec, "escalation.json")))
                self.assertEqual(body["stop"], "packet refused")
                self.assertTrue(any(_names_path(missing, line) for line in body["problems"]), body["problems"])
                self.assertTrue(_names_path(missing, str(exc)), str(exc))
                return
            # accepted form 2: a recorded fail-closed stop in round 1, before the Maker runs
            self.assertEqual(_dispatches(log), 0, "the Maker ran although the held-out check could not be made")
            self.assertEqual(summary["stop"], EXPECTED_STOP)
            self.assertEqual(summary["terminal_state"], EXPECTED_TERMINAL)
            self.assertEqual(summary["outcome"], EXPECTED_OUTCOME)
            held_rec = _round(rec, 1)["held_out"]
            self.assertEqual(held_rec["result"], "fail")
            self.assertTrue(str(held_rec.get("method") or "").strip())
            self.assertTrue(str(held_rec.get("by") or "").strip())
            self.assertTrue(_names_path(missing, json.dumps(held_rec)), held_rec)
            self.assertFalse(os.path.exists(os.path.join(rec, "findings-01.json")))

    def test_held_out_path_lost_mid_run_stops_before_round_2(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as held, TemporaryDirectory() as logs, \
                TemporaryDirectory() as rec:
            maker, suite, log = _job(tmp, logs)
            control = _write(held, "control.txt", SYNTH_HELD_LINE + "\n")

            def fn(record, cwd):
                if os.path.exists(control):
                    os.remove(control)  # the held-out file disappears after round 1 was checked
                return _scores(0.5, "regenerate", violations=[{
                    "id": "V1", "class": "artifact_missed_standard", "observation": "synthetic shortfall",
                }])

            summary = loop(_packet(tmp, maker, suite, [control]), record_dir=rec, cwd=tmp, evaluator_fn=fn)
            self.assertEqual(_dispatches(log), 1, "round 2 dispatched the Maker without a held-out check")
            self.assertEqual(summary["stop"], EXPECTED_STOP)
            self.assertEqual(summary["terminal_state"], EXPECTED_TERMINAL)
            self.assertEqual(summary["outcome"], EXPECTED_OUTCOME)
            self.assertEqual(_round(rec, 1)["held_out"]["result"], "pass")
            held_rec = _round(rec, 2)["held_out"]
            self.assertEqual(held_rec["result"], "fail")
            self.assertTrue(str(held_rec.get("method") or "").strip())
            self.assertTrue(str(held_rec.get("by") or "").strip())
            self.assertTrue(_names_path(control, json.dumps(held_rec)), held_rec)
            self.assertFalse(os.path.exists(os.path.join(rec, "findings-02.json")))

    def test_pretty_json_held_file_does_not_stop_a_clean_run(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as held, TemporaryDirectory() as logs, \
                TemporaryDirectory() as rec:
            maker, suite, log = _job(tmp, logs)
            control = _write(held, "control.json", SYNTH_HELD_JSON)
            summary = loop(_packet(tmp, maker, suite, [control]), record_dir=rec, cwd=tmp,
                           evaluator_fn=lambda record, cwd: _scores(1, "accept"))
            self.assertNotEqual(summary["stop"], LEAK_STOP, "false positive: a lone '{' line read as a leak")
            self.assertEqual(summary["terminal_state"], "accepted")
            self.assertEqual(_dispatches(log), 1)
            self.assertEqual(_round(rec, 1)["held_out"]["result"], "pass")

    def test_genuine_leak_still_stops_and_never_reaches_findings(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as held, TemporaryDirectory() as logs, \
                TemporaryDirectory() as rec:
            maker, suite, log = _job(tmp, logs)
            control = _write(held, "control.txt", SYNTH_HELD_LINE + "\n")

            def fn(record, cwd):
                return _scores(0.5, "regenerate", violations=[{
                    "id": "V1", "class": "artifact_missed_standard", "observation": "x",
                    "remedy": "see " + SYNTH_HELD_LINE,
                }])

            summary = loop(_packet(tmp, maker, suite, [control]), record_dir=rec, cwd=tmp, evaluator_fn=fn)
            self.assertEqual(summary["stop"], LEAK_STOP)
            self.assertEqual(summary["terminal_state"], "needs_owner")
            self.assertFalse(os.path.exists(os.path.join(rec, "findings-02.json")))
            for name in os.listdir(rec):
                if name.startswith("findings"):
                    self.assertNotIn(SYNTH_SECRET, open(os.path.join(rec, name)).read())


class StopNameDeclared(unittest.TestCase):
    """K7: the new stop is a declared state mapped to terminal needs_owner AND outcome needs_owner (D2; an outcome
    of no_observation is the alternative D2 rejected), distinct from the leak stop."""

    def test_stop_is_declared_and_maps_to_needs_owner(self):
        names = {getattr(conductor_loop, n) for n in dir(conductor_loop) if n.isupper()
                 and isinstance(getattr(conductor_loop, n), str)}
        self.assertIn(EXPECTED_STOP, names)
        self.assertNotEqual(EXPECTED_STOP, LEAK_STOP)
        self.assertIn(EXPECTED_STOP, conductor_loop._STATES)
        terminal, outcome = conductor_loop._STATES[EXPECTED_STOP]
        self.assertEqual(terminal, EXPECTED_TERMINAL)
        self.assertEqual(outcome, EXPECTED_OUTCOME, "D2: outcome is needs_owner, not no_observation")


if __name__ == "__main__":
    unittest.main()
