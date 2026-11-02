# Examples: two frozen E-DI jobs with custody/v1 records

These are two of Plumbline's own jobs, copied exactly as they were closed. Nothing in a job folder has been
edited for publication.

| Job | What it did | Subject commit | Public custody checker @ `3e3ca58` |
|---|---|---|---|
| `2026-10-27-custody-emitter-gaps` | Closed gaps in the custody/v1 emitter | `c7db5b0` | `OK`, `CL1`, 19/19 |
| `2026-10-28-custody-times-ledger-spend` | Added custody times, ledger commands, fixture modes and spend caps | `912828a` | `OK`, `CL1`, 19/19 |

## Provenance

- **Frozen evidence.** Each record's digests bind the bytes of its bar, evidence and subject files, so the
  files are not rewritten. They keep the paths, user names and machine names of the environment that produced
  them, such as home-directory paths, box paths and model-harness logs. Tidying them would break the records.
- **Subject bytes.** A record judges files at a commit of Plumbline's private development repository, which
  is not public. `subjects/<job-id>/` holds exactly those files at that commit. Every sha256 matches the
  record's `subject` digests.
- **Plumbline layer.** Both records predate the current `x-plumbline` schema. `kit/plumbline_verify.py`
  passes them at the custody layer and then reports exit 4 (Plumbline-layer schema failures on
  `x-plumbline.schema` and `x-plumbline.hand_times`). That result is expected and is not a custody failure.

## Re-check a record

```sh
git clone https://github.com/evaluatordriven/custody
git -C custody checkout 3e3ca58de5631bdc58291564303a2e9d25a8653e
cd examples/2026-10-27-custody-emitter-gaps
python3 ../../custody/checker/check.py custody/record.custody.json \
  --files ../subjects/2026-10-27-custody-emitter-gaps \
  --evidence custody/evidence --bar custody/bar.md
```

For the other job, use the same command with `2026-10-28-custody-times-ledger-spend`. Expected result for
both: exit 0 and `"verdict": "OK"`, `"levelAchieved": "CL1"`, all 19 requirements `OK`. Each job's
`custody/CHECK-COMMAND.txt` is the command used when the job closed. That command uses `--files ../../..`
because the job then lived at `dot-plumbline/jobs/<id>/` inside the development repository. Here,
`--files ../subjects/<job-id>` takes its place.

## Run Plumbline's two-layer verifier

From the repository root, with the same custody checkout:

```sh
J=2026-10-28-custody-times-ledger-spend   # or 2026-10-27-custody-emitter-gaps
python3 kit/plumbline_verify.py --record examples/$J/custody/record.custody.json \
  --files examples/subjects/$J --evidence examples/$J/custody/evidence \
  --ledger examples/$J/inputs/custody-events.jsonl --custody custody
```

Expected result for both: **exit 4**. The custody layer passes; the Plumbline layer then reports `FAIL schema`
lines for `x-plumbline.schema` and `x-plumbline.hand_times`, because these records were written before the
current `x-plumbline-v1` schema. Exit 3 would mean a custody-layer failure; neither record gives it.
