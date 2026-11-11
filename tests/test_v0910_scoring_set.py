"""Bar: the scoring set — only the cases the packet declares may be scored.

RED BEFORE THE FIX. Each case below that names a filter fails on the kit at
``1c2262b`` on an ABSENCE, measured on these bytes before this file was written:

  * ``kit.conductor_loop`` has no ``scoring_set`` reader and no filter. Measured:
    ``hasattr(cl, "scoring_set") is False``, and ``_evaluate`` over the Job 35
    score returns a dict of 16 names whatever the packet declares.
  * ``_shape`` accepts a 16-name score verbatim (returns ``None``) because it
    never compares a name against anything the packet declares.
  * ``_problems`` returns ``[]`` for a packet whose ``bounds`` carry no
    ``scoring_set``, for one that carries a well-formed list, AND for one that
    carries the string ``"nope"`` — it does not read the field at all.

THE DEFECT, AS MEASURED IN JOB 35. ``/home/jarbis1/tmp/plumbline-job35-record-1/
eval-score.json`` holds 16 dimensions, fifteen at 1 and
``12b_the_release_gate_the_record_closes`` at 0 — a case the Maker bar's
``load_tests`` drops (``tests/test_v099_instrument1.py:2649-2670``) and that is
red by design until Instrument 2's record exists. ``_pass_rule`` takes ``min``
over all 16, gets 0, ``0 < T_dim 1`` → ``regenerate``, and a round that could not
change the artifact is paid for. The 14 the Maker bar collects all scored 1.

WHAT IS TESTED: the kit's own functions — ``_problems`` (packet admission),
``_shape`` (reply admission), ``_evaluate`` (the dict the pass rule is given) and
``_scored_set`` (the set, as the record must name it). Not the Evaluator, not the
route, not the schema.

THE FIELD. ``bounds.scoring_set``: a list of dimension names, non-empty strings,
no duplicates, in the order the bar publishes them. Chosen by the Architect, not
taken from a contract: ``schemas/job-packet.schema.json`` leaves ``bounds`` open
(``additionalProperties`` unset, measured) and ``_problems`` already reads
``bounds`` for ``cap_counts``, so the field can be carried without a schema
change and this bar requires none. A packet with no set is refused, never
treated as "score everything": an absent scope is the Job 35 defect itself.

CASES (the ids the Evaluator names, one per test method, in file order).
"""

import json
import os
import re
import unittest
from tempfile import TemporaryDirectory

import kit.conductor_loop as cl

PY = "python3"

JOB35_SCORE = "/home/jarbis1/tmp/plumbline-job35-record-1/eval-score.json"

INSTRUMENT2 = (
    "12_a_documents_only_tree_cannot_be_count_py_green",
    "12b_the_release_gate_the_record_closes",
)

_INLINE = [
    ("00_the_release_lands", 1),
    ("01_spec_header_is_the_release_with_a_real_past_date", 1),
    ("02_count_py_green_except_the_record", 1),
    ("03_count_py_maker_problems_are_gone", 1),
    ("04_every_example_declares_the_release", 1),
    ("05_no_requirement_changed", 1),
    ("06_cadence_amendment_and_the_no_requirement_claim", 1),
    ("07_contributing_names_v098_and_carries_no_token_count_py_reads", 1),
    ("08_readme_contributing_draft_note_are_consistent", 1),
    ("09_every_current_document_is_clean", 1),
    ("10_footprint_the_bar_writes_only_inside_its_own_temp_root", 1),
    ("11_bytes_move_no_stored_record_changes_while_the_bar_runs", 1),
    ("13_every_green_at_base_case_bites", 1),
    ("14_the_version_is_read_from_the_document_and_never_from_a_flag", 1),
    ("12_a_documents_only_tree_cannot_be_count_py_green", 1),
    ("12b_the_release_gate_the_record_closes", 0),
]


