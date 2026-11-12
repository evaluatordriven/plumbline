# Changelog

Each release is a git tag, and each carries its own custody record in `record/`, or a note in `record/` saying
why it does not. Before 1.0.0 any release may turn a record that read `OK` into one that reads `FAILED`
(SPEC.md section 8); every such change is listed here under **Breaking**.

## 0.9.9 (candidate)

This release changes no requirement. It moves the release documents to 0.9.9 — `SPEC.md`'s header and
section 4's example, `README.md`'s status line, both example files — and records the Owner's cadence
amendment in `CONTRIBUTING.md`'s Releases section. `DRAFT-NOTE.md` inventories only the documents this
release touched.

**Changed**
- `CONTRIBUTING.md` records that a release that changes no requirement does not count toward the
  monthly cadence.
- The sentence about the release that shipped without a record now names that earlier release in words
  and points at the gap note in `record/`.

**Clarified** (the rules did not change)
- No requirement row and no section 4 required cell moved; the examples' digests are unchanged.

## 0.9.8 (candidate)

**Breaking** (what a producer must change)
- CL1-10: the referee in `checker/check.py` is now total—it no longer crashes or returns `NOT-CHECKABLE`
  for malformed input—and under structural precedence (`CR-2` owns field presence and type; `CL1-10` owns
  the semantics of well-formed disagreement data), malformed shapes in `checks` and `disagreements` are
  rejected as follows:
  - 9 semantic shapes fail `CL1-10` alone: an index in `disagreements[].checks` that is `true`, `false`,
    `1.5`, `"1"`, `-1`, `len(checks)`, `null`, or `[1]`, or a `disagreements[].checks` list of one
    element.
  - 20 structural shapes fail `CR-2` alone (which already owned field presence and type):
    `disagreements[].checks` missing, `null`, a string, a number, or an object;
    `disagreements[].dimension` missing, `null`, a number, or a list; a `disagreements[]` entry that is
    not an object; `disagreements` as `null`, an object, or a string; and a `checks[]` entry that is not
    an object, has `dimension` missing, `null`, or a list, or has `outcome` missing, a list, or an object.
  - No record's verdict changed: all 118 shared fixtures compared between the base commit and this commit
    show zero differences in `(verdict, levelAchieved, failing requirements)`.

**Clarified** (the rules did not change)
- CL2-3's conditional prose in SPEC.md §5.3 is replaced by a single fenced pseudocode block with
  unchanged meaning; the requirement row keeps its rationale sentence and points to the block.
- Human-readable level display in `tools/explain.py` and the README level table formats `CL1`, `CL2`,
  and `CL3` as `CLn · process`, and in `tools/explain.py` prints, directly after each level it
  prints, one line saying what the level does not certify: the quality of the work, and the
  substance or depth of the readings. The line claims nothing for the record; it rests on
  SPEC.md §1 ("answerable, not correct") and README.md ("a record certifies nothing").
  `explain.py` prints a level in two places, so the line appears twice in a full report.

**Changed**
- `tools/make_record.py` derives each control's `expected` and `outcome` from score rows rather than
  trusting control event fields, exits nonzero naming the control `id` if a score row is missing or
  disagrees with event values, names packages by role (`package-<role>.tar.gz`) while refusing if cited
  bytes change, and emits disposition package references under `x-on` (converting legacy `on`).
- `tests/red_counts.py` computes planted version strings dynamically from the repository's current
  version in `SPEC.md`.

## 0.9.7 (candidate)

**Breaking** (what a producer must change)
- CL1-9: a control's `case` is the digest of the case it ran on and may not be all zeros; a record whose
  controls cite all-zero digests now reads `FAILED`.

**Clarified** (the rules did not change)
- CL2-3 explains why at least one model evaluator's endpoint differs from the maker's: it keeps one
  operator from controlling both the work and its judge.

**Added**
- `tools/file_event.py` appends a `check` or `control` event to a custody log after checking that its
  data has the record's fields, valid values, a non-zero control case digest, and matching evidence
  files.
