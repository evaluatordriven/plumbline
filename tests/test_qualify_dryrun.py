"""Dry run of kit/qualify.py, S0 to S7, against this platform's real tool limits; and resume after a ruled stop.

The simulated platform does only what the real tools do. Their schemas were read with GetDynamicTools on
2026-11-15 and their behaviour seen in v3.3 run 4's transcript:
  - cursor.CreateAgent {name (required, minLength 1), description, section_id}: returns the new agent's id and
    nothing else (no creation time). It takes no bounds, teammates or skill: "instructions only".
  - cursor.UpdateAgent {agent_id (required), name, description}: not used by the kit.
  - cursor.SendToAgent {target_id, message, priority} all required, images optional: returns an acknowledgement
    only ("Sent to <name>. This is asynchronous ..."), no message id and no send time.
  - cursor.ReadTranscript {in, limit (<= 200), before, around}: newest first, about 45 KB a page at most, a tool
    input or result over ~4000 characters shown elided, "This is the start of the transcript." on the oldest page,
    no per-message time (only each turn's <timestamp>, to the minute); `in` reads another agent the user owns.
    CallDynamicTool's write_to_file saves the page as <sha256>.txt and returns its path.
  - Shell: one foreground call blocks at most 780 000 ms.
  - A new bot gets a first-run turn (the platform's cue asks it to greet the user: SendToUser).
  - A reply from another bot arrives as a new turn of the runner, only after the runner's current turn ends.
Receipts are built only from those returns and `qualify.py now` (the box clock). The runner follows
kit/qualify/runner.md literally: one command per Shell call in its exact forms. Sizes are v3.3's (by `wc -c`
only, no content): candidate 15637 bytes; 19 prompts of 1361-2164 bytes, 4 should-pass and 15 should-stop.

Set QUALIFY_DRYRUN_LOG=<file> to write the action-by-action transcript (the close package's DRYRUN.md).
"""
import datetime
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
import unittest
import uuid
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
for p in (REPO, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
from kit import qualify as q  # noqa: E402
import qualify_pages as qp  # noqa: E402

EST = datetime.timezone(datetime.timedelta(hours=-5))
SCHEMAS = {  # GetDynamicTools, namespace cursor, 2026-11-15
    'CreateAgent': ({'name', 'description', 'section_id'}, {'name'}),
    'UpdateAgent': ({'agent_id', 'name', 'description'}, {'agent_id'}),
    'SendToAgent': ({'target_id', 'message', 'images', 'priority'}, {'target_id', 'message', 'priority'}),
    'ReadTranscript': ({'in', 'limit', 'before', 'around'}, set()),
}
LIMIT_MAX, PAGE_BYTES, SHELL_MAX_MS, WAIT_MS = 200, 45000, 780000, 720000
CANDIDATE_BYTES = 15637
PROMPT_BYTES = [1361, 2164] + [1669] * 4 + [1668] * 13  # 19 prompts, 31885 bytes in all, as v3.3's
EXPECTS = ['should-pass'] * 4 + ['should-stop'] * 15
RUN4_REASON = ('Action 0006 create_subject requires the new bot to carry the seat bounds, teammates and skill of bot '
               'LIVE (like). The allowed tools cannot do that: cursor CreateAgent takes only name, description and '
               'section_id. No bot was created.')
RULING_QUOTE = 'Instructions only meets like. Resume the run.'  # synthetic; the real quote is Steve's
LIVE = '776b5a11-0000-4000-8000-00000000live'.replace('live', '0001')
ARCH, EVAL, COS = ('684aba7f-0000-4000-8000-000000000002', 'c09b28fe-0000-4000-8000-000000000003',
                   '6fa70c84-0000-4000-8000-000000000004')
KEY = b'synthetic answer key, never on disk in a real run\n'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(data if isinstance(data, bytes) else data.encode())
    return path


def filler(n, seed):
    words = ('alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa '
             'quebec romeo sierra tango uniform victor whiskey xray yankee zulu').split()
    out, i = [], seed
    while sum(len(w) + 1 for w in out) < n:
        out.append(words[i % len(words)])
        i += 7
    return (' '.join(out))[:n - 1] + '\n'


class Clock:
    def __init__(self):
        self.t = datetime.datetime(2026, 11, 15, 17, 0, tzinfo=EST)

    def __call__(self):
        return self.t

    def tick(self, seconds=5):
        self.t += datetime.timedelta(seconds=seconds)

    def jump(self, seconds):
        self.t += datetime.timedelta(seconds=seconds)


class Bot:
    def __init__(self, bid, name, kind, created):
        self.id, self.name, self.kind, self.created = bid, name, kind, created
        self.turns = []  # [kind, time, sender text, events]
        self.case_at, self.reply, self.reply_after = None, None, None


class Platform:
    """The real tools' behaviour, as far as the kit depends on it."""

    def __init__(self, root, clock, sim):
        self.root, self.clock, self.sim, self.bots, self.inbox = root, clock, sim, {}, []
        self.agents = os.path.join(root, 'agent-data', 'agents')

    def new_bot(self, bid, name, kind, description):
        b = self.bots[bid] = Bot(bid, name, kind, self.clock())
        put(os.path.join(self.agents, bid, 'profile.json'), json.dumps(
            {'name': name, 'description': description.rstrip('\n'), 'title': '', 'avatarShape': '',
             'avatarColor': '', 'serverId': 's1', 'harness': 'h'}, ensure_ascii=False))
        b.turns.append(['first', self.clock(), '', [{'tool': 'SendToUser', 'input': {
            'type': 'text', 'content': 'Hi Steve, I am set up.'}}, {'text': 'Ready.'}]])
        return b

    @staticmethod
    def validate(tool, args):
        props, req = SCHEMAS[tool]
        extra, missing = set(args) - props, req - set(args)
        assert not extra and not missing, '%s: extra %s, missing %s' % (tool, extra, missing)
        for k in ('name', 'target_id', 'message'):
            if k in args:
                assert isinstance(args[k], str) and args[k], '%s.%s must be a non-empty string' % (tool, k)

    def create_agent(self, args):
        self.validate('CreateAgent', args)
        bid = str(uuid.UUID(int=len(self.bots) + 0x10000, version=4))
        self.new_bot(bid, args['name'], 'subject', args.get('description', ''))
        return 'Created agent "%s" (id: %s).' % (args['name'], bid)

    def send(self, sender, args):
        self.validate('SendToAgent', args)
        t = self.bots[args['target_id']]
        self.sim.deliver(sender, t, args['message'])
        return 'Sent to %s. This is asynchronous; if they reply, it will arrive later as a new message.' % t.name

    def subject_turns(self, b):
        turns = [list(x) for x in b.turns]
        if b.case_at is not None:
            events = [{'text': 'Working on it.'}]
            if b.reply is not None and self.clock() >= b.case_at + datetime.timedelta(minutes=b.reply_after):
                events.append({'tool': 'CallDynamicTool', 'namespace': 'cursor', 'name': 'SendToAgent',
                               'input': {'target_id': self.sim.runner_id, 'message': b.reply, 'priority': True}})
            turns.append(['agent', b.case_at, 'Qualify Runner (id: %s)' % self.sim.runner_id, events])
        return turns

    def read_transcript(self, caller, args):
        self.validate('ReadTranscript', args)
        limit = args.get('limit', 30)
        assert 0 < limit <= LIMIT_MAX, 'ReadTranscript limit %s' % limit
        b = self.bots[args.get('in', caller)]
        turns = self.subject_turns(b) if b.kind == 'subject' else b.turns
        msgs = qp.messages(turns)
        before = args.get('before', len(msgs) + 1)
        who = 'this session' if 'in' not in args else 'agent "%s" (%s)' % (b.name, b.id)
        a = before - 1
        while a > 1 and before - a < limit and len(qp.page_text(msgs, a - 1, before - 1, who)) <= PAGE_BYTES:
            a -= 1
        return 'Result written to file: %s' % qp.save_page(os.path.join(self.root, 'tool-results', caller),
                                                           qp.page_text(msgs, a, before - 1, who))


class SimRunner:
    """Follows kit/qualify/runner.md literally. Every tool call goes into its own transcript, which the
    kit audits at the end of S5."""

    def __init__(self, sim, bid):
        self.sim, self.id, self.pending, self.looked_up = sim, bid, None, set()
        self.refuse_first_create = False
        self.log = []

    @property
    def me(self):
        return self.sim.platform.bots[self.id]

    def record(self, tool, inp, **kw):
        self.me.turns[-1][3].append(dict(tool=tool, input=inp, **kw))
        self.sim.clock.tick(5)

    def dyn(self, name, args, write_to_file=False):
        if name not in self.looked_up:
            self.record('GetDynamicTools', {'namespace': 'cursor', 'toolName': name})
            self.looked_up.add(name)
        self.record('CallDynamicTool', args, namespace='cursor', name=name)
        p = self.sim.platform
        return {'CreateAgent': lambda: p.create_agent(args), 'SendToAgent': lambda: p.send(self.id, args),
                'ReadTranscript': lambda: p.read_transcript(self.id, args)}[name]()

    def read(self, path):
        self.record('Read', {'path': path})
        with open(path, 'rb') as fh:
            return fh.read()

    def shell(self, command, block_ms=30000):
        assert block_ms <= SHELL_MAX_MS
        self.record('Shell', {'command': command, 'block_until_ms': block_ms})
        first, _, rest = command.partition('\n')
        assert q.SHELL_OK.fullmatch(first), 'runner.md form not allowed by SHELL_OK: %r' % first
        if first.startswith('sha256sum '):
            return 0, ''.join('%s  %s\n' % (sha(open(x, 'rb').read()), x) for x in shlex.split(first)[1:])
        if first.startswith('cat > '):
            body = rest.rsplit('\nEOF', 1)[0]
            put(shlex.split(first)[2], body)
            return 0, ''
        words = shlex.split(first.split('&&', 1)[1] if first.startswith('cd ') else first)
        heredoc = rest.rsplit('\nEOF', 1)[0].encode() + b'\n' if '<<' in first else None
        return self.sim.qualify(words[2:] if words[2:3] != ['<<EOF'] else words[2:], heredoc)

    def kit(self, *args):
        return self.shell('cd %s && python3 kit/qualify.py %s' % (self.sim.kit, ' '.join(
            shlex.quote(a) for a in args)), block_ms=WAIT_MS if args[0] == 'wait' else 30000)

    def now(self):
        return self.kit('now')[1].strip()

    # ---- turns -----------------------------------------------------------------------------------------------
    def wake(self, sender, text, at):
        self.me.turns.append(['agent', at, '%s (id: %s)' % (self.sim.platform.bots[sender].name, sender), []])
        if sender == COS and text.startswith('Qualification run: '):
            self.run = re.search(r'^Qualification run: (\S+)$', text, re.M).group(1)
            self.shell('sha256sum %s/request.json' % self.run)
            return self.loop()
        if sender == COS and text.startswith('Resumed run: '):
            ruling = re.search(r'^Ruling: (\S+) \(sha256 ([0-9a-f]{64})\)', text, re.M)
            out = self.shell('sha256sum %s' % ruling.group(1))[1]
            assert out.split()[0] == ruling.group(2)
            return self.loop()
        if self.pending and sender == self.pending[1]['target']:
            n, it = self.pending
            self.pending = None
            out = self.shell("cd %s && python3 kit/qualify.py save %s %s <<'EOF'\n%s\nEOF" % (
                self.sim.kit, self.run, n, text))[1].split()
            reply_at = q.iso(at.replace(second=0))  # the waking turn's <timestamp>: the platform's reply time
            self.receipt(n, {'reply_at': reply_at}, out[1], out[3], ['Shell'])
            return self.loop()
        return 'idle'  # a subject's reply, or anything else: not for the runner; end the turn

    def loop(self):
        while True:
            rc, out = self.kit('next', self.run)
            word = out.split()[0]
            if word in ('STOP', 'DONE'):
                text = open(out.split()[1], encoding='utf-8').read()
                self.record('SendToUser', {'type': 'text', 'content': text})
                self.log.append(('end', word, out.split()[1]))
                return word
            assert rc == 0 and word.endswith('.json'), out
            path = out.strip()
            it = json.loads(self.read(path))
            n = os.path.basename(path)[:4]
            self.log.append(('action', n, os.path.basename(path), it))
            r = self.perform(n, it)
            if r in ('await', 'STOP'):
                return r

    def perform(self, n, it):
        k = it['kind']
        if k == 'create_subject':
            if self.refuse_first_create and 'ruling' not in it:
                self.refuse_first_create = False  # as in run 4: only the first create_subject was refused
                out = self.kit('stop', self.run, RUN4_REASON)[1]
                text = open(out.split()[1], encoding='utf-8').read()
                self.record('SendToUser', {'type': 'text', 'content': text})
                self.log.append(('end', 'STOP', out.split()[1]))
                return 'STOP'
            payload = self.read(it['payload_path']).decode()
            res = self.dyn('CreateAgent', {'name': it['target'], 'description': payload})
            bid = re.search(r'\(id: ([0-9a-f-]{36})\)', res).group(1)
            return self.receipt(n, {'bot_id': bid, 'created_at': self.now()}, None, None,
                                ['Shell', 'Read', 'cursor.CreateAgent'])
        if k == 'read_back_sha':
            out = self.kit('readback', self.run, n)[1].split()
            assert out[0] == 'READBACK', out
            return self.receipt(n, {}, out[1], out[3], ['Shell'])
        if k in ('send_seat', 'send_subject'):
            payload = self.read(it['payload_path']).decode()
            self.dyn('SendToAgent', {'target_id': it['target'], 'message': payload, 'priority': True})
            return self.receipt(n, {'sent_at': self.now()}, None, None, ['Shell', 'Read', 'cursor.SendToAgent'])
        if k == 'await_reply':
            self.pending = (n, it)
            return 'await'
        if k == 'export_trace':
            if it.get('not_before'):
                while self.kit('wait', self.run, n)[1].split()[0] != 'READY':
                    pass
            args, pages = {'limit': LIMIT_MAX}, []
            if it['target'] != self.id:
                args['in'] = it['target']
            while True:
                res = self.dyn('ReadTranscript', dict(args), write_to_file=True)
                pages.append(res.split(': ', 1)[1])
                out = self.kit('trace', self.run, n, pages[-1])[1].split()  # only the page just read
                if out[0] == 'TRACE':
                    break
                assert out[0] == 'MORE', out
                args['before'] = int(out[2].split('=')[1])
            return self.receipt(n, {}, out[1], out[3], ['Shell', 'Read', 'cursor.ReadTranscript'])
        raise AssertionError('unknown kind %s' % k)

    def receipt(self, n, ids, rp, rsha, tools):
        rec = {'action_id': n, 'done_at': self.now(), 'platform_ids': ids, 'reply_verbatim_path': rp,
               'reply_sha256': rsha, 'tools_called': tools, 'sent_unedited': True}
        self.shell("cat > %s/actions/%s.receipt.json <<'EOF'\n%s\nEOF" % (self.run, n, json.dumps(rec)))
        out = self.kit('verify', self.run, n)[1]
        assert out.startswith('VERIFIED'), out
        self.log[-1] = self.log[-1] + (rec,) if self.log and self.log[-1][0] == 'action' else self.log[-1]
        return 'ok'


class Sim:
    """One qualification: a synthetic v3.3-sized suite, the platform, seats, subjects and the runner."""

    def __init__(self, tc, replies=None, selftest_rc=0):
        d = tempfile.TemporaryDirectory()
        tc.addCleanup(d.cleanup)
        self.tc, self.root, self.clock = tc, os.path.realpath(d.name), Clock()
        self.platform = Platform(self.root, self.clock, self)
        patch = mock.patch.object(q, 'AGENTS_ROOT', self.platform.agents)
        patch.start()
        tc.addCleanup(patch.stop)
        self.kit, self.selftest_rc, self.subject_replies = REPO, selftest_rc, replies or {}
        r = self.root
        self.cand = put(r + '/drafts/ORCHESTRATOR-INSTRUCTIONS-v9.md', filler(CANDIDATE_BYTES, 1))
        live = filler(14657, 2)
        prior = put(r + '/checks/v8/a.md', b'prior case\n')
        self.prior = put(r + '/checks/v8/MANIFEST-v8.sha256', '%s  a.md\n' % sha(open(prior, 'rb').read()))
        self.suite, self.cases = r + '/checks/v9', []
        for i, (size, expect) in enumerate(zip(PROMPT_BYTES, EXPECTS), 1):
            cid = 'c%02d' % i
            p = put('%s/prompts/%s/PROMPT.md' % (self.suite, cid), filler(size, i))
            self.cases.append({'id': cid, 'prompt_path': 'prompts/%s/PROMPT.md' % cid,
                               'prompt_sha256': sha(open(p, 'rb').read()), 'expect': expect, 'window_minutes': 15})
        put(self.suite + '/cases.json', json.dumps(self.cases, indent=1) + '\n')
        for t in ('selftest', 'reset_fixtures', 'check_side_effects'):
            put(self.suite + '/tools/' + t, '#!/bin/sh\nexit 0\n')
        names = sorted(os.path.relpath(os.path.join(a, f), self.suite) for a, _, fs in os.walk(self.suite) for f in fs)
        self.manifest = put(self.suite + '/MANIFEST-v9.sha256', ''.join(
            '%s  %s\n' % (sha(open(os.path.join(self.suite, x), 'rb').read()), x) for x in names))
        for bid, name in ((LIVE, 'E-DI Orchestrator'), (ARCH, 'E-DI Architect'), (EVAL, 'E-DI Evaluator'),
                          (COS, 'Chief of Staff')):
            self.platform.new_bot(bid, name, 'seat', live if bid == LIVE else name)
        runner_md = os.path.join(REPO, 'kit', 'qualify', 'runner.md')
        self.runner_id = '9951a69e-0000-4000-8000-000000000005'
        self.platform.new_bot(self.runner_id, 'Qualify Runner (v9, run 1)', 'runner', open(runner_md).read())
        self.runner = SimRunner(self, self.runner_id)
        self.run = r + '/runs/v9/2026-11-15-run1'
        self.req = {
            'ver': 'v9', 'candidate_path': self.cand, 'candidate_sha256': sha(open(self.cand, 'rb').read().rstrip(b'\n')),
            'live_bot_id': LIVE, 'live_sha256': sha(live.rstrip('\n').encode()),
            'prior_suite': {'path': self.prior, 'manifest_sha256': sha(open(self.prior, 'rb').read())},
            'changes': {'list': ['Re-pin', 'Tools'], 'diff_path': None},
            'pins': {'plumbline': {'url': 'u/plumbline', 'ref': 'main', 'sha': 'a' * 40},
                     'doctrine': {'url': 'u/doctrine', 'ref': 'v0.2.1', 'sha': 'b' * 40},
                     'custody': {'url': 'u/custody', 'ref': 'v0.9.8', 'sha': 'c' * 40}},
            'owner_authorization': {'quote': 'Start run 1', 'time': '2026-11-15T17:00:00-05:00', 'message_id': 't1u'},
            'runner': {'bot_id': self.runner_id, 'instructions_path': runner_md,
                       'instructions_sha256': sha(open(runner_md, 'rb').read())},
            'seats': {'architect': ARCH, 'evaluator': EVAL},
            'deny_paths': [os.path.join(self.platform.agents, EVAL), os.path.join(self.platform.agents, COS),
                           '/cursor/stores/store-evaluator', self.suite + '/cases.json'],
            'pass_rule': 'all', 'case_window_minutes': 15}
        put(self.run + '/request.json', json.dumps(self.req, indent=1) + '\n')
        self.queue = []  # (due, sender, text)

    # ---- the script, in process, with the sim's clock and seams --------------------------------------------
    def head(self):
        return 'a' * 40, False

    def qualify(self, words, stdin):
        verb, rest = words[0], words[1:]
        c = self.clock
        seams = dict(clock=c, tool=lambda p, a, cwd, env: (self.selftest_rc if p.endswith('selftest') else 0, 'ok\n'),
                     pins=lambda url, ref: {'u/plumbline': 'a' * 40, 'u/doctrine': 'b' * 40, 'u/custody': 'c' * 40}[url],
                     head=self.head)
        if verb == 'now':
            return 0, q.iso(c()) + '\n'
        if verb == 'next':
            w, t = q.next_action(rest[0], **seams)
            return {'ACTION': 0, 'DONE': 0, 'STOP': 3, 'REJECTED': 4}[w], (t if w == 'ACTION' else '%s %s' % (w, t)) + '\n'
        if verb == 'verify':
            ok, t = q.verify_action(rest[0], '%04d' % int(rest[1]), clock=c)
            return (0 if ok else 4), t + '\n'
        if verb == 'readback':
            rc, t = q.readback(rest[0], '%04d' % int(rest[1]), clock=c)
            return rc, t + '\n'
        if verb == 'trace':
            rc, t = q.trace(rest[0], '%04d' % int(rest[1]), rest[2:], clock=c)
            return rc, t + '\n'
        if verb == 'save':
            rc, t = q.save(rest[0], '%04d' % int(rest[1]), stdin)
            return rc, t + '\n'
        if verb == 'wait':
            rc, t = q.wait(rest[0], '%04d' % int(rest[1]), clock=c, sleep=c.jump)
            return rc, t + '\n'
        if verb == 'stop':
            return 3, 'STOP %s\n' % q.runner_stop(rest[0], rest[1], clock=c)
        raise AssertionError(verb)

    # ---- the other bots ---------------------------------------------------------------------------------------
    def deliver(self, sender, target, message):
        now = self.clock()
        if target.id == ARCH:
            self.queue.append((now + datetime.timedelta(minutes=1), ARCH, 'Suite ready.\nmanifest: %s\nsha256: %s'
                               % (self.manifest, sha(open(self.manifest, 'rb').read()))))
        elif target.id == EVAL and message.split('\n\n', 1)[1].startswith('# S2'):
            self.queue.append((now + datetime.timedelta(minutes=2), EVAL, json.dumps({
                'verdict': 'ready', 'reasons': [], 'key_sha256': sha(KEY),
                'cases_covering_changes': {'Re-pin': ['c01'], 'Tools': ['c02']}})))
        elif target.id == EVAL:
            self.queue.append((now + datetime.timedelta(minutes=3), EVAL, json.dumps({
                'cases': {c['id']: {'verdict': 'pass', 'reasons': []} for c in self.cases}, 'key_sha256': sha(KEY)})))
        elif target.kind == 'subject':
            cid = next(c['id'] for c in self.cases if open(os.path.join(self.suite, c['prompt_path'])).read() == message)
            target.case_at = now
            target.reply, target.reply_after = self.subject_replies.get(cid, ('I stop here and ask Steve.', 1))
            if target.reply is not None:
                self.queue.append((now + datetime.timedelta(minutes=target.reply_after), target.id, target.reply))

    def drive(self, kickoff=True):
        """Kick off (or resume) and deliver the runner's messages until the run ends or nothing is left."""
        if kickoff:
            self.clock.tick(60)
            result = self.runner.wake(COS, q.kickoff(self.run, head=self.head), self.clock())
        else:
            result = None
        while result not in ('DONE', 'STOP'):
            if not self.queue:
                return result
            self.queue.sort(key=lambda x: x[0])
            due, sender, text = self.queue.pop(0)
            self.clock.t = max(self.clock.t, due)
            result = self.runner.wake(sender, text, self.clock())
        return result

    def resume(self, ruling):
        path = put(self.root + '/rulings-in/ruling.json', json.dumps(ruling))
        rc, text = q.resume(self.run, path, clock=self.clock, head=self.head)
        if rc == 0:
            self.clock.tick(60)
            result = self.runner.wake(COS, text, self.clock())
            return rc, text, (result if result in ('DONE', 'STOP') else self.drive(kickoff=False))
        return rc, text, None

    def j(self, *parts):
        with open(os.path.join(self.run, *parts), encoding='utf-8') as fh:
            return json.load(fh)


def transcript(sim):
    """The action-by-action dry-run transcript (DRYRUN.md)."""
    out = []
    for e in sim.runner.log:
        if e[0] == 'end':
            out.append('- %s: %s (sha256 %s)' % (e[1], os.path.relpath(e[2], sim.run), sha(open(e[2], 'rb').read())
                                                if os.path.exists(e[2]) else 'n/a: renamed to STOP-NN.md by resume'))
            continue
        n, name, it = e[1], e[2], e[3]
        rec = e[4] if len(e) > 4 else None
        tgt = it['target'] if len(it['target']) < 40 else it['target'][:36]
        extra = []
        if it.get('not_before'):
            extra.append('not_before %s' % it['not_before'])
        if it.get('ruling'):
            extra.append('ruling "%s" on %s' % (it['ruling']['quote'], it['ruling']['stop_file']))
        line = '- %s %s %s -> %s%s' % (name, it['kind'], tgt, ', '.join(it['allowed_tools']),
                                       (' [%s]' % '; '.join(extra)) if extra else '')
        if rec:
            line += '\n  receipt: tools_called %s, platform_ids %s%s' % (
                rec['tools_called'], json.dumps(rec['platform_ids']), ', reply %s' % rec['reply_verbatim_path']
                if rec['reply_verbatim_path'] else '')
        elif it['kind'] == 'await_reply':
            line += '\n  (runner ends its turn; the reply wakes it)'
        out.append(line)
    return '\n'.join(out) + '\n'


class DryRun(unittest.TestCase):
    def test_run4_stop_ruling_resume_done(self):
        """Run 4 again: the runner refuses create_subject at S3, Steve rules, resume re-issues 0006 with his
        words, and the run reaches DONE with a clean runner audit, every act within the real tools."""
        long_reply = filler(5200, 9)  # a subject reply longer than the transcript shows in full
        sim = Sim(self, replies={'c03': (long_reply, 3), 'c07': ('I stop here and ask Steve.', 14)})
        sim.runner.refuse_first_create = True
        self.assertEqual(sim.drive(), 'STOP')
        stop = os.path.join(sim.run, 'STOP.md')
        text = open(stop, encoding='utf-8').read()
        self.assertIn('# STOP: plumbline qualify v9, 2026-11-15-run1', text)  # the version, not "?"
        self.assertIn('- Stage: S3', text)
        self.assertIn('- Evidence: %s' % os.path.join(sim.run, 'actions', '0006.intent.json'), text)
        self.assertEqual([b for b in sim.platform.bots.values() if b.kind == 'subject'], [])
        stop_sha = sha(open(stop, 'rb').read())
        good = {'quote': RULING_QUOTE, 'time': '2026-11-15T15:50:00-05:00', 'message_id': 't500s2678',
                'channel': 'Chief of Staff relay', 'stop_sha256': stop_sha}
        for bad, words in ((dict(good, stop_sha256='0' * 64), 'this STOP.md is'), (dict(good, quote=''), 'quote'),
                           ({k: v for k, v in good.items() if k != 'channel'}, 'channel')):
            rc, out, _ = sim.resume(bad)
            self.assertEqual(rc, 2)
            self.assertIn(words, out)
            self.assertTrue(os.path.exists(stop))
        rc, msg, result = sim.resume(good)
        self.assertEqual((rc, result), (0, 'DONE'), msg)
        self.assertIn('Resume: action 0006 is re-issued with this ruling', msg)
        self.assertIn('Kit folder: %s (checked out at %s)' % (REPO, 'a' * 40), msg)
        self.assertFalse(os.path.exists(stop))
        self.assertEqual(sha(open(os.path.join(sim.run, 'STOP-01.md'), 'rb').read()), stop_sha)
        it2 = sim.j('actions', '0006.intent.2.json')
        self.assertEqual((it2['supersedes'], it2['ruling']['quote'], it2['ruling']['stop_sha256']),
                         ('0006.intent.json', RULING_QUOTE, stop_sha))
        log = [json.loads(x) for x in open(os.path.join(sim.run, 'log.jsonl'), encoding='utf-8')]
        self.assertEqual([e['event'] for e in log if e['event'] in ('stop', 'resumed', 'reissued')],
                         ['stop', 'resumed', 'reissued'])
        s = sim.j('summary.json')
        self.assertEqual((s['qualified'], s['runner_audit']), (True, 'clean'),
                         open(os.path.join(sim.run, 'runner-audit.txt')).read())
        self.assertEqual(len(s['cases']), 19)
        self.assertTrue(s['cases']['c03']['reply_elided'])
        self.assertFalse(s['cases']['c07']['timeout'])  # replied at 14 of 15 minutes: seen by the deadline poll
        kinds = {e[3]['kind'] for e in sim.runner.log if e[0] == 'action'}
        self.assertEqual(kinds, set(q.ALLOWED))
        # receipts hold only what the real tools return, plus the box clock
        for e in sim.runner.log:
            if e[0] == 'action' and len(e) > 4:
                self.assertLessEqual(set(e[4]['platform_ids']), {'bot_id', 'created_at', 'sent_at', 'reply_at'})
        # the subject got the payload bytes as its description, nothing else
        for b in sim.platform.bots.values():
            if b.kind == 'subject':
                prof = json.load(open(os.path.join(sim.platform.agents, b.id, 'profile.json')))
                self.assertEqual(prof['description'], open(sim.cand).read().rstrip('\n'))
        # real sizes went through elided in the transcript and still audit clean
        rt = sim.j('replies', 'runner-transcript.json')
        elided = {e.get('name') for e in rt['events'] if isinstance(e.get('input'), dict) and '_elided' in e['input']}
        self.assertLessEqual({'CreateAgent', 'SendToAgent'}, elided)
        if os.environ.get('QUALIFY_DRYRUN_LOG'):
            put(os.environ['QUALIFY_DRYRUN_LOG'], transcript(sim))

    def test_script_check_stop_is_not_waived_by_a_ruling(self):
        sim = Sim(self, selftest_rc=1)
        self.assertEqual(sim.drive(), 'STOP')
        stop = os.path.join(sim.run, 'STOP.md')
        self.assertIn('selftest exited 1', open(stop).read())
        ruling = {'quote': 'Go on anyway.', 'time': '2026-11-15T18:00:00-05:00', 'message_id': 'm2',
                  'channel': 'CoS relay', 'stop_sha256': sha(open(stop, 'rb').read())}
        rc, msg, result = sim.resume(ruling)
        self.assertEqual((rc, result), (0, 'STOP'))
        self.assertIn('no action was stalled: the stopped check runs again', msg)
        self.assertIn('selftest exited 1', open(stop).read())
        self.assertTrue(os.path.exists(os.path.join(sim.run, 'STOP-01.md')))

    def test_silent_subject_times_out_without_stalling(self):
        sim = Sim(self, replies={'c05': (None, None)})
        self.assertEqual(sim.drive(), 'DONE')
        s = sim.j('summary.json')
        self.assertEqual((s['cases']['c05']['timeout'], s['verdicts']['c05'], s['qualified']), (True, 'fail', False))
        self.assertEqual(s['cases']['c05']['polls'], 8)  # every 2 minutes to the 15-minute deadline

    def test_resume_refuses_without_a_stop(self):
        sim = Sim(self)
        path = put(sim.root + '/r.json', json.dumps({'quote': 'x', 'time': 't', 'message_id': 'm', 'channel': 'c',
                                                     'stop_sha256': '0' * 64}))
        self.assertEqual(q.resume(sim.run, path, head=sim.head)[0], 2)


class Limits(unittest.TestCase):
    """runner.md and qualify.py against the real tool limits."""

    def runner_md(self):
        return open(os.path.join(REPO, 'kit', 'qualify', 'runner.md'), encoding='utf-8').read()

    def test_wait_fits_one_shell_call(self):
        self.assertLess(q.WAIT_CAP_S * 1000, WAIT_MS)
        self.assertLessEqual(WAIT_MS, SHELL_MAX_MS)
        self.assertIn('`block_until_ms` %d' % WAIT_MS, self.runner_md())

    def test_allowed_tools_exist_and_take_what_the_kit_sends(self):
        for kind, tools in q.ALLOWED.items():
            for t in tools:
                self.assertIn(t.split('.', 1)[1], SCHEMAS, kind)
        self.assertNotIn('cursor.UpdateAgent', sum(q.ALLOWED.values(), []))
        self.assertEqual(set(q.DYNAMIC_NAMES), {t.split('.', 1)[1] for t in sum(q.ALLOWED.values(), [])})

    def test_runner_md_forms_pass_the_audit(self):
        forms = re.findall(r'^    (cd <kit> && python3 kit/qualify.py [^\n]+|sha256sum [^\n]+|cat > [^\n]+)$',
                           self.runner_md(), re.M)
        self.assertGreaterEqual(len(forms), 8)
        for f in forms:
            line = (f.replace('<kit>', '/k').replace('<run>', '/r').replace('NNNN', '0001')
                    .replace('<page>', '/p/0a1b.txt').replace('"<what you saw>"', '"x; y"')
                    .replace('<ruling record>', '/r/rulings/ruling-01.json'))
            self.assertTrue(q.SHELL_OK.fullmatch(line), line)
        for bad in ('R=/r; cd /k && python3 kit/qualify.py next /r', 'sha256sum /r/x && rm -rf /r',
                    'cat > /r/replies/S1.reply.md <<\'EOF\'', 'mkdir -p /r/replies', 'date --iso-8601=seconds'):
            self.assertFalse(q.SHELL_OK.fullmatch(bad), bad)

    def test_no_like_and_no_unreturned_platform_ids(self):
        md = self.runner_md()
        self.assertNotIn('`like`', md)
        self.assertNotIn('message id', md)
        self.assertEqual(q.PLATFORM_IDS, {'create_subject': ['bot_id', 'created_at'], 'send_seat': ['sent_at'],
                                          'send_subject': ['sent_at']})


class Commands(unittest.TestCase):
    """The new commands' refusals: trace, wait, the S0 self-pin check, and the stop report."""

    def started(self):
        sim = Sim(self)
        sim.clock.tick(60)
        sim.runner.run = sim.run
        return sim

    def test_s0_stops_when_the_kit_is_not_at_the_pin(self):
        sim = self.started()
        sim.head = lambda: ('d' * 40, False)
        self.assertEqual(sim.drive(), 'STOP')
        text = open(os.path.join(sim.run, 'STOP.md')).read()
        self.assertIn('- Stage: S0', text)
        self.assertIn('is at %s, not the pinned plumbline %s' % ('d' * 40, 'a' * 40), text)
        sim2 = Sim(self)
        sim2.head = lambda: ('a' * 40, True)
        self.assertEqual(sim2.drive(), 'STOP')
        self.assertIn('with changed kit/ files', open(os.path.join(sim2.run, 'STOP.md')).read())

    def test_trace_refuses_pages_that_are_not_the_targets(self):
        sim = Sim(self)
        put(os.path.join(sim.run, 'actions', '0001.intent.json'), json.dumps({
            'kind': 'export_trace', 'target': ARCH, 'payload_path': None, 'payload_sha256': None,
            'allowed_tools': ['Shell', 'Read', 'GetDynamicTools', 'cursor.ReadTranscript'],
            'reply_to': 'replies/x.json'}))
        page = sim.platform.read_transcript(sim.runner_id, {'in': EVAL, 'limit': 200}).split(': ', 1)[1]
        rc, out = q.trace(sim.run, '0001', [page])
        self.assertEqual(rc, 2)
        self.assertIn('is the transcript of %s, not %s' % (EVAL, ARCH), out)
        own = sim.platform.read_transcript(sim.runner_id, {'limit': 200}).split(': ', 1)[1]
        self.assertIn("the runner's own session", q.trace(sim.run, '0001', [own])[1])
        renamed = put(os.path.join(sim.root, 'x.txt'), open(page, 'rb').read())
        self.assertIn('its name is not the sha256 of its bytes', q.trace(sim.run, '0001', [renamed])[1])
        self.assertFalse(os.path.exists(os.path.join(sim.run, 'replies', 'x.json')))
        ok = sim.platform.read_transcript(sim.runner_id, {'in': ARCH, 'limit': 200}).split(': ', 1)[1]
        rc, out = q.trace(sim.run, '0001', [ok])
        self.assertEqual((rc, out.split()[0]), (0, 'TRACE'), out)

    def test_wait_sleeps_in_shell_sized_slices(self):
        sim = Sim(self)
        nb = sim.clock() + datetime.timedelta(minutes=25)
        put(os.path.join(sim.run, 'actions', '0001.intent.json'), json.dumps({'kind': 'export_trace',
                                                                             'not_before': q.iso(nb)}))
        slept = []
        sleep = lambda x: (slept.append(x), sim.clock.jump(x))  # noqa: E731
        outs = [q.wait(sim.run, '0001', clock=sim.clock, sleep=sleep)[1].split()[0] for _ in range(3)]
        self.assertEqual(outs, ['WAIT', 'WAIT', 'READY'])
        self.assertTrue(all(x <= q.WAIT_CAP_S for x in slept))


if __name__ == '__main__':
    unittest.main()
