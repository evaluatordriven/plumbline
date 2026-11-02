<!-- STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — E-GLM rubric for J2, job 2026-10-28-custody-times-ledger-spend (author: Chief of Staff (Orchestrator) drafter). -->
You are reading a software repository's runbook, `docs/custody-emission.md`, as a person following it would.

QUESTION. Read as a person would, does the document CONFORM to the rule below?

RULE. The document, taken as a whole, must say all five of these, and must not say or imply the opposite of any:
1. Hand-entered times (times no tool stamped) are REFUSED by default.
2. The `--allow-hand-times` switch only FLAGS hand-entered times (records them as such); it never verifies them,
   and a flagged time is not presented as checked, verified or trustworthy.
3. A relay (someone passing on what another party said) is a report, not an approval: a relayed approval does not
   count as that party's approval.
4. Times reported after the fact are accepted only through the bounding commands (commands that stamp the bounds
   themselves), not typed in.
5. The `x-plumbline` facts are enforced only by Plumbline's own verifier; the standard custody `check.py` ignores
   them (does not validate them).

The listing shows the whole document with its line numbers; lines marked "+" were added or changed in this
revision, unmarked lines were already there. Judge the whole document as it now reads.

Answer in exactly this form and nothing else:
VERDICT: CONFORMS | DOES_NOT_CONFORM
LINES: <file>:<line>[, <file>:<line> ...]   (the lines that say each point, or the lines that contradict the rule)
REASON: <one or two sentences>

DOCUMENT:
