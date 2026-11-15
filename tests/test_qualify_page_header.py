"""kit-page-header: the transcript page check against the platform's real ReadTranscript pages, and resuming run 5
at the fixed kit commit.

Run 5 (v3.3, kit pin 146a4776) stopped at S4, action 0044 export_trace for subject 01: the real page said
"positions 0\u201311 of 12" and held 11 messages, and parse_page required one line per position. The kit had passed
its dry run because tests/qualify_pages.py invented the page format. tests/fixtures/qualify/
readtranscript-subject-first-run.txt is a synthetic page with the same structure, line for line, as the real one
(same wrapper bytes, header, roles, content items, tool names, input keys, footer, no trailing newline).
"""
import datetime
import json
import os
import re
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
from test_qualify_dryrun import Sim, put, sha  # noqa: E402

FIXTURE = os.path.join(HERE, 'fixtures', 'qualify', 'readtranscript-subject-first-run.txt')
SUBJECT = '00000000-0000-4000-8000-000000010005'
OLD, NEW, OTHER = 'a' * 40, 'b' * 40, 'c' * 40
RUN5_QUOTE = ('Have the Architect fix the transcript page check to accept the platform\'s real page header, in a way '
              'that lets run 5 resume from this stop, then resume run 5')


def run4_style_parse(path):
    """parse_page as it was at 146a4776: one JSON line per position, else refuse (the check run 5 stopped on)."""
    text = open(path, encoding='utf-8').read()
    m = re.search(r'^Transcript of .*positions (\d+)\s*[\u2013-]\s*(\d+) of (\d+):\s*$', text, re.M)
    n = sum(1 for x in text[m.end():].splitlines() if x.strip().startswith('{'))
    if n != int(m.group(2)) - int(m.group(1)) + 1:
        raise q.TraceError('page %s says positions %s-%s but holds %d messages' % (path, m.group(1), m.group(2), n))
    return REAL_PARSE(path)


REAL_PARSE = q.parse_page


