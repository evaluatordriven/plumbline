#!/usr/bin/env python3
"""
NON-FORECLOSURE — the channel. A DECLARATION channel, the same device as proportionality.

The condition: "the solutions only work for small businesses and cannot be improved or scaled." §9 of the
architecture already resolved how to answer it — EVERY ARCHITECTURE CHOICE IS EITHER REVERSIBLE, OR
EXPLICITLY DECLARED A ONE-WAY DOOR. So the channel reads the one-way-door registers in this repo's ADRs.

STRICT POLARITY, and the Owner left it as drafted: an ADR with NO register counts as UNDECLARED. Target
zero. Nothing passes by silence — the same shape that makes the proportionality ledger work.

WHAT IT CANNOT CHECK, stated so nobody reads more into a 10 than is there. It checks that a register
EXISTS and that each entry declares reversible true/false. It does NOT check that the declaration is
RIGHT: a choice called reversible that is not would pass this channel. So it measures whether the
decision was FACED, not whether it was faced correctly.

AND THE SAMPLE IS THIN. There is exactly one ADR in the repo, so this reading rests on n=1. That is a
limit of the reading, not of the channel, and it should be said wherever the score appears.

Usage:  check_foreclosure.py [--selftest]
"""
import json
import pathlib
import re
import sys

SHIP = pathlib.Path(__file__).resolve().parent.parent
JOBS = SHIP / 'dot-plumbline' / 'jobs'

HEADING = re.compile(r'^#{1,6}\s*.*(one-way|reversib)', re.I)
DECLARED_YES = re.compile(r'\byes\b', re.I)
DECLARED_NO = re.compile(r'\bno\b', re.I)


def adrs():
    return sorted(JOBS.glob('*/ADR-*.md'))


def registers_of(path):
    """EVERY register in the ADR, in document order, each as (heading, rows, doors).

    Two corrections are baked into this shape, both found by reading the first output rather than
    trusting it:

    1. It scans the whole SECTION after a matching heading, not just the contiguous table lines below it.
       The first version stopped at the first prose paragraph and reported ADR-001 as UNDECLARED when
       that ADR carries a register — a false finding produced by the instrument, not the artifact.
    2. It returns ALL registers, because ADR-001's §5 declares a one-way door and its §7 CORRECTS that
       declaration. Reading only the first register would report a door the ADR itself later un-declared.
       A register that cannot see its own correction is reporting the past as the present.
    """
    lines = path.read_text().splitlines()
    level = re.compile(r'^(#{1,6})\s')
    out = []
    for i, line in enumerate(lines):
        mh = level.match(line)
        if not (mh and HEADING.match(line)):
            continue
        depth = len(mh.group(1))
        rows = []
        for j in range(i + 1, len(lines)):
            m2 = level.match(lines[j])
            if m2 and len(m2.group(1)) <= depth:
                break                      # section over
            s = lines[j].strip()
            if s.startswith('|'):
                rows.append([c.strip() for c in s.strip('|').split('|')])
            elif rows:
                break                      # the table ended
        if not rows:
            continue
        header = [c.lower() for c in rows[0]]
        try:
            col = next(k for k, c in enumerate(header) if 'reversib' in c)
        except StopIteration:
            continue
        data = [r for r in rows[1:] if not set(''.join(r)) <= set('-: ')]
        doors = [r[0] for r in data if len(r) > col and DECLARED_NO.search(r[col])
                 and not DECLARED_YES.search(r[col])]
        out.append((line.strip('# ').strip(),
                    [{'choice': r[0], 'says': r[col] if len(r) > col else ''} for r in data],
                    doors))
    return out


def register_of(path):
    """Kept for callers that want the first register; returns (rows, doors) or (None, None)."""
    regs = registers_of(path)
    return (regs[0][1], regs[0][2]) if regs else (None, None)


def one_way_headings(path):
    """Every heading in the ADR that mentions one-way doors or reversibility — WITH OR WITHOUT a table.
    A heading with no table is prose about one-way doors outside the register, and that is where ADR-001
    keeps its correction to §5. Counting only registers missed it: the correction is prose, so the
    register count stayed at one while the reading still reported a door the ADR had already un-declared."""
    return [l.strip() for l in path.read_text().splitlines()
            if re.match(r'^#{1,6}\s', l) and HEADING.match(l)]


