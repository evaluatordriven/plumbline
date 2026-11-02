#!/usr/bin/env python3
"""
JEV ROUND 2 — the same question, with round 1's design faults fixed.

WHAT ROUND 1 GOT WRONG, and the source of each fix (all vendor or independent docs, not my guesses):
1. WRONG PRIMITIVE. TypeSafe: "a Choice is RELATIVE, settling which option, while each Noul is ABSOLUTE
   and can be low for ALL of them." Round 1 asked ten `noul` questions, so a mid-band answer for every
   clause was the CORRECT response to the question actually asked. -> `choice` over the three legal
   readings, with `unobserved` as an EXPLICIT option (PriorBench rec 04: without an explicit "none of
   these", 0 of 30 out-of-scope items were flagged, at 0.99 confidence).
2. WRONG THRESHOLDS. PriorBench: accuracy is flat from 0.50 to 0.95 then jumps to 100% at 0.99,
   covering 60.2%. "Gate at 0.99, or do not gate." -> gate at 0.99 on the choice confidence.
3. CONTEXT ROT. TypeSafe failure mode #5, "large state full of irrelevant detail". -> filtered state:
   the clause, and only the facts that clause needs. No tests/, no build script, no full rule index.
4. COMPOUND QUESTIONS. TypeSafe #7 contradictory criteria, #8 "ask each decision one way"; PriorBench:
   wrong criteria are catastrophic (16.7%, below the 25% random floor) while MISSING criteria cost 0.8
   points. -> short, exact criteria; one judgment per question.

Option order is FIXED and declared (PriorBench rec 07: up to 13 points of movement on ambiguous tasks),
and criteria are ordered low-to-high so order never carries information.

RULE 12: five defects are seeded, each the specific thing one clause governs. Every one must move to
`does_not_conform`. An engine that cannot fail the artifact class it judges certifies nothing.
"""
import json
import os
import pathlib
import subprocess
import tempfile
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
# pin.json names the corpus repository; the checkout itself comes from $EDI_CORPUS.
CORPUS = pathlib.Path(os.environ.get('EDI_CORPUS') or 'EDI_CORPUS-not-set').expanduser()
OUT = REPO / 'dot-plumbline' / 'probes' / 'jev-evaluator-probe'
OUT.mkdir(parents=True, exist_ok=True)
TMP = pathlib.Path(tempfile.gettempdir()) / 'jev-r2'; TMP.mkdir(exist_ok=True)  # honours $TMPDIR
# The TypeSafe key comes from the environment only; nothing is read from a dotfile.
KEY = os.environ.get('TYPESAFE_API_KEY', '')
if not KEY and __name__ == '__main__':
    raise SystemExit('set TYPESAFE_API_KEY to run this probe')
PACKET = REPO / 'dot-plumbline/jobs/2026-09-29-plumbline-conformance-census/packet.json'

# FIXED option order, low-to-high, with `unobserved` last so it reads as the escape, not as a middle score.
OPTS = {
    'does_not_conform': 'The evidence in the state shows this requirement is NOT met.',
    'conforms': 'The evidence in the state shows this requirement IS met.',
    'unobserved': 'The state does not contain what is needed to decide this, or the point is not governed.',
}

CL = ['C5', 'C6', 'C7', 'C9', 'C11', 'C15', 'C18', 'C25', 'C31', 'C33']


def questions():
    """ONE uniform, NON-LEADING question per clause: does this artifact satisfy it?

    Round 1 asked bespoke questions that carried the answer inside them — the C33 question literally told
    the model to go and look at the checker. That is PriorBench's catastrophic-wrong-criteria failure and
    TypeSafe's #7, in the question rather than the criteria. This asks the same thing of every clause, so
    nothing in the wording favours an outcome, and it is the exact question the census asked."""
    return {_c.lower(): {'type': 'choice', 'criteria': OPTS,
                         'instructions': f'Clause {_c} states: "{clause_text(_c)}". Does the artifact '
                                         f'described in the state satisfy this clause?'}
            for _c in CL}


def _gate_lines(*needles, cap=34):
    """Only the checker lines a clause actually turns on. Round 1 passed bare words like 'bounds', which
    matched dozens of unrelated lines — TypeSafe failure mode #5, large state full of irrelevant detail,
    which the docs call context rot."""
    src = (CORPUS / 'tools/validate_job_packet.py').read_text().splitlines()
    keep = set()
    for i, l in enumerate(src):
        if any(n in l for n in needles):
            keep.update({i - 1, i, i + 1})
    return '\n'.join(f'{i+1:>4}| {src[i]}'
                     for i in sorted(k for k in keep if 0 <= k < len(src))[:cap])