class Folder(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(d.cleanup)
        self.dir = d.name

    def page(self, data):
        """A page file as write_to_file saves it: named by the sha256 of its bytes."""
        data = data if isinstance(data, bytes) else data.encode('utf-8')
        return put(os.path.join(self.dir, sha(data) + '.txt'), data)

    def fixture(self):
        with open(FIXTURE, 'rb') as fh:
            return fh.read()


class RealPage(Folder):
    def test_the_real_page_shape_is_accepted_and_counted_honestly(self):
        raw = self.fixture()
        self.assertFalse(raw.endswith(b'\n'))
        self.assertTrue(raw.startswith(b'<cursor_untrusted_data_' + b'1337 source="ReadTranscript">\n\n'))
        pg = q.parse_page(self.page(raw))
        self.assertEqual((pg['kind'], pg['id'], pg['a'], pg['b'], pg['of'], len(pg['msgs']), pg['start']),
                         ('page', SUBJECT, 0, 11, 12, 11, True))
        self.assertEqual(pg['unreadable'], 1)  # 12 positions, 11 shown: position 0 (the bot's setup) is not readable
        self.assertEqual([m['role'] for m in pg['msgs']], ['user', 'user', 'assistant', 'tool', 'tool', 'assistant',
                                                          'tool', 'assistant', 'tool', 'assistant', 'tool'])
        export, complete, _ = q.export_from_pages([pg], SUBJECT)
        self.assertTrue(complete and export['start_of_transcript'])
        self.assertEqual((export['positions'], export['of'], export['messages'], export['unreadable_positions']),
                         ([0, 11], 12, 11, 1))
        self.assertEqual([e['tool'] for e in export['events']], ['SendToUser', 'Shell', 'Shell', 'Shell', 'SendToUser'])
        self.assertTrue(all(e['first_run'] and e['at'] == '2026-11-15T18:05:00-05:00' for e in export['events']))

    def test_the_check_run_5_stopped_on_refuses_this_page(self):
        with self.assertRaises(q.TraceError) as e:
            run4_style_parse(self.page(self.fixture()))
        self.assertIn('says positions 0-11 but holds 11 messages', str(e.exception))

    def test_what_the_page_check_still_refuses(self):
        raw = self.fixture().decode('utf-8')
        lines = raw.split('\n')
        line = lines[4]
        cases = {
            'holds 13 messages': raw.replace(line, line + '\n' + line + '\n' + line),
            'role \'system\'': raw.replace('{"role":"tool"', '{"role":"system"', 1),
            'ends with \'Older messages remain': raw.replace('This is the start of the transcript.', 'Older messages '
                                                            'remain: call ReadTranscript again with the same in '
                                                            'and before=0.'),
            'is not part of a ReadTranscript page': raw.replace(line, line + '\nsomething else'),
            'does not close it': raw.rsplit('\n', 1)[0],
            'no "Transcript of': raw.replace('positions 0\u201311', 'positions 0-11'),  # the platform uses an en dash
            'is not JSON': raw.replace(line, line[:-5]),
        }
        for words, text in cases.items():
            with self.subTest(words=words):
                with self.assertRaises(q.TraceError) as e:
                    q.parse_page(self.page(text))
                self.assertIn(words, str(e.exception))
        with self.assertRaises(q.TraceError) as e:
            q.parse_page(put(os.path.join(self.dir, 'renamed.txt'), self.fixture()))
        self.assertIn('its name is not the sha256 of its bytes', str(e.exception))
        later = raw.replace('positions 0\u201311 of 12', 'positions 5\u201311 of 12').replace(
            'This is the start of the transcript.', 'Older messages remain: call ReadTranscript again with the same '
            'in and before=6.')
        with self.assertRaises(q.TraceError) as e:
            q.parse_page(self.page(later))
        self.assertIn("ends with 'Older messages remain", str(e.exception))


class Paging(Folder):
    """Pages join by their header ranges, newest to oldest, and must reach the start."""

    def pages(self, limit, hidden_at=()):
        at = datetime.datetime(2026, 11, 15, 18, 5, tzinfo=datetime.timezone(datetime.timedelta(hours=-5)))
        msgs = qp.messages([('first', at, '', [{'text': 'line %d' % i} for i in range(20)])], hidden_at)
        paths = qp.pages(msgs, self.dir, SUBJECT, 'subject', limit=limit)
        return msgs, [q.parse_page(p) for p in paths]

    def test_pages_join_and_unreadable_positions_are_counted(self):
        msgs, pgs = self.pages(5, hidden_at=(7, 12))
        self.assertEqual(len(msgs), 25)  # 22 messages + position 0 + two unreadable ones
        export, complete, _ = q.export_from_pages(pgs, SUBJECT)
        self.assertTrue(complete)
        self.assertEqual((export['positions'], export['messages'], export['unreadable_positions']), ([0, 24], 22, 3))
        self.assertEqual([e['text'] for e in export['events']], ['line %d' % i for i in range(20)])
        # newest page alone: not complete, MORE before its A
        export, complete, low = q.export_from_pages(pgs[:1], SUBJECT)
        self.assertEqual((complete, low), (False, pgs[0]['a']))

    def test_a_gap_or_a_page_that_is_not_the_newest_is_refused(self):
        _, pgs = self.pages(5)
        with self.assertRaises(q.TraceError) as e:
            q.export_from_pages([pgs[0], pgs[2]], SUBJECT)
        self.assertIn('do not join', str(e.exception))
        with self.assertRaises(q.TraceError) as e:
            q.export_from_pages(pgs[1:], SUBJECT)
        self.assertIn('it is not the newest page', str(e.exception))

    def test_a_no_readable_messages_page_ends_the_chain(self):
        msgs, _ = self.pages(5)
        who = qp.who(SUBJECT, 'subject')
        p1 = q.parse_page(self.page(qp.page_text(msgs, 1, len(msgs) - 1, who)))
        none = self.page(qp.page_text(msgs, 0, 0, who))
        self.assertIn(b'No readable messages in agent "subject" (%s) before position 1.' % SUBJECT.encode(),
                      open(none, 'rb').read())
        pn = q.parse_page(none)
        export, complete, _ = q.export_from_pages([p1, pn], SUBJECT)
        self.assertTrue(complete)
        self.assertEqual((export['positions'][0], export['unreadable_positions']), (0, 1))
        wrong = self.page(qp.page_text(msgs, 0, 0, who).replace(b'position 1.', b'position 3.'))
        with self.assertRaises(q.TraceError):
            q.export_from_pages([p1, q.parse_page(wrong)], SUBJECT)


class SimShape(Folder):
    def test_the_simulator_emits_the_real_shape(self):
        sim = Sim(self)
        sim.drive()
        folder = os.path.join(sim.root, 'tool-results', sim.runner_id)
        names = sorted(os.listdir(folder))
        self.assertTrue(names)
        for name in names:
            raw = open(os.path.join(folder, name), 'rb').read()
            self.assertEqual(name, sha(raw) + '.txt')
            self.assertTrue(raw.startswith(b'<cursor_untrusted_data_' + b'1337 source="ReadTranscript">\n\n'))
            self.assertFalse(raw.endswith(b'\n'))
            pg = q.parse_page(os.path.join(folder, name))
            if pg['kind'] == 'page' and pg['a'] == 0:
                self.assertGreaterEqual(pg['unreadable'], 1)
        s = sim.j('summary.json')
        self.assertEqual((s['qualified'], s['runner_audit']), (True, 'clean'))
        self.assertIn('not audited: 1 transcript position(s)', open(os.path.join(sim.run, 'runner-audit.txt')).read())


class Run5Resume(unittest.TestCase):
    """Run 5 again: the kit at OLD refuses subject 01's real-shaped page at 0044 and stops; Steve's ruling moves the
    run to NEW (a descendant of OLD) and resume, run by the kit at NEW, re-issues 0044; the run reaches DONE."""

    def stopped(self):
        sim = Sim(self)
        sim.ancestor = lambda old, new: old == new or (old, new) == (OLD, NEW)
        patch = unittest.mock.patch.object(q, 'parse_page', run4_style_parse)
        patch.start()
        self.assertEqual(sim.drive(), 'STOP')
        patch.stop()
        return sim

    def test_stop_at_0044_ruling_at_a_new_kit_commit_resume_done(self):
        sim = self.stopped()
        stop = os.path.join(sim.run, 'STOP.md')
        text = open(stop, encoding='utf-8').read()
        self.assertIn('- Stage: S4', text)
        self.assertIn('trace on that file exited 2 with REFUSED 0044: page', text)
        self.assertRegex(text, r'says positions 0-\d+ but holds \d+ messages')
        intent = sim.j('actions', '0044.intent.json')
        self.assertEqual((intent['kind'], intent['target']), ('export_trace', SUBJECT))
        self.assertFalse(os.path.exists(os.path.join(sim.run, 'actions', '0044.receipt.json')))
        stop_sha = sha(open(stop, 'rb').read())
        good = {'quote': RUN5_QUOTE, 'time': '2026-11-15T18:28:00-05:00', 'message_id': 't5xxs0000',
                'channel': 'Chief of Staff relay', 'stop_sha256': stop_sha, 'kit_sha': NEW}
        sim.head = lambda: (NEW, False)  # the conduit checked the kit folder out at the merge of the fix
        refusals = (
            ({k: v for k, v in good.items() if k != 'kit_sha'}, 'carries "kit_sha"'),
            (dict(good, kit_sha=OTHER), 'run resume from the kit checked out at kit_sha'),
            (dict(good, kit_sha=NEW[:12]), 'full 40-hex'),
        )
        for bad, words in refusals:
            rc, out, _ = sim.resume(bad)
            self.assertEqual(rc, 2, out)
            self.assertIn(words, out)
            self.assertTrue(os.path.exists(stop))
        sim.ancestor = lambda old, new: False
        rc, out, _ = sim.resume(good)
        self.assertEqual(rc, 2)
        self.assertIn('does not descend from the pin in force %s' % OLD, out)
        sim.ancestor = lambda old, new: old == new or (old, new) == (OLD, NEW)
        rc, msg, result = sim.resume(good)
        self.assertEqual((rc, result), (0, 'DONE'), msg)
        self.assertIn('Resume: action 0044 is re-issued with this ruling', msg)
        self.assertIn('(checked out at %s)' % NEW, msg)
        r = sim.j('rulings', 'ruling-01.json')
        self.assertEqual((r['kit_sha'], r['kit_from'], r['action'], r['stop_file']), (NEW, OLD, '0044', 'STOP-01.md'))
        it2 = sim.j('actions', '0044.intent.2.json')
        self.assertEqual((it2['supersedes'], it2['ruling']['kit_sha'], it2['ruling']['stop_sha256']),
                         ('0044.intent.json', NEW, stop_sha))
        self.assertTrue(sim.j('steps', 'trace-0044.json')['complete'])
        log = [json.loads(x) for x in open(os.path.join(sim.run, 'log.jsonl'), encoding='utf-8')]
        resumed = [e for e in log if e['event'] == 'resumed']
        self.assertEqual((resumed[0]['kit_sha'], resumed[0]['kit_from']), (NEW, OLD))
        s = sim.j('summary.json')
        self.assertEqual((s['qualified'], s['runner_audit']), (True, 'clean'),
                         open(os.path.join(sim.run, 'runner-audit.txt')).read())
        # S0-head.json still records the first start at OLD; the ruling is what moved the pin
        self.assertEqual(sim.j('steps', 'S0-head.json')['sha'], OLD)

    def test_after_the_move_next_at_the_old_commit_stops(self):
        sim = self.stopped()
        stop = os.path.join(sim.run, 'STOP.md')
        sim.head = lambda: (NEW, False)
        ruling = {'quote': RUN5_QUOTE, 'time': '2026-11-15T18:28:00-05:00', 'message_id': 't5xxs0000',
                  'channel': 'Chief of Staff relay', 'stop_sha256': sha(open(stop, 'rb').read()), 'kit_sha': NEW}
        path = put(os.path.join(sim.root, 'r.json'), json.dumps(ruling))
        self.assertEqual(q.resume(sim.run, path, clock=sim.clock, head=sim.head, ancestor=sim.ancestor)[0], 0)
        w, t = q.next_action(sim.run, clock=sim.clock, head=lambda: (OLD, False),
                             tool=lambda p, a, cwd, env: (0, 'ok\n'),
                             pins=lambda url, ref: {'u/plumbline': OLD, 'u/doctrine': 'b' * 40,
                                                    'u/custody': 'c' * 40}[url])
        self.assertEqual(w, 'STOP')
        text = open(t, encoding='utf-8').read()
        self.assertIn('is at %s, but the run is pinned to %s (rulings/ruling-01.json)' % (OLD, NEW), text)

    def test_resume_at_the_pin_needs_no_kit_sha(self):
        sim = self.stopped()
        stop = os.path.join(sim.run, 'STOP.md')
        ruling = {'quote': RUN5_QUOTE, 'time': '2026-11-15T18:28:00-05:00', 'message_id': 't5xxs0000',
                  'channel': 'Chief of Staff relay', 'stop_sha256': sha(open(stop, 'rb').read())}
        rc, msg, result = sim.resume(ruling)  # same kit commit as the request pin, now with the fixed page check
        self.assertEqual((rc, result), (0, 'DONE'), msg)
        self.assertNotIn('kit_sha', sim.j('rulings', 'ruling-01.json'))


if __name__ == '__main__':
    unittest.main()
