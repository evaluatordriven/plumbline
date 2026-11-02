#!/usr/bin/env python3
"""THE HOST'S CALL SHAPE — the regression the other two suites could not see.

Measured 2026-10-01, the gate's first live turn: `plumbline_escalate` failed on EVERY call through
the host with `TypeError: unhashable type: 'slice'`. The cause was a dispatch-shape mismatch, not a
rules bug:

    hermes-agent/tools/registry.py:851,853     result = entry.handler(args, **kwargs)

The host passes the WHOLE argument dict as the first POSITIONAL argument. `test_discoverability_gate.py`
(11/11) and `test_discoverability_gate_doors.py` (19/19) both call the handler with **named keyword
arguments** — a shape the host never uses — so 30 green cases certified a tool that was unusable
behind the interface it ships on. That is the family this file exists to close: a check that cannot
fail for the reason that matters certifies nothing.

Every case here calls the handler the way the host does. Proven red on the pre-fix handler (the same
TypeError the host returned), green after it normalised both shapes.

Contracts §7.3 by analogy: the invocation is verified through the real caller, not through a
convenient stub.
"""
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import gate  # noqa: E402

VALID = {
    'question': 'Should the discoverability gate be armed while no Plumbline job is active?',
    'attempted': ['read gate/__init__.py for the arming rule',
                  'measured the ledger: it has never existed, so no policy can be inferred'],
    'why_undecidable': 'Which constraint yields when they conflict is a risk-appetite call, and risk '
                       'appetite is recorded nowhere in the repo, the constitution or the run-log.',
    'options': ['Arm per job only. Cost: gate_coverage stays unobservable.',
                'Leave it armed. Cost: a Plumbline rule governs unrelated work.'],
    'recommendation': 'Leave it armed. Cost: a Plumbline rule governs unrelated work. Reason: '
                       'the mechanism must fire once before it is trusted.',
    'seat': 'Owner',
}
REFUSABLE = dict(VALID, seat='Nobody')


def run():
    cases, bad = [], 0

    def case(name, ok, detail=''):
        nonlocal bad
        cases.append((name, ok, detail))
        bad += 0 if ok else 1

    with tempfile.TemporaryDirectory() as td:
        ledger = pathlib.Path(td) / 'escalations.jsonl'
        gate._LEDGER_DEFAULT = ledger
        gate._active_job = lambda: 'test-job-host-shape'

        # 1. THE HOST'S SHAPE: one positional dict, framework kwargs alongside it. This is the case
        #    that was red — it raised TypeError instead of returning a verdict.
        try:
            raw = gate.plumbline_escalate(dict(VALID), turn_id='t-host-1', session_id='s-host-1')
            r = json.loads(raw) if isinstance(raw, str) else {}
            ok = r.get('accepted') is True
            detail = json.dumps(r)[:120]
        except Exception as exc:                                     # noqa: BLE001
            ok, detail = False, f'raised {type(exc).__name__}: {exc}'
        case('host shape: a VALID escalation in one positional dict is accepted', ok, detail)

        # 2. A refusal is a verdict, never a crash — the same shape, a payload the rules refuse.
        try:
            raw = gate.plumbline_escalate(dict(REFUSABLE), turn_id='t-host-2', session_id='s-host-2')
            r = json.loads(raw) if isinstance(raw, str) else {}
            ok = r.get('refused') is True and r.get('refusals')
            detail = json.dumps(r)[:120]
        except Exception as exc:                                     # noqa: BLE001
            ok, detail = False, f'raised {type(exc).__name__}: {exc}'
        case('host shape: a REFUSABLE escalation returns refusals, not an exception', ok, detail)

        # 3. And the acceptance actually reached the ledger — the evidence, not just the return value.
        rows = [json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else []
        events = [row.get('event') for row in rows]
        case('host shape: acceptance and refusal were both written to the ledger',
             'escalation_accepted' in events and 'escalation_refused' in events, str(events))

        # 4. The named-kwargs shape still works, because the other two suites and every local caller
        #    use it. Fixing one caller's shape must not break the other.
        try:
            r = json.loads(gate.plumbline_escalate(**VALID))
            ok = r.get('accepted') is True
            detail = json.dumps(r)[:120]
        except Exception as exc:                                     # noqa: BLE001
            ok, detail = False, f'raised {type(exc).__name__}: {exc}'
        case('named shape: keyword arguments still work', ok, detail)

        # 5. THE TWO DOORS MUST SHARE A KEY, and the host gives them different ids.
        #    A plugin TOOL is dispatched with {"task_id", "session_id"} and no turn_id
        #    (hermes-agent/model_tools.py:808); a pre_tool_call HOOK is invoked with turn_id,
        #    tool_call_id AND session_id. A window written under one key and read under another can
        #    never be found, so `clarify` stays blocked forever and the sanctioned path cannot work.
        gate._SATISFIED.clear()
        r = json.loads(gate.plumbline_escalate(dict(VALID), session_id='s-shared'))
        case('host shape: escalation accepted with session_id only (as a tool is called)',
             r.get('accepted') is True, json.dumps(r)[:110])

        blocked = gate.pre_tool_call(tool_name='clarify', args={}, turn_id='t-later',
                                     session_id='s-shared')
        case('host shape: ...opens the second door in a SESSION whose id is all it shares',
             blocked is None, json.dumps(blocked)[:140])

        other = gate.pre_tool_call(tool_name='clarify', args={}, turn_id='t-other',
                                   session_id='s-elsewhere')
        case('  and a different session is still blocked (the window is not global)',
             (other or {}).get('action') == 'block', json.dumps(other)[:120])

    for name, ok, detail in cases:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else '  <- ' + detail}")
    print(f"\n  {'ALL CASES BEHAVED AS DESIGNED' if not bad else str(bad) + ' CASE(S) FAILED'}")
    return bad


if __name__ == '__main__':
    sys.exit(run())
