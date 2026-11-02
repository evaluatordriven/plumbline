# dot-plumbline

Plumbline's content for this program lives here. Committed, never gitignored — it is evidence,
not state.

**Contracts §10.1:** *two records are retained **with the artifact*** — the evaluation record and
the instrument record. A record that cannot be found from the thing it judges cannot discharge
that, and failure F6 is *"accepted work cannot be reconstructed from its records."* That is why
this directory is version-controlled rather than local scratch.

## Layout

```
dot-plumbline/
  README.md          this file
  constitution.json  the standing frame for this program — ratified once, versioned   [instance layer]
  jobs/<job_id>/     packet.json · each iteration's artifact + §5 record · per-dimension vectors
  run-log.json       append-only: run id · commit · who held which seat · bounds supplied ·
                     dimensions + verdict · escalation class · cost · §5 record ref
  audits/            conformance audits of THIS program, as §5 records
  probes/            measurements taken on this program — the reading plus the protocol that
                     produced it (operator burden, the JEV evaluator probe)
  operating-loop.jsonl  append-only history of the operating loop: one line per run, written by
                     tools/check_operating_loop.py — the commit, the checks that ran, the failures
```

**In the public repository** only `README.md` and `constitution.json` are present: Plumbline's own `jobs/`,
`run-log.json`, `audits/`, `probes/` and `operating-loop.jsonl` stay in its private evidence archive, and two
jobs are published, frozen, under `examples/`.

Only the parts that exist are present. `jobs/` and `run-log.json` appear when this program's
first job runs; an empty placeholder would be structure nothing asked for.

## What does not go here

- **The doctrine.** The seven weight-bearing E-DI files live in the corpus (a private repository; the
  public reading copy is `github.com/evaluatordriven/doctrine`), and this program's schemas are DERIVED from a pinned commit of it
  — see Plumbline's `tools/build_schemas.py` and `tools/pin.json`. Do not copy doctrine in.
  public doctrine: `github.com/evaluatordriven/doctrine` (DOCTRINE.md v0.1 @ `dc61854`) — for reading; the tools and schemas still pin the private corpus.
- **Local state.** Caches, build output, scratch. Those are not evidence.

## Naming

Spelled `dot-plumbline`, not `.plumbline` — no leading dot, so it is visible in `ls`, in a git
host's file list, and in a Drive client, and the same name works in both places.

## Program

Plumbline itself — `dot-plumbline` is a *job in Plumbline*, so the applier and the applied are the same directory. No special case.

Doctrine in force: see the program's own `dot-plumbline/README.md` or Plumbline's `tools/pin.json`
for the pinned corpus commit.
