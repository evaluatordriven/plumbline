#!/usr/bin/env python3
"""
plumbline-gate — the discoverability gate.

WHAT IT DOES. Two doors, because the Owner can be reached three ways and two are gateable:

  1. `plumbline_escalate`  — the sanctioned path. It REFUSES an escalation that records no attempt,
                             names no method, restates its own question as the reason, offers fewer
                             than two options, recommends something that is not one of its options, or
                             names no seat. Rules live in discoverability-rules.json as DATA.
  2. a `pre_tool_call` hook — blocks `clarify` unless an escalation was accepted in this turn. This is
                             the second door, and it is why the declared gap is narrow: the only
                             remaining path is a question typed into an ordinary reply, which no hook
                             can touch because the reply is not a tool call.

WHAT IT CANNOT DO, STATED SO NOBODY ASSUMES OTHERWISE. It cannot see or stop the turn's reply. There is
no pre-send hook in the host and the send is deliberately not a tool call (toolsets.py). So the gate
governs the paths the agent routes through, and `gate_coverage` measures what share of questions took
one — it is not a claim to catch everything.

FAILURE POLICY. A hook that raises is a gate that silently did not fire, so every hook path is wrapped.
On an internal error the gate FAILS OPEN and writes a `gate_error` row to the ledger. That choice is
deliberate: failing closed on a broken rules file would make `clarify` permanently unusable, which is a
worse defect than a gate that did not fire. Failing open silently would hide it, so the error is
recorded rather than swallowed.
"""
import json
import pathlib
import sys
import time

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from rules import load_rules, validate_escalation  # noqa: E402

try:
    from hermes_constants import get_hermes_home  # type: ignore[import-not-found]
except Exception:  # outside a Hermes process — the tests import rules.py and never land here
    def get_hermes_home():
        return str(pathlib.Path.home() / '.hermes')

_LEDGER_DEFAULT = pathlib.Path(get_hermes_home()) / 'state' / 'plumbline-gate' / 'escalations.jsonl'

_SATISFIED: dict = {}   # turn key -> epoch seconds of the last accepted escalation
_LOADED = load_rules()


def _ledger_path():
    try:
        import yaml
        cfg = pathlib.Path(get_hermes_home()) / 'config.yaml'
        node = (yaml.safe_load(cfg.read_text()) or {}).get('plugins', {}).get('plumbline-gate', {})
        if node.get('ledger_path'):
            return pathlib.Path(node['ledger_path']).expanduser()
    except Exception:
        pass
    return _LEDGER_DEFAULT


