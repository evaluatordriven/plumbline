"""kit-export-fresh: a re-issued export_trace starts fresh, with the earlier attempt's pages set aside.

Run 6 (v3.3.1, kit f8d02244) stopped at S5, action 0101, the runner's export of its own transcript: page 14's file was
missing (STOP-01). Steve ruled a retry; resume re-issued 0101 as 0101.intent.2.json, but `trace` kept the page list
steps/trace-0101.pages.jsonl from attempt 1, so the fresh newest page (the transcript had grown) overlapped the 13
kept pages and every call refused "do not join" (STOP.md, second stop). Owner ruling 2026-11-16 12:29 EST: "Have the
Architect fix the kit so a re-issued transcript export starts fresh (keeping the old pages aside) ...".
"""
import json
import os
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
from test_qualify_dryrun import Sim, SimRunner, put, sha  # noqa: E402

OLD, NEW = 'a' * 40, 'b' * 40
MISSING = ('page 2 ReadTranscript reported writing a file but trace printed REFUSED cannot read page, No such file '
           'or directory')
RETRY = 'Resume run 6 and have the runner retry the transcript read; the missing page file was a platform hiccup'
FRESH = ('Have the Architect fix the kit so a re-issued transcript export starts fresh (keeping the old pages aside), '
         'push, PR and merge on green CI, then resume run 6 at that commit')


class Run6Runner(SimRunner):
    """The run-6 runner: on its first export of its own transcript, the second page's file is missing, so after
    the first page (MORE) it stops, as the real runner did at 0101 (STOP-01)."""

    def __init__(self, sim, bid):
        super().__init__(sim, bid)
        self.missed = False

    def perform(self, n, it):
        if it['kind'] == 'export_trace' and it['target'] == self.id and not self.missed:
            self.missed = True
            res = self.dyn('ReadTranscript', {'limit': 200}, write_to_file=True)
            out = self.kit('trace', self.run, n, res.split(': ', 1)[1])[1].split()
            assert out[0] == 'MORE', out  # the runner transcript is longer than one page
            self.dyn('ReadTranscript', {'limit': 200, 'before': int(out[2].split('=')[1])}, write_to_file=True)
            stop = self.kit('stop', self.run, MISSING)[1]
            self.record('SendToUser', {'type': 'text', 'content': open(stop.split()[1], encoding='utf-8').read()})
            self.log.append(('end', 'STOP', stop.split()[1]))
            return 'STOP'
        return super().perform(n, it)


def run6_sim(tc):
    sim = Sim(tc)
    sim.runner = Run6Runner(sim, sim.runner_id)
    sim.ancestor = lambda old, new: old == new or (old, new) == (OLD, NEW)
    return sim


def log(sim):
    return [json.loads(x) for x in open(os.path.join(sim.run, 'log.jsonl'), encoding='utf-8')]


def ruling(sim, quote, **extra):
    stop = os.path.join(sim.run, 'STOP.md')
    return dict({'quote': quote, 'time': '2026-11-16T12:16:00-05:00', 'message_id': 't6xxs0000',
                 'channel': 'Chief of Staff relay', 'stop_sha256': sha(open(stop, 'rb').read())}, **extra)


