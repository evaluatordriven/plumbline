#!/usr/bin/env python3
"""
Prepare the constitution's LAW view for speech.

TWO RULES THIS OBEYS.
1. The recording is a LISTENING AID, never the instrument. Every change made for the ear is declared here
   and printed, so the audio can be checked against the file rather than trusted in place of it. The same
   discipline as a read-back: declare the normalisation before comparing.
2. Nothing may change MEANING. Only presentation. A normalisation that altered what a clause requires would
   be an edit to the law disguised as a format change.

Spoken normalisation, and why each is here:
    markdown emphasis (**bold**, *italic*, `code`)  -> removed; a voice reads "asterisk" otherwise
    heading markers (#)                             -> a pause and the heading spoken as a title
    bullet markers (-)                              -> removed
    blockquote marker (>)                           -> removed
    em dash and middot                              -> a comma, i.e. a spoken pause
    section sign (S)                                -> the word "section"
    underscores in identifiers (T_accept)           -> a space, so it reads as two words
"""
import pathlib
import re
import sys

SRC = pathlib.Path.home() / '.hermes' / 'tmp' / 'plumbline' / 'constitution-LAW.md'
OUT = pathlib.Path.home() / '.hermes' / 'tmp' / 'plumbline' / 'constitution-LAW.spoken.txt'


def normalise(text):
    changes = []
    t = text

    def sub(pattern, repl, label, flags=0):
        nonlocal t
        n = len(re.findall(pattern, t, flags))
        if n:
            changes.append((label, n))
        t = re.sub(pattern, repl, t, flags=flags)

    sub(r'\*\*(.+?)\*\*', r'\1', 'bold markers removed', re.S)
    sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', 'italic markers removed', re.S)
    sub(r'`([^`]+)`', r'\1', 'code markers removed')
    sub(r'^#{1,6}\s*(.+)$', r'\n\1.\n', 'headings spoken as titles', re.M)
    sub(r'^>\s*', '', 'blockquote markers removed', re.M)
    sub(r'^\s*[-*]\s+', '', 'bullet markers removed', re.M)
    sub(r'\s*[—–·]\s*', ', ', 'dashes and middots -> spoken pause')
    sub(r'§\s*', 'section ', 'section sign -> the word')
    sub(r'\b([A-Za-z])_([A-Za-z])', r'\1 \2', 'underscores in identifiers -> space')
    # A voice reads "1." as a full stop or skips it; the value numbers are spoken as words.
    _w = {'1': 'One', '2': 'Two', '3': 'Three', '4': 'Four', '5': 'Five', '6': 'Six', '7': 'Seven',
          '8': 'Eight', '9': 'Nine'}
    sub(r'^(\d)\.\s', lambda m: (_w[m.group(1)] if m.group(1) in _w else m.group(1)) + '. ',
        'value numbers spoken as words', re.M)
    sub(r'\s*\(LAW\)', '', 'the view label dropped from the spoken title')
    sub(r'\n{3,}', '\n\n', 'blank-line runs collapsed')
    t = t.lstrip()
    return t, changes


def main():
    raw = SRC.read_text()
    spoken, changes = normalise(raw)

    print('NORMALISATION APPLIED (declared, so the audio can be checked against the file):')
    for label, n in changes:
        print(f'  {n:>4}x  {label}')
    print()

    # Anything left that a voice might spell out or stumble over.
    odd = re.findall(r'[^\w\s.,;:()\'"\-\n]', spoken)
    from collections import Counter
    if odd:
        print('characters still non-word after normalisation (top 10):')
        for ch, n in Counter(odd).most_common(10):
            print(f'    {ch!r} x{n}')
    else:
        print('no stray punctuation left.')
    print()

    OUT.write_text(spoken)
    words = len(spoken.split())
    print(f'raw {len(raw):,} chars -> spoken {len(spoken):,} chars / {words:,} words')
    print(f'listen time at ~150 wpm: {words / 150:.1f} minutes')
    print(f'written -> {OUT}')
    print()
    print('===BEGIN SPOKEN TEXT===')
    print(spoken)
    print('===END SPOKEN TEXT===')


if __name__ == '__main__':
    sys.exit(main())
