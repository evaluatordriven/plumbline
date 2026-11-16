"""kit-reply-agentid: subject replies sent with SendToAgent "agentId", rescoring a stopped run from its saved
exports, and rehearsing a resume on a plain copy of a run.

Run 5 (v3.3) logged 10 of 19 cases timeout:true at S5: the subjects replied with CallDynamicTool cursor
SendToAgent {"agentId": <runner>, "message": ..., "priority": true} (CoS trace evidence, n8.trace.8.json), and
subject_reply matched only "target_id". The fixed kit takes agentId, target_id or agent_id. A run resumed at the
fixed kit commit replays its saved exports: the first export that shows the reply scores the case; the later
exports the old kit asked for are performed again in order (verified from their receipts), so the action numbers
still match the record. Nothing is waived and nothing on record is rewritten.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
for p in (REPO, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
from kit import qualify as q  # noqa: E402
import qualify_pages as qp  # noqa: E402
from test_qualify_dryrun import EST, Sim, put, sha  # noqa: E402
import datetime  # noqa: E402

RUNNER = 'c17ecd50-28ce-40d4-9cd3-8a00000ae518'
SUBJECT = 'f6fe0f72-0000-4000-8000-000000000010'
OLD, NEW = 'a' * 40, 'b' * 40
STOP_QUOTE = ('Stop run 5 now and have the Architect fix how subject replies are found (agentId), ideally '
              're-scoring from the saved transcripts, then resume or rerun')


def real_reply_event(key='agentId', target=RUNNER, message='<text>'):
    """The redacted shape of a real subject reply event (subject 10, run 5, 2026-11-15T21:24:00-05:00)."""
    return {'at': '2026-11-15T21:24:00-05:00', 'first_run': False, 'tool': 'CallDynamicTool', 'namespace': 'cursor',
            'name': 'SendToAgent', 'input': {key: target, 'message': message, 'priority': True}}


def old_subject_reply(tr, runner):
    """subject_reply as it was at 09b7323e: SendToAgent target_id only (the check run 5 timed out on)."""
    for e in tr['events']:
        if e.get('first_run') or e.get('tool') != 'CallDynamicTool':
            continue
        inp = e.get('input') if isinstance(e.get('input'), dict) else {}
        if e.get('namespace') == 'cursor' and e.get('name') == 'SendToAgent' and inp.get('target_id') == runner:
            return str(inp.get('message', '')), False
    return None


class ReplyKey(unittest.TestCase):
    def test_agentid_reply_is_found(self):
        tr = {'events': [real_reply_event()]}
        self.assertEqual(q.subject_reply(tr, RUNNER), ('<text>', False))
        self.assertIsNone(old_subject_reply(tr, RUNNER))  # what run 5 scored as no reply

    def test_target_id_and_agent_id_still_work(self):
        for key in ('target_id', 'agent_id', 'agentId'):
            self.assertEqual(q.subject_reply({'events': [real_reply_event(key)]}, RUNNER), ('<text>', False), key)

    def test_other_target_first_run_or_namespace_is_not_a_reply(self):
        other = real_reply_event(target='00000000-0000-4000-8000-000000000099')
        first = dict(real_reply_event(), first_run=True)
        ns = dict(real_reply_event(), namespace='x')
        self.assertIsNone(q.subject_reply({'events': [other, first, ns]}, RUNNER))
        self.assertEqual(q.subject_reply({'events': [other, real_reply_event(message='b')]}, RUNNER), ('b', False))

    def test_agentid_reply_on_a_real_shaped_page_short_and_elided(self):
        """The reply as ReadTranscript shows it, through parse_page and export_from_pages: a short message and one
        over ~4000 characters (shown elided, with agentId still readable at its head)."""
        t = datetime.datetime(2026, 11, 15, 21, 24, tzinfo=EST)
        for msg, elided in (('Short reply.', False), ('L' * 5000, True)):
            ev = real_reply_event(message=msg)
            turns = [['first', t - datetime.timedelta(minutes=30), '', [{'tool': 'SendToUser', 'input': {
                'type': 'text', 'content': 'Hi'}}]],
                ['agent', t, 'Qualify Runner (id: %s)' % RUNNER, [{'text': 'Working.'},
                                                                  {k: ev[k] for k in ('tool', 'namespace', 'name',
                                                                                       'input')}]]]
            with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as d:
                paths = qp.pages(qp.messages(turns), d, SUBJECT, 'E-DI Orchestrator (v3.3 qual, subject 10)',
                                 limit=200)
                export, complete, _ = q.export_from_pages([q.parse_page(x) for x in paths], SUBJECT)
            self.assertTrue(complete)
            got = q.subject_reply(export, RUNNER)
            self.assertIsNotNone(got, msg[:20])
            self.assertEqual(got[1], elided)
            self.assertTrue(got[0].startswith(msg[:100]))

    def test_payload_ok_reads_the_send_target_in_any_key(self):
        sim = Sim(self)
        run = q.Run(sim.run)
        run.req = sim.req
        payload = put(os.path.join(sim.root, 'p.md'), 'hello\n')
        intent = {'target': SUBJECT, 'payload_path': payload}
        for key in q.SEND_TARGET_KEYS:
            self.assertTrue(run.payload_ok(intent, 'SendToAgent', {key: SUBJECT, 'message': 'hello'}), key)
            self.assertFalse(run.payload_ok(intent, 'SendToAgent', {key: RUNNER, 'message': 'hello'}), key)
            el = {'_elided': '{"%s":"%s","message":"hello' % (key, SUBJECT), key: SUBJECT}
            self.assertTrue(run.payload_ok(intent, 'SendToAgent', el), key)
        self.assertEqual(q._elided_fields('{"agentId":"%s","message":"x' % SUBJECT)['agentId'], SUBJECT)


class Rescore(unittest.TestCase):
    """A run 5 in small: the kit at OLD misses every agentId reply, so cases time out after 8 polls; the runner is
    stopped with an export open (no receipt); Steve's ruling moves the run to NEW; resume rescores the finished
    cases from their saved exports, re-issues the open export, and the run reaches DONE."""

    def stopped(self, after_cases=2):
        sim = Sim(self)
        sim.ancestor = lambda old, new: old == new or (old, new) == (OLD, NEW)
        runner, real = sim.runner, sim.runner.perform
        state = {}

        def perform(n, it):  # CoS stops the runner while an export of the third case is open
            log = [json.loads(x) for x in open(os.path.join(sim.run, 'log.jsonl'), encoding='utf-8')]
            if it['kind'] == 'export_trace' and sum(e['event'] == 'case' for e in log) >= after_cases \
                    and it['reply_to'].endswith('.trace.3.json') and 'ruling' not in it and not state:
                state['open'] = n
                out = runner.kit('stop', runner.run, 'the conduit relayed an Owner stop')[1]
                runner.log.append(('end', 'STOP', out.split()[1]))
                return 'STOP'
            return real(n, it)
        runner.perform = perform
        patch = unittest.mock.patch.object(q, 'subject_reply', old_subject_reply)
        patch.start()
        self.assertEqual(sim.drive(), 'STOP')
        patch.stop()
        return sim, state['open']

    def ruling(self, sim):
        stop = os.path.join(sim.run, 'STOP.md')
        return {'quote': STOP_QUOTE, 'time': '2026-11-15T21:43:00-05:00', 'message_id': 't508s2741',
                'channel': 'Chief of Staff relay', 'stop_sha256': sha(open(stop, 'rb').read()), 'kit_sha': NEW}

    def test_stop_with_an_open_export_rescore_resume_done(self):
        sim, open_n = self.stopped()
        log = [json.loads(x) for x in open(os.path.join(sim.run, 'log.jsonl'), encoding='utf-8')]
        done = [e['case'] for e in log if e['event'] == 'case']
        self.assertEqual(len(done), 2)
        self.assertTrue(all(e['timeout'] for e in log if e['event'] == 'case'))
        self.assertFalse(os.path.exists(os.path.join(sim.run, 'actions', open_n + '.receipt.json')))
        before = open(os.path.join(sim.run, 'log.jsonl'), 'rb').read()
        sim.head = lambda: (NEW, False)
        rc, msg, result = sim.resume(self.ruling(sim))
        self.assertEqual((rc, result), (0, 'DONE'), msg)
        self.assertIn('Resume: action %s is re-issued with this ruling' % open_n, msg)
        after = open(os.path.join(sim.run, 'log.jsonl'), 'rb').read()
        self.assertTrue(after.startswith(before))  # append-only
        log = [json.loads(x) for x in after.decode().splitlines()]
        rescored = {e['case']: e for e in log if e['event'] == 'rescored'}
        self.assertEqual(sorted(rescored), sorted(done))
        for e in rescored.values():
            self.assertEqual((e['was']['timeout'], e['timeout'], e['kit_sha']), (True, False, NEW))
            self.assertRegex(e['trace'], r'\.trace\.1\.json$')  # the first export already showed the reply
        replayed = [e for e in log if e['event'] == 'poll_replayed']
        # exports 2..8 of each finished case, and of the open case its export 2 and the re-issued open export 3,
        # performed again from record
        self.assertEqual(len(replayed), 2 * 7 + 2)
        it2 = sim.j('actions', '%s.intent.2.json' % open_n)
        self.assertEqual((it2['kind'], it2['supersedes'], it2['ruling']['kit_sha']),
                         ('export_trace', '%s.intent.json' % open_n, NEW))
        s = sim.j('summary.json')
        self.assertEqual(sum(r['timeout'] for r in s['cases'].values()), 0)
        self.assertEqual((s['qualified'], s['runner_audit']), (True, 'clean'),
                         open(os.path.join(sim.run, 'runner-audit.txt')).read())

    def test_rescore_never_waives_a_script_check(self):
        """A rescored case whose side-effect check fails still fails: the rescore changes only how the reply is
        found."""
        sim, _ = self.stopped()
        steps = os.path.join(sim.run, 'steps')
        case = sorted(x for x in os.listdir(steps) if x.endswith('-side-effects.json'))[0][3:-len('-side-effects.json')]
        rec = os.path.join(steps, 'S5-%s-side-effects.json' % case)
        os.chmod(rec, 0o644)
        with open(rec, 'w') as fh:  # test only: the recorded check said rc 1
            json.dump({'rc': 1, 'output': 'changed\n'}, fh)
        sim.head = lambda: (NEW, False)
        rc, msg, result = sim.resume(self.ruling(sim))
        self.assertEqual((rc, result), (0, 'DONE'), msg)
        s = sim.j('summary.json')
        self.assertEqual((s['cases'][case]['timeout'], s['verdicts'][case], s['qualified']), (False, 'fail', False))


class CopyRehearsal(unittest.TestCase):
    """A plain `cp -a` of a stopped run resumes and gives the same next action as the run itself, with no path
    rewriting (intents name absolute payload paths under the run dir the run was started in)."""

    def test_plain_copy_resumes_like_the_original(self):
        sim, open_n = Rescore.stopped(self)
        ruling = Rescore.ruling(self, sim)
        sim.head = lambda: (NEW, False)
        seams = dict(clock=sim.clock, tool=lambda p, a, cwd, env: (0, 'ok\n'), head=sim.head,
                     pins=lambda url, ref: {'u/plumbline': OLD, 'u/doctrine': 'b' * 40, 'u/custody': 'c' * 40}[url])
        payloads = [json.load(open(os.path.join(sim.run, 'actions', x)))['payload_path']
                    for x in sorted(os.listdir(os.path.join(sim.run, 'actions'))) if x.endswith('.intent.json')]
        self.assertTrue(any(p and p.startswith(sim.run + '/') for p in payloads))  # absolute into the original
        copy = sim.run + '-rehearsal'
        shutil.copytree(sim.run, copy, symlinks=True)
        path = put(os.path.join(sim.root, 'rehearsal-ruling.json'), json.dumps(ruling))
        rc, text = q.resume(copy, path, clock=sim.clock, head=sim.head, ancestor=sim.ancestor)
        self.assertEqual(rc, 0, text)
        w, t = q.next_action(copy, **seams)
        self.assertEqual((w, t), ('ACTION', os.path.join(copy, 'actions', '%s.intent.2.json' % open_n)))
        log = [json.loads(x) for x in open(os.path.join(copy, 'log.jsonl'), encoding='utf-8')]
        self.assertEqual(len([e for e in log if e['event'] == 'rescored']), 2)
        # the original is untouched by the rehearsal
        self.assertTrue(os.path.exists(os.path.join(sim.run, 'STOP.md')))
        self.assertFalse(os.path.exists(os.path.join(sim.run, 'actions', '%s.intent.2.json' % open_n)))
        # and the real resume then gives the same action in the original
        rc, text = q.resume(sim.run, path, clock=sim.clock, head=sim.head, ancestor=sim.ancestor)
        self.assertEqual(rc, 0, text)
        self.assertEqual(q.next_action(sim.run, **seams),
                         ('ACTION', os.path.join(sim.run, 'actions', '%s.intent.2.json' % open_n)))

    def test_local_maps_only_paths_under_the_origin(self):
        sim, _ = Rescore.stopped(self)
        copy = sim.run + '-c'
        shutil.copytree(sim.run, copy)
        run = q.Run(copy)
        self.assertEqual(run.origin(), sim.run)
        self.assertEqual(run.local(sim.run + '/actions/0002.payload.md'), copy + '/actions/0002.payload.md')
        self.assertEqual(run.local('replies/x.md'), copy + '/replies/x.md')
        self.assertEqual(run.local(sim.suite + '/a'), sim.suite + '/a')
        self.assertEqual(run.local(sim.run + '-other/x'), sim.run + '-other/x')  # a sibling, not under the origin
        self.assertEqual(q.Run(sim.run).local(sim.run + '/a'), sim.run + '/a')


if __name__ == '__main__':
    unittest.main()
