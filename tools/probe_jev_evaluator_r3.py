#!/usr/bin/env python3
"""
TWO EXPERIMENTS the composition rests on.

PHASE A — RULE 12, clause by clause. Round 2 seeded a BUNDLE, so only two clauses were cleanly
attributable. Here each clause gets its OWN defect, applied alone, and every clause is asked in the
same call. That tests two things at once: does the clause move (can it fail), and does any OTHER
clause move unnecessarily (specificity). A defect that moves clauses it has nothing to do with means
the instrument is reading something other than the clause.

PHASE B — DOES MAX SHARE PREDICT INSTABILITY? Round 2 suggested it with n=10 and one unstable clause.
Here: all 32 live clauses, 6 repeats, and a correlation between per-clause max share and per-clause
pick stability. The confound is stated up front: thin evidence can lower the share AND destabilise the
pick, so a correlation is evidence that share is a usable "look here" signal — not proof that it is
calibrated confidence.
"""
import copy
import json
import os
import pathlib
import subprocess
import tempfile
import sys
import time
from statistics import mean

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import probe_jev_evaluator_r2 as R  # noqa: E402  (extraction helpers, contract text, checker lines)

REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / 'dot-plumbline' / 'probes' / 'jev-evaluator-probe'
TMP = pathlib.Path(tempfile.gettempdir()) / 'jev-r3'; TMP.mkdir(exist_ok=True)  # honours $TMPDIR
# The TypeSafe key comes from the environment only; nothing is read from a dotfile.
KEY = os.environ.get('TYPESAFE_API_KEY', '')
if not KEY and __name__ == '__main__':
    raise SystemExit('set TYPESAFE_API_KEY to run this probe')
PACKET = REPO / 'dot-plumbline/jobs/2026-09-29-plumbline-conformance-census/packet.json'
OPTS = R.OPTS

CHECKLIST = json.loads((REPO / 'dot-plumbline/jobs/2026-09-29-plumbline-conformance-census/'
                        'instrument/compliance-checklist.json').read_text())
ALL = [c['id'] for c in CHECKLIST['clauses']]


def clause_text(cid):
    for c in CHECKLIST['clauses']:
        if c['id'] == cid:
            return c['clause']
    return '?'


def qs(clauses):
    return {c.lower(): {'type': 'choice', 'criteria': OPTS,
                        'instructions': f'Clause {c} states: "{clause_text(c)}". Does the artifact '
                                        f'described in the state satisfy this clause?'}
            for c in clauses}


