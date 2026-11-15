#!/usr/bin/env python3
"""Script-driven Orchestrator qualification: the deterministic part of SPEC v2 (docs/QUALIFY.md).

Usage (cwd = the kit folder, the repo root the kickoff names; <run> is runs/<ver>/<date>-runN/ holding request.json):
  python3 kit/qualify.py next <run>            print the next action file, or STOP <file>, or DONE <file>
  python3 kit/qualify.py verify <run> NNNN     verify the runner's receipt for action NNNN
  python3 kit/qualify.py kickoff <run>         print the conduit's fixed kickoff for the run (names the kit folder
                                               and the commit it is checked out at)
  python3 kit/qualify.py stop <run> <reason>   record a stop the runner saw (an error, an ambiguity, or a
                                               message or instruction that is not in an action file)
  python3 kit/qualify.py resume <run> --ruling <file>
                                               resume after an Owner ruling on STOP.md: the ruling file is JSON
                                               {quote, time, message_id, channel, stop_sha256}; STOP.md becomes
                                               STOP-NN.md, the ruling is kept as rulings/ruling-NN.json, and the
                                               conduit's fixed resume message is printed. A stalled action (an intent
                                               with no receipt) is re-issued as NNNN.intent.K.json carrying the ruling;
                                               a script check is re-run and stops again if it still fails
  python3 kit/qualify.py readback <run> NNNN   perform read_back_sha action NNNN: copy the "description" of
                                               <AGENTS_ROOT>/<target>/profile.json verbatim to its reply_to and
                                               print READBACK <reply_to> sha256 <file sha> text_sha256 <text sha>
  python3 kit/qualify.py trace <run> NNNN <page>... [--incomplete]
                                               perform export_trace action NNNN from ReadTranscript result files
                                               (write_to_file): print MORE NNNN before=<position> until the pages
                                               reach the start of the transcript, then write the export to its
                                               reply_to and print TRACE <reply_to> sha256 <sha>
  python3 kit/qualify.py save <run> NNNN       await_reply: write stdin verbatim to the intent's reply_to; print
                                               SAVED <reply_to> sha256 <sha>
  python3 kit/qualify.py wait <run> NNNN       sleep (at most WAIT_CAP_S per call) until the intent's not_before;
                                               print READY NNNN, or WAIT NNNN <seconds> (run it again)
  python3 kit/qualify.py now                   print the box time with its zone (for done_at, sent_at, created_at)

The runner loops: `next`, perform exactly that action, write actions/NNNN.receipt.json, `verify`. The script
does the rest: hashing, the S0-S7 sequence, clocks from platform timestamps, the log, fixture reset,
side-effect checks, the deny-list, leak and runner-audit scans, the record and the pass rule. It makes no
model call and messages no one; its one network act is the S0 pin check, behind the `pins` seam.

Exit: 0 an action file or DONE; 3 STOP; 4 a receipt was rejected (write NNNN.receipt.2.json naming the one it
supersedes; a second failure stops); 2 usage.

readback exits 0 on success (an existing reply_to with identical bytes is a no-op success that reprints the line),
and refuses, writing no reply file and changing none, with:
  1. exit 2 (usage, prints REFUSED; the run goes on): there is no intent NNNN, or its kind is not read_back_sha;
  2. exit 3 (STOP.md): target is not a canonical lowercase UUID (this blocks path traversal);
  3. exit 3 (STOP.md): target is neither request.json live_bot_id nor the bot_id of a create_subject action in
     this run whose latest receipt passes verification;
  4. exit 3 (STOP.md): the profile path falls under a request.json deny_paths entry;
  5. exit 3 (STOP.md): profile.json is missing or not JSON, or "description" is missing or not a string;
  6. exit 3 (STOP.md): reply_to (or the script record steps/readback-NNNN.json) already exists with other content.
On a run that has already stopped it prints STOP <file> and exits 3.
"""
import argparse, datetime, hashlib, json, os, random, re, string, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, 'qualify', 'templates')
STAGES = ['S0', 'S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7']
REQUIRED = ['ver', 'candidate_path', 'candidate_sha256', 'live_bot_id', 'live_sha256', 'prior_suite',
            'changes', 'pins', 'owner_authorization', 'runner', 'seats']
DEFAULTS = {'pass_rule': 'all', 'case_window_minutes': 15, 'deny_paths': [], 'known_defects': []}
AGENTS_ROOT = '/home/box/agent-data/agents'  # bot profiles; only tests override it, by patching this attribute
EVERY = ['Shell', 'Read', 'GetDynamicTools']
ALLOWED = {
    'create_subject': ['cursor.CreateAgent'],  # instructions only (Owner ruling 2026-11-15 15:50 EST): name + description
    'read_back_sha': [],
    'send_seat': ['cursor.SendToAgent'],
    'send_subject': ['cursor.SendToAgent'],
    'await_reply': [],
    'export_trace': ['cursor.ReadTranscript'],
}
NEVER = {'WebSearch', 'WebFetch', 'UpdateMemory', 'UpdateRoutine', 'UpdateSkill', 'UpdateProfile', 'Task',
         'CreateChannel', 'Vault', 'FillCredential'}
FIRST_RUN_OK = ('Read', 'SendToUser')  # the platform's first-run cue asks a new bot to greet the user
DYNAMIC_NAMES = ('CreateAgent', 'SendToAgent', 'ReadTranscript')  # the only schemas GetDynamicTools may look up
RECEIPT_FIELDS = ['action_id', 'done_at', 'platform_ids', 'reply_verbatim_path', 'reply_sha256',
                  'tools_called', 'sent_unedited']
PLATFORM_IDS = {'create_subject': ['bot_id', 'created_at'], 'send_seat': ['sent_at'], 'send_subject': ['sent_at']}
REPLY_REQUIRED = ('read_back_sha', 'export_trace')
KEY_NAME = re.compile(r'(?<![\w.-])(keys/|KEY(?:[._-][\w.-]*)?(?!\w))')
SHA64 = re.compile(r'\b[0-9a-f]{64}\b')
# The runner's Shell forms, matched against the command's first line in full (a heredoc body follows it): one
# command per call, no chaining. kit/qualify.py with plain or quoted arguments (and a heredoc for `save`),
# sha256sum, or a receipt written with cat and a heredoc.
_ARG = r"""(?:"[^"\n]*"|'[^'\n]*'|[^\s;&|`$<>'"]+)"""
SHELL_OK = re.compile(r"(?:cd [^\s;&|`$<>]+ && )?python3? (?:\S*/)?kit/qualify\.py [a-z]+(?: %s)*(?: <<'?EOF'?)?"
                      r"|sha256sum(?: [^\s;&|`$<>]+)+"
                      r"|cat > [^\s;&|`$<>]*actions/\d{4}\.receipt(?:\.2)?\.json <<'?EOF'?" % _ARG)