def facts(cid, d, defect):
    """Return ONLY the evidence this clause needs. No hand-written conclusions — literals only."""
    pkt = {k: d.get(k) for k in ('job_id', 'entry', 'mode', 'ratified', 'buyer', 'specialist', 'maker',
                                 'evaluator', 'human_seat', 'escalation', 'ground_truth', 'mandate_ref',
                                 'bounds', 'pass_rule', 'reads_before_freeze') if k in d}
    sch = json.loads((REPO / 'schemas/job-packet.schema.json').read_text())
    f = []
    if cid == 'C5':
        f.append('job mode: ' + str(d.get('mode')))
        f.append('packet bounds, verbatim: ' + json.dumps(d.get('bounds')))
        f.append('derived schema requires, for a scored job: ' +
                 json.dumps(_find(sch, 'bounds')[0] if _find(sch, 'bounds') else None)[:300])
        f.append('corpus checker lines about bounds and readings mode:\n' +
                 _gate_lines('SCORED_BOUND_KEYS', 'readings mode must not supply', 'scored bounds missing'))
    elif cid == 'C6':
        f.append('packet maker: ' + json.dumps(d.get('maker'))[:400])
        f.append('packet evaluator: ' + json.dumps(d.get('evaluator')))
        f.append('AGENTS.md seats: ' + _agr('seats'))
        f.append('corpus checker lines on role separation:\n' + _gate_lines('must not hold the Evaluator'))
    elif cid == 'C7':
        f.append('packet dimensions: ' + json.dumps(d.get('dimensions'))[:800])
        f.append('derived schema on ground truth access: ' +
                 json.dumps(_find(sch, 'ground_truth_access')[:2])[:400])
    elif cid == 'C9':
        f.append('derived schema terminal-state enum: ' + json.dumps(_find(sch, 'terminal_state')[:3])[:400])
        f.append('derived schema top-level required: ' + json.dumps(sch.get('required', []))[:300])
        f.append('corpus checker lines on terminal state:\n' + _gate_lines('terminal_state'))
    elif cid == 'C11':
        f.append('packet escalation, verbatim: ' + json.dumps(d.get('escalation'))[:400])
        f.append('packet human_seat: ' + json.dumps(d.get('human_seat')))
        f.append('derived schema escalation definition: ' + json.dumps(_find(sch, 'escalation')[:2])[:400])
    elif cid == 'C15':
        f.append('AGENTS.md invariants on external writes: ' + _agr('writes'))
        f.append('tools/ listing: ' + json.dumps(sorted(p.name for p in (REPO / 'tools').glob('*'))))
        f.append('any read-back verifier in the repo: ' +
                 json.dumps([str(p.relative_to(REPO)) for p in REPO.rglob('*read_back*')]))
    elif cid == 'C18':
        f.append('instance-extensions.json, verbatim: ' +
                 json.dumps(json.loads((REPO / 'schemas/instance-extensions.json').read_text()), indent=1)[:4500])
    elif cid == 'C25':
        f.append('packet maker, verbatim: ' + json.dumps(d.get('maker'))[:600])
        f.append('AGENTS.md Maker row: ' + _agr('maker'))
    elif cid == 'C31':
        f.append('derived schema outcome enum: ' + json.dumps(_find(sch, 'outcome')[:3])[:400])
        f.append('AGENTS.md outcomes: ' + _agr('outcome'))
        f.append('corpus checker lines on no_artifact:\n' + _gate_lines('no_artifact', 'no_artifact'))
    elif cid == 'C33':
        f.append('job mode: ' + str(d.get('mode')))
        f.append('packet ground_truth, verbatim: ' + json.dumps(d.get('ground_truth'))[:500])
        f.append('packet mandate_ref, verbatim: ' + json.dumps(d.get('mandate_ref')))
        f.append('packet escalation, verbatim: ' + json.dumps(d.get('escalation'))[:400])
        f.append('derived schema definitions: ' + json.dumps(
            {k: _find(sch, k)[:1] for k in ('ground_truth', 'mandate_ref', 'escalation')})[:900])
        f.append('corpus checker: the full frame check it runs on a scored job:\n' +
                 _gate_lines('SCORED_BOUND_KEYS', 'scored mode missing', 'frame', 'escalation'))
    return '\n'.join(f)


