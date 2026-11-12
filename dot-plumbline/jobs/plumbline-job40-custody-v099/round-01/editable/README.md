# Evaluator Driven — the custody record

A specification for the record kept with a piece of evaluated work: what the work was measured against,
who measured it, what they found, and who decided. The record makes work answerable, not correct.

Why the name: see "Why this name" in `SPEC.md`.

**Who this is for**
- **Implementers** who want work they hand off, or receive, to carry its own account.
- **Reviewers** in procurement, security, or legal who need to check that account. Start with the
  [reviewer's guide](docs/REVIEWERS-GUIDE.md); every word the specification uses is in the
  [glossary](docs/GLOSSARY.md).

**Status: v0.9.9, candidate.** Early. One reference checker exists, in this repository. Known
implementations and their status are listed in the doctrine's README:
<https://github.com/evaluatordriven/doctrine#the-custody-record>. Nothing here implies endorsement by
anyone. Each release carries
its own custody record in `record/`, kept with that release's tag; this release's record claims CL1,
and states why not higher.

**Limits, stated first**
- The evidence base is one author's work and a handful of jobs.
- The reference checker verifies a record's shape and internal consistency. It cannot tell whether a
  reading was honest; that is what independent evaluators and the approver are for.
- External evidence (CL1-15, CL3-3) is only as good as the party who read it.
- No signing tool ships here yet, **by decision rather than omission**, and the reference checker does not
  verify signatures, so it reads CL3-3 as `NOT-CHECKABLE`: no record reaches CL3 with it. SPEC.md names
  Sigstore as the method; [`docs/SIGNING-DECISION.md`](docs/SIGNING-DECISION.md) records why it is not
  built, what was weighed instead, and the three conditions that would start it.
- The custody log catches an edited, removed or reordered event, but a log rewritten from the start, or
  cut short at the end, still verifies. Nothing outside the log anchors it until the record is signed.
- A control shows that a reader caught a known case. No checker can tell whether the case was hard enough
  to miss.
- "Held out" means held out from the maker of the record in hand, not from everyone.
- Records whose evidence files are withheld read `NOT-CHECKABLE` on CL1-8 and CL1-15 for anyone without
  those files. That includes this repository's own records: their reader evidence is private.
- This release had no reader panel, guide tester or human reader. Its record says so.
- There is no certifying body, assessor or registry. A record certifies nothing; see GOVERNANCE.md.
- One person maintains the specification. GOVERNANCE.md says how it continues without him.

## Quickstart

Python 3.10 or newer, standard library only:

```sh
git clone https://github.com/evaluatordriven/custody && cd custody
python3 tools/make_record.py examples/minimal/inputs.json examples/minimal/record.json
python3 checker/check.py examples/minimal/record.json --files examples/minimal --bar examples/minimal/bar.md --evidence examples/minimal/evidence
```

The second command turns a hand-written inputs file into a record, computing every digest. The third
checks it against the work's files, the bar, and the evidence behind each reading, and prints a report;
exit code 0 means `OK`, 1 `FAILED`, 2 `NOT-CHECKABLE`. CI runs these two commands exactly.

To make your own: copy `examples/minimal/`, replace the files with yours, edit `inputs.json`, and run
the same two commands.

## Record as you go

`tools/record.py` keeps a custody log while the work happens: each event gets the clock time and the
digests of the files it names, chained so that an edited, reordered or missing event is caught.

```
python3 tools/record.py init job.jsonl --job "Q3 vendor report"
python3 tools/record.py add job.jsonl bar-frozen --actor "Casey Park" --file bar.md
python3 tools/make_record.py inputs.json record.json --log job.jsonl
```

## What is here

| Path | What it is |
|---|---|
| `SPEC.md` | The specification. Its *(normative)* sections define conformance. |
| `schema/custody-v1.schema.json` | The record's shape, for JSON Schema 2020-12 validators |
| `checker/check.py` | Reference verifier (not normative) |
| `tools/make_record.py` | Builds a record from a plain inputs file, or from a custody log (`--log`) |
| `tools/record.py` | Keeps the custody log as work happens |
| `tools/count.py` | Checks this repository's own size limits and cross-file agreement |
| `tools/explain.py` | Prints a record in plain words, for reviewers, with the checker's answer |
| `tools/verify_note.py` | Writes, or checks, a published note of a record's checker result, in the checker's own words |
| `tools/readability.py` | Checks the reviewer's guide against its reading target (advisory in CI) |
| `docs/REVIEWERS-GUIDE.md` | A plain-language guide for people who review records rather than build them |
| `docs/GLOSSARY.md` | Every word the specification uses, explained in plain language |
| `CHANGELOG.md`, `GOVERNANCE.md`, `SECURITY.md` | What changed in each release; who decides and how it continues; how to report a flaw |
| `examples/minimal/` | A one-page memo, its bar, and a CL1 record |
| `fixtures/` | Passing and failing records, one named reason per failure; `generate.py` rebuilds them |
| `tests/` | Runs the checker over the fixtures |
| `record/` | This repository's own custody record (added at release), and the screening test's record |

## Levels at a glance

The requirements live in `SPEC.md` section 5; this is only orientation.

| Level | In one line |
|---|---|
| CL1 · process | All four moves: bar first and approved, work pinned, read independently beside a control, record kept with a named decision |
| CL2 · process | CL1, plus repeated runs with their spread, and model readers on a separate family and endpoint |
| CL3 · process | CL2, plus each reader shown failing a held-out planted case first, and a signed, logged record |
| baseline | The bar came after the work started: a valid description, with no level |

## Licenses

- Text (`SPEC.md`, documentation): **CC BY 4.0**, © 2026 Steve Moitozo II — see `LICENSE`.
- Code (`checker/`, `tools/`, `fixtures/`, `tests/`, `schema/`): **Apache-2.0** — see `LICENSE-CODE`.
- Patents: the author's non-assertion pledge — see `PATENTS.md`.
- Copyright notice for the code: `NOTICE`.

## Lineage

Condensed from a private working corpus and checked against evaluatordriven.com. The corpus is lineage,
not evidence: nothing here depends on it, and it is not public.
