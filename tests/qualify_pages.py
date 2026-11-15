"""Render a bot's transcript the way the real cursor ReadTranscript tool returns it with write_to_file, matched to
pages read on this platform 2026-11-15 (tests/fixtures/qualify/readtranscript-subject-first-run.txt has the same
structure as a real one): the page wrapped in <cursor_untrusted_data_1337 source="ReadTranscript"> ...
</cursor_untrusted_data_1337> with no trailing newline; a blank line; the header
'Transcript of agent "NAME" (ID), positions A\u2013B of N:' (or 'Transcript of this session, ...') with 0-based
inclusive positions and an en dash; one JSON object {"role", "message"} per line, oldest first, roles user,
assistant and tool; 'Older messages remain: call ReadTranscript again with the same in and before=A.' or, when
A = 0, 'This is the start of the transcript.'. Not every position is readable: position 0 of a top-level bot (its
setup) is never shown, so a page holds fewer lines than positions; a `before` that leaves only unreadable
positions gets 'No readable messages in agent "NAME" (ID) before position P.' alone. `limit` counts positions. A
tool input over ELIDE characters is shown as its first and last ~2000 characters with '...' between; the page
file is named <sha256 of its bytes>.txt. Used by tests only.

The previous version of this file (kit-resume) invented 1-based positions with one line per position and no
unreadable positions; the kit passed against it and failed on the first real page (run 5, action 0044)."""
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


HIDDEN = None  # a position the transcript counts but does not show


def messages(turns, hidden_at=()):
    """turns: [(kind, time, user_text, events)], kind 'first' (the platform's first-run cue) or 'agent'. Position 0
    is the bot's setup, never shown; `hidden_at` adds unreadable positions after the given message indexes."""
    out = [HIDDEN, {'role': 'user', 'message': {'content': [{'type': 'text', 'text':
                                                              '<memory_context>none</memory_context>'}]}}]
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
    for x in sorted(hidden_at, reverse=True):
        out.insert(x + 1, HIDDEN)
    return out


# the page file's own wrapper tag ends in 1337 (tool results inside a page use _redacted); a chat view of the
# file may show it as _redacted, which is how it was first reported
TAG = 'cursor_untrusted_data_' + '1337'
WRAP = '<' + TAG + ' source="ReadTranscript">\n\n%s\n\n</' + TAG + '>'


def page_text(msgs, a, b, who):
    """The bytes of one page: positions a..b (0-based, inclusive) of msgs; who is 'this session' or
    'agent "NAME" (ID)'."""
    shown = [m for m in msgs[a:b + 1] if m is not HIDDEN]
    if not shown:
        return (WRAP % ('No readable messages in %s before position %d.' % (who, b + 1))).encode()
    body = '\n'.join(json.dumps(m, ensure_ascii=False, separators=(',', ':')) for m in shown)
    tail = 'This is the start of the transcript.' if a == 0 else \
        'Older messages remain: call ReadTranscript again with the same in and before=%d.' % a
    return (WRAP % ('Transcript of %s, positions %d\u2013%d of %d:\n%s\n%s' % (who, a, b, len(msgs), body, tail))
            ).encode()


def save_page(folder, text):
    """write_to_file: the page saved as <sha256 of its bytes>.txt."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, hashlib.sha256(text).hexdigest() + '.txt')
    with open(path, 'wb') as fh:
        fh.write(text)
    return path


def who(bot_id=None, name=None):
    return 'this session' if bot_id is None else 'agent "%s" (%s)' % (name or 'bot', bot_id)


def pages(msgs, folder, bot_id=None, name=None, limit=25, drop_oldest=False):
    """Write the pages a runner gets by paging back from the newest position; returns their paths, newest first."""
    paths, before = [], len(msgs)
    while before > 0:
        a, b = max(0, before - limit), before - 1
        paths.append(save_page(folder, page_text(msgs, a, b, who(bot_id, name))))
        before = a
    return paths[:-1] if drop_oldest and len(paths) > 1 else paths


def minute(t):
    return t.replace(second=0, microsecond=0) if isinstance(t, datetime.datetime) else t
