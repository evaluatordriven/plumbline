#!/usr/bin/env python3
"""
Perform the ratification. A validated transform, not a hand edit.

The Owner said "Constitution Ratified" on 2026-09-30. Under the schema that is not a comment — it is a
STRUCTURAL change, and the schema says exactly which one:

  ratified:true  ->  `proposed` must be ABSENT, and buyer, specialist, values, principles must be PRESENT
                     at the top level. (constitution.schema.json, allOf case 1.)
  ratified:false ->  the reverse, with everything standing in `proposed`.

So this moves values, principles, escalation_classes and human_seat up from `proposed`, admits the two
seat rows the Owner named (S2 as Buyer; the E-DI corpus held by S2 as its Author as Specialist), records
who ratified and when, and drops the DRAFT suffix from the version.

It VALIDATES BEFORE WRITING. A transform that writes first and checks after is how a broken frame gets
committed, and this file is the frame.
"""
import json
import pathlib
import subprocess
import sys

from jsonschema import Draft202012Validator

SHIP = pathlib.Path(__file__).resolve().parent.parent
SRC = SHIP / 'dot-plumbline' / 'constitution.json'
SCHEMA = json.loads((SHIP / 'schemas' / 'constitution.schema.json').read_text())


def main():
    today = subprocess.run(['date', '+%Y-%m-%d'], capture_output=True, text=True).stdout.strip()
    d = json.loads(SRC.read_text())
    if d.get('ratified'):
        print('already ratified — nothing to do')
        return 0

    p = d['proposed']
    out = {
        'program': d['program'],
        'version': d['version'].replace('-DRAFT', ''),
        'ratified': True,
        'ratified_at': today,
        'ratified_by': 'S2',
        'buyer': {
            'name': 'S2 (the Owner)',
            'provenance': "Owner, 2026-09-30: 'I am the buyer.' Contracts §1.1 requires the Buyer with "
                          "provenance on every job; C1 audits it.",
        },
        'specialist': {
            'name': 'The E-DI corpus, quoted and versioned at the pin, held by S2 as its Author',
            'provenance': "Owner, 2026-09-30: 'Can the edi corpus be the specialist?' then 'It's me as "
                          "Author.' The Operating Instrument permits a document to carry the standard "
                          "'if it is quoted and versioned, and the holder is still escalated'. Scope: "
                          "jobs whose craft standard IS E-DI conformance. It does not hold for jobs in "
                          "another field, where E-DI is the process rather than the craft.",
        },
        'values': p['values'],
        'principles': p['principles'],
        'escalation_classes': p['escalation_classes'],
        'human_seat': p['human_seat'],
        'non_negotiable': d['non_negotiable'],
    }
    # `proposed.rationale` HAS NOWHERE TO GO once ratified: the schema sets additionalProperties:false at
    # the root and names no note field, so the only places for who and when are `ratified_by` and
    # `ratified_at`. There is no slot for WHAT WAS FLAGGED at ratification. Discovered by the validator
    # refusing to write rather than by reading. The draft rationale is preserved in the instance layer and
    # in DECISIONS.log instead; the schema gap is recorded rather than routed around.

    v = Draft202012Validator(SCHEMA)
    errs = [f'{"/".join(str(x) for x in e.path) or "(root)"}: {e.message}' for e in v.iter_errors(out)]
    if errs:
        print('REFUSING TO WRITE — the ratified form does not validate:')
        for e in errs[:8]:
            print('   ', e)
        return 1
    print('validates against constitution.schema.json before writing: OK')

    SRC.write_text(json.dumps(out, indent=2) + '\n')
    back = json.loads(SRC.read_text())
    errs = [f'{"/".join(str(x) for x in e.path) or "(root)"}: {e.message}' for e in v.iter_errors(back)]
    print(f'written and re-read: {len(back)} keys, validated from disk: '
          f'{"OK" if not errs else "FAILED"}')
    print(f'  ratified={back["ratified"]}  by={back["ratified_by"]}  at={back["ratified_at"]}  '
          f'version={back["version"]}')
    print(f'  values={len(back["values"])}  principles={len(back["principles"])}  '
          f'escalation_classes={len(back["escalation_classes"])}  non_negotiable={len(back["non_negotiable"])}')
    print(f'  buyer={back["buyer"]["name"]!r}')
    print(f'  specialist={back["specialist"]["name"]!r}')
    print(f'  "proposed" present? {"proposed" in back}  (must be False)')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main())
