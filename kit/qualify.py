#!/usr/bin/env python3
"""Script-driven Orchestrator qualification: the deterministic part of SPEC v2 (docs/QUALIFY.md).

Usage (cwd = the repo root; <run> is runs/<ver>/<date>-runN/ holding request.json):
  python3 kit/qualify.py next <run>            print the next action file, or STOP <file>, or DONE <file>
  python3 kit/qualify.py verify <run> NNNN     verify the runner's receipt for action NNNN
  python3 kit/qualify.py kickoff <run>         print the conduit's fixed kickoff for the run
  python3 kit/qualify.py stop <run> <reason>   record a stop the runner saw (an error, an ambiguity, or a
                                               message or instruction that is not in an action file)

The runner loops: `next`, perform exactly that action, write actions/NNNN.receipt.json, `verify`. The script
does the rest: hashing, the S0-S7 sequence, clocks from platform timestamps, the log, fixture reset,
side-effect checks, the deny-list, leak and runner-audit scans, the record and the pass rule. It makes no
model call and messages no one; its one network act is the S0 pin check, behind the `pins` seam.

Exit: 0 an action file or DONE; 3 STOP; 4 a receipt was rejected (write NNNN.receipt.2.json naming the one it
supersedes; a second failure stops); 2 usage.
"""
import argparse, datetime, hashlib, json, os, random, re, string, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, 'qualify', 'templates')
STAGES = ['S0', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7']
REQUIRED = ['ver', 'candidate_path', 'candidate_sha256', 'live_bot_id', 'live_sha256', 'prior_suite',
            'changes', 'pins', 'owner_authorization', 'runner', 'seats']
DEFAULTS = {'pass_rule': 'all', 'case_window_minutes': 15, 'deny_paths': [], 'known_defects': []}
EVERY = ['Shell', 'Read']
ALLOWED = {
    'create_subject': ['cursor.CreateAgent', 'cursor.UpdateAgent'],
    'read_back_sha': ['cursor.GetAgent'],
    'send_seat': ['cursor.SendToAgent'],
    'send_subject': ['cursor.SendToAgent'],
    'await_reply': [],
    'export_trace': ['cursor.ReadTranscript'],
}
NEVER = {'WebSearch', 'WebFetch', 'UpdateMemory', 'UpdateRoutine', 'UpdateSkill', 'UpdateProfile', 'Task',
         'CreateChannel', 'Vault', 'FillCredential'}
RECEIPT_FIELDS = ['action_id', 'done_at', 'platform_ids', 'reply_verbatim_path', 'reply_sha256',
                  'tools_called', 'sent_unedited']
PLATFORM_IDS = {'create_subject': ['bot_id'], 'send_seat': ['sent_at'], 'send_subject': ['sent_at']}
REPLY_REQUIRED = ('read_back_sha', 'export_trace')
KEY_NAME = re.compile(r'(?<![\w.-])(keys/|KEY(?:[._-][\w.-]*)?(?!\w))')
SHA64 = re.compile(r'\b[0-9a-f]{64}\b')
SHELL_OK = re.compile(r'^(cd \S+ && )?((\S*/)?python3? (\S*/)?kit/qualify\.py |sha256sum |'
                      r'(cat|tee|printf|echo)\b[^\n]*actions/\d{4}\.receipt(\.2)?\.json)')
SILENT_ARCHITECT_MIN = 24 * 60
EXPECTS = ('should-pass', 'should-stop')
VERDICTS = ('pass', 'fail', 'void')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_bytes(path):
    with open(path, 'rb') as fh:
        return fh.read()


def file_sha(path):
    return sha256(read_bytes(path))


def text_sha(data):
    """The sha of a bot text: trailing newlines stripped (SPEC L44)."""
    return sha256(data.rstrip(b'\n'))


def now_local():
    return datetime.datetime.now().astimezone()


def iso(t):
    return t.isoformat(timespec='seconds')


def parse_time(text):
    """An ISO 8601 time with its zone, else None."""
    try:
        t = datetime.datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else None


def load_json(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def first_json(text):
    """The first JSON object in a seat's reply, else None."""
    dec = json.JSONDecoder()
    for m in re.finditer(r'\{', text):
        try:
            obj, _ = dec.raw_decode(text, m.start())
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def sha_check(manifest):
    """In-process `sha256sum -c`: '<hex>  <path>' lines, paths relative to the manifest's directory.
    Returns the failing lines (an empty list is a pass)."""
    base, bad = os.path.dirname(os.path.abspath(manifest)), []
    try:
        lines = read_bytes(manifest).decode('utf-8').splitlines()
    except (OSError, UnicodeDecodeError) as e:
        return ['cannot read %s: %s' % (manifest, e)]
    for line in lines:
        m = re.match(r'^([0-9a-f]{64}) [ *](.+)$', line)
        if not m:
            bad.append('malformed line: %r' % line)
            continue
        p = os.path.join(base, m.group(2))
        try:
            ok = file_sha(p) == m.group(1)
        except OSError:
            ok = False
        if not ok:
            bad.append('%s: FAILED' % m.group(2))
    return bad if lines else ['empty manifest']


def write_sums(root, name='SHA256SUMS'):
    """Write `sha256sum` lines for every file under root except the sums file and .tmp/."""
    rows = []
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if not (d == root and x == '.tmp'))
        for f in sorted(files):
            p = os.path.join(d, f)
            rel = os.path.relpath(p, root)
            if rel != name:
                rows.append('%s  %s\n' % (file_sha(p), rel))
    path = os.path.join(root, name)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.writelines(rows)
    return path


def tmp_entries():
    return len(os.listdir('/tmp'))  # S0: count entries before and after (SPEC L75)


def git_pin(url, ref):
    """The S0 pin check (SPEC L74): the commit a remote ref names, else None."""
    r = subprocess.run(['git', 'ls-remote', url, ref], capture_output=True, text=True, timeout=120)
    words = r.stdout.split()
    return words[0] if r.returncode == 0 and words else None


def run_tool(path, args, cwd, env):
    """Run one suite tool; returns (exit code, combined output)."""
    try:
        r = subprocess.run([path] + list(args), cwd=cwd, env=env, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)
    return r.returncode, r.stdout + r.stderr


def render(name, **values):
    with open(os.path.join(TEMPLATES, name), encoding='utf-8') as fh:
        return string.Template(fh.read()).substitute(values)


def bullets(items):
    return '\n'.join('- %s' % x for x in items) or '- (none)'


class Stop(Exception):
    """A stop rule fired (SPEC section 5): STOP.md is written and goes to Steve."""

    def __init__(self, stage, check, evidence=None, quote=None):
        super().__init__(check)
        self.stage, self.check, self.evidence, self.quote = stage, check, evidence, quote


class Wait(Exception):
    """The runner has something to do first: an action file to perform, or a receipt to correct."""

    def __init__(self, word, text):
        super().__init__(text)
        self.word, self.text = word, text


class Transport:
    """The five acts the runner does by hand (SPEC L38-40). A supported API could implement them in code."""

    def create_subject(self, name, payload_path, like):
        raise NotImplementedError

    def read_back(self, bot_id, reply_to):
        raise NotImplementedError

    def send(self, kind, target, payload_path):
        raise NotImplementedError

    def await_reply(self, target, reply_to):
        raise NotImplementedError

    def export_trace(self, bot_id, reply_to):
        raise NotImplementedError


class RunnerTransport(Transport):
    """Each act is an intent file the runner performs; its result is the runner's verified receipt."""

    def __init__(self, run):
        self.run = run

    def create_subject(self, name, payload_path, like):
        return self._act('create_subject', name, payload_path, like=like)['platform_ids']['bot_id']

    def read_back(self, bot_id, reply_to):
        return self._act('read_back_sha', bot_id, reply_to=reply_to)['reply']

    def send(self, kind, target, payload_path):
        return parse_time(self._act(kind, target, payload_path)['platform_ids']['sent_at'])

    def await_reply(self, target, reply_to):
        r = self._act('await_reply', target, reply_to=reply_to)
        return r['reply'], parse_time(r['platform_ids'].get('reply_at')), parse_time(r['done_at'])

    def export_trace(self, bot_id, reply_to):
        return self._act('export_trace', bot_id, reply_to=reply_to)['reply']

    def _act(self, kind, target, payload_path=None, reply_to=None, like=None):
        run = self.run
        run.n += 1
        n = '%04d' % run.n
        intent = {'kind': kind, 'target': target, 'payload_path': payload_path,
                  'payload_sha256': file_sha(payload_path) if payload_path else None,
                  'allowed_tools': EVERY + ALLOWED[kind]}
        if reply_to:
            intent['reply_to'] = reply_to
        if like:
            intent['like'] = like
        ip = run.p('actions', n + '.intent.json')
        if not os.path.exists(ip):
            run.write_new(ip, json.dumps(intent, indent=1) + '\n')
            run.log('intent', n, intent['payload_sha256'], kind=kind, target=target)
            raise Wait('ACTION', ip)
        old = load_json(ip)
        if dict(old, payload_sha256=None) != dict(intent, payload_sha256=None):
            raise Stop(run.stage, 'action %s on record is not the action the procedure needs now' % n, ip)
        if old['payload_sha256'] != intent['payload_sha256']:
            raise Stop(run.stage, 'runner deviation in action %s: payload edited after its intent' % n, payload_path)
        receipts = run.receipts(n)
        if not receipts:
            raise Stop(run.stage, 'intent %s has no receipt: never resend blind; ask Steve' % n, ip)
        rp = receipts[-1]
        problem, fatal, rec = check_receipt(run, n, intent, rp, len(receipts))
        rel = os.path.relpath(rp, run.dir)
        if not problem:
            run.log('verified', n, key='verified ' + rel)
            return rec
        if fatal:
            raise Stop(run.stage, 'runner deviation in action %s: %s' % (n, problem), rp)
        run.log('rejected', n, key='rejected ' + rel, reason=problem)
        if len(receipts) >= 2:
            raise Stop(run.stage, 'receipt for action %s failed verification twice: %s' % (n, problem), rp)
        raise Wait('REJECTED', '%s %s; write actions/%s.receipt.2.json with "supersedes": "%s"'
                   % (n, problem, n, os.path.basename(rp)))


def check_receipt(run, n, intent, path, count):
    """Returns (problem or None, fatal, receipt with 'reply' bytes). A fatal problem is a runner deviation."""
    try:
        r = load_json(path)
    except (OSError, ValueError) as e:
        return 'receipt is not JSON: %s' % e, False, None
    if not isinstance(r, dict):
        return 'receipt is not a JSON object', False, None
    missing = [f for f in RECEIPT_FIELDS if f not in r]
    if missing:
        return 'receipt lacks %s' % missing, False, None
    if count > 1 and r.get('supersedes') != os.path.basename(run.receipts(n)[0]):
        return 'a second receipt must name the one it supersedes', False, None
    if r['action_id'] != n:
        return 'action_id is %r, not %s' % (r['action_id'], n), False, None
    if r['sent_unedited'] is not True:
        return 'the runner does not report the payload sent unedited', True, None
    tools = r['tools_called'] if isinstance(r['tools_called'], list) else [r['tools_called']]
    off = [t for t in tools if t not in intent['allowed_tools']]
    if off:
        return 'off-list tool(s) %s' % off, True, None
    if intent['payload_path'] and file_sha(intent['payload_path']) != intent['payload_sha256']:
        return 'payload changed after its intent was written', True, None
    if not parse_time(r['done_at']):
        return 'done_at is not a time with its zone', False, None
    ids = r['platform_ids'] if isinstance(r['platform_ids'], dict) else {}
    need = [k for k in PLATFORM_IDS.get(intent['kind'], []) if not ids.get(k)]
    if need:
        return 'platform_ids lacks %s' % need, False, None
    if any(not parse_time(v) for k, v in ids.items() if k.endswith('_at') and v is not None):
        return 'a platform timestamp is not a time with its zone', False, None
    reply, rp = None, r['reply_verbatim_path']
    if intent['kind'] in REPLY_REQUIRED and not rp:
        return 'no reply_verbatim_path', False, None
    if rp:
        if intent.get('reply_to') and rp != intent['reply_to']:
            return 'reply saved at %r, not %r' % (rp, intent['reply_to']), False, None
        full = rp if os.path.isabs(rp) else run.p(rp)
        if not os.path.isfile(full):
            return 'reply file %s is missing' % rp, False, None
        reply = read_bytes(full)
        if sha256(reply) != r['reply_sha256']:
            return 'reply_sha256 does not match the saved reply', False, None
        if intent['kind'] == 'await_reply' and not parse_time(ids.get('reply_at')):
            return 'a reply without a platform reply_at time', False, None
    return None, False, dict(r, reply=reply, platform_ids=ids)


class Run:
    """One qualification run, replayed from its append-only record on every command."""

    def __init__(self, path, clock=now_local, tool=run_tool, pins=git_pin):
        self.dir = os.path.abspath(path)
        self.clock, self.tool_fn, self.pins = clock, tool, pins
        self.t = RunnerTransport(self)
        self.n, self.stage, self.suite = 0, 'S0', None
        self.keys = set()
        lp = self.p('log.jsonl')
        if os.path.exists(lp):
            with open(lp, encoding='utf-8') as fh:
                self.keys = {json.loads(x).get('key') for x in fh if x.strip()}

    def p(self, *parts):
        return os.path.join(self.dir, *parts)

    def receipts(self, n):
        names = [n + '.receipt.json', n + '.receipt.2.json']
        return [self.p('actions', x) for x in names if os.path.exists(self.p('actions', x))]

    def log(self, event, action=None, payload_sha=None, key=None, **extra):
        """One line per event: time with zone, stage, action id, payload sha. Nothing is rewritten."""
        key = key or '%s %s %s' % (event, self.stage, action or '')
        if key in self.keys:
            return
        self.keys.add(key)
        line = dict(at=iso(self.clock()), stage=self.stage, action=action, payload_sha256=payload_sha,
                    event=event, key=key, **extra)
        with open(self.p('log.jsonl'), 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(line, sort_keys=True) + '\n')

    def write_new(self, path, text):
        """Write a record file once; an existing one is never rewritten."""
        path = path if os.path.isabs(path) else self.p(path)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + '.part', 'w', encoding='utf-8') as fh:
                fh.write(text)
            os.replace(path + '.part', path)
        return path

    def once(self, name, fn):
        """A step the script runs itself (a tool, a seed, a count) runs once; replays read its record."""
        path = self.p('steps', name + '.json')
        if os.path.exists(path):
            return load_json(path)
        value = fn()
        self.write_new(path, json.dumps(value, indent=1, sort_keys=True) + '\n')
        return value

    def tool(self, name, which, args=()):
        path = os.path.join(self.suite, 'tools', which)
        res = self.once(name, lambda: dict(zip(('rc', 'output'), self.tool_fn(path, list(args), self.suite,
                                                                               self.env))))
        self.log('tool', key='tool ' + name, tool=which, rc=res['rc'])
        return res

    # ---- the procedure -------------------------------------------------------------------------
    def procedure(self):
        for stage in (self.s0, self.s1, self.s2, self.s3, self.s4, self.s5, self.s6):
            stage()
        return self.s7()

    def s0(self):
        self.stage = 'S0'
        rq = self.p('request.json')
        try:
            req = load_json(rq)
        except (OSError, ValueError) as e:
            raise Stop('S0', 'request.json is unreadable: %s' % e, rq)
        missing = [k for k in REQUIRED if k not in req]
        if missing:
            raise Stop('S0', 'request.json lacks %s' % missing, rq)
        self.req = R = dict(DEFAULTS, **req)
        if R['pass_rule'] != 'all':
            raise Stop('S0', 'pass_rule %r: only "all" is defined (SPEC L51, L155)' % R['pass_rule'], rq)
        self.log('start', payload_sha=file_sha(rq))
        cand = R['candidate_path']
        if not os.path.isfile(cand) or text_sha(read_bytes(cand)) != R['candidate_sha256']:
            raise Stop('S0', 'candidate sha does not match candidate_sha256 (trailing newline stripped)', cand)
        ins = R['runner'].get('instructions_path')
        if not ins or not os.path.isfile(ins) or file_sha(ins) != R['runner'].get('instructions_sha256'):
            raise Stop('S0', 'runner instructions do not match request.json runner.instructions_sha256', ins)
        man = R['prior_suite'].get('path')
        if not man or not os.path.isfile(man) or file_sha(man) != R['prior_suite'].get('manifest_sha256'):
            raise Stop('S0', 'prior suite manifest does not match its sha256', man)
        bad = sha_check(man)
        if bad:
            raise Stop('S0', 'sha256sum -c on the prior manifest failed: %s' % '; '.join(bad), man)
        pins = self.once('S0-pins', lambda: {k: self.pins(v['url'], v['ref']) for k, v in sorted(R['pins'].items())})
        wrong = [k for k, v in sorted(R['pins'].items()) if not (pins.get(k) or '').startswith(v['sha'])
                 or len(v['sha']) < 7]
        if wrong:
            raise Stop('S0', 'pin mismatch: %s' % ', '.join('%s remote %s, pinned %s' % (
                k, pins.get(k), R['pins'][k]['sha']) for k in wrong), self.p('steps', 'S0-pins.json'))
        tmp = self.p('.tmp')
        os.makedirs(tmp, exist_ok=True)
        self.env = dict(os.environ, TMPDIR=tmp, TMP=tmp, TEMP=tmp)
        self.tmp = self.once('S0-tmp', lambda: {'tmpdir': tmp, 'tmp_entries_before': tmp_entries()})
        live = self.t.read_back(R['live_bot_id'], 'replies/live-before.txt')
        if text_sha(live) != R['live_sha256']:
            raise Stop('S0', 'live bot sha is not live_sha256', self.p('replies', 'live-before.txt'))

    def header(self, n, body):
        R, o, r = self.req, self.req['owner_authorization'], self.req['runner']
        return render('header.txt', ver=R['ver'], action=n, runner_id=r['bot_id'],
                      runner_sha=r['instructions_sha256'], quote=o['quote'], time=o['time'],
                      msg_id=o['message_id'], body_sha=sha256(body.encode())).rstrip('\n')

    def send_seat(self, seat, name, body):
        """A seat message: the section 8 header, a blank line, then the rendered body."""
        n = '%04d' % (self.n + 1)
        self.write_new('%s.md' % name, body)
        path = self.write_new('actions/%s.payload.md' % n, self.header(n, body) + '\n\n' + body)
        return self.t.send('send_seat', self.req['seats'][seat], path)

    def await_(self, target, reply_to, sent, limit_min):
        """Wait for a reply. Times are platform times; a no-reply receipt before the limit waits again."""
        while True:
            reply, at, done = self.t.await_reply(target, reply_to)
            if reply is not None:
                return reply, at
            if limit_min is not None and done >= sent + datetime.timedelta(minutes=limit_min):
                return None, None

    def s1(self):
        self.stage, R = 'S1', self.req
        ch = R['changes']
        body = render('S1.request.md', ver=R['ver'], candidate_sha=R['candidate_sha256'],
                      prior=R['prior_suite']['path'], prior_sha=R['prior_suite']['manifest_sha256'],
                      changes=bullets(ch.get('list', [])), diff=ch.get('diff_path'),
                      defects=bullets(R['known_defects']))
        sent = self.send_seat('architect', 'S1.request', body)
        reply, _ = self.await_(R['seats']['architect'], 'replies/S1.reply.md', sent, SILENT_ARCHITECT_MIN)
        ev = self.p('replies', 'S1.reply.md')
        if reply is None:
            raise Stop('S1', 'the Architect is silent after 24 hours', self.p('log.jsonl'))
        text = reply.decode('utf-8', 'replace')
        m = re.search(r'(/\S*MANIFEST-%s\.sha256)' % re.escape(R['ver']), text)
        s = SHA64.search(text)
        if not (m and s):
            raise Stop('S1', 'the reply gives no manifest path and sha', ev, text)
        man = m.group(1).strip('`\'"')
        if not os.path.isfile(man) or file_sha(man) != s.group(0):
            raise Stop('S1', 'the manifest at %s does not have the sha the reply gives' % man, ev, text)
        bad = sha_check(man)
        if bad:
            raise Stop('S1', 'sha256sum -c failed: %s' % '; '.join(bad), man)
        self.suite, self.manifest_sha = os.path.dirname(man), s.group(0)
        cp = os.path.join(self.suite, 'cases.json')
        try:
            cases = load_json(cp)
            ok = isinstance(cases, list) and cases and all(
                isinstance(c, dict) and {'id', 'prompt_path', 'prompt_sha256', 'expect'} <= set(c)
                and c['expect'] in EXPECTS for c in cases) and len({c['id'] for c in cases}) == len(cases)
        except (OSError, ValueError):
            ok = False
        if not ok:
            raise Stop('S1', 'cases.json does not parse as a list of {id, prompt_path, prompt_sha256, expect,'
                       ' window_minutes}', cp)
        self.cases = cases
        hits = self.leak_scan([self.suite], None, R['deny_paths'])
        if hits:
            raise Stop('S1', 'leak scan: %s' % '; '.join(hits), self.suite)
        for which in ('selftest', 'reset_fixtures'):
            res = self.tool('S1-' + which, which)
            if res['rc'] != 0:
                raise Stop('S1', '%s exited %s' % (which, res['rc']), self.p('steps', 'S1-%s.json' % which))
        self.s1_out = self.write_new('S1.checks.txt', 'manifest %s sha256 %s: sha256sum -c OK\ncases.json: %d '
                                     'cases\nleak scan: clean\nselftest: exit 0\nreset_fixtures: exit 0\n'
                                     % (man, self.manifest_sha, len(cases)))

    def s2(self):
        self.stage, R = 'S2', self.req
        body = render('S2.request.md', ver=R['ver'], manifest_sha=self.manifest_sha,
                      cases=read_bytes(os.path.join(self.suite, 'cases.json')).decode('utf-8'),
                      changes=bullets(R['changes'].get('list', [])),
                      s1_output=read_bytes(self.s1_out).decode('utf-8'))
        sent = self.send_seat('evaluator', 'S2.request', body)
        reply, _ = self.await_(R['seats']['evaluator'], 'replies/S2.reply.md', sent, None)
        ev, text = self.p('replies', 'S2.reply.md'), reply.decode('utf-8', 'replace')
        review = first_json(text)
        if review is None:
            raise Stop('S2', 'the reply holds no review.json object', ev, text)
        self.write_new('review.json', json.dumps(review, indent=1, sort_keys=True) + '\n')
        if review.get('verdict') != 'ready':
            raise Stop('S2', 'verdict is %r, not ready' % review.get('verdict'), ev, text)
        ids = {c['id'] for c in self.cases}
        cov = review.get('cases_covering_changes')
        cov = cov if isinstance(cov, dict) else {}
        loose = [c for c in R['changes'].get('list', []) if not ids & set(cov.get(c) or [])]
        if loose:
            raise Stop('S2', 'change(s) with no case: %s' % loose, ev, text)
        lacking = [e for e in EXPECTS if e not in {c['expect'] for c in self.cases}]
        if lacking:
            raise Stop('S2', 'no %s case (D4.5)' % ' or '.join(lacking), ev, text)
        key = review.get('key_sha256')
        if not (isinstance(key, str) and re.fullmatch(r'[0-9a-f]{64}', key)):
            raise Stop('S2', 'review.json has no key_sha256', ev, text)
        self.key_sha = key
        self.check_leaks()

    def check_leaks(self):
        name = self.stage + '-leak-scan'
        hits = self.once(name, lambda: self.leak_scan([self.dir, self.suite], self.key_sha, []))
        if hits:
            raise Stop(self.stage, 'key leak: %s' % '; '.join(hits), self.p('steps', name + '.json'))

    def leak_scan(self, roots, key_sha, store_paths):
        """Key file names in paths, a file whose sha256 is the key's, key-store paths in contents (L91, L192)."""
        hits = []
        for root in roots:
            for d, dirs, files in os.walk(root):
                dirs.sort()
                for f in sorted(files):
                    p = os.path.join(d, f)
                    rel = os.path.relpath(p, root)
                    if KEY_NAME.search(rel):
                        hits.append('key file name %s' % p)
                    data = read_bytes(p)
                    if key_sha and sha256(data) == key_sha:
                        hits.append('a file with the key\'s sha256: %s' % p)
                    hits += ['%s in %s' % (s, p) for s in store_paths if s.encode() in data]
        return hits

    def make_subject(self, i, suffix):
        name = 'E-DI Orchestrator (%s qual, subject %02d%s)' % (self.req['ver'], i, suffix)
        bot = self.t.create_subject(name, self.req['candidate_path'], self.req['live_bot_id'])
        rel = 'replies/subject-%02d%s.readback.txt' % (i, suffix)
        if text_sha(self.t.read_back(bot, rel)) != self.req['candidate_sha256']:
            raise Stop(self.stage, 'subject sha mismatch: %s (%s)' % (name, bot), self.p(rel))
        self.log('subject', key='subject %s %s' % (name, bot), name=name, bot_id=bot)
        return [name, bot]

    def subjects_file(self, name, note=''):
        lines = ['%s\t%s\t%s\n' % (c['id'], *self.subjects[c['id']]) for c in self.cases]
        return self.write_new(name, note + ''.join(lines))

    def s3(self):
        self.stage = 'S3'
        self.subjects = {c['id']: self.make_subject(i, '') for i, c in enumerate(self.cases, 1)}
        self.subjects_file('SUBJECTS-%s.txt' % self.req['ver'])

    def trace(self, bot, rel):
        data = self.t.export_trace(bot, rel)
        try:
            tr = json.loads(data.decode('utf-8'))
            tr['events'] = [e for e in tr['events'] if isinstance(e, dict)]
        except (ValueError, KeyError, TypeError, AttributeError):
            tr = None
        return tr

    def deny_patterns(self, case):
        own = os.path.dirname(os.path.join(self.suite, case['prompt_path']))
        others = {os.path.dirname(os.path.join(self.suite, c['prompt_path'])) for c in self.cases} - {own}
        return list(self.req['deny_paths']) + [os.path.join(self.suite, 'tools') + '/', 'qualify-script/run/',
                                               self.p('actions') + '/'] + [d + '/' for d in sorted(others)]

    def deny_hits(self, tr, case, first_run_only):
        """Scan tool-call inputs and prose against the fixed deny list (SPEC L112-118)."""
        pats, hits = self.deny_patterns(case), []
        for e in tr['events']:
            if first_run_only and not e.get('first_run'):
                continue
            text = json.dumps(e.get('input', ''), sort_keys=True) + ' ' + str(e.get('text', ''))
            found = [x for x in pats if x in text] + (['keys/ or a KEY file'] if KEY_NAME.search(text) else [])
            hits += ['%s at %s' % (x, e.get('at')) for x in found]
        return hits

    def s4(self):
        self.stage, retired = 'S4', False
        for i, c in enumerate(self.cases, 1):
            tries = 0
            while True:
                name, bot = self.subjects[c['id']]
                rel = 'replies/subject-%02d%s.first-run.json' % (i, '-r%d' % tries if tries else '')
                tr = self.trace(bot, rel)
                if tr is None or not tr.get('start_of_transcript'):
                    raise Stop('S4', 'the export of %s is not complete (no start-of-transcript footer)' % bot,
                               self.p(rel))
                hits = self.deny_hits(tr, c, True)
                if not hits:
                    break
                tries, retired = tries + 1, True
                self.log('retired', key='retired %s' % bot, bot_id=bot, case=c['id'], why=hits)
                if tries >= 2:
                    raise Stop('S4', 'two contaminations on case %s: %s' % (c['id'], '; '.join(hits)), self.p(rel))
                self.subjects[c['id']] = self.make_subject(i, '-r%d' % tries)
                self.log('replacement', key='replacement %s' % c['id'], case=c['id'], resend=False)
        if retired:
            v = self.req['ver']
            self.subjects_file('SUBJECTS-%s.r1.txt' % v, 'supersedes: SUBJECTS-%s.txt\n' % v)

    def s5(self):
        self.stage, R = 'S5', self.req
        ids = [c['id'] for c in self.cases]

        def shuffle():
            seed = random.SystemRandom().randrange(2 ** 32)
            order = list(ids)
            random.Random(seed).shuffle(order)
            return {'seed': seed, 'order': order}
        self.order = self.once('S5-order', shuffle)
        self.log('order', seed=self.order['seed'], order=self.order['order'])
        self.results = {}
        for cid in self.order['order']:
            c = next(x for x in self.cases if x['id'] == cid)
            bot = self.subjects[cid][1]
            if self.tool('S5-%s-reset-before' % cid, 'reset_fixtures')['rc'] != 0:
                raise Stop('S5', 'reset_fixtures failed before case %s' % cid, self.p('steps'))
            prompt = os.path.join(self.suite, c['prompt_path'])
            if not os.path.isfile(prompt) or file_sha(prompt) != c['prompt_sha256']:
                raise Stop('S5', 'prompt of case %s is not pristine' % cid, prompt)
            sent = self.t.send('send_subject', bot, prompt)
            window = c.get('window_minutes') or R['case_window_minutes']
            deadline = sent + datetime.timedelta(minutes=window)
            rel = 'replies/%s.reply.md' % cid
            reply, at = self.await_(bot, rel, sent, window)
            timeout = reply is None or at > deadline
            tr = self.trace(bot, 'replies/%s.trace.json' % cid)
            if tr is None or not tr.get('start_of_transcript'):
                raise Stop('S5', 'the export of %s is not complete (no start-of-transcript footer)' % bot, self.p(
                    'replies', '%s.trace.json' % cid))
            hits = self.deny_hits(tr, c, False)
            se = self.tool('S5-%s-side-effects' % cid, 'check_side_effects', [cid])
            sp = self.write_new('replies/%s.side-effects.txt' % cid, se['output'])
            self.results[cid] = {
                'subject': self.subjects[cid][0], 'bot_id': bot, 'sent_at': iso(sent), 'deadline': iso(deadline),
                'reply_at': iso(at) if at else None, 'timeout': timeout, 'deny_hits': hits,
                'reply_path': rel if reply is not None else None,
                'reply_sha256': sha256(reply) if reply is not None else None,
                'side_effects_rc': se['rc'], 'side_effects_path': os.path.relpath(sp, self.dir),
                'side_effects_sha256': file_sha(sp)}
            self.log('case', key='case ' + cid, payload_sha=self.results[cid]['reply_sha256'], case=cid,
                     timeout=timeout, void=bool(hits), side_effects_rc=se['rc'])
            if self.tool('S5-%s-reset-after' % cid, 'reset_fixtures')['rc'] != 0:
                raise Stop('S5', 'reset_fixtures failed after case %s' % cid, self.p('steps'))
        tr = self.trace(R['runner']['bot_id'], 'replies/runner-transcript.json')
        reasons = self.audit(tr)
        self.audit_result = 'void' if reasons else 'clean'
        self.audit_path = self.write_new('runner-audit.txt', 'runner audit: %s\n%s' % (
            self.audit_result, ''.join('- %s\n' % x for x in reasons)))
        self.log('runner_audit', payload_sha=file_sha(self.audit_path), result=self.audit_result)

    def windows(self):
        """Each action's window: from its intent's logged time to its receipt's done_at."""
        starts = {}
        with open(self.p('log.jsonl'), encoding='utf-8') as fh:
            for x in fh:
                e = json.loads(x)
                if e['event'] == 'intent':
                    starts[e['action']] = parse_time(e['at'])
        out = []
        for n, start in sorted(starts.items()):
            rs = self.receipts(n)
            if rs:
                r = load_json(rs[-1])
                out.append((start, parse_time(r.get('done_at')), load_json(self.p('actions', n + '.intent.json')),
                            r))
        return out

    def audit(self, tr):
        """The post-run runner audit (SPEC L228-242): every reason found voids the run."""
        if tr is None:
            return ['the runner transcript export is not a JSON transcript']
        reasons = [] if tr.get('start_of_transcript') else [
            'export lacks the start-of-transcript footer: not accepted as complete']
        wins = self.windows()
        guard = list(self.req['deny_paths'])
        for e in tr['events']:
            if 'tool' not in e:
                continue
            ns, inp, at = e.get('namespace'), e.get('input') or {}, parse_time(e.get('at'))
            tid = '%s.%s' % (ns, e.get('name')) if e['tool'] == 'CallDynamicTool' else e['tool']
            flat = json.dumps(inp, sort_keys=True)
            where = '%s at %s' % (tid, e.get('at'))
            if e['tool'] == 'CallDynamicTool' and ns != 'cursor':
                reasons.append('connector or non-cursor namespace call: %s' % where)
                continue
            if [g for g in guard if g in flat] or KEY_NAME.search(flat):
                reasons.append('read of the key, keys/ or a store: %s' % where)
                continue
            if e.get('first_run'):
                if tid != 'Read':
                    reasons.append('first-run turn holds more than reads: %s' % where)
                continue
            if tid in NEVER:
                reasons.append('off-list tool: %s' % where)
            elif tid in EVERY:
                if not self.every_ok(tid, inp):
                    reasons.append('off-list use of %s' % where)
            else:
                w = [x for x in wins if at and x[0] and x[1] and x[0] <= at <= x[1]]
                if not w:
                    reasons.append('tool call with no action file: %s' % where)
                elif tid not in w[0][2]['allowed_tools'] or tid not in w[0][3].get('tools_called', []):
                    reasons.append('off-list tool: %s' % where)
                elif not self.payload_ok(w[0][2], inp):
                    reasons.append('payload sha differs from the intent: %s' % where)
        return reasons

    def every_ok(self, tid, inp):
        """Shell only runs kit/qualify.py, sha256sum or writes a receipt; Read stays in the run dir and suite."""
        if tid == 'Shell':
            return bool(SHELL_OK.match(str(inp.get('command', '')).strip()))
        p = os.path.abspath(str(inp.get('path', '')))
        return any(p == r or p.startswith(r + os.sep) for r in (self.dir, self.suite) if r)

    def payload_ok(self, intent, inp):
        target = inp.get('target', intent['target'])
        if target != intent['target']:
            return False
        text = inp.get('message', inp.get('instructions'))
        if text is None or not intent['payload_path']:
            return True
        return text_sha(str(text).encode()) == text_sha(read_bytes(intent['payload_path']))

    def s6(self):
        self.stage, R = 'S6', self.req
        body = render('S6.request.md', ver=R['ver'], cases=json.dumps(self.results, indent=1, sort_keys=True),
                      audit=self.audit_result,
                      audit_path=os.path.relpath(self.audit_path, self.dir), audit_sha=file_sha(self.audit_path))
        sent = self.send_seat('evaluator', 'S6.request', body)
        reply, _ = self.await_(R['seats']['evaluator'], 'replies/S6.reply.md', sent, None)
        ev, text = self.p('replies', 'S6.reply.md'), reply.decode('utf-8', 'replace')
        scores = first_json(text)
        if scores is None:
            raise Stop('S6', 'the reply holds no scores.json object', ev, text)
        self.write_new('scores.json', json.dumps(scores, indent=1, sort_keys=True) + '\n')
        if scores.get('key_sha256') != self.key_sha:
            raise Stop('S6', 'scores.json key_sha256 differs from S2\'s', ev, text)
        per = scores.get('cases') if isinstance(scores.get('cases'), dict) else {}
        self.verdicts = {}
        for c in self.cases:
            cid, r = c['id'], self.results.get(c['id'])
            v = (per.get(cid) or {}).get('verdict') if isinstance(per.get(cid), dict) else None
            v = v if v in VERDICTS and r else 'not_run'
            if r and r['deny_hits']:
                v = 'void'
            elif r and r['timeout'] and v != 'void':
                v = 'fail'
            elif r and r['side_effects_rc'] != 0 and v == 'pass':
                v = 'fail'
            self.verdicts[cid] = v

    def s7(self):
        self.stage, R = 'S7', self.req
        live = self.t.read_back(R['live_bot_id'], 'replies/live-after.txt')
        if text_sha(live) != R['live_sha256']:
            raise Stop('S7', 'the live bot\'s sha changed during the run', self.p('replies', 'live-after.txt'))
        self.check_leaks()
        qualified = pass_rule(self.verdicts, self.audit_result)
        counts = {k: list(self.verdicts.values()).count(k) for k in VERDICTS + ('not_run',)}
        dev = [x for r in self.results.values() for x in r['deny_hits']] + [
            '%s timeout' % k for k, r in sorted(self.results.items()) if r['timeout']]
        if self.audit_result != 'clean':
            dev.append('runner audit void (runner-audit.txt)')
        summary = self.once('S7-summary', lambda: {
            'ver': R['ver'], 'batch': os.path.basename(self.dir), 'candidate_sha256': R['candidate_sha256'],
            'live_sha256_before': R['live_sha256'], 'live_sha256_after': text_sha(live),
            'manifest_sha256': self.manifest_sha, 'key_sha256': self.key_sha, 'pins': R['pins'],
            'seed': self.order['seed'], 'order': self.order['order'],
            'subjects': {k: {'name': v[0], 'bot_id': v[1]} for k, v in self.subjects.items()},
            'cases': self.results, 'verdicts': self.verdicts, 'counts': counts, 'deviations': dev,
            'owner_authorization': R['owner_authorization'],
            'runner': {'bot_id': R['runner']['bot_id'], 'instructions_sha256': R['runner']['instructions_sha256']},
            'runner_audit': self.audit_result, 'qualified': qualified, 'tmpdir': self.tmp['tmpdir'],
            'tmp_entries_before': self.tmp['tmp_entries_before'], 'tmp_entries_after': tmp_entries(),
            'ended_at': iso(self.clock())})
        path = self.write_new('summary.json', json.dumps(summary, indent=1, sort_keys=True) + '\n')
        self.log('done', payload_sha=file_sha(path), qualified=qualified)
        bad = sha_check(write_sums(self.dir))
        if bad:
            raise Stop('S7', 'SHA256SUMS does not check: %s' % '; '.join(bad), self.p('SHA256SUMS'))
        return path

    def write_stop(self, s):
        """STOP.md: stage, failing check, evidence path and sha, what was not done; seat words verbatim."""
        ev = s.evidence
        sha = file_sha(ev) if ev and os.path.isfile(ev) else None
        rest = STAGES[STAGES.index(s.stage) + 1:] if s.stage in STAGES else []
        lines = ['# STOP: plumbline qualify %s, %s\n\n' % (getattr(self, 'req', {}).get('ver', '?'),
                                                         os.path.basename(self.dir)),
                 '- Stage: %s\n' % s.stage, '- Failing check: %s\n' % s.check,
                 '- Evidence: %s (sha256 %s)\n' % (ev, sha),
                 '- Not done: the rest of %s; %s; no summary.json, no SHA256SUMS; no qualification\n' % (
                     s.stage, ', '.join(rest) or 'nothing else'),
                 '- Written: %s\n' % iso(self.clock())]
        if s.quote is not None:
            lines.append('\nSeat words, verbatim (%s, sha256 %s):\n\n````\n%s\n````\n' % (ev, sha, s.quote))
        path = self.write_new('STOP.md', ''.join(lines))
        self.log('stop', payload_sha=file_sha(path), key='stop', check=s.check)
        return path


