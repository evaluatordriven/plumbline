# Evaluator Driven — the custody record

**Version 0.9.9 · candidate · 2026-11-12** · Predicate type `https://evaluatordriven.com/custody/v1`
Author: Steve Moitozo II · Text: CC BY 4.0 · Code: Apache-2.0 · Patents: see `PATENTS.md`

Sections marked *(normative)* define conformance. Everything else explains it.

## Why this name *(non-normative)*

If you want acceptable output from work with AI, you have to be able to show that the output meets a
standard an independent evaluator can check, and that standard has to be informed by two people: the
person who wants the output, and a specialist who knows the craft.

Evaluator-driven because the evaluator, and the standard it applies, come first. Build them first and the
work can be aimed at the standard. Build them afterward and you have a description, not a standard.

---

## 0. Status

Early. One reference checker exists, in this repository. The evidence base is narrow and its limits are
listed in `README.md`. Comments and failing records are welcome under `CONTRIBUTING.md`.

---

## 1. Scope *(normative)*

This specification defines the **custody record**: a record kept with a piece of work that shows what the
work was measured against, who measured it, what they found, and who decided.

It standardizes the record, not the process that produced the work. How work is made, revised or
iterated is out of scope.

A conforming record makes work **answerable, not correct**. No requirement here claims, or may be read
as claiming, that conforming work is good.

A signature or content credential on the artifact describes where the artifact came from. It is never an
outcome for a dimension.

---

## 2. Terms *(normative)*

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT",
"RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14
(RFC 2119, RFC 8174) when, and only when, they appear in all capitals.

| Term | Meaning |
|---|---|
| **artifact** | The work being evaluated, identified by the digests in the record's `subject`. |
| **bar** | The written statement of what good means for the artifact: its dimensions and, for each, what conforming looks like. Frozen before the work starts. |
| **dimension** | One part of the bar, judged on its own. |
| **maker** | The party that produced the artifact. |
| **evaluator** | A person, a model session, or a script that reads the artifact against the bar. An evaluator did not make the artifact and did not author the bar. Each session of a model is a separate party, so a session of the maker's own model can evaluate at CL1 if the record declares it (CL1-6); at CL2 it may sit alongside other evaluators, provided at least one model evaluator differs from the maker in both family and endpoint (CL2-3). |
| **buyer** | The party the work is for. The buyer's test is whether the work does the job it was meant to do. |
| **specialist** | The party that knows the field well enough to say what good means. |
| **check** | One evaluator's reading of one dimension in one run. Its outcome is `conforms`, `does_not_conform`, or `unobserved`. |
| **instrument** | The written rubric an evaluator reads by, and the runner that applies it. |
| **record** | The custody record defined here: an in-toto Statement whose predicate is `custody/v1`. |
| **published** | Made available at a stable address to the people who rely on the record. Published need not mean public. |
| **disposition** | The decision about the artifact — `given`, `not_yet_given`, or `declined` — made by a named person, the approver. |

**Plain-language equivalents** used on evaluatordriven.com:

| This specification | evaluatordriven.com |
|---|---|
| specialist | subject matter expert |
| `unobserved` | not observed |
| `given` / `not_yet_given` / `declined` | accepted / not yet accepted / declined |

---

## 3. The four moves

The record carries evidence of four moves. Section 5 states what each requires.

| Move | What the record shows | Requirements |
|---|---|---|
| Set the bar | The bar existed, unchanged, before the work started; its buyer and specialist approved that exact bar | CL1-1 to CL1-3 |
| Produce | Who made the work, by what method, against which bar, with which instrument | CL1-4, CL1-5 |
| Evaluate independently | Who read it, against what, with what outcome, beside a control | CL1-6 to CL1-10, CL1-15 to CL1-17 |
| Keep the record | What failed, what separation was missing, where the record lives, who decided | CL1-11 to CL1-14 |

---

## 4. The record *(normative)*

A record MUST be an in-toto Statement v1 whose `predicateType` is
`https://evaluatordriven.com/custody/v1` and whose `predicate` has the fields below. A field listed as
required MUST be present; a required list MAY be empty only where this table says so. Absence never
means a default.

