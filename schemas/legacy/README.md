# Frozen schemas — one directory per generation

These are copies of the schemas as they stood in each generation. They are frozen on purpose and must never
be edited. A filed record keeps the vocabulary it was written in; a reader maps it forward.

**Generation map.** `tests/validate_audit.py` holds the same table — a record is judged against the
generation in force on the day it was filed, never against today's schema.

| Generation | Directory | In force | Vocabulary |
|---|---|---|---|
| pre-observation | `schemas/legacy/` (this level) | before 2026-09-20 | `evidence` / `evidence_channel` / `fix` / `unevidenced_dimensions`, terminal state `needs_human` |
| Plumbline §8 extension | `plumbline-s8-2026-09/` | 2026-09-20 → 2026-09-29 | `observation` vocabulary; audit-only fields as top-level properties; `severity: P0/P1/P2` |
| derived from the corpus | `schemas/` (live) | from 2026-09-29 | corpus §5 shape exactly; Plumbline's record-level additions ride in `instance_extensions` |

## pre-observation (this level)

Audit records `audits/2026-09-18-*.json` cite `evidence_channel`, `evidence`, `fix`,
`unevidenced_dimensions` and the terminal state `needs_human`. Those are the names in force when the records
were filed, and the Contracts' own rule (v1.8 §12) is that a record keeps the vocabulary it was written in.
Rewriting the records would destroy the thing that makes them evidence, and loosening the live schemas to
accept both vocabularies would make the rename unenforced.

So: historical records validate against these snapshots, live records validate against `schemas/`. A record
whose date is after the cutover that fails the live schema is a defect; one that fails it only because of the
old vocabulary is a mis-filed record, and the fix is the record, not the schema.

| Old name | Current name |
|---|---|
| `evidence_channel` | `observation_channel` |
| `evidence` (dimension) | `observation` |
| `evidence_ref` | `observation_ref` |
| `evidence` / `fix` (violation) | `observation` / `remedy` (optional) |
| `unevidenced_dimensions` | `unjudged_dimensions` |
| `needs_human` (terminal state / verdict) | `needs_owner` |

## 2026-09-21 — `generator` → `maker`

The `job-packet` property `generator` was renamed `maker` when proposals 0010 and 0011 were ratified
(Contracts v1.9). **No packet was ever filed under the old name**, so no frozen schema is added for it: an
instance that appears with `generator` is a defect to correct, not a record to grandfather.

## 2026-09-29 — `plumbline-s8-2026-09/`

Frozen when Plumbline's schemas stopped being hand-authored and became derived from the corpus
(`tools/build_schemas.py`). The generation it replaces carried audit-only fields as top-level properties of
its own `audit-record.schema.json`, and a `severity` enum (`P0/P1/P2`) that the Contracts explicitly do not
define — an implementation "must not copy them, must not invent substitutes".

**No audit record was filed under this generation**, so this directory is provenance rather than a
requirement: it records what the instance law was when the alignment happened. It is kept because the next
reader is entitled to know which schema a record filed in that window would have been judged against — and
because a freeze that only exists for records that happen to exist is a freeze that arrives too late.
