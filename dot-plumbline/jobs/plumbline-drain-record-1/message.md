The frozen bar is tests/test_seat_move_notice_drain.py. Run it:

    python3 tests/test_seat_move_notice_drain.py

It is red: Ran 7 tests, FAILED (failures=1, errors=6).

Your editable set is three paths, all in this dispatch's `files` list, and all inside the worktree:
  - kit/seat_move_drain.py                                 (new: the drain/announce module)
  - deployment/plumbline-conductor/seat-move-notice.py     (existing: the deployment entry point)
  - deployment/plumbline-conductor/README.md               (existing: the deployment record)

The bar is your read-only reference. Read it and implement what its seven tests demand; plant nothing in it.

What it encodes, in short: when a conductor turn begins, whatever is waiting in the seat-notice mailbox is
staged and handed to the turn as context so the turn can announce it; a turn that fails leaves the notices
recoverable -- not lost, and not announced twice on a retry; an empty mailbox changes nothing and costs nothing.
Corrupt receipts raise rather than being replayed. The deployment record must document the consume-after-success
mechanism and the live verification step.

Note the boundary that has bitten this program twice: everything you need is inside this worktree. Do not write
to the profile directory, do not shell out to a hermes session, and do not claim a session.

Rule 12 applies: the red above is what the bar reports, and the bar is the standard.

Do not edit tests/, schemas/, tools/, kit/conductor_loop.py, or any other kit/ file.