| Field | Type | Required | Notes |
|---|---|---|---|
| `specVersion` | string | yes | This document's version, e.g. `0.9.9` |
| `levelClaimed` | `CL1` · `CL2` · `CL3` · `baseline` | yes | |
| `bar.digest` | digest | yes | sha256 of the frozen bar document |
| `bar.frozenAt` | timestamp | yes | RFC 3339, UTC |
| `bar.author` | string | yes | |
| `bar.dimensions[]` | list, non-empty | yes | `id`, `criterion`; `scale` when scored |
| `bar.dimensions[].scale` | object or `null` | yes | `anchors`, `threshold`, `floor` |
| `bar.approvals[]` | list | yes | `role` (`buyer`·`specialist`), `by`, `barDigest`, `at`, `adopted` |
| `bar.publishedAt` | URI or `null` | yes | |
| `bar.groundTruth[]` | list, may be empty | yes | `name`, `version`, `digest` — each reference the bar judges against |
| `bar.dissent[]` | list, may be empty | yes | `by`, `note` — where the buyer and specialist disagree about the bar, recorded, never averaged |
| `maker` | object | yes | `name`, `kind` (`person`·`model`·`script`), `version`, `method` (digest), `model` (or `null`) |
| `startedAt` | timestamp | yes | When work on the artifact began |
| `producedAt` | timestamp | yes | When the artifact was finished |
| `readsBeforeFreeze[]` | list, may be empty | only in a `baseline` claim; BL-1 checks it | Not required, and not read, in any other record |
| `instrument` | object | yes | `rubric` (digest), `runner` (digest) |
| `evaluators[]` | list, non-empty | yes | `id`, `name`, `kind` (`person`·`model`·`script`), `model` (or `null`); `script` (`name`, `author`, `digest`) when `kind` is `script`; optional `sameModelAsMaker` (boolean) |
| `checks[]` | list, non-empty | yes | `dimension`, `evaluator`, `run` (1 or more), `batch`, `at`, `outcome`, `score`, `failureCondition`, `evidence` (an evidence file, or `null`), `unobserved`; optional `endpoint` |
| `controls[]` | list, non-empty | yes | `id`, `batch`, `evaluator`, `case` (digest), `expected`, `outcome` |
| `spread[]` | list | in a CL2 or CL3 claim | `dimension`, `evaluator`, `runs`, `agreement` |
| `disagreements[]` | list, may be empty | yes | `dimension`, `checks` (indexes into `checks[]`), `note` |
| `violations[]` | list, may be empty | yes | `dimension`, `description` |
| `separationGaps[]` | list, may be empty | yes | strings |
| `retention` | object | yes | `location`, `public` (boolean) |
| `demonstrations[]` | list | in a CL3 claim | `dimension`, `evaluator`, `planted` (digest), `outcome`, `at` |
| `external[]` | list, may be empty | yes | `requirement` (`CL1-15`, or its 0.x name `CL2-4`; `CL3-3`), `subject` (the evaluator's `id` for CL1-15; `record` for CL3-3), `evidence` (an evidence file), `readBy` |
| `disposition` | object | yes | `state`, `by`, `at`, `acknowledgesUnobserved[]` |

Every check in a record is read against `bar.digest`; a reading against any other bar belongs in another
record. A filed check is not edited: a correction is a new check with a later `at`, and both stay in
`checks`. A record is plain JSON, readable without any tool.

A **digest** is an object `{"sha256": "<64 lowercase hex>"}`. An **evidence file** is an object
`{"name": "<relative path>", "sha256": "<64 lowercase hex>"}`, naming a file in the evidence a verifier is
given. `model`, wherever it appears, is `null` or an object with `family`, `identifier`, `endpoint`, and
`readOnly` (boolean). `family` is the model line as its builder names it, in lowercase letters and
hyphens only, with no version (for example `gpt` or `qwen`), or `undisclosed` when the builder does not
say. `identifier` is the exact model version. `endpoint` is the host name of the service that answered,
in lowercase with at least one dot (for example `api.example.com`); a router that passed the request on
is not the service that answered. A check MAY carry its own `endpoint` when the host that answered it
differs from its evaluator's. A `control` may also carry a `dimension`, naming the one dimension it tests.

A **scale** (`bar.dimensions[].scale`) has `anchors`, an object that keys a description by score (for
example `{"1": "no figure cites a source", "5": "every figure cites its source"}`); a `floor`, the lowest
score on the scale; and a `threshold`, the score a check needs to conform.

**Extensions.** A producer MAY add its own fields anywhere in the predicate under keys that begin with
`x-`. No requirement reads them, and a verifier ignores them. *(Non-normative: a record re-filed from an
earlier instrument keeps its original times and can carry the earlier verdict under an `x-` key; it
conforms only on its own fields.)*

`schema/custody-v1.schema.json` encodes this table for JSON Schema 2020-12 validators. Where the schema
and this section differ, this section governs.

---

## 5. Requirements *(normative)*

A record MUST meet CR-1, CR-2, and every requirement of the level it claims and of every level below it.
A record that claims `baseline` MUST meet CR-1, CR-2, BL-1, CL1-2 to CL1-14, CL1-16 and CL1-17. BL-1
applies only to a record that claims `baseline`: a record that claims CL1, CL2 or CL3 is not held to it,
and a verifier does not report it for that record.

Each requirement has a stable ID and a **check class**:

- **structural** — decidable from the record's shape alone;
- **semantic** — decidable from the record's content, and from supplied files where noted;
- **external** — needs evidence outside the record, read by a named party.

**When evidence is missing:** a structural or semantic requirement that the record breaks reads
`FAILED`. A semantic requirement that needs files no one supplied reads `NOT-CHECKABLE`. An external
requirement reads `OK` only when its evidence file is supplied, its digest matches, and `readBy` names a
party who is not the maker (and, for CL3-3, the verifier has verified the bundle itself); a mismatched digest reads `FAILED`; evidence read only by the maker is
self-report and reads `NOT-CHECKABLE`; a named file that was not supplied reads `NOT-CHECKABLE`. When the record names **no** evidence at all, the two
external requirements differ: independence (CL1-15) is a claim about the world, so an unevidenced claim
reads `NOT-CHECKABLE`; a signature (CL3-3) is a property of the record, so its absence reads `FAILED`. A
field that only asserts independence never satisfies a requirement on its own.

**One defect, one failure.** When a field is missing or malformed, the requirement that checks that
field reads `FAILED`: CR-2, or the requirement this section names as checking the field itself. Any
other requirement that cannot be decided without that field reads `NOT-CHECKABLE`. *(Non-normative
example: a check whose `evidence` is `{"sha256": "…"}`, with no `name`, does not cite an evidence file.
CR-2 reads `FAILED`; CL1-8, which cannot look for a file that is not named, reads `NOT-CHECKABLE`.)*

### 5.1 Every record

| ID | Requirement | Class |
|---|---|---|
| CR-1 | The record is an in-toto Statement v1: `_type` is `https://in-toto.io/Statement/v1`; `subject` is non-empty and every entry has a `name` and a sha256 digest; `predicateType` is exactly `https://evaluatordriven.com/custody/v1`. | structural |
| CR-2 | Every field section 4 marks `yes` is present with its stated type and form (a `family`, an `endpoint`, a `run`), and so are `spread` in a CL2 or CL3 claim and `demonstrations` in a CL3 claim. CR-2 does not check the following fields, because the requirement named beside each checks it itself: each dimension's `id`, `criterion` and `scale` (CL1-2); `maker` (CL1-4); `instrument`, and each script evaluator's `script` (CL1-5); `violations` and `separationGaps` (CL1-11); `retention` (CL1-12); `readsBeforeFreeze` (BL-1, and only in a `baseline` claim). | structural |

### 5.2 CL1 — the four moves

| ID | Requirement | Class |
|---|---|---|
| CL1-1 | `bar.frozenAt` is earlier than `startedAt`, and `startedAt` is no later than `producedAt`. A record whose bar was frozen after the work started can claim only `baseline` (BL-1). A bar frozen at the same instant the work started fits neither: it is not earlier, and it is not after. | semantic |
| CL1-2 | The bar names its author and at least one dimension. Every dimension has a unique `id` and a `criterion`. A dimension whose checks carry scores declares a `scale` with `anchors`, a `threshold`, and a `floor`. A scale's anchors are keyed by score, there is at least one, none is below the `floor`, and the `threshold` lies between the `floor` and the highest anchor. | structural |
| CL1-3 | `bar.approvals` holds one `buyer` and one `specialist` approval, each naming who approved, when, and a `barDigest` equal to `bar.digest`. A specialist that is a published document is recorded with `adopted` naming the document and its version (a shape CR-2 checks), and `by` naming the person who adopted it. | semantic |
| CL1-4 | The maker is named with its `kind` and a version, and `maker.method` is the digest of the written rules used to make the artifact. | structural |
| CL1-5 | The instrument is pinned: `instrument.rubric` and `instrument.runner` are digests, and every evaluator of kind `script` names its script, its script's author, and its digest. | structural |
| CL1-6 | No evaluator is the maker or the bar's author, and no script evaluator's script was written by either. The approver is not an evaluator. A model evaluator carries a `model` block. A model evaluator whose `identifier` equals the maker's declares `sameModelAsMaker: true`, and one whose `identifier` differs does not. For a person, this shows separately named parties, not proven independence; a record holder who needs more attaches evidence. | semantic |
| CL1-7 | Every dimension on the bar has at least one check. A dimension with no check fails the record: its evidence is not attributable. | semantic |
| CL1-8 | Every check names a dimension on the bar and a listed evaluator, gives a run, batch, and time, and declares its `failureCondition` — what would have made it return `does_not_conform`. A `conforms` or `does_not_conform` outcome cites an evidence file, and the file supplied to the verifier matches its digest: a mismatch reads `FAILED`, and a file not supplied reads `NOT-CHECKABLE`. An `unobserved` outcome names the channel tried and why it could not observe, and carries no score. | semantic |
| CL1-9 | In every batch, each evaluator with a check that is not `unobserved` reads at least two controls there: one whose expected outcome is `conforms`, and one whose expected outcome is `does_not_conform`. Every control records its expected and actual outcome, and its `case` is the digest of the case it ran on, never all zeros. A control is a case whose correct outcome is known in advance. A control whose actual outcome differs from its expected outcome shows its reader could not be relied on: every check by that evaluator in that batch reads `unobserved`, or, if the control names a `dimension`, every such check of that dimension. | semantic |
| CL1-10 | Where checks of one dimension return different outcomes, `disagreements` names that dimension and the checks. Outcomes are never averaged into one. | semantic |
| CL1-11 | Every dimension with a `does_not_conform` check appears in `violations`. `violations` and `separationGaps` are present even when empty. If the maker wrote the bar (`bar.author`), or approved it as buyer or specialist, an entry in `separationGaps` names the maker. | semantic |
| CL1-12 | `retention` states where the full record is kept and whether it is public. A record need not be public; it is kept, and it can be produced on request. | structural |
| CL1-13 | The disposition is `given`, `not_yet_given`, or `declined`, with the approver's name and time. If any check is `unobserved`, the record's overall result is not "all conform", and a `given` disposition lists each unobserved dimension in `acknowledgesUnobserved`. | semantic |
| CL1-14 | Each `subject` digest matches the supplied artifact file of that name, and `bar.digest` matches the supplied bar file. Without those files this reads `NOT-CHECKABLE`. | semantic |
| CL1-15 | For every model evaluator, `external` holds evidence of its configuration — for example a harness log showing which model and endpoint answered — read by a named party who is not the maker. A model's own settings block (`model`) is a claim, not evidence. | external |
| CL1-16 | Every check and every control names a listed evaluator, and every listed evaluator appears on at least one check or control. A reading is filed under the evaluator that gave it, never under a script that collected or scored it: no script evaluator's script is the instrument's runner (`instrument.runner`), and an evaluator listed with neither a check nor a control fails the record. | semantic |
| CL1-17 | A scored check `conforms` exactly when its score is at least its dimension's `threshold`, and reads `does_not_conform` otherwise; its score is no lower than the `floor` and no higher than the highest anchor. A producer's own rule, such as a mean, a minimum, or another run, may decide what happens next; it never decides a check's outcome. A check whose `score` is `null` is not judged by CL1-17. CL1-17 does not judge a check whose dimension's scale CL1-2 fails. | semantic |

### 5.3 CL2 — independent

| ID | Requirement | Class |
|---|---|---|
| CL2-1 | Every evaluator reads every dimension it checks in at least two runs, and `spread` gives, for each such pair, the number of runs and how many agreed. | semantic |
| CL2-2 | Every model evaluator records `family`, `identifier`, `endpoint`, and `readOnly: true`. | structural |
| CL2-3 | The `CL2_3` block below returns `OK`. Requiring an evaluator whose endpoint differs from the maker's keeps one operator from controlling both the work and its judge. | semantic |

```python
01: def CL2_3(predicate):
02:   for a in predicate.bar.approvals:                                                 # <- (a) "No buyer or specialist approval is by the maker"
03:     if a.role in {"buyer", "specialist"} and a.by.strip().casefold() == predicate.maker.name.strip().casefold():  # <- (a) "No buyer or specialist approval is by the maker"
04:       return FAILED                                                                 # <- (a) "No buyer or specialist approval is by the maker"
05:   if predicate.bar.author.strip().casefold() == predicate.maker.name.strip().casefold():  # <- (a) "and the maker did not write the bar"
06:     return FAILED                                                                   # <- (a) "and the maker did not write the bar"
07:   if predicate.maker.kind != "model":                                               # <- (b),(c) "If the maker's kind is model"
08:     return OK                                                                       # <- (b),(c) "If the maker's kind is model"
09:   if predicate.maker.model is null:                                                 # <- (b) "`maker.model` is present"
10:     return FAILED                                                                   # <- (b) "`maker.model` is present"
11:   m_fam = predicate.maker.model.family.casefold()                                   # <- (b) "the maker's" `family`
12:   m_ep = predicate.maker.model.endpoint                                             # <- (b) "the maker's" `endpoint`
13:   model_evs = [e for e in predicate.evaluators if e.kind == "model" and e.model is not null]  # <- (b) "model evaluators"
14:   def endpoints(e):                                                                 # <- (b) "its endpoints (its model's `endpoint`, and any `endpoint` its checks name)"
15:     return {e.model.endpoint} | {                                                   # <- (b) "its model's `endpoint`"
16:       c.endpoint for c in predicate.checks                                          # <- (b) "and any `endpoint` its checks name"
17:       if c.evaluator == e.id and c.endpoint is present                              # <- (b) "any `endpoint` its checks name"
18:     }
19:   if model_evs is not empty:                                                        # <- (b) "if the record has model evaluators"
20:     diff_ep = [                                                                     # <- (b) evaluators with "none of its endpoints ... equals the maker's" and disclosed family
21:       e for e in model_evs                                                          # <- (b) "model evaluators"
22:       if e.model.family.casefold() != "undisclosed"                                 # <- "an evaluator whose `family` is `undisclosed` ... never differs from the maker"
23:       and m_ep not in endpoints(e)                                                  # <- (b) "none of its endpoints ... equals the maker's"
24:     ]
25:     if m_fam == "undisclosed":                                                      # <- "if the maker's `family` is `undisclosed`"
26:       if len({e.model.family.casefold() for e in diff_ep}) < 2:                     # <- "(b) holds only when model evaluators from at least two different disclosed families each have no endpoint equal to the maker's"
27:         return FAILED                                                               # <- "(b) holds only when model evaluators from at least two different disclosed families each have no endpoint equal to the maker's"
28:     else:                                                                           # <- (b) disclosed maker `family`
29:       if not any(e.model.family.casefold() != m_fam for e in diff_ep):              # <- (b) "at least one of them has a `family` different from the maker's, and none of its endpoints ... equals the maker's"
30:         return FAILED                                                               # <- (b) "at least one of them has a `family` different from the maker's, and none of its endpoints ... equals the maker's"
31:   evs_by_id = {e.id: e.model.family.casefold() for e in model_evs}                  # <- (c) model evaluator `family` by `id`
32:   for d in predicate.bar.dimensions:                                                # <- (c) "for each dimension"
33:     r_ids = {c.evaluator for c in predicate.checks if c.dimension == d.id}          # <- (c) "all the evaluators with a check of that dimension; persons and scripts count toward that total"
34:     r_fams = [evs_by_id[id] for id in r_ids if id in evs_by_id]                     # <- (c) model `family` of each model evaluator on that dimension
35:     undisc = [f for f in r_fams if f == "undisclosed"]                              # <- "every evaluator on that dimension whose `family` is `undisclosed`"
36:     if m_fam == "undisclosed":                                                      # <- "if the maker's `family` is `undisclosed` ... in (c), for each dimension"
37:       disc_fams = [f for f in r_fams if f != "undisclosed"]                         # <- "whichever single disclosed family has the most evaluators on that dimension"
38:       largest = max((count(f in disc_fams) for f in set(disc_fams)), default=0)     # <- "whichever single disclosed family has the most evaluators on that dimension"
39:       same = largest + len(undisc)                                                  # <- "those of whichever single disclosed family has the most evaluators on that dimension, together with every evaluator on that dimension whose `family` is `undisclosed`"
40:     else:                                                                           # <- (c) disclosed maker `family`
41:       same = count(f for f in r_fams if f == m_fam) + len(undisc)                   # <- (c) "evaluators of the maker's `family`" + "an evaluator whose `family` is `undisclosed` always counts as the maker's `family`"
42:     if 2 * same > len(r_ids):                                                       # <- (c) "twice the number of evaluators of the maker's `family` is no more than the number of all the evaluators with a check of that dimension"
43:       return FAILED                                                                 # <- (c) "twice the number of evaluators of the maker's `family` is no more than the number of all the evaluators with a check of that dimension"
44:   return OK
```

*Provenance of the `CL2_3` block against the base CL2-3 paragraph (non-normative):*

| Clause in base CL2-3 paragraph | Lines in `CL2_3` |
|---|---|
| `(a) No buyer or specialist approval is by the maker` | 02–04 |
| `and the maker did not write the bar.` | 05–06 |
| `(b) If the maker's kind is model,` | 07–08 |
| `maker.model is present;` | 09–10 |
| `and if the record has model evaluators,` | 13, 19 |
| `at least one of them has a family different from the maker's, and none of its endpoints (its model's endpoint, and any endpoint its checks name) equals the maker's.` | 11–12, 14–18, 20–24, 28–30 |
| `Requiring an evaluator whose endpoint differs from the maker's keeps one operator from controlling both the work and its judge.` | No line in `CL2_3`: this sentence is non-operational rationale and is kept in the CL2-3 table cell above. |
| `Others may share the maker's family or endpoint.` | No separate line in `CL2_3`: carried by the existential quantifier `any(...)` on line 29 (and `len(...) < 2` on line 26), which inspects whether the required evaluator(s) exist without restricting any other evaluators in `model_evs`. |
| `(c) If the maker's kind is model, then for each dimension, twice the number of evaluators of the maker's family is no more than the number of all the evaluators with a check of that dimension; persons and scripts count toward that total.` | 07–08, 31–34, 40–43 |
| `In (b) and (c), undisclosed is read the least favourable way: an evaluator whose family is undisclosed always counts as the maker's family and never differs from the maker;` | 22 (in `diff_ep`, excluding `undisclosed` from differing in (b)), 35, 41 (counting `undisclosed` as the maker's `family` in (c)) |
| `if the maker's family is undisclosed, it could be any one disclosed family, so (b) holds only when model evaluators from at least two different disclosed families each have no endpoint equal to the maker's,` | 25–27 |
| `and in (c), for each dimension, the evaluators of the maker's family are those of whichever single disclosed family has the most evaluators on that dimension, together with every evaluator on that dimension whose family is undisclosed.` | 35–39 |

*Worked example for CL2-3 (non-normative).* The maker is a model of family `gpt`, answered at
`api.a.example`. Dimension D1 is read by E1 (`gpt`, at `api.b.example`), E2 (`undisclosed`, at
`api.c.example`), E3 (`qwen`, at `api.d.example`) and one person. E1 and E2 count as the maker's family:
twice 2 is 4, no more than the 4 evaluators of D1, so (c) holds. E3 differs in family, and none of its
endpoints is the maker's, so (b) holds. Had one of E3's checks named `endpoint` `api.a.example`, no model
evaluator would differ in both, and (b) would fail. Had the maker's own `family` been `undisclosed` and
D1 been read only by E1 (`gpt`, at `api.b.example`) and E3 (`qwen`, at `api.d.example`), the two
disclosed families `gpt` and `qwen` could not both be the maker's, so (b) would hold, and the largest
disclosed family on D1 would have 1 of the 2 evaluators, so (c) would hold too.

### 5.4 CL3 — proven

| ID | Requirement | Class |
|---|---|---|
| CL3-1 | For every evaluator and dimension it checked, `demonstrations` holds a planted case on which that evaluator returned `does_not_conform`, timed before its first check of that dimension. The planted case is held out from the maker; the record carries only its digest. | semantic |
| CL3-2 | The bar is published: `bar.publishedAt` is a URI where the people who rely on the record can read it. | structural |
| CL3-3 | The record is signed and logged in a transparency log: a Sigstore bundle holding the record as a DSSE envelope, logged in Rekor. `external` holds the bundle, read by a named party who is not the maker. A verifier reads `OK` only when it verifies the bundle itself (signature, certificate and log entry) against the record; one that does not reads `NOT-CHECKABLE`, even when the bundle's digest matches. | external |

### 5.5 Baseline

| ID | Requirement | Class |
|---|---|---|
| BL-1 | A record that claims `baseline` has a `bar.frozenAt` strictly later than `startedAt`, a `startedAt` no later than `producedAt`, and lists in `readsBeforeFreeze` what was read before the bar was frozen. A baseline record carries no conformance level: a bar written afterward is a description, not a standard. | semantic |

### 5.6 The four observation states

| State | Effect |
|---|---|
| A dimension with **no check** | The record fails (CL1-7) |
| A check with outcome **`unobserved`** | The record stays valid; the dimension is not scored; the overall result cannot be "all conform"; the record goes to the approver (CL1-8, CL1-13) |
| **`conforms`** / **`does_not_conform`** | As read |
| **Disposition** | Always separate from outcomes, never rewriting them |

---

## 6. Verifying a record *(normative)*

A verifier is given the record, the artifact's files, the bar file, and the evidence files the record names. It reports,
for each requirement in scope, `OK`, `FAILED`, or `NOT-CHECKABLE`, and then (the requirements in scope are
those section 5 says the claimed level must meet: a `baseline` claim is not held to CL1-1 or CL1-15, nor
to any CL2 or CL3 requirement; a CL1, CL2 or CL3 claim is not held to BL-1):

- **verdict** — `FAILED` if any requirement failed; otherwise `NOT-CHECKABLE` if any could not be checked;
  otherwise `OK`;
- **level achieved** — the highest claimed-or-lower level whose requirements, and those of every level
  below it, are all `OK`; `baseline` when a baseline claim passes; `none` otherwise;
- **routing** — `to approver` when the disposition is `not_yet_given`, or when a check is `unobserved` and
  no `given` disposition acknowledges every unobserved dimension; `acknowledged` when a check is
  `unobserved` and a `given` disposition acknowledges every unobserved dimension; otherwise `none`.

A verifier MUST NOT report a level the record does not claim, and MUST NOT turn an `unobserved` outcome
into any other outcome.

`checker/check.py` is a reference verifier. It is not normative: where it and this document differ, this
document governs, and the difference is a bug in the checker.

---

## 7. Security and privacy considerations *(normative)*

**The record can be separated from the artifact.** Kept beside the work, a record can be dropped by
anyone who copies the work. CL1-14 binds the record to the artifact by digest; CL3-3 adds a signature
and a transparency-log entry so a stripped record can be found again.

**Held-out cases stay held out.** At CL3 the record carries only the digest of each planted case. A
planted case published with the record teaches the next maker to write to it. "Held out" means held out
from the maker of this record: a control or planted case that this record's maker never saw is held out
for this record, whoever else has seen it. The same holds for CL1 controls.

**A control shows what a reader caught, not how hard the case was.** A verifier confirms that each control
was read and that its outcome matched what was expected. Whether a control could have been missed is a
judgment no verifier can make from the record.

**The custody log has no outside anchor.** `tools/record.py` chains each event to the one before it, so an
edited, removed or reordered event inside a log is caught. A log rewritten from its first event, or cut
short at its end, still verifies. Signing the record (CL3-3) is what fixes it in place.

**Signing publishes the signer.** A transparency log is public and permanent: a record signed for CL3-3
puts the signer's identity in that log for good.

**Publication is optional.** CL1-12 requires the record be kept and producible, not public. Evidence can
name people and contain confidential work; a record holder MAY withhold evidence files and publish only
digests. A verifier without them reads CL1-8 and CL1-15 as `NOT-CHECKABLE`.

**Names are personal data.** `by`, `author`, and `name` fields identify people. Record holders are
responsible for the law that applies to them.

---

## 8. Versioning *(normative)*

This specification follows Semantic Versioning 2.0.0. A record names the version it was written to in
`specVersion`. A change that would turn an `OK` record into a `FAILED` one is a major change; the
predicate type's version changes with the major version. Before 1.0.0, any release may make such a
change, and CHANGELOG.md lists it. An identifier renamed within a major version keeps its old value valid
until the next major version: `CL2-4` is not a requirement of its own; it is the former name of `CL1-15`,
accepted wherever `CL1-15` is. Each release is
a git tag and is citable by commit. No implementation is part of the specification.

---

## Appendix A. Why a new predicate *(non-normative)*

in-toto asks a new predicate to explain why existing ones do not cover its use. Read against the
predicates vetted in the in-toto Attestation Framework at tag `v1.2.0` and the SLSA Verification Summary
specification (the draft in the SLSA repository at commit `3cd3fdd`):

| Existing predicate | What it records | What `custody/v1` needs that it does not carry |
|---|---|---|
| **SLSA Verification Summary** (`slsa.dev/verification_summary/v1`) | A verifier's `PASSED`/`FAILED` against a policy, with SLSA levels | A bar frozen *before* the work; buyer and specialist approval of that bar; per-dimension outcomes including `unobserved`; controls; a named human disposition separate from the result |
| **Test Result** (`in-toto.io/attestation/test-result/v0.1`) | One test-suite run: `PASSED`/`WARNED`/`FAILED` and test names | Judgment by evaluators who are not the maker; the bar's provenance; a third outcome that refuses to score; disagreement between readers |
| **Simple Verification Result** (`in-toto.io/attestation/svr/v0.1`) | Properties a trusted verifier confirmed | It lists only passing properties and states it does not carry information to reproduce the result; custody needs every outcome and enough to reconstruct the decision |
| **SCAI** (`in-toto.io/attestation/scai`) | Attributes of software and its supply chain, with evidence | No bar, no evaluator separation, no disposition |
| **Human review** | No human-review predicate is in the vetted list at `v1.2.0`; one appears only as an example in SLSA material | — |

`custody/v1` can reference any of these as evidence in a check. It does not replace them.

## Appendix B. Lineage *(non-normative)*

This specification was condensed from a private working corpus (`e-di`, archived at commit `a48a464`)
and checked against the commitments published on evaluatordriven.com. That corpus is **lineage, not
evidence**: nothing here depends on it, and readers cannot inspect it.

## Appendix C. Patent non-assertion *(non-normative pointer)*

See `PATENTS.md`.
