#!/usr/bin/env python3
"""
OPERATOR BURDEN — the channel, rebuilt around the Owner's own signals (2026-09-30).

The Owner's definition of the burden:
  "constantly being asked to approve things, read long walls of text, make lots of decisions by
   decoding specialized language (high cognitive load). It feels like the machine is working me, not
   the other way round."

The Owner's signals — and these are BETTER than the proxies the first version measured, for one
structural reason: **they are events in HIS turns, not mine.** A count I can lower by writing
differently is a count I can game. His reactions are the burden showing up where it actually lands.

  1. RE-EXPLANATION REQUESTS — he asks for other terms, an unpacking, or a lower grade level.
     This is the *consequence* of specialist language, which is why it replaces "jargon density" as
     the measure. Density was a proxy; a re-explanation request is the injury.
  2. REPEATED APPROVALS OF THE SAME SHAPE — one ask about a class of action is fine. Asking again for
     the same SHAPE is the burden. So approvals are counted by CLASS, and the signal is classes asked
     more than once — not the raw count, which the first version wrongly treated as the measure.
  3. OPTION HAND-OFFS WITHOUT A RECOMMENDATION — choosing among complex options is work. Handing over
     options with no recommendation and no rationale is work pushed back, and the doctrine's own
     discoverability gate already says an escalation must carry "the options with a recommendation".

Each signal's target is ZERO. That makes the dimension passable, which the first version could not do:
it reported densities with no bar, so it could only ever be a reading.
"""
import json
import pathlib
import re
import sqlite3
import sys


def hits(pats, text):
    """Which of these patterns fire on this text."""
    return [p for p in pats if re.search(p, text, re.I)]

DB = pathlib.Path.home() / '.hermes' / 'state.db'
THIS = '20260929_151207_4a61e36a'

# ---- signal 1: his requests to re-explain.
# The Owner's own words for the sense (2026-09-30): "As in, I don't understand WHAT YOU MEAN." So the object
# of the failure must be MY OUTPUT. That single rule settles three rounds of drift:
#   "I don't understand what you mean"      -> his signal
#   "I don't understand why the pipeline…"  -> a question about the world, not about my writing
#   "I don't know"                          -> him expressing his own uncertainty. NOT his signal.
#   "I don't see the file"                  -> not comprehension at all. NOT his signal.
REEXPLAIN = [r'in other terms', r'in other words', r'\bunpack\b', r'\brephrase\b', r're-?explain',
             r'explain (?:it|that|this)(?:\s+\w+){0,3}?\s*(?:again|in|more|simpler|differently)',
             r'what do you mean', r'what does that mean',
             # bare non-comprehension, apostrophe optional. The negative lookahead is doing real work: the
             # bare form is a PREFIX of "I don't understand why the pipeline failed", so matching one
             # matches the other. The Owner's clarification settles which gives way — the object must be
             # MY OUTPUT, so a following "why"/"how" marks a question about the world and stays quiet.
             # DECLARED COST: "I don't understand how that works" said ABOUT MY REPLY would be missed.
             # Undercounting is recoverable; counting questions about the system as comprehension failures
             # would inflate the measure that exists to catch me.
             r"i\s*(?:'m| am)?\s*not\s+(?:understanding|following|getting)",
             r"i\s+do\s*n'?ot\s+(?:understand|follow|get)(?!\s+(?:why|how))\b",
             r"i\s+don'?t\s+(?:understand|follow|get)(?!\s+(?:why|how))\b",
             # ...or when it names MY output as the object
             r"i\s+don'?t\s+(?:understand|follow|get)\s+(?:what|you|your|that|this)",
             r"i\s+don'?t\s+see\s+(?:what you mean|your point|how that|why you)",
             r"\bi'?m\s+(?:lost|confused)\b", r"\blost me\b", r'over my head',
             r'makes?\s+(?:no|zero)\s+sense', r"doesn'?t\s+make\s+sense",
             r'what (?:are you|do you) (?:saying|talking about)',
             r"\bi(?:'m| am)\b[^.!?]{0,20}\bnot clear\b",            # first person only
             r'what do you mean by', r'explain (?:it|that|this) to me',
             r'simplif(?:y|ied)\s+(?:that|it|this)', r'\bbreak (?:it|that) down\b',
             r'\btoo dense\b', r'(?:too much|less|no|without|drop the|cut the)\s+jargon',
             r'plain english', r'dumb it down',
             r'lower grade', r'grade level']

