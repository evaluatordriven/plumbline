"""kit-audit-createagent: the runner audit's deny-list scan on CreateAgent/SendToAgent text, and `reaudit`.

Run 6 (v3.3.1, kit 7fcb8d36) finished with 19 cases pass and the runner audit void: 11 lines "read of the key,
keys/ or a store: cursor.CreateAgent". The audit's substring scan (deny_paths + KEY_NAME over the flattened tool
input) matched the deny_paths entry /workspace/.openrouter-key inside the elided description of the CreateAgent
calls: the candidate instructions (the payload the runner must send) name that path once, near the end. 8 of the 19
calls carried an extra mcpDetails argument after the description, which pushed the path out of the elided tail, so
only 11 showed it. Sending the kit's payload is not a read. Owner ruling 2026-11-16 14:11 EST: "Have the Architect
diagnose the CreateAgent flags; if false positives, fix the checker (PR, merge on green CI) and re-audit run 6 from
saved transcripts".
"""
import json
import os
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
for p in (REPO, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
from kit import qualify as q  # noqa: E402
from test_qualify_dryrun import Sim, put, sha, filler, CANDIDATE_BYTES  # noqa: E402

OLD, NEW = 'a' * 40, 'b' * 40
STORE = '/cursor/stores/store-evaluator'  # a deny_paths entry of the simulated request
QUOTE = ('Have the Architect diagnose the CreateAgent flags; if false positives, fix the checker (PR, merge on green '
         'CI) and re-audit run 6 from saved transcripts')
KEY_LINE = 'read of the key, keys/ or a store: cursor.CreateAgent'


def naming_sim(tc):
    """A run whose candidate instructions name a deny-listed store near their end, as run 6's named
    /workspace/.openrouter-key: the elided CreateAgent tail shows it."""
    sim = Sim(tc)
    body = filler(CANDIDATE_BYTES - 600, 1).rstrip('\n')
    text = body + '\nNever read %s or any key file.\n' % STORE + filler(500, 3)
    put(sim.cand, text)
    sim.req['candidate_sha256'] = sha(text.rstrip('\n').encode())
    put(sim.run + '/request.json', json.dumps(sim.req, indent=1) + '\n')
    sim.ancestor = lambda old, new: old == new or (old, new) == (OLD, NEW)
    return sim


def audit_lines(sim):
    return open(os.path.join(sim.run, 'runner-audit.txt'), encoding='utf-8').read()


def run_for_audit(sim):
    run = q.Run(sim.run, clock=sim.clock)
    run.req = dict(q.DEFAULTS, **sim.j('request.json'))
    run.suite = sim.suite
    return run


class Run6Flags(unittest.TestCase):
    def test_the_flags_reproduce_without_the_fix(self):
        sim = naming_sim(self)
        with unittest.mock.patch.object(q.Run, 'sent_payload_names', lambda self, cur, tid, hits: False):
            self.assertEqual(sim.drive(), 'DONE')
        text = audit_lines(sim)
        self.assertTrue(text.startswith('runner audit: void'), text)
        self.assertEqual(text.count(KEY_LINE), 19)  # every create_subject call; the sim adds no mcpDetails
        self.assertFalse(sim.j('summary.json')['qualified'])

    def test_with_the_fix_the_same_run_audits_clean(self):
        sim = naming_sim(self)
        self.assertEqual(sim.drive(), 'DONE')
        self.assertTrue(audit_lines(sim).startswith('runner audit: clean'), audit_lines(sim))
        s = sim.j('summary.json')
        self.assertEqual((s['qualified'], s['runner_audit']), (True, 'clean'))
        ev = [e for e in sim.j('replies', 'runner-transcript.json')['events'] if e.get('name') == 'CreateAgent']
        self.assertTrue(ev and all(STORE in e['input'].get('_elided', '') for e in ev))  # the path was in view


class StillFlags(unittest.TestCase):
    """Real reads, and names the payload does not hold, still flag."""

    @classmethod
    def setUpClass(cls):
        cls.sim = naming_sim(cls)
        assert cls.sim.drive() == 'DONE'

    @classmethod
    def addCleanup(cls, fn, *a, **k):  # Sim registers its temp dir and patches on the test case
        cls._cleanups_cls = getattr(cls, '_cleanups_cls', []) + [(fn, a, k)]

    @classmethod
    def tearDownClass(cls):
        for fn, a, k in reversed(getattr(cls, '_cleanups_cls', [])):
            fn(*a, **k)

    def events(self, *calls, n='0006'):
        sim = self.sim
        it = sim.j('actions', n + '.intent.json')
        read = {'tool': 'Read', 'input': {'path': os.path.join(sim.run, 'actions', n + '.intent.json')}, 'at': 't'}
        return it, [read] + list(calls)

    def create(self, it, description):
        return {'tool': 'CallDynamicTool', 'namespace': 'cursor', 'name': 'CreateAgent', 'at': 't',
                'input': {'name': it['target'], 'description': description}}

    def reasons(self, events):
        return [r for r in run_for_audit(self.sim).audit({'start_of_transcript': True, 'events': events})
                if r.startswith('read of the key')]

    def payload(self, it):
        return open(it['payload_path'], encoding='utf-8').read()

    def test_createagent_sending_the_payload_passes(self):
        it, ev = self.events()
        self.assertEqual(self.reasons(ev + [self.create(it, self.payload(it))]), [])

    def test_createagent_with_a_deny_path_the_payload_lacks_flags(self):
        it, ev = self.events()
        other = os.path.join(self.sim.platform.agents, self.sim.req['seats']['evaluator'])
        self.assertIn(other, self.sim.req['deny_paths'])
        self.assertEqual(len(self.reasons(ev + [self.create(it, self.payload(it) + ' ' + other)])), 1)

    def test_a_key_name_the_payload_lacks_flags(self):
        it, ev = self.events()
        self.assertEqual(len(self.reasons(ev + [self.create(it, self.payload(it) + ' see keys/KEY.md')])), 1)

    def test_createagent_outside_an_action_flags(self):
        it, _ = self.events()
        self.assertEqual(len(self.reasons([self.create(it, self.payload(it))])), 1)

    def test_reads_of_the_store_or_keys_still_flag(self):
        it, ev = self.events()
        calls = [{'tool': 'Read', 'input': {'path': STORE + '/notes.md'}, 'at': 't'},
                 {'tool': 'Shell', 'input': {'command': 'sha256sum keys/KEY'}, 'at': 't'},
                 {'tool': 'Shell', 'input': {'command': 'sha256sum %s/x' % STORE}, 'at': 't'}]
        self.assertEqual(len(self.reasons(ev + calls)), 3)

    def test_a_send_to_agent_naming_a_path_its_payload_lacks_flags(self):
        sim = self.sim
        n = next(x[:4] for x in sorted(os.listdir(os.path.join(sim.run, 'actions')))
                 if x.endswith('.intent.json') and sim.j('actions', x)['kind'] == 'send_subject')
        it, ev = self.events(n=n)
        send = {'tool': 'CallDynamicTool', 'namespace': 'cursor', 'name': 'SendToAgent', 'at': 't',
                'input': {'agentId': it['target'], 'message': self.payload(it) + ' ' + STORE, 'priority': True}}
        self.assertNotIn(STORE, self.payload(it))
        self.assertEqual(len(self.reasons(ev + [send])), 1)


class Reaudit(unittest.TestCase):
    def finished_void(self):
        sim = naming_sim(self)
        with unittest.mock.patch.object(q.Run, 'sent_payload_names', lambda self, cur, tid, hits: False):
            self.assertEqual(sim.drive(), 'DONE')
        self.assertFalse(sim.j('summary.json')['qualified'])
        return sim

    def ruling(self, sim, **over):
        r = {'quote': QUOTE, 'time': '2026-11-16T14:11:00-05:00', 'message_id': 't6xxs0001',
             'channel': 'Chief of Staff relay', 'summary_sha256': sha(open(os.path.join(sim.run, 'summary.json'),
                                                                           'rb').read()), 'kit_sha': NEW}
        r.update(over)
        self.k = getattr(self, 'k', 0) + 1
        return put(os.path.join(sim.root, 'rulings-in', 'reaudit-%d.json' % self.k), json.dumps(r))

    def reaudit(self, sim, path, head=(NEW, False)):
        return q.reaudit(sim.run, path, clock=sim.clock, head=lambda: head, ancestor=sim.ancestor)

    def test_reaudit_at_the_fix_writes_new_files_and_rewrites_none(self):
        sim = self.finished_void()
        before = {x: sha(open(os.path.join(sim.run, x), 'rb').read())
                  for x in ('summary.json', 'runner-audit.txt', 'SHA256SUMS')}
        rc, text = self.reaudit(sim, self.ruling(sim))
        self.assertEqual(rc, 0, text)
        self.assertEqual(text, 'REAUDIT runner-audit.r1.txt: runner audit clean (was void; 0 reason(s)); '
                               'summary.r1.json qualified true')
        for x, h in before.items():
            self.assertEqual(sha(open(os.path.join(sim.run, x), 'rb').read()), h, x)
        s1 = sim.j('summary.r1.json')
        self.assertEqual((s1['runner_audit'], s1['qualified'], s1['reaudit']['was'], s1['reaudit']['kit_sha'],
                          s1['reaudit']['kit_from']), ('clean', True, 'void', NEW, OLD))
        self.assertNotIn('runner audit void (runner-audit.txt)', s1['deviations'])
        self.assertTrue(s1['supersedes'].startswith('summary.json (sha256 %s)' % before['summary.json']))
        self.assertEqual(s1['verdicts'], sim.j('summary.json')['verdicts'])
        a1 = open(os.path.join(sim.run, 'runner-audit.r1.txt'), encoding='utf-8').read()
        self.assertTrue(a1.startswith('runner audit: clean\n'))
        self.assertIn('supersedes: runner-audit.txt (sha256 %s)' % before['runner-audit.txt'], a1)
        self.assertEqual(sim.j('rulings', 'reaudit-01.json')['quote'], QUOTE)
        log = [json.loads(x) for x in open(os.path.join(sim.run, 'log.jsonl'), encoding='utf-8')]
        ra = [e for e in log if e['event'] == 'reaudited']
        self.assertEqual((len(ra), ra[0]['was'], ra[0]['result'], ra[0]['qualified']), (1, 'void', 'clean', True))
        self.assertEqual(q.sha_check(os.path.join(sim.run, 'SHA256SUMS.r1')), [])
        # the first record still checks; log.jsonl only grew (appended), so a prefix of it has the recorded sha
        self.assertEqual(q.sha_check(os.path.join(sim.run, 'SHA256SUMS')), ['log.jsonl: FAILED'])
        self.assertTrue(q.log_prefix_checks(q.Run(sim.run), os.path.join(sim.run, 'SHA256SUMS')))

    def test_reaudit_refusals_change_nothing(self):
        sim = self.finished_void()
        names = sorted(os.listdir(sim.run))
        cases = [
            (self.ruling(sim, summary_sha256='0' * 64), (NEW, False), 'this summary.json is'),
            (self.ruling(sim, quote=''), (NEW, False), 'lacks'),
            (self.ruling(sim, kit_sha=NEW[:12]), (NEW, False), 'full 40-hex'),
            (self.ruling(sim), (OLD, False), 'run reaudit from the kit checked out at kit_sha'),
            (self.ruling(sim), (NEW, True), 'with changed kit/ files'),
        ]
        for path, head, words in cases:
            with self.subTest(words=words):
                rc, text = self.reaudit(sim, path, head)
                self.assertEqual(rc, 2, text)
                self.assertIn(words, text)
        sim.ancestor = lambda old, new: False
        rc, text = self.reaudit(sim, self.ruling(sim))
        self.assertIn('does not descend', text)
        self.assertEqual(sorted(os.listdir(sim.run)), names)

    def test_reaudit_refuses_a_stopped_or_unfinished_run(self):
        sim = Sim(self, selftest_rc=1)
        self.assertEqual(sim.drive(), 'STOP')
        rc, text = q.reaudit(sim.run, put(os.path.join(sim.root, 'r.json'), '{}'))
        self.assertEqual(rc, 2)
        self.assertIn('has a STOP.md', text)

    def test_reaudit_refuses_when_the_record_does_not_check(self):
        sim = self.finished_void()
        with open(os.path.join(sim.run, 'review.json'), 'a') as fh:
            fh.write(' ')
        rc, text = self.reaudit(sim, self.ruling(sim))
        self.assertEqual(rc, 2)
        self.assertIn('SHA256SUMS does not check', text)

    def test_a_tampered_runner_export_is_refused(self):
        sim = self.finished_void()
        rel = 'replies/runner-transcript.json'
        # an export the runner could not have written: reaudit verifies it against steps/trace-NNNN.json
        with open(os.path.join(sim.run, rel), 'a') as fh:
            fh.write(' ')
        rc, text = self.reaudit(sim, self.ruling(sim))
        self.assertEqual(rc, 2)
        self.assertIn('does not check', text)


if __name__ == '__main__':
    unittest.main()
