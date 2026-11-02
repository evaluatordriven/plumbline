# Held-out controls — job 2026-10-28-custody-times-ledger-spend
STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — part of the freeze set; sha256 in ../MANIFEST.sha256.

The controls are NOT in this repository and must never be put in it or in any Maker prompt. They live on the shared
box at `/workspace/job-controls/2026-10-28-custody-times-ledger-spend/` (readable by other agents on that box; disclosed). Only their manifest is committed:
`controls/MANIFEST.sha256` (1130 files), sha256 of the manifest fe03346b4b62240ec461f3feedc89ae28b6d96fc177e967852566cec1a655ccf.
T6 also re-uses the prior job's controls at `/workspace/next-job-controls/controls/` (manifest 9764d8e4...60bf), copied
into the held-out set under `t6/` with their own manifest.

Per batch the Evaluator bot copies the folder to a writable copy under `/workspace/edi-work/2026-10-28-custody-times-ledger-spend/eval/` (never /tmp)
and checks it with `sha256sum -c` against this manifest before the batch; `run_instrument.sh` checks it again itself
(exit 3 on mismatch). S1: every S1 check has at least one planted case that must FAIL and one clean case that must
PASS, run in the same batch. E-GLM: every J batch carries its planted and clean listings (J1: 2 planted + 1 clean;
J2: 3 planted + 1 clean; J3 and J4: 1 planted + 1 clean each), checked against `glm/expected.json`; the control
order rotates per batch and the subject is read from the batch's own `order`. Any control answered wrong makes the
batch void: counted against money and time, not against the cap.

Interpretations disclosed (no change to what any check means):
- F1 refusal detection accepts `REFUSED:` on stdout or stderr (base commands print it on stdout; INTERFACE.md asks
  new refusals on stderr).
- J3/J4 controls are planted and clean versions of the field guide; the J3 prompt carries a verbatim CC BY 4.0 copy
  of DOCTRINE.md @ dc61854 (`freeze/instrument/fixtures/doctrine/`).