# The detector ships with its own falsification cases, so a future change that widens or narrows it has to
# face the examples that produced the corrections. Four of these were real messages from the record.
SELFTEST = [
    ("I don't understand what you mean", True),
    ("I dont understand what you mean", True),
    ("I don't understand", True),
    ("I'm not understanding this", True),
    ("I'm not following", True),
    ("I don't follow", True),
    ("I don't get it", True),
    ("I'm losing you", False),            # not in the set — declared, not silently assumed
    ("I'm lost", True),
    ("You lost me", True),
    ("that makes no sense", True),
    ("what do you mean by that", True),
    ("in other words?", True),
    ("can you simplify that", True),
    ("I'm still not clear on P6", True),
    # must stay QUIET — each of these produced a false positive in an earlier version
    ("I don't understand why the pipeline failed", False),
    ("some of them need more thought. I don't know", False),
    ("store transcripts when it's not clear or empty", False),
    ("I don't see the file on Drive", False),
    ("The Listen page title is still in English", False),
    ("explain how the pipeline works", False),
    ("Clarifying: she says the sound is not in her ear", False),
    ("Ruling 1 - 0008 ratified", False),
    ("Go", False),
]

# ---- signal 2: shapes of approval ask, keyed by what the ask is ABOUT.
# Each message is assigned to AT MOST ONE shape (first match in this priority order), because v1 let one
# message count toward every shape it mentioned — an ask about AGENTS.md also said "commit".
SHAPES = [
    ('re-asking a timed-out approval',   r're-?issue|re-?ask|again for permission|ask again'),
    ('agent instruction file (AGENTS.md)', r'agents\.md|agent instruction|modify agents'),
    ('destructive / purge / delete',     r'\bpurge\b|\brm -rf\b|\bdelete\b'),
    ('credentials / secrets',            r'\bcredential|\bsecret|\bapi key'),
    ('external send (email / post)',     r'\bemail\b|\btweet\b|\bpost (?:it|this)\b'),
    ('Drive document write',             r'\bdrive\b|goals\.md|decisions\.log'),
    ('commit / push',                    r'\bcommit\b|\bpush\b'),
    ('run a probe / experiment',         r'\bprobe\b|\bbake-?off\b'),
]
# An ASK must be directed at him. v1 also caught status statements like "it stays untouched without your
# word", which report a standing state rather than request anything now.
# ---- DECISION HAND-OFFS, and the RECOMMENDATION RATE.
# CORRECTED BY THE OWNER, 2026-09-30: "Making lots of decisions isn't terrible. Being asked to make lots
# of decisions without recommendations is." So VOLUME IS NOT A BURDEN MEASURE and is not reported as one
# — a decision handed over WITH a recommendation is the Owner doing the job only the Owner can do. The
# defect is the hand-off that arrives without the machine having formed a view, which is work pushed back.
# The measure is therefore a RATE, and its target is 100%: of the decisions put to the Owner, the
# fraction carrying a recommendation and its rationale.
DECISION = [r'your call', r'you decide', r'which would you', r'which of (?:these|the|those)',
            r'choose between', r'let me know which', r'your preference',
            r'would you rather', r'which do you', r'\bdecisions? (?:i|we) need\b',
            r'do you want .{0,30}\bor\b', r'\byour move\b']

# ---- THE CHANNEL THAT CANNOT BE GAMED BY MY OWN PHRASING.
# Three regex attempts failed to measure the recommendation rate over MY OWN output (v1 counted every
# numbered list; v2 was so strict it read 0; v3 was so broad it classified status reports as decision
# hand-offs and missed recommendations wearing words it did not know — "my proposal", "I'd start"). Each
# time the number measured my regex, not my behaviour. The Owner's own correction gives the way out:
# "Being asked to make lots of decisions without recommendations is [the burden]." So the signal is the
# Owner ASKING ME FOR A RECOMMENDATION. It lives in HIS turns, it cannot be produced or suppressed by
# how I phrase things, and its target is ZERO. Rare enough that every hit is read rather than counted.
ASK_RECOMMENDATION = [r'what do you recommend', r'which do you recommend',
                      r"what(?:'s| is)\s+your recommendation", r'\byour recommendation\s*\?',
                      r'what would you (?:do|recommend|suggest)',
                      r"what'?s your (?:take|read|call)",
                      r'any recommendations?', r'\brecommend\?']
