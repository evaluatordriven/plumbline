---
name: plumbline
description: "Use when running, building, or auditing a Plumbline deployment (an E-DI job). Points at the canonical files and the kit's commands; restates no law."
version: 0.1.0
author: Steve Moitozo II
license: CC-BY-4.0
metadata:
  hermes:
    tags: [plumbline, e-di, evaluator, conformance, job-packets]
---

# Plumbline — which role are you in, and what do you run

Three roles a session can hold. They have different rules; say which one you are in before acting.

1. **Working IN Plumbline** (this repository's checkout) — read `AGENTS.md` first. It is authoritative for
   this repo and it is not restated here: a restatement is a second place to go stale.
2. **Running a job** — the packet is that job's law: `dot-plumbline/jobs/<job_id>/packet.json`, with the
   artifact, the §5 record(s) and the instrument that produced them beside it. Validate the packet *before*
   generation, not after.
3. **Auditing a deployment** (another program's `dot-plumbline/`) — run the corpus's own checkers over their
   records; do not read for impressions. Findings live with their program (Contracts §10.1); a copy filed in
   Plumbline's repo is the drift trap the corpus names.

## The commands

A job has two, and neither is skippable — the folder comes into existence BY its packet, and it ends BY the
record and the close:

```
plumbline_job.py open  --brief brief.json --job-dir dot-plumbline/jobs/<job_id>   # refused brief = no folder
plumbline_job.py close --job-dir dot-plumbline/jobs/<job_id> --run run-1.json     # record, close, close recorded
```

or, when a job already exists:

```
plumbline.py --doctor                          python, corpus checkout, checkers present, enforcement level
plumbline.py --corpus <checkout> <path>...     a packet, a job directory, or an evaluator record
```

Three verdicts, never two: **`OK` · `FAILED` · `NOT-CHECKABLE`**. *Not-checkable is not a pass* — a record no
checker can read is a finding, not a silence. Exit 1 when anything failed or nothing could be checked.

Corpus resolution, in order, then it refuses rather than guesses:
`--corpus` → `$EDI_CORPUS` → `plugins.edi-loop.corpus` in `~/.hermes/config.yaml`.

**A weak OK is not a verdict.** The gate runs its stdlib structural check always and the Draft 2020-12 schema
pass only where `jsonschema` is importable, and it now names which one produced the result —
`OK (schema-verified)` or `OK (structural only)`. The kit refuses to certify on the structural-only path.

## Every seat gets what it needs

**Every seat in an E-DI loop must be provided everything it is entitled to for making its best contribution to the job** — clear instructions, essential context, necessary computing resources, appropriate tooling, adequate tokens, ample time, and the full scope of agency vested in that seat. (Owner ruling 2026-11-06, every E-DI loop; the fuller statement and the story behind it are in `AGENTS.md` → the instance layer, and in `docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md`.)

What that means when you are routing a job:

- **Architect** — the failure record of that job: every prior stop, the red text, the Maker's reply if one exists, plus the tree, bars, packet and doctrine pin. Not your diagnosis of the fix.
- **Maker** — the red, the rule-12 handoff, and an editable set that includes the file the bar actually fails in.
- **Evaluator** — the frozen standard and the turn. Never held-out material, never the Maker's model.

A brief made short rather than complete is a choke. The seat answers honestly against a partial surface, and the answer is useless.

## Traps that cost this instance a day each

- **The host calls a plugin tool as `handler(args_dict, **kwargs)`** — the whole argument dict positionally. A
  handler expecting named kwargs dies on every real call while its unit suite stays green: test the host's call
  shape, not a convenient one.
- **A backup directory beside a plugin is itself a plugin.** A same-name duplicate silently wins registration,
  so a `.bak-…` copy can be the code that runs. Back up to `~/.hermes/backups/`.
- **A new seat inherits `model.base_url`.** An OpenRouter seat sent to the maker's endpoint satisfies role
  separation on paper and violates it in fact. Clear it, and verify the seat answers before building on it.
- **Plugins bind at gateway start.** A file swap needs `pm2 restart hermes-gateway`; `hermes gateway restart`
  does nothing while a detached gateway holds the profile.
- **Derived schemas are never hand-edited** — change `schemas/instance-extensions.json`, then build. A hand
  edit is erased by the next build and is invisible in review.

## The rule for this file

Cite by location; never restate. Where this skill disagrees with the corpus or with Plumbline's `AGENTS.md`,
those win and this file gets fixed.
