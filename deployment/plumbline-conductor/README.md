# Plumbline conductor seat-move notices

This directory records how seat-move notices reach the conductor's `Bot Chat`
and how the profile's loop invokes them. The script is
`deployment/plumbline-conductor/seat-move-notice.py`; it imports
`kit.seat_move_notice` and calls `send_notice` for both directions.

These files are records of the deployment step. Nothing in this directory
installs anything.

## Install

Copy or symlink the repo-resident script into the conductor profile:

    ~/.hermes/profiles/plumbline-conductor/bin/seat-move-notice.py

The script imports the repo-resident module `kit.seat_move_notice`, so the
repository root must be importable (on `PYTHONPATH`, or the profile's working
directory must be the repo root).

## Channel: the Plumbline mailbox

The conductor's `Bot Chat` is a CLI session, and a side process must not write a
session it does not own. Seat moves therefore travel through a Plumbline-private
mailbox under the conductor profile's runtime directory:

    ~/.hermes/profiles/plumbline-conductor/runtime/plumbline-seat-notices/

`send_notice` writes one durable JSON notice into that directory and returns the
notice id. It never writes the session, runs no `hermes` subprocess, and takes no
session lease.

## Side-process enqueue hooks

The profile launcher script, produced by the deployment step, lives at:

    ~/.hermes/profiles/plumbline-conductor/bin/run-loop

`run-loop` invokes the notice script at the two hook points where the side
process detects a seat move:

- **to_seat** — work is dispatched to a seat:

      seat-move-notice.py --direction to_seat --seat "$SEAT" --job-id "$JOB_ID"

- **from_seat** — a seat hands work back:

      seat-move-notice.py --direction from_seat --seat "$SEAT" --job-id "$JOB_ID"

Both calls enqueue into the mailbox above. A write failure surfaces as a non-zero
exit; the notice is never silently dropped. Set `PLUMBLINE_SEAT_NOTICE=0` to
disable delivery without writing anything.

## Conductor-own-turn stage and consume hook

The conductor's turn launcher brackets every turn with `kit.seat_move_drain`:

1. `prepare_turn(profile_home=...)` recovers any notices left in the in-flight
   directory by a previous failed turn, drains the mailbox in FIFO order into
   `runtime/plumbline-seat-notices/inflight`, and returns `(notices, context)`.
   The launcher hands `context` to the Bot Chat, which announces it as its own
   prose.
2. The turn runs.
3. Only after the turn completes cleanly does the launcher call
   `consume_turn(profile_home=...)`, which deletes the staged files.

A turn that raises leaves the staged files in `inflight`. The next turn recovers
them before staging, so the notice is announced exactly once on the retry and
then consumed. An empty mailbox returns an empty context string, writes nothing,
and costs nothing. A corrupt notice file raises from `prepare_turn` before any
file is staged, so a bad receipt is never replayed or silently dropped.

The live acceptance step -- enqueue a real notice, run a conductor Bot Chat turn,
and confirm the text appears in session `20261106_173554_a10444` title
"Bot Chat" in `state.db` -- is recorded in `seat-move-turn.md`.
