# Changelog

Versions follow Semantic Versioning 2.0.0. Before 1.0.0 any release may change what the emitter writes or
what the verifier accepts; every such change is listed under **Breaking**. Each release is a git tag and is
cited by its commit.

## Unreleased

**Added**
- `kit/conductor_software.py` and `kit/conductor_run.py`: a single-turn release-gate building block. It detects a green base, a frozen path in the editable set, an edit or a new file outside that set, a Maker that changed nothing, a non-zero Maker exit, a moved freeze, and a timeout. Nothing is skipped by default: `.git` and `__pycache__` are recorded. The caller may pass an ignore list; ignored paths are listed on the record. Ignoring `__pycache__` re-opens a bytecode plant. The default bound is 600 seconds. A command that starts its own session leaves the process group and is not killed; this is not a sandbox. It does not stop edits. It is not the conductor: routing, cap, budget, the state machine, and persistence are not here. The conductor is still unbuilt.

## 0.1.0 (2026-11-02)

First public-facing cut: a custody/v1 emitter plus an E-DI kit.

**Added**
- `tests/fixtures/custody/verify/real/`: a synthetic job and its emitted custody record that custody's real
  checker (@ `3e3ca58`) accepts; the real-checker test now runs on it and passes, and CI runs that test.
- `kit/plumbline_verify.py`: a standard-layer failure (exit 3) now prints, under its `FAIL standard record`
  line, one line per requirement the checker reports `FAILED`, with the requirement id and detail.
- `LICENSE` (CC BY 4.0, text), `LICENSE-CODE` (Apache-2.0, code) and `NOTICE`.
- `requirements.txt`, `CONTRIBUTING.md`, `SECURITY.md`, this changelog, and `kit/plumbline.py --version`.
- `schemas/vendor/e-di@f8bfb793/`: the corpus's job-packet and evaluator-record schemas and its 45-fixture
  battery, vendored byte for byte at the pin, with `VENDOR.json` (source, commit, copy command, sha256 of each
  file, licence). `NOTICE` names it.
- `tests/run_all.py`: runs every suite and `kit/cases/run_cases.py`; prints one `SKIP[corpus]`, `RAN[corpus]`
  or `FAIL[corpus]` line per corpus check and ends with `PLUMBLINE-TALLY pass= fail= skip= skipped=`.
- `tools/edi_corpus.py`: one corpus resolver for the tools and suites (`--corpus`, `EDI_CORPUS`, the Hermes
  config where it existed), with `PLUMBLINE_REQUIRE_CORPUS`.
- `.github/workflows/ci.yml`: `tests/run_all.py` on Python 3.11–3.13 with no corpus and an empty `HOME`, and
  the custody upstream comparison.
- `examples/`: two frozen job records with their custody/v1 records and the subject bytes they bind
  (`examples/README.md`). This public repository is a fresh snapshot; Plumbline's other job, audit and probe
  records stay in a private evidence archive.

**Changed**
- The corpus pin moves from the private development pin `e-di@a48a4645` (Contracts v1.22.0) to the public
  `evaluatordriven/doctrine` at `f8bfb7934dbb` (Contracts v1.27.0), read from its `contracts/` directory.
  `tools/pin.json` gains `path` (`--check` requires the corpus to be exactly `<checkout>/contracts`) and
  `doctrine_files`, the sha256 of `DOCTRINE.md` and `AUTHORITY.json`, whose drift `--check` reports.
  The four derived schemas are rebuilt; the checklist now runs C1–C40 with C17 retired.
- `kit/cases/run_cases.py` reads two committed stand-ins, `tests/fixtures/cases/readings-control.json` (the
  corpus's `readings-census.json`) and `scored-control.json` (a neutral stand-in scored packet), instead of two
  unpublished job packets, so it runs in a checkout with no `dot-plumbline/jobs/`. 37 cases.
- `kit/emit_packet.py` prints a NOTE when the brief's evaluator has no `kind` (`person`, `model` or `script`;
  Contracts §4). It is optional, so it never refuses.
