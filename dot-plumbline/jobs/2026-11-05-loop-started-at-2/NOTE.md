# Filed, not closed

These files are the surviving loop record for job `2026-11-05-loop-started-at-2`.
They were copied byte for byte. They were not produced by `plumbline_job.py open` or `close`.

`open` needs a brief. No brief is on disk. `close` needs a §5 run file.
`summary.json` is the loop summary, not that file. Inventing either would make a missing reading look like a closed job.

The code this job accepted is already on `main`: feature commit `bd5d73c`, merge `cb746094636113f157281539ad54668f653f980b` (PR #8).

What is here:

- `packet.json` — the ratified packet. sha256 `9cb9ae27044bebfc5059644fedcc9d0510b2cbec4cc35bb81d24bb8d9ed03235`
- `summary.json` — `stop: accepted`, `terminal_state: accepted`, `accepted_round: 1`
- `round-01.json` — the round the summary names. sha256 `9c64baf5214c1423b869523fbec47bbcffe8853f7c2eec4a4d20273979469979`
- `eval-score.json` — the score the loop parsed
- `cost-01-maker.json`, `cost-01-eval-0.json`, `cost-01-eval-1.json` — the measured cost files

Aider transcripts were left out. They are not required to reconstruct the accept.
