# The deployment conformance kit

**What it is.** One entry point that runs the E-DI corpus's own checkers over a deployment's records and tells
you, per artifact, whether it is conforming, non-conforming, or **not checkable at all**.

**Why it exists (measured, 2026-10-02).** The first external Plumbline deployment produced a full record — a
frozen instrument, four iterations, §5 records, Buyer amendments — that the corpus's own checkers reject: zero
of four §5 records validated, and the packet was markdown, which the gate cannot parse. Nothing had told that
deployment which command to run, against which file, or what the exit code meant. The checkers were never the
problem; the reach was.

**What it does not do.** It does not re-implement a single check. Re-implementing would create a second ruler,
and the corpus's own rule is that *the check that can override the Evaluator is the Evaluator*. It wraps
`tools/*.py` from a corpus checkout and reports their exit codes. It requires no plugin, no package install and
no network.

## Run it — a job has two commands

```
# 1. OPEN: the job folder comes into existence BY its packet. If the brief is refused, the folder is removed.
$ plumbline_job.py open  --brief brief.json --job-dir dot-plumbline/jobs/<job-id>

# ... the Maker works; the artifact lands in the job folder ...

# 2. CLOSE: a §5 record for every run file, then the close, then the close recorded in the packet.
$ plumbline_job.py close --job-dir dot-plumbline/jobs/<job-id> --run run-iteration-1.json
```

`open` and `close` are a job's whole lifecycle, and neither is skippable: there is no folder without a packet,
and no close on a refused record. A run file is filed under `inputs/` where the close will not judge it as
terms, and a replaced record goes to `superseded/` where it is named and counted but does not block.

The tools underneath can also be run alone, when a job already exists:

```
$ plumbline.py --doctor                              # environment + which enforcement level can run
$ plumbline.py --corpus ~/edi path/to/job            # a job directory: packet + every record in it
$ plumbline.py --corpus ~/edi packet.json record.json
$ emit_packet.py --brief brief.json --out-dir <job>  # terms only
$ emit_record.py --run run.json --out-dir <job>      # one iteration's §5 record + its filed passes
```

### What the emitters refuse, rather than warn about

Every refusal below stops the write. A record that fails the law is worse than no record, because it looks like
one — and a packet the gate cannot read is not a job's terms.

| refusal | rule |
|---|---|
| a pass whose scores are not a list of `{dimension, score}` | the checker reads a list; a dict keyed by dimension counts as observing nothing |
| a filed scored pass with no dimension observed | the pass is the evidence that it happened |
| a void pass carrying scores | §5: file the cause, not a reading |
| a violation class outside rule 4's four locators | `artifact_missed_standard` · `standard_moved` · `dimension_unauthorized` · `frame_at_fault` |
| a pass scoring a dimension the record does not declare | **C35** — evidence not attributable |
| a declared dimension no filed pass observed | **C35** — zero is not one, and rule 10 labels one |
| a `regenerate` with no violation | **C36** — an iteration that names nothing it is tasked with is not an iteration |
| a below-floor dimension with no violation naming it | **C36** — the shortfall is classified into a locator and the violation carries `dimension` |
| a scored brief with no `k` or `x` | **B.1.2** — both are declared per job, and a bound written after the run is not a bound |
| a violation naming a dimension the record does not declare | C35's link applied to C36's new field — *this instance's addition* |

Corpus resolution is not the same for every kit command:

- `kit/emit_record.py` and `kit/plumbline.py` use the shared resolver, `tools/edi_corpus.py`: `--corpus` →
  `$EDI_CORPUS` (unset or `""` counts as not set) → `plugins.edi-loop.corpus` in `$HERMES_HOME/config.yaml`, else
  `~/.hermes/config.yaml`; the first rule that is set wins. Reading the Hermes config needs PyYAML; a config that
  cannot be read (no PyYAML, bad YAML) is reported with its path and treated as no corpus. A set value that is not a
  corpus is a usage error (exit 2) naming it, and never falls through to the next rule. `PLUMBLINE_REQUIRE_CORPUS`
  is read first: `1` requires a corpus, unset, `""` or `0` leave it off, any other value is exit 2 naming the
  variable. The source that resolved is printed as `corpus source: <src>`.
- `kit/emit_record.py` resolves the corpus **before it writes anything**: with no corpus (`PLUMBLINE_REQUIRE_CORPUS=1`
  included) it exits 1 and writes nothing; with a bad source it exits 2 and writes nothing; with a corpus it writes
  the record and its pass files and runs the corpus validator on them. `--print-only` writes nothing and needs no
  corpus.
- `kit/emit_packet.py` and `kit/plumbline_job.py` read `--corpus` and `$EDI_CORPUS` only (no Hermes config, no
  `PLUMBLINE_REQUIRE_CORPUS`). `kit/emit_packet.py` refuses with exit 2 when no corpus resolves.

## Two layers, and the product harness