- CI gains a `corpus` job: doctrine checked out at the pin, `tests/run_all.py` with `PLUMBLINE_REQUIRE_CORPUS=1`.
- `tests/validate_audit.py`: a checkout with no `dot-plumbline/audits/` of its own and no audit home in reach
  now reports that by name and passes on its schema checks. A checkout that has the directory but no records
  still fails.
- `tools/pin.json` and the derived schemas name the corpus repository (`github.com/evaluatordriven/doctrine`), not a
  local path; the checkout is resolved through `--corpus` or `$EDI_CORPUS`.
- Scripts use `#!/usr/bin/env python3` and resolve their own repository; no machine-specific paths.
- Probe and conformance-read tools take their keys from the environment; `tools/edi/or_call.py` reads its key
  file from `--key-file`, `$OPENROUTER_KEY_FILE`, or `~/.openrouter-key`.
- `tests/validate_schemas.py` hashes with `hashlib` instead of calling `shasum`.
- The suites run with no corpus. `tests/validate_schemas.py` runs the fixture battery on the vendored copy;
  `tests/validate_audit.py` checks the record schema against the vendored one; `tools/build_schemas.py --check`
  checks the vendored copy against `VENDOR.json` and `tools/pin.json`. The checks that need the corpus itself
  (`corpus.audit-equality`, `corpus.battery-equality`, `corpus.build-check`, `corpus.pin-on-disk`,
  `corpus.run-cases`) print `SKIP[corpus] <id>` without one, or `FAIL[corpus] <id>` under
  `PLUMBLINE_REQUIRE_CORPUS=1`.
- `EDI_CORPUS` set to something that is not a corpus is now an error naming the path (exit 2); it no longer
  falls through. Only `PLUMBLINE_REQUIRE_CORPUS=1` turns the requirement on; any value other than unset, `""`,
  `0` or `1` is a usage error. A Hermes config that cannot be read is reported, not ignored, and one whose `corpus` is not a corpus
  checkout is an error (exit 2), no longer ignored.
- `kit/plumbline.py --doctor` with no corpus reports `corpus NOT RESOLVED` and exits 0 (it exited 1), or 1
  under `PLUMBLINE_REQUIRE_CORPUS=1`; its `corpus pin` line shows the pin from `tools/pin.json`.
- `kit/cases/run_cases.py` takes the corpus from `EDI_CORPUS` when no argument is given; with neither it
  prints `SKIP[corpus] corpus.run-cases` and exits 0.
- `tools/build_schemas.py --check` names a corpus that is not a git checkout (`COMMIT NOT VERIFIABLE`) and each
  derived file that does not rebuild byte-identical.
- The emitter tests' throwaway git tree ignores `__pycache__/`, so the suite passes with bytecode on.
- `kit/emit_record.py` resolves its corpus with `tools/edi_corpus.py` (`--corpus`, `EDI_CORPUS`, the Hermes
  config, `PLUMBLINE_REQUIRE_CORPUS`) and does so before it writes anything. With no corpus it exits 1 and writes
  nothing (it wrote the record and its pass files, then exited 1); a `--corpus`, `EDI_CORPUS` or Hermes value that
  is not a corpus, or a bad `PLUMBLINE_REQUIRE_CORPUS`, exits 2 naming it (it exited 1). A resolved corpus prints
  `corpus source: <src>`. New test: `tests/test_emit_record.py`.
- `.github/workflows/ci.yml` uses `actions/checkout@v7` and `actions/setup-python@v7` on `ubuntu-26.04`.

**Fixed**
- `tools/edi/or_call.py`: request and response headers pass through the new `log_safe_headers` before they
  reach the harness log. Credential and cookie headers (`Authorization`, `Proxy-Authorization`, `X-API-Key`,
  `api-key`, `Cookie`, `Set-Cookie` and similar, any case) are masked; a Bearer `Authorization` logs as
  `Bearer [REDACTED]`. Other headers such as `Date` and `CF-Ray` are kept.
- `kit/custody_ledger.py spend` writes `spend_ledger` and `key_reading` relative to the job directory, with
  `../` steps when the file lives outside the job, never as an absolute path.

**Known gaps**
- C37–C40, the §4 roles table and Instrument A2/I2 are new in this corpus. No Plumbline check, case or fixture
  exercises them yet.
