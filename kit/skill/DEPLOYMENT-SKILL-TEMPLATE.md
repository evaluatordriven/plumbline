---
name: <program>-plumbline
description: "Use when running a job under Plumbline in <program>. Two commands — open and close — and the rules the kit holds you to."
---

# Plumbline jobs in `<program>`

**This is a template.** Copy it, replace `<program>` and `<repo>`, and delete this line. Do not copy another
instance's skill file: it names that instance's path and tree, and two hand-written command sets is the drift
trap the kit exists to measure. The **doctrine's** procedure is a different, canonical skill —
`skills/evaluator-driven-iteration/` in the corpus — and you should install that one as it is.

A job lives in `<repo>/dot-plumbline/jobs/<job-id>/`. Its terms are `packet.json`; its §5 records are
`iteration-N-eval-record.json`, each with the passes it names filed beside it under `passes/`.

## A job has two commands, and neither is skippable

```
plumbline_job.py open  --brief brief.json --job-dir <repo>/dot-plumbline/jobs/<job-id>
plumbline_job.py close --job-dir <repo>/dot-plumbline/jobs/<job-id> --run run-iteration-1.json
```

`open` creates the folder **by** its packet — a refused brief leaves no folder at all. `close` emits the §5
record(s), closes the job, and records the close in the packet. `--corpus <path to the corpus checkout>` on
either call, or set `$EDI_CORPUS`.

## What the kit will hold you to

- **Every dimension has one name** — in the record, in every filed pass, in every channel output. A pass scoring
  a dimension the record does not declare is refused, and a declared dimension no filed pass observed is
  refused (C35).
- **A `regenerate` carries at least one violation**, and a dimension below `T_dim` carries a violation
  classified into one of rule 4's four locators that **names** it (C36).
- **`k` and `x` are declared at open** — the iteration bound and the budget tolerance. A bound written after the
  run is not a bound (B.1.2).
- **The artifact is checked**: a record must have the artifact it names beside it, hashing to what was recorded.
- **The Maker never grades its own work**, and the Owner never holds the Evaluator seat.

## What not to do, and each of these has a defect behind it

- **Do not edit a record to make it pass.** A record that fails is a finding; one edited to pass is a lie with
  a signature. Superseded readings are re-issued as new records and the old one moves to `superseded/`.
- **Do not use `superseded/` to hide a failure.** The close skips that directory *by name and counts it*, so
  moving a failing record there changes nothing and the count shows it.
- **Do not put a brief or a run file in the job root.** They are inputs, not terms — they belong in `inputs/`,
  where the close will not judge them.
- **Do not hand-write a packet.** The emitter reads the corpus's own required list and runs the gate on its own
  output; a packet typed by hand is the failure this kit was built after.