SILENT_ARCHITECT_MIN = 24 * 60
FIRST_TURN_MIN = 10
POLL_MIN = 2  # S5: a case's subject transcript is exported every POLL_MIN minutes until a reply or the deadline
DEADLINE_SLACK_S = 60  # a reply counts as on time when an export done within this of the deadline shows it
WAIT_CAP_S = 600  # one `wait` call sleeps at most this; the Shell tool's foreground limit is 780 s
# ReadTranscript (real tool, 2026-11-15): pages of at most 200 messages (and about 45 KB), newest first, paged
# with `before`; a tool input or result over about 4000 characters is shown as its first and last ~2000 with
# "..." between; the oldest page ends with START_FOOTER. write_to_file saves a page as <sha256 of its bytes>.txt.
TRANSCRIPT_HEAD = re.compile(r'^Transcript of (?:agent "(?P<name>.*)" \((?P<id>[^)\s]+)\)|(?P<session>this session)), '
                             r'positions (?P<a>\d+)\s*[\u2013-]\s*(?P<b>\d+) of (?P<n>\d+):\s*$', re.M)
START_FOOTER = 'This is the start of the transcript.'
STAMP = re.compile(r'<timestamp>\w+, (\w+ \d+, \d{4}), (\d+:\d+ [AP]M) \(UTC([+-]\d+)(?::(\d+))?\)</timestamp>')
BOT_UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
READBACK_EXIT = {1: 2, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3}  # refusal case -> exit code (2 usage, 3 STOP)
PLATFORM = 'platform'  # check_receipt's fatal value for a fresh-read mismatch: a platform change, not the runner
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


