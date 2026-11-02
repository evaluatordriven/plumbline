#!/usr/bin/env python3
"""
OPERATIONAL RELIABILITY — the channel, and it is a PROXY.

WHAT IT IS A PROXY FOR. The direction's second falsification condition is "the solutions cannot be
relied upon for the real operations of a business". That is about solutions running in the OWNER'S work.
Plumbline's own tooling is not his business's operations. So this channel reads PLUMBLINE'S OWN
OPERATING LOOP and is declared a proxy at DOCUMENT hardness, everywhere the reading appears. If it
scores well and the label is forgotten, the job will have certified Plumbline's tidiness instead of the
condition the direction names. The Owner accepted the proxy on 2026-10-01 with "proxy accepted (record
it as such in the report)".

WHY THE METRIC IS NOT A PASS FRACTION. This probe passes almost always. A fraction near 1.0 would be a
number that cannot move and therefore certifies nothing. What can move is the STRETCH OF CONSECUTIVE
FAILING RUNS, and how often the Owner has to intervene.

ITS DECLARED WEAKNESS, and it is a real one. The intervention count is a DECLARED source, not a
detected one: a breakage the Owner fixes without telling the agent is invisible to this instrument. So
the channel is BIASED TOWARD PASSING. It reports `not recorded` rather than zero when no intervention log
exists, because zero would be a fabricated reading — under-counting is preferable to fabricating.

Usage:  check_operating_loop.py [--record] [--selftest]
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import time

SHIP = pathlib.Path(__file__).resolve().parent.parent
HISTORY = SHIP / 'dot-plumbline' / 'operating-loop.jsonl'
INTERVENTIONS = SHIP / 'dot-plumbline' / 'interventions.jsonl'
# The E-DI corpus checkout, from $EDI_CORPUS (no home-directory guessing).
CORPUS = pathlib.Path(os.environ.get('EDI_CORPUS') or 'EDI_CORPUS-not-set').expanduser()
# The plugin home. The env override exists so the shadow guard below can be PROVEN RED against a planted
# duplicate instead of asserted — a guard nobody has seen fail is a guard nobody knows works.
PLUGINS_ROOT = pathlib.Path(os.environ.get(
    'PLUMBLINE_PLUGINS_ROOT', pathlib.Path.home() / '.hermes' / 'plugins'))
PY = sys.executable

CHECKS = [
    ('pin_and_build', ['tools/build_schemas.py', '--check']),
    ('schemas', ['tests/validate_schemas.py']),
    ('constitution', ['tests/validate_constitution.py']),
    ('pin_prose', ['tests/validate_pin_prose.py']),
    ('gate_acceptance', ['tests/test_discoverability_gate.py']),
    ('gate_doors', ['tests/test_discoverability_gate_doors.py']),
    ('gate_host_shape', ['tests/test_discoverability_gate_host_shape.py']),
]


def _run_log_exemption(job_dir):
    """A job's own declaration that the run-log does not name it. In the FOLDER, where §10.1 puts it."""
    pkt = job_dir / 'packet.json'
    if not pkt.is_file():
        return None
    try:
        decl = json.loads(pkt.read_text()).get('run_log_exempt')
    except Exception:
        return None
    return decl if isinstance(decl, dict) and decl.get('reason') else None


