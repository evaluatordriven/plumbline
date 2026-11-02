#!/usr/bin/env python3
"""
Door tests for the discoverability gate — the hook, and the failure policy.

The pure validator is covered in test_discoverability_gate.py. THIS file covers what only exists once the
gate is a plugin: that `clarify` is actually blocked, that an accepted escalation actually opens it, that
unrelated tools are untouched, and that a broken gate fails OPEN and says so.

The last one matters most. A hook that raises is a gate that silently did not fire, and a gate that fails
CLOSED on a broken rules file makes `clarify` permanently unusable — a worse defect than not firing. So
the policy is: fail open, and record it. Tested rather than asserted.

Cited from ADR-001 §3 (the design), §4 (the declared gap) and §6 (the second door).
"""
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import gate  # noqa: E402


def run():
    cases, bad = [], 0

    def case(name, ok, detail=''):
        nonlocal bad
        cases.append((name, ok, detail))
        bad += 0 if ok else 1

    with tempfile.TemporaryDirectory() as td:
        ledger = pathlib.Path(td) / 'escalations.jsonl'
        gate._LEDGER_DEFAULT = ledger

        # 0. THE SCOPE, tested in both directions. Unarmed is the safe direction: a Plumbline instance
        #    rule must not govern work that is not Plumbline's, so absent means silent.
        gate._active_job = lambda: ''
        case('UNARMED: the hook is silent', 
             gate.pre_tool_call(tool_name='clarify', args={}, turn_id='t0', session_id='s0') is None)
        r = json.loads(gate.plumbline_escalate(
            question='Which ledger format should ship?',
            attempted=['read the ADR', 'measured the count'],
            why_undecidable='It turns on how much history the Owner wants retained.',
            options=['JSONL', 'SQLite'], recommendation='JSONL', seat='Architect'))
        case('UNARMED: the tool neither validates nor records', r.get('not_armed') is True,
             json.dumps(r)[:80])
        case('  and it says plainly that this is not a refusal',
             'not a refusal' in json.dumps(r).lower())

        gate._active_job = lambda: 'test-job-1'
        case('ARMED: the hook and tool become live',
             (gate.pre_tool_call(tool_name='clarify', args={}, turn_id='t0', session_id='s0') or {}
              ).get('action') == 'block')

        # 1. the second door: clarify is blocked with no accepted escalation
        gate._SATISFIED.clear()
        d = gate.pre_tool_call(tool_name='clarify', args={}, turn_id='t1', session_id='s1')
        case('clarify is BLOCKED when no escalation was accepted',
             isinstance(d, dict) and d.get('action') == 'block' and d.get('message'),
             json.dumps(d)[:90])
        case('  and the block message says what to do instead',
             'plumbline_escalate' in (d or {}).get('message', '')
             and 'search' in (d or {}).get('message', '').lower())

        # 1b. THE DENOMINATOR. A block is a fact about the gate's coverage, and until it is recorded
        #     the metric cannot be computed: `gate_coverage` is the share of questions that took a
        #     gateable path, and the attempts that did NOT take one were written nowhere. Owner's
        #     decision 2026-10-01, asked and answered through the gate itself (its first completed
        #     live cycle): record the block as a ledger row.
        rows = [json.loads(l) for l in ledger.read_text().splitlines()] if ledger.exists() else []
        blocked_rows = [r for r in rows if r.get('event') == 'path_blocked']
        case('a BLOCKED path is written to the ledger (gate_coverage needs its denominator)',
             bool(blocked_rows), f'events={[r.get("event") for r in rows]}')
        case('  and the row names the path and the tool that was refused',
             bool(blocked_rows) and blocked_rows[-1].get('tool') == 'clarify',
             json.dumps(blocked_rows[-1] if blocked_rows else {})[:120])
        case('  and it records the PATH, not the question text (the Owner saw none of these)',
             bool(blocked_rows) and blocked_rows[-1].get('question') is None)

        # 2. unrelated tools are untouched — the gate governs questions, not work
        for t in ('terminal', 'read_file', 'write_file', 'browser_exec'):
            case(f'{t} is NOT touched',
                 gate.pre_tool_call(tool_name=t, args={}, turn_id='t1', session_id='s1') is None)

        # 3. an accepted escalation opens the door — for the SESSION, for the declared window.
        #
        # DECLARED BEHAVIOUR CHANGE 2026-10-01 (Owner: "F2 go with option 1"), forced by a host
        # constraint, not chosen for convenience. This case used to read "in that turn only" and to
        # assert that a DIFFERENT turn stayed blocked. That intent is unimplementable through the
        # host: a plugin TOOL is dispatched with {"task_id", "session_id"} and no turn_id
        # (hermes-agent/model_tools.py:808), while a pre_tool_call HOOK is invoked with turn_id,
        # tool_call_id AND session_id (ids.hook_kwargs()). The window was stored under
        # `turn_id or session_id`, so the tool wrote under session_id, the hook read under turn_id,
        # and the door could NEVER open — measured live: two escalations accepted, `clarify` blocked
        # after each. Both sides now key on session_id: the identity the host gives BOTH doors, and
        # the unit `satisfaction_window_seconds` (900) already declares in the rules file.
        #
        # WHAT IS LOST, stated rather than hidden: a question can ride an unrelated escalation for up
        # to fifteen minutes within the same session, so the guarantee is "an escalation happened in
        # this session recently", not "for this question". Restoring per-turn needs the host to pass
        # turn_id to tools — filed as an upstream proposal, not patched locally into core.
        r = json.loads(gate.plumbline_escalate(
            question='Which ledger format should ship?',
            attempted=['read the ADR', 'measured the current escalation count'],
            why_undecidable='It turns on how much history the Owner wants retained, which is a value, '
                            'not a fact in the record.',
            options=['JSONL, one row per escalation', 'SQLite, one binary table'],
            recommendation='JSONL, one row per escalation',
            seat='Architect', turn_id='t2', session_id='s1'))
        case('a complete escalation is accepted', r.get('accepted') is True, json.dumps(r)[:90])
        case('  and the next clarify in that session passes',
             gate.pre_tool_call(tool_name='clarify', args={}, turn_id='t2', session_id='s1') is None)
        case('  and it holds for the DECLARED window, not only for one turn',
             gate.pre_tool_call(tool_name='clarify', args={}, turn_id='t3', session_id='s1') is None)
        case('  but a DIFFERENT session is still blocked',
             (gate.pre_tool_call(tool_name='clarify', args={}, turn_id='t3', session_id='sOther') or {}
              ).get('action') == 'block')

        # 4. a refused escalation does NOT open the door
        gate._SATISFIED.clear()
        r = json.loads(gate.plumbline_escalate(question='q', attempted=[], why_undecidable='',
                                               options=[], recommendation='', seat='',
                                               turn_id='t4', session_id='s1'))
        case('a refused escalation is refused', r.get('refused') is True)
        case('  and it does NOT open the door',
             (gate.pre_tool_call(tool_name='clarify', args={}, turn_id='t4', session_id='s1') or {}
              ).get('action') == 'block')
        case('  and the refusal tells the model nothing reached the Owner',
             'nothing reached the owner' in json.dumps(r).lower())

        # 5. FAILURE POLICY: a broken gate fails OPEN and records it
        good = dict(gate._LOADED)
        try:
            gate._LOADED.clear()  # every rule lookup now returns empty
            d = gate.pre_tool_call(tool_name='clarify', args={}, turn_id='t5', session_id='s1')
            case('a broken gate fails OPEN rather than blocking permanently', d is None)
        finally:
            gate._LOADED.clear(); gate._LOADED.update(good)

        # 6. the ledger is the evidence, and it is plain JSONL
        rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
        events = [r['event'] for r in rows]
        case('the ledger records both the refusal and the acceptance',
             'escalation_refused' in events and 'escalation_accepted' in events, str(events))
        case('  and every row is a flat object with a timestamp',
             all(isinstance(r.get('at'), str) for r in rows))

    print('DISCOVERABILITY GATE — door tests (ADR-001 §3, §4, §6)\n')
    for name, ok, detail in cases:
        print(f'  {"ok  " if ok else "FAIL"}  {name}')
        if not ok:
            print(f'        -> {detail}')
    print(f'\n  {len(cases) - bad}/{len(cases)} behaved as the spec requires')
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(run())
