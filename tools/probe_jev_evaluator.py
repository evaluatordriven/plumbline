#!/usr/bin/env python3
"""
PROBE v2: can JEV hold any of Plumbline's Evaluator work?

WHAT CHANGED FROM v1, AND WHY IT MATTERS
v1 fed JEV the raw 158k surface verbatim. It was REJECTED: `max_tokens_exceeded`. Measured ceiling:
150k chars passes (~30k tokens), 160k fails, and the census's own surface was 137k chars of dense
code/JSON. So **JEV cannot hold the census's surface in one call** — which means it cannot do the
READING. It can only do the JUDGING, over facts extracted first. That is a real architectural
constraint, not a tuning problem, and it is the honest headline of this probe.

So the state here is a FACT SHEET, extracted DETERMINISTICALLY from the repo by the code below — no
hand-written conclusions, only literals: field values, definitions, the checker's own lines, greps.
The judgment stays with JEV. This is also the prototype of the extraction layer JEV would need.

THE EXPERIMENT
Two states, identical questions, identical repeats. The ONLY difference is whether the enforcement
layer is present:
    A  = fact sheet WITHOUT the corpus gate and the rule index   (what the census could see)
    B  = fact sheet WITH them                                    (the fix)
C33 is the control with a KNOWN right answer: the gate rejects an empty escalation, so on B the
reading must be `conforms`, while the census read `does_not_conform` three times out of three on A.
A third run seeds defects the gate is known to reject — Rule 12: an engine must be shown able to fail.

The flat band is not a failure: p>=0.85 conforms, p<=0.15 does_not_conform, else UNOBSERVED — the
third legal reading, which the LLM produced erratically under the name "flapping".
"""
import json
import os
import pathlib
import re
import subprocess
import tempfile
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
# pin.json names the corpus repository; the checkout itself comes from $EDI_CORPUS.
CORPUS = pathlib.Path(os.environ.get('EDI_CORPUS') or 'EDI_CORPUS-not-set').expanduser()
OUT = REPO / 'dot-plumbline' / 'probes' / 'jev-evaluator-probe'
OUT.mkdir(parents=True, exist_ok=True)
TMP = pathlib.Path(tempfile.gettempdir()) / 'jev-probe2'; TMP.mkdir(exist_ok=True)  # honours $TMPDIR
# The TypeSafe key comes from the environment only; nothing is read from a dotfile.
KEY = os.environ.get('TYPESAFE_API_KEY', '')
if not KEY and __name__ == '__main__':
    raise SystemExit('set TYPESAFE_API_KEY to run this probe')

CLAUSES = ['C5', 'C6', 'C7', 'C9', 'C11', 'C15', 'C18', 'C25', 'C31', 'C33']
PACKET = REPO / 'dot-plumbline/jobs/2026-09-29-plumbline-conformance-census/packet.json'

_Q = {
    'c5_cap_budget_set': 'Is it true that BOTH a cap and a budget are set for this job?',
    'c6_roles_separate': 'Is it true that no party judges its own work — the party that produced the '
                         'artifact is different from the party that reads it, and no rule forbids it?',
    'c7_channel_blind': 'Is it true that the observation channel is blind to the answer it is checked '
                        'against, and that no reading rests on the producing party\'s self-report?',
    'c9_terminal_states': 'Is it true that the allowed terminal states are exactly accepted, needs_owner '
                          'and rejected, with no fourth state permitted anywhere?',
    'c11_escalation_named': 'Is it true that escalation classes are defined AND a human seat is named?',
    'c15_fresh_value': 'Is it true that a record of an external write must carry a value fresh on every '
                       'run, such as a run id or timestamp, and that verification is by independent read-back?',
    'c18_extensions_labelled': 'Is it true that every instance extension is labelled as instance-specific '
                               'and is forbidden from weakening the doctrine\'s generation, seat or evidence rules?',
    'c25_maker_supplied': 'Is it true that the Maker is a supplied and recorded choice with the feedback '
                          'forms it can consume named, rather than assumed?',
    'c31_no_artifact': 'Is it true that a run in which no artifact was produced has a defined outcome and '
                       'terminal state, tested structurally rather than by counting characters?',
    'c33_scored_frame_enforced':
        'The clause requires a scored job to carry ground_truth rows with source, version and hardness; a '
        'mandate reference as doc plus version; and a NON-EMPTY escalation route. Reading the machine '
        'surface in this state — the schema AND any checker program it contains — is it true that an '
        'empty or missing escalation route would be REJECTED, so the requirement is enforced and not '
        'merely written down?',
}
# Each question is an OBJECT with a type and instructions — a bare string is rejected by the API
# (`model_attributes_type` at body.questions.<id>). Learned the hard way on the first run.
QUESTIONS = {k: {'type': 'noul', 'instructions': v} for k, v in _Q.items()}


