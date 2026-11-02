#!/usr/bin/env python3
"""
The discoverability gate's decision, as a PURE FUNCTION.

Pure on purpose: the acceptance tests in tests/test_discoverability_gate.py import this directly, so the
thing under test is the decision and not the plugin machinery around it. A test that had to stand up a
Hermes plugin to check a refusal would be testing the host.

It reads the rules from data (gate/discoverability-rules.json) and contains no thresholds of its own.
Every threshold is in the file, which is what makes the definition portable to a host that is not Hermes.
"""
import json
import pathlib
import re

RULES_PATH = pathlib.Path(__file__).resolve().parent / 'discoverability-rules.json'


def load_rules(path=None):
    return json.loads(pathlib.Path(path or RULES_PATH).read_text())


def _norm(s):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', str(s or '').lower())).strip()


def _tokens(s):
    return set(_norm(s).split())


def _names_a_method(text, methods):
    """An attempt counts only if it names HOW — one of the declared methods. 'I thought about it' is not
    an attempt, and the difference is the whole point of the gate."""
    low = str(text or '').lower()
    return [m for m, triggers in methods.items() if any(t in low for t in triggers)]


def validate_escalation(payload, rules=None):
    """Returns {'ok': bool, 'refusals': [str]}. Never raises on a malformed payload — a refusal must be
    the output, because an exception in a gate is an escalation that silently did not happen."""
    r = rules or load_rules()
    p = payload if isinstance(payload, dict) else {}
    refusals = []

    question = p.get('question', '')

    # 1. What was tried, and did it name a method.
    attempted = p.get('attempted') or []
    if isinstance(attempted, str):
        attempted = [attempted]
    attempted = [a for a in attempted if str(a).strip()]
    if len(attempted) < r['minimum_attempts']:
        refusals.append(
            f"no attempt recorded: `attempted` must list at least {r['minimum_attempts']} thing that was "
            f"searched, measured, read, probed or run. Nothing was tried, so this is not yet a question "
            f"for the Owner."
        )
    else:
        unnamed = [a for a in attempted if not _names_a_method(a, r['declared_methods'])]
        if unnamed:
            refusals.append(
                "attempt names no declared method: "
                + '; '.join(f'"{str(u)[:60]}"' for u in unnamed)
                + f". Each attempt must name HOW — one of {sorted(r['declared_methods'])}. "
                  f"\"I thought about it\" is not an attempt."
            )

    # 2. Why no observable answer exists — and it must not merely restate the question.
    why = _norm(p.get('why_undecidable'))
    if not why:
        refusals.append(
            "why_undecidable is missing: state why no observable answer exists in the record. If one "
            "does exist, this escalation should not be happening."
        )
    elif len(why) < r['minimum_why_chars']:
        refusals.append(
            f"why_undecidable is too short ({len(why)} chars, minimum {r['minimum_why_chars']}): a "
            f"reason, not a restatement, and it must survive being read on its own."
        )
    else:
        w, q = _tokens(why), _tokens(question)
        if w and q and len(w & q) / len(w) >= r['restatement_token_overlap']:
            refusals.append(
                f"why_undecidable merely restates the question ({len(w & q)}/{len(w)} of its words come "
                f"from it): say what KIND of answer is missing — a value, a priority, a risk appetite — "
                f"not the question again."
            )

    # 3. Options, and enough of them.
    options = p.get('options') or []
    if isinstance(options, str):
        options = [options]
    options = [o for o in options if str(o).strip()]
    if len(options) < r['minimum_options']:
        refusals.append(
            f"{len(options)} option(s) given, minimum {r['minimum_options']}: a question without options "
            f"is work pushed back. Each option must carry what it costs."
        )

    # 4. The recommendation, and that it names a real option.
    rec = p.get('recommendation')
    if not str(rec or '').strip():
        refusals.append(
            "no recommendation: say which option you would take and why. This is the defect stated "
            "verbatim — asking the Owner to choose without one is the machine working him."
        )
    elif r.get('require_recommendation_names_an_option') and options:
        nrec = _norm(rec)
        if not any(nrec == _norm(o) or _norm(o) in nrec or nrec in _norm(o) for o in options):
            refusals.append(
                f"the recommendation does not name one of the options: it reads \"{str(rec)[:70]}\" and "
                f"none of the {len(options)} options matches. Recommend one of THESE, or add the option "
                f"you actually mean."
            )

    # 5. Which seat is answering.
    if r.get('require_seat'):
        seat = str(p.get('seat') or '').strip()
        if not seat:
            refusals.append(
                "no seat named: the Owner's rule is that every escalation asks which seat is answering "
                f"— one of {r['seats']}. A question answered in the wrong capacity is answered twice."
            )
        elif seat not in r['seats']:
            refusals.append(
                f"seat \"{seat}\" is not one of the seven: {r['seats']}."
            )

    return {'ok': not refusals, 'refusals': refusals}


if __name__ == '__main__':
    import sys
    doc = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    out = validate_escalation(doc)
    print(json.dumps(out, indent=2))
    sys.exit(0 if out['ok'] else 1)