def ask(state, tag, clauses):
    req = TMP / f'_req_{tag}.json'
    req.write_text(json.dumps({'state': state, 'model': 'jev-latest', 'questions': qs(clauses)}))
    r = subprocess.run(['curl', '-sS', '-X', 'POST', 'https://api.typesafe.ai/v1/systemone',
                        '-H', f'Authorization: Bearer {KEY}', '-H', 'Content-Type: application/json',
                        '-A', 'Mozilla/5.0 curl/8', '--data-binary', f'@{req}', '--max-time', '240'],
                       capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        return {'error': (r.stderr or 'empty')[:200]}
    try:
        x = json.loads(r.stdout)
    except Exception as e:
        return {'error': f'unparseable: {e}'}
    if not isinstance(x, dict):
        return {'error': 'non-object'}
    if 'detail' in x:
        return {'error': f'api: {x["detail"]}'}
    return x


def row_of(resp, clauses):
    ans = resp.get('answers', {})
    out = {}
    for c in clauses:
        a = ans.get(c.lower()) or {}
        d = a.get('probabilities') or {}
        shares = [v for v in d.values() if isinstance(v, (int, float))]
        out[c] = {'choice': a.get('choice'), 'confidence': a.get('confidence'),
                  'max_share': max(shares) if shares else None, 'probabilities': d}
    return out


# ---------------------------------------------------------------- PHASE A: per-clause defects
def defect(cid, pkt, sch, ext):
    """Apply ONE clause's defect, alone. Returns (pkt, sch, ext, note)."""
    p, s, e = copy.deepcopy(pkt), copy.deepcopy(sch), copy.deepcopy(ext)
    note = ''
    if cid == 'C5':
        p['mode'] = 'scored'; p.pop('specialist', None)
        p['bounds'] = {'T_accept': 8.0, 'T_dim': 7.0, 'T_reject': 5.0, 'budget': {'tokens': 1}}
        note = 'scored job with a bounds object that has NO cap'
    elif cid == 'C6':
        p.setdefault('evaluator', {})['who'] = 'Owner'
        note = 'the Owner holds the Evaluator seat'
    elif cid == 'C7':
        for d in p.get('dimensions', []):
            d['ground_truth_access'] = 'saw_gt'
        note = 'a dimension saw ground truth'
    elif cid == 'C9':
        s['$defs']['terminalState'] = {'enum': ['accepted', 'needs_owner', 'rejected', 'stalled']}
        note = 'a fourth terminal state, stalled, permitted by the schema'
    elif cid == 'C11':
        p.pop('escalation', None); p.pop('human_seat', None)
        note = 'no escalation route and no human seat'
    elif cid == 'C15':
        note = 'cannot be seeded cleanly: the clause governs a write pattern, not a field in this state'
    elif cid == 'C18':
        for k in list(e.keys()):
            if isinstance(e[k], dict):
                e[k].pop('instance_specific', None); e[k].pop('instance_rule', None)
        e.pop('instance_rule', None); e.pop('note', None)
        note = 'extension labels and the instance_rule removed'
    elif cid == 'C25':
        p['maker'] = ''
        note = 'the Maker is an empty string — not a supplied choice'
    elif cid == 'C31':
        s['$defs']['outcome'] = {'enum': ['accepted', 'rejected']}
        note = 'the no_artifact outcome removed from the schema'
    elif cid == 'C33':
        p['mode'] = 'scored'; p.pop('escalation', None); p.pop('specialist', None)
        note = 'a SCORED job with no escalation route — the clause is engaged and violated'
    return p, s, e, note


def build(clauses, pkt, sch, ext, tail=None):
    blocks = ['A software repository is being read against a doctrine checklist. Below are the clauses and '
              'the evidence for them. Judge only from that evidence.']
    for c in clauses:
        ev = R.facts(c, pkt, False) if c in R.CL else generic(c, pkt, sch, ext)
        blocks.append(f'===== {c} =====\nCLAUSE {c}: {clause_text(c)}\n\nEVIDENCE:\n{ev}')
    return '\n\n'.join(blocks)


def generic(cid, pkt, sch, ext):
    keep = ('job_id', 'entry', 'mode', 'ratified', 'buyer', 'specialist', 'maker', 'evaluator',
            'human_seat', 'escalation', 'ground_truth', 'mandate_ref', 'bounds', 'pass_rule',
            'reads_before_freeze', 'dimensions')
    view = {k: pkt[k] for k in keep if k in pkt}
    return ('packet, relevant fields: ' + json.dumps(view)[:1500] + '\n'
            'derived schema constraints: ' + json.dumps(R._find(sch, 'not')[:3])[:600] + '\n'
            'derived schema required: ' + json.dumps(sch.get('required', []))[:300] + '\n'
            'instance-extensions.json: ' + json.dumps(ext)[:2500] + '\n'
            'corpus checker lines:\n' + R._gate_lines('missing required', 'scored mode missing',
                                                      'readings mode must not'))


def phase_a():
    pkt = json.loads(PACKET.read_text())
    sch = json.loads((REPO / 'schemas/job-packet.schema.json').read_text())
    ext = json.loads((REPO / 'schemas/instance-extensions.json').read_text())
    res = {}
    print('=== PHASE A: does each clause move on ITS OWN defect? (all clauses asked each time) ===')
    for label, p, s, e in [('clean', copy.deepcopy(pkt), copy.deepcopy(sch), copy.deepcopy(ext))] + \
                          [(c,) + defect(c, pkt, sch, ext)[:3] for c in R.CL]:
        state = build(R.CL, p, s, e)
        resp = ask(state, f'A_{label}', R.CL)
        if 'error' in resp:
            print(f'  {label:<6} FAILED {resp["error"][:100]}'); res[label] = {'error': resp['error']}; continue
        res[label] = {'row': row_of(resp, R.CL), 'state_chars': len(state),
                      'usage': resp.get('usage'), 'note': (defect(label, pkt, sch, ext)[3]
                                                           if label != 'clean' else 'baseline')}
        print(f'  {label:<6} asked {len(R.CL)} clauses  in={resp["usage"]["input_tokens"]}  '
              f'({res[label]["note"][:60]})')
        time.sleep(0.2)

    print('\n  movement per seeded clause (clean -> seeded):')
    print(f'  {"seeded":<7} {"own clause reading":<40} moved?  collateral moved')
    payload = {}
    for c in R.CL:
        cl = res['clean']['row'][c]['choice']
        sd = res.get(c, {}).get('row', {}).get(c, {}).get('choice')
        collat = [o for o in R.CL if o != c
                  and res.get(c, {}).get('row', {}).get(o, {}).get('choice') != res['clean']['row'][o]['choice']]
        moved = cl != sd
        print(f'  {c:<7} {cl+" -> "+str(sd):<40} {"YES" if moved else "NO":<7} {collat or "-"}')
        payload[c] = {'clean': cl, 'seeded': sd, 'moved': moved, 'collateral': collat}
    res['_movement'] = payload
    return res


# ---------------------------------------------------------------- PHASE B: share vs instability
def shared_evidence(pkt, sch, ext):
    """ONE evidence block, then every clause as a question — the census's own shape, and it keeps the
    state under JEV's ceiling. Round 3's first attempt repeated a per-clause evidence block 32 times and
    the state came to 152,281 chars, which the API rejected (`max_tokens_exceeded`) on all six passes."""
    keep = ('job_id', 'entry', 'mode', 'ratified', 'buyer', 'specialist', 'maker', 'evaluator',
            'human_seat', 'escalation', 'ground_truth', 'mandate_ref', 'bounds', 'pass_rule',
            'reads_before_freeze', 'dimensions')
    view = {k: pkt[k] for k in keep if k in pkt}
    gate = (R.CORPUS / 'tools/validate_job_packet.py').read_text()
    return '\n\n'.join([
        'A software repository is being read against a doctrine checklist. The evidence below is the '
        'whole of what is available; each question concerns one clause of that checklist.',
        '===== THE JOB PACKET =====\n' + json.dumps(view, indent=1)[:5000],
        '===== MACHINE SURFACE: derived schema constraints =====\n' +
        json.dumps({'required': sch.get('required', []),
                    'terminal_state': R._find(sch, 'terminal_state')[:2],
                    'outcome': R._find(sch, 'outcome')[:2],
                    'escalation': R._find(sch, 'escalation')[:2],
                    'ground_truth': R._find(sch, 'ground_truth')[:2],
                    'bounds': R._find(sch, 'bounds')[:2]}, indent=1)[:5000],
        '===== MACHINE SURFACE: instance-extensions.json =====\n' + json.dumps(ext, indent=1)[:6000],
        '===== THE CORPUS ENFORCEMENT GATE: the checker that runs on a packet =====\n' + gate[:8500],
    ])


def phase_b(repeats=6):
    pkt = json.loads(PACKET.read_text())
    sch = json.loads((REPO / 'schemas/job-packet.schema.json').read_text())
    ext = json.loads((REPO / 'schemas/instance-extensions.json').read_text())
    state = shared_evidence(pkt, sch, ext)
    print(f'\n=== PHASE B: share vs instability, {len(ALL)} clauses x {repeats} repeats '
          f'(state {len(state):,} chars) ===')
    runs = []
    for i in range(repeats):
        resp = ask(state, f'B_{i+1}', ALL)
        if 'error' in resp:
            print(f'  pass {i+1} FAILED {resp["error"][:110]}'); continue
        r = row_of(resp, ALL)
        runs.append(r)
        print(f'  pass {i+1}: in={resp["usage"]["input_tokens"]} out={resp["usage"]["output_tokens"]}')
        time.sleep(0.2)
    if len(runs) < 2:
        return {'error': 'not enough passes'}
    table = []
    for c in ALL:
        picks = [r[c]['choice'] for r in runs if c in r]
        shares = [r[c]['max_share'] for r in runs if c in r and r[c]['max_share'] is not None]
        if not picks or not shares:
            continue
        mode_pick = max(set(picks), key=picks.count)
        stab = picks.count(mode_pick) / len(picks)
        table.append({'clause': c, 'max_share_mean': round(mean(shares), 3),
                      'stability': round(stab, 3), 'picks': picks,
                      'pick': mode_pick, 'share_range': round(max(shares) - min(shares), 3)})
    table.sort(key=lambda x: -x['max_share_mean'])
    print(f'\n  {"clause":<7} {"share":<7} {"share range":<12} {"stability":<10} pick')
    for t in table:
        print(f'  {t["clause"]:<7} {t["max_share_mean"]:<7} {t["share_range"]:<12} '
              f'{t["stability"]:<10} {t["pick"]}')
    hi = [t for t in table if t['max_share_mean'] >= 0.70]
    lo = [t for t in table if t['max_share_mean'] < 0.70]
    print(f'\n  mean stability at share >= 0.70: '
          f'{mean([t["stability"] for t in hi]):.3f}  (n={len(hi)})' if hi else '  no high-share group')
    print(f'  mean stability at share <  0.70: '
          f'{mean([t["stability"] for t in lo]):.3f}  (n={len(lo)})' if lo else '  no low-share group')
    unstable = [t['clause'] for t in table if t['stability'] < 1.0]
    print(f'  clauses with any instability: {unstable or "none"}')
    if unstable:
        ranks = {t['clause']: i + 1 for i, t in enumerate(table)}
        print(f'  their share ranks (1 = highest share): '
              f'{ {c: ranks[c] for c in unstable} } of {len(table)}')
    return {'table': table, 'runs': len(runs), 'state_chars': len(state)}


if __name__ == '__main__':
    only = sys.argv[1] if len(sys.argv) > 1 else 'all'
    path = OUT / 'jev-probe-r3-raw.json'
    out = json.loads(path.read_text()) if path.exists() else {}
    if only in ('all', 'a'):
        out['phase_a'] = phase_a()
    if only in ('all', 'b'):
        out['phase_b'] = phase_b()
    path.write_text(json.dumps(out, indent=2))
    print(f'\nraw -> {path}')
