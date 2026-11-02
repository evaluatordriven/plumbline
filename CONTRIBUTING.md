# Contributing

## Two kinds of change

| Kind | What it is | What it needs |
|---|---|---|
| **Behavioral** | Anything that could change what the emitter writes, what the verifier accepts, or what a schema allows | A failing record or packet from real use, or a reproducible counterexample, attached to the issue |
| **Editorial** | Wording, typos, examples, layout | A declaration in the pull request: *no semantic change* |

A behavioral change without a failing record or counterexample is closed, not argued.

**Derived schemas are never hand-edited.** Change `schemas/instance-extensions.json` (or the vendored custody
schema, by re-vendoring), then run `tools/build_schemas.py`. Read `AGENTS.md` before changing anything.

## How to file a failing record

1. Run `python3 kit/plumbline_verify.py --record your-record.json ...` (see `docs/custody-emission.md`).
2. Open an issue with the record, the output, and one sentence on what you expected instead.
3. Remove anything confidential first; digests are enough for most reports.

## Before you open a pull request

```sh
pip install -r requirements.txt
python3 tests/run_all.py          # every suite; the last line is PLUMBLINE-TALLY pass=… fail=… skip=…
```

It must exit 0 (`fail=0`), and the tests must leave the working tree clean (`git status` shows nothing new).
Without the E-DI corpus checkout, the five corpus checks print `SKIP[corpus] <id>: <reason>` and are counted
as skipped, not passed. If you have the checkout, set `EDI_CORPUS` to it and run `tests/run_all.py` again: each
of the five then prints `RAN[corpus] <id>: pass`. Set `PLUMBLINE_REQUIRE_CORPUS=1` to make a missing corpus a
failure instead of a skip. Only `1` turns it on; unset, `""` or `0` leave it off, and any other value is a usage
error. An `EDI_CORPUS` that is set but is not a corpus checkout is an error naming the path (an empty
`EDI_CORPUS` counts as unset), never a fallback. `kit/emit_packet.py`, `kit/plumbline_job.py` (open and
close) and the schema build need the corpus checkout and refuse without it; `kit/emit_record.py` without it
writes an unvalidated record and exits 1.

A change to the corpus pin re-vendors `schemas/vendor/e-di@<pin8>/` from the new commit and updates its
`VENDOR.json`; `tools/build_schemas.py --check` fails until the copy, `VENDOR.json` and `tools/pin.json`
agree. A new rule arrives with a fixture that fails for it and only it.