def _record(row):
    """Append-only JSONL. The FORMAT is the portable part — plain lines, no host coupling — so a
    different runtime can read the same ledger without a rewrite (ADR-001 §7)."""
    try:
        p = _ledger_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('a') as fh:
            fh.write(json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%S'), **row}) + '\n')
    except Exception:
        pass  # the ledger is evidence, never a reason to fail the turn


def _active_job():
    """The SCOPE. The gate is armed only while a Plumbline job is active, because a Plumbline instance
    rule must not govern work that is not Plumbline's. Unarmed is the safe direction: absent means silent.

    Declared limitation: this scopes BEHAVIOUR, not SURFACE. A plugin is enabled globally, so
    `plumbline_escalate` appears in every session's tool list regardless — what the scope controls is
    whether it refuses or acts. The surface leak is the price of the plugin home, and it is recorded
    rather than glossed."""
    try:
        import yaml
        cfg = pathlib.Path(get_hermes_home()) / 'config.yaml'
        node = (yaml.safe_load(cfg.read_text()) or {}).get('plugins', {}).get('plumbline-gate', {})
        return str(node.get('active_job') or '').strip()
    except Exception:
        return ''


def _block(message):
    """The host's pre_tool_call directive shape (hermes_cli/plugins.py:1787)."""
    return {'action': 'block', 'message': message}


def pre_tool_call(tool_name=None, args=None, turn_id='', session_id='', **_kw):
    try:
        if not _active_job():
            return None  # not armed — outside its instance the gate stays silent
        cfg = _LOADED.get('gateable_paths', {})
        if tool_name not in cfg.get('question_tools', []):
            return None
        # The key must be one BOTH doors can produce. The host dispatches a plugin TOOL with
        # {"task_id", "session_id"} and no turn_id (hermes-agent/model_tools.py:808), while a
        # pre_tool_call HOOK receives turn_id, tool_call_id and session_id (ids.hook_kwargs()).
        # Preferring turn_id therefore stored the window under a key the tool could never write, and
        # `clarify` stayed blocked forever: the sanctioned path — escalate, then ask — could not work
        # at all. Measured live 2026-10-01. The session is the identity both sides hold, and the
        # rules file's own satisfaction_window_seconds (900) is the rule that governs it.
        key = session_id or turn_id
        when = _SATISFIED.get(key)
        window = _LOADED.get('satisfaction_window_seconds', 900)
        if when and (time.time() - when) < window:
            return None
        # THE DENOMINATOR. `gate_coverage` is the share of questions that took a gateable path, and
        # until this row existed the attempts that did NOT take one were written nowhere — so the
        # gate's own declared metric could never be computed. Owner's decision 2026-10-01, asked and
        # answered through the gate itself on its first completed live cycle. The PATH is recorded,
        # not the question text: the ledger is a record of routes taken, and these questions were
        # never put to the Owner — holding their text in a file he reads would be a second exposure,
        # not evidence. The rate itself is judged in HIS turns (ADR-001 §3), not from this text.
        _record({'event': 'path_blocked', 'tool': tool_name, 'job_id': _active_job(),
                 'session_id': session_id, 'turn_id': turn_id,
                 'path': 'question_asking_tool_without_an_accepted_escalation'})
        return _block(
            f"`{tool_name}` is a question-asking path and no escalation was accepted this turn, so this "
            f"call is blocked.\n"
            f"Classify the question first, then:\n"
            f"  · if the record can answer it — search, measure, read the repo, probe the record, or run "
            f"the code — do that instead of asking. That is the whole point.\n"
            f"  · if it genuinely cannot, call `plumbline_escalate` with what you attempted, why no "
            f"observable answer exists, at least two options each with its cost, your recommendation, "
            f"and the seat the Owner should answer in. Then call this tool again.\n"
            f"An escalation without options is work pushed back."
        )
    except Exception as e:  # fail open, and say so rather than swallow it
        _record({'event': 'gate_error', 'where': 'pre_tool_call', 'error': repr(e)[:300]})
        return None


def _arg(args0, named, key):
    """The host calls a plugin tool as ``entry.handler(args, **kwargs)`` — the whole argument dict
    POSITIONALLY (hermes-agent/tools/registry.py:851,853) — while this repo's suites and any local
    caller use named keywords. Both shapes work, and that is not politeness: on the gate's first live
    turn the host's shape landed the dict in ``question``, validation refused it, and the refusal path
    died slicing a dict — `TypeError: unhashable type: 'slice'` on EVERY call, while thirty green
    cases certified the rules. Tests that call only the shape the host never uses certify nothing.
    """
    if isinstance(args0, dict) and key in args0:
        return args0[key]
    return named


def plumbline_escalate(_args0=None, question='', attempted=None, why_undecidable='', options=None,
                       recommendation='', seat='', job_id='', turn_id='', session_id='', **_kw):
    question = _arg(_args0, question, 'question')
    attempted = _arg(_args0, attempted, 'attempted')
    why_undecidable = _arg(_args0, why_undecidable, 'why_undecidable')
    options = _arg(_args0, options, 'options')
    recommendation = _arg(_args0, recommendation, 'recommendation')
    seat = _arg(_args0, seat, 'seat')
    job_id = _arg(_args0, job_id, 'job_id')
    if not _active_job():
        return json.dumps({
            'not_armed': True,
            'message': 'The discoverability gate is scoped to Plumbline jobs and no job is active, so '
                       'this escalation was neither validated nor recorded. This is not a refusal — '
                       'just ask normally, or arm the gate by setting plugins.plumbline-gate.active_job '
                       'to the job id.',
        })
    job_id = job_id or _active_job()
    payload = {'question': question, 'attempted': attempted or [], 'why_undecidable': why_undecidable,
               'options': options or [], 'recommendation': recommendation, 'seat': seat}
    try:
        result = validate_escalation(payload, _LOADED)
    except Exception as e:
        _record({'event': 'gate_error', 'where': 'plumbline_escalate', 'error': repr(e)[:300]})
        return json.dumps({'error': f'the gate itself failed: {e!r}'})

    if not result['ok']:
        _record({'event': 'escalation_refused', 'question': question[:200],
                 'refusals': result['refusals']})
        return json.dumps({
            'refused': True,
            'refusals': result['refusals'],
            'how_to_satisfy': 'Fix every refusal above and call again. Nothing reached the Owner — this '
                              'is the gate doing its job, not an error.',
        })

    key = session_id or turn_id      # the key the hook can also produce — see pre_tool_call
    if key:
        _SATISFIED[key] = time.time()
    _record({'event': 'escalation_accepted', 'question': question[:200], 'seat': seat,
             'job_id': job_id, 'options': len(payload['options']),
             'attempted': payload['attempted']})
    return json.dumps({
        'accepted': True,
        'seat': seat,
        'next': 'Escalation recorded. You may now ask the Owner — carrying what was tried, why no '
                'observable answer exists, the options, and your recommendation.',
    })


SCHEMA = {
    'name': 'plumbline_escalate',
    'description': (
        'Escalate a question to the Owner through the discoverability gate. Use this BEFORE asking the '
        'Owner anything: it refuses an escalation that records no attempt, names no method, restates its '
        'own question as the reason, offers fewer than two options, recommends something that is not one '
        'of its options, or names no seat. If the record can answer the question, do not escalate — go '
        'find out. An escalation without options is work pushed back.'
    ),
    'parameters': {
        'type': 'object',
        'properties': {
            'question': {'type': 'string', 'description': 'The question, in one sentence.'},
            'attempted': {'type': 'array', 'items': {'type': 'string'},
                          'description': 'What you tried: each entry must name HOW — searching, '
                                         'measuring, reading the repo, probing the record, or running '
                                         'the code. "I thought about it" is not an attempt.'},
            'why_undecidable': {'type': 'string',
                                'description': 'Why no observable answer exists in the record — what '
                                               'KIND of answer is missing (a value, a priority, a risk '
                                               'appetite). Not the question restated.'},
            'options': {'type': 'array', 'items': {'type': 'string'},
                        'description': 'At least two, each carrying what it costs.'},
            'recommendation': {'type': 'string',
                               'description': 'Which option you would take, named exactly as one of '
                                              'the options, and why.'},
            'seat': {'type': 'string',
                     'description': 'Which of the seven seats the Owner should answer in: Owner, '
                                    'Architect, Buyer, Specialist, Maker, Evaluator, Orchestrator.'},
            'job_id': {'type': 'string', 'description': 'The Plumbline job this belongs to, if any.'},
        },
        'required': ['question', 'attempted', 'why_undecidable', 'options', 'recommendation', 'seat'],
    },
}


def register(ctx):
    ctx.register_tool(name='plumbline_escalate', toolset='plumbline', schema=SCHEMA,
                      handler=plumbline_escalate, emoji='🚧')
    ctx.register_hook('pre_tool_call', pre_tool_call)