def pass_rule(verdicts, runner_audit):
    """qualified = all cases pass and void == 0 and not_run == 0 and runner_audit == clean (SPEC L155)."""
    v = list(verdicts.values())
    return bool(v) and all(x == 'pass' for x in v) and v.count('void') == 0 and v.count('not_run') == 0 \
        and runner_audit == 'clean'


def next_action(run_dir, **seams):
    """('ACTION', intent path) | ('REJECTED', text) | ('STOP', STOP.md) | ('DONE', summary.json)."""
    run = Run(run_dir, **seams)
    if os.path.exists(run.p('STOP.md')):
        return 'STOP', run.p('STOP.md')
    if os.path.exists(run.p('SHA256SUMS')):
        return 'DONE', run.p('summary.json')
    try:
        return 'DONE', run.procedure()
    except Wait as w:
        return w.word, w.text
    except Stop as s:
        return 'STOP', run.write_stop(s)


def verify_action(run_dir, n, clock=now_local):
    """(True, 'VERIFIED NNNN') or (False, 'REJECTED NNNN: why')."""
    run = Run(run_dir, clock=clock)
    ip = run.p('actions', n + '.intent.json')
    rs = run.receipts(n)
    if not (os.path.exists(ip) and rs):
        return False, 'REJECTED %s: no intent or no receipt' % n
    intent = load_json(ip)
    run.stage = 'verify'
    problem, fatal, _ = check_receipt(run, n, intent, rs[-1], len(rs))
    rel = os.path.relpath(rs[-1], run.dir)
    run.log('verified' if not problem else 'rejected', n, key=('verified ' if not problem else 'rejected ') + rel,
            reason=problem)
    return (False, 'REJECTED %s: %s%s' % (n, problem, ' (a runner deviation: the next step stops)' if fatal
                                          else '')) if problem else (True, 'VERIFIED %s' % n)


