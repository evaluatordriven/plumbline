#!/usr/bin/env python3
"""
Plumbline conformance-read runner — the CODE half of the instrument (Contracts C30: the instrument
is BOTH the rubric and the runner; the record names the version and the sha256 of each).

Reads a frozen surface of a repo at a pinned commit and returns one reading per §9 clause, in the
readings form: `conforms` / `does_not_conform` / `unobserved`. No numbers, no thresholds — with no
Specialist named at the outset there is no bar, and a bar invented here would be law nothing ratified.

WHY IT CHUNKS THE CLAUSES. Measured on this seat: a trivial prompt reasons for ~190 tokens, but a
three-clause read of a 27 KB surface reasons for ~19,400 tokens before emitting anything
(finish_reason `stop`, content 1,422 chars of JSON). Reasoning therefore scales with the reading,
and 33 clauses in one call would need on the order of 200k reasoning tokens — which is why every
single-call attempt returned `finish_reason: length` with EMPTY content and a full reasoning budget.
Chunking is not an optimisation; it is what makes the reading possible at all.

NO PROVIDER-ENFORCED RESPONSE SCHEMA, deliberately. The corpus measures this seat as ignoring strict
json_schema in roughly one call in three, so a strict schema is false confidence. The runner asks for
JSON in the prompt and normalises tolerantly instead, then VALIDATES the result itself: every clause
id exactly once, every reading one of the three legal words. A chunk that fails validation is
recorded `no_observation` with its reason — never a silently short reading set.

A parse failure is NOT a crash: it is recorded as `no_observation`, because the doctrine budgets for
it (a run that produced no observation is an outcome, not an error).

Usage:
  run_conformance_read.py --out <path> --label <name> [--root <dir>] [--surface legacy]
                          [--chunk-size 6] [--max-tokens 0]
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import time

import requests
import yaml

REPO = pathlib.Path(__file__).resolve().parent.parent
PROFILE_DIR = pathlib.Path(os.environ.get('PLUMBLINE_EVAL_PROFILE')
                           or pathlib.Path.home() / '.hermes' / 'profiles' / 'plumbline-eval')
RUBRIC = REPO / 'schemas' / 'compliance-checklist.json'
LEGAL_READINGS = ('conforms', 'does_not_conform', 'unobserved')
# The pinned corpus, so the ENFORCEMENT SURFACE can be observed and not only the derived schema.
# pin.json names the corpus repository; the checkout itself comes from $EDI_CORPUS.
CORPUS_ROOT = pathlib.Path(os.environ.get('EDI_CORPUS') or 'EDI_CORPUS-not-set').expanduser()

# The frozen observed surface. Deterministic by construction — no globbing, no discovery order.
DEFAULT_SURFACE = [
    'AGENTS.md',
    'README.md',
    'dot-plumbline/README.md',
    'dot-plumbline/jobs/2026-09-29-plumbline-conformance-census/packet.json',
    'schemas/instance-extensions.json',
    'schemas/job-packet.schema.json',
    'schemas/evaluator-record.schema.json',
    'schemas/audit-record.schema.json',
    'schemas/constitution.schema.json',
    'schemas/compliance-checklist.json',
    'tools/build_schemas.py',
    'tools/pin.json',
    'tests/validate_schemas.py',
    'tests/validate_audit.py',
    # THE ENFORCEMENT SURFACE, NOT JUST THE SCHEMA. A JSON Schema is half the machine: the corpus's
    # own gate covers object shapes the schema's `not` blocks miss. MEASURED on 2026-09-30 — with
    # `escalation: ""` the gate exits 1 ("scored mode missing: escalation") while a bare jsonschema
    # pass over the same packet reports ZERO errors. So an instrument that observes the schema
    # without the gate reports the schema's looseness as a defect in the doctrine. It did exactly
    # that on 2026-09-29; the finding had to be withdrawn. Read both, or read wrongly.
    'corpus:tools/validate_job_packet.py',
    'corpus:EDI-RULE-INDEX.json',
]

# The known-bad comparator for the failure test: the frozen pre-alignment generation, which carried
# the severity enum Contracts §5 forbids. An instrument that does not read this as non-conforming is
# broken, and its verdicts on anything else are worthless.
LEGACY_SURFACE = [
    'schemas/legacy/plumbline-s8-2026-09/job-packet.schema.json',
    'schemas/legacy/plumbline-s8-2026-09/evaluator-record.schema.json',
    'schemas/legacy/plumbline-s8-2026-09/audit-record.schema.json',
]


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(p):
    return sha256_bytes(pathlib.Path(p).read_bytes())


def load_seat():
    """Model and provider come from the profile, so the seat cannot drift from what is recorded."""
    cfg = yaml.safe_load((PROFILE_DIR / 'config.yaml').read_text())
    model = cfg['model']['default']
    provider = cfg['model']['provider']
    key = os.environ.get('OPENROUTER_API_KEY') or None  # the environment wins over the profile .env
    env = PROFILE_DIR / '.env'
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith('OPENROUTER_API_KEY='):
                key = line.split('=', 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit('no OPENROUTER_API_KEY in the profile .env — the seat cannot be reached')
    return model, provider, key


def load_clauses():
    rub = json.loads(RUBRIC.read_text())
    clauses = rub.get('clauses')
    if not isinstance(clauses, list) or not clauses:
        sys.exit('rubric has no clauses[] — refusing to read against an unreadable rubric')
    for c in clauses:
        if 'id' not in c:
            sys.exit(f'rubric clause without an id: {str(c)[:80]}')
    return clauses


def assemble(surface, root):
    parts, manifest = [], []
    for rel in surface:
        # `corpus:<path>` resolves inside the PINNED CORPUS, not the artifact under audit. The
        # enforcement surface lives there — the gate, the disposition index — and leaving it out of
        # the observation is what produced a finding that had to be withdrawn.
        if rel.startswith('corpus:'):
            p = CORPUS_ROOT / rel.split(':', 1)[1]
        else:
            p = pathlib.Path(root) / rel
        if not p.exists():
            sys.exit(f'surface file missing: {rel} — the surface is frozen; fix it rather than skipping')
        raw = p.read_bytes()
        manifest.append({'path': rel, 'bytes': len(raw), 'sha256': sha256_bytes(raw),
                         'source': 'corpus' if rel.startswith('corpus:') else 'artifact'})
        parts.append(f'\n===== FILE: {rel} =====\n{raw.decode("utf-8")}\n===== END {rel} =====\n')
    return ''.join(parts), manifest


def build_prompt(rubric_subset, surface_text, manifest, artifact_commit, surface_name, n_total, lo, hi):
    man = '\n'.join(f"  {m['path']}  {m['bytes']} bytes  sha256 {m['sha256'][:16]}…" for m in manifest)
    clause_list = json.dumps(rubric_subset, indent=2)
    # DESCRIBE THE PASS ACCURATELY, contiguous or not. An earlier version always printed
    # "CLAUSES {lo}-{hi}", which LIED whenever the subset was non-contiguous: handed the ids
    # C1,C3,C5,C7,C8,C11,C13 it announced "C1-C13", the seat read the clauses in between, returned
    # six that were never supplied, and the chunk was rejected whole. The chunk validator caught it
    # — a tolerant parser would have accepted the extras silently. The ids are now always listed.
    ids = [c.get('id') for c in rubric_subset]
    contiguous = all(f'C{int(ids[0][1:]) + i}' == c for i, c in enumerate(ids))
    scope = (f"THIS PASS COVERS CLAUSES {lo}-{hi} OF {n_total}" if contiguous
             else f"THIS PASS COVERS A SELECTED SET OF {len(ids)} CLAUSES")
    return f"""You are the EVALUATOR for a conformance audit. You are reading an existing artifact and returning ONE READING PER CLAUSE of the frozen rubric below. You are not scoring anything. You are not producing numbers. There is no bar to be above or below.

