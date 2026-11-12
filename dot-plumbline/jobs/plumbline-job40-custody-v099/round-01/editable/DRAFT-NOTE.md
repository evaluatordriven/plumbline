# Draft Note — v0.9.9 (candidate)

## 1. Hunk inventory (N6)

1. `CHANGELOG.md` (+18 -0) — the 0.9.9 entry, saying no requirement changed — `release mechanics`
2. `CONTRIBUTING.md` (+8 -5) — retire the stale version token, carry the cadence amendment — `release mechanics`
3. `DRAFT-NOTE.md` (+52 -49) — this note — `release mechanics`
4. `README.md` (+1 -1) — the status line names the release — `release mechanics`
5. `SPEC.md` (+1 -1) — the header, and the version example in the field table — `release mechanics`
6. `examples/minimal/inputs.json` (+1 -1) — declare the release — `release mechanics`
7. `examples/minimal/record.json` (+1 -1) — declare the release — `release mechanics`

## 2. Record verdicts (G5.4)

Run at the base commit and at this commit, comparing `(verdict, levelAchieved, failing requirements)`
produced zero differences: no record's verdict changed, because no requirement changed. The minimal
example reads `OK` / `CL1` at both commits, and every fixture still reads as its expected outcome says.

## 3. What changed and what did not

This release is documents only. The header of `SPEC.md` names the release and the field table of section 4
follows it; nothing else in that document moved, and every requirement row is byte for byte the earlier
release's. `CHANGELOG.md` carries the release's entry, which says no requirement changed.
`CONTRIBUTING.md` stops naming the earlier release by a bare version token — the sentence still says
which release shipped without a record, and where its note is kept — and its Releases section carries
the cadence amendment. `README.md` states the new status, and both files under the minimal example
declare the release. We deliberately left the verifier, the counting tool, the schema, the fixtures and
everything under `record/` untouched.

## 4. Where to look hardest

The field table of `SPEC.md` section 4 is the place to look first. Its example cell is the only cell in
that table a release may move, and here only the version token inside it moved: the prose around the
token, the type cell, and the required cell are the earlier release's, word for word. Read
`CONTRIBUTING.md`'s Releases section next, then the release's entry in `CHANGELOG.md`. Each states a
claim a reviewer can check against the release's own documents, and none of them asks a reader to trust
a claim the documents do not carry.
## Hunk map

Every hunk, by file. This release touches the documents named below and nothing else: no path the job
freezes appears here, because no frozen path moved.

| file | hunks | item |
|---|---|---|
| `CHANGELOG.md` | 1 | release mechanics |
| `CONTRIBUTING.md` | 2 | release mechanics |
| `DRAFT-NOTE.md` | 1 | release mechanics |
| `README.md` | 1 | release mechanics |
| `SPEC.md` | 2 | release mechanics |
| `examples/minimal/inputs.json` | 1 | release mechanics |
| `examples/minimal/record.json` | 1 | release mechanics |

Total: 9 hunks across 7 files.