- `tools/release_record.py` verifies the custody log, checks that every check and control in a
  declarations file was filed after the last `artifact-produced` event, and builds the record.

**Stranger test** — cycle r2 did not pass: minimax unobserved (0 of 3 sessions counted); nemotron did not meet the gate (0 of 3 counted sessions meeting); seed met the gate (3 of 3 counted sessions meeting). CL1-10 is open; see `record/STRANGER-TEST-v0.9.7.md`.

## 0.9.6 (candidate)

**Changed**
- CL2-3 reads `undisclosed` model families the least favourable way rather than failing every undisclosed
  maker. An evaluator with `family: "undisclosed"` still counts as the maker's family. When the maker's
  `family` is `undisclosed`, (b) holds when model evaluators from at least two different disclosed
  families each differ from the maker in endpoint, and (c) counts, on each dimension, the largest
  disclosed evaluator family there plus every undisclosed evaluator there as the maker's family. This
  loosens CL2-3: no record that read `OK` under 0.9.5 reads `FAILED`.

**Clarified** (the rules did not change)
- CL1-17 says explicitly that it does not judge a check whose dimension's scale CL1-2 fails.

**Stranger test** — cycle 1 did not pass: minimax unobserved (1 of 3 sessions counted); nemotron did not meet the gate (0 of 2 counted sessions meeting); seed met the gate (3 of 3 counted sessions meeting). CL1-10 is open; see `record/STRANGER-TEST-v0.9.6.md`.

## 0.9.5 (candidate)

Theme: can a stranger implement the standard from its text alone? v0.9.4's stranger test did not pass,
and one session per implementer could not tell a hard sentence from a bad draw. This release measures
that properly (`record/` holds the result) and fixes what v0.9.4's evidence pointed at.

**Breaking** (what a producer must change)
- CL1-9: every evaluator with an observed check in a batch reads at least one clean control (expected
  `conforms`) **and** one planted control (expected `does_not_conform`) there. A reader that rejects
  everything can no longer pass on planted controls alone. *Give each reader both kinds.* (The batch-wide
  clean-control clause of v0.9.4 is folded into this.)

**Clarified** (the rules did not change)
- CL1-17: a check whose `score` is `null` is not judged by it.
- CL2-3 (c) is stated as arithmetic, with a worked example covering `undisclosed` on either side and a
  check's own `endpoint`.
- "One defect, one failure" gains a worked example: an `evidence` value with no `name` fails CR-2, and
  CL1-8 reads `NOT-CHECKABLE`.

**Clarified after the stranger test's cycle 1** (revision 1; no record changes outcome)
- BL-1 applies only to a `baseline` claim. Section 5 no longer says it applies to every record, and a
  verifier does not report it for a CL1, CL2 or CL3 claim; the reference checker no longer lists it there.
  In cycle 1, readers split three ways on a CL1 record over this sentence.
- CR-2 names the fields it does not check, and the requirement that checks each one, instead of a list of
  requirement IDs. Section 4's table says `readsBeforeFreeze` is required, and read, only in a `baseline`
  claim.

**Clarified after the stranger test's cycle 2** (revision 2; no record changes outcome)
- CL2-3's `undisclosed` sentence now says what it means in both directions: an evaluator whose family is
  undisclosed never differs from the maker, and if the maker's family is undisclosed, no evaluator
  differs from it. In cycle 2 the adjudicator found two careful readings of the old sentence; the
  revision states the rule as ratified and as the checker applies it.

**Known limitation, carried to the next release.** The rule above is stricter than it needs to be. When
the maker's family is undisclosed and the evaluators come from two different disclosed families, the
maker can share a family with at most one of them, so the other differs; CL2-3 still fails that record.
The error runs toward denying independence, never toward claiming it. Found by the Owner during this
release; changing the rule mid-test would have changed the frame the stranger test measures, so it waits
for the next bar.

