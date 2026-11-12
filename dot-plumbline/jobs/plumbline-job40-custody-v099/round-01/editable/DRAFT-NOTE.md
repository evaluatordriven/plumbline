# Draft Note — v0.9.9 (candidate)

## 1. Hunk inventory (N6)

1. `CHANGELOG.md` (+17 -0) — the 0.9.9 entry
2. `CONTRIBUTING.md` (+3 -2) — the cadence amendment, and the gap sentence reworded to name the earlier release in words
3. `DRAFT-NOTE.md` (+22 -101) — this note
4. `README.md` (+1 -1) — the status line bumped to 0.9.9
5. `SPEC.md` (+2 -2) — the header and section 4's example bumped to 0.9.9
6. `examples/minimal/inputs.json` (+1 -1) — `specVersion` set to 0.9.9
7. `examples/minimal/record.json` (+1 -1) — `specVersion` set to 0.9.9

## 2. What changed and what did not

This release changes no requirement. It cuts the release documents to 0.9.9 — the header and section 4's
example, the status line, both example files — and records the Owner's cadence amendment in the Releases
section of `CONTRIBUTING.md`. No requirement row moved, no section 4 required cell moved, and the
examples' digests are unchanged: only their `specVersion` moved.

## 3. Where to look hardest

The sentence in `CONTRIBUTING.md` about the release that shipped without a record is the only prose that
had to lose a version token. It still states the fact, still names the note a reader can open, and now
attributes the absence to the previous release in words rather than by number. This release touches no
frozen path: it is documents and the two example files only.
## Hunk map

Every hunk in this release, by file. All of them are documents or examples; no frozen path moved.

| file | hunks |
|---|---|
| `CHANGELOG.md` | 1 |
| `CONTRIBUTING.md` | 2 |
| `DRAFT-NOTE.md` | 1 |
| `README.md` | 1 |
| `SPEC.md` | 2 |
| `examples/minimal/inputs.json` | 1 |
| `examples/minimal/record.json` | 1 |