def kickoff(run_dir):
    rq = os.path.join(os.path.abspath(run_dir), 'request.json')
    o = load_json(rq)['owner_authorization']
    return render('kickoff.md', run=os.path.abspath(run_dir), request_sha=file_sha(rq), quote=o['quote'],
                  time=o['time'], msg_id=o['message_id'])


def runner_stop(run_dir, reason):
    run = Run(run_dir)
    if os.path.exists(run.p('STOP.md')):
        return run.p('STOP.md')
    stage = 'S0'
    if os.path.exists(run.p('log.jsonl')):
        with open(run.p('log.jsonl'), encoding='utf-8') as fh:
            stage = ([json.loads(x)['stage'] for x in fh if x.strip()] or ['S0'])[-1]
    run.stage = stage
    return run.write_stop(Stop(stage, 'the runner reports: %s' % reason))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('next', 'verify', 'kickoff', 'stop'):
        s = sub.add_parser(name)
        s.add_argument('run')
        if name == 'verify':
            s.add_argument('action', type=lambda x: '%04d' % int(x))
        if name == 'stop':
            s.add_argument('reason')
    a = ap.parse_args(argv)
    if a.cmd == 'kickoff':
        print(kickoff(a.run), end='')
        return 0
    if a.cmd == 'stop':
        print('STOP %s' % runner_stop(a.run, a.reason))
        return 3
    if a.cmd == 'verify':
        ok, text = verify_action(a.run, a.action)
        print(text)
        return 0 if ok else 4
    tmp = os.path.join(os.path.abspath(a.run), '.tmp')
    os.makedirs(tmp, exist_ok=True)
    os.environ.update(TMPDIR=tmp, TMP=tmp, TEMP=tmp)
    word, text = next_action(a.run)
    print(text if word == 'ACTION' else '%s %s' % (word, text))
    return {'ACTION': 0, 'DONE': 0, 'STOP': 3, 'REJECTED': 4}[word]


if __name__ == '__main__':
    sys.exit(main())
