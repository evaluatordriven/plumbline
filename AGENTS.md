# Plumbline — AGENTS.md

Session context for AI agents working in this repo. Read this before touching anything.

## Project Overview

Plumbline is a **custody/v1 emitter plus an E-DI kit**: it writes and verifies custody/v1 records for a job's
work, and it carries software work from requirements elicitation through development, deployment and revision
so that every stage transition is gated by an evaluator independent of whoever produced the work. It was built
under, and runs well under, Hermes Agent; the Hermes-specific notes below apply only there.

It is **not** a pipeline framework, and it is **not** a second copy of the doctrine. Orchestration is reused
from the Kingsgate pattern (role-per-profile, a conductor script, `no_agent` crons). What Plumbline adds is
the **instance layer** — the labels, the standing frame, and the discoverability gate that E-DI deliberately
leaves to each deployment (Contracts §8) — plus the conformance audits that check real instances against the
doctrine.

The strategy documents (goals, architecture, decision log) are kept outside this repository.

## The one rule that shapes everything

**A prompted model promises; a configured instance enforces.**

Contracts §3's must-ask list lives in a schema, not in an instruction. "While `ratified: false` the must-ask
fields must be absent" is a JSON Schema `if/then` — structurally impossible to violate. If you are about to add
a paragraph telling an agent to behave correctly, stop and ask whether it should be a schema constraint or a
hook instead.

## The doctrine this obeys — seven weight-bearing files, authority by question

Plumbline's schemas are **derived from the public corpus `evaluatordriven/doctrine` at `e-di@f8bfb7934dbb`
(Contracts v1.27.0)**, its `contracts/` directory. Point `--corpus` or `$EDI_CORPUS` at
`<a checkout of it>/contracts`; `tools/pin.json` requires exactly that path. **When two files disagree,
`AUTHORITY.json` at the doctrine's top level says which wins**; read it before acting on a conflict. Record the
commit, not just a version: a version number cannot be checked, a commit can. Every derived schema names the pin.
**Re-pinning is a deliberate act, and the build refuses until you do it.** `tools/build_schemas.py` will not
run when the corpus has moved, because a silent stale build is the failure mode. Re-read the changed doctrine,
then `--repin`. A re-read under a moved rubric is a NEW job, never a correction of an old one — same runner
with a different rubric is a different instrument (C30).

**A changed derived hash is NOT a moved rubric.** The pin is embedded in every derived file's `description`, so
a pin-only bump changes all four hashes while the law is untouched. Measured 2026-09-30: the corpus moved only
to file an evaluation record and bump a skill pointer; four derived files changed hash and the sole diff in
each was `edi@318533b6bc00` -> `edi@2f8a54be9cae`, with the checklist's clause text and every `why`
annotation byte-identical. **Read the diff.** Treating a hash change as a rubric move would declare a new job
under C30 and wrongly invalidate an existing read.

Authority is **by question**, and the load order is published in exactly one place — `EDI-FOR-MACHINES.md`.
Do not invent another sequence.

| Question | Primary home |
|---|---|
| Purpose, values, behaviour, strategy, priority, **seat meanings** | `EDI-PLAYBOOK.md` (the clarity spine; changes least) |
| The corpus's own must / must not, failure conditions | `EDI-MANDATE.md` (the frame instrument, Contracts §1.7) |
| States, schemas, pass rule, NORMATIVE implementer law | `EDI-MACHINE-CONTRACTS.md` |
| **The form of one handoff** | `EDI-OPERATING-INSTRUMENT.md` (rank 2; loses to Contracts only on mechanics) |
| One worked job to copy | `EDI-EXAMPLE.md` |
| Agent load order and bans | `EDI-FOR-MACHINES.md` |
| Human on-ramp | `EDI-QUICKSTART.md` |

**Not authority, ever:** `evidence/**`, `proposals/**`, `evaluation/**` (unless the job *is* to audit them),
`EDI-PRIMER.md`, `EDI-ARCHITECTURE.md`, `EDI-CHANGELOG.md`, Applied/Research narratives. The Primer explains
*why*; it is not law. Implementing from an Applied narrative is the documented failure mode — it promotes
examples to defaults.

A conflict between the Playbook and the Contracts on **seats or purpose** escalates to the Owner. On
**states or schema**, obey the Contracts and report the conflict. Never quiet-edit the Playbook down to match
a projection.

## How the schemas are made — derived, never hand-edited

Plumbline no longer authors its own field names. It shipped a second job-packet schema that disagreed with
the corpus's own (measured: the corpus's fixtures give 18 errors against it). Two live schemas for one law
means neither is authority, and a hand-copied schema drifts silently.

```
tools/build_schemas.py   corpus @ pin  +  schemas/instance-extensions.json
                         -> schemas/job-packet.schema.json       (corpus §3/§6 + instance layer)
                         -> schemas/evaluator-record.schema.json (corpus §5, shape-for-shape)
                         -> schemas/audit-record.schema.json     (corpus §5 + required audit extensions)
                         -> schemas/compliance-checklist.json    (Contracts §9, `why` re-attached by id)
                         -> tools/pin.json                       (commit + every source file's sha256)
```

- **`schemas/instance-extensions.json` is the only place instance law is written.** Everything else in
  `schemas/` is derived and must never be edited by hand — a hand edit is erased by the next build and is
  invisible in review.