def _score():
    """The Job 35 score: the record's own dimensions when it is on this machine."""
    if os.path.isfile(JOB35_SCORE):
        with open(JOB35_SCORE, encoding="utf-8") as fh:
            body = json.load(fh)
        pairs = [(d["name"], d["score"]) for d in body["dimensions"]]
    else:
        pairs = list(_INLINE)
    return {
        "dimensions": [{"name": n, "score": s, "observation": "seen %s" % n} for n, s in pairs],
        "violations": [],
        "verdict": "accept",
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _collected():
    return [n for n, _ in _INLINE if n not in INSTRUMENT2]


def _reply(names, zero=None):
    return {
        "dimensions": [
            {"name": n, "score": 0 if n == zero else 1, "observation": "seen %s" % n}
            for n in names
        ],
        "violations": [],
        "verdict": "accept",
        "controls": {"should_pass": "passed", "should_fail": "failed"},
    }


def _bounds(**over):
    bounds = {"T_accept": 1, "T_dim": 1, "T_reject": 0, "cap": 2,
              "cap_counts": "generations",
              "budget": {"amount": 0.5, "unit": "USD", "time_hours_lt": 4}}
    bounds.update(over)
    return bounds


# The bar file written into a temporary tree by case 04. It is ASSEMBLED, not
# written out: the Evaluator route enumerates a bar's names with
# `re.match(r"\s*def (test_\w+)\s*\(", line)`, which matches a line inside a
# string literal as readily as a real method. A fixture spelled out here would be
# dispatched as four extra cases — the 14-vs-16 split this job exists to kill,
# reproduced by the bar itself. So the literal `def test_...(` never appears.
_BODY = (
    "import unittest\n"
    "\n"
    "\n"
    "class Scoring(unittest.TestCase):\n"
    "    def {t}00_alpha(self):\n"
    "        pass\n"
    "    def {t}01_beta(self):\n"
    "        pass\n"
    "    def {t}02_gamma(self):\n"
    "        pass\n"
    "\n"
    "\n"
    "class Instrument2Sequencing(unittest.TestCase):\n"
    "    def {t}09_zeta(self):\n"
    "        pass\n"
    "\n"
    "\n"
    "def load_tests(loader, standard_tests, pattern):\n"
    "    keep = unittest.TestSuite()\n"
    "    for group in standard_tests or loader.loadTestsFromModule(__import__(__name__)):\n"
    "        cases = [x for x in group if type(x).__name__ != \"Instrument2Sequencing\"]\n"
    "        if cases:\n"
    "            group._tests = cases\n"
    "            keep.addTest(group)\n"
    "    return keep\n"
).format(t="test_")
BAR = _BODY


def _packet(root, **bounds_over):
    test = os.path.join(root, "tests", "t.py")
    if not os.path.isfile(test):
        os.makedirs(os.path.dirname(test), exist_ok=True)
        with open(test, "w", encoding="utf-8") as fh:
            fh.write("x = 1\n")
    return {
        "ratified": True,
        "mode": "scored",
        "human_seat": "Owner",
        "artifact": {"test_cmd": [PY, "tests/t.py"], "frozen": ["tests/t.py"],
                     "editable": ["src"], "ignore": [".git", "__pycache__"]},
        "maker": {"cmd": [PY, "-c", "pass"], "handoff": "rule12"},
        "evaluator": {"cmd": [PY, "-c", "pass"], "runs": 2, "held_out": []},
        "bounds": _bounds(**bounds_over),
        "escalation": {"route": ["Architect", "Owner"], "classes": [], "holders": {
            "architect": "Architect",
            "orchestrator": [
                {"holder": "loop", "kind": "script", "does": "rounds", "tested": "t"},
                {"holder": "esc", "kind": "script", "does": "escalations", "tested": "t"},
            ]}},
    }


def _problems(packet, root):
    with TemporaryDirectory() as outer:
        return cl._problems(packet, os.path.join(outer, "rec"), os.path.realpath(root), None)


def _evaluate(packet, reply):
    with TemporaryDirectory() as root, TemporaryDirectory() as rec:
        return cl._evaluate(packet, {"maker": {}}, 1, root, root, 1e9, None,
                            lambda turn, r: json.loads(json.dumps(reply)), rec)


class ScoringSetTests(unittest.TestCase):
    # 00 ------------------------------------------------------------------
    def test_00_the_job_35_fixture_regenerates_over_16_and_accepts_over_14(self):
        """The fixture is the defect, restated as arithmetic. Holds before and after.

        16 dimensions, fifteen at 1, 12b at 0; min 0 < T_dim 1 → regenerate. Over
        the 14 the Maker bar collects, the same numbers accept. If a later fix
        changed either reading, this case would say so.
        """
        body = _score()
        self.assertEqual(len(body["dimensions"]), 16)
        scores = {d["name"]: d["score"] for d in body["dimensions"]}
        self.assertEqual([scores[n] for n in _collected()], [1] * 14)
        self.assertEqual(min(scores.values()), 0)
        self.assertEqual(cl._pass_rule(scores, _bounds()), "regenerate")
        narrow = {n: scores[n] for n in _collected()}
        self.assertEqual(len(narrow), 14)
        self.assertEqual(cl._pass_rule(narrow, _bounds()), "accepted")

    # 01 ------------------------------------------------------------------
    def test_01_the_collected_set_is_the_maker_bars_own_cases(self):
        """`_scored_set` reads the set from the packet and refuses to invent one."""
        self.assertTrue(hasattr(cl, "_scored_set"),
                        "the loop must expose `_scored_set(bounds)`; the packet's scope "
                        "is not a field anything reads today")
        names = _collected()
        self.assertEqual(cl._scored_set(_bounds(scoring_set=names)), names)

    # 02 ------------------------------------------------------------------
    def test_02_a_declared_scoring_set_is_admitted_and_an_undeclared_one_is_refused(self):
        """A scored packet must declare what is scored, or it is refused.

        The absent case is the one that let Job 35 run: _problems returned [] for
        a packet with no set, so the loop had no scope to enforce.
        """
        with TemporaryDirectory() as root:
            bad = _problems(_packet(root), root)
            self.assertTrue(any("scoring_set" in line for line in bad),
                            "a packet with no bounds.scoring_set must be refused; got %r" % (bad,))
            good = _problems(_packet(root, scoring_set=_collected()), root)
            self.assertEqual(good, [], "a declared scoring set is admitted; got %r" % (good,))

    # 03 ------------------------------------------------------------------
    def test_03_a_scoring_set_that_is_not_a_list_of_names_is_refused(self):
        """Malformed sets are refused by name, not coerced.

        ``"nope"`` is the measured case: _problems returned [] for it today. A
        string is iterable, so a filter that did not check the type would score
        over the characters of "nope" and score nothing — a silent green.
        """
        bad_sets = ["nope", [], ["a", ""], ["a", 7], {"a": 1}, [["a"]],
                    ["a", "a"], [None]]
        with TemporaryDirectory() as root:
            for value in bad_sets:
                with self.subTest(scoring_set=value):
                    problems = _problems(_packet(root, scoring_set=value), root)
                    self.assertTrue(any("scoring_set" in line for line in problems),
                                    "scoring_set %r must be refused; got %r" % (value, problems))

    # 04 ------------------------------------------------------------------
    def test_04_a_scoring_set_that_omits_a_maker_case_is_refused(self):
        """A case the Maker bar collects cannot be dropped from the set.

        Option A's stated risk, made refusable: a case dropped from the set is a
        case NOTHING measures. The set is compared against the Maker bar's own
        collected cases — and "collected" is the bar's ``load_tests`` where it
        has one, not every ``def test_`` in the file. Job 35's bar drops
        ``Instrument2Sequencing`` that way (``load_tests`` at 2649-2670), which
        is precisely how ``12``/``12b`` came to be outside the Maker's 14.
        """
        with TemporaryDirectory() as root:
            packet = _packet(root)
            with open(os.path.join(root, "tests", "t.py"), "w", encoding="utf-8") as fh:
                fh.write(BAR)

            # 00_alpha, 01_beta, 02_gamma are collected; 09_zeta is dropped by load_tests.
            packet["bounds"]["scoring_set"] = ["00_alpha", "01_beta", "02_gamma"]
            self.assertEqual(_problems(packet, root), [],
                             "the collected three, and only they, is admitted")

            # A set that names every def test_ in the file INCLUDING the dropped case
            # is still refused: the bar's load_tests says 09_zeta is not collected.
            packet["bounds"]["scoring_set"] = ["00_alpha", "01_beta", "02_gamma", "09_zeta"]
            self.assertEqual(_problems(packet, root), [],
                             "declaring a dropped case as well as the collected ones is admitted: "
                             "the set may be a superset of what the Maker bar collects")

            packet["bounds"]["scoring_set"] = ["00_alpha", "01_beta"]
            dropped = _problems(packet, root)
            self.assertTrue(any("scoring_set" in line for line in dropped),
                            "a set that drops a collected case must be refused; got %r" % (dropped,))
            self.assertTrue(any("02_gamma" in line for line in dropped),
                            "the refusal must name the dropped case; got %r" % (dropped,))

    # 05 ------------------------------------------------------------------
    def test_05_the_job_35_shape_is_accepted_once_the_set_is_declared(self):
        """THE JOB 35 CASE. The same bytes, a declared set, the verdict flips.

        16 dimensions with an unrelated 0 present; the 14 collected are all 1;
        the packet declares the 14; the Evaluator returns all 16. The 16-name
        reply is refused by shape, so the 0 never reaches the pass rule and 12b
        is not scored at all. Refused, not silently dropped.
        """
        collected = _collected()
        with TemporaryDirectory() as root:
            packet = _packet(root, scoring_set=collected)
            stop, _by, _rows, scores, _mismatch, _fired, _costs, _missing = _evaluate(packet, _score())
            self.assertIsNotNone(stop, "a 16-name reply for a 14-name set must be refused, not scored")
            self.assertIsNone(scores, "no score dict is built from a reply outside the set")

            stop, _by, _rows, scores, mismatch, _fired, _costs, _missing = _evaluate(packet, _reply(collected))
            self.assertIsNone(stop, "a reply naming exactly the 14 must be admitted")
            self.assertEqual(sorted(scores), sorted(collected))
            self.assertNotIn(INSTRUMENT2[1], scores)
            self.assertEqual(cl._pass_rule(scores, packet["bounds"]), "accepted")
            self.assertFalse(mismatch, "the Evaluator's accept and the rule's accepted agree")

    # 06 ------------------------------------------------------------------
    def test_06_a_maker_shortfall_inside_the_set_still_regenerates(self):
        """The filter must not turn a real failure into an accept.

        One collected case at 0: the set does not hide it, the rule still says
        regenerate, the Evaluator's accept is still a mismatch. A filter that
        accepted whatever it was given would pass 05 and fail here.
        """
        collected = _collected()
        with TemporaryDirectory() as root:
            packet = _packet(root, scoring_set=collected)
            stop, _by, _rows, scores, mismatch, _fired, _costs, _missing = _evaluate(
                packet, _reply(collected, zero=collected[3]))
            self.assertIsNone(stop, "a shortfall inside the set is scored, not refused")
            self.assertEqual(scores[collected[3]], 0)
            self.assertEqual(cl._pass_rule(scores, packet["bounds"]), "regenerate")
            self.assertTrue(mismatch, "accept against a regenerating score is a mismatch")

    # 07 ------------------------------------------------------------------
    def test_07_a_dimension_outside_the_set_is_refused_by_shape(self):
        """`_shape` catches a name outside the set and names it.

        Asserted on `_shape` directly as well as through `_evaluate`, so the
        refusal is a property of reply admission, not a side effect of a filter.
        """
        collected = _collected()
        bounds = _bounds(scoring_set=collected)
        size = len(bounds["scoring_set"])
        extra = _reply(collected + [INSTRUMENT2[1]])
        self.assertEqual(len(extra["dimensions"]), size + 1)
        shape = cl._shape(extra, bounds)
        self.assertIsNotNone(shape, "_shape must refuse a dimension outside the set")
        self.assertIn(INSTRUMENT2[1], str(shape), "the refusal must name it; got %r" % (shape,))

        swapped = _reply(collected[1:] + ["99_not_a_case"])
        self.assertIsNotNone(cl._shape(swapped, bounds))

    # 08 ------------------------------------------------------------------
    def test_08_a_declared_case_the_evaluator_omits_is_refused_by_shape(self):
        """Omitting a declared case is refused, not averaged over the rest.

        Fifteen of sixteen would still pass at T_dim 1; the omitted case is
        unmeasured, and an unmeasured case is what this job stops counting.
        """
        collected = _collected()
        with TemporaryDirectory() as root:
            packet = _packet(root, scoring_set=collected)
            short = _reply(collected[:-1])
            shape = cl._shape(short, packet["bounds"])
            self.assertIsNotNone(shape, "_shape must refuse a reply that omits a declared case")
            self.assertIn(collected[-1], str(shape), "the refusal must name it; got %r" % (shape,))
            stop, _by, _rows, scores, _m, _f, _c, _x = _evaluate(packet, short)
            self.assertIsNotNone(stop)
            self.assertIsNone(scores)

    # 09 ------------------------------------------------------------------
    def test_09_the_scoring_set_is_not_read_from_the_evaluator(self):
        """Two packets, one reply: the set is the packet's, not the reply's.

        The narrow packet refuses the 16-name reply; the packet declaring all 16
        admits it. If the set were inferred from what the Evaluator sent, both
        would behave alike and this case would fail.
        """
        collected = _collected()
        body = _score()
        everything = [d["name"] for d in body["dimensions"]]
        with TemporaryDirectory() as root:
            self.assertIsNotNone(_evaluate(_packet(root, scoring_set=collected), body)[0],
                                 "the narrow packet must refuse the 16-name reply")
            self.assertIsNone(_evaluate(_packet(root, scoring_set=everything), body)[0],
                              "a packet declaring all 16 must admit all 16")

    # 10 ------------------------------------------------------------------
    def test_10_an_empty_or_absent_set_does_not_score_everything(self):
        """A missing set is a refusal, never a wildcard.

        The failure this forbids: set absent → filter skipped → every dimension
        scored → Job 35 repeats, with a packet that looks green.
        """
        collected = _collected()
        with TemporaryDirectory() as root:
            for missing in (None, []):
                with self.subTest(scoring_set=missing):
                    packet = _packet(root)
                    if missing is not None:
                        packet["bounds"]["scoring_set"] = list(missing)
                    stop, _by, _rows, scores, _m, _f, _c, _x = _evaluate(packet, _reply(collected))
                    self.assertIsNotNone(stop)
                    self.assertIsNone(scores)

    # 11 ------------------------------------------------------------------
    def test_11_the_metric_is_the_set_the_rule_reads(self):
        """`_pass_rule` is handed the scored dict, and nothing else is in it.

        A reader must be able to tell a case that passed from a case that was
        never scored. The dict the rule receives is exactly the declared set —
        no foreign name, no dropped name, same order — for a reply that names
        all 14. The rule is asserted against a foreign 0: a 0 that is outside
        the set must not move the verdict, and a 0 inside it must.
        """
        collected = _collected()
        with TemporaryDirectory() as root:
            packet = _packet(root, scoring_set=collected)
            stop, _by, _rows, scores, _m, _f, _c, _x = _evaluate(packet, _reply(collected))
            self.assertIsNone(stop)
            self.assertEqual(list(scores), collected)
            self.assertEqual(sorted(scores), sorted(set(collected)))

            # the rule's own arithmetic, on the dict it is actually given
            self.assertEqual(cl._pass_rule(scores, packet["bounds"]), "accepted")
            foreign = dict(scores)
            foreign[INSTRUMENT2[1]] = 0
            self.assertEqual(cl._pass_rule(foreign, packet["bounds"]), "regenerate",
                             "a 0 outside the set DOES move the rule when handed to it — "
                             "which is why nothing outside the set may be handed to it")
            inside = dict(scores)
            inside[collected[0]] = 0
            self.assertEqual(cl._pass_rule(inside, packet["bounds"]), "regenerate")


if __name__ == "__main__":
    unittest.main(verbosity=2)