A custody record is judged at **two layers**. The **standard layer** is the custody corpus's own
`checker/check.py` at CL1; per SPEC.md line 141 it **ignores every `x-` key**, so it never reads `x-plumbline`.
The **Plumbline layer** is `kit/plumbline_verify.py`: it runs `check.py` first, requires OK, and then enforces
the `x-plumbline` block the emitter writes — hand times and their allowance, events against the ledger and logs,
spend, and the no-shadow rule. `x-plumbline` is enforced by Plumbline only. The verifier exits `0` (OK at both
layers), `3` (the standard layer failed), `4` (the Plumbline layer failed) or `2` (cannot run); every failure
prints `FAIL <kind> <field> <file>:<line>`. `plumbline_job.py close` and `custody` run it and refuse on failure.

The model calls are made by the product harness under `tools/edi/`: `or_call.py` (one logged call, with the
pre-call spend guard and `--max-cost`), `judge_batch.py` (a rotated model-judge batch), `fixture_run.py` (a
mode-normalizing fixture runner) and `extract_files.py` (the whole-file reply extractor). `custody_ledger.py
spend` records the reading `or_call.py --spend-status` writes. Every summary-writing instrument stamps its own
`started_at`, `finished_at` and `writer`.

## Adopting this in your own program

The kit is the part that travels. These four things are what a deployment installs, and one it should not.

**1. The corpus's skill — take it.** `skills/evaluator-driven-iteration/` in the corpus (`~/…/edi/`), copied
into `~/.hermes/skills/`. That is where the doctrine's procedure lives, and it is canonical — do not write your
own version of it.

**2. The doctrine's public checkers — use them.** The four deterministic checks live in
[`evaluatordriven/doctrine`](https://github.com/evaluatordriven/doctrine/tree/f8bfb79/contracts/tools) at `contracts/tools/` (pin `f8bfb79`, v0.2.1):
`validate_job_packet.py`, `check_role_separation.py`, `check_terminal_state.py` and
`check_best_artifact_handoff.py`. Run them directly; do not re-implement them. The earlier `edi-loop` Hermes
plugin wrapped these same checks, but its corpus copy (`integrations/hermes-edi-loop/`) no longer exists and
it is not part of the public contracts, so nothing here depends on it. The same check the kit runs at open and
close is the check you run in flight; the difference is only when it is called.

**3. Two traps, both measured on this repo rather than read about:**

- **Never park a plugin backup inside `~/.hermes/plugins/`.** A sibling directory carrying a `plugin.yaml`
  **is** a plugin: discovery loads it, and a same-name duplicate can quietly win the registration — so every
  disk check says the new code is installed while the old code answers. Back up to `~/.hermes/backups/`.
- **After any install, assert exactly one directory declares the name:**
  `grep -l '^name: <plugin>' ~/.hermes/plugins/*/plugin.yaml`. One line, and it is the difference between
  debugging the fix and debugging the ghost of the fix.

**4. This repo's own skill (`kit/skill/plumbline/`) — generate yours instead of copying it.** It names *this*
repo's path and tree, so it is wrong in yours. Write your own from the two commands above: two hand-written
command sets is the drift trap this kit exists to measure.

**And one thing not to take: `plumbline-gate`.** The discoverability gate is instance machinery built for this
direction's design consequence (§8 leaves that to each deployment) — not a doctrine requirement. If your program
wants one, build it for your program, and keep it **job-scoped**: ours governs every session on the machine
while armed, which is a declared defect of it, not a feature to copy.

## The three verdicts

| verdict | meaning |
|---|---|
| `OK` | the corpus checker ran and passed |
| `FAILED` | the corpus checker ran and rejected the artifact |
| `NOT-CHECKABLE` | no checker applies, or the artifact is in a shape no checker can read |

**Not-checkable is not a pass.** A record no checker can read is a finding. Exit code is 1 when anything
failed or nothing could be checked, so a pipeline cannot mistake silence for success.

## A weak OK is not a verdict

`validate_job_packet.py` runs a stdlib structural check always, and the Draft 2020-12 schema pass only when
`jsonschema` is importable — "a packet must pass both", by its own docstring. Both used to print the same word
`OK`. Measured on one packet with one invalid value: `OK`, exit 0 under python 3.9 without jsonschema;
`FAILED`, exit 1 under python 3.11 with it. Since proposal 0049 the tools name the level
(`OK (schema-verified)` / `OK (structural only)`), and **this kit refuses to certify on the structural-only
path** — it marks those rows `OK*` and exits 1.

## What has been demonstrated

- **Planted defects:** 8 cases, two controls (a readings packet and a scored one), each mutation a defect the
  doctrine names — `ratified: false` reaching `accepted`, `evaluator: "Owner"`, blank `escalation`, bounds on a
  readings job, Maker identity equal to Evaluator identity, and a markdown packet that must read
  NOT-CHECKABLE. `python3 cases/run_cases.py <corpus>` → 8/8. The first draft of that runner reported 7/7 while
  its control was failing, because its assertion was a substring match; the control caught it.
- **A real deployment:** against the first external deployment's job directory, the kit reports
  `0 ok · 8 failed · 7 not-checkable`, reproducing that audit's structural findings mechanically.

## Scope limits

No doctrine change. No corpus edit — if one is owed, it is a proposal, not a quiet edit. Transport is git and
corpus resolution follows the existing rule, so a machine on a different cloud is not excluded. Publication and
verification belong inside this kit rather than after it: a checker that cannot reach the record certifies
nothing.