def provenance_checks():
    """Provenance guards, added 2026-10-01 after two incidents in one job.

    1. THE VANISHING PACKET. Job full-score's packet was authored, never committed, and gone from disk
       hours later when the evaluator needed it — the open commit carried only the ADR. Nothing
       detected it; the failure surfaced by luck. So: every jobs/<id>/ directory must contain a
       packet.json, and every packet on disk must be TRACKED in git. An authored-but-uncommitted packet
       is a record that cannot be reconstructed (failure F6), caught by the loop probe rather than by
       luck.

    2. THE UNEARNED SURFACE. Two channel tools were built and immediately became unearned surface —
       proportionality read 92% until the lapse was noticed at the NEXT reading. The polarity exists;
       it should not wait for a reading to fire. So the loop probe runs it and FAILS on any unearned
       surface: unearned surface is a broken loop, not a filing chore.
    """
    out = []
    jobs = SHIP / 'dot-plumbline' / 'jobs'
    for d in sorted(jobs.iterdir()):
        if not d.is_dir():
            continue
        pkt = d / 'packet.json'
        if not pkt.exists():
            out.append({'check': f'provenance:packet-present:{d.name}', 'ok': False, 'exit': 1,
                        'detail': f'{d.name} has no packet.json — an authored record is unaccounted for'})
            continue
        r = subprocess.run(['git', 'ls-files', '--error-unmatch', str(pkt.relative_to(SHIP))],
                           cwd=SHIP, capture_output=True, text=True)
        out.append({'check': f'provenance:packet-tracked:{d.name}', 'ok': r.returncode == 0,
                    'exit': r.returncode,
                    'detail': ('tracked' if r.returncode == 0
                               else 'packet exists but is NOT committed to git — failure F6 waiting')})

    # 3. THE SHORT BODY. Measured by the corpus maintainer 2026-10-05: 8 job folders on disk, 7 named in
    # run-log.json — so an audit that enumerates from the index reads a short body SILENTLY, and the tool that
    # creates job folders (the kit's wrapper) wrote no row at open or at close. Every folder is now named in
    # the log BY THE TOOL that made it, and this check holds the whole body to that. The one historical folder
    # is declared below with its reason rather than tolerated by a loose check: a tolerance nobody can see is
    # the same defect as a skip nobody can see.
    log = SHIP / 'dot-plumbline' / 'run-log.json'
    named: set[str] = set()
    if log.is_file():
        # READ THE SHAPE THE LOG IS IN. Measured 2026-10-05, by me: the log is {"note": ..., "runs": [...]}, and
        # a reader that iterated the top level read the KEYS as rows and reported five folders unnamed that are
        # named. A reader that does not know what it is reading reports a short body.
        try:
            doc = json.loads(log.read_text())
            rows = doc.get('runs') if isinstance(doc, dict) else doc
            if not isinstance(rows, list):
                raise ValueError(f'no list of runs found (top-level {type(doc).__name__})')
            named = {str(r.get('job_id')) for r in rows if isinstance(r, dict) and r.get('job_id')}
        except Exception as exc:
            out.append({'check': 'provenance:run-log-readable', 'ok': False, 'exit': 1,
                        'detail': f'run-log.json is not readable as a list of runs: {exc}'})

    folders = [d for d in sorted(jobs.iterdir()) if d.is_dir()]
    exempt_n = 0
    for d in folders:
        if d.name in named:
            out.append({'check': f'provenance:job-named-in-run-log:{d.name}', 'ok': True, 'exit': 0,
                        'detail': 'named in run-log.json'})
        elif isinstance(decl := _run_log_exemption(d), dict):
            # The exemption lives in the FOLDER, not in this checker: it is counted below, its reason is the
            # job's own, and adding one is visible in the output rather than invisible in a constant.
            exempt_n += 1
            out.append({'check': f'provenance:job-named-in-run-log:{d.name}', 'ok': True, 'exit': 0,
                        'detail': f'EXEMPT BY DECLARATION — {decl.get("reason", "no reason given")} '
                                  f'(declared by {decl.get("declared_by", "unknown")})'})
        else:
            out.append({'check': f'provenance:job-named-in-run-log:{d.name}', 'ok': False, 'exit': 1,
                        'detail': 'the run-log does not name this folder and the folder declares no '
                                  'run_log_exempt — an audit enumerating from the index reads a short body '
                                  'silently. The wrapper writes the row; a folder made by hand is named in '
                                  'the log, or declares why it is not.'})
    out.append({'check': 'provenance:run-log-body', 'ok': True, 'exit': 0,
                'detail': f'{len(folders)} folders · {len(named & {d.name for d in folders})} named in the log · '
                          f'{exempt_n} exempt by declaration — the count is stated so that adding one is visible'})

    r = subprocess.run([PY, str(SHIP / 'tools' / 'check_proportionality.py')],
                       capture_output=True, text=True, timeout=300)
    unearned = [l for l in r.stdout.splitlines() if 'UNEARNED' in l.upper() and '0' not in l]
    txt = (r.stdout + r.stderr)
    n_unearned = 0
    for line in txt.splitlines():
        if line.strip().startswith('surface items') or 'earned fraction' in line:
            pass
    import re as _re
    m_earn = _re.search(r'earned fraction\s+([0-9.]+)%', txt)
    frac = float(m_earn.group(1)) if m_earn else None
    m_un = _re.search(r'UNEARNED\s+(\d+)', txt)
    n_unearned = int(m_un.group(1)) if m_un else None
    out.append({'check': 'provenance:proportionality-ledger-current', 'ok': frac == 100.0,
                'exit': 0 if frac == 100.0 else 1,
                'detail': (f'earned fraction {frac}%, {n_unearned} unearned'
                           if frac is not None else 'could not read the proportionality output')
                          + (' — UNEARNED SURFACE means a built thing was not declared; fail the loop'
                             if (n_unearned or 0) > 0 else '')})
    return out