- **The build refuses to run when the corpus has moved.** Re-read the changed doctrine, then `--repin`.
  `--check` verifies the pin without writing; run `tests/run_all.py` before every commit (CI runs it too,
  with no corpus).
- **The corpus is vendored at the pin.** `schemas/vendor/e-di@f8bfb793/` holds the corpus's two schemas and
  its fixture battery, byte for byte, with `VENDOR.json` (provenance, every sha256). The battery runs on it, so
  the suites need no corpus; `tools/build_schemas.py --check` fails when the copy, `VENDOR.json` and
  `tools/pin.json` disagree. Never edit the copy; re-vendor it from the corpus when the pin moves.
- **Corpus resolution follows the edi-loop plugin's own rule** — `--corpus`, else `EDI_CORPUS`, else (under
  Hermes, in `tools/build_schemas.py` and `kit/plumbline.py`) `plugins.edi-loop.corpus` in
  `$HERMES_HOME/config.yaml` or `~/.hermes/config.yaml`. No homedir guessing: a wrong guess produces a silent
  stale build. The rules are in `tools/edi_corpus.py`: an empty `EDI_CORPUS` is unset; a set one that is not a
  corpus is an error naming the path and never falls through; the resolved rule prints `corpus source: …`; an
  unreadable Hermes config is reported with its path and reason.
- **No silent skips.** A check that needs the corpus and has none prints `SKIP[corpus] <id>: <reason>`;
  `PLUMBLINE_REQUIRE_CORPUS=1` (only `1`; `""`/`0` are off, anything else is a usage error) turns each into
  `FAIL[corpus] <id>`. `tests/run_all.py` prints one line per id and the `PLUMBLINE-TALLY` last.
  `kit/emit_packet.py`, `kit/emit_record.py` and `kit/plumbline_job.py` still need a corpus (without one,
  `emit_packet.py` refuses and `emit_record.py` exits 1 with its output unvalidated).
- **`tools/pin.json` is PLUMBLINE-relative** — it lives in this repository, and its `corpus` field names the
  corpus repository, not a local path. It does **not** exist in the corpus checkout, so a reader looking for the pin under `edi/` will not find it. The
  conformance runner resolves its `corpus:` surface entries through it.