# `r'your recommendation'` alone was too loose and the selftest caught it: "I accept your recommendation"
# is the Owner ACCEPTING a view, which is this channel's SUCCESS case, not its failure. Counting an
# acceptance as a request would have made the load-bearing channel report the opposite of the truth.

APPROVAL = [r'want me to', r'shall i\b', r'may i\b', r'say the word', r'your call',
            r'permission', r'request approval', r'do you want me to', r'should i\b',
            r'would you like me to', r'shall we']

# ---- signal 3: option lists vs recommendations. v1's `^\s*\d\.\s` matched every numbered list, including
# lists of FINDINGS, which I write constantly — hence 131. An option hand-off now needs two distinct
# lettered/numbered OPTION markers or the word "option".
OPTION_MARK = [r'\boption [123a-c]\b', r'\boption\b.*\boption\b', r'\b\(a\).*\b\(b\)',
               r'\beither\b.*\bor\b', r'\btwo options\b', r'the options are', r'\bwhich would you\b',
               r'\bchoose between\b']
RECOMMEND = [r'i recommend', r"i'd recommend", r'my recommendation', r'i would recommend',
             r"i'd lean", r'\bi lean\b', r'\bprefer\b', r'\bi suggest\b', r'\brecommend\b',
             r'my read\b', r'best option', r'i would do', r'\bmy pick\b']

# ---- THE READING-LEVEL BAR, SET BY THE OWNER 2026-09-30: "Set the reading level bar at grade 10. That
# should help you write responses that are a bit less dense and jargon filled."
# It is a BAR, not a reading, so this channel is now scorable. It is enforced per MESSAGE rather than in
# aggregate, because an average hides the one reply that was unreadable — the same lesson as the pooled
# average that hid a regression. Note the measured position when it was set: this session read 9.5 (inside
# the bar) while the Owner's other work read 11.1 (outside it), so the bar binds on my ORDINARY writing.
READING_LEVEL_BAR = 10.0


def grade_messages(messages):
    """(gradeable, over_bar, worst) — per-message, so a dense reply cannot hide in an average."""
    graded = [(flesch_kincaid(t), t) for t in messages]
    graded = [(g, t) for g, t in graded if g is not None]
    over = [(g, t) for g, t in graded if g > READING_LEVEL_BAR]
    worst = sorted(graded, key=lambda x: -x[0])[:3]
    return graded, over, worst


# ---- THE SPECIALIST-LANGUAGE CHANNEL (added 2026-09-30, on the Owner's question "where's the jargon
# thing?"). It was a declared gap with NOTHING measuring it: jargon density had been dropped when this was
# rebuilt around the Owner's signals, leaving only the rare REACTION to specialist language (a re-explain
# request) and not the standing cost of producing it. Two readings, and neither is invented here:
#
#   (a) SPECIALIST-TERM DENSITY — per 1,000 words of my output, over a term list that is DECLARED below and
#       therefore arguable. A term list is a judgement, so it is visible rather than buried.
#   (b) FLESCH-KINCAID GRADE — the standard formula, not my invention:
#           FK = 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59
#       It is used because the Owner already works to a reading-level bar elsewhere (devotional text
#       targets FK ~8-9), so the number is comparable across his projects rather than bespoke to this one.
#
# BOTH ARE READINGS, NOT PASS/FAIL. No bar has been set for this work, and density is not harm: a clause
# identifier in a sentence about that clause is not a burden. The readings exist so a trend is visible and
# a bar CAN be set, not to assert one.
JARGON_TERMS = [
    r'§\s?\d', r'\bC\d{1,2}\b', r'\bM[1-8]\b', r'\bX[1-4]\b', r'\bO[1-4]\b',
    r'\b(?:null|nullable)\b',
    r'\bINVARIANT\b', r'\bDOCUMENT\b', r'\bPRIOR\b',
    r'\bhardness\b', r'\bpass rule\b', r'\bT_accept\b', r'\bT_dim\b', r'\bT_reject\b',
    r'\blocator\b', r'\bquorum\b', r'\bmandate\b', r'\bmust-ask\b', r'\bterminal state\b',
    r'\bground[- ]truth\b', r'\binstance layer\b', r'\bescalation class\b',
    r'\bdecision_rule\b', r'\bnon-negotiable\b', r'\bdisposition\b', r'\bconformance\b',
    r'\bcensus\b', r'\bcanonical\b', r'\bNORMATIVE\b', r'\bunratified\b',
    r'\bderived artifact\b', r'\bobserved surface\b', r'\bsha256\b', r'\bpin(?:ned)?\b',
    r'\bper-dimension\b', r'\bsubset invariant\b', r'\bone-directional\b',
]