**Added**
- `tools/verify_note.py` writes a published note of a record's checker result in the checker's own
  words, and `--check` refuses a note that was retyped.
- `count.py`: a kept record added to `record/` carries its release's version in its name, so no release
  overwrites an earlier one.

**Changed**
- The tools and tests no longer write Python cache files into the repository, and CI fails if any appear.

**Correction to 0.9.4.** The 0.9.4 entry below gives four wrong reasons for the v0.9.3 record failing
(CR-2, CL1-4, CL1-9, CL1-16): they were written by hand, not copied. The verdict and requirement IDs
were right. The v0.9.4 checker's own words, on tag `v0.9.3` without the private evidence:
- **CR-2** — `FAILED`: predicate.startedAt missing or not ts; evaluators[1].model.family missing or not family; evaluators[1].model.endpoint missing or not host; evaluators[2].model.family missing or not family; evaluators[2].model.endpoint missing or not host
- **CL1-4** — `FAILED`: predicate.maker.kind missing or not str; predicate.maker.model.family missing or not family; predicate.maker.model.endpoint missing or not host
- **CL1-9** — `FAILED`: evaluator R1 reads in batch v093-batch but reads no control there
- **CL1-16** — `FAILED`: evaluator glm-5.3 is listed but appears on no check and no control; evaluator gpt-6.1-sol is listed but appears on no check and no control; evaluator grok-4.7 is listed but appears on no check and no control; evaluator qwen-3.8 is listed but appears on no check and no control

The correction appended to `record/VERIFY.md` on 2026-10-22 summarised these lines rather than copying
them; the lines above are exact.

**Stranger test** (three cycles; `record/STRANGER-TEST-v0.9.5.md` holds the tables)
- Cycle 1 — **unobserved**. Seed 2.1 Turbo s1 counted A=9 B=12; Seed 2.1 Turbo s2 counted A=11 B=11; Seed 2.1 Turbo s3 not counted A=8 B=11; MiniMax M3 s1 not counted A=4 B=2; MiniMax M3 s2 not counted A=5 B=2; MiniMax M3 s3 not counted A=4 B=0; Nemotron 3 Ultra s1 counted A=10 B=9; Nemotron 3 Ultra s2 not counted A=8 B=11; Nemotron 3 Ultra s3 not counted A=6 B=11.
- Cycle 2 — **does not pass**. Seed 2.1 Turbo s1 counted A=10 B=8; Seed 2.1 Turbo s2 counted A=11 B=11; Seed 2.1 Turbo s3 not counted A=4 B=0; MiniMax M3 s1 counted A=11 B=9; MiniMax M3 s2 not counted A=4 B=10; MiniMax M3 s3 not counted A=5 B=9; Nemotron 3 Ultra s1 not counted A=4 B=0; Nemotron 3 Ultra s2 counted A=8 B=9; Nemotron 3 Ultra s3 counted A=10 B=9.
- Cycle 3 — **passes**. Seed 2.1 Turbo s1 counted A=12 B=11; Seed 2.1 Turbo s2 counted A=12 B=11; Seed 2.1 Turbo s3 not counted A=4 B=0; MiniMax M3 s1 not counted A=4 B=0; MiniMax M3 s2 counted A=12 B=12; MiniMax M3 s3 counted A=11 B=10; Nemotron 3 Ultra s1 not counted A=4 B=9; Nemotron 3 Ultra s2 not counted A=6 B=9; Nemotron 3 Ultra s3 not counted A=4 B=0.
- A first attempt at cycle 3 is void and is not a cycle: its planted control was built with a wrong evidence digest, so the control never validated, and its sessions ran when the runbook said stop. No result is taken from it; cycle 3 above ran on twelve fresh records. The custody record discloses it.

## 0.9.4 (candidate)

Theme: make the record mean what it says. Four independent reviewers read the v0.9.3 release record
against its checker and found that it passed while filing every model reading under a script, binding
check evidence to nothing, and holding no clean control. Each fix below closes one of those holes.