**The one-directional invariant.** Plumbline is an instance, so it may constrain itself **more**, never
less. `tests/validate_schemas.py` runs the corpus's own fixture battery through both schemas and asserts
that **no fixture is accepted by Plumbline and rejected by the corpus** (the battery is the vendored copy;
with `EDI_CORPUS` set, `corpus.battery-equality` checks the copy is still the corpus's bytes). If that ever fires, Plumbline has
become its own law.

## Key invariants from the doctrine (do not weaken)

- **Roles separate, and the seats are seven:** Owner, Architect, Buyer, Specialist, Maker, Evaluator,
  Orchestrator (Playbook §6, Contracts §4). One party may hold several — **recorded as such**. The Owner may
  never hold the Evaluator seat on the same job. The Maker never grades its own work.
- **The Evaluator recommends; the Orchestrator applies.** Only the Orchestrator applies the pass rule, the
  cap, and escalation. An Evaluator that decides whether to iterate has collapsed two roles. Applying
  escalation means handing `needs_owner` to the Architect, which writes the options and the recommendation;
  the Orchestrator delivers them to the Owner and writes none of it. **Plumbline rule** (Owner ruling
  2026-11-04, `schemas/instance-extensions.json` → `escalation_pen`): no doctrine tier names this pen, and
  Contracts §4's "recommends … and the Architect decides" is about a design gap, not `needs_owner`.
- **Pass rule = `mean >= T_accept` AND `min >= T_dim`.** An average alone lets a fatal defect be averaged
  away.
- **A verdict needs ≥2 scored runs.** One run is a sample, not a measurement, and a reading resting on one
  run is labelled as such (Instrument rule 10).
- **Terminal states are exactly `accepted`, `needs_owner`, `rejected`** — and a record carries the **outcome**
  it exited under: `accepted` · `census` · `needs_owner` · `rejected` · `no_observation` · `no_artifact`.
  An outcome is not a state. Cap-reached above the floor is `needs_owner`, **not** `rejected` — routing it to
  `rejected` discards work a human was meant to see.
- **`mode: scored` requires a Specialist named at the outset.** With none, the job declares `mode: readings`,
  supplies **no thresholds**, returns *conforms / does not conform / unobserved* and **never numbers**, and
  **may not produce `rejected`** — there is no floor to be below. Naming a Specialist after the readings are
  in does not license scoring.
- **A dimension with no observation ⇒ forced `needs_owner`,** never `rejected`, never a synthesised
  below-floor score. `observation` is required by the schema, so this is structural.
- **A dimension that saw ground truth is invalid.** `saw_gt` fails that dimension (§7.2).
- **Entry is decided by the artifact, not by intent.** Work that already exists is Entry B — a labelled
  baseline (C32) that is legal only when `reads_before_freeze` names the reads that could reveal a defect and
  states they came after the rubric was frozen. A fix is a **new job**.
- **Violations are classified into rule 4's four locators** — `artifact_missed_standard`, `standard_moved`,
  `dimension_unauthorized`, `frame_at_fault` — never "bad Maker". **There is no severity scale**: `P0/P1/P2`
  are undefined and must not be copied or invented. The shortfall is required; the **remedy is optional**,
  and a fabricated remedy is itself a violation.
- **The instrument is retained with the artifact**, and it is **both** the rubric and the code: the record
  names its version and the sha256 of rubric **and** runner (C30). A re-run holding the same rubric and a
  different runner is a different instrument.
- **A revision carries a control in the same batch.** Comparing against a stored score reports the
  instrument's drift as change in the artifact — measured: a document scored 8.64 returned 8.33/8.14/8.00/
  7.86/8.39 on byte-identical input.
- **Carry the best parts forward.** The standing artifact is the frontier; the **best** artifact is the
  Maker's input, with every known defect and its measurement. A trade is the Owner's to declare.
- **Verdict and disposition are separate acts.** The Owner may ship a reject or bin an accept; the recorded
  verdict stands as the loop produced it.
- **External writes are verified by read-back,** with a normalization declared before comparing and a value
  fresh on every run (§7.3).

## The instance layer (Contracts §8 / C18 — labelled, and it weakens nothing)

Declared in `schemas/instance-extensions.json`. Each item is Plumbline's, not the doctrine's:

- **The standing constitution** (`constitution.schema.json`) — the Owner's values, principles and escalation
  classes for one program, each value carrying a `decision_rule` so it can arbitrate. **Subordinate to the
  mandate:** the mandate is the doctrine's frame instrument; the constitution is this instance's encoding of
  it. A disagreement escalates to the Owner and is never auto-resolved.
- **`stage`** — the chain-of-loops label, **optional**, and **the decision is DEFERRED, not open**.
  `constitution.schema.json` declares `principles[].applies_to_stages`, so a stage-scoped principle would be
  evaluated *using the packet's stage* — but **the ratified constitution carries no stage-scoped principle**:
  of its seven principles exactly one declares `applies_to_stages`, and it declares it empty (`[]` — the whole
  chain, not a stage), so nothing is scoped to a stage and the trigger never fires. *(Corrected 2026-10-01:
  the earlier reason — "no constitution instance exists anywhere" — stopped being true when
  `dot-plumbline/constitution.json` was ratified. The deferral is unchanged; its stated reason was not.)* Requiring the field (or writing the stage → ground-truth/channel map
  as law) would be a check that cannot fail, which Instrument rule 3 bars.
  **Revisit when either:** (i) a constitution instance carries a stage-scoped principle; (ii) a conductor runs
  a real job whose ground-truth channel needs classifying.
- **What `stage` does *not* do:** carry the elicitation rule. A job with no independent ground truth cannot
  be scored whatever its label, because C33 requires non-empty `ground_truth`, `mandate_ref` and `escalation` on
  a scored job and an unratified job can never reach `accepted`. The field **classifies**; it does not gate.
- **The stage → ground-truth/evidence-channel map** lives only in prose (GOALS.md's Stage Map) and is law
  nowhere: the packet records its own `ground_truth[]` and nothing checks the row against the stage. That is a
  deliberate deferral, not an oversight — see above.
- **The discoverability gate** — before any escalation, classify: *discoverable* (search, measurement, reading
  the repo, probing the record, running the code) → resolve it and never ask; *undecidable* (values, doctrine,
  Buyer intent, priority, risk appetite) → escalate, carrying the question, what was tried, why no observable
  answer exists, **and the options with a recommendation** — written by the Architect, delivered by the
  Orchestrator (Plumbline rule: `escalation_pen`). An escalation without options is work pushed back.
  Metric: **discoverable-escalation rate**.
- **Seat entitlement** (Owner ruling 2026-11-06, every E-DI loop). Every seat must be provided everything it is entitled to for making its best contribution to the job — and nothing more. The list: clear instructions, essential context, necessary computing resources, appropriate tooling, adequate tokens, ample time, and the full scope of agency vested in that seat. Entitlement is the ceiling as well as the floor. Do not hand a seat another seat's material, another seat's agency, held-out, or a diagnosis it was not vested to make. The Orchestrator owns delivering this, and owns not delivering past it. Architect: the failure record of the job, the tree, the bars, the packet, the doctrine pin. Maker: the red, rule 12, and an editable set that includes the file the bar fails in. Evaluator: the frozen standard and the turn — never held-out material, never the Maker's model. Entitlement is the record and the paths, not the Orchestrator's diagnosis of the fix. A brief made short rather than complete is a choke; the seat answers honestly against a partial surface and the answer is useless.
- **Two dimensions the Contracts cannot supply** — *operator burden* and *proportionality*. Three of the
  direction's four falsification conditions cannot be contract violations, so a contract-derived evaluator is
  blind to them. **Operator burden is DEFINED as operator FRICTION** (2026-10-05, Owner instruction): zero weight
  on his ratifications, selections and amendments — architecture is a collaborative stage and his judgement there
  is designed-in — and weight only on what the loop took from him: a reading he had to ask about, a question
  asked twice, a re-ratification caused by a defect of ours. **Target zero, counted absolutely per job; never a
  ratio against engagement**, because that denominator lets the program that imposed more unnecessary work read
  better. Design rule: the metric must never be improvable by showing him less of the work. Declared in
  `schemas/instance-extensions.json` → `operator_friction`; first reading 1 event across 5 jobs.
- **The Maker carries task classes** (generation ≠ revision, each shown by a completed run). Doctrine requires
  this (§4.1, rule 10); C33 does not enforce it structurally, so Plumbline does.
- **The standing authorization** (`standing_authorization` in `schemas/instance-extensions.json`) — the Owner's
  risk appetite for **ordinary operating actions**, authorized 2026-09-30. Read the two lists **there**; do not
  restate them here, because a restatement is a second place to go stale. It came from measurement rather than
  preference: `tools/measure_operator_burden.py` found **236 repeated same-shape approval asks in 30 days**,
  while the Owner's two other operator-burden signals sat at zero. The defect was asking per *instance* about a
  shape already settled, so the three authorized shapes stop being questions and the rest keep asking.

## Enforcement available to this instance

The doctrine's public checkers in `evaluatordriven/doctrine` `contracts/tools/` (pin `f8bfb79`, v0.2.1) are
the four deterministic checks — `validate_job_packet.py`, `check_terminal_state.py`,
`check_role_separation.py`, `check_best_artifact_handoff.py`. **Use them; do not re-implement them here.**
(The older `edi-loop` Hermes plugin wrapped them; its corpus copy no longer exists and nothing depends on it.)
The skill is `evaluator-driven-iteration`.

**One gate.** Plumbline validates against the corpus's `tools/validate_job_packet.py`. A private jsonschema
pass is **not** a census of the corpus. `EDI-FOR-MACHINES.md:79` is the corpus-side rule, and it is **not
restated here** — *"`tools/validate_job_packet.py` is the full structural gate and covers the remaining object
shapes. Trust the checker, not the schema alone."* Cite it by location rather than copying it: a restatement
is a second place to go stale, which is the argument proposal 0001 already made about this file.

**Surface completeness.** The observed surface of any conformance read must **contain the enforcement layer**
— the gate, not only the schemas. A finding whose subject is a schema-versus-clause divergence is **not a
corpus finding until the gate has been run on it.** Measured 2026-09-30: with `escalation: ""` the gate exits
1 while a bare jsonschema pass reports **zero** errors over the same packet — so a read that observes only
schemas will report the schema's looseness as a defect in the doctrine. It did exactly that on 2026-09-29,
and the finding had to be withdrawn.

**Why this is not local hygiene.** A census scored against the schema while the corpus gate enforces is
running a **second ruler**. The rule set on 2026-09-29 applies unchanged — *the check that can override the
Evaluator is the Evaluator* — and a census that quietly outranks the corpus gate has become the corpus's real
evaluator.

**Three passes measure consistency, never correctness.** The ~25% clause spread below says one pass is not a
verdict; it does **not** say that agreement makes a reading true. The withdrawn C33 finding was stable across
**all three** passes — the instrument agreed with itself and was wrong together, because the surface omitted
the gate. **Repetition cannot detect a blind spot.** Check the surface before trusting the agreement.

**Run the gate, do not argue about it.** Dispositions for C5, C16 and C32 were settled on 2026-09-30 by
constructing each state the finding names and running the gate on it — never by reasoning that no gate could
bear on them. Inspection had already produced C20, the failure-test premise and C33, and it was wrong about
C5 and C16 too (it would have claimed the gate enforces neither; it in fact enforces cap/budget presence and
the 0028 A seat rule). Both probes are retained under the job's `instrument/`.

## Profile roster

**The Evaluator seat is built and has run a job.** `plumbline-eval` — model `z-ai/glm-5.3-flash` via provider
`openrouter`, a **different model family** from the Maker (DeepSeek), per rule 2. Smoke-tested before the job.

- **THE `base_url` TRAP, on every new seat.** A new profile inherits `model.base_url` from `default`. With
  `model.provider: openrouter` and an inherited `base_url: https://api.deepseek.com/v1`, GLM requests would
  have been routed to **DeepSeek's own server** — role separation nominally satisfied and actually violated,
  because the "independent" evaluator would have run on the maker's infrastructure. Clear `model.base_url`
  when pinning a seat, and verify the seat answers before building anything on it.
- **The seat is a heavy reasoner.** ~6.5k reasoning tokens per clause plus the surface, so 33 clauses in one
  call needs ~200k and never completes (`finish_reason: length`, empty content). Chunk the clauses; bound
  thinking with `reasoning: {max_tokens: N}`.

The remaining seats are unbuilt. The seat set is Playbook §6's seven; these are the profiles that would carry
them (one profile per role, model pinned per profile — the §4 role-independence mechanism).

| Profile | Seat | Tools | Notes |
|---|---|---|---|
| `<program>-conductor` | Orchestrator | none | Routes, enforces bounds, applies the pass rule, runs the discoverability gate; hands `needs_owner` to the Architect and delivers its options. Decides nothing. |
| `<program>-maker` | Maker | file, terminal (write) | Works in a git worktree |
| `<program>-eval` | Evaluator | file, terminal (read/run) | **Different model family** from the Maker. No write tools. |
| `<program>-deploy` | Deployment | terminal, web | Read-back verification scripts |
| `<program>-audit` | Auditor | file, terminal | Job-record audit + discoverable-escalation rate |

**Constraint:** `delegate_task` children all inherit one model from `delegation.*` config — there is no
per-child model. Role separation therefore requires separate profiles/processes, not subagents. This also
preserves prompt caching.

## Where a program's Plumbline content lives — `dot-plumbline/`

Every program Plumbline touches carries its content in **`dot-plumbline/`**, in the program's own space:
`dot-plumbline/` in a git repo — **committed, never gitignored** (it is evidence) — and `dot-plumbline/` in a
Drive project folder for a program with no checkout. Spelled out, no leading dot, so it is visible in `ls`,
in a git host's file list, and in a Drive client, with one name in both places.

**Records travel with the artifact (Contracts §10.1).** Failure F6 is *"accepted work cannot be reconstructed
from its records"*, so a conformance audit **of wsww** lives in wsww's repo. This repo's `dot-plumbline/` holds
Plumbline's audits **of itself**, and the per-program split is what keeps one home per record — a second copy
is the drift trap the corpus names.

```
dot-plumbline/
  README.md          the convention, and which doctrine commit this program obeys
  constitution.json  the standing frame — ratified once, versioned  [instance layer]
  jobs/<job_id>/     packet.json · each iteration's artifact + §5 record + per-dimension vectors
                     · instrument/  the rubric AND runner that produced the records, content-addressed
  run-log.json       append-only: run id · commit · seats · bounds · dimensions + verdict · escalation · cost
  audits/            conformance audits of THIS program — §5 records, or a labelled readings record
  probes/            measurements taken on this program — the reading plus the protocol that produced
                     it (operator burden, the JEV evaluator probe)
  operating-loop.jsonl  append-only history of the operating loop: one line per run, written by
                     tools/check_operating_loop.py — the commit, the checks that ran, the failures
```

Only what exists is present. `jobs/` and `run-log.json` appeared when job one ran; an empty placeholder is
structure nothing asked for.

**Retain the instrument, not just its hash.** The record names the runner's sha256 (C30), but the runner is a
source file that keeps changing — so the instrument that produced a past record is gone unless it was filed.
On job one the runner was patched after the run and the census's instrument no longer existed on disk; it had
to be reconstructed from git history. The runner now **archives itself content-addressed** on every run
(`instrument/run_conformance_read.<sha12>.py`), so a later version never overwrites an earlier one and two
instruments can coexist in one job.

## Conventions

- Scripts run under `python3` (tested on 3.13) after `pip install -r requirements.txt`; under Hermes, the Hermes
  venv's Python works too.
- **Never hand-edit a derived schema.** Change `schemas/instance-extensions.json`, then run
  `tools/build_schemas.py`. `tests/validate_schemas.py` asserts derived artifacts name their pin.
- `jsonschema` (draft 2020-12) is the only required dependency (`requirements.txt`).
- If a schema and a doc disagree, the schema wins and the doc gets fixed — and if the schema is derived, the
  fix belongs in the instance layer or upstream in the corpus.
- Do not add prose instructions here that should be enforced elsewhere. If removing a line would not cause a
  mistake, cut it.

## Current state

| Item | Status |
|---|---|
| Direction (outcome / done / falsification) | ✅ Set 2026-09-17 |
| Doctrine alignment (seven weight-bearing files) | ✅ **Re-pinned 2026-10-05 (sixth — PIN-ONLY, no new job)** — Contracts **v1.22.0**. The corpus moved once more for a **decision record and hygiene**: the enumeration-control candidate was CLOSED with no C-id, no version bump and no rule, and the *practice* survived it — `tools/check_consistency.py` now reconciles the fixture registry against the directory (43 · 43 · 0 unaccounted) and `tools/validate_evaluator_record.py` reports its population on every run. **Read the diff before believing the filenames:** the three files that moved are `EDI-CHANGELOG.md`, `MANIFEST.sha256` and that checker — **no weight-bearing file moved, so this is a pin-only bump** and every reading stands. **It did require a change here anyway, and not one the law demanded:** the changelog records *this repo's* zero-file short body as the evidence that striking clause 4 was over-generalised, so the practice was applied to my own reader — `--job-close` now states the population it read (files present · judged · skipped by name · not judged by shape) and a record naming an artifact that is not beside it, or that no longer hashes to what was recorded, **fails the close** — the sibling of C34's *evidence not filed*, one level up, which nothing had checked before. **Before that, the same day: a MOVED RUBRIC and a SHAPE change** — Contracts v1.22.0, C36 appended (an iteration names what it sends back), taken as a new job. Proposal **0053** applied as amended: **C36** appended (a `regenerate` carries at least one violation, *because an iteration that names nothing it is tasked with is not an iteration*; and a dimension below `T_dim` carries a violation whose class is rule 4's locator and whose `dimension` names it), `schemas/evaluator-record.schema.json` gained `violations[].dimension` — declared before any checker could require it, since the record schema sets `additionalProperties: false` and the violation object cannot know the scores, so the conditional lives in the checker — and two red fixtures were added. Re-read in `dot-plumbline/jobs/2026-10-05-contracts-1-22-0-reread/`, opened and closed by the kit's wrapper. **The obligation lands at the point of writing**: two refusals in `kit/emit_record.py`, the kit inherits C36 with zero changes and both new fixtures fail through it — held by cases. Checklist **C1..C36**; battery 44/44. The three records Plumbline already held are non-conformant under **C34** (no `passes`, so the checker stops before C36 — C36 adds no cost to them); recorded as three `finding` rows in the run-log, records unchanged per V1. **Before that, the same day: three earlier re-pins** — two moved rubrics and one pin-only bump from a proposal's filing. Proposal **0052** (one dimension, one name) was applied as amended: **C35** appended, `tools/validate_evaluator_record.py` and `tools/classify_rules.py` changed, a red fixture added. Re-read in `dot-plumbline/jobs/2026-10-05-contracts-1-21-0-reread/`, opened and closed by the kit's own wrapper. **The derived layer needed no change** — C35 is enforced by the checker, not the schema — and **the kit inherits it with zero changes**, proven live by the corpus's new fixture failing through it. The checklist follows to C1..C35 on its own; battery 44/44. **Before that, the same day, a pin-only bump** — a proposal's FILING moved the corpus and nothing weight-bearing moved with it. Our own proposal **0052** (one dimension, one name — filed, not applied) moved the corpus; the only files that moved are `proposals/` and `MANIFEST.sha256`, so **no weight-bearing file changed and this is a pin-only bump** — no new job, every reading stands. The pin moved because filing a proposal is a commit, and a pin is a commit: the discipline is to *read the diff*, not to treat every commit as a moved rubric. **Before that, the same day, a MOVED RUBRIC** (v1.20.0, taken as a new job — the state row does not quote the superseded commit, because `tests/validate_pin_prose.py` cannot tell history from a claim and reads any `e-di@<sha>` string as one; describe a superseded pin, never cite it). **This one is a MOVED RUBRIC, not a pin-only bump:** `EDI-MACHINE-CONTRACTS.md` moved (0050 as amended — a §5 record names its passes, C34 appended, §9/§10.1/§10.6 touched), so it took a **new job** — `dot-plumbline/jobs/2026-10-05-contracts-1-20-0-reread/` — and every prior reading stands as the 1.19.0 baseline, none re-issued. **The derived record shape now requires `passes`**, so Plumbline's own records file their passes from this job forward. The same day's second corpus change (0051, maintainer tooling only) added no re-read obligation. Earlier the same day: a pin-only bump when 0050 was filed; before that 2026-10-02 (0047/0048/0049, pin-only) and 0046's C1/§1.1 rescope. Derived layer rebuilt (78 in-scope rules, 0 uncovered), **44/44 schema cases**, **kit 16/16 including the corpus's own new red fixtures**, corpus `check_consistency` ALL CHECKS PASSED |
| Schemas | ✅ Derived from the pin; constitution is the only hand-authored schema |
| Compliance checklist | ✅ Rebuilt from §9 at the v1.19.0 pin — C1–C33, C17 retired and reserved |
| Conformance audits (eddie, wsww) | ✅ Filed 2026-09-18, pre-observation vocabulary. Each now lives with its program under `dot-plumbline/audits/`: wsww's in its repo, eddie's in its Drive project folder |
| **Job one — conformance census of Plumbline itself** | ✅ 2026-09-29. Entry B, `mode: readings`, §9 C1–C33 over 3 passes, exit `needs_owner`. 5 stable non-conformances, 8 flapping. **C1 CLOSED as `standard_moved`** (proposal 0046 rescoped C1/§1.1 and cites this audit as evidence; the reading stands as taken against v1.18.0, unrevised). **C33 WITHDRAWN** — the reading was taken against the wrong surface, see the gate rules above; the corpus was already right and nothing was filed. **C5 and C16 NARROWED** by running the gate (cap/budget presence and the 0028 A seat rule *are* enforced). **C32 CONFIRMED** — the one finding the gate genuinely cannot bear on. Record at `dot-plumbline/audits/2026-09-29-plumbline-conformance-census.{json,md}`; run-log.json created |
| **Jobs two–four, and the ratification** | ✅ 2026-10-01. **Job two** (self-score) = Plumbline's **first scored record** — 3/10 on its own attention cost, identical across three passes. **Job three** (discoverability gate) = the first Entry A job, the first to run architecture and development, and the first to deploy; exit `needs_owner` under `no_observation` — it *cannot* be scored yet, and that is correct. **Job four** (full score) = the first job with **all four dimensions observed**; verdict `regenerate` at iteration 1, `needs_owner` at iteration 2 (cap reached above the floor), then **dispositioned by the Owner** — verdict and disposition are separate acts. `dot-plumbline/constitution.json` **ratified v0.1.0** (S2, 2026-10-01): the frame is out of draft, four of the seven seats are held by the Owner and recorded as such, and a scored job became possible for the first time. Five runs in `dot-plumbline/run-log.json` |
| Enforcement plugin (5 hook gates) | ⚠️ Partly supplied by the `edi-loop` plugin's four checks; the **conformance-read runner** now exists (`tools/run_conformance_read.py`) and has run a real job; the conductor is still unbuilt |
| Profile roster + conductor | ⚠️ **Evaluator seat built** (`plumbline-eval`); Maker, Conductor, Deploy, Audit seats not started. The conductor is still unbuilt. |
| Release-gate building block | ⚠️ `kit/conductor_software.py` and `kit/conductor_run.py` detect one turn. `kit/conductor_loop.py` runs rounds on top of that turn: it dispatches, applies the pass rule, and writes a record for each round. It does not score, diagnose, or decide. **A finish is filed by the loop or not filed at all.** It writes `summary.json` with what the finish says, and `escalation.json` beside it for a stop a human must see (never for an accepted finish), then returns the summary; it files no custody/v1 record. The one finish it does not file is one whose stamps are not its own reading — a run whose clock was replaced took stamps it cannot file — and that finish raises `kit.conductor_loop.CustodyNotDone`, an `Exception`, never a `ValueError`, with `exit_code` 1 (the work was accepted), 2 (rejected, below the floor) or 3 (every stop a human must see), and files neither `summary.json` nor `escalation.json`; the halt carries what the record would have said, its separation gaps and its stamps. A packet refusal is not a finish and is unchanged: `ValueError`, `escalation.json` with `started_at` and `refused_at`, a later reading of the same clock, and no `ended_at`. Its spend is whole: the Maker's cost **and every Evaluator run's cost** are summed into the round and the job, so `budget.amount` binds on the Evaluator too (with `amount > 0`, an Evaluator that writes no cost record stops the job as `budget unmeasured`). Its clock binds **per command**: each Maker turn and each Evaluator run gets the smaller of `timeout_s` and the time left before the deadline. Its separation-gap sentence cites **Contracts §4.2**. Its round records carry wall-clock stamps: `started_at` is taken once at `loop()` entry, before the packet is loaded, and each written round record carries its own `started_at` and an `ended_at` taken when that record is written, inside the job window and in order across rounds. Nothing reads the stamps back, so the deadline and the clock stop stay on the monotonic clock. The escalations holder is not built. The conductor is still unbuilt. |
| Discoverability gate script | ✅ **Built, deployed, live, and working end to end — arm it per job, disarm after (2026-10-01).** `gate/` holds the plugin (rules as data, a thin adapter) and three suites: 11/11 acceptance, **20/20 doors, 7/7 host shape**. **It has fired in a live turn** — the hook blocked a real `clarify` — and **its tool has taken real escalations**: `~/.hermes/state/plumbline-gate/escalations.jsonl` holds the first rows this mechanism ever wrote. **Two production defects were found by LIVE USE, not by the suites, and both are fixed.** F1: the tool died on every call because the host passes the argument dict positionally while the handler declared `question=''` first (`b70c9a1`). F2: the two doors keyed the satisfaction window differently — a TOOL is dispatched with `session_id` and no `turn_id` (`model_tools.py:808`), a HOOK with `turn_id` + `session_id` — so an accepted escalation could never open the door and *escalate, then ask* did not work at all. Both now key on `session_id`: the identity the host gives both, and the unit `satisfaction_window_seconds` (900) already declares — **per session, not per turn**, which is the Owner's decision, and both the cost and the upstream path back are recorded in the doors case and in `dot-plumbline/jobs/2026-10-01-gate-dispatch-shape-fix/FINDINGS.md`. **Arm per job, disarm after** — while armed the hook governs every session on this machine. `gate_coverage` can now be computed for the first time: a blocked path is a ledger row (`path_blocked`, written before the refusal), which was the denominator it never had — though nothing reads it yet, so the metric is computable and not yet computed |
| Audit cron (incl. discoverable-escalation rate) | ❌ Not started |
| First real instantiation (program + repo) | ✅ **Plumbline itself.** Job one audited Plumbline's own repo, so the first instantiation is settled: Plumbline is a job in Plumbline, and its own `dot-plumbline/` is the live evidence channel |
| GitHub remote | ✅ `github.com/evaluatordriven/plumbline`, public: a fresh snapshot. The full history and the job, audit and probe records cited in this table stay in a private evidence archive; two jobs are in `examples/`. From 2026-11-05 a job that closes on this program is committed under `dot-plumbline/jobs/` and appended to `dot-plumbline/run-log.json`. Do not backfill. |

### What job one measured about the INSTRUMENT (read before trusting any reading)

- **The instrument's own spread is ~25%.** Across three passes of the *same* instrument on byte-identical
  input, 8 of 32 clauses read differently. Confirmed independently with the provider pinned, so the variance
  is the **seat's**, not routing. **A single pass is not a verdict** and no reading resting on one pass may
  be reported as a finding — report only what agreed on every pass, and label the rest as flapping.
- **Agreement is not correctness, and the quorum cannot supply it.** The rule above tells you which readings
  to report; it does **not** tell you they are true. The withdrawn C33 reading was stable across all three
  passes — the instrument agreed with itself and was wrong together, because the observed surface omitted the
  corpus gate. **A quorum measures consistency; a blind spot survives it intact.** Before trusting agreement,
  check that the surface contains the enforcement layer, and **run the gate on any schema-versus-clause
  finding** rather than reasoning about whether a gate could bear on it.
- **No configuration removed the variance.** A 7-arm bake-off (thinking cap, seed, strict `json_schema`,
  chunk shape, a different model family) left contradictions between 1 and 5 with a floor of 1 — and
  `structured` scored both the best and the worst arm, so the levers are **within noise of each other**. A
  different family cost 25–40× more for no gain. **The quorum is the mechanism, not the configuration.**
- **The readings record has no corpus schema.** §5's schema is titled "(scored)" and requires `score:number`;
  C29's readings form requires **never numbers**; C29 is LINE-enforced. A census is therefore written in a
  **labelled instance shape** (`plumbline-instance-readings-v1`, `pending_corpus_shape: true`) and is evidence
  for a corpus proposal — never a private second home for a law. `tests/validate_audit.py` understands this
  form and **recomputes** stable-vs-flapping from the raw pass files rather than trusting the summary.

## Known quirks

- **The PAT cannot create workflow files.** `.github/workflows/verify.yml` is held back by `.git/info/exclude`,
  because the fine-grained token lacks the `workflow` scope and GitHub rejects any push containing one. Add
  that permission and one commit lands it (the same applies to `e-di`; note e-di's Actions are off at account
  level, so the workflow would not run until that is enabled too).
- **G1 was withdrawn — it was not a doctrine gap (2026-09-29, S2's correction).** I had claimed C20 was
  unanswerable because the mandate's annexes live in `evidence/`, which `EDI-FOR-MACHINES.md` "bans". The ban
  reads *"do not load **as authority**"* — a weight ranking, not a prohibition — and the short mandate **names**
  the full text twice, including *"Auditing the corpus or dimensions/outcomes: open
  `evidence/EDI-MANDATE-full.md` (Annex A dimension set, Annex B outcome criteria O1–O4)"*. The load set points
  at the annexes and says when to open them. The residual is a wording nit, not a proposal, and no corpus change
  is owed.
- **`extend-never-shrink` is PLUMBLINE'S RULE, not the doctrine's — do not attribute it to E-DI.** The phrase
  appears nowhere in the corpus (not Contracts, Playbook, Mandate or Instrument). It was the Owner's framing
  (2026-09-29), recorded here as an instance rule in `schemas/instance-extensions.json`.
  **The doctrine's own version is §8, audited by C18, and it is narrower:** instance extensions must be
  labelled instance-specific, **must not weaken §3, §4 or §7**, and must be recorded with the job. Note what
  C18 does *not* say — its non-weakening clause is a closed set of three sections, so weakening something in
  §1, §2, §5, §6, §9 or §10 is not caught by it, and it is framed as a condition on *extending* rather than a
  principle about shrinking. Plumbline's rule is **broader, and therefore stricter**, than the doctrine's —
  which is permitted, since an instance may constrain itself more. **Do not read it back into the corpus, and
  do not cite it to the corpus as if the corpus said it.** Proposal 0046's *"instance code does not shrink C1"*
  is that proposal's argument, not a rule it cites.
  **What Plumbline's rule says:** it may **extend** — adding dimensions, channels, engines or labels, each
  labelled instance-specific and recorded with the job (§8/C18) — and it may never **shrink**: dropping or
  failing to apply a mechanism (M1–M8), an exclusion (X1–X4, or A.4's *may never be scored* classes), a
  must-ask, a terminal state, or an outcome. **Missing an exclusion because it was never read IS a shrink**, so
  the exclusions must be **reached**, not merely cited; adopting what is read at `DOCUMENT` hardness with its
  version recorded is the honest form and is not "loading it as authority". The mechanical form already exists:
  `tests/validate_schemas.py` asserts Plumbline accepts a strict **subset** of what the corpus accepts.
- **The gate's hook is process-global, and arming is not job-scoped.** While
  `plugins.plumbline-gate.active_job` is non-empty, its `pre_tool_call` hook blocks `clarify` in **every
  session on this machine**, Plumbline's or not — which the plugin's own docstring forbids ("a Plumbline instance
  rule must not govern work that is not Plumbline's"). Arming and disarming are **live** — the plugin re-reads
  `config.yaml` on every call, so no restart is needed to change scope — but the hook receives only tool name,
  args, `turn_id` and `session_id`, so it has no job context to test. Until it is scoped properly, the
  mechanism is discipline: arm per job, disarm after.
- **A plugin's code binds at gateway start, and PM2 is the handle.** A plugin file swap needs a restart —
  there is no hot reload. `hermes gateway restart` does nothing while a detached gateway holds the profile
  (`hermes gateway status` reports "Gateway service is not loaded"); the live gateway is the PM2 app
  `hermes-gateway`, so `pm2 restart hermes-gateway` is the command that lands a plugin change. Related, and
  paid for once: the host calls a plugin **tool** as `handler(args_dict, **kwargs)` — the whole argument dict
  **positionally** — so a handler must normalise that shape *and* named keywords, or it dies on every call
  while a unit suite that calls it with keywords stays green.
- **A plugin install can be silently shadowed by its own backup.** A sibling directory inside
  `~/.hermes/plugins/` that carries a `plugin.yaml` **is a plugin**: discovery loads it, and the registry lets
  a same-name, same-toolset duplicate **overwrite silently** (`hermes-agent/tools/registry.py:89`) — so a
  `.bak-…` copy can win the registration and you will debug the old code while every disk check says the new
  one is installed. Measured 2026-10-01: the fixed gate kept failing with its pre-fix `TypeError` after a
  verified install and restart. Back up to `~/.hermes/backups/`. **The operating loop guards this now** —
  `plugins:plumbline-gate-single-install` and `plugins:no-duplicate-declarations` fail the run instead of
  leaving it to be remembered, and both were **proven red** against a planted duplicate before being trusted:
  `PLUMBLINE_PLUGINS_ROOT` is the seam that makes that proof possible (point it at a throwaway plugin home and
  watch them fail). A guard nobody has seen fail is a guard nobody knows works.
- **Headless runs cannot prompt.** An approval gate inside a cron run hangs until timeout. Human gates must be
  queues (delivered to a Telegram topic), never blocking prompts.
