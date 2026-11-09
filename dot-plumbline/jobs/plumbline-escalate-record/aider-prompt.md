# Task: implement `kit/escalate.py` so the frozen bar `tests/test_escalate.py` passes

The failing tests are the spec. Read `tests/test_escalate.py` in full before writing
anything, and implement the module it imports.

## Current state (measured this turn)

`python3 tests/test_escalate.py` exits 1 with:

    ModuleNotFoundError: No module named 'kit.escalate'

`kit/escalate.py` does not exist. That import being absent is the only red. A later
failure that is an assertion inside the bar, reached by an attempt to satisfy the bar
in ways the bar does not describe, is the wrong red.

## Files

- Write: `kit/escalate.py` (does not exist yet; create it).
- Do not edit:
  - `tests/test_escalate.py` (frozen; sha256
    `40eb3d7e3b985974ff3f462b4252c6fc7a65d71848b1431f98f5efe76dd0c7af`)
  - `kit/conductor_loop.py` — the bar asserts at `tests/test_escalate.py:310-313` that
    this file contains neither `kit.escalate` nor `import escalate`. It already
    satisfies that today. Changing it breaks the bar.
  - `schemas/job-packet.schema.json` — the bar validates against it as-is.
  - Any other file outside `kit/escalate.py`.

## What the bar requires (the observables, not a design)

Derive the implementation from the test file. These are the points it checks, so you
know where to look; the exact assertions are in the file.

1. `test_module_is_public_kit_escalate` — the module resolves to `kit/escalate.py` under
   the repo root; its **source text** contains no email address and none of the profile
   names listed in `PROFILES`; `deliver` takes `architect` and `transport` as required
   (no default) keyword/positional parameters and raises `TypeError` when they are
   omitted.
2. `test_loop_does_not_call_the_architect` — already green; do not touch
   `kit/conductor_loop.py`, and do not import it into a name the bar's loop guard would
   interpolate (see the guard in `_guard_loop`).
3. `test_broken_or_incomplete_architect_delivers_nothing` — architect raising, returning
   `None`, a bare string, `{}`, or a dict whose `text` is empty/blank/`None` results in
   **zero** transport calls, no copy of the analysis text written under the record dir,
   and no `delivered: true`.
4. `test_delivers_architect_text_with_sha256_and_not_verified` — on a send, the
   transport is called once with the text unchanged (first positional arg or `text=`
   keyword), the result is a dict with `delivered is True` and
   `sha256 == sha256(text utf-8).hexdigest()`, that same digest appears in some file
   under the record dir, and **nothing** labelled `verified` appears in the result or
   in any file the call wrote (the bar scans keys, values and JSON blobs).
5. `test_retry_does_not_send_twice_or_rerun_rounds` and
   `test_transport_failure_is_not_sent_twice` — after transport has been called once,
   a later `deliver` (even after `importlib.reload`) does not call transport again,
   including when the first transport call raised. The record dir is the durable state;
   the module-level state is not.
6. `test_broken_run_does_not_consume_the_send` — a broken architect run is not a send,
   so a later finished run still sends exactly once.
7. `test_decide_records_the_reply_and_does_not_touch_terminal_state` — `decide(record_dir,
   reply)` writes the reply's exact text into some file under the record dir and leaves
   `terminal_state` in both `summary.json` and `escalation.json` byte-identical.
8. `test_proposed_packet_ratified_is_not_delivered`,
   `test_proposed_packet_invalid_is_not_delivered`,
   `test_proposed_packet_unratified_is_delivered_and_not_run`,
   `test_null_proposed_packet_is_not_present` — a `proposed_packet` that validates
   against `schemas/job-packet.schema.json` (Draft 2020-12) **and** says `ratified: true`
   is not delivered; an invalid `proposed_packet` is not delivered; a valid unratified
   one is delivered; `None` and a missing key mean not present and change nothing about
   delivery.

## Explicitly out of scope

The bar's docstring (`tests/test_escalate.py:55-69`) lists open questions the module
must not answer: no minimum option count, no clock arithmetic, no `decision.json`, no
`escalation_id`, no `prepared`/`sent`/`answered` state names, no exit-code policy, no
`_held_out`. Do not encode answers to them. Do not add a CLI or an intent file. Do not
add a hardcoded address or profile name anywhere in the module.

## Done

`python3 tests/test_escalate.py` exits 0. Do not modify the bar to get there.
