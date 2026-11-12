# Job 40b — Custody v0.9.9: cut the version across the seven release documents

You are editing SEVEN DOCUMENTS ONLY. No code. No record. No test.

## The failing test is the spec

Run:

    cd /home/jarbis1/tmp/custody-job40b
    PYTHONPATH=. python3 tests/test_v099_instrument1.py

Measured on this tree at the start of your turn: `Ran 14 tests` / `FAILED (failures=1)`.
The one red case is:

    test_00_the_release_lands

Its assertion message, verbatim:

    SPEC.md: the header declares 0.9.8, which is not later than the base release 0.9.8
    (derived from git show 534d8738f233:SPEC.md); the release has not been cut
    SPEC.md: header is dated 2026-11-04, which is not strictly later than the base
    header's date 2026-11-04 (from git show 534d8738f233:SPEC.md header); a later
    release carries a later date
    record/RECORD-GAP-v0.9.8.md: a gap note carries the release's name; this release
    ships a record (Instrument 2), and a gap is the exception 0.9.8 argued for

Do not edit the bar to make it green. It is frozen at sha256
11c7dc7115f2e1b1403678275b787b7c0fe332e9f05cfd60799370e17a097a16.

## DO NOT EDIT — frozen

Do not edit `tests/test_v099_instrument1.py` for any reason.
Do not edit anything under `checker/`, `tools/`, `schema/`, `fixtures/`, or `tests/`.
Do not create `record/RECORD-GAP-v0.9.9.md` (a gap note for this release is refused).
Do not create or modify `record/custody-v0.9.9.json` (that file is Instrument 2's work,
not the document Maker's).

## What `measure_release_lands` requires of the documents

`test_00` calls `measure_release_lands(root)` and requires the returned problem list to
be EMPTY. Reading that function (`tests/test_v099_instrument1.py:329-407`) and its
neighbours, the tree must satisfy all of:

1. `SPEC.md` carries a header matching
   `**Version X.Y.Z · status · YYYY-MM-DD**` whose version is STRICTLY LATER than the
   version in `git show 534d8738f233:SPEC.md` (which is 0.9.8).
2. The newest CHANGELOG.md version heading (`^#{0,3}\s*(\d+\.\d+\.\d+)\b`) names that
   same version. The heading is the FIRST such heading in the file.
3. Every `specVersion` value found anywhere in `examples/minimal/inputs.json` and
   `examples/minimal/record.json` equals that same version.
4. The header date is a real calendar day, is NOT in the future, and is STRICTLY LATER
   than the base header's date (2026-11-04).
5. `record/RECORD-GAP-v<declared version>.md` does not exist.

The version is read from your SPEC.md header and the base from git history. Nothing
requires the number 0.9.9 by literal — but the job is named for the 0.9.9 release and the
carried-forward artifact already says 0.9.9, so keep 0.9.9 unless you find a reason not to.

## What the other 13 cases require of the documents

They are green at base and must stay green. They are sensitive to:

- `test_01` — the header's section-4 example value is the release's own version, and the
  header date is later than 2026-11-04 and not in the future.
- `test_02` / `test_03` — `tools/count.py` (frozen, do not edit) must report zero problems
  apart from the one missing-record problem the release is expected to carry, and no stale
  version token and no gap note for the declared release may exist. `tools/count.py:44`
  sets `GAP_EXCEPTIONS = {"0.9.8"}` — so 0.9.9 may NOT have a gap note.
- `test_05` — every requirement row (`CR-`, `CL1-`, `CL2-`, `CL3-`, `BL-`) and every
  section-4 required cell must be byte-identical apart from version tokens. Do not reword,
  add, or remove a requirement.
- `test_06` — the CHANGELOG's newest entry is the release's own, and its text claims no
  requirement change.
- `test_07` — CONTRIBUTING.md keeps naming 0.9.8 as the release that shipped without a
  record (that is a past fact, not this release), and carries no version token that
  `count.py` reads as a stale current-version token.
- `test_08` — README, CONTRIBUTING and DRAFT-NOTE are mutually consistent: they agree on
  which version is current. The CONTRIBUTING sentences `test_08` requires must survive.
- `test_09` — no current document carries a stale version token.

## Implementation approach (document edits only)

The best artifact from Job 35's round 1 is on disk at
`/home/jarbis1/tmp/plumbline-job35-tree` (HEAD 900f2ba). Its seven documents are already
cut to 0.9.9 and are carried forward by the packet as the Maker's starting artifact.
`git -C /home/jarbis1/tmp/plumbline-job35-tree status --short` shows:

    M CHANGELOG.md  M CONTRIBUTING.md  M DRAFT-NOTE.md  M README.md  M SPEC.md
    M examples/minimal/inputs.json  M examples/minimal/record.json

Use that tree's versions of THESE SEVEN FILES as the target content for the same seven
paths in `/home/jarbis1/tmp/custody-job40b`. Read each source file and write its content to
the corresponding destination path. Do not copy `tests/test_v099_release.py` from that
tree — it belongs to a different job and is not yours.

After copying, verify against the destination tree, not the source:

    cd /home/jarbis1/tmp/custody-job40b
    head -3 SPEC.md                                   # header must read 0.9.9 with a date > 2026-11-04
    grep -n 'specVersion' examples/minimal/*.json     # both must read 0.9.9
    head -12 CHANGELOG.md                             # newest heading must be 0.9.9
    PYTHONPATH=. python3 tools/count.py               # only the missing-record problem should remain
    PYTHONPATH=. python3 tests/test_v099_instrument1.py

One caveat to check when you copy: `DRAFT-NOTE.md` in the Job 35 tree claims hunk counts
(`SPEC.md (+2 -2)`, `CHANGELOG.md (+24 -0)`, etc.) in its inventory section. If `test_08` or
`test_09` rejects them, correct the inventory numbers to the actual `git diff --stat` of
this tree, keeping the sentence structure the bar requires. Prefer fixing the document to
match reality over fixing the bar.

If any case beyond `test_00` is still red after the copy, read that case's assertion and its
`measure_*` helper, and adjust the DOCUMENT it names — never the test, never `tools/count.py`.

## Done means

`PYTHONPATH=. python3 tests/test_v099_instrument1.py` reports `Ran 14 tests` with no
`FAILED` line, and `git status --short` in `/home/jarbis1/tmp/custody-job40b` shows changes
to at most the seven editable paths:

    CHANGELOG.md
    CONTRIBUTING.md
    DRAFT-NOTE.md
    README.md
    SPEC.md
    examples/minimal/inputs.json
    examples/minimal/record.json

Nothing else. Do not commit. Do not create files under `record/`.