def fact_clauses():
    rub = json.loads((REPO / 'dot-plumbline/jobs/2026-09-29-plumbline-conformance-census/'
                      'instrument/compliance-checklist.json').read_text())
    want = {c['clause']: c for c in rub['clauses']}
    out = ['===== THE CLAUSES UNDER TEST (the rubric the census actually read) =====']
    for cid in CLAUSES:
        c = want.get(cid)
        if c:
            out.append(f"\n{cid}: {c.get('clause', '')}")
    return '\n'.join(out)


def fact_packet(patch=None):
    d = json.loads(PACKET.read_text())
    if patch:
        patch(d)
    keep = ('job_id', 'entry', 'mode', 'ratified', 'buyer', 'specialist', 'maker', 'evaluator',
            'human_seat', 'escalation', 'ground_truth', 'mandate_ref', 'standard_ref', 'bounds',
            'pass_rule', 'reads_before_freeze', 'dimensions')
    view = {k: d[k] for k in keep if k in d}
    return '===== THE JOB PACKET (fields relevant to these clauses) =====\n' + json.dumps(view, indent=1)


def fact_schema():
    s = json.loads((REPO / 'schemas/job-packet.schema.json').read_text())
    defs = s.get('$defs', {})

    def dig(node, key, acc):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == key:
                    acc.append(v)
                dig(v, key, acc)
        elif isinstance(node, list):
            for v in node:
                dig(v, key, acc)
        return acc
    out = ['===== MACHINE SURFACE: the derived job-packet schema (extracted constraints) =====']
    for name in ('escalation', 'bounds', 'ground_truth', 'mandate_ref', 'terminal_state', 'outcome'):
        hits = dig(s, name, [])
        for h in hits[:3]:
            out.append(f'  "{name}": {json.dumps(h)[:600]}')
    out.append('  required (top level): ' + json.dumps(s.get('required', []))[:400])
    for dn, dv in list(defs.items())[:6]:
        if isinstance(dv, dict) and 'enum' in dv:
            out.append(f'  $defs.{dn}.enum = {json.dumps(dv["enum"])[:200]}')
    m = re.search(r'"description":\s*"([^"]{0,300})', json.dumps(s))
    if m:
        out.append('  schema description head: ' + m.group(1)[:300])
    return '\n'.join(out)


def fact_extensions():
    t = (REPO / 'schemas/instance-extensions.json').read_text()
    out = ['===== MACHINE SURFACE: schemas/instance-extensions.json (the only hand-written instance law) =====']
    try:
        d = json.loads(t)
        out.append(json.dumps(d, indent=1)[:6000])
    except Exception:
        out.append(t[:6000])
    return '\n'.join(out)


def fact_repo_state():
    tools = sorted(p.name for p in (REPO / 'tools').glob('*') if p.is_file())
    scripts_dir = (REPO / 'scripts')
    out = ['===== REPOSITORY STATE (greps and listings, not conclusions) =====',
           f'  tools/ contains: {tools}',
           f'  scripts/ exists: {scripts_dir.exists()}',
           f'  dot-plumbline/ contains: {sorted(p.name for p in (REPO / "dot-plumbline").glob("*"))}',
           f'  files matching *conductor* anywhere in the repo: '
           f'{[str(p.relative_to(REPO)) for p in REPO.rglob("*conductor*")]}',
           f'  files matching *discoverab* anywhere in the repo: '
           f'{[str(p.relative_to(REPO)) for p in REPO.rglob("*discoverab*")]}']
    agr = (REPO / 'AGENTS.md').read_text()
    seat_rows = [l.strip() for l in agr.splitlines()
                 if l.strip().startswith('|') and ('seat' in l.lower() or 'Evaluator' in l
                                                   or 'Conductor' in l or 'Maker' in l)][:14]
    out.append('  AGENTS.md roster/seat rows:')
    out += [f'    {r[:170]}' for r in seat_rows]
    inv = [l.strip() for l in agr.splitlines()
           if l.strip().startswith('- **') and any(w in l for w in
              ('read-back', 'fresh on every run', 'Roles separate', 'Terminal states', 'Writer',
               'blind', 'Maker never'))][:10]
    out.append('  AGENTS.md invariant lines:')
    out += [f'    {r[:200]}' for r in inv]
    return '\n'.join(out)


