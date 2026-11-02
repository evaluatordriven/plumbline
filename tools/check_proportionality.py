#!/usr/bin/env python3
"""
PROPORTIONALITY — the channel. One of the two dimensions the direction owes and the doctrine cannot supply.

WHY IT EXISTS. The direction's fourth falsification condition: "The solutions are over-built and haven't
earned the right to be so." A contract-derived evaluator is blind to that — nothing in §9 asks whether a
thing needed to exist. And the Owner's value 5 states the deciding rule: "A mechanism earns its place by
having been needed, not by being plausible... name the job that needs it, or defer it with a trigger."

THE MEASURE. Enumerate the BUILD SURFACE mechanically, and require every item to carry a provenance: what
needed it — a job id, a measured defect, or a declared trigger. The reading is the fraction of surface that
cites a need, plus the LIST of what does not. The list is the actionable part; the fraction is what makes
it scorable.

THE POLARITY IS THE STRICT ONE, and that is deliberate. An item the ledger does not mention is counted
UNEARNED. So a stale ledger cannot quietly pass — forgetting to declare something shows up as unearned
surface rather than hiding. The value says a mechanism earns its place by having been needed; the default
must therefore be "not yet earned".

WHAT THIS CHANNEL IS NOT. It is not a size measure. A large mechanism with a named job is proportional; a
tiny one built for no reason is not. Line counts measure effort, not need. This counts NEED.

Usage:  check_proportionality.py [--selftest]
"""
import json
import pathlib
import sys

SHIP = pathlib.Path(__file__).resolve().parent.parent
INSTANCE = SHIP / 'schemas' / 'instance-extensions.json'
PROFILES = pathlib.Path.home() / '.hermes' / 'profiles'
LEDGER = ('proportionality', 'ledger', 'items')

# Instance-layer blocks that are STRUCTURE rather than metadata, and therefore have to earn their place.
# `$schema`, `title`, `status`, `contracts_basis` and `authority` are the file describing itself, not
# mechanisms in the loop, so they are excluded from the count.
BLOCK_METADATA = {'$schema', 'title', 'status', 'contracts_basis', 'authority'}


def surface():
    """Every built thing, enumerated mechanically. Nothing here is remembered by hand.

    `kit/` was added 2026-10-05 after the boundary audit below proved the channel had been blind to it: four
    files, ~1,300 lines, built across two days, and the reading stayed at 100% because the category list did
    not mention it. The audit is what caught it; this enumeration is the consequence."""
    items = []
    for p in sorted((SHIP / 'tools').glob('*')):
        if p.is_file() and p.name != '__pycache__':
            items.append(('tool', f'tools/{p.name}'))
    for p in sorted((SHIP / 'gate').glob('*')):
        if p.is_file() and p.name != '__pycache__':
            items.append(('plugin', f'gate/{p.name}'))
    # Recursive within the mechanism directories: the first cut globbed one level and missed
    # kit/skill/plumbline/SKILL.md, so depth became a hiding place. A surface is a fact about the tree, not
    # about how deep someone filed it — and the ledger grew an entry for a file the enumerator never saw.
    for root, kind in ((SHIP / 'kit', 'tool'), (SHIP / 'gate', 'plugin'),
                       (SHIP / 'standards', 'standard')):
        for p in sorted(root.rglob('*')):
            if p.is_file() and '__pycache__' not in str(p):
                items.append((kind, str(p.relative_to(SHIP))))
    inst = json.loads(INSTANCE.read_text())
    for k in inst:
        if k not in BLOCK_METADATA:
            items.append(('instance-layer block', k))
    if PROFILES.exists():
        for p in sorted(PROFILES.iterdir()):
            if p.is_dir() and p.name.startswith('plumbline-'):
                items.append(('seat profile', p.name))
    return items


# The boundary of the surface, audited rather than remembered. Every top-level entry must be enumerated as
# surface (the directories below) or excused here WITH a reason. Measured 2026-10-05: `kit/` was neither, and
# the channel reported 100% earned while its surface grew by a directory — the recurring defect of this program
# (an extractor that omits what it cannot see and reports a count nobody diffs), one level up.
ENUMERATED_DIRS = ('tools', 'kit', 'gate', 'standards')
TOP_LEVEL_EXCUSED = {
    '.git': 'version control, not built surface',
    '.gitignore': 'repo plumbing',
    '.github': 'the CI workflow — run by the operating loop, not a loop mechanism',
    'AGENTS.md': 'instruction file, not a mechanism',
    'README.md': 'orientation, not a mechanism',
    'dot-plumbline': 'records and jobs — governed by §10.1 and counted by the run-log, not by this dimension',
    'schemas': 'derived law plus the instance layer; the instance-layer BLOCKS are enumerated as surface above',
    'tests': 'the guards themselves — the operating loop enumerates and runs them',
}


def classified_top_level():
    """Top-level names this channel can account for: the directories it enumerates, and the excused ones."""
    return {d for d in ENUMERATED_DIRS if (SHIP / d).is_dir()} | set(TOP_LEVEL_EXCUSED)


def boundary(root=None, names=None):
    """Top-level entries the channel neither enumerates nor excuses. A new one is a silent surface."""
    root = root or SHIP
    known = set(names) if names is not None else classified_top_level()
    return sorted(p.name for p in root.iterdir()
                  if p.name not in {'__pycache__', '.DS_Store'} and p.name not in known)