def _find(node, key, acc=None):
    acc = [] if acc is None else acc
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                acc.append(v)
            _find(v, key, acc)
    elif isinstance(node, list):
        for v in node:
            _find(v, key, acc)
    return acc


def _agr(what):
    t = (REPO / 'AGENTS.md').read_text().splitlines()
    if what == 'seats':
        return ' | '.join(l.strip()[:150] for l in t if 'plumbline-eval' in l or 'Evaluator seat' in l)[:700]
    if what == 'writes':
        return ' | '.join(l.strip()[:200] for l in t if 'read-back' in l or 'fresh on every run' in l)[:700]
    if what == 'maker':
        return ' | '.join(l.strip()[:200] for l in t if 'Maker' in l and ('seat' in l or 'profile' in l))[:700]
    if what == 'outcome':
        return ' | '.join(l.strip()[:300] for l in t if 'outcome' in l.lower())[:900]
    return ''


def clause_text(cid):
    """The checklist keys are `id` (the C-number) and `clause` (the requirement TEXT). Round 1 inverted
    them, so its clause block came out empty and the model was asked to judge ten requirements whose
    wording it never saw. That is the single largest fault in round 1 and it is fixed here."""
    rub = json.loads((REPO / 'dot-plumbline/jobs/2026-09-29-plumbline-conformance-census/'
                      'instrument/compliance-checklist.json').read_text())
    for c in rub['clauses']:
        if c.get('id') == cid:
            return c.get('clause', '')
    return '<clause text not found — the instrument is broken, not the artifact>'


def seed(d):
    d.pop('escalation', None)
    if isinstance(d.get('evaluator'), dict):
        d['evaluator']['who'] = 'Owner'
    if isinstance(d.get('bounds'), dict):
        d['bounds'].pop('cap', None)
    d.pop('human_seat', None)
    d['reads_before_freeze'] = 'none'
    return d


def build_state(defect=False):
    d = json.loads(PACKET.read_text())
    if defect:
        d = seed(d)
    blocks = ['A software repository is being read against a doctrine checklist. Below is ONE clause and '
              'the evidence gathered for it. Judge only from that evidence.']
    for n, cid in enumerate(CL):
        blocks.append(f'===== Q{n+1} / {cid} =====\nCLAUSE {cid}: {clause_text(cid)}\n\nEVIDENCE:\n'
                      f'{facts(cid, d, defect)}')
    return '\n\n'.join(blocks)


def ask(state, tag):
    req = TMP / f'_req_{tag}.json'
    req.write_text(json.dumps({'state': state, 'model': 'jev-latest', 'questions': questions()}))
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
        return {'error': 'non-object response'}
    if 'detail' in x:
        return {'error': f'api: {x["detail"]}'}
    return x


def main():
    runs = {}
    for label, defect, reps in (('clean', False, 3), ('seeded_defects', True, 2)):
        state = build_state(defect)
        print(f'\n=== {label} (state {len(state):,} chars, {reps} repeats) ===')
        runs[label] = {'state_chars': len(state), 'passes': []}
        for i in range(reps):
            t0 = time.time(); resp = ask(state, f'{label}_{i+1}'); el = time.time() - t0
            if 'error' in resp:
                print(f'  pass {i+1}: FAILED {resp["error"][:130]}')
                runs[label]['passes'].append({'error': resp['error']}); continue
            ans = resp.get('answers', {}); u = resp.get('usage', {})
            row = {}
            for q in questions():
                a = ans.get(q) or {}
                # GATE AT 0.99 (PriorBench: flat 0.50-0.95, then 100% at 0.99; gate at 0.99 or not at all)
                conf = a.get('confidence')
                pick = a.get('choice')
                row[q] = {'choice': pick, 'confidence': conf,
                          'probabilities': a.get('probabilities'),
                          'gated': pick if (conf is not None and conf >= 0.99) else 'unobserved'}
            runs[label]['passes'].append({'row': row, 'usage': u, 'elapsed_s': round(el, 2)})
            print(f'  pass {i+1}: {el:.1f}s in={u.get("input_tokens")} out={u.get("output_tokens")}')
            for q, v in row.items():
                print(f'      {q:<18} conf={str(v["confidence"]):<6} pick={str(v["choice"]):<16} '
                      f'gated={v["gated"]}')
            time.sleep(0.3)
    (OUT / 'jev-probe-r2-raw.json').write_text(json.dumps(runs, indent=2))
    print(f'\nraw -> {OUT / "jev-probe-r2-raw.json"}')


if __name__ == '__main__':
    main()
