"""Render a bot's transcript the way the real cursor ReadTranscript tool returns it with write_to_file (seen on
this platform 2026-11-15): a page per call, newest first, at most `limit` messages; a header line
'Transcript of agent "NAME" (ID), positions A-B of N:' (or 'Transcript of this session, ...' for the caller's own
run); one JSON object {"role", "message"} per line; 'Older messages remain: ... before=A.' or the footer
'This is the start of the transcript.'; a tool input over ELIDE characters shown as its first and last ~2000
characters with '...' between; the page file named <sha256 of its bytes>.txt. Used by tests only."""
import datetime
import hashlib
import json
import os

ELIDE = 4000
HEAD = 2000


def stamp(t):
    """'<timestamp>Saturday, Nov 14, 2026, 8:00 PM (UTC-5)</timestamp>', as the platform opens a turn."""
    off = int(t.utcoffset().total_seconds() // 3600)
    return '<timestamp>%s, %s %d, %d, %d:%02d %s (UTC%+d)</timestamp>' % (
        t.strftime('%A'), t.strftime('%b'), t.day, t.year, (t.hour % 12) or 12, t.minute,
        'AM' if t.hour < 12 else 'PM', off)


def elide(s):
    return s if len(s) <= ELIDE else s[:HEAD] + '...' + s[-(ELIDE - HEAD - 4):]


def tool_use(e, k):
    """A normalized event {tool, namespace?, name?, input} as the transcript's tool_use block."""
    if e['tool'] == 'CallDynamicTool':
        inp = {'namespace': e.get('namespace'), 'toolName': e.get('name'), 'arguments': e.get('input') or {}}
    else:
        inp = e.get('input') or {}
    flat = json.dumps(inp, separators=(',', ':'), ensure_ascii=False)
    return {'type': 'tool_use', 'id': 'toolu_%06d' % k, 'name': e['tool'], 'input': elide(flat) if len(flat) > ELIDE
            else inp}


def messages(turns):
    """turns: [(kind, time, user_text, events)], kind 'first' (the platform's first-run cue) or 'agent'."""
    out = [{'role': 'user', 'message': {'content': [{'type': 'text', 'text': '<memory_context>none</memory_context>'}]}}]
    k = 0
    for kind, t, text, events in turns:
        cue = '[GROK_BOT_HIDDEN_PROMPT][first run] This is your very first turn.' if kind == 'first' else \
            '[GROK_BOT_HIDDEN_PROMPT][agent] A message just arrived from another of your user\'s agents: %s' % text
        out.append({'role': 'user', 'message': {'content': [{'type': 'text', 'text': '%s\n<user_query>\n%s\n'
                                                              '</user_query>' % (stamp(t), cue)}]}})
        for e in events:
            k += 1
            if 'tool' in e:
                out.append({'role': 'assistant', 'message': {'content': [{'type': 'thinking', 'thinking': '.'},
                                                                         tool_use(e, k)]}})
                out.append({'role': 'tool', 'message': {'content': [{'type': 'tool_result', 'tool_use_id':
                                                                     'toolu_%06d' % k, 'name': e['tool'],
                                                                     'result': 'ok'}]}})
            else:
                out.append({'role': 'assistant', 'message': {'content': [{'type': 'text', 'text': e['text']}]}})
    return out


def page_text(msgs, a, b, who):
    """The bytes of one page: messages a..b (1-based) of msgs; who is 'this session' or 'agent "NAME" (ID)'."""
    body = '\n'.join(json.dumps(m, ensure_ascii=False) for m in msgs[a - 1:b])
    tail = 'This is the start of the transcript.' if a == 1 else \
        'Older messages remain: call ReadTranscript again with the same in and before=%d.' % a
    return ('<cursor_untrusted_data_redacted source="ReadTranscript">\n\nTranscript of %s, positions %d\u2013%d '
            'of %d:\n%s\n%s\n\n</cursor_untrusted_data_redacted>\n' % (who, a, b, len(msgs), body, tail)).encode()


def save_page(folder, text):
    """write_to_file: the page saved as <sha256 of its bytes>.txt."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, hashlib.sha256(text).hexdigest() + '.txt')
    with open(path, 'wb') as fh:
        fh.write(text)
    return path


def pages(msgs, folder, bot_id=None, name=None, limit=25, drop_oldest=False):
    """Write the pages a runner gets by paging back from the newest message; returns their paths, newest first."""
    paths, before = [], len(msgs) + 1
    who = 'this session' if bot_id is None else 'agent "%s" (%s)' % (name or 'bot', bot_id)
    while before > 1:
        a, b = max(1, before - limit), before - 1
        paths.append(save_page(folder, page_text(msgs, a, b, who)))
        before = a
    return paths[:-1] if drop_oldest and len(paths) > 1 else paths


def minute(t):
    return t.replace(second=0, microsecond=0) if isinstance(t, datetime.datetime) else t