def specialist_terms(text):
    return sum(len(re.findall(p, text)) for p in JARGON_TERMS)


def count_syllables(word):
    """Standard heuristic. Silent-e and leading-y handled; floor of 1."""
    w = re.sub(r'[^a-z]', '', word.lower())
    if not w:
        return 0
    w = re.sub(r'(?:[^laeiouy]es|[^laeiouy]e)$', '', w)
    w = re.sub(r'^y', '', w)
    return max(1, len(re.findall(r'[aeiouy]{1,2}', w)))


def flesch_kincaid(text):
    """FK grade level, standard constants. Returns None when the text is too short to grade."""
    body = re.sub(r'[`*_#>|]|MEDIA:\S+', ' ', text)
    sentences = [s for s in re.split(r'[.!?]+(?:\s|$)', body) if s.strip()]
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]*", body)]
    if len(sentences) < 2 or len(words) < 20:
        return None
    syl = sum(count_syllables(w) for w in words)
    return round(0.39 * (len(words) / len(sentences)) + 11.8 * (syl / len(words)) - 15.59, 1)


# ---- SELFTESTS FOR EVERY DETECTOR, not just one. The Owner asked "are there proper detectors in the
# script?", and the honest answer was no: REEXPLAIN had 24 cases while every other list had none — including
# ASK_RECOMMENDATION, which had just been promoted to load-bearing. A detector with no cases cannot be
# shown to fire where it should and stay quiet where it should, which is a check that certifies nothing.
DETECTOR_CASES = {
    'ASK_RECOMMENDATION': [
        ("What's your recommendation?", True),
        ('what do you recommend', True),
        ('which do you recommend?', True),
        ('What would you do here?', True),
        ('Any recommendations?', True),
        ('I accept your recommendation', False),      # he is ACCEPTING one, not asking for one
        ('Go', False),
        ('Do what you think is best', False),         # delegated, but he did not ask for a view
    ],
    'APPROVAL': [
        ('Want me to run it?', True),
        ('Shall I commit this?', True),
        ('Say the word and I will push', True),
        ('This stays untouched without your word', False),   # status, not an ask
        ('Committed and pushed, 7e532ca', False),
        ('Go', False),
    ],
    'DECISION': [
        ('Which of these do you prefer?', True),
        ('Your call on the third one', True),
        ('Let me know which folder', True),
        ('Committed and pushed — here is where we are', False),
    ],
    'SHAPES': [
        ('May I modify AGENTS.md?', 'agent instruction file (AGENTS.md)'),
        ('Want me to purge that evidence directory?', 'destructive / purge / delete'),
        ('Shall I re-issue the approval prompt?', 're-asking a timed-out approval'),
        ('Want me to push this?', 'commit / push'),
        ('Committed and pushed, 7e532ca', None),      # not an ask at all — no shape should match
    ],
}

PREFIX_RE = re.compile(r'^\s*\[[^\]]{1,60}\]\s*')
NOT_HUMAN = ('[CONTEXT COMPACTION', '[IMPORTANT:', '[System:', '[OUT-OF-BAND', '[Reminder',
             '[The user sent', '[ASYNC DELEGATION', '[Background', '[Attached', '[Tool')
# Matched ANYWHERE in a row, not just at the start: a real message can carry an appended compaction
# summary, and a start-only check walks straight past it.
NOT_HUMAN_ANYWHERE = ('[CONTEXT COMPACTION', 'END OF PRIOR CONTEXT', '[END OF PRIOR CONTEXT')
# The notice list keeps growing because every injection class looks like a user row. Each addition came
# from a false positive found by inspecting hits, not from imagining what might appear.


