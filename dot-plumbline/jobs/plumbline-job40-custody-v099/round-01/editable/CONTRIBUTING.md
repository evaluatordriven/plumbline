# Contributing

## Three kinds of change

| Kind | What it is | What it needs |
|---|---|---|
| **Behavioral** | Anything that could change whether a record reads `OK`, `FAILED`, or `NOT-CHECKABLE` — the checker, the fixtures, the schema, or a normative requirement | A failing record from real use, or a reproducible counterexample, attached to the issue |
| **Structural** | Changes what the repository refuses without moving any verdict: `tools/count.py`, `tools/check_verdicts.py`, `tests/`, CI | The check proved to fail on the defect it names, before it is trusted, and a reader who is not its author |
| **Editorial** | Wording, typos, examples, layout | A declaration in the pull request: *no semantic change* |

A behavioral change without a failing record or counterexample is closed, not argued. Records made to
test this specification itself do not count as real use.

A behavioral change to the checker, the fixtures or the schema is itself a job: the bar is frozen before the
change, a reader who could not see the maker's answer reads it, and the release carrying it ships a record.
The release before this one shipped without one — the gap note in `record/` says why — and `count.py`
now refuses a release that neither carries a record nor declares its absence.

## How to file a failing record

1. Run `python3 checker/check.py your-record.json --files your-artifact-folder`.
2. Open an issue with the record, the report, and one sentence on what you expected instead.
3. Remove anything confidential first; digests are enough for most reports.

## Releases

At most one release a month while the version starts with 0, quarterly after 1.0. Versions follow
Semantic Versioning 2.0.0; `SPEC.md` section 8 says what counts as a major change. Every release is a
git tag, and is cited by its commit.

In the Owner's words: a release that changes no requirement does not count toward the monthly cadence.

## Before you open a pull request

```sh
python3 fixtures/generate.py && python3 tests/run_fixtures.py && python3 tools/count.py
```

All three must pass. A new requirement arrives with a fixture that fails for it and only it.