def git_head(root=None):
    """(HEAD sha or None, dirty) of the kit checkout holding this script; dirty = tracked kit/ files changed."""
    root = root or os.path.dirname(HERE)
    try:
        r = subprocess.run(['git', '-C', root, 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=60)
        d = subprocess.run(['git', '-C', root, 'status', '--porcelain', '--untracked-files=no', '--', 'kit'],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None, True
    return (r.stdout.strip() or None) if r.returncode == 0 else None, d.returncode != 0 or bool(d.stdout.strip())


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

    def create_subject(self, name, payload_path):
        raise NotImplementedError

    def read_back(self, bot_id, reply_to):
        raise NotImplementedError

    def send(self, kind, target, payload_path):
        raise NotImplementedError

    def await_reply(self, target, reply_to):
        raise NotImplementedError

    def export_trace(self, bot_id, reply_to, not_before=None):
        raise NotImplementedError


class RunnerTransport(Transport):
    """Each act is an intent file the runner performs; its result is the runner's verified receipt."""

    def __init__(self, run):
        self.run = run

    def create_subject(self, name, payload_path):
        ids = self._act('create_subject', name, payload_path)['platform_ids']
        return ids['bot_id'], parse_time(ids['created_at'])

    def read_back(self, bot_id, reply_to):
        return self._act('read_back_sha', bot_id, reply_to=reply_to)['reply']

    def send(self, kind, target, payload_path):
        return parse_time(self._act(kind, target, payload_path)['platform_ids']['sent_at'])

    def await_reply(self, target, reply_to):
        r = self._act('await_reply', target, reply_to=reply_to)
        return r['reply'], parse_time(r['platform_ids'].get('reply_at')), parse_time(r['done_at'])

    def export_trace(self, bot_id, reply_to, not_before=None):
        r = self._act('export_trace', bot_id, reply_to=reply_to, not_before=not_before)
        return r['reply'], parse_time(r['done_at'])

    def _act(self, kind, target, payload_path=None, reply_to=None, not_before=None):
        run = self.run
        run.n += 1
        n = '%04d' % run.n
        intent = {'kind': kind, 'target': target, 'payload_path': payload_path,
                  'payload_sha256': file_sha(payload_path) if payload_path else None,
                  'allowed_tools': EVERY + ALLOWED[kind]}
        if reply_to:
            intent['reply_to'] = reply_to
        if not_before:
            intent['not_before'] = iso(not_before)
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
            again = run.reissue(n, intent)
            if again:
                raise Wait('ACTION', again)
            raise Stop(run.stage, 'intent %s has no receipt: never resend blind; ask Steve' % n, run.intent_path(n))
        rp = receipts[-1]
        problem, fatal, rec = check_receipt(run, n, intent, rp, len(receipts))
        rel = os.path.relpath(rp, run.dir)
        if not problem:
            run.log('verified', n, key='verified ' + rel)
            return rec
        if fatal == PLATFORM:
            raise Stop(run.stage, 'action %s: %s' % (n, problem), rp)
        if fatal:
            raise Stop(run.stage, 'runner deviation in action %s: %s' % (n, problem), rp)
        run.log('rejected', n, key='rejected ' + rel, reason=problem)
        if len(receipts) >= 2:
            raise Stop(run.stage, 'receipt for action %s failed verification twice: %s' % (n, problem), rp)
        raise Wait('REJECTED', '%s %s; write actions/%s.receipt.2.json with "supersedes": "%s"'
                   % (n, problem, n, os.path.basename(rp)))


def check_receipt(run, n, intent, path, count):
    """Returns (problem or None, fatal, receipt with 'reply' bytes). A fatal problem is a runner deviation, except
    fatal == PLATFORM: verify's fresh read of profile.json found the bot's instructions changed on the platform."""
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
        if intent['kind'] == 'read_back_sha':
            problem, fatal = readback_cross_check(run, n, intent, reply)
            if problem:
                return problem, fatal, None
        if intent['kind'] == 'export_trace':
            problem = trace_cross_check(run, n, intent, reply)
            if problem:
                return problem, True, None
    return None, False, dict(r, reply=reply, platform_ids=ids)


def readback_cross_check(run, n, intent, reply):
    """A read_back_sha reply must be what `qualify.py readback` wrote: its record steps/readback-NNNN.json names
    the intent's target and the reply's sha256. Reads no agent-data, so a replay never depends on today's
    profile.json. A recorded fresh-read mismatch (verify) stays fatal on every replay."""
    rec_path = run.p('steps', 'readback-%s.json' % n)
    if not os.path.isfile(rec_path):
        return ('no script record steps/readback-%s.json: the reply was not written by qualify.py readback'
                % n), True
    try:
        rec = load_json(rec_path)
    except (OSError, ValueError):
        rec = None
    if not isinstance(rec, dict):
        return 'the script record steps/readback-%s.json is not a JSON object' % n, True
    if rec.get('target') != intent['target']:
        return 'the script record steps/readback-%s.json names target %r, not %r' % (
            n, rec.get('target'), intent['target']), True
    if rec.get('description_sha256') != sha256(reply):
        return ('the reply (sha256 %s) is not what qualify.py readback wrote (sha256 %s): hand-written or edited'
                % (sha256(reply), rec.get('description_sha256'))), True
    fresh = run.p('steps', 'readback-%s.fresh.json' % n)
    if os.path.isfile(fresh):
        try:
            why = load_json(fresh).get('reason')
        except (OSError, ValueError, AttributeError):
            why = None
        return why or 'the fresh read of profile.json at verify did not match the reply', PLATFORM
    return None, False


def trace_cross_check(run, n, intent, reply):
    """An export_trace reply must be what `qualify.py trace` wrote from ReadTranscript result files."""
    try:
        rec = load_json(run.p('steps', 'trace-%s.json' % n))
    except (OSError, ValueError):
        return 'no script record steps/trace-%s.json: the export was not written by qualify.py trace' % n
    if not isinstance(rec, dict) or rec.get('target') != intent['target']:
        return 'the script record steps/trace-%s.json does not name target %s' % (n, intent['target'])
    if rec.get('export_sha256') != sha256(reply):
        return 'the export (sha256 %s) is not what qualify.py trace wrote (sha256 %s): hand-written or edited' % (
            sha256(reply), rec.get('export_sha256'))
    return None


class Refusal(Exception):
    """A readback refusal: case 1-6 of the readback spec (docs/QUALIFY.md item 16)."""

    def __init__(self, case, text):
        super().__init__(text)
        self.case, self.text = case, text


def readback_allowed(run, req):
    """live_bot_id plus the bot_id of each create_subject action whose latest receipt passes check_receipt,
    derived from actions/*.intent.json and their receipts (never from the log)."""
    ok = {req.get('live_bot_id')}
    d = run.p('actions')
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        m = re.fullmatch(r'(\d{4})\.intent\.json', name)
        if not m:
            continue
        try:
            it = load_json(os.path.join(d, name))
            if not (isinstance(it, dict) and it.get('kind') == 'create_subject'):
                continue
            rs = run.receipts(m.group(1))
            if not rs:
                continue
            problem, _, rec = check_receipt(run, m.group(1), it, rs[-1], len(rs))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        if not problem:
            ok.add(rec['platform_ids'].get('bot_id'))
    return ok


def under(path, root):
    root = os.path.normpath(root) if root else ''
    return bool(root) and (path == root or path.startswith(root.rstrip(os.sep) + os.sep))


def readback_profile(run, intent, req):
    """The profile.json path of an allowed readback target (refusals 2, 3 and 4)."""
    target = intent.get('target')
    if not (isinstance(target, str) and BOT_UUID.fullmatch(target)):
        raise Refusal(2, 'target %r is not a canonical lowercase UUID' % (target,))
    if target not in readback_allowed(run, req):
        raise Refusal(3, 'target %s is neither live_bot_id nor a verified create_subject bot_id of this run'
                      % target)
    path = os.path.join(AGENTS_ROOT, target, 'profile.json')
    seen = {os.path.abspath(path), os.path.realpath(path)}
    deny = [x for x in req.get('deny_paths') or [] if isinstance(x, str) and x]
    hit = [x for x in deny for p in seen if under(p, os.path.abspath(x))]
    if hit:
        raise Refusal(4, 'profile path %s falls under deny_paths entry %s' % (path, hit[0]))
    return path


def readback_description(path):
    """The "description" string of a profile.json, as UTF-8 bytes (refusal 5)."""
    try:
        prof = json.loads(read_bytes(path).decode('utf-8'))
    except FileNotFoundError:
        raise Refusal(5, '%s is missing' % path)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise Refusal(5, '%s is not JSON: %s' % (path, e))
    desc = prof.get('description') if isinstance(prof, dict) else None
    if not isinstance(desc, str):
        raise Refusal(5, '%s has no "description" string' % path)
    try:
        return desc.encode('utf-8')
    except UnicodeEncodeError as e:
        raise Refusal(5, '%s "description" is not encodable as UTF-8: %s' % (path, e))


def last_stage(run):
    stage = 'S0'
    if os.path.exists(run.p('log.jsonl')):
        with open(run.p('log.jsonl'), encoding='utf-8') as fh:
            stage = ([json.loads(x)['stage'] for x in fh if x.strip()] or ['S0'])[-1]
    return stage


def readback(run_dir, n, clock=now_local):
    """Perform read_back_sha action NNNN (exit code, printed line). Writes the reply verbatim (UTF-8, no added
    newline) and the once-only record steps/readback-NNNN.json; never writes an intent or advances the stage.
    Refusal cases and their exit codes are in the module docstring (READBACK_EXIT)."""
    run = Run(run_dir, clock=clock)
    if os.path.exists(run.p('STOP.md')):
        return 3, 'STOP %s' % run.p('STOP.md')
    ip = run.p('actions', n + '.intent.json')
    try:
        intent = load_json(ip) if os.path.isfile(ip) else None
        if not isinstance(intent, dict):
            raise Refusal(1, 'there is no intent %s' % n)
        if intent.get('kind') != 'read_back_sha' or not isinstance(intent.get('reply_to'), str):
            raise Refusal(1, 'action %s is a %r action, not read_back_sha' % (n, intent.get('kind')))
        try:
            req = load_json(run.p('request.json'))
        except (OSError, ValueError):
            req = None
        if not isinstance(req, dict):
            raise Refusal(3, 'request.json is unreadable, so no readback target is allowed')
        run.req = req
        path = readback_profile(run, intent, req)
        data = readback_description(path)
        rp = intent['reply_to']
        full = rp if os.path.isabs(rp) else run.p(rp)
        rec_path = run.p('steps', 'readback-%s.json' % n)
        if os.path.exists(full) and read_bytes(full) != data:
            raise Refusal(6, 'reply_to %s already exists with other bytes' % rp)
        if os.path.exists(rec_path):
            try:
                old = load_json(rec_path)
            except (OSError, ValueError):
                old = None
            if not (isinstance(old, dict) and old.get('target') == intent['target']
                    and old.get('description_sha256') == sha256(data)):
                raise Refusal(6, 'the script record steps/readback-%s.json already exists with other content' % n)
    except Refusal as e:
        if READBACK_EXIT[e.case] == 2:
            return 2, 'REFUSED %s: %s' % (n, e.text)
        run.stage = last_stage(run)
        return 3, 'STOP %s' % run.write_stop(Stop(run.stage, 'readback %s refused (case %d): %s'
                                                  % (n, e.case, e.text), ip))
    if not os.path.exists(full):
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full + '.part', 'wb') as fh:
            fh.write(data)
        os.replace(full + '.part', full)
    run.write_new(rec_path, json.dumps({'action': n, 'target': intent['target'], 'profile_path': path,
                                        'description_sha256': sha256(data), 'read_at': iso(clock())},
                                       indent=1, sort_keys=True) + '\n')
    run.stage = last_stage(run)
    run.log('readback', n, sha256(data), key='readback %s' % n, target=intent['target'])
    return 0, 'READBACK %s sha256 %s text_sha256 %s' % (rp, sha256(data), text_sha(data))


def fresh_read(run, n, intent):
    """verify only: read profile.json again (same target rules) and require its description's sha256 to be the
    reply's. A mismatch is recorded once (steps/readback-NNNN.fresh.json) so every later replay stops."""
    rp = intent['reply_to']
    reply = read_bytes(rp if os.path.isabs(rp) else run.p(rp))
    desc_sha, path = None, None
    try:
        req = load_json(run.p('request.json'))
        if not isinstance(req, dict):
            raise Refusal(3, 'request.json is not a JSON object')
        path = readback_profile(run, intent, req)
        desc_sha = sha256(readback_description(path))
        why = None if desc_sha == sha256(reply) else 'its description now has sha256 %s' % desc_sha
    except (OSError, ValueError) as e:
        why = 'request.json is unreadable (%s)' % e
    except Refusal as e:
        why = 'the fresh read failed (%s)' % e.text
    if why is None:
        return None, False
    reason = ('fresh read at verify: the profile.json of bot %s no longer matches reply %s (sha256 %s): %s. '
              'The bot\'s instructions changed on the platform after qualify.py readback ran; this is a platform '
              'change, not a runner deviation' % (intent['target'], rp, sha256(reply), why))
    run.write_new(run.p('steps', 'readback-%s.fresh.json' % n), json.dumps({
        'action': n, 'target': intent['target'], 'profile_path': path, 'description_sha256': desc_sha,
        'reply_sha256': sha256(reply), 'read_at': iso(run.clock()), 'reason': reason}, indent=1, sort_keys=True)
        + '\n')
    return reason, PLATFORM


class Run:
    """One qualification run, replayed from its append-only record on every command."""

    def __init__(self, path, clock=now_local, tool=run_tool, pins=git_pin, head=git_head):
        self.dir = os.path.abspath(path)
        self.clock, self.tool_fn, self.pins, self.head = clock, tool, pins, head
        self.t = RunnerTransport(self)
        self.n, self.stage, self.suite = 0, 'S0', None
        self.keys, self.created = set(), {}
        lp = self.p('log.jsonl')
        if os.path.exists(lp):
            with open(lp, encoding='utf-8') as fh:
                self.keys = {json.loads(x).get('key') for x in fh if x.strip()}

    def p(self, *parts):
        return os.path.join(self.dir, *parts)

    def intent_path(self, n):
        """The intent now in force for action n: NNNN.intent.json, or the latest NNNN.intent.K.json re-issue."""
        path, k = self.p('actions', n + '.intent.json'), 2
        while os.path.exists(self.p('actions', '%s.intent.%d.json' % (n, k))):
            path, k = self.p('actions', '%s.intent.%d.json' % (n, k)), k + 1
        return path

    def rulings(self):
        d = self.p('rulings')
        return [load_json(os.path.join(d, x)) for x in sorted(os.listdir(d))
                if re.fullmatch(r'ruling-\d{2}\.json', x)] if os.path.isdir(d) else []

    def reissue(self, n, intent):
        """After `resume`, a stalled action (intent, no receipt) is issued again once per ruling that names it, as
        NNNN.intent.K.json carrying the ruling: the runner performs it with Steve's words in hand."""
        rulings = [r for r in self.rulings() if r.get('action') == n]
        latest = self.intent_path(n)
        k = 1 if latest.endswith('.intent.json') else int(latest.rsplit('.', 2)[-2])
        if len(rulings) < k:
            return None
        r = rulings[k - 1]
        path = self.p('actions', '%s.intent.%d.json' % (n, k + 1))
        self.write_new(path, json.dumps(dict(intent, supersedes=os.path.basename(latest), ruling={
            x: r.get(x) for x in ('quote', 'time', 'message_id', 'channel', 'stop_sha256', 'stop_file')}),
            indent=1) + '\n')
        self.log('reissued', n, intent['payload_sha256'], key='reissued %s %d' % (n, k + 1),
                 intent=os.path.basename(path))
        return path

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
        if 'plumbline' in R['pins']:
            head = self.once('S0-head', lambda: dict(zip(('sha', 'dirty'), self.head())))
            want = R['pins']['plumbline']['sha']
            if not (head['sha'] or '').startswith(want) or head['dirty']:
                raise Stop('S0', 'this kit checkout (%s) is at %s%s, not the pinned plumbline %s' % (
                    os.path.dirname(HERE), head['sha'], ' with changed kit/ files' if head['dirty'] else '', want),
                    self.p('steps', 'S0-head.json'))
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
        bot, at = self.t.create_subject(name, self.req['candidate_path'])
        self.created[bot] = at
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
        return self.trace_at(bot, rel)[0]

    def trace_at(self, bot, rel, not_before=None):
        data, done = self.t.export_trace(bot, rel, not_before)
        try:
            tr = json.loads(data.decode('utf-8'))
            tr['events'] = [e for e in tr['events'] if isinstance(e, dict)]
        except (ValueError, KeyError, TypeError, AttributeError):
            tr = None
        return tr, done

    def deny_patterns(self, case):
        own = os.path.dirname(os.path.join(self.suite, case['prompt_path']))
        others = {os.path.dirname(os.path.join(self.suite, c['prompt_path'])) for c in self.cases} - {own}
        return list(self.req['deny_paths']) + [os.path.join(self.suite, 'tools') + '/', 'qualify-script/run/',
                                               self.p('actions') + '/'] + [d + '/' for d in sorted(others)]

    def deny_hits(self, tr, case, first_run_only):
        """Scan tool-call inputs and prose against the fixed deny list (SPEC L112-118)."""
        pats, hits = self.deny_patterns(case), []
        for e in tr['events']:
            if first_run_only and not e.get('first_run') or e.get('role') == 'user':
                continue
            text = json.dumps(e.get('input', ''), sort_keys=True) + ' ' + str(e.get('text', ''))
            found = [x for x in pats if x in text] + (['keys/ or a KEY file'] if KEY_NAME.search(text) else [])
            hits += ['%s at %s' % (x, e.get('at')) for x in found]
        return hits

    def first_run(self, bot, base):
        """Export until a receipt's done_at is 10 minutes past created_at (SPEC L110); return the last export.
        Each export carries not_before = created_at + 10 min, so the runner's `wait` makes one export enough."""
        limit, k = self.created[bot] + datetime.timedelta(minutes=FIRST_TURN_MIN), 0
        while True:
            k += 1
            rel = '%s.%d.json' % (base, k)
            tr, done = self.trace_at(bot, rel, limit)
            if tr is None or not tr.get('start_of_transcript'):
                raise Stop('S4', 'the export of %s is not complete (no start-of-transcript footer)' % bot,
                           self.p(rel))
            if done >= limit:
                self.log('first_run_scanned', key='first_run_scanned %s' % bot, bot_id=bot, file=rel)
                return tr, rel

    def s4(self):
        self.stage, retired = 'S4', False
        for i, c in enumerate(self.cases, 1):
            tries = 0
            while True:
                name, bot = self.subjects[c['id']]
                tr, rel = self.first_run(bot, 'replies/subject-%02d%s.first-run' % (i, '-r%d' % tries if tries else ''))
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
            reply, at, tr, trace_rel, elided, polls = self.poll(cid, bot, sent, deadline, rel)
            timeout = reply is None or at > deadline + datetime.timedelta(seconds=DEADLINE_SLACK_S)
            hits = self.deny_hits(tr, c, False)
            se = self.tool('S5-%s-side-effects' % cid, 'check_side_effects', [cid])
            sp = self.write_new('replies/%s.side-effects.txt' % cid, se['output'])
            self.results[cid] = {
                'subject': self.subjects[cid][0], 'bot_id': bot, 'sent_at': iso(sent), 'deadline': iso(deadline),
                'reply_at': iso(at) if at else None, 'timeout': timeout, 'deny_hits': hits,
                'reply_path': rel if reply is not None else None,
                'reply_sha256': sha256(reply) if reply is not None else None, 'reply_elided': elided,
                'trace_path': trace_rel, 'polls': polls,
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

    def poll(self, cid, bot, sent, deadline, rel):
        """S5: export the subject's transcript every POLL_MIN minutes (each export waits for its not_before) until
        it shows the subject's SendToAgent reply to the runner, or the export at the deadline is done. The reply
        is taken from the platform transcript by the script, never typed by the runner. Returns (reply bytes or
        None, the done_at of the export that first showed it, that export, its path, elided, polls)."""
        runner, k = self.req['runner']['bot_id'], 0
        while True:
            k += 1
            nb = min(sent + datetime.timedelta(minutes=POLL_MIN * k), deadline)
            trace_rel = 'replies/%s.trace.%d.json' % (cid, k)
            tr, done = self.trace_at(bot, trace_rel, nb)
            if tr is None or not tr.get('start_of_transcript'):
                raise Stop('S5', 'the export of %s is not complete (no start-of-transcript footer)' % bot,
                           self.p(trace_rel))
            got = subject_reply(tr, runner)
            if got is not None:
                text, elided = got
                write_once(self.p(rel), text.encode('utf-8'))
                self.log('reply_seen', key='reply_seen %s' % cid, case=cid, file=trace_rel, elided=elided)
                return read_bytes(self.p(rel)), done, tr, trace_rel, elided, k
            if nb >= deadline and done >= deadline:
                return None, None, tr, trace_rel, False, k

    def audit(self, tr):
        """The post-run runner audit (SPEC L228-242): every reason found voids the run. Calls are mapped to actions
        by transcript order (the platform gives no per-call time): an action opens when the runner Reads its intent
        file and closes when it runs `qualify.py verify <run> NNNN`."""
        if tr is None:
            return ['the runner transcript export is not a JSON transcript']
        reasons = [] if tr.get('start_of_transcript') else [
            'export lacks the start-of-transcript footer: not accepted as complete']
        guard, cur = list(self.req['deny_paths']), None
        for e in tr['events']:
            if 'tool' not in e:
                continue
            ns, inp = e.get('namespace'), e.get('input') or {}
            inp = inp if isinstance(inp, dict) else {'_elided': str(inp)}
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
                if tid not in FIRST_RUN_OK:
                    reasons.append('first-run turn holds more than reads: %s' % where)
                continue
            m = re.search(r'/actions/(\d{4})\.intent(?:\.\d+)?\.json$', str(inp.get('path', '')))
            if tid == 'Read' and m and under(os.path.abspath(inp['path']), self.dir):
                cur = m.group(1)
            if tid in NEVER:
                reasons.append('off-list tool: %s' % where)
            elif tid in EVERY:
                if not self.every_ok(tid, inp):
                    reasons.append('off-list use of %s' % where)
            elif tid == 'SendToUser':
                if cur is not None and not self.is_stop_report(inp):
                    reasons.append('SendToUser inside action %s: %s' % (cur, where))
            elif cur is None:
                reasons.append('tool call with no action file: %s' % where)
            else:
                intent, rs = load_json(self.intent_path(cur)), self.receipts(cur)
                called = load_json(rs[-1]).get('tools_called', []) if rs else []
                if tid not in intent['allowed_tools'] or tid not in called:
                    reasons.append('off-list tool: %s' % where)
                elif not self.payload_ok(intent, e.get('name'), inp):
                    reasons.append('payload sha differs from the intent: %s' % where)
            if tid == 'Shell' and cur and re.search(r'kit/qualify\.py (verify \S+ 0*%d\b|stop )' % int(cur),
                                                   str(inp.get('command', ''))):
                cur = None
        return reasons

    def is_stop_report(self, inp):
        """A SendToUser whose text is a STOP the run recorded (STOP-NN.md): the report a stop calls for."""
        text = next((inp[k] for k in ('content', 'text', 'message') if isinstance(inp.get(k), str)), None)
        if text is None:
            return False
        stops = [x for x in os.listdir(self.dir) if re.fullmatch(r'STOP(-\d{2})?\.md', x)]
        return any(text_sha(text.encode()) == text_sha(read_bytes(self.p(x))) for x in stops)

    def every_ok(self, tid, inp):
        """Shell runs only the SHELL_OK forms (first line, in full); Read stays in the run dir, the suite and the
        intents' payload files; GetDynamicTools looks up only the cursor tools an action may use."""
        if tid == 'Shell':
            first = str(inp.get('command', '')).strip().split('\n', 1)[0].strip()
            return bool(SHELL_OK.fullmatch(first))
        if tid == 'GetDynamicTools':
            return inp.get('namespace') == 'cursor' and inp.get('toolName') in DYNAMIC_NAMES
        p = os.path.abspath(str(inp.get('path', '')))
        return any(under(p, r) for r in (self.dir, self.suite) if r) or p in self.payload_paths()

    def payload_paths(self):
        d = self.p('actions')
        return {load_json(os.path.join(d, x)).get('payload_path') for x in sorted(os.listdir(d))
                if re.fullmatch(r'\d{4}\.intent(\.\d+)?\.json', x)} - {None} if os.path.isdir(d) else set()

    def payload_ok(self, intent, name, inp):
        """The call's target and text against the intent, in the real argument names (SendToAgent target_id and
        message, CreateAgent name and description, ReadTranscript in). An input the transcript shows elided
        (over ~4000 characters) is checked on what is shown: the target, and for a seat message its header line,
        which carries the body's sha256; a subject's instructions are proven by the S3 readback instead."""
        target = {'SendToAgent': 'target_id', 'CreateAgent': 'name', 'ReadTranscript': 'in'}.get(name)
        if target and target in inp and inp[target] != intent['target']:
            return False
        if name == 'ReadTranscript' and 'in' not in inp and '_elided' not in inp:
            return intent['target'] == self.req['runner']['bot_id']
        text = inp.get({'SendToAgent': 'message', 'CreateAgent': 'description'}.get(name, ''))
        if not intent['payload_path'] or name not in ('SendToAgent', 'CreateAgent'):
            return True
        payload = read_bytes(intent['payload_path'])
        if '_elided' in inp:
            if target and target not in inp:
                return False
            first = payload.decode('utf-8', 'replace').split('\n', 1)[0]
            return name == 'CreateAgent' or any(json.dumps(first, ensure_ascii=a)[1:-1] in inp['_elided']
                                                for a in (False, True))
        return text is not None and text_sha(str(text).encode()) == text_sha(payload)

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
        k = 1 + len([x for x in os.listdir(self.dir) if re.fullmatch(r'STOP-\d{2}\.md', x)])
        self.log('stop', payload_sha=file_sha(path), key='stop %02d' % k, check=s.check)
        return path


def write_once(path, data):
    """Write bytes once via .part; an existing file is never rewritten."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + '.part', 'wb') as fh:
            fh.write(data)
        os.replace(path + '.part', path)
    return path


def subject_reply(tr, runner):
    """A subject's reply: its first cursor SendToAgent call to the runner after its first-run turn, as
    (text, elided). None when the export shows no such call."""
    for e in tr['events']:
        if e.get('first_run') or e.get('tool') != 'CallDynamicTool':
            continue
        inp = e.get('input') if isinstance(e.get('input'), dict) else {}
        if e.get('namespace') == 'cursor' and e.get('name') == 'SendToAgent' and inp.get('target_id') == runner:
            if '_elided' in inp:
                raw = inp['_elided']
                i = raw.find('"message":"')
                return (raw[i + len('"message":"'):] if i >= 0 else raw), True
            return str(inp.get('message', '')), False
    return None


# ---- ReadTranscript result files -> the export (runner.md shape) ------------------------------------------------
class TraceError(Exception):
    pass


def parse_page(path):
    """One ReadTranscript result file (write_to_file): header, one JSON message per line, then the paging line or
    the start-of-transcript footer."""
    try:
        data = read_bytes(path)
    except OSError as e:
        raise TraceError('cannot read page %s: %s' % (path, e))
    if os.path.basename(path) != sha256(data) + '.txt':
        raise TraceError('page %s is not a ReadTranscript result file: its name is not the sha256 of its bytes'
                         % path)
    text = data.decode('utf-8', 'replace')
    m = TRANSCRIPT_HEAD.search(text)
    if not m:
        raise TraceError('page %s has no "Transcript of ..., positions A-B of N:" header' % path)
    msgs = []
    for line in text[m.end():].splitlines():
        line = line.strip()
        if line.startswith('{'):
            try:
                msgs.append(json.loads(line))
            except ValueError as e:
                raise TraceError('page %s holds a line that is not JSON: %s' % (path, e))
    a, b = int(m.group('a')), int(m.group('b'))
    if len(msgs) != b - a + 1:
        raise TraceError('page %s says positions %d-%d but holds %d messages' % (path, a, b, len(msgs)))
    return {'path': path, 'sha256': sha256(data), 'id': m.group('id'), 'name': m.group('name'),
            'session': bool(m.group('session')), 'a': a, 'b': b, 'of': int(m.group('n')), 'msgs': msgs,
            'start': START_FOOTER in text[m.end():]}


def stamp_time(text):
    m = STAMP.search(text)
    if not m:
        return None
    t = datetime.datetime.strptime('%s %s' % (m.group(1), m.group(2)), '%b %d, %Y %I:%M %p')
    off = datetime.timedelta(hours=int(m.group(3)), minutes=int(m.group(4) or 0) * (1 if int(m.group(3)) >= 0 else -1))
    return iso(t.replace(tzinfo=datetime.timezone(off)))


def _elided_fields(s):
    """The scalar fields still readable at the head of an elided tool input."""
    out = {'_elided': s}
    for k in ('namespace', 'toolName', 'target_id', 'name', 'in', 'agent_id', 'path', 'command'):
        m = re.search(r'"%s"\s*:\s*"((?:[^"\\]|\\.)*)"' % k, s)
        if not m:
            continue
        raw = m.group(1).split('\\n', 1)[0] if k == 'command' else m.group(1)
        try:
            out[k] = json.loads('"%s"' % raw)
        except ValueError:
            out[k] = raw
    return out


def is_elided(s):
    """ReadTranscript shows a tool input over ~4000 characters as a string: its first ~2000 characters, '...', its
    last ~2000. The cut can fall inside one string value, so the shortened text may still parse as JSON."""
    return isinstance(s, str) and len(s) >= 3900 and '...' in s[1990:2010]


def tool_event(c, at, first):
    inp = c.get('input')
    if isinstance(inp, str):
        try:
            inp = _elided_fields(inp) if is_elided(inp) else json.loads(inp)
        except ValueError:
            inp = _elided_fields(inp)
    inp = inp if isinstance(inp, dict) else {}
    e = {'at': at, 'first_run': first, 'tool': c.get('name')}
    if c.get('name') == 'CallDynamicTool':
        args = inp.get('arguments') if '_elided' not in inp else {
            k: v for k, v in inp.items() if k not in ('namespace', 'toolName')}
        if isinstance(args, str):
            try:
                args = _elided_fields(args) if is_elided(args) else json.loads(args)
            except ValueError:
                args = _elided_fields(args)
        e.update(namespace=inp.get('namespace'), name=inp.get('toolName'), input=args if isinstance(args, dict) else {})
    else:
        e['input'] = inp
    return e


def export_from_pages(pages, target):
    """Stitch pages (any order) into {"bot_id", "start_of_transcript", "events", ...}. Events are the assistant's
    prose and tool calls in transcript order; `at` is the platform timestamp of the turn (minute precision, the
    only time the platform shows); `first_run` marks the turn the platform's first-run cue opened."""
    by_pos = {}
    for pg in pages:
        for i, msg in enumerate(pg['msgs']):
            by_pos.setdefault(pg['a'] + i, msg)
    top = max(by_pos) if by_pos else 0
    contiguous = all(p in by_pos for p in range(1, top + 1))
    start = contiguous and any(pg['a'] == 1 and pg['start'] for pg in pages)
    events, at, first = [], None, False
    for pos in range(1, top + 1):
        msg = by_pos.get(pos)
        if not isinstance(msg, dict):
            continue
        body = msg.get('message')
        content = body.get('content') if isinstance(body, dict) else body
        content = [{'type': 'text', 'text': content}] if isinstance(content, str) else content or []
        if msg.get('role') == 'user':
            text = ' '.join(str(c.get('text', '')) for c in content if isinstance(c, dict))
            if '<user_query>' in text:
                at, first = stamp_time(text) or at, '][first run]' in text
            continue
        if msg.get('role') != 'assistant':
            continue
        for c in content:
            if isinstance(c, dict) and c.get('type') == 'text':
                events.append({'at': at, 'first_run': first, 'text': c.get('text', '')})
            elif isinstance(c, dict) and c.get('type') == 'tool_use':
                events.append(tool_event(c, at, first))
    return {'bot_id': target, 'start_of_transcript': bool(start), 'positions': [1 if by_pos else 0, top],
            'pages': sorted(pg['sha256'] for pg in pages), 'events': events}, contiguous and start, \
        min((pg['a'] for pg in pages), default=0)


def load_intent(run, n, kind):
    ip = run.intent_path(n)
    intent = load_json(ip) if os.path.isfile(ip) else None
    if not isinstance(intent, dict):
        raise Refusal(1, 'there is no intent %s' % n)
    if intent.get('kind') != kind or not isinstance(intent.get('reply_to'), str):
        raise Refusal(1, 'action %s is a %r action, not %s' % (n, intent.get('kind'), kind))
    return intent


def trace(run_dir, n, pages, incomplete=False, clock=now_local):
    """Perform export_trace action NNNN from ReadTranscript result files: (exit code, printed line)."""
    run = Run(run_dir, clock=clock)
    if os.path.exists(run.p('STOP.md')):
        return 3, 'STOP %s' % run.p('STOP.md')
    try:
        intent = load_intent(run, n, 'export_trace')
        req = load_json(run.p('request.json'))
        given = [parse_page(p) for p in pages]
        if not given:
            raise TraceError('no page files given')
        # pages given by earlier calls for this action are kept in steps/trace-NNNN.pages.jsonl (appended), so each
        # call names only the page just read and the Shell command stays short
        lp = run.p('steps', 'trace-%s.pages.jsonl' % n)
        known = [json.loads(x) for x in open(lp, encoding='utf-8')] if os.path.isfile(lp) else []
        parsed = [parse_page(k['path']) for k in known if os.path.isfile(k['path'])]
        if len(parsed) != len(known) or [pg['sha256'] for pg in parsed] != [k['sha256'] for k in known]:
            raise TraceError('a page named by an earlier trace call for action %s is gone or changed' % n)
        for pg in given:
            if pg['session'] and intent['target'] != req['runner']['bot_id']:
                raise TraceError('page %s is the runner\'s own session, not bot %s' % (pg['path'], intent['target']))
            if not pg['session'] and pg['id'] != intent['target']:
                raise TraceError('page %s is the transcript of %s, not %s' % (pg['path'], pg['id'], intent['target']))
        new = [pg for pg in given if pg['sha256'] not in {x['sha256'] for x in parsed}]
        if new:
            os.makedirs(run.p('steps'), exist_ok=True)
            with open(lp, 'a', encoding='utf-8') as fh:
                fh.writelines(json.dumps({'path': os.path.abspath(pg['path']), 'sha256': pg['sha256']}) + '\n'
                              for pg in new)
        parsed += new
        export, complete, low = export_from_pages(parsed, intent['target'])
        if not complete and not incomplete:
            return 0, 'MORE %s before=%d' % (n, low)
        data = (json.dumps(export, indent=1, sort_keys=True) + '\n').encode('utf-8')
        full = intent['reply_to'] if os.path.isabs(intent['reply_to']) else run.p(intent['reply_to'])
        if os.path.exists(full) and read_bytes(full) != data:
            raise TraceError('reply_to %s already exists with other bytes' % intent['reply_to'])
    except Refusal as e:
        return 2, 'REFUSED %s: %s' % (n, e.text)
    except (TraceError, OSError, ValueError, KeyError, TypeError) as e:
        return 2, 'REFUSED %s: %s' % (n, e)
    write_once(full, data)
    run.write_new(run.p('steps', 'trace-%s.json' % n), json.dumps({
        'action': n, 'target': intent['target'], 'export_sha256': sha256(data), 'complete': complete,
        'pages': [{'path': pg['path'], 'sha256': pg['sha256'], 'positions': [pg['a'], pg['b']], 'of': pg['of']}
                  for pg in sorted(parsed, key=lambda x: x['a'])], 'written_at': iso(clock())},
        indent=1, sort_keys=True) + '\n')
    run.stage = last_stage(run)
    run.log('trace', n, sha256(data), key='trace %s' % n, target=intent['target'], complete=complete)
    return 0, 'TRACE %s sha256 %s' % (intent['reply_to'], sha256(data))


def save(run_dir, n, data):
    """await_reply: write the reply (stdin) verbatim to the intent's reply_to, once."""
    run = Run(run_dir)
    if os.path.exists(run.p('STOP.md')):
        return 3, 'STOP %s' % run.p('STOP.md')
    try:
        intent = load_intent(run, n, 'await_reply')
    except Refusal as e:
        return 2, 'REFUSED %s: %s' % (n, e.text)
    full = intent['reply_to'] if os.path.isabs(intent['reply_to']) else run.p(intent['reply_to'])
    if os.path.exists(full) and read_bytes(full) != data:
        return 2, 'REFUSED %s: reply_to %s already exists with other bytes' % (n, intent['reply_to'])
    write_once(full, data)
    return 0, 'SAVED %s sha256 %s' % (intent['reply_to'], sha256(data))


def wait(run_dir, n, clock=now_local, sleep=time.sleep):
    """Sleep until the intent's not_before, at most WAIT_CAP_S per call."""
    ip = Run(run_dir).intent_path(n)
    if not os.path.isfile(ip):
        return 2, 'REFUSED %s: there is no intent %s' % (n, n)
    nb = parse_time(load_json(ip).get('not_before'))
    left = (nb - clock()).total_seconds() if nb else 0
    if left > 0:
        sleep(min(left, WAIT_CAP_S))
        left = (nb - clock()).total_seconds()
    return 0, ('READY %s' % n) if left <= 0 else ('WAIT %s %d' % (n, int(left) + 1))


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
    ip = run.intent_path(n)
    rs = run.receipts(n)
    if not (os.path.exists(ip) and rs):
        return False, 'REJECTED %s: no intent or no receipt' % n
    intent = load_json(ip)
    run.stage = 'verify'
    problem, fatal, _ = check_receipt(run, n, intent, rs[-1], len(rs))
    if not problem and intent.get('kind') == 'read_back_sha':
        problem, fatal = fresh_read(run, n, intent)
    rel = os.path.relpath(rs[-1], run.dir)
    run.log('verified' if not problem else 'rejected', n, key=('verified ' if not problem else 'rejected ') + rel,
            reason=problem)
    note = {PLATFORM: ' (not a runner deviation: the next step stops)', True:
            ' (a runner deviation: the next step stops)'}.get(fatal, '')
    return (False, 'REJECTED %s: %s%s' % (n, problem, note)) if problem else (True, 'VERIFIED %s' % n)


def kit_folder(head=git_head):
    """The kit folder (the repo root holding kit/qualify.py) and the commit it is checked out at."""
    sha, dirty = head()
    return os.path.dirname(HERE), (sha or 'unknown: not a git checkout') + (' (kit/ files changed)' if dirty else '')


def kickoff(run_dir, head=git_head):
    rq = os.path.join(os.path.abspath(run_dir), 'request.json')
    o = load_json(rq)['owner_authorization']
    kit, at = kit_folder(head)
    return render('kickoff.md', run=os.path.abspath(run_dir), request_sha=file_sha(rq), quote=o['quote'],
                  time=o['time'], msg_id=o['message_id'], kit=kit, head=at)


def stalled(run):
    """The last action with an intent and no receipt, else None."""
    d = run.p('actions')
    ns = sorted({x[:4] for x in os.listdir(d) if re.fullmatch(r'\d{4}\.intent(\.\d+)?\.json', x)}) \
        if os.path.isdir(d) else []
    return ns[-1] if ns and not run.receipts(ns[-1]) else None


RULING_FIELDS = ('quote', 'time', 'message_id', 'channel', 'stop_sha256')


def resume(run_dir, ruling_path, clock=now_local, head=git_head):
    """Resume after an Owner ruling on STOP.md: (exit code, printed text). Refuses (exit 2, nothing changed) with
    no STOP.md, a ruling that is not JSON or lacks a non-empty quote, time, message_id or channel, or a
    stop_sha256 that is not the sha256 of STOP.md."""
    run = Run(run_dir, clock=clock)
    sp = run.p('STOP.md')
    if not os.path.isfile(sp):
        return 2, 'REFUSED: %s has no STOP.md to resume from' % run.dir
    try:
        ruling = load_json(ruling_path)
    except (OSError, ValueError) as e:
        return 2, 'REFUSED: the ruling %s is not JSON: %s' % (ruling_path, e)
    if not isinstance(ruling, dict):
        return 2, 'REFUSED: the ruling %s is not a JSON object' % ruling_path
    bad = [k for k in RULING_FIELDS if not (isinstance(ruling.get(k), str) and ruling[k].strip())]
    if bad:
        return 2, 'REFUSED: the ruling lacks %s (the Owner\'s words verbatim, time, message id and channel, and the ' \
                  'sha256 of the STOP.md it rules on)' % bad
    if ruling['stop_sha256'] != file_sha(sp):
        return 2, 'REFUSED: the ruling is on STOP.md sha256 %s; this STOP.md is %s' % (ruling['stop_sha256'],
                                                                                     file_sha(sp))
    k = 1 + len([x for x in os.listdir(run.dir) if re.fullmatch(r'STOP-\d{2}\.md', x)])
    old, n = 'STOP-%02d.md' % k, stalled(run)
    rec = dict(ruling, stop_file=old, action=n, ruling_path=os.path.abspath(ruling_path),
               ruling_file_sha256=file_sha(ruling_path), resumed_at=iso(clock()))
    rp = run.write_new(run.p('rulings', 'ruling-%02d.json' % k), json.dumps(rec, indent=1, sort_keys=True) + '\n')
    os.rename(sp, run.p(old))
    run.stage = last_stage(run)
    run.log('resumed', n, ruling['stop_sha256'], key='resumed %02d' % k, stop_file=old,
            ruling=os.path.relpath(rp, run.dir), ruling_sha256=file_sha(rp), quote=ruling['quote'])
    kit, at = kit_folder(head)
    return 0, render('resume.md', run=run.dir, ruling=rp, ruling_sha=file_sha(rp), stop_file=run.p(old),
                     stop_sha=ruling['stop_sha256'], quote=ruling['quote'], time=ruling['time'],
                     msg_id=ruling['message_id'], channel=ruling['channel'], kit=kit, head=at,
                     action=('action %s is re-issued with this ruling' % n) if n else
                     'no action was stalled: the stopped check runs again')


def runner_stop(run_dir, reason, clock=now_local):
    run = Run(run_dir, clock=clock)
    if os.path.exists(run.p('STOP.md')):
        return run.p('STOP.md')
    try:
        run.req = load_json(run.p('request.json'))
    except (OSError, ValueError):
        run.req = {}
    stage = last_stage(run)
    run.stage = stage if stage in STAGES else 'S0'
    n = stalled(run)
    return run.write_stop(Stop(run.stage, 'the runner reports: %s' % reason, run.intent_path(n) if n else None))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('next', 'verify', 'kickoff', 'stop', 'readback', 'resume', 'trace', 'save', 'wait', 'now'):
        s = sub.add_parser(name)
        if name == 'now':
            continue
        s.add_argument('run')
        if name in ('verify', 'readback', 'trace', 'save', 'wait'):
            s.add_argument('action', type=lambda x: '%04d' % int(x))
        if name == 'stop':
            s.add_argument('reason')
        if name == 'resume':
            s.add_argument('--ruling', required=True)
        if name == 'trace':
            s.add_argument('pages', nargs='*')
            s.add_argument('--incomplete', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'now':
        print(iso(now_local()))
        return 0
    if a.cmd == 'kickoff':
        print(kickoff(a.run), end='')
        return 0
    if a.cmd in ('resume', 'trace', 'save', 'wait'):
        rc, text = {'resume': lambda: resume(a.run, a.ruling),
                    'trace': lambda: trace(a.run, a.action, a.pages, a.incomplete),
                    'save': lambda: save(a.run, a.action, sys.stdin.buffer.read()),
                    'wait': lambda: wait(a.run, a.action)}[a.cmd]()
        print(text, end='' if text.endswith('\n') else '\n')
        return rc
    if a.cmd == 'stop':
        print('STOP %s' % runner_stop(a.run, a.reason))
        return 3
    if a.cmd == 'readback':
        rc, text = readback(a.run, a.action)
        print(text)
        return rc
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
