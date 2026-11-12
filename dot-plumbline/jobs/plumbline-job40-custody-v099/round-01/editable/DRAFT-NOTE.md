# Draft Note — v0.9.9 (candidate)

This note describes one change: the version is cut across the seven release documents. No requirement
moved, no field changed shape, and no file outside those seven was touched.

## 1. Hunk inventory (N6)

Seven files moved, and nothing else:

1. `SPEC.md` — the header's version and date, and the `specVersion` example value in section 4.
2. `CHANGELOG.md` — this release's entry, added above the previous release's.
3. `CONTRIBUTING.md` — the sentence that explains the earlier release's missing record now names that
   release in words rather than by a version token, and the cadence sentence in "Releases" gains the
   Owner's amendment.
4. `README.md` — the status line.
5. `DRAFT-NOTE.md` — this note.
6. `examples/minimal/inputs.json` — `specVersion`, which must name the release.
7. `examples/minimal/record.json` — `specVersion`, which must name the release.

Line counts are not quoted: two of these changes re-wrap a paragraph, so a count would measure where the
author's line broke rather than what moved. The diff against the base commit is the record.

## 2. No verdict moved

The reference checker, the schema, the fixtures and the test runner are the base commit's, byte for byte,
so no record's reading can have changed: `examples/minimal/record.json` reads `OK` / `CL1`, and every
fixture reads what it read before. The only bytes that differ between this tree and the base commit are
the seven files in section 1.

## 3. What changed and what did not

The version moved and nothing else did. `SPEC.md`'s header names this release and carries a date later
than the header it replaces; the example value in section 4 names the same release; `CHANGELOG.md` gains
this release's entry; `README.md`'s status line names this release; this note describes it; and the two
example files declare it. Every requirement row in SPEC.md section 5 is the base commit's, id for id and
text for text, and section 4's field table is the base commit's cell for cell apart from the example
value. Signing, the schema and the kept records are untouched.

## 4. Where to look hardest

Two sentences carry the risk, because each states a fact a reader relies on and each is rewritten here.
The first is in `CONTRIBUTING.md`: it explains that an earlier release shipped without a record. It no
longer names that release by a version token — the repository's own agreement check refuses a current
document that names a version other than this one — so it names the release in words and points at the
note that explains it. A reviewer should check that the sentence still says which release it is about
and where the note is kept. The second is the cadence sentence in the same document's Releases section,
which now carries the Owner's amendment in the Owner's words; a reviewer should check that the amendment
reads as a sentence in that section, not as a citation of one.
## 5. What is not claimed

This note makes no claim about code: no file outside the seven named in section 1 differs from the base
commit, so nothing about a reader's behaviour, a fixture's reading or a record's verdict can have
changed. Nothing here certifies the quality of any work; it says only which version this tree declares.
