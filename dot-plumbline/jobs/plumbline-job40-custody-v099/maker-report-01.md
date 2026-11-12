# Maker report — job40 round 1 — STOPPED, no dispatch written

Seat: Maker (route-maker), round 1. Findings read: none (best null, defects []).
Packet read: /home/jarbis1/tmp/plumbline-job40/packet.job40.ratified.json (only packet read).

## What I measured

Test command from the packet (`PYTHONPATH=. python3 tests/test_v099_instrument1.py`,
cwd /home/jarbis1/tmp/custody-job40):

    Ran 14 tests in 1.954s
    FAILED (failures=1)
    exit 1
    RED: test_02_count_py_green_except_the_record (only)

The bar in the tree is the approved digest:
`11c7dc7115f2e1b1403678275b787b7c0fe332e9f05cfd60799370e17a097a16` — matches the packet.

Tree state: the seven release documents are the carried-forward 0.9.9 set (M in git status),
HEAD 0984170. SPEC.md header reads `**Version 0.9.9 · candidate · 2026-11-12**`, base header
(dd64e06) reads `0.9.8 · 2026-11-04`. Plain `python3 tools/count.py` exits 1 with exactly one
problem, the release's missing record — which is Instrument 2's file, not the Maker's.

## Why the one red is not writable by the Maker

test_02 fails on its BITE, not on the subject (subject half is green: the only count.py problem
is the record one). The failing assertion:

    gap_gate.write_file(gaproot / "record" / "RECORD-GAP-v0.9.9.md", "# a gap\n")
    gap_problems = measure_count_maker_problems(gaproot)
    self.assertTrue(any("declares a gap" in p for p in gap_problems), ...)
    AssertionError: ... did not report it: ['count.py exited 0 on a documents-only tree for 0.9.9;
    see test_02 — a green here came from a gap note']

The bar matches a count.py sentence via `GAP_PROBLEM_RE` (bar line 149):

    re.compile(r"declares a gap for (?P<v>\S+); a gap note is permitted only")

and cites it as "count.py's sentence for a gap note on a release that may not take one
(tools/count.py:127-128)".

Measured against the frozen tool actually in the tree:
- `tools/count.py` in the tree is 222 lines. Line 127-128 is inside the schema/checker enum
  comparison, not gap handling.
- The strings `GAP_EXCEPTIONS` and `declares a gap` do not occur anywhere in tools/ or checker/
  (grep: no matches).
- The tree's count.py accepts EITHER a record OR a `RECORD-GAP-v<version>.md` for ANY version
  (lines 115-118), with no permission gate — so the planted gap note is silently accepted and
  count.py exits 0. That is exactly the observed failure.
- `tools/count.py` is frozen (packet artifact.frozen; bar FROZEN_PATHS/FROZEN_DIRECTORIES) and is
  unmodified from HEAD (sha256 2448f8c326ba21f020e8b6a0257c374f93616238aabdbdd92c5b086a69f47244,
  identical to `git show HEAD:tools/count.py`). So the tool cannot be changed to make the bite bite.

Conclusion: the bar is written against a count.py revision that this tree does not carry. The
remaining red can only be cleared by editing a frozen tool (the gap-refusal sentence and
GAP_EXCEPTIONS) or the frozen bar. Both are refused to the Maker. This is the escalation class
`frame_at_fault`, not a document defect. The packet's note "If the bar is wrong, that is
frame_at_fault and the Owner's, not a Maker edit" applies.

This is NOT solved by touching the seven documents: the bite plants its own copy and edits only
that copy's SPEC.md; the subject tree never enters the failing assertion.

## What I did not write

- No aider-prompt.md, no aider-dispatch.json — I will not hand Aider a prompt whose only
  satisfiable reading is "edit tests/test_v099_instrument1.py or tools/count.py", both frozen.
- No cost file — I measured no model spend.

## For the Orchestrator

1. The bar's `GAP_PROBLEM_RE` / `measure_count_maker_problems` green-exit branch, together with the
   packet's ground_truth citation of "`GAP_EXCEPTIONS = {'0.9.8'}` (tools/count.py:44)", describe a
   count.py this tree does not contain. Please check the tree's count.py digest against the one the
   Specialist approved the bar against.
2. If the intended count.py is a newer revision, the work tree base (dd64e06) is short of it and
   bringing it in is a job/packet change, not a Maker edit.
3. If the bar is to stand as-is on this count.py, the bar is wrong (frame_at_fault) and the Owner
   decides. The Maker cannot proceed on this red.