def _declared_plugin_names(root):
    """plugin name -> [directory names that declare it], read from each plugin.yaml."""
    declared = {}
    if not root.is_dir():
        return declared
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        manifest = d / 'plugin.yaml'
        if not manifest.is_file():
            continue
        try:
            text = manifest.read_text()
        except Exception:
            continue
        m = re.search(r'^\s*name:\s*["\']?([^"\'\n#]+)', text, re.M)
        if m:
            declared.setdefault(m.group(1).strip(), []).append(d.name)
    return declared


def plugin_shadow_checks():
    """THE SHADOWED INSTALL — added 2026-10-01, after an hour lost to it.

    A sibling directory inside the plugin home that carries a `plugin.yaml` IS a plugin: discovery loads
    it, and the host's registry lets a same-name, same-toolset duplicate OVERWRITE SILENTLY
    (hermes-agent/tools/registry.py:89). A backup parked next to the real plugin can therefore win the
    registration, and the symptom is the worst kind: the fix is on disk, verified byte-for-byte,
    installed, the gateway restarted — and the OLD code answers. Every file check said "new code"; only
    the traceback's `File` path disagreed.

    Two guards, because the trap is general while this project owns exactly one plugin:
      1. exactly ONE installed directory declares this project's plugin name;
      2. NO plugin name is declared by two different directories, whoever owns them.
    """
    declared = _declared_plugin_names(PLUGINS_ROOT)
    out = []

    ours = declared.get('plumbline-gate', [])
    out.append({'check': 'plugins:plumbline-gate-single-install', 'ok': len(ours) == 1, 'exit': 0 if len(ours) == 1 else 1,
                'detail': (f'exactly one install declares plumbline-gate ({ours[0]})' if len(ours) == 1
                           else f'{len(ours)} directories declare plumbline-gate: {ours} — the registry lets a '
                                'same-name duplicate overwrite SILENTLY, so the loaded code may not be the '
                                'code you installed. Move backups out of the plugin home.')})

    dupes = {n: ds for n, ds in declared.items() if len(ds) > 1}
    out.append({'check': 'plugins:no-duplicate-declarations', 'ok': not dupes, 'exit': 0 if not dupes else 1,
                'detail': ('no plugin name is declared twice' if not dupes
                           else f'declared more than once: {dupes} — each is a silent-overwrite candidate')})
    return out


SKILLS_INSTALLED_ROOT = pathlib.Path(os.environ.get(
    'PLUMBLINE_SKILLS_ROOT', pathlib.Path.home() / '.hermes' / 'skills'))