def fact_rule_index():
    p = CORPUS / 'EDI-RULE-INDEX.json'
    d = json.loads(p.read_text())
    s = json.dumps(d)
    return ('===== CORPUS DISPOSITION INDEX (which rules are enforced by a line, by a schema, or by '
            f'nothing) =====\n  {s[:4000]}')


def fact_gate():
    return ('===== THE CORPUS ENFORCEMENT GATE: tools/validate_job_packet.py (full source) =====\n'
            + (CORPUS / 'tools/validate_job_packet.py').read_text())


def build_state(include_enforcement, patch=None):
    blocks = ['You are reading facts extracted from a software repository called Plumbline, and judging '
              'it against doctrine clauses. The state below is the evidence.', fact_clauses(),
              fact_packet(patch), fact_schema(), fact_extensions(), fact_repo_state()]
    if include_enforcement:
        blocks.append(fact_gate())
        blocks.append(fact_rule_index())
    return '\n\n'.join(blocks)


def ask(state, tag):
    req = TMP / f'_req_{tag}.json'
    req.write_text(json.dumps({'state': state, 'model': 'jev-latest', 'questions': QUESTIONS}))
    r = subprocess.run(['curl', '-sS', '-X', 'POST', 'https://api.typesafe.ai/v1/systemone',
                        '-H', f'Authorization: Bearer {KEY}', '-H', 'Content-Type: application/json',
                        '-A', 'Mozilla/5.0 curl/8', '--data-binary', f'@{req}', '--max-time', '240'],
                       capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        return {'error': (r.stderr or 'empty')[:200]}
    try:
        d = json.loads(r.stdout)
    except Exception as e:
        return {'error': f'unparseable: {e}'}
    if not isinstance(d, dict):
        return {'error': 'non-object response'}
    if 'detail' in d:
        return {'error': f"api: {d['detail']}"}
    return d


def band(p):
    if p is None:
        return 'unobserved'
    return 'conforms' if p >= 0.85 else ('does_not_conform' if p <= 0.15 else 'unobserved')


def seed(d):
    d.pop('escalation', None)
    if isinstance(d.get('evaluator'), dict):
        d['evaluator']['who'] = 'Owner'
    if isinstance(d.get('bounds'), dict):
        d['bounds'].pop('cap', None)


def main():
    runs = {}
    plan = (('A_facts_without_enforcement', False, None, 3),
            ('B_facts_with_enforcement', True, None, 3),
            ('B_seeded_defects', True, seed, 2))
    for label, enforces, patch, reps in plan:
        state = build_state(enforces, patch)
        print(f'\n=== {label} (state {len(state):,} chars, {reps} repeats) ===')
        runs[label] = {'state_chars': len(state), 'include_enforcement': enforces, 'passes': []}
        for i in range(reps):
            t0 = time.time(); resp = ask(state, f'{label}_{i+1}'); el = time.time() - t0
            if 'error' in resp:
                print(f'  pass {i+1}: FAILED {resp["error"][:120]}')
                runs[label]['passes'].append({'error': resp['error']}); continue
            ans = resp.get('answers', {}); u = resp.get('usage', {})
            probs = {q: (ans.get(q) or {}).get('noul') for q in QUESTIONS}
            readings = {q: band(probs[q]) for q in QUESTIONS}
            runs[label]['passes'].append({'probs': probs, 'readings': readings, 'usage': u,
                                          'elapsed_s': round(el, 2), 'model': resp.get('model')})
            print(f'  pass {i+1}: {el:.1f}s in={u.get("input_tokens")} out={u.get("output_tokens")}')
            for q in QUESTIONS:
                print(f'      {q:<28} {str(probs[q]):<6} -> {readings[q]}')
            time.sleep(0.3)
    (OUT / 'jev-probe-raw.json').write_text(json.dumps(runs, indent=2))
    print(f'\nraw -> {OUT / "jev-probe-raw.json"}')


if __name__ == '__main__':
    main()