def owner_text(t):
    """The Owner's words, or None if the row is not a human turn.

    Three leaks, each found by inspecting a false positive rather than by imagining what might appear:
    (1) his messages carry a '[S M] ' prefix, so no directive pattern matched until it was stripped;
    (2) `[S M] [IMPORTANT: Background process...` starts with the prefix, so a not-a-human check that runs
        only BEFORE stripping lets injected notices through as human turns;
    (3) a real message can have a COMPACTION SUMMARY APPENDED TO ITS TAIL — one 61,378-char 'user' row
        begins with the Owner's words and then carries an entire historical summary, whose quoted text
        matched a pattern and produced a false re-explain hit. A start-only check cannot see that, so the
        markers are now matched ANYWHERE in the row.
    """
    if not t:
        return None
    stripped = PREFIX_RE.sub('', t.lstrip()).strip()
    for candidate in (t.lstrip(), stripped):
        if any(candidate.startswith(p) for p in NOT_HUMAN):
            return None
    if any(m in t for m in NOT_HUMAN_ANYWHERE) or len(stripped) > 4000:
        return None
    return stripped


def rows_for(c, ids):
    """ALL rows, not just active=1.

    Found the hard way: this session reported 20 Owner turns, then 3, on the SAME session minutes apart.
    Nothing had changed except that a compaction had run — and compaction sets earlier rows active=0. So an
    `active=1` filter measures a window that SHRINKS as the session grows, which would make operator burden
    appear to fall the longer I talk. A measure that moves in the flattering direction when nothing improved
    is not a measure. Dedupe by rowid so a row counted once is counted once."""
    q = ','.join('?' * len(ids))
    rows = c.execute(f"select session_id, role, content from messages "
                     f"where session_id in ({q})", ids).fetchall()
    # DEDUPE. Compaction leaves the pre-compaction row and a second copy behind: one Owner message showed
    # up twice in the same hit list, which double-counts turns, words and reading minutes alike. Collapse
    # on (session, role, content) — two genuinely separate turns with byte-identical text do not exist in
    # a conversation where every message carries a timestamp and a platform id.
    seen, uniq = set(), []
    for s, r, t in rows:
        k = (s, r, t)
        if k in seen:
            continue
        seen.add(k)
        uniq.append((s, r, t))
    return uniq


