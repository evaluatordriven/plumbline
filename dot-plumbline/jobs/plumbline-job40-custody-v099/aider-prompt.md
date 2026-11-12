# Task: cut the custody v0.9.9 release across the release documents

You are editing a custody work tree at /home/jarbis1/tmp/custody-job40b.
The failing tests are the spec. Read them; do not edit them.

## The bar (FROZEN — do not edit)

    tests/test_v099_instrument1.py   (sha256 11c7dc7115f2e1b1403678275b787b7c0fe332e9f05cfd60799370e17a097a16)

Also frozen and not yours to edit:

    checker/check.py
    tools/count.py
    tools/check_verdicts.py
    schema/custody-v1.schema.json
    fixtures/expected.json
    tests/example_version_check.py

Do not create or modify anything under record/. In particular do not create
record/RECORD-GAP-v0.9.9.md and do not create record/custody-v0.9.9.json.
The record is another instrument's file, not this job's.

## The red, measured at base (before your edit)

    PYTHONPATH=. python3 tests/test_v099_instrument1.py
    Ran 14 tests ... FAILED (failures=1)

    FAIL: test_00_the_release_lands
      measure_release_lands(self.subject) returned:
        - SPEC.md: the header declares 0.9.8, which is not later than the base release 0.9.8
          (derived from git show 534d8738f233:SPEC.md); the release has not been cut
        - SPEC.md: header is dated 2026-11-04, which is not strictly later than the base
          header's date 2026-11-04
        - record/RECORD-GAP-v0.9.8.md: a gap note carries the release's name

The other 13 cases are green at base and must stay green. test_00 also plants five
deliberate breakages on copies of the tree and requires each to be reported; those bites
pass at base and must keep passing.

## What the documents must become

Read measure_release_lands, measure_header, measure_count_except_record,
measure_count_maker_problems, measure_spec_change, measure_spec_section4, measure_examples
and measure_documents_clean in the bar. They are the specification; implement what they
measure, nothing more. In shorthand, the subject tree must carry:

1. SPEC.md — a `**Version X.Y.Z · status · YYYY-MM-DD**` header naming one release strictly
   later than the base commit's 0.9.8, dated a real calendar day, not in the future, and
   strictly later than the base header's 2026-11-04.
2. CHANGELOG.md — its newest version heading is that same release, with a real entry for it.
3. examples/minimal/inputs.json and examples/minimal/record.json — `specVersion` is that
   same release in both files.
4. No record/RECORD-GAP-v<that release>.md exists. The existing
   record/RECORD-GAP-v0.9.8.md stays where it is; it is the earlier release's note.
5. README.md — the status line carries the same version token.
6. CONTRIBUTING.md — carries no version token count.py would read as stale, while keeping
   verbatim the three sentences test_08/test_07 require (see CONTRIBUTING_REQUIRED_PHRASES
   in the bar), keeping its Releases cadence sentences, and keeping the fact that a release
   shipped without a record and where that note lives.
7. DRAFT-NOTE.md — names the release, keeps an "Hunk inventory" section and its numbered
   sections, and carries no stale version token.
8. No requirement moves: every CR-/CL1-/CL2-/CL3-/BL- row in SPEC.md keeps its text, every
   section-4 required cell keeps its answer, and section 4's `specVersion` example cell is
   the release's own version. No other current document (GOVERNANCE.md, SECURITY.md, NOTICE,
   PATENTS.md), schema, tool, checker or fixture changes.

Do not add, remove or reword any requirement row. Do not change the seven frozen files.

## A precise starting point

The bytes that make this bar green on exactly this tree have already been measured:
seven document files at /home/jarbis1/tmp/plumbline-job35-tree (HEAD 900f2ba) — the same
seven paths named in artifact.editable — were copied over the corresponding files here,
the bar was run, and it reported `Ran 14 tests ... OK`. You may read those files and use
them as your target bytes for those seven paths. Copy their content into the matching
paths in the work tree; do not copy anything else from that tree (its
tests/test_v099_release.py is a different job's bar and must not appear here).

## Files you may edit

    CHANGELOG.md
    CONTRIBUTING.md
    DRAFT-NOTE.md
    README.md
    SPEC.md
    examples/minimal/inputs.json
    examples/minimal/record.json

Nothing else. No new files.

## Done when

    cd /home/jarbis1/tmp/custody-job40b
    PYTHONPATH=. python3 tests/test_v099_instrument1.py

reports `Ran 14 tests ... OK`.