{scope}.
READ ONLY THE CLAUSES LISTED BELOW — {len(ids)} of {n_total} — and return a reading for EVERY one of them and for NO other clause. The clause ids in this pass are exactly: {', '.join(ids)}.

YOUR TASK, FOR EVERY CLAUSE:
- `conforms` — the observed surface shows the clause holds. Quote the exact text you relied on.
- `does_not_conform` — the observed surface shows the clause does not hold. Quote the exact text, and say in one or two sentences what the artifact does and what the clause requires.
- `unobserved` — the observed surface cannot show whether the clause holds. `quotation` must be the empty string. Do NOT guess, and do NOT read a clause favourably because the artifact's own documentation claims compliance. A claim of compliance is not evidence of compliance. `unobserved` is a legitimate and expected answer.

RULES THAT OVERRIDE YOUR JUDGEMENT:
1. Judge ONLY against the rubric's wording and the observed surface. Do not import requirements from your own knowledge of good practice.
2. The artifact's own documentation is EVIDENCE OF INTENT, NOT OF BEHAVIOUR. Where the docs claim something the surface does not show, read the clause against the surface, and treat the gap as itself an observation.
3. A file the surface does not contain is not evidence of absence unless the clause is about that file's existence. Prefer `unobserved` to a confident negative you cannot support.
4. This artifact is a RETROFIT. Clauses about behaviour that ran historically (a loop, a run, an escalation) are `unobserved` if the surface cannot show them.
5. Read each clause ONCE and stop. Do not re-litigate a reading you have already made; state it and move on. You have a limited output budget and the readings are the deliverable.