def measure(ids, label):
    c = sqlite3.connect(DB)
    rows = rows_for(c, ids)
    mine = [(s, t) for s, r, t in rows if r == 'assistant' and t and len(t.strip()) >= 40]
    his = [x for x in (owner_text(t) for s, r, t in rows if r == 'user') if x]

    reexp = [t for t in his if any(re.search(p, t, re.I) for p in REEXPLAIN)]
    asks = [(s, t) for s, t in mine if any(re.search(p, t, re.I) for p in APPROVAL)]
    by_shape = {}
    for s, t in asks:
        for shape, pat in SHAPES:            # priority order; at most ONE shape per ask
            if re.search(pat, t, re.I):
                by_shape.setdefault(shape, []).append(s)
                break
    repeated = {k: len(v) for k, v in by_shape.items() if len(v) > 1}
    # A DECISION HAND-OFF puts a decision to the Owner — either by asking him to choose, or by presenting
    # an option set. The RECOMMENDATION RATE over those hand-offs is the measure; the count is context.
    asked_rec = [s for s in his if any(re.search(p, s, re.I) for p in ASK_RECOMMENDATION)]
    handoffs = []
    for s, t in mine:
        marks = sum(1 for p in OPTION_MARK if re.search(p, t, re.M))
        if any(re.search(p, t, re.I) for p in DECISION) or marks >= 2:
            handoffs.append((s, t))
    no_rec = [s for s, t in handoffs if not any(re.search(p, t, re.I) for p in RECOMMEND)]
    rate = round(100.0 * (len(handoffs) - len(no_rec)) / len(handoffs), 1) if handoffs else None

    words = sum(len(t.split()) for _, t in mine)
    alltext = '\n'.join(t for _, t in mine)
    term_hits = specialist_terms(alltext)
    graded, over_bar, worst = grade_messages([t for _, t in mine])
    r = {
        'sessions': len(ids), 'his_human_turns': len(his), 'my_substantive_replies': len(mine),
        'signal_1_reexplain_requests': len(reexp),
        'signal_1_examples': [t[:70] for t in reexp[:6]],
        'signal_2_approval_asks_total': len(asks),
        'signal_2_distinct_shapes': len(by_shape),
        'signal_2_SHAPES_ASKED_MORE_THAN_ONCE': repeated,
        'signal_2_repeated_ask_instances': sum(repeated.values()),
        'signal_3_handoffs_without_recommendation': len(no_rec),
        'channel_owner_asked_me_for_a_recommendation': len(asked_rec),
        'channel_specialist_terms_per_1000w': round(1000.0 * term_hits / max(1, words), 1),
        'channel_flesch_kincaid_grade': flesch_kincaid(alltext),
        'channel_reading_level_bar': READING_LEVEL_BAR,
        'channel_reading_level_meets_bar': not over_bar,
        'channel_messages_over_reading_bar': f'{len(over_bar)} of {len(graded)} gradeable',
        'channel_reading_minutes': round(words / 200, 1),
        'channel_decision_handoffs_total': len(handoffs),
        'coarse_untrusted_recommendation_rate_pct': rate,
    }
    if worst:
        print(f'\n  DENSEST REPLIES (bar is grade {READING_LEVEL_BAR}) — the ones to rewrite:')
        for g, t in worst:
            flag = '  OVER BAR' if g > READING_LEVEL_BAR else ''
            print(f'    grade {g:5}{flag}  {t[:150]!r}')
    if asked_rec:
        print('\n  THE OWNER HAD TO ASK FOR A RECOMMENDATION — read every one:')
        for t in asked_rec:
            print(f'    - {t[:250]}')
    print(f'\n=== {label} ===')
    for k, v in r.items():
        if k == 'signal_1_examples':
            continue
        print(f'  {k:<48} {v}')
    if reexp:
        print('  signal 1 hits IN FULL (a rare signal is read, not counted):')
        for t in reexp:
            print(f'    - {t[:400]}')
    return r


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        bad = total = 0

        print('  REEXPLAIN')
        for text, should in SELFTEST:
            got = bool(hits(REEXPLAIN, text))
            total += 1
            if got != should:
                bad += 1
            print(f'    {"ok  " if got == should else "FAIL"} expect={"match" if should else "quiet":5} '
                  f'got={"match" if got else "quiet":5}  {text!r}')

        for name, cases in DETECTOR_CASES.items():
            pats = SHAPES if name == 'SHAPES' else globals()[name]
            print(f'  {name}')
            for text, should in cases:
                if name == 'SHAPES':
                    got = next((sh for sh, pat in SHAPES if re.search(pat, text, re.I)), None)
                else:
                    got = bool(hits(pats, text))
                total += 1
                if got != should:
                    bad += 1
                print(f'    {"ok  " if got == should else "FAIL"} expect={str(should):32} '
                      f'got={str(got):32}  {text!r}')

        print('  READABILITY (standard formula — checked against a known simple vs complex pair)')
        simple = ('The cat sat on the mat. The dog ran. A boy saw it. We can go now. '
                  'It was fun. The sun is out. I like it here. She said yes.')
        complex_ = ('Notwithstanding the considerable methodological heterogeneity evident across the '
                    'constituent investigations, the aggregate estimation procedure demonstrates '
                    'substantial sensitivity to presuppositional specification. Consequently the '
                    'inferential apparatus requires substantial qualification whenever practitioners '
                    'interpret the aggregated results.')
        fk_simple, fk_complex = flesch_kincaid(simple), flesch_kincaid(complex_)
        ok = fk_simple is not None and fk_complex is not None and fk_complex > fk_simple
        bad += 0 if ok else 1
        total += 1
        print(f'    {"ok  " if ok else "FAIL"} simple={fk_simple}  complex={fk_complex}  '
              f'(complex must grade higher)')

        print(f'\n  detectors: {total - bad}/{total} as designed')
        sys.exit(0 if bad == 0 else 1)
    c = sqlite3.connect(DB)
    base = [x[0] for x in c.execute(
        "select distinct session_id from messages where session_id != ? "
        "and timestamp >= strftime('%s','now','-30 days')", (THIS,)).fetchall()]
    out = {'owner_signals': {
        '1': 'operator asking to explain in other terms, to unpack dense responses, or to explain at a '
             'lower grade level',
        '2': 'repeated requests to approve the same shape of action',
        '3': 'asking the operator to choose between multiple complex options without a recommendation '
             'and rationale'},
        'target': 'zero for each signal',
        'this_session': measure([THIS], f'THIS SESSION ({THIS})'),
        'baseline_30d': measure(base, f'BASELINE: other sessions, last 30 days ({len(base)})')}
    p = (pathlib.Path(__file__).resolve().parent.parent / 'dot-plumbline' / 'probes'
         / 'operator-burden-2026-09-30.json')
    p.write_text(json.dumps(out, indent=2))
    print(f'\nraw -> {p}')