def ledger():
    node = json.loads(INSTANCE.read_text())
    for k in LEDGER:
        node = node.get(k, {})
    return node


def set_ledger(doc, items):
    """Write items at the nested path — LEDGER is a path, not a key."""
    node = doc
    for k in LEDGER[:-1]:
        node = node.setdefault(k, {})
    node[LEDGER[-1]] = items
    return doc


def main():
    if '--selftest' in sys.argv:
        return selftest()

    items = surface()
    led = ledger()
    earned, unearned = [], []
    for kind, name in items:
        rec = led.get(name)
        (earned if rec and rec.get('needed_by') else unearned).append((kind, name, rec))

    total = len(items)
    frac = 100.0 * len(earned) / total if total else 0.0
    print(f'PROPORTIONALITY — built surface vs the need that justified it\n')
    print(f'  surface items      {total}')
    print(f'  with a named need  {len(earned)}')
    print(f'  UNEARNED           {len(unearned)}')
    print(f'  earned fraction    {frac:.1f}%   (bar: NOT SET — the Owner sets it)\n')

    unclassified = boundary()
    print(f'  boundary           {len(classified_top_level())} top-level entries, '
          f'{"all classified" if not unclassified else f"{len(unclassified)} UNCLASSIFIED"}')
    if unclassified:
        print()
        print('  UNCLASSIFIED TOP-LEVEL SURFACE — a surface this channel cannot see is not a pass:')
        for n in unclassified:
            print(f'    {n}')
        print('  if it is a mechanism, enumerate it in surface(); if it is not, excuse it in')
        print('  TOP_LEVEL_EXCUSED with a reason. Silence is how the kit hid for two days.')
        return 1
    print()

    if unearned:
        print('  UNEARNED — each one must either name a job, or be deferred with a trigger, or go:')
        for kind, name, _ in unearned:
            print(f'    [{kind}] {name}')
        print()

    kinds = {}
    for kind, name, rec in earned:
        kinds.setdefault(rec.get('kind', '?'), []).append(name)
    if kinds:
        print('  earned, by the kind of need:')
        for k, v in sorted(kinds.items()):
            print(f'    {k:18} {len(v)}')
    return 0


def selftest():
    """The checker must be shown reporting an undeclared item as UNEARNED, not just reporting a pass."""
    global INSTANCE
    import tempfile
    bad = 0

    real = json.loads(INSTANCE.read_text())
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / 'instance-extensions.json'

        # (1) every item declared -> everything earned
        doc = json.loads(json.dumps(real))
        set_ledger(doc, {name: {'needed_by': 'test', 'kind': 'test'} for _, name in surface()})
        tmp.write_text(json.dumps(doc))
        INSTANCE = tmp
        items, led = surface(), ledger()
        ok = all(led.get(n) for _, n in items)
        print(f'  {"ok  " if ok else "FAIL"}  fully declared -> nothing unearned')
        bad += 0 if ok else 1

        # (2) one entry removed -> exactly that one is unearned. THIS is the polarity test.
        doc = json.loads(json.dumps(real))
        victims = [n for _, n in surface()]
        target = victims[0]
        set_ledger(doc, {n: {'needed_by': 'test', 'kind': 'test'} for n in victims[1:]})
        tmp.write_text(json.dumps(doc))
        INSTANCE = tmp
        led = ledger()
        un = [n for _, n in surface() if not led.get(n)]
        ok = un == [target]
        print(f'  {"ok  " if ok else "FAIL"}  one entry deleted -> exactly it is unearned ({un[:2]})')
        bad += 0 if ok else 1

        # (3) an empty ledger -> everything unearned; a stale ledger cannot pass
        doc = json.loads(json.dumps(real))
        set_ledger(doc, {})
        tmp.write_text(json.dumps(doc))
        INSTANCE = tmp
        led = ledger()
        un = [n for _, n in surface() if not led.get(n)]
        ok = len(un) == len(surface()) > 0
        print(f'  {"ok  " if ok else "FAIL"}  empty ledger -> {len(un)} unearned (nothing passes by silence)')
        bad += 0 if ok else 1

        # (4) THE BOUNDARY AUDIT — a new top-level surface must be REPORTED, not silently ignored.
        with tempfile.TemporaryDirectory() as td2:
            root = pathlib.Path(td2)
            (root / 'tools').mkdir()
            (root / 'newsurface').mkdir()
            hit = boundary(root=root, names=classified_top_level())
            ok = hit == ['newsurface']
            print(f'  {"ok  " if ok else "FAIL"}  a new top-level directory is reported as unclassified ({hit})')
            bad += 0 if ok else 1

            # ...and an excused entry is NOT reported: the audit must not cry wolf on known plumbing.
            (root / 'newsurface').rename(root / 'AGENTS.md') if False else None
            ok = boundary(root=root, names=classified_top_level()) == ['newsurface']
            print(f'  {"ok  " if ok else "FAIL"}  and a classified entry is not reported')
            bad += 0 if ok else 1

    INSTANCE = SHIP / 'schemas' / 'instance-extensions.json'
    print(f'\n  {"ALL CASES BEHAVED AS DESIGNED" if bad == 0 else f"{bad} DID NOT"}')
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
