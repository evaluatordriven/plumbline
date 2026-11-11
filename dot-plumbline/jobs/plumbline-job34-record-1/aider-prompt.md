# Job 34, round 2 — `tests/test_emit_spec_version.py`

The failing test IS the spec. Read the bar in full before touching anything:

    tests/test_emit_spec_version.py

Its module docstring is the requirement set and is authoritative. Do not restate it, do not weaken
it, do not edit it.

## What is true right now (measured, round 2)

Round 1 was already sent to this bar and the ENGINE's edits are on top of the base in the work tree.
Measured just now, from this tree:

    python3 tests/test_emit_spec_version.py   ->  exit 1
    Ran 9 tests, FAILED (failures=1)

    RED   test_the_bar_leaves_its_subject_clean
    ok    version_is_read_from_the_custody_document
    ok    no_document_no_override_refuses
    ok    the_override_is_honoured
    ok    the_override_does_not_collide_with_the_document
    ok    every_published_verdict_is_byte_for_byte_unchanged
    ok    the_claim_about_the_emitter_survives_the_emitter_changing
    ok    the_claims_tool_selftest_runs_and_keeps_its_rule_set
    ok    a_deleted_selftest_rule_is_caught

So the eight cases that grade behaviour are GREEN. Do not regress them. Re-read those eight cases
before you change anything: whatever you do must leave them passing.

## The one red, in the bar's own words

    AssertionError: ' M kit/emit_custody.py\n M tools/check_version_claims.py\n' != ''
    : the bar dirtied the tree it was run from. `git status --porcelain` must be empty.
      If it names this bar, the bar is untracked: the Orchestrator commits it into the job tree,
      and a bar that is untracked reddens its own control case.

Case 6a is: `_porcelain(REPO)` is empty, where `REPO` is the tree the bar was run from. The bar's
docstring (`WHY THE SCRATCH TREE IS COMMITTED, AND WHAT IT MEANS FOR CASE 6`) states what 6a
measures: the SOURCE tree's porcelain after every case above has emitted, read and written nothing
into it. It is a control on the tree's state, not on any behaviour of the emitter.

## Where this leaves you

The tree is red only because files in it differ from HEAD. That is a fact about the work tree, not a
line of source. Your editable set does not contain a file in which that state can be corrected, and
the remediation is not yours to write.

Therefore:

  - Do NOT revert, delete, or re-stamp anything to make porcelain quiet.
  - Do NOT touch the bar, `kit/custody_history.py`, `tools/pin.json`, or any stored *.custody.json.
  - Do NOT edit outside the two paths below.
  - If you cannot make the bar green by editing only the two editable paths, change nothing and say
    so plainly in your final message: which case is red, and that the red is the tree's state
    rather than the emitter's behaviour. An honest "no edit needed" is the correct answer here; a
    fabricated edit is not.

## Files you may edit — exactly these two, nothing else

    kit/emit_custody.py
    tools/check_version_claims.py

## Files you must NOT edit (frozen)

    tests/test_emit_spec_version.py
    kit/custody_history.py
    tools/pin.json
    every stored *.custody.json in the tree
    tests/fixtures/custody/job-rejected/**
    dot-plumbline/jobs/plumbline-cl1-time-record-1/**

Do not widen the editable set. Do not move the pin.

## Verify before you finish

    python3 tests/test_emit_spec_version.py ; echo "EXIT=$?"
    # want: exit 0, "Ran 9 tests", "bar emit_spec_version: GREEN"

If you make no edit, report the run you got and why no edit was the right move.

## Bounds

Spend: strictly under US$0.25 total. Wall: under 2 h.
