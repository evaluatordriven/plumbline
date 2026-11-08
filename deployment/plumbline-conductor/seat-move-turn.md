# Seat-move notices in the conductor Bot Chat: stage and consume

This record documents how a seat-move notice reaches the conductor's `Bot Chat`
and how the deployment is verified against a live session. It complements
`README.md`; nothing in this directory installs anything by itself.

## Turn boundary

The conductor's turn launcher brackets each turn with `kit.seat_move_drain`
(the template is `deployment/plumbline-conductor/seat-move-turn.py`, copied into
the profile's `bin` directory):

    notices, context = prepare_turn(profile_home=CONDUCTOR_HOME)
    turn_result = run_turn(context)              # the Bot Chat turn
    consume_turn(profile_home=CONDUCTOR_HOME)    # only after clean success

`prepare_turn` does three things, in order:

1. Recover. Any `*.json` left in
   `runtime/plumbline-seat-notices/inflight` by a previous failed turn is moved
   back into the mailbox.
2. Drain. The mailbox is read in FIFO order and every notice is moved into the
   `inflight` staging directory.
3. Format. The parsed notices and a context string are returned; the launcher
   passes the context to the turn, which emits it as its own prose.

Parsing happens before staging, so a corrupt receipt raises with the mailbox
untouched instead of being replayed or silently dropped.

## Consume after success

`consume_turn` deletes the staged `inflight` files and is called only after the
turn returns cleanly:

- **Turn succeeds** — `consume_turn` deletes the staged files, so the notice is
  announced exactly once and never again on later turns.
- **Turn fails** — `consume_turn` is never reached; the files stay in
  `inflight`. The next turn's `prepare_turn` recovers them and announces them
  once, then the successful turn consumes them.

An empty mailbox returns `([], "")`, creates no `inflight` files, and leaves the
directory untouched.

## Live verification (Owner acceptance)

The fixture tests exercise `prepare_turn`/`consume_turn` against a temporary
profile home. They cannot write to a Hermes session, so the live Bot Chat step
is performed by the Owner:

1. Enqueue one real notice into the conductor mailbox:

       ~/.hermes/profiles/plumbline-conductor/runtime/plumbline-seat-notices/

   (for example by invoking `seat-move-notice.py --direction to_seat ...`).

2. Start a real conductor `Bot Chat` turn through the normal launcher.

3. Confirm the notice text appears in an assistant message in the SQLite state
   database:

       ~/.hermes/profiles/plumbline-conductor/state.db

   session `20261106_173554_a10444`, title "Bot Chat".

4. Confirm `runtime/plumbline-seat-notices/inflight` is empty after the turn,
   proving the notice was consumed, and that the same notice is not announced
   again on the next turn.