Return JSON ONLY, in exactly this shape, with one entry per clause covered by this pass:
{{"readings": [{{"clause": "the clause id exactly as given", "reading": "conforms|does_not_conform|unobserved", "quotation": "exact text relied on, or empty string", "note": "one or two sentences"}}]}}
No prose outside the JSON. No markdown fences. Every clause id in this pass must appear exactly once.

ARTIFACT: Plumbline repository at commit {artifact_commit}, surface "{surface_name}".
FILES OBSERVED ({len(manifest)}):
{man}

===== THE CLAUSES TO READ (frozen rubric) =====
{clause_list}
===== END CLAUSES =====

===== THE OBSERVED SURFACE =====
{surface_text}
===== END OBSERVED SURFACE =====
"""


def parse_readings(text, expected_ids):
    """Tolerant of fences and prose. Returns (list_of_readings, how) or (None, why_not)."""
    if not text or not text.strip():
        return None, 'empty content'
    body = text.strip()
    body = re.sub(r'^```(?:json)?\s*', '', body)
    body = re.sub(r'\s*```$', '', body)
    obj = None
    try:
        obj = json.loads(body)
    except Exception:
        m = re.search(r'\{.*\}', body, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
            except Exception:
                return None, 'unparseable even after fence-strip and brace salvage'
    if obj is None:
        return None, 'unparseable'
    items = obj.get('readings') if isinstance(obj, dict) else obj
    if not isinstance(items, list):
        return None, f'no readings array (top-level keys: {list(obj)[:8]})'

    # Normalise: the seat naturally emits `clause_id`; the record uses `clause`.
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        cid = it.get('clause') or it.get('clause_id') or it.get('id')
        rd = (it.get('reading') or it.get('verdict') or '').strip().lower().replace(' ', '_')
        if rd == 'does_not_conform' or rd == 'doesnotconform':
            rd = 'does_not_conform'
        out.append({'clause': cid, 'reading': rd,
                    'quotation': it.get('quotation') or it.get('quote') or it.get('evidence') or '',
                    'note': it.get('note') or it.get('why') or it.get('rationale') or ''})

    got = [o['clause'] for o in out]
    missing = [c for c in expected_ids if c not in got]
    extra = [c for c in got if c not in expected_ids]
    dupes = sorted({c for c in got if got.count(c) > 1})
    illegal = sorted({o['reading'] for o in out if o['reading'] not in LEGAL_READINGS})
    problems = []
    if missing:
        problems.append(f'missing clauses: {missing}')
    if extra:
        problems.append(f'clauses not in this pass: {extra}')
    if dupes:
        problems.append(f'duplicated clauses: {dupes}')
    if illegal:
        problems.append(f'illegal readings: {illegal}')
    if problems:
        return None, '; '.join(problems)
    return out, 'validated'


def call_chunk(prompt, model, key, timeout, max_tokens, reasoning_max_tokens=0, provider_order=''):
    body = {'model': model, 'temperature': 0,
            'messages': [{'role': 'user', 'content': prompt}]}
    if max_tokens:
        body['max_tokens'] = max_tokens
    if reasoning_max_tokens:
        body['reasoning'] = {'max_tokens': reasoning_max_tokens}
    if provider_order:
        body['provider'] = {'order': [provider_order], 'allow_fallbacks': False}
    t = time.time()
    try:
        r = requests.post('https://openrouter.ai/api/v1/chat/completions',
                          headers={'Authorization': f'Bearer {key}',
                                   'Content-Type': 'application/json'},
                          json=body, timeout=timeout)
    except Exception as e:
        return {'outcome': 'no_observation', 'error': f'{type(e).__name__}: {e}',
                'elapsed_s': round(time.time() - t, 1)}
    el = round(time.time() - t, 1)
    if r.status_code != 200:
        return {'outcome': 'no_observation', 'http_status': r.status_code,
                'error': r.text[:400], 'elapsed_s': el}
    b = r.json()
    u = b.get('usage') or {}
    ch = b['choices'][0]
    msg = ch.get('message') or {}
    return {
        'outcome': 'raw', 'elapsed_s': el, 'served_by': b.get('provider'),
        'finish_reason': ch.get('finish_reason'),
        'completion_tokens': u.get('completion_tokens'),
        'prompt_tokens': u.get('prompt_tokens'),
        'reasoning_tokens': (u.get('completion_tokens_details') or {}).get('reasoning_tokens'),
        'cost_usd': u.get('cost'),
        'content': msg.get('content'),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--label', required=True)
    ap.add_argument('--root', default=str(REPO))
    ap.add_argument('--surface', choices=['default', 'legacy'], default='default')
    ap.add_argument('--artifact-commit', default='')
    ap.add_argument('--chunk-size', type=int, default=6)
    # 0 = omit the cap entirely. Measured: every capped single-call attempt starved (`length`,
    # empty content, reasoning == cap); the uncapped call finished (`stop`) with content.
    ap.add_argument('--max-tokens', type=int, default=0)
    # BOUNDED THINKING. Measured: an unbounded budget produced 9,630-29,468 reasoning tokens across
    # six same-sized chunks over the same surface — a 3x intrinsic spread, NOT explained by provider
    # routing (same provider varied 2x). A floating thinking length means a floating instrument, and
    # the instrument is what produced the reading (C30), so two passes would not be comparable. With
    # reasoning.max_tokens=6000 the seat returned IDENTICAL readings at half the elapsed time and
    # ~40% of the cost. Measured on this seat via OpenRouter.
    ap.add_argument('--reasoning-max-tokens', type=int, default=6000)
    # The serving backend is an instrument property: four providers served one run (Decart, Parasail,
    # Together, OpenInference). Not pinned by default — pinning turns a provider outage into a failed
    # chunk — but recorded per chunk so a spread across passes can be attributed.
    ap.add_argument('--provider-order', default='')
    ap.add_argument('--timeout', type=int, default=1200)
    args = ap.parse_args()

    surface = LEGACY_SURFACE if args.surface == 'legacy' else DEFAULT_SURFACE
    model, provider, key = load_seat()
    all_clauses = load_clauses()
    surface_text, manifest = assemble(surface, args.root)

    # RETAIN THE INSTRUMENT WITH THE ARTIFACT (§10.1). The record names the rubric and runner
    # hashes (C30), but naming a hash is worthless if the bytes are gone — the runner is a source
    # file that changes, so the instrument that produced a past record was unrecoverable until it
    # was reconstructed from git history. Archived CONTENT-ADDRESSED, so a changed instrument never
    # overwrites an earlier one and two versions coexist for the same job.
    inst_dir = pathlib.Path(args.out).parent / 'instrument'
    inst_dir.mkdir(parents=True, exist_ok=True)
    for src, tag in ((pathlib.Path(__file__), 'run_conformance_read'), (RUBRIC, 'compliance-checklist')):
        baked = sha256_file(src)
        (inst_dir / f'{tag}.{baked[:12]}{src.suffix}').write_bytes(src.read_bytes())

    chunks = [all_clauses[i:i + args.chunk_size]
              for i in range(0, len(all_clauses), args.chunk_size)]

    record = {
        'label': args.label,
        'instrument': {
            'rubric': {'path': 'schemas/compliance-checklist.json', 'sha256': sha256_file(RUBRIC)},
            'runner': {'path': 'tools/run_conformance_read.py', 'sha256': sha256_file(__file__)},
            'chunk_size': args.chunk_size,
            'max_tokens': args.max_tokens or 'uncapped',
            'reasoning_max_tokens': args.reasoning_max_tokens or 'uncapped',
            'provider_order': args.provider_order or 'not pinned — recorded per chunk',
            'response_format': 'none — prompt-asked JSON, normalised and validated by the runner',
        },
        'seat': {'profile': 'plumbline-eval', 'model': model, 'provider': provider, 'temperature': 0},
        'observed_surface': manifest,
        'artifact_commit': args.artifact_commit,
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'chunks': [],
    }

    readings, total_cost, total_reasoning = [], 0.0, 0
    for n, chunk in enumerate(chunks, 1):
        ids = [c['id'] for c in chunk]
        prompt = build_prompt(chunk, surface_text, manifest, args.artifact_commit,
                              args.surface, len(all_clauses), ids[0], ids[-1])
        res = call_chunk(prompt, model, key, args.timeout, args.max_tokens,
                         args.reasoning_max_tokens, args.provider_order)
        entry = {'chunk': n, 'clauses': ids, **{k: v for k, v in res.items() if k != 'content'}}
        if res.get('outcome') == 'raw':
            parsed, how = parse_readings(res.get('content'), ids)
            entry['parse'] = how
            if parsed:
                entry['outcome'] = 'observed'
                readings.extend(parsed)
            else:
                entry['outcome'] = 'no_observation'
                entry['reason'] = how
                entry['raw_head'] = (res.get('content') or '')[:400]
        total_cost += res.get('cost_usd') or 0
        total_reasoning += res.get('reasoning_tokens') or 0
        record['chunks'].append(entry)
        # Persist after EVERY chunk. A six-chunk pass runs ~25 minutes; holding it all in memory means
        # one failure at the last chunk discards every validated chunk before it. Observed for real:
        # five chunks validated and invisible until the sixth returned.
        _p = pathlib.Path(args.out)
        _p.parent.mkdir(parents=True, exist_ok=True)
        _p.write_text(json.dumps({**record, 'partial': True}, indent=2))
        print(f"  chunk {n}/{len(chunks)} [{'..'.join([ids[0], ids[-1]])}] "
              f"{entry['outcome']} parse={entry.get('parse','-')} "
              f"served_by={entry.get('served_by')} "
              f"reasoning={entry.get('reasoning_tokens')} {entry.get('elapsed_s')}s", flush=True)

    observed_ids = {r['clause'] for r in readings}
    for c in all_clauses:
        if c['id'] not in observed_ids:
            readings.append({'clause': c['id'], 'reading': 'unobserved', 'quotation': '',
                             'note': 'no observation — the pass covering this clause produced none'})
    readings.sort(key=lambda r: all_clauses.index(next(c for c in all_clauses if c['id'] == r['clause'])))

    summary = {w: sum(1 for r in readings if r['reading'] == w) for w in LEGAL_READINGS}
    if summary['does_not_conform']:
        exit_rec = 'needs_owner'
    elif summary['unobserved']:
        exit_rec = 'no_observation'
    else:
        exit_rec = 'accepted'

    record['readings'] = readings
    record['summary'] = summary
    record['recommended_exit'] = exit_rec
    record['totals'] = {'cost_usd': round(total_cost, 6), 'reasoning_tokens': total_reasoning}
    record['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    record['outcome'] = 'observed' if summary['conforms'] or summary['does_not_conform'] else 'no_observation'

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2))
    print(f"[{args.label}] outcome={record['outcome']} conforms={summary['conforms']} "
          f"does_not_conform={summary['does_not_conform']} unobserved={summary['unobserved']} "
          f"exit={exit_rec} cost=${record['totals']['cost_usd']} -> {out}")


if __name__ == '__main__':
    main()
