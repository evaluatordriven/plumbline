#!/usr/bin/env python3
"""
Validate the constitution — the LIVE file and the §3 structural rules, in whichever state the frame is in.

WHY THIS WAS REWRITTEN. The first version ran its structural cases against the live file, assuming it was an
unratified draft. The moment the Owner ratified it, the file stopped having a `proposed` block and the test
died with KeyError: 'proposed' — a test that breaks on the very transition it exists to police, and one that
would have reported nothing useful at exactly the moment the state changed. So the structural cases now run
against SYNTHETIC documents built here, and the live file is checked for the state it actually claims.

The rules under test (constitution.schema.json, allOf):
  ratified:false ->  `proposed` REQUIRED; buyer, specialist, values, principles, escalation_classes and
                     human_seat must be ABSENT. This is Contracts §3's must-ask rule: an unratified value
                     may not occupy the place a configured value occupies, or the next reader takes it as
                     configured.
  ratified:true  ->  the reverse: buyer, specialist, values, principles REQUIRED; `proposed` must be ABSENT.
"""
import copy
import json
import pathlib
import sys

from jsonschema import Draft202012Validator

SHIP = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = json.loads((SHIP / 'schemas' / 'constitution.schema.json').read_text())
LIVE = json.loads((SHIP / 'dot-plumbline' / 'constitution.json').read_text())
V = Draft202012Validator(SCHEMA)


def errs(doc):
    return [f'{"/".join(str(p) for p in e.path) or "(root)"}: {e.message}' for e in V.iter_errors(doc)]


def as_unratified(live):
    """Build an unratified draft carrying the same content, whatever state the live file is in."""
    if not live.get('ratified'):
        return copy.deepcopy(live)
    d = {'program': live['program'], 'version': live['version'] + '-DRAFT', 'ratified': False,
         'proposed': {'values': copy.deepcopy(live['values']),
                      'principles': copy.deepcopy(live['principles']),
                      'escalation_classes': copy.deepcopy(live['escalation_classes']),
                      'human_seat': live['human_seat'],
                      'rationale': 'synthesised for the test'}}
    if 'non_negotiable' in live:
        d['non_negotiable'] = live['non_negotiable']
    return d


def main():
    bad = total = 0
    draft = as_unratified(LIVE)

    def case(name, doc, should_pass, note=''):
        nonlocal bad, total
        total += 1
        e = errs(doc)
        ok = (not e) == should_pass
        bad += 0 if ok else 1
        print(f'  {"ok  " if ok else "FAIL"}  expect={"valid" if should_pass else "invalid":7} '
              f'got={"valid" if not e else f"INVALID ({len(e)})":10}  {name}{note}')
        if not ok:
            for m in e[:2]:
                print(f'           {m[:110]}')

    print(f'LIVE FILE — {SHIP / "dot-plumbline/constitution.json"}')
    case('the live file validates in the state it claims', LIVE, True,
         f'   [ratified={LIVE.get("ratified")}]')
    if LIVE.get('ratified'):
        case('a ratified file carries no `proposed` block', LIVE, 'proposed' not in LIVE)
        case('a ratified file names its Buyer', LIVE, bool(LIVE.get('buyer', {}).get('name')))
        case('a ratified file names its Specialist', LIVE, bool(LIVE.get('specialist', {}).get('name')))
    else:
        case('an unratified file carries `proposed`', LIVE, 'proposed' in LIVE)
        case('an unratified file names no Buyer', LIVE, 'buyer' not in LIVE)

    print('\nSTRUCTURAL RULES — run against a synthetic draft, so they survive ratification')
    case('a synthetic unratified draft is valid', draft, True)

    lifted = copy.deepcopy(draft)
    lifted['values'] = lifted['proposed']['values']
    case('values lifted to top level while unratified', lifted, False, '   [§3]')

    noprop = copy.deepcopy(draft)
    del noprop['proposed']
    case('`proposed` removed while unratified', noprop, False, '   [§3]')

    in_prop = copy.deepcopy(draft)
    in_prop['proposed']['buyer'] = {'name': 'S2', 'provenance': 'x'}
    case('a Buyer smuggled into `proposed`', in_prop, False, '   [additionalProperties:false]')

    promoted = copy.deepcopy(draft)
    promoted['ratified'] = True
    case('marked ratified with no Buyer or Specialist', promoted, False)

    complete = as_unratified(LIVE)
    complete['ratified'] = True
    complete['ratified_at'] = '2026-10-01'
    complete['ratified_by'] = 'S2'
    complete['buyer'] = {'name': 'S2 (the Owner)', 'provenance': 'Owner 2026-09-30: "I am the buyer."'}
    complete['specialist'] = {'name': 'The E-DI corpus at the pin, held by S2 as its Author',
                              'provenance': 'Owner: "It\'s me as Author."'}
    for k in ('values', 'principles', 'escalation_classes', 'human_seat'):
        complete[k] = complete['proposed'][k]
    del complete['proposed']
    case('a complete ratified constitution is valid', complete, True)

    vals = (LIVE.get('values') or LIVE.get('proposed', {}).get('values', []))
    missing = [v['name'] for v in vals if not v.get('decision_rule')]
    total += 1
    bad += len(missing)
    print(f'\n  values: {len(vals)}, without a decision_rule: {len(missing)} {missing}')

    print(f'\n  {"ALL CASES BEHAVED AS DESIGNED" if bad == 0 else f"{bad} DID NOT"}')
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