class Run6Replay(unittest.TestCase):
    def two_stops(self):
        """Attempt 1 stops on the missing page; attempt 2 (re-issued under ruling-01) refuses as f8d02244 did."""
        sim = run6_sim(self)
        self.assertEqual(sim.drive(), 'STOP')
        n = os.path.basename(q.Run(sim.run).intent_path('%04d' % max(
            int(x[:4]) for x in os.listdir(os.path.join(sim.run, 'actions')) if x[:4].isdigit())))[:4]
        it = sim.j('actions', n + '.intent.json')
        self.assertEqual((it['kind'], it['target'], it['reply_to']),
                         ('export_trace', sim.runner_id, 'replies/runner-transcript.json'))
        self.assertIn(MISSING, open(os.path.join(sim.run, 'STOP.md'), encoding='utf-8').read())
        with unittest.mock.patch.object(q.Run, 'set_aside_trace', lambda self, n, k, intent: None):  # f8d02244
            rc, msg, result = sim.resume(ruling(sim, RETRY))
        self.assertEqual((rc, result), (0, 'STOP'), msg)
        text = open(os.path.join(sim.run, 'STOP.md'), encoding='utf-8').read()
        self.assertIn('REFUSED %s: pages' % n, text)
        self.assertIn('do not join', text)
        self.assertTrue(os.path.exists(os.path.join(sim.run, 'actions', n + '.intent.2.json')))
        return sim, n

    def test_the_second_stop_reproduces_at_the_old_kit(self):
        sim, n = self.two_stops()
        kept = [json.loads(x) for x in open(os.path.join(sim.run, 'steps', 'trace-%s.pages.jsonl' % n))]
        self.assertEqual(len(kept), 2)  # attempt 1's page, plus attempt 2's refused newest page, appended

    def test_resume_at_the_fix_reissues_fresh_and_reaches_done(self):
        sim, n = self.two_stops()
        lp = os.path.join(sim.run, 'steps', 'trace-%s.pages.jsonl' % n)
        before = open(lp, 'rb').read()
        old_shas = {json.loads(x)['sha256'] for x in before.decode().splitlines()}
        sim.head = lambda: (NEW, False)  # the conduit checked the kit folder out at the merge of the fix
        rc, msg, result = sim.resume(ruling(sim, FRESH, kit_sha=NEW))
        self.assertEqual((rc, result), (0, 'DONE'), msg)
        self.assertIn('Resume: action %s is re-issued with this ruling' % n, msg)
        r2 = sim.j('rulings', 'ruling-02.json')
        self.assertEqual((r2['action'], r2['kit_sha'], r2['kit_from'], r2['stop_file']), (n, NEW, OLD, 'STOP-02.md'))
        it3 = sim.j('actions', n + '.intent.3.json')
        self.assertEqual((it3['supersedes'], it3['ruling']['kit_sha'], it3['ruling']['quote']),
                         (n + '.intent.2.json', NEW, FRESH))
        # the old list is set aside byte for byte, named by the attempt it came from, and the move is logged
        aside = os.path.join(sim.run, 'steps', 'trace-%s.attempt-2' % n)
        self.assertEqual(sorted(os.listdir(aside)), ['trace-%s.pages.jsonl' % n])
        self.assertEqual(open(os.path.join(aside, 'trace-%s.pages.jsonl' % n), 'rb').read(), before)
        ev = [e for e in log(sim) if e['event'] in ('resumed', 'trace_set_aside', 'reissued')]
        self.assertEqual([e['event'] for e in ev], ['resumed', 'reissued', 'resumed', 'trace_set_aside', 'reissued'])
        self.assertEqual((ev[3]['action'], ev[3]['attempt'], ev[3]['moved'], ev[3]['to']),
                         (n, 2, ['steps/trace-%s.pages.jsonl' % n], 'steps/trace-%s.attempt-2' % n))
        # the export and its record count the current attempt's pages only
        rec = sim.j('steps', 'trace-%s.json' % n)
        new_shas = {x['sha256'] for x in rec['pages']}
        self.assertTrue(rec['complete'])
        self.assertFalse(new_shas & old_shas)
        self.assertEqual({json.loads(x)['sha256'] for x in open(lp)}, new_shas)
        rt = sim.j('replies', 'runner-transcript.json')
        self.assertEqual(set(rt['pages']), new_shas)
        self.assertEqual(rt['positions'][0], 0)
        s = sim.j('summary.json')
        self.assertEqual((s['qualified'], s['runner_audit']), (True, 'clean'),
                         open(os.path.join(sim.run, 'runner-audit.txt')).read())