def measure():
    found = []
    for a in adrs():
        regs = registers_of(a)
        headings = one_way_headings(a)
        found.append({
            'adr': str(a.relative_to(SHIP)),
            'has_register': bool(regs),
            'registers': len(regs),
            'entries': sum(len(r[1]) for r in regs),
            'one_way_doors': [d for r in regs for d in r[2]],
            'headings': [r[0] for r in regs],
            'prose_beyond_register': max(0, len(headings) - len(regs)),
        })
    total = len(found)
    with_reg = [f for f in found if f['has_register']]
    undeclared = [f['adr'] for f in found if not f['has_register']]
    corrected = [f['adr'] for f in found if f['prose_beyond_register'] > 0]
    return {'adrs': total, 'with_register': len(with_reg), 'undeclared': undeclared,
            'corrected': corrected,
            'declared_doors': sum(len(f['one_way_doors']) for f in found), 'detail': found}


def main():
    if '--selftest' in sys.argv:
        return selftest()
    m = measure()
    print('NON-FORECLOSURE — the one-way-door register\n')
    print(f'  ADRs found        {m["adrs"]}')
    print(f'  carrying a register {m["with_register"]}')
    print(f'  UNDECLARED        {len(m["undeclared"])}   <- the reading; target zero')
    print(f'  declared one-way doors {m["declared_doors"]} (a count, not a failure — some doors'
          f' legitimately close)')
    if m['corrected']:
        print(f'  ADRs carrying a CORRECTION to their own register: {len(m["corrected"])} — the count '
              f'above is the SUM across registers, so it counts a door an ADR later un-declared. Read '
              f'the latest register in each file, not the number.')
    print()
    for d in m['detail']:
        mark = 'ok ' if d['has_register'] else 'UND'
        doors = f" — one-way: {', '.join(d['one_way_doors'])}" if d['one_way_doors'] else ''
        extra = (f'  << carries {d["registers"]} registers — a CORRECTION; read the latest'
                 if d['registers'] > 1 else '')
        print(f'    [{mark}] {d["adr"]} ({d["entries"]} entries, {d["registers"]} register(s)){doors}{extra}')
    if m['undeclared']:
        print(f'\n  An ADR with no register is an architecture decision nobody faced:')
        for u in m['undeclared']:
            print(f'    {u}')
    print(f'\n  LIMITS: checks that a register EXISTS, not that it is RIGHT — a choice called reversible')
    print(f'  that is not would pass. And there are {m["adrs"]} ADR(s), so this rests on a sample of'
          f' {m["adrs"]}.')
    return 0


def selftest():
    bad = 0

    def case(name, ok, detail=''):
        nonlocal bad
        print(f'  {"ok  " if ok else "FAIL"}  {name}')
        if not ok:
            print(f'        -> {detail}')
        bad += 0 if ok else 1

    m = measure()
    case('the live repo is measured', m['adrs'] >= 1, str(m))
    case('the gate ADR is found and carries its register',
         any(d['has_register'] and d['entries'] > 0 for d in m['detail']), str(m['detail']))
    case('its one real door is detected as a one-way door',
         any(d['one_way_doors'] for d in m['detail']),
         str([d['one_way_doors'] for d in m['detail']]))
    # A REAL polarity check, not a vacuous one: no entry whose reversible column says "Yes" may be
    # counted as a one-way door. The first version iterated only the ADRs WITHOUT a register, so it
    # passed trivially — a test that cannot fail, which is the defect this project keeps naming.
    yes_entries, doors = [], []
    for d in m['detail']:
        if not d['has_register']:
            continue
        rows, dd = register_of(SHIP / d['adr'])
        doors += dd or []
        yes_entries += [r['choice'] for r in (rows or []) if DECLARED_YES.search(r['says'])]
    case('a choice declared "Yes" is NOT counted as a one-way door',
         not (set(yes_entries) & set(doors)) and doors,
         f'yes={yes_entries[:3]} doors={doors[:3]}')
    # THE POLARITY, shown failing: strip the register from a copy and confirm it reads UNDECLARED.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / 'ADR-999.md'
        tmp.write_text('# ADR-999\n\nThe decision, with the register deleted.\n')
        rows, doors = register_of(tmp)
        case('an ADR with NO register is reported undeclared (nothing passes by silence)',
             rows is None, f'{rows!r}')
    print(f'\n  {5 - bad}/5 behaved as designed' if bad == 0 else f'\n  {bad} DID NOT')
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
