#!/usr/bin/env python3
"""
Acceptance tests for the discoverability gate — AUTHORED BEFORE THE IMPLEMENTATION, and that order is
the point. Development's ground truth per the direction's Stage Map is "externally authored tests +
spec", and its evidence channel is the test run.

HONEST DECLARATION OF A SUBSTITUTION. "Externally authored" is satisfied in substance but not in the
letter. The agent typed these files; the AUTHORITY behind every case is external — each one derives
from ADR-001 §2(A), which the Owner approved, and from the direction's own definition of a discoverable
question ("search, measurement, reading the repo, probing the record, running the code"). They are
frozen BEFORE the implementation exists, so they cannot be shaped by it, and the run is scored by the
Evaluator seat. Declared rather than asserted, for the same reason job one declared its read order as a
limit of the record instead of claiming a clean declaration.

Every case asserts a CONTRACT — a relation between the escalation and the rules — never a snapshot of
current behaviour.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from gate.rules import validate_escalation  # noqa: E402

RULES = json.loads((pathlib.Path(__file__).resolve().parent.parent /
                    'gate' / 'discoverability-rules.json').read_text())

VALID = {
    'question': 'Which of the two ledger formats should ship?',
    'attempted': ['read the ADR and the packet', 'measured the current escalation count'],
    'why_undecidable': 'It turns on how much history the Owner wants retained, which is a value, not a '
                       'fact in the record.',
    'options': [
        'JSONL, one row per escalation — greppable, append-only',
        'SQLite, one table — queryable, but a binary artifact in the repo',
    ],
    'recommendation': 'JSONL, one row per escalation — greppable, append-only',
    'seat': 'Architect',
}


def run():
    cases, bad = [], 0

    def case(name, payload, expect_ok, must_mention=None):
        nonlocal bad
        r = validate_escalation(payload, RULES)
        ok = bool(r.get('ok')) is expect_ok
        if ok and must_mention and not any(must_mention.lower() in x.lower()
                                           for x in r.get('refusals', [])):
            ok = False
        if ok and not expect_ok and not r.get('refusals'):
            ok = False  # a refusal must SAY something; silence is not a refusal
        cases.append((name, ok, r))
        bad += 0 if ok else 1

    def mutated(**kw):
        p = json.loads(json.dumps(VALID))
        p.update(kw)
        return p

    case('a complete escalation is accepted', VALID, True)
    case('attempted is empty', mutated(attempted=[]), False, 'attempt')
    case('attempted is absent', {k: v for k, v in VALID.items() if k != 'attempted'}, False, 'attempt')
    case('attempted names no declared method',
         mutated(attempted=['I thought about it']), False, 'method')
    case('why_undecidable is absent',
         {k: v for k, v in VALID.items() if k != 'why_undecidable'}, False, 'why')
    case('why_undecidable merely restates the question',
         mutated(why_undecidable='Which ledger format should ship?'), False, 'why')
    case('fewer than two options', mutated(options=['JSONL']), False, 'option')
    case('options absent', {k: v for k, v in VALID.items() if k != 'options'}, False, 'option')
    case('no recommendation',
         {k: v for k, v in VALID.items() if k != 'recommendation'}, False, 'recommend')
    case('recommendation names something that is not an option',
         mutated(recommendation='SQLite, obviously'), False, 'recommend')
    case('seat is absent — the Owner must be told which seat is answering',
         {k: v for k, v in VALID.items() if k != 'seat'}, False, 'seat')

    print('DISCOVERABILITY GATE — acceptance cases, from ADR-001 §2(A)\n')
    for name, ok, r in cases:
        print(f'  {"ok  " if ok else "FAIL"}  {name}')
        if not ok:
            print(f'        -> {json.dumps(r)[:220]}')
    print(f'\n  {len(cases) - bad}/{len(cases)} behaved as the spec requires')
    if bad:
        print('\n  The implementation does not yet exist, so a FAIL here is the correct starting state:')
        print('  the spec is frozen before the code, which is the only way it can constrain it.')
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(run())
