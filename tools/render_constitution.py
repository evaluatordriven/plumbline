#!/usr/bin/env python3
"""
Render the constitution into its two audiences. One source of truth, two views — the same pattern the
schemas already use, because a hand-kept second copy is the drift trap the corpus names.

WHY TWO VIEWS (measured 2026-09-30, Owner's question "does an agent need all that in order to convince it
to obey the constitution?"): the source file ran 14,123 characters, of which 5,246 (37%) was the LAW and
5,934 (42%) was the case for each clause — slightly more argument than law.

  --law       THE LOAD PATH. Statements, decision rules, escalation classes, the human seat, the
              non-negotiables. No provenance, no evidence, no rationale. What an agent needs to act.
  --readable  THE REVIEW PATH, and it is a SUPERSET of the law view: the same law, plus the rationale,
              the provenance and the evidence. What a PERSON needs — and what an auditor needs, to answer
              the question §1.1 makes a standard's validity depend on: who is buying this, and which master
              of the craft approved the standard.

The citations are not useless; they are simply not for the agent. This project's own rule decides it — a
prompted model promises, a configured instance enforces. Citations do not make an agent obey; schemas and
hooks do. So case-making in the load path buys nothing behaviourally while costing 42% of the file. The
corpus says the same thing about its own load set: the Primer explains why, and is explicitly not law.

FIRST ATTEMPT GOT THIS WRONG, and the numbers caught it: the "review" view was built as provenance-only, so
it omitted the statements a reviewer needs to read the provenance AGAINST, and both views came out ~6,200
chars — near-equal, which is the signature of a split that split nothing. A review view must be a superset.

Usage:  render_constitution.py [--law|--readable|both] [--out=DIR]
"""
import json
import pathlib
import sys

SHIP = pathlib.Path(__file__).resolve().parent.parent
SRC = SHIP / 'dot-plumbline' / 'constitution.json'


def render(d, include_case):
    """include_case=False -> the law. True -> the review view (a superset)."""
    c = d
    ratified = c.get('ratified')
    # While unratified the content stands in `proposed`; once ratified the same content sits at top level.
    body = c['proposed'] if not ratified else c
    values = sorted(body.get('values', []), key=lambda x: x.get('rank', 99))
    principles = body.get('principles', [])

    out = [f"# {c['program']} — constitution{'' if include_case else ' (LAW)'}", '']
    meta = f"version {c['version']} · ratified: {str(ratified).lower()}"
    if c.get('ratified_by'):
        meta += f" · ratified_by {c['ratified_by']}"
    if ratified and include_case:
        meta += f" · at {c.get('ratified_at', '-')}"
    out += [meta, '']
    if not ratified:
        out += ['> NOT IN FORCE. Nothing here binds until this constitution is ratified.', '']
    if include_case:
        out += ['> This is the review view: the full law, plus its rationale, provenance and evidence. '
                'The load path an executing agent reads is the law view.', '']
        if ratified and c.get('buyer'):
            out += [f"**Buyer:** {c['buyer'].get('name', '-')}  ", 
                    f"**Specialist:** {c['specialist'].get('name', '-')}", '']
        if body.get('rationale'):
            out += ['## Rationale', '', body['rationale'], '']

    out += ['## Values — ranked; each states what it forces when two options conflict', '']
    for v in values:
        out += [f"### {v.get('rank', '-')}. {v['name']}", '', v['statement'], '',
                f"**When two defensible options conflict, this value forces:** {v['decision_rule']}", '']
        if include_case:
            out += [f"**Provenance:** {v['provenance']}", '']
            if v.get('evidence_of_adherence'):
                out += [f"**Evidence of adherence:** {v['evidence_of_adherence']}", '']

    out += ['## Principles', '']
    for p in principles:
        out.append(f"- **{p['name']}** — {p['statement']}")
        if include_case:
            out.append(f"  - *From:* {p['provenance']}")
    out.append('')

    out += ['## Escalation classes — straight to the Owner, bypassing regeneration', '']
    out += [f'- {e}' for e in body.get('escalation_classes', [])] + ['']

    out += ["## The Owner's seat", '', body.get('human_seat', '(unnamed)'), '']

    out += ['## Non-negotiable — never delegated to any agent', '']
    out += [f'- {n}' for n in c.get('non_negotiable', [])] + ['']

    return '\n'.join(out)


def main():
    argv = sys.argv[1:]
    flags = [a for a in argv if a.startswith('--')]
    mode = next((f for f in flags if f in ('--law', '--readable', 'both')), 'both')
    outs = [f.split('=', 1)[1] for f in flags if f.startswith('--out=')]
    outdir = pathlib.Path(outs[0]) if outs else pathlib.Path.home() / '.hermes' / 'tmp' / 'plumbline'
    outdir.mkdir(parents=True, exist_ok=True)

    d = json.loads(SRC.read_text())
    law, review = render(d, False), render(d, True)
    if mode in ('--law', 'both'):
        (outdir / 'constitution-LAW.md').write_text(law)
        print(f'  law view (the load path)  -> constitution-LAW.md       {len(law):,} chars')
    if mode in ('--readable', 'both'):
        (outdir / 'constitution-readable.md').write_text(review)
        print(f'  review view (superset)    -> constitution-readable.md  {len(review):,} chars')
    print(f'  source JSON                                            {len(json.dumps(d, indent=2)):,} chars')
    print(f'  an agent loading the law reads {100.0 * len(law) / len(review):.0f}% of the review view')


if __name__ == '__main__':
    main()
