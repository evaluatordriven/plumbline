# Plumbline

**A custody/v1 emitter plus an E-DI kit.**

- **Custody.** Plumbline writes [custody/v1](https://github.com/evaluatordriven/custody) records for a job's
  work (`kit/emit_custody.py`, fed by the append-only ledger in `kit/custody_ledger.py`) and verifies them at
  two layers (`kit/plumbline_verify.py`: custody's own checker first, then Plumbline's `x-plumbline` block), which
  needs a checkout of custody at its pinned commit `3e3ca58` (`--custody`; the verifier will not run without it).
- **E-DI kit.** It carries software work through Evaluator-Driven Iteration: every stage transition is gated by
  an evaluator independent of whoever produced the work. Jobs open and close through `kit/plumbline_job.py`;
  `kit/plumbline.py` runs the doctrine's own checkers over a deployment's records.

It was built under, and runs well under, [Hermes Agent](https://github.com/NousResearch/hermes-agent), but
nothing in the emitter, the verifier or the test suites needs it.

## The one rule that shapes everything

**A prompted model promises; a configured instance enforces.**

Contracts §3's must-ask list lives in a schema, not in an instruction. "While `ratified: false` the must-ask
fields must be absent" is a JSON Schema `if/then` — structurally impossible to violate. If you are about to
add a paragraph telling an agent to behave correctly, stop and ask whether it should be a schema constraint
or a hook instead.

## Quickstart

You need `python3` (tested on 3.13) and `git`.

```sh
git clone <this repository> plumbline && cd plumbline
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # jsonschema, the only required dependency
```

**One command runs every suite** — no corpus, no custody checkout, no `~/.hermes` needed:

```sh
python3 tests/run_all.py     # every suite below, plus kit/cases/run_cases.py; the last line is the tally
```

With no corpus it passes on everything a stranger can check, and names each corpus check it could not run,
one line each, never silently: `SKIP[corpus] <id>: <reason>` for `corpus.audit-equality`,
`corpus.battery-equality`, `corpus.build-check`, `corpus.pin-on-disk` and `corpus.run-cases`. Its last line is
`PLUMBLINE-TALLY pass=7 fail=0 skip=5 skipped=<those ids>`; it exits 0 exactly when `fail=0`. With a corpus
each id prints `RAN[corpus] <id>: pass` (or `fail`) instead, and the tally is `pass=12 fail=0 skip=0 skipped=-`.

The suites it runs, each of which also runs on its own with nothing else:

```sh
python3 tools/build_schemas.py --check                 # vendored corpus copy matches VENDOR.json and tools/pin.json
python3 tests/validate_schemas.py                      # behaviour, and the corpus fixture battery on the vendored copy
python3 tests/validate_audit.py                        # audit records discovered by convention (none ship here); every verdict recomputed
python3 tests/validate_pin_prose.py                    # the prose pins agree with tools/pin.json
python3 tests/validate_constitution.py                 # the standing frame's schema behaves as designed
python3 tools/build_schemas.py --custody --check       # vendored custody schema + derived schema (partial: upstream not compared)
python3 -m unittest discover -s tests -p 'test_*.py'   # emitter, ledger, verifier, job lifecycle
```

The corpus schemas and fixture battery those suites read are **vendored** at the pin, byte for byte, in
`schemas/vendor/e-di@f8bfb793/` (provenance and every file's sha256 in its `VENDOR.json`; licence in `NOTICE`).

**Opting in to the corpus checks.** With a checkout of the public corpus ([`evaluatordriven/doctrine`](https://github.com/evaluatordriven/doctrine)), set
`EDI_CORPUS` and the same commands also check the corpus itself: that it is still at the pin, that the derived
schemas rebuild byte-identical from it, that the vendored copy is still its bytes, and the kit cases:

```sh
export EDI_CORPUS=/path/to/doctrine/contracts   # evaluatordriven/doctrine at f8bfb7934dbbefe3b32bc146b4481dba1744bc53
python3 tests/run_all.py                   # each corpus id now prints RAN[corpus] <id>: pass
export PLUMBLINE_REQUIRE_CORPUS=1          # make a missing corpus a failure, never a skip (for a gate)
```

The two variables, exactly:

- `EDI_CORPUS`: unset or `""` means not set. A set value that is not a corpus checkout (it has no
  `schemas/job-packet.schema.json`) is an error: exit 2, naming the path. It never falls back to the vendored
  copy or to the Hermes config.
- `PLUMBLINE_REQUIRE_CORPUS`: only the exact value `1` turns it on, and then every corpus check that would
  SKIP is a `FAIL[corpus] <id>` instead and the run exits non-zero. Unset, `""` or `0` leave it off. Any other
  value (`true`, `yes`, `on`, `2`, ` 1`) is a usage error: exit 2, naming the variable.
- `tools/build_schemas.py`, `kit/plumbline.py` and `kit/emit_record.py` also take `--corpus PATH` (first), and after `EDI_CORPUS`
  fall back to `plugins.edi-loop.corpus` in `$HERMES_HOME/config.yaml` or `~/.hermes/config.yaml`. Whatever
  resolves is printed as `corpus source: --corpus`, `corpus source: EDI_CORPUS` or
  `corpus source: hermes-config <path>`; nothing is printed when no corpus resolves. A Hermes config that
  exists but cannot be read (no PyYAML, or bad YAML) is reported with its path and the reason, and the tool
  carries on as with no Hermes corpus. A readable config whose `corpus` value is not a corpus checkout is an
  error naming the config and the path (exit 2), like a bad `EDI_CORPUS`.

**Commands that still need the corpus** (they refuse, or report `NOT RESOLVED`, without it):
`kit/emit_packet.py` (it reads the corpus schema and runs the corpus gate, so with no corpus it refuses),
`kit/emit_record.py` (it resolves the corpus before writing: with no corpus it writes nothing and exits 1, and a
bad `--corpus`, `EDI_CORPUS` or `PLUMBLINE_REQUIRE_CORPUS` exits 2 naming it), `kit/plumbline_job.py` (open and close), `kit/plumbline.py <paths>` (it wraps the corpus's
checkers), `kit/cases/run_cases.py` (with no corpus it prints `SKIP[corpus] corpus.run-cases` and exits 0), and
`tools/build_schemas.py` in build mode (`--repin` included). `kit/plumbline.py --doctor` reports
`corpus NOT RESOLVED` and exits 0, or 1 under `PLUMBLINE_REQUIRE_CORPUS=1`.

**To compare against custody's upstream**, clone it and set `CUSTODY_DIR`:

```sh
git clone https://github.com/evaluatordriven/custody
git -C custody checkout 3e3ca58de5631bdc58291564303a2e9d25a8653e
export CUSTODY_DIR=$PWD/custody
python3 tools/build_schemas.py --custody --check   # now also compares the upstream pin
```

With `CUSTODY_DIR` set, `tests/test_plumbline_verify.py` also runs the clean fixture against custody's real
checker (see Known limitations). How to emit and verify a record is in **`docs/custody-emission.md`**.

## The doctrine this obeys

Plumbline's schemas are **derived from the public corpus
[`evaluatordriven/doctrine`](https://github.com/evaluatordriven/doctrine) at `e-di@f8bfb7934dbb` (Contracts
v1.27.0)**, read from its `contracts/` directory. `tools/pin.json` records the commit, that path, every source
file's sha256, and the sha256 of `DOCTRINE.md` and `AUTHORITY.json` (pinned so `--check` reports their drift;
nothing is derived from them). The summary and the load order are in
**`AGENTS.md`** — read it before changing anything.

Cite the commit, not just the version: a version number cannot be checked, a commit can. The build refuses to
run against a moved corpus; re-read, then `--repin`.

## Derived, not forked

Plumbline does not author its own field names. Its schemas are **generated** from the pinned corpus plus the
instance layer:

```
tools/build_schemas.py   corpus @ pin  +  schemas/instance-extensions.json  ->  schemas/*.json
```

`schemas/instance-extensions.json` is the only place instance law is written; everything else under `schemas/`
is derived and must never be hand-edited. The invariant that keeps this honest is one-directional: **every
packet Plumbline accepts, the corpus accepts too.** Plumbline is an instance, so it may constrain itself more,
never less.

The custody record schema is derived the same way from the vendored `schemas/custody/custody-v1.schema.json`
(`tools/build_schemas.py --custody`).

## Where Plumbline's content lives — `dot-plumbline/`

Every program Plumbline touches carries its content in a directory named **`dot-plumbline/`**, in the
program's own space and committed — **never** gitignored, it is evidence. No leading dot, so nothing is hidden.
Contracts §10.1 retains the records *with the artifact*, so an audit of another program lives in that
program's repository. In this public repository `dot-plumbline/` holds only Plumbline's README and its ratified
`constitution.json`; Plumbline's own job, audit and probe records are kept in a private evidence archive, and
two of its jobs are published, frozen, under `examples/` (below).

```
dot-plumbline/
  README.md          the convention, and which doctrine commit this program obeys
  constitution.json  the standing frame — ratified once, versioned  [instance layer]
  jobs/<job_id>/     packet.json · each iteration's artifact + §5 record · per-dimension vectors
  run-log.json       append-only: run id · commit · seats · bounds · dimensions + verdict · escalation · cost
  audits/            conformance audits of THIS program, as §5 records
```

`tests/validate_audit.py` searches the directory that holds this checkout (or `$PLUMBLINE_AUDIT_ROOT`) for
`*/dot-plumbline/audits/`, and **names** any program whose records it cannot read — a validator that silently
checks nothing is worse than none. This repository ships no audit records, so on a plain clone it runs its
schema checks and says, by name, that no records were in reach.

## Examples — frozen job records

`examples/` holds two of Plumbline's own E-DI jobs exactly as they were closed, each with its custody/v1 record:
`2026-10-27-custody-emitter-gaps` and `2026-10-28-custody-times-ledger-spend`. Both re-check `OK`, `CL1`, 19/19
with custody's public checker at `3e3ca58`; `examples/README.md` gives the commands.

**Provenance.** These records are frozen evidence and are not rewritten. Each record's digests bind the bytes
of its files, so the files keep the paths, user names and machine names of the environment that produced them
(for example home-directory paths, box paths and model-harness logs); editing them to tidy those would break
the records. The subject files each record judges come from commits in a private repository, so their exact
bytes are shipped beside the jobs in `examples/subjects/<job-id>/`. `examples/subjects/` is those subject bytes only:
it is not Plumbline's codebase, and nothing in Plumbline imports or runs it. The two records predate the current
`x-plumbline` schema, so `kit/plumbline_verify.py` passes them at the custody layer and reports exit 4
(Plumbline-layer schema) on them; that is expected and is not a custody failure.

## Layout

```
AGENTS.md   the doctrine, the invariants, the instance layer — read this first
kit/        the emitter, ledger, verifier, job lifecycle and conformance entry point (+ kit/README.md, kit/skill/)
schemas/
  instance-extensions.json   AUTHORED — Plumbline's labelled instance layer (Contracts §8 / C18)
  constitution.schema.json   AUTHORED — the standing values frame (instance-specific)
  job-packet.schema.json     DERIVED  — corpus §3/§6 + the instance layer
  evaluator-record.schema.json DERIVED — corpus §5, shape-for-shape
  audit-record.schema.json   DERIVED  — corpus §5 + the three required audit extensions
  compliance-checklist.json  DERIVED  — Contracts §9 as data, authored `why` re-attached by id
  custody/ + custody-record.schema.json   VENDORED custody/v1 schema and the record schema derived from it
  legacy/                    FROZEN   — one directory per schema generation; a filed record keeps its vocabulary
tools/      build_schemas.py + pin.json, and the instance's measurement tools
gate/       the discoverability gate (a Hermes plugin; optional)
docs/       custody emission, the orchestrator field guide
dot-plumbline/  THIS program's README and ratified constitution (its jobs and audits stay in a private archive)
examples/   two frozen job records with their custody/v1 records, and the subject bytes they bind
tests/      the suites
```

## Known limitations

- **The corpus checks need a doctrine checkout.** The schemas and fixtures the suites read are vendored, so
  every suite runs without one, and the five checks that need the corpus itself print `SKIP[corpus] <id>` by name (see
  above). The emitters (`kit/emit_packet.py`, `kit/emit_record.py`), `kit/plumbline_job.py`,
  `kit/plumbline.py <paths>`, `kit/cases/run_cases.py` and the schema build still need a corpus checkout.
- **Hand-entered times.** The emitter refuses a hand-entered time by default (exit 3, kind `hand-time`). Under
  `--allow-hand-times` it records each one in `x-plumbline.hand_times[]` and never verifies it. Records made
  before the ledger existed may carry flagged hand times. Details: `docs/custody-emission.md`.
- **Custody's real checker.** `kit/plumbline_verify.py` always needs a custody checkout at `3e3ca58` (`--custody`
  is required, and the `x-plumbline` layer runs only after custody's checker passes). With `CUSTODY_DIR` set to
  custody @ `3e3ca58`, the real-checker test runs the
  `tests/fixtures/custody/verify/real/` fixture (a synthetic job and the record `kit/emit_custody.py` emitted
  for it, its hand times flagged) through custody's real `checker/check.py`, directly and through the verifier,
  and passes. The shared `clean/` fixture's record is a stand-in that only the stand-in checker accepts. Without
  `CUSTODY_DIR` that test skips.
- **CI runs the stranger's run.** `.github/workflows/ci.yml` runs `tests/run_all.py` on Python 3.11, 3.12
  and 3.13 with no corpus and an empty `HOME`, then checks out custody's upstream at its pin, compares the
  vendored custody schema with it, and runs the real-checker test against it with `CUSTODY_DIR` set. A separate CI job clones `evaluatordriven/doctrine` at the
  `tools/pin.json` commit and runs `tests/run_all.py` with `PLUMBLINE_REQUIRE_CORPUS=1`.
- **Instance tools.** Some tools under `tools/` measured Plumbline's own private records (for example
  `check_operating_loop.py`, `measure_operator_burden.py`, `run_conformance_read.py`, `probe_jev_evaluator*.py`)
  and do not run on a plain clone.
- **Rules not yet exercised.** Contracts v1.26.0 added C37–C40, the §4 roles table and Instrument A2/I2.
  `schemas/compliance-checklist.json` lists C37–C40, but no Plumbline check, case or fixture exercises them,
  and nothing here enforces the roles table or A2/I2. They are disclosed gaps, not covered rules.
- **Versions.** This is 0.1.0, dated 2026-11-02 (`CHANGELOG.md`).

## Licenses

- Text (README, AGENTS, CHANGELOG, CONTRIBUTING, SECURITY, `docs/`, `standards/`, the Markdown under `kit/`,
  and job records): **CC BY 4.0**, © 2026 Steve Moitozo II — see `LICENSE`.
- Code (`kit/`, `tools/`, `tests/`, `gate/`, `schemas/` and their fixtures): **Apache-2.0** — see `LICENSE-CODE`.
- Copyright notice and which folder is which: `NOTICE`. The vendored custody/v1 schema is from
  `evaluatordriven/custody` under Apache-2.0.