**The v0.9.3 record under this release's rules.** The record has not changed; the requirements have. It
still conforms to v0.9.3, the version it names. Run under this release's checker with its private
evidence, it reads **FAILED**, achieving **no conformance level**, routing **acknowledged**. Each
requirement that does not read `OK`:

- **CR-2** — `FAILED`: `maker.kind` is absent.
- **CL1-1** — `NOT-CHECKABLE`: the record carries no `startedAt`, so the bar cannot be placed before the work began.
- **CL1-4** — `FAILED`: the maker names no `kind` and no version.
- **CL1-8** — `NOT-CHECKABLE`: its checks name evidence as bare digests, not evidence files.
- **CL1-9** — `FAILED`: a batch holds no clean control.
- **CL1-16** — `FAILED`: readings are filed under a script evaluator that is also the instrument's runner.

**Breaking** (what a producer must change)
- `startedAt` is required. CL1-1: the bar is frozen before the work **started**, not just before it was
  finished, and `startedAt` is no later than `producedAt`. BL-1: a baseline's bar is frozen after
  `startedAt`. *Add the time work began; `tools/make_record.py --log` takes it from the first
  `work-started` event.*
- `maker.kind` is required: `person`, `model` or `script` (CL1-4). *Add it.*
- CL1-8: a check's `evidence` is an evidence file, `{name, sha256}`, and the file supplied with
  `--evidence` must match; without it, CL1-8 reads `NOT-CHECKABLE`. *Change each check's evidence from a
  digest to a named file, and keep the file.*
- CL1-9: every evaluator with an observed check in a batch reads a control in that batch, and every batch
  holds at least one clean control (expected `conforms`). *Give each reader its own control, and add a
  clean one.*
- CL1-16 (new): every listed evaluator appears on a check or a control; every control names a listed
  evaluator; no script evaluator's script is the instrument's runner. *File each reading under the
  evaluator who gave it.*
- CL1-17 (new): a scored check conforms exactly when its score reaches the threshold, and its score lies
  between the floor and the highest anchor. CL1-2: anchors are keyed by score, none below the floor, and
  the threshold lies inside the scale. *Make outcomes follow scores; keep any mean or minimum as your own
  rule for what happens next.*
- Model identity (CR-2): `family` is lowercase letters and hyphens with no version, or `undisclosed`;
  `endpoint` is a host name with at least one dot. A check may carry its own `endpoint`. CL1-6: a model
  evaluator carries a `model` block. CL2-3: an undisclosed family counts as the maker's; a check's own
  endpoint counts as its evaluator's. *Write `gpt`, not `GPT` or `gpt-6`; write the answering host, not
  the router.*
- CL1-11 and CL2-3: a maker who wrote the bar is named in `separationGaps` at CL1, and is not allowed at
  CL2. CL2-3 also needs `maker.model` when `maker.kind` is `model`.
- CL3-3: the signature is a Sigstore bundle (a DSSE envelope logged in Rekor). A verifier reads `OK`
  only if it verifies the bundle itself; the reference checker does not, so it reads `NOT-CHECKABLE`, and
  no record reaches CL3 with it.
- `run` must be 1 or more, in the checker as in the schema.

**Added**
- Extensions: producers may add fields under keys beginning `x-`; verifiers ignore them (SPEC.md
  section 4), with a note on re-filing older records.
- SPEC.md section 7 names four limits: the custody log has no outside anchor; a control cannot show the
  case was hard; "held out" means held out from this record's maker; signing publishes the signer.
- The plain view states who made the work and whether the bar was fixed before the work started. The
  glossary gives both senses of "signature".

