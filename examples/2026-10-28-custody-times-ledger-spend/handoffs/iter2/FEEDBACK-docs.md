ITERATION 2 FEEDBACK, part docs (docs/custody-emission.md, kit/README.md)

The files shown above are YOUR iteration-1 files as committed. The new sections are kept: the evaluator read them
as stating all five required points (hand times refused by default; the switch only flags; a relay is a report;
reported times only through the bounding commands; the two layers). Change only what the item below needs.

Item D1. Bar J2 (bar.md line 139): read as a person would, the doc must say that hand times are refused by default,
  the switch flags hand times and never verifies them, a relay is a report and not an approval, reported times are
  accepted only through the bounding commands, and `x-plumbline` is enforced by Plumbline's verifier only (the
  standard check.py ignores it). The doc must not also teach the opposite anywhere.
  What your iteration-1 doc did: the retained fact-source section still teaches the old policy.
  docs/custody-emission.md line 96 says "The emitter no longer trusts a typed time, a typed host or a typed
  approver when a log can say otherwise" (implying typed times are trusted where no log exists), and line 106 (the
  `bar.frozenAt`, `approvals[].at`, `disposition.at` row) says "no harness log exists: typed, or better logged
  live ... | if a live event log exists, refused when it differs" (implying a typed time is accepted by default).
  Rows 98-101 (`startedAt`, `producedAt`, `checks[].at`, control times) also call a hand-entered value only "a
  cross-check".
  Change: rewrite line 96 and the "A hand-entered value is..." column of that table so every row agrees with the
  new sections: a typed or hand-written time (no tool-written ledger line or logger time behind it) is refused as
  `hand-time` by default; with `--allow-hand-times` it is flagged in `x-plumbline.hand_times[]`, never verified;
  logged times are still cross-checked within 60 s. A typed `passes.<id>.at` or `controls[<id>].at` is a hand time
  even when a harness call is linked (source `inputs-no-ledger`), and a log call with no logger `sent_at` or
  `received_at` is a hand time with source `server-header`/`response-created`. Keep the US$0.0001 spend
  tolerance, the exit codes and the kinds as documented (bar V9, line 117).