PUBLISHED_COPY_ID = os.environ.get('EDI_PUBLISHED_COPY_ID', '')   # the published copy's Drive file id (unarmed)
PUBLICATION_ARMED = False                                   # declared deferral — see publication_check()
PUBLICATION_PROBE = (SHIP / 'dot-plumbline' / 'probes' / 'drive-vs-local-2026-10-02' / 'compare_drive.py')


def compare_trees(a, b):
    """Pure. Returns (missing_in_b, extra_in_b, differing) as relative-path lists."""
    def files(root):
        return {str(p.relative_to(root)): p.read_bytes()
                for p in root.rglob('*') if p.is_file() and '__pycache__' not in str(p)}
    fa, fb = files(a), files(b)
    return (sorted(set(fa) - set(fb)), sorted(set(fb) - set(fa)),
            sorted(k for k in set(fa) & set(fb) if fa[k] != fb[k]))


def skill_copy_check(installed_root=None, canonical_root=None):
    """The installed adapter must be byte-identical to the corpus copy.

    RED CASE, 2026-10-02: the installed E-DI skill sat at v1.5.15 — a version behind the corpus — and still
    carried the sentence the corpus had already corrected. Nothing watched the copy: a human found it with
    grep, which is not a guard. The seam (installed_root / PLUMBLINE_SKILLS_ROOT) exists so a drift can be
    PLANTED and this check shown failing, rather than trusted.
    """
    name = 'skills:installed-copy-matches-corpus'
    installed = pathlib.Path(installed_root or SKILLS_INSTALLED_ROOT) / 'productivity' / 'evaluator-driven-iteration'
    canonical = pathlib.Path(canonical_root or CORPUS) / 'skills' / 'evaluator-driven-iteration'
    for label, p in (('canonical', canonical), ('installed', installed)):
        if not p.is_dir():
            return {'check': name, 'ok': False, 'exit': None,
                    'detail': f'{label} skill directory absent: {p} — an absent copy is not a matching one'}
    missing, extra, differ = compare_trees(canonical, installed)
    ok = not (missing or extra or differ)
    first = (differ or missing or extra or [''])[0]
    detail = ('identical to the corpus copy' if ok else
              f'installed copy differs: {len(missing)} missing, {len(extra)} extra, '
              f'{len(differ)} differing — first: {first}')
    return {'check': name, 'ok': ok, 'exit': 0 if ok else 1, 'detail': detail}


def publication_verdict(report):
    """Pure: (ok, detail) for a compare_drive report."""
    diff, only_drive, only_local = (len(report.get(k, [])) for k in ('differ', 'only_drive', 'only_local'))
    ok = not (diff or only_drive or only_local)
    return ok, ('published copy matches the corpus' if ok else
                f'published copy differs: {diff} differing, {only_drive} on Drive only, '
                f'{only_local} local only')


def publication_check():
    """The hand-published Drive copy of the doctrine against the local corpus.

    DECLARED DEFERRAL, not an oversight. Measured 2026-10-02: that copy is stale since 2026-09-30 and carries
    two junk folders named '.'. Reconciling or retiring it is the Owner's call and is open, so this guard is
    NOT ARMED — and it says so, loudly, instead of reporting a pass. A deferral with a named trigger is
    legitimate; a silent skip is not. TRIGGER: the Owner's disposition on the published copy.
    """
    name = 'publication:published-copy-matches-corpus'
    if not PUBLICATION_ARMED:
        return {'check': name, 'ok': True, 'exit': 0,
                'detail': ('NOT ARMED — declared deferral: the hand-published copy is stale since 2026-09-30 '
                           'with junk "." folders; its disposition is open with the Owner since '
                           '2026-10-02. Trigger: that decision; then clear PUBLICATION_ARMED.')}
    if not PUBLICATION_PROBE.is_file():
        return {'check': name, 'ok': False, 'exit': None, 'detail': f'probe absent: {PUBLICATION_PROBE}'}
    out = PUBLICATION_PROBE.parent / 'last-report.json'
    r = subprocess.run([PY, str(PUBLICATION_PROBE), '--drive-id', PUBLISHED_COPY_ID,
                        '--local', str(CORPUS), '--json-out', str(out)],
                       capture_output=True, text=True, timeout=300)
    if not out.is_file():
        return {'check': name, 'ok': False, 'exit': r.returncode,
                'detail': f'no report produced (exit {r.returncode}): {(r.stderr or r.stdout).strip()[-80:]}'}
    ok, detail = publication_verdict(json.loads(out.read_text()))
    return {'check': name, 'ok': ok, 'exit': 0 if ok else 1, 'detail': detail}


def run_check(name, argv):
    try:
        r = subprocess.run([PY, *argv], cwd=SHIP, capture_output=True, text=True, timeout=300)
        return {'check': name, 'ok': r.returncode == 0,
                'exit': r.returncode,
                'detail': ((r.stdout + r.stderr).strip().splitlines() or [''])[-1][:110]}
    except Exception as e:
        return {'check': name, 'ok': False, 'exit': None, 'detail': f'{type(e).__name__}: {e}'[:110]}


def corpus_gate():
    """The corpus's own gate over every live packet. The loop is not 'green' if a packet it produced
    no longer validates against the law it claims to obey."""
    out = []
    for p in sorted((SHIP / 'dot-plumbline' / 'jobs').glob('*/packet.json')):
        try:
            r = subprocess.run([PY, str(CORPUS / 'tools' / 'validate_job_packet.py'), str(p)],
                               capture_output=True, text=True, timeout=300)
            out.append({'check': f'corpus_gate:{p.parent.name}', 'ok': r.returncode == 0,
                        'exit': r.returncode,
                        'detail': ((r.stdout + r.stderr).strip().splitlines() or [''])[-1][:110]})
        except Exception as e:
            out.append({'check': f'corpus_gate:{p.parent.name}', 'ok': False,
                        'detail': f'{type(e).__name__}: {e}'[:110]})
    return out


def history():
    if not HISTORY.exists():
        return []
    rows = []
    for line in HISTORY.read_text().splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def interventions():
    """Declared, not detected. Returns None when nothing is recorded — which is NOT zero."""
    if not INTERVENTIONS.exists():
        return None
    n = sum(1 for l in INTERVENTIONS.read_text().splitlines() if l.strip())
    return n


def streak(rows):
    n = 0
    for r in reversed(rows):
        if r.get('ok'):
            break
        n += 1
    return n


def measure():
    results = ([run_check(n, a) for n, a in CHECKS] + corpus_gate() + provenance_checks()
               + plugin_shadow_checks() + [skill_copy_check(), publication_check()])
    return {'at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=SHIP,
                                     capture_output=True, text=True).stdout.strip()[:12],
            'ok': all(c['ok'] for c in results),
            'failures': [c['check'] for c in results if not c['ok']],
            'checks_run': len(results),
            'results': results}


def main():
    if '--selftest' in sys.argv:
        return selftest()
    row = measure()
    if '--record' in sys.argv:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY.open('a') as fh:
            fh.write(json.dumps(row) + '\n')
    rows = history() or [row]
    iv = interventions()
    print('OPERATIONAL RELIABILITY — PROXY over Plumbline\'s own operating loop\n')
    print(f'  PROXY, NOT THE CONDITION: this reads Plumbline\'s tooling, not the Owner\'s business')
    print(f'  operations. Declared at DOCUMENT hardness.\n')
    print(f'  this run          {"PASS" if row["ok"] else "FAIL"}  '
          f'({row["checks_run"] - len(row["failures"])}/{row["checks_run"]} checks)')
    if row['failures']:
        for f in row['failures']:
            print(f'      FAILED: {f}')
    print(f'  runs recorded     {len(rows)}')
    print(f'  consecutive fails {streak(rows)}   <- THE METRIC; a pass fraction would sit at ~1.0 and')
    print(f'                       never move, which is why it is not the metric')
    print(f'  interventions     {"not recorded — the log is absent; this count is DECLARED, not detected" if iv is None else f"{iv} recorded"}')
    print(f'\n  BIAS DECLARED: a breakage nobody reports is invisible here, so a good reading is weaker')
    print(f'  evidence than it looks.')
    return 0 if row['ok'] else 1


def selftest():
    """Prove the probe can fail. A probe that cannot report a broken loop certifies nothing."""
    bad = 0
    total = 0
    global CHECKS

    def case(name, ok, detail=''):
        nonlocal bad, total
        total += 1
        print(f'  {"ok  " if ok else "FAIL"}  {name}')
        if not ok:
            print(f'        -> {detail}')
        bad += 0 if ok else 1

    saved = list(CHECKS)
    try:
        # 1. a healthy loop reports ok
        r = measure()
        case('a healthy loop measures as pass', r['ok'] and not r['failures'], str(r['failures']))
        case('  and it exercised real checks', r['checks_run'] >= len(CHECKS), str(r['checks_run']))

        # 2. a BROKEN loop is reported as broken — the whole point
        CHECKS = [('deliberately_broken', ['-c', 'raise SystemExit(1)'])]
        r = measure()
        case('a broken loop measures as FAIL', not r['ok'] and r['failures'] == ['deliberately_broken'],
             str(r['failures']))

        # 3. the streak counts consecutive failures from the end, and resets on a pass
        rows = [{'ok': True}, {'ok': False}, {'ok': False}]
        case('a streak of 2 is counted', streak(rows) == 2, str(streak(rows)))
        case('a trailing pass resets it', streak([{'ok': False}, {'ok': True}]) == 0)

        # 4. interventions report NOT RECORDED rather than zero
        truth = INTERVENTIONS.exists()
        case('interventions from an absent log are NOT zero', interventions() is None if not truth
             else True, f'exists={truth}')

        # 5. THE PROVENANCE GUARDS — each shown able to FAIL, not just pass
        pv = provenance_checks()
        names = [c['check'] for c in pv]
        case('provenance guards run on every job dir',
             any(n.startswith('provenance:packet-tracked:') for n in names), str(names))
        case('  the ledger-current check exists',
             'provenance:proportionality-ledger-current' in names)
        case('  and the live repo passes them',
             all(c['ok'] for c in pv), str([c for c in pv if not c['ok']]))

        # 6. THE DRIFT GUARDS — the same rule as every other guard here: shown failing before trusted.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            canon = base / 'corpus' / 'skills' / 'evaluator-driven-iteration'
            inst = base / 'skills' / 'productivity' / 'evaluator-driven-iteration'
            for rel, body in (('SKILL.md', 'version 1\n'), ('references/a.md', 'ref\n')):
                for root in (canon, inst):
                    p = root / rel
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(body)
            r = skill_copy_check(installed_root=base / 'skills', canonical_root=base / 'corpus')
            case('the skill-copy guard passes an identical pair', r['ok'], r['detail'])
            (inst / 'SKILL.md').write_text('version 0\n')          # the 2026-10-02 drift, in miniature
            r = skill_copy_check(installed_root=base / 'skills', canonical_root=base / 'corpus')
            case('  and FAILS on a drifted installed copy',
                 (not r['ok']) and 'differ' in r['detail'], r['detail'])
            r = skill_copy_check(installed_root=base / 'nothing-here', canonical_root=base / 'corpus')
            case('  and FAILS when nothing is installed', not r['ok'], r['detail'])

        pub = publication_check()
        case('the publication guard is a declared deferral with a named trigger',
             ('NOT ARMED' in pub['detail']) and ('Owner' in pub['detail']), pub['detail'])
        clean, _ = publication_verdict({'differ': [], 'only_drive': [], 'only_local': []})
        drifted, d_detail = publication_verdict({'differ': [{'path': 'x'}], 'only_drive': [],
                                                 'only_local': []})
        case('  and its comparison FAILS on a drifted pair', clean and not drifted, d_detail)
    finally:
        CHECKS = saved

    print(f'\n  {total - bad}/{total} behaved as designed' if bad == 0 else f'\n  {bad} DID NOT')
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
