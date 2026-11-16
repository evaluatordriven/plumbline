"""kit-small-gaps: the runner audit is final before S6 scores (G1), and `next` on a finished run names the latest
summary (G2). Owner word, relayed by Chief of Staff 2026-11-16 16:07 EST: "Yes, have the architect close small
gaps".

G1: a void runner audit stops at the end of S5 for an Owner ruling, so the Evaluator never scores against a void
audit nobody ruled on. A ruling on that stop re-runs the audit at the kit the ruling pins, from the same saved
runner export, as runner-audit.rK.txt (runner-audit.txt is never rewritten), and S6 sends the latest audit. Still
void stops again, unless the ruling carries "audit_void": "accept". `reaudit` of a finished run records what S6's
request carried (evaluator_saw_audit).
G2: `next` on a finished run prints DONE with the highest summary.rK.json (K as a number), else summary.json.

Synthetic runs only (test_qualify.World, test_qualify_dryrun.Sim); no network, no model, no bot.
"""
import contextlib
import io
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
for p in (REPO, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
from kit import qualify as q  # noqa: E402
from test_qualify import World, put, read, sha  # noqa: E402
from test_qualify_audit_createagent import naming_sim, pre_g1  # noqa: E402

OLD, NEW = 'a' * 40, 'b' * 40
QUOTE = 'Yes, have the architect close small gaps'
FLAG = 'synthetic false positive'


def flagged():
    """The audit as an old kit with a false positive ran it: one reason, so the audit is void."""
    return mock.patch.object(q.Run, 'audit', lambda self, tr: [FLAG])


def tree(root):
    """{relative path: sha256} of every file under root."""
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            out[os.path.relpath(p, root)] = sha(read(p))
    return out


def evaluator_sends(w):
    d = w.p('actions')
    return [x for x in sorted(os.listdir(d)) if x.endswith('.intent.json')
            and json.loads(read(os.path.join(d, x)))['kind'] == 'send_seat'
            and json.loads(read(os.path.join(d, x)))['target'] == 'evaluator-bot']


def s6_audit_line(w):
    return next(x for x in read(w.p('S6.request.md')).decode().splitlines() if x.startswith('Runner audit: '))


class G1(unittest.TestCase):
    def world(self):
        w = World(self).start()
        w.ancestor = lambda old, new: old == new or (OLD.startswith(old) and new == NEW)  # request pins 12 hex
        return w

    def stopped_void(self, w):
        with flagged():
            w.stopped('S5', '- Failing check: ' + q.AUDIT_STOP, 'runner-audit.txt')
        return sha(read(w.p('runner-audit.txt')))

    def ruling(self, w, **over):
        r = {'quote': QUOTE, 'time': '2026-11-16T16:07:00-05:00', 'message_id': 't533u',
             'channel': 'Chief of Staff relay', 'stop_sha256': sha(read(w.p('STOP.md')))}
        r.update(over)
        self.k = getattr(self, 'k', 0) + 1
        return put(os.path.join(w.root, 'rulings-in', 'ruling-%d.json' % self.k), json.dumps(r))

    def resume(self, w, path, head=(OLD, False)):
        return q.resume(w.run, path, clock=w.clock, head=lambda: head, ancestor=w.ancestor)

    def test_a_void_audit_stops_before_s6_and_no_s6_request_is_sent(self):
        w = self.world()
        self.stopped_void(w)
        self.assertIn('runner audit: void\n- %s\n' % FLAG, read(w.p('runner-audit.txt')).decode())
        self.assertFalse(os.path.exists(w.p('S6.request.md')))
        self.assertEqual(len(evaluator_sends(w)), 1)  # S2 only
        self.assertFalse(os.path.exists(w.p('summary.json')))
        self.assertEqual(q.next_action(w.run, clock=w.clock, tool=w.tool, pins=w.pins, head=w.head)[0], 'STOP')

    def test_a_clean_audit_goes_straight_to_s6(self):
        w = self.world()
        s = w.done()
        self.assertEqual(s6_audit_line(w), 'Runner audit: clean (runner-audit.txt, sha256 %s)'
                         % sha(read(w.p('runner-audit.txt'))))
        self.assertEqual((s['runner_audit'], s['runner_audit_path'], s['qualified']), ('clean', 'runner-audit.txt',
                                                                                       True))
        self.assertEqual([x for x in os.listdir(w.run) if x.startswith(('STOP', 'runner-audit.r'))], [])

    def test_resume_at_a_new_kit_reaudits_and_s6_sends_the_rk_audit(self):
        w = self.world()
        h0 = self.stopped_void(w)
        rc, text = self.resume(w, self.ruling(w, kit_sha=NEW), head=(NEW, False))
        self.assertEqual(rc, 0, text)
        w.head = lambda: (NEW, False)
        s = w.done()
        a1 = read(w.p('runner-audit.r1.txt')).decode()
        self.assertTrue(a1.startswith('runner audit: clean\n'), a1)
        self.assertIn('supersedes: runner-audit.txt (sha256 %s)\n' % h0, a1)
        self.assertIn('re-audited at kit %s on the ruling rulings/ruling-01.json (on STOP-01.md)' % NEW, a1)
        self.assertEqual(sha(read(w.p('runner-audit.txt'))), h0)
        self.assertEqual(s6_audit_line(w), 'Runner audit: clean (runner-audit.r1.txt, sha256 %s)'
                         % sha(read(w.p('runner-audit.r1.txt'))))
        self.assertEqual((s['runner_audit'], s['runner_audit_path'], s['qualified']),
                         ('clean', 'runner-audit.r1.txt', True))
        rows = dict(x.split('  ', 1)[::-1] for x in read(w.p('SHA256SUMS')).decode().splitlines())
        self.assertEqual(rows['runner-audit.r1.txt'], sha(read(w.p('runner-audit.r1.txt'))))
        self.assertEqual(rows['runner-audit.txt'], h0)
        log = [json.loads(x) for x in read(w.p('log.jsonl')).decode().splitlines()]
        ra = [e for e in log if e['event'] == 'runner_audit']
        self.assertEqual([(e['key'], e['result']) for e in ra], [('runner_audit S5 ', 'void'),
                                                                  ('runner_audit r1', 'clean')])
        self.assertEqual((ra[1]['kit_sha'], ra[1]['supersedes']), (NEW, 'runner-audit.txt'))

    def test_still_void_after_the_ruling_stops_again(self):
        w = self.world()
        h0 = self.stopped_void(w)
        rc, text = self.resume(w, self.ruling(w))
        self.assertEqual(rc, 0, text)
        with flagged():
            stop = w.stopped('S5', '- Failing check: ' + q.AUDIT_STOP, 'runner-audit.r1.txt')
        self.assertTrue(read(w.p('runner-audit.r1.txt')).decode().startswith('runner audit: void\n- %s\n' % FLAG))
        self.assertTrue(os.path.exists(w.p('STOP-01.md')))
        self.assertFalse(os.path.exists(w.p('S6.request.md')))
        self.assertEqual(len(evaluator_sends(w)), 1)
        self.assertEqual(sha(read(w.p('runner-audit.txt'))), h0)
        self.assertIn('Stage: S5', stop)

    def test_still_void_with_audit_void_accept_scores_the_void_audit(self):
        w = self.world()
        h0 = self.stopped_void(w)
        rc, text = self.resume(w, self.ruling(w, audit_void='accept'))
        self.assertEqual(rc, 0, text)
        self.assertEqual(w.j('rulings', 'ruling-01.json')['audit_void'], 'accept')
        with flagged():
            s = w.done()
        self.assertEqual(s6_audit_line(w), 'Runner audit: void (runner-audit.r1.txt, sha256 %s)'
                         % sha(read(w.p('runner-audit.r1.txt'))))
        self.assertEqual((s['runner_audit'], s['runner_audit_path'], s['qualified']),
                         ('void', 'runner-audit.r1.txt', False))
        self.assertIn('runner audit void (runner-audit.r1.txt)', s['deviations'])
        self.assertEqual(sha(read(w.p('runner-audit.txt'))), h0)

    def test_a_bad_audit_void_value_refuses_and_writes_nothing(self):
        w = self.world()
        self.stopped_void(w)
        before = tree(w.run)
        for bad in ('yes', 'Accept', '', True, ['accept'], None, 1):
            with self.subTest(bad=bad):
                rc, text = self.resume(w, self.ruling(w, audit_void=bad))
                self.assertEqual(rc, 2, text)
                self.assertIn('audit_void must be "accept"', text)
                self.assertEqual(tree(w.run), before)

    def test_audit_void_refuses_on_a_stop_that_is_not_the_audit_stop(self):
        w = self.world()
        w.rc.update(selftest=1)
        w.stopped('S1', 'selftest exited 1')
        before = tree(w.run)
        rc, text = self.resume(w, self.ruling(w, audit_void='accept'))
        self.assertEqual(rc, 2, text)
        self.assertIn('audit_void rules only on a runner-audit stop', text)
        self.assertEqual(tree(w.run), before)

    def test_runner_audit_txt_is_never_rewritten(self):
        w = self.world()
        h0 = self.stopped_void(w)
        self.assertEqual(self.resume(w, self.ruling(w))[0], 0)
        with flagged():
            w.stopped('S5', q.AUDIT_STOP, 'runner-audit.r1.txt')
        h1 = sha(read(w.p('runner-audit.r1.txt')))
        self.assertEqual(self.resume(w, self.ruling(w, audit_void='accept'))[0], 0)
        with flagged():
            w.done()
        a2 = read(w.p('runner-audit.r2.txt')).decode()
        self.assertIn('supersedes: runner-audit.r1.txt (sha256 %s)' % h1, a2)
        self.assertEqual((sha(read(w.p('runner-audit.txt'))), sha(read(w.p('runner-audit.r1.txt')))), (h0, h1))
        self.assertIn('runner-audit.r2.txt', s6_audit_line(w))


class G2(unittest.TestCase):
    def finished(self):
        w = World(self).start()
        w.done()
        return w

    def next_line(self, w):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = q.main(['next', w.run])
        return rc, out.getvalue()

    def test_next_on_a_finished_run_names_summary_json(self):
        w = self.finished()
        self.assertEqual(q.next_action(w.run), ('DONE', w.p('summary.json')))

    def test_next_names_the_highest_summary_rk_json_by_number(self):
        w = self.finished()
        for k in (1, 2, 10, 9):
            put(w.p('summary.r%d.json' % k), '{}\n')
        self.assertEqual(q.next_action(w.run), ('DONE', w.p('summary.r10.json')))
        rc, text = self.next_line(w)
        self.assertEqual((rc, text), (0, 'DONE %s\n' % w.p('summary.r10.json')))

    def test_the_procedure_done_path_names_the_latest_summary(self):
        w = World(self).start()
        self.assertEqual(w.drive(), ('DONE', w.p('summary.json')))


class Reaudit(unittest.TestCase):
    def ruling(self, sim):
        r = {'quote': QUOTE, 'time': '2026-11-16T16:07:00-05:00', 'message_id': 't533u',
             'channel': 'Chief of Staff relay', 'kit_sha': NEW,
             'summary_sha256': sha(read(q.latest_summary(q.Run(sim.run))))}
        self.k = getattr(self, 'k', 0) + 1
        return put(os.path.join(sim.root, 'rulings-in', 'reaudit-%d.json' % self.k), json.dumps(r))

    def reaudit(self, sim):
        return q.reaudit(sim.run, self.ruling(sim), clock=sim.clock, head=lambda: (NEW, False),
                         ancestor=sim.ancestor)

    def test_reaudit_records_what_s6_carried_and_next_names_its_summary(self):
        sim = naming_sim(self)
        with mock.patch.object(q.Run, 'sent_payload_names', lambda self, cur, tid, hits: False), pre_g1():
            self.assertEqual(sim.drive(), 'DONE')
        rc, text = self.reaudit(sim)
        self.assertEqual(rc, 0, text)
        r = sim.j('summary.r1.json')['reaudit']
        self.assertEqual((r['evaluator_saw_audit'], r['evaluator_saw_audit_path'], r['was']),
                         ('void', 'runner-audit.txt', 'void'))
        self.assertEqual(q.next_action(sim.run), ('DONE', os.path.join(sim.run, 'summary.r1.json')))

    def test_reaudit_after_an_accepted_void_supersedes_the_latest_audit(self):
        sim = naming_sim(self)
        with mock.patch.object(q.Run, 'sent_payload_names', lambda self, cur, tid, hits: False):
            self.assertEqual(sim.drive(), 'STOP')
            stop = os.path.join(sim.run, 'STOP.md')
            self.assertIn(q.AUDIT_STOP, read(stop).decode())
            rc, text, end = sim.resume({'quote': QUOTE, 'time': '2026-11-16T16:07:00-05:00', 'message_id': 't533u',
                                        'channel': 'Chief of Staff relay', 'stop_sha256': sha(read(stop)),
                                        'audit_void': 'accept'})
            self.assertEqual((rc, end), (0, 'DONE'), text)
        self.assertEqual(sim.j('summary.json')['runner_audit_path'], 'runner-audit.r1.txt')
        rc, text = self.reaudit(sim)
        self.assertEqual(rc, 0, text)
        self.assertTrue(text.startswith('REAUDIT runner-audit.r2.txt: runner audit clean (was void'), text)
        s2 = sim.j('summary.r2.json')
        self.assertTrue(s2['supersedes'].startswith('summary.json (sha256 '))
        self.assertEqual((s2['reaudit']['evaluator_saw_audit'], s2['reaudit']['evaluator_saw_audit_path']),
                         ('void', 'runner-audit.r1.txt'))
        a2 = read(os.path.join(sim.run, 'runner-audit.r2.txt')).decode()
        self.assertIn('supersedes: runner-audit.r1.txt (sha256 %s)' % sha(read(os.path.join(
            sim.run, 'runner-audit.r1.txt'))), a2)
        self.assertEqual(q.next_action(sim.run), ('DONE', os.path.join(sim.run, 'summary.r2.json')))


if __name__ == '__main__':
    unittest.main()