**Clarified** (revision 1, after the stranger test's first run; the rules did not change)
- CL2-3 is split into parts (a), (b) and (c), and says where `undisclosed` applies.
- "One defect, one failure" (SPEC.md section 5): a missing or malformed field fails the requirement that
  checks it; another requirement that cannot be decided without it reads `NOT-CHECKABLE`. The reference
  checker already worked this way; an evidence name that is not a relative path now fails CR-2 alone,
  as this rule says.
- Section 6 says which requirements are in scope for each claim.

**Stranger test** — run 1, read against revision 0's text
- Seed 2.1 Turbo: A 11 of 12, B 10 of 12; both controls correct; counted; met both thresholds.
- MiniMax M3: A 9 of 12, B 9 of 12; both controls correct; counted; short of both thresholds.
- Nemotron 3 Ultra, an extra reading (its seat was taken on an orchestration error): A 8 of 12, B 7 of 12.
- Adjudicator's note, rec-10: the reference checker's reading upheld — CR-2 fails and CL1-8 reads
  `NOT-CHECKABLE`. The same adjudicator later read CL1-8 as failing on the same record; both cannot stand,
  and this entry records that it ruled both ways.
- Adjudicator's note, rec-11: CL2-3 — "no more than half" is inclusive of exactly half, so the record
  conforms; the implementers' readings were wrong.
- Run 1's result: the stranger test did not pass.

**Stranger test — the re-run** (decision 1, against this release's text, one run only)
- Seed 2.1 Turbo: **not counted** — it failed **both** controls: the clean one flipped to FAILED, and the
  planted one gained a failing ID. Its verifier reads CL1-17 as failed on every record. A 5 of 12, B 1 of 12.
- MiniMax M3: counted; A 10 of 12, B 9 of 12; short of both thresholds.
- The re-run does not pass: one implementer short and one not counted. The stranger test fails, and this
  release ships as a candidate saying so.
- **The stranger test did not pass; see `record/STRANGER-TEST.md`.**

**Changed**
- `count.py` no longer caps the checker at 300 lines (the cap pushed the code into one-liners), and now
  fails if CI and README.md run different quickstart commands. CI runs those commands exactly, and checks
  that the committed example record is the one they build.
- The reading-level check runs in CI as advisory, not as a gate.
- `count.py` skips `record/`: kept records, such as a release's bar, are quoted word for word and may
  use words the specification reserves (revision 2).
- `count.py` treats earlier releases' records in `record/` as history.

## 0.9.3 (candidate)

**Added**
- A plain-language guide for reviewers (`docs/REVIEWERS-GUIDE.md`) and a glossary of every word the
  specification uses (`docs/GLOSSARY.md`), with a reading check in CI (`tools/readability.py`).
- `tools/explain.py`, which prints any record in plain words with the checker's answer.
- Routing `acknowledged`: some checks were unobserved and a given disposition names them all.
- A control may name the `dimension` it tests.
- `CHANGELOG.md`, `SECURITY.md` and `GOVERNANCE.md`.

**Breaking**
- CL1-6: `sameModelAsMaker` must be declared exactly when the evaluator's model is the maker's.
- CL1-9: a control whose outcome differs from its expected outcome voids its reader's observations in
  that batch (or in that dimension, if the control names one); those checks must read `unobserved`.
- CL1-11: if the maker approved the bar as buyer or specialist, a separation gap names the maker.
- CL1-14: the bar file is checked against `bar.digest`; without it, CL1-14 reads `NOT-CHECKABLE`.
- CL2-3: no buyer or specialist approval is by the maker; and for each dimension, evaluators from the
  maker's model family are no more than half of its readers.

**Fixed**
- The checker no longer applies CL1-15 to a baseline claim (SPEC.md: CL1-2 to CL1-14).
- `count.py` checks the license files themselves, not only the documents that name them.

## 0.9.2

**Added** an append-only, hash-chained custody log (`tools/record.py`) and building a record from it;
same-model sessions declared at CL1; "published" defined; the screening test's record.

**Breaking**
- CL1-6: a model evaluator that is a session of the maker's own model must declare `sameModelAsMaker`.

**Changed**
- CL2-3 now asks for at least one model evaluator differing from a model maker in both family and
  endpoint; others may share them. This loosened the rule, so no record that read `OK` became `FAILED`.

## 0.9.1

First published release.