class SetAside(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(d.cleanup)
        self.run = os.path.join(d.name, 'run')
        os.makedirs(os.path.join(self.run, 'steps'))
        self.intent = {'kind': 'export_trace', 'target': 'x', 'payload_path': None, 'payload_sha256': None,
                       'allowed_tools': [], 'reply_to': 'replies/runner-transcript.json'}

    def test_a_finished_attempt_moves_its_record_and_reply_too(self):
        files = {'steps/trace-0101.pages.jsonl': b'{"path": "p", "sha256": "s"}\n',
                 'steps/trace-0101.json': b'{"export_sha256": "e"}\n', 'replies/runner-transcript.json': b'{}\n'}
        for rel, data in files.items():
            put(os.path.join(self.run, rel), data)
        run = q.Run(self.run)
        run.set_aside_trace('0101', 1, self.intent)
        aside = os.path.join(self.run, 'steps', 'trace-0101.attempt-1')
        for rel, data in files.items():
            self.assertFalse(os.path.exists(os.path.join(self.run, rel)))
            self.assertEqual(open(os.path.join(aside, os.path.basename(rel)), 'rb').read(), data)
        line = json.loads(open(os.path.join(self.run, 'log.jsonl')).read())
        self.assertEqual((line['event'], line['attempt'], sorted(line['moved'])),
                         ('trace_set_aside', 1, sorted(files)))

    def test_nothing_kept_moves_nothing_and_logs_nothing(self):
        q.Run(self.run).set_aside_trace('0101', 1, self.intent)
        self.assertEqual(os.listdir(os.path.join(self.run, 'steps')), [])
        self.assertFalse(os.path.exists(os.path.join(self.run, 'log.jsonl')))

    def test_an_existing_set_aside_is_never_overwritten(self):
        put(os.path.join(self.run, 'steps', 'trace-0101.pages.jsonl'), b'new\n')
        put(os.path.join(self.run, 'steps', 'trace-0101.attempt-1', 'trace-0101.pages.jsonl'), b'old\n')
        with self.assertRaises(q.Stop):
            q.Run(self.run).set_aside_trace('0101', 1, self.intent)
        self.assertEqual(open(os.path.join(self.run, 'steps', 'trace-0101.attempt-1', 'trace-0101.pages.jsonl'),
                              'rb').read(), b'old\n')

    def test_only_export_trace_is_set_aside_on_reissue(self):
        put(os.path.join(self.run, 'rulings', 'ruling-01.json'), json.dumps({'action': '0006', 'quote': 'q'}))
        it = dict(self.intent, kind='create_subject', target='subject 01')
        put(os.path.join(self.run, 'actions', '0006.intent.json'), json.dumps(it))
        put(os.path.join(self.run, 'steps', 'trace-0006.pages.jsonl'), b'x\n')  # not this action's kind: untouched
        with unittest.mock.patch.object(q.Run, 'set_aside_trace', side_effect=AssertionError('called')):
            self.assertTrue(q.Run(self.run).reissue('0006', it).endswith('0006.intent.2.json'))
        self.assertTrue(os.path.exists(os.path.join(self.run, 'steps', 'trace-0006.pages.jsonl')))


class FirstAttempt(unittest.TestCase):
    """The join check is not loosened: within one attempt, overlapping pages still refuse."""

    def test_overlapping_pages_in_one_attempt_still_refuse(self):
        sim = Sim(self)
        d = os.path.join(sim.root, 'pages')
        msgs = qp.messages([('first', sim.clock(), '', [{'text': 'line %d' % i} for i in range(30)])])
        who = qp.who(sim.runner_id, 'runner')
        put(os.path.join(sim.run, 'actions', '0001.intent.json'), json.dumps(
            {'kind': 'export_trace', 'target': sim.runner_id, 'payload_path': None, 'payload_sha256': None,
             'allowed_tools': [], 'reply_to': 'replies/t.json'}))
        top = qp.save_page(d, qp.page_text(msgs, 20, len(msgs) - 1, who))
        overlap = qp.save_page(d, qp.page_text(msgs, 10, 24, who))
        self.assertEqual(q.trace(sim.run, '0001', [top])[1], 'MORE 0001 before=20')
        rc, text = q.trace(sim.run, '0001', [overlap])
        self.assertEqual(rc, 2)
        self.assertIn('do not join', text)


if __name__ == '__main__':
    unittest.main()
