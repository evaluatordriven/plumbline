# Script-driven Orchestrator qualification (`kit/qualify.py`)

`kit/qualify.py` qualifies a candidate Orchestrator text with no bot conducting (SPEC v2; DOCTRINE D6.1).
The script runs a fixed procedure; judgment stays with the seat that owns it. The Architect writes the suite,
manifest, runbook addendum and key. The Evaluator reviews the suite (S2 readiness gate) and scores each case
against the key (S6). The candidate, on fresh subject bots, answers the cases. The script does everything else:
hashing, the action sequence, clocks, the log, fixture reset, side-effect checks, contamination, leak and audit
scans, the record and the pass rule. A runner bot carries out each action file literally and writes receipts
(`kit/qualify/runner.md`). The Chief of Staff (conduit) creates the runner, reads its instructions back by sha,
sends it the fixed kickoff and reads the record; it never messages a seat. Steve authorizes the run, decides the
switch and deletes the runner and subjects. The candidate never arranges its own test.

## Transport, and what it cannot see

No supported API creates or messages Grok Bot agents, so the runner is the script's hands. The script keeps one
`Transport` interface (`create_subject`, `read_back`, `send`, `await_reply`, `export_trace`); `RunnerTransport`
turns each call into an action file and returns the runner's verified receipt. A supported API could implement
the same five methods in code with no other change. A fresh bot inherits every connector; the fence is the job
description, the per-action allow-list, receipt verification and the runner audit. Residual risk: the audit
trusts the platform transcript to be complete, so an act missing from the export is not seen; the
start-of-transcript footer check and Steve deleting the runner right after the run are the mitigation. The runner
needs no qualification: each act is pre-written, sha-verified and audited, so a bad runner costs a rerun, not a
false pass.

## Running it

Files: `kit/qualify.py`; `kit/qualify/runner.md`; `kit/qualify/templates/` holds `S1.request.md` (Architect),
`S2.request.md` and `S6.request.md` (Evaluator), `kickoff.md` (the conduit's message), `resume.md` (the conduit's
message after a ruled stop) and `header.txt` (the script-issued header). Suites, keys and runs stay out of this
repository. `tests/test_qualify_dryrun.py` replays S0-S7 against the platform's real tool shapes and limits
(below).

1. The conduit writes `runs/<ver>/<date>-runN/request.json`, creates `Qualify Runner (<ver>, run N)` with
   `runner.md` as its instructions, reads them back, records `runner`, and sends the output of
   `qualify.py kickoff <run>`. The kickoff names the absolute kit folder and the commit it is checked out at
   (`git HEAD`); S0 stops unless that HEAD starts with `pins.plumbline.sha` and `kit/` has no local changes
   (`steps/S0-head.json`).
2. The runner loops, one command per Shell call from the kit folder: `python3 kit/qualify.py next <run>` prints
   an action file; it performs that action, writes `actions/NNNN.receipt.json` and runs
   `python3 kit/qualify.py verify <run> NNNN`. `now` prints box time for receipts, `save` writes a seat reply,
   `wait` sleeps toward an intent's `not_before`, and `trace` turns ReadTranscript pages into an export.
3. At the end `next` prints `STOP <run>/STOP.md` or `DONE <run>/summary.json`, which the runner sends to Steve
   verbatim. `qualify.py stop <run> "<reason>"` records a stop the runner saw. Exit: 0 action or DONE, 3 STOP,
   4 rejected receipt, 2 usage.
4. Resume after a stop, on Steve's ruling only. The conduit writes a ruling file `{quote, time, message_id,
   channel, stop_sha256}` (Steve's words verbatim, where and when he said them, and the sha256 of the `STOP.md`
   he ruled on) and runs `qualify.py resume <run> --ruling <file>`. It refuses (exit 2, nothing written) when
   there is no `STOP.md`, the file is not JSON, a field is missing or empty, or `stop_sha256` is not the sha256 of
   the current `STOP.md`. Otherwise it writes `rulings/ruling-NN.json` (the ruling plus `stop_file`,
   `resumed_at`), renames `STOP.md` to `STOP-NN.md`, logs `resumed` with both shas and prints the resume message
   (`resume.md`), which the conduit sends to the same runner. On the runner's next `next`: an action the runner
   refused or left without a receipt is re-issued as `actions/NNNN.intent.K.json` (`supersedes`, and `ruling` with
   the quote, time, message id, channel and STOP sha) and logged `reissued`; a stop from a script check runs that
   check again, so a ruling never waives a failed check. A stop with no ruling file stays a stop.
   A re-issued `export_trace` starts fresh (Owner ruling 2026-11-16 12:29 EST, run 6 action 0101): before
   `NNNN.intent.K+1.json` is written, what attempt K kept, the page list `steps/trace-NNNN.pages.jsonl` (and
   `steps/trace-NNNN.json` and the `reply_to` file, if that attempt got so far), moves to
   `steps/trace-NNNN.attempt-K/`, never deleted, and the move is logged `trace_set_aside` (`attempt`, `moved`,
   `to`). The runner pages its transcript again from the newest page, and those pages are checked, joined and
   counted on their own; nothing reads the set-aside folder again, so scoring, the audit and a rescore see only the
   current attempt. Within one attempt the join check is unchanged: overlapping pages refuse. Before this fix the
   list was kept per action across attempts, so a fresh newest page (the transcript had grown) overlapped the
   kept pages and every call refused "do not join".
5. Resume at a later kit commit. A fix to the kit itself lands as a new commit, but the run is pinned to the old
   one, and every `next` checks the kit checkout's HEAD (with `kit/` clean) against the pin in force: request.json's
   `pins.plumbline.sha`, or the `kit_sha` of the latest ruling that moved it. To move it, the ruling file adds
   `kit_sha`, the full sha of the new commit. The conduit checks the kit folder out at that commit first and runs
   `resume` from it: it refuses unless HEAD is exactly `kit_sha` with `kit/` clean and the pin in force is an
   ancestor of `kit_sha` (`git merge-base --is-ancestor`). Without `kit_sha`, `resume` refuses when HEAD is not at
   the pin in force. `rulings/ruling-NN.json` records `kit_sha` and `kit_from`, the `resumed` log line both, and the
   re-issued intent's `ruling` the `kit_sha`. `steps/S0-head.json` keeps the first start's commit. The run's
   actions on record must be the ones the new kit would issue, or `next` stops ("not the action the procedure
   needs now"). So a kit fix that changes what an action says, or `runner.md` (its sha is in request.json),
   cannot resume a run. It needs a new run.
   One change to the S5 actions is replayed instead of stopping: a rescore. When a later kit finds a case's reply
   in an export an earlier kit already asked for (run 5: the subjects' SendToAgent used `agentId` or `agent_id`, some
   called directly), the case is
   scored from the first export that shows it, and the later exports of that case on record are performed again
   in order (verified from their receipts, or re-issued under the ruling when one has none) so the action numbers
   still match. Each such export logs `poll_replayed`; a case whose codes change logs `rescored` with `was` (the
   old `timeout`, `void`, `side_effects_rc`), the new codes and the `kit_sha`. The old `case` line stays. Script
   checks (`steps/*.json`) are read from their records as always; nothing is waived. The deny scan and timeout use
   the export that first showed the reply, as a live run would have.
   A copy of a run (`cp -a`) replays and resumes with no rewriting: intents name absolute paths under the dir the
   run was started in (the parent of `steps/S0-tmp.json`'s `tmpdir`), and the kit maps those to the same place in
   the copy.
6. Re-audit a finished run at a later kit commit (Owner ruling 2026-11-16 14:11 EST, run 6). A finished run
   (`summary.json` and `SHA256SUMS`) is not replayed: `next` prints DONE, and S6's request already carries the old
   audit result. `qualify.py reaudit <run> --ruling <file>` re-runs only the S5 runner audit, from the runner's
   saved export (its latest receipt verified, the export checked against `steps/trace-NNNN.json`). The ruling file
   is `{quote, time, message_id, channel, summary_sha256, kit_sha}`: Steve's words, the sha256 of the
   `summary.json` he ruled on, and the kit commit, which is checked as for `resume` (HEAD exactly, `kit/` clean,
   descended from the pin in force). It refuses, writing nothing, on a run with `STOP.md`, an unfinished run, a
   `SHA256SUMS` that does not check (`log.jsonl` may only have grown: a prefix ending at a line must match), or a
   ruling that fails a check. Nothing is rewritten. It writes `runner-audit.rK.txt` (`supersedes`),
   `summary.rK.json` (`runner_audit`, `qualified` by the pass rule from the recorded verdicts, `deviations`,
   `supersedes`, `reaudit`), `rulings/reaudit-KK.json` and `SHA256SUMS.rK`, and it logs `reaudited` (`was`, `result`,
   `qualified`, `kit_sha`). Case verdicts are not re-asked: the Evaluator scored with the old audit result in S6's
   request.

Stages: S0 preflight, S1 Architect, S2 gate, S3 subjects, S4 first-run contamination, S5 cases and the runner
audit, S6 scoring, S7 record. `qualified = all cases pass and void == 0 and not_run == 0 and runner_audit ==
clean`, in one batch; a rerun is a new run dir with a fresh runner and subjects, on Steve's word.

`request.json`: `ver`; `candidate_path`, `candidate_sha256`; `live_bot_id`, `live_sha256`; `prior_suite`
`{path (its manifest), manifest_sha256}`; `changes` `{list, diff_path}`; `pins` `{name: {url, ref, sha}}` for
plumbline, doctrine and custody; `owner_authorization` `{quote, time, message_id}`; `runner` `{bot_id,
instructions_path, instructions_sha256}`; `seats` `{architect, evaluator}`; `deny_paths` (the box paths of the
Evaluator and Chief of Staff stores, the runbooks and the provider key); optional `known_defects`, `pass_rule`
(`all`) and `case_window_minutes` (15).

## The record

The run dir is append-only: nothing is rewritten, and a correction is a new file naming the one it supersedes.
One move is made, never a rewrite or a delete: a re-issued `export_trace` renames its earlier attempt's files into
`steps/trace-NNNN.attempt-K/` ("Running it" item 4), logged `trace_set_aside`.
`log.jsonl` has one line per event (`at` with zone, `stage`, `action`, `payload_sha256`, `event`).
`actions/NNNN.intent.json` holds `{kind, target, payload_path, payload_sha256, allowed_tools}` (plus `reply_to`,
`not_before`); a re-issued action is `NNNN.intent.K.json` with `supersedes` and `ruling`; `rulings/ruling-NN.json`
and `STOP-NN.md` keep each ruled stop; `actions/NNNN.payload.md` a seat message; `actions/NNNN.receipt.json`
`{action_id, done_at,
platform_ids, reply_verbatim_path, reply_sha256, tools_called, sent_unedited: true}`. When `next` replays, a
verified receipt is passed over, an intent with no receipt stops (never resend blind), and neither means act.
`payload_path` is absolute; paths under the run's first dir are read relative to the dir the run is in now.
`replies/` keeps every reply, readback and export verbatim; `steps/<name>.json` what the script ran itself, once.
Then `S1.checks.txt`, `review.json`, `SUBJECTS-<ver>.txt` (case, subject, bot id, list order), `scores.json`,
`runner-audit.txt`, `summary.json` and `SHA256SUMS`, or `STOP.md` (stage, failing check, evidence path and
sha256, what was not done, seat words verbatim).

Key custody: the key lives only in the Evaluator's own store, never under `/workspace` and never in the script's
inputs, outputs or logs. The script knows only its sha256. The runner, the conduit and the subjects never read
the key or a store; the deny list and the runner audit enforce this.

## Decisions where the spec is silent

1. Commands beyond `next` and `verify`: `kickoff`, `stop`, `readback`, `resume`, `reaudit`, `trace`, `save`, `wait`,
   `now`.
2. A receipt that fails verification is `REJECTED`; the runner may correct it once as `NNNN.receipt.2.json` with
   `"supersedes"`; a second failure stops. An off-list tool in `tools_called`, `sent_unedited` not true or an
   edited payload is a runner deviation and stops at once.
3. `request.json` adds `ver`, `seats`, `deny_paths` (Q7 (a): the repo holds the rule and generic patterns, the
   box paths come from here) and `known_defects` (S1, SPEC L80).
4. "Trailing newline stripped" strips every trailing LF, for the candidate and every readback.
5. `sha256sum -c` runs in-process, same format; `SHA256SUMS` covers the run dir but itself and `.tmp/`.
6. A pin passes when the remote names, for `ref`, a commit starting with the pinned sha (7+ hex).
7. `reply_to` names where a reply is saved. A subject is `CreateAgent` with `name` the target and `description`
   the payload bytes unedited: instructions only, nothing copied from the live bot (CreateAgent takes only `name`,
   `description` and `section_id`). A seat message is the header, a blank line and the body. The header's `Body sha256` is the sha256 of
   the body that follows the header (the bytes after the blank line), not request.json's sha256. A subject gets
   `PROMPT.md` itself.
8. No tool returns a creation time, a send time or a message id, so `sent_at`, `created_at` and `done_at` are box
   time from `qualify.py now`, and a reply's `reply_at` is the platform's turn timestamp (to the minute) on the
   message that carried it. An `await_reply` receipt with no reply waits again unless its `done_at` is past the
   limit: 24 h for the Architect (stop), the Evaluator has no limit. The runner wakes only on a new message, so a
   silent seat needs the conduit's `Check run: <run>` (runner.md) for that check to run. A case reply is not
   awaited: S5 polls the subject's transcript (below).
9. What the script runs itself (pins, temp counts, `tools/selftest`, `tools/reset_fixtures`,
   `tools/check_side_effects <case>` in the suite, the seed, the summary) runs once, with `TMPDIR` set to the
   run's `.tmp`. A failed reset in S5 stops.
10. The Architect's reply gives the absolute path of `MANIFEST-<ver>.sha256` and its sha256; the suite is that
    directory; `cases.json` is a list of `{id, prompt_path, prompt_sha256, expect, window_minutes}`.
11. A seat's JSON reply is its first JSON object; `scores.json` is `{"cases": {"<id>": {"verdict", "reasons"}},
    "key_sha256"}`.
12. A key file name is a `keys/` directory or a file `KEY`, `KEY.*`, `KEY-*` or `KEY_*`. "The key's sha appears"
    means a file whose sha256 is the key's (the sha as text belongs in `review.json` and `summary.json`). S1 scans
    the suite for key file names and `deny_paths`; after S2 and at S7 the run and suite trees are scanned.
13. The deny list: `deny_paths`, the suite's `tools/`, `keys/` and KEY files, `qualify-script/run/`, this run's
    `actions/` and every other case's prompt directory. S4 scans first-run events, S5 the whole trace.
    The runner audit scans every tool input for `deny_paths` and key names. One case is not a read: a cursor
    CreateAgent or SendToAgent inside an action whose payload file holds every hit is sending the kit's own text.
    Run 6's candidate names `/workspace/.openrouter-key`, and 11 CreateAgent calls were voided for it before this
    rule. Any hit the payload does not hold still flags, as does a call outside an action and every Read, Shell
    or GetDynamicTools hit.
14. An export is JSON `{bot_id, start_of_transcript, events}`, built by `qualify.py trace` from the files
    ReadTranscript writes with `write_to_file`; the runner names each new page and the script keeps the list in
    `steps/trace-NNNN.pages.jsonl` (the current attempt's pages: a re-issue sets the list aside, "Running it"
    item 4). The real page shape (pages read 2026-11-15; a structural copy is
    `tests/fixtures/qualify/readtranscript-subject-first-run.txt`): a `<cursor_untrusted_data_1337
    source="ReadTranscript">` wrapper, no trailing newline; the header `Transcript of agent "NAME" (ID),
    positions A–B of N:` (0-based, inclusive, en dash) or `Transcript of this session, ...`; one compact JSON line
    `{role, message}` per readable message, oldest first, role `user`, `assistant` or `tool`; then `Older messages
    remain: ... before=A.` or, when A = 0, `This is the start of the transcript.`. `limit` (at most 200) counts
    positions and a page also stops near 45 KB. Not every position is readable: a top-level bot's position 0 (its
    setup) is never shown, so a page can hold fewer lines than B−A+1, and it does not say which positions it left
    out. A `before` that leaves only unreadable positions returns `No readable messages in ... before position P.`
    alone. A page counts only if its file name is the sha256 of its bytes, every line is one of these, its header
    names the target (or this session, for the runner's own), it holds at most B−A+1 lines, and it ends with the
    footer exactly when A = 0. Pages join by their header ranges: the newest ends at N−1, each older one ends at
    the next one's A−1, and none overlap. The chain is complete when it reaches A = 0, or a no-readable page
    before the lowest A. The export and `steps/trace-NNNN.json` record `unreadable_positions`, and
    `runner-audit.txt` states the runner's count as not audited. What this can no longer prove: that the
    positions not shown hold nothing the audit or the deny scan would flag. Their number is known, not their
    content or place. Events carry the turn timestamp; tool inputs and
    results over about 4000 characters arrive elided (first and last 2000), and the audit then checks the
    target and the header line instead of the full payload sha (the S3 readback proves a subject's
    instructions). `steps/trace-NNNN.json` records the export sha, which the receipt must match. A subject export
    without the footer stops the run; a runner export without it voids the audit.
15. The runner exports its own transcript as the last S5 action, since S6 sends the audit result (SPEC L140,
    L241) and the conduit cannot wake the runner after the kickoff (L67-69). Later acts are not in it; the
    conduit's full export after the run (L229) is there for the Evaluator, who may void the run.
16. The audit maps a call to an action by order, since the transcript has no per-call time: a Read of
    `actions/NNNN.intent(.K).json` opens the action and `qualify.py verify <run> NNNN` (or `stop`) closes it.
    Shell's first line must fully match one of the forms in `runner.md` (`qualify.py <command>`, `sha256sum`, a
    receipt heredoc); Read stays in the run dir, the suite and the intent's payload; GetDynamicTools only looks up
    CreateAgent, SendToAgent and ReadTranscript; the first-run turn may hold only Read and the platform's greeting
    (SendToUser); inside an action SendToUser may only send a `STOP` file verbatim. The readback is the script's own command, `python3 kit/qualify.py readback <run> NNNN`:
    it reads `actions/NNNN.intent.json`, then the `"description"` string of
    `<AGENTS_ROOT>/<target>/profile.json` (`AGENTS_ROOT = '/home/box/agent-data/agents'`, a module constant only
    tests patch), writes it verbatim (UTF-8, no added newline) to the intent's `reply_to` once via `.part`, records
    `steps/readback-NNNN.json` `{action, target, profile_path, description_sha256, read_at}` once, logs
    `readback NNNN` and prints `READBACK <reply_to> sha256 <file sha> text_sha256 <text sha>`; the receipt's
    `reply_sha256` is the printed sha256, `tools_called` is `["Shell"]` and `platform_ids` is `{}`. The
    `read_back_sha` allow-list adds nothing to every action's Shell and Read; a runner Read of agent-data voids the
    audit. It reads only the allowed target's `profile.json` (never `settings.json`, `store.db`, a key or a store).
    Refusals write no reply file and change none: (1) no intent NNNN or its kind is not `read_back_sha`: exit 2,
    usage (`REFUSED`), the run goes on; (2) `target` is not a canonical lowercase UUID; (3) `target` is neither
    `live_bot_id` nor the `bot_id` of a `create_subject` action whose latest receipt passes verification (from the
    intents and receipts, not the log); (4) the profile path falls under a `deny_paths` entry; (5) `profile.json`
    is missing or not JSON, or `description` is missing or not a string; (6) `reply_to` (or the record) already
    exists with other content (identical bytes reprint the line, exit 0). Cases 2-6 exit 3 through `STOP.md`.
    Receipt verification (every `verify` and every `next` replay) requires the record, its target and
    `sha256(reply) == description_sha256`, else a fatal runner deviation; it reads no agent-data, so a replay never
    re-reads `profile.json`. `verify NNNN` alone also re-reads `profile.json` (same target rules); a mismatch is
    recorded once in `steps/readback-NNNN.fresh.json` and rejects as fatal, and the next `next` stops with "fresh
    read at verify: ... The bot's instructions changed on the platform after qualify.py readback ran; this is a
    platform change, not a runner deviation".
17. A replacement subject is `... subject NN-r1`, listed in `SUBJECTS-<ver>.r1.txt`.
18. Verdicts: a deny-list hit voids, a timeout fails, a side-effect failure turns a pass into a fail, a case with
    no score is `not_run`. A `pass_rule` other than `all` stops at S0. The live bot is read back at S0 and S7.
19. S4 waits per subject before its scan (SPEC L110) with the five methods and the L205-216 tools only: one
    `export_trace` per subject with `not_before` = the subject's `created_at` + 10 minutes; the runner sleeps with
    `qualify.py wait` (at most 600 s a call, inside Shell's 780 s limit) until it prints `READY`
    (`replies/subject-NN.first-run.K.json`). It scans that export and logs its file (`first_run_scanned`); it
    does not stop earlier on a finished turn. A turn still
    running then is scanned as it stands, and a hit retires the subject. Later events reach the S5 case trace
    scan, where a hit voids the case. A replacement subject waits the same way.

20. S5 sends the case and then polls: an `export_trace` of the subject every 2 minutes (`not_before`) until the
    subject's first SendToAgent to the runner after its first-run turn appears (called through CallDynamicTool
    cursor or directly, with the runner's id in `agentId`, `agent_id` or `target_id`: run 5's subjects used the
    first three shapes), or the window plus 60 s has
    passed. The script writes that message as `replies/<case>.reply.md` (flagged `reply_elided` when the platform
    shortened it) and scans the last export. No reply, or one stamped after the deadline plus 60 s, is a
    `timeout`; the 60 s covers the minute-precision stamp.
21. Real tool limits the kit is held to (checked by `tests/test_qualify_dryrun.py`): CreateAgent `{name,
    description, section_id}`; SendToAgent `{target_id, message, priority}` returns no id (the runner's schema
    read on 2026-11-15; run 5's subjects sent `{agentId, message, priority}`, so every check of a SendToAgent
    target takes `agentId`, `target_id` or `agent_id`); ReadTranscript `{in,
    limit <= 200, before, around}`; Shell foreground at most 780000 ms. UpdateAgent is never allowed.

The prompt rule (SPEC L136-137: no "do not message any person or bot", name the outbox) is a suite-authoring rule:
`S1.request.md` states it, and the script does not check it (Q10).

## Coverage list (bar.md K2)

- T01: tests.test_qualify.Loop.test_intent_without_receipt_stops
- T02: tests.test_qualify.Loop.test_verified_receipt_is_not_reissued
- T03: tests.test_qualify.Loop.test_bad_receipt_sha_is_rejected
- T04: tests.test_qualify.Subjects.test_subject_sha_mismatch_stops
- T05: tests.test_qualify.Subjects.test_first_run_contamination_retires_subject, tests.test_qualify.Subjects.test_export_waits_for_first_turn_or_10_minutes
- T06: tests.test_qualify.Cases.test_deny_hit_voids_case
- T07: tests.test_qualify.Cases.test_late_notice_is_not_a_timeout, tests.test_qualify.Cases.test_reply_after_deadline_is_timeout, tests.test_qualify_dryrun.DryRun.test_silent_subject_times_out_without_stalling
- T08: tests.test_qualify.Record.test_pass_rule
- T09: tests.test_qualify.Suite.test_leak_scan_finds_key_file_name, tests.test_qualify.Cases.test_key_file_under_run_tree_fails
- T10: tests.test_qualify.Gate.test_not_ready_stops_at_s2
- T11: tests.test_qualify.Record.test_sha256sums_round_trip
- T12: tests.test_qualify.Cases.test_header_is_byte_exact
- T13: tests.test_qualify.Cases.test_no_header_goes_to_subjects
- T14: tests.test_qualify.Audit.test_unmapped_tool_call_voids_run
- T15: tests.test_qualify.Audit.test_off_list_tool_voids_run
- T16: tests.test_qualify.Audit.test_connector_namespace_voids_run
- T17: tests.test_qualify.Audit.test_first_run_send_voids_run
- T18: tests.test_qualify.Loop.test_clean_run_qualifies
- B01: tests.test_qualify.Preflight.test_candidate_sha_strips_trailing_newline
- B02: tests.test_qualify.Preflight.test_live_sha_change_stops
- B03: tests.test_qualify.Preflight.test_prior_manifest_failure_stops_before_s1
- B04: tests.test_qualify.Preflight.test_pin_mismatch_stops_before_s1
- B05: tests.test_qualify.Preflight.test_tmpdir_and_tmp_counts_recorded
- B06: tests.test_qualify.Suite.test_s1_checks_each_stop
- B07: tests.test_qualify.Suite.test_silent_architect_stops_after_24h
- B08: tests.test_qualify.Gate.test_s2_gate_checks_stop
- B09: tests.test_qualify.Subjects.test_subjects_file_in_list_order
- B10: tests.test_qualify.Subjects.test_first_run_contamination_retires_subject, tests.test_qualify.Subjects.test_two_contaminations_on_one_case_stop
- B11: tests.test_qualify.Cases.test_shuffle_seed_recorded
- B12: tests.test_qualify.Cases.test_late_notice_is_not_a_timeout
- B13: tests.test_qualify.Cases.test_s6_key_sha_mismatch_stops
- B14: tests.test_qualify.Cases.test_side_effects_fail_overrides_pass
- B15: tests.test_qualify.Loop.test_receipt_failing_twice_stops
- B16: tests.test_qualify.Cases.test_key_file_under_run_tree_fails
- B17: tests.test_qualify.Gate.test_stop_md_fields
- B18: tests.test_qualify.Record.test_log_is_append_only, tests.test_qualify.Subjects.test_first_run_contamination_retires_subject
- B19: tests.test_qualify.Record.test_intent_and_receipt_fields
- B20: tests.test_qualify.Audit.test_store_read_or_payload_change_voids
- B21: tests.test_qualify.Audit.test_export_without_footer_not_complete
- B22: tests.test_qualify.Audit.test_runner_audit_hashed_into_sums
- B23: tests.test_qualify.Record.test_summary_fields_key_by_sha_only
- B24: tests.test_qualify.Loop.test_next_and_verify_commands
- R01: tests.test_qualify.Readback.test_refuses_an_action_that_is_not_read_back_sha
- R02: tests.test_qualify.Readback.test_refuses_a_target_that_is_not_a_canonical_uuid
- R03: tests.test_qualify.Readback.test_refuses_a_target_that_is_not_live_or_a_verified_subject
- R04: tests.test_qualify.Readback.test_refuses_a_deny_listed_profile_path
- R05: tests.test_qualify.Readback.test_refuses_a_missing_or_bad_profile
- R06: tests.test_qualify.Readback.test_refuses_an_existing_reply_with_other_bytes
- R07: tests.test_qualify.Readback.test_reply_is_written_verbatim, tests.test_qualify.Loop.test_clean_run_qualifies
- R08: tests.test_qualify.Readback.test_verify_rejects_a_hand_edited_reply, tests.test_qualify.Readback.test_verify_rejects_a_reply_with_no_readback, tests.test_qualify.Readback.test_verify_rejects_a_changed_profile, tests.test_qualify.Readback.test_replay_does_not_re_read_profile
- R09: tests.test_qualify.Audit.test_runner_read_of_profile_voids
- R10: tests.test_qualify.Loop.test_readback_command_refuses
- H01: tests.test_qualify.Cases.test_header_is_byte_exact, tests.test_qualify.Cases.test_header_body_sha_is_the_body_not_request_json
- H02: tests.test_qualify.Record.test_old_header_label_is_gone
- K01 (resume after a ruled stop): tests.test_qualify_dryrun.DryRun.test_run4_stop_ruling_resume_done, tests.test_qualify_dryrun.DryRun.test_resume_refuses_without_a_stop, tests.test_qualify_dryrun.DryRun.test_script_check_stop_is_not_waived_by_a_ruling
- K02 (instructions only, real tool shapes): tests.test_qualify_dryrun.Limits.test_allowed_tools_exist_and_take_what_the_kit_sends, tests.test_qualify_dryrun.Limits.test_no_like_and_no_unreturned_platform_ids
- K03 (kickoff names the folder, S0 self-pin): tests.test_qualify_dryrun.Commands.test_s0_stops_when_the_kit_is_not_at_the_pin, tests.test_qualify.Loop.test_kickoff_holds_only_run_request_sha_and_quote
- K04 (runner commands pass the audit): tests.test_qualify_dryrun.Limits.test_runner_md_forms_pass_the_audit, tests.test_qualify_dryrun.Limits.test_wait_fits_one_shell_call, tests.test_qualify_dryrun.Commands.test_wait_sleeps_in_shell_sized_slices
- K05 (export from real pages): tests.test_qualify_dryrun.Commands.test_trace_refuses_pages_that_are_not_the_targets
- K06 (the real page header): tests.test_qualify_page_header.RealPage.test_the_real_page_shape_is_accepted_and_counted_honestly, tests.test_qualify_page_header.RealPage.test_the_check_run_5_stopped_on_refuses_this_page, tests.test_qualify_page_header.RealPage.test_what_the_page_check_still_refuses, tests.test_qualify_page_header.Paging.test_pages_join_and_unreadable_positions_are_counted, tests.test_qualify_page_header.Paging.test_a_gap_or_a_page_that_is_not_the_newest_is_refused, tests.test_qualify_page_header.Paging.test_a_no_readable_messages_page_ends_the_chain, tests.test_qualify_page_header.SimShape.test_the_simulator_emits_the_real_shape
- K07 (resume at a later kit commit): tests.test_qualify_page_header.Run5Resume.test_stop_at_0044_ruling_at_a_new_kit_commit_resume_done, tests.test_qualify_page_header.Run5Resume.test_after_the_move_next_at_the_old_commit_stops, tests.test_qualify_page_header.Run5Resume.test_resume_at_the_pin_needs_no_kit_sha
- K08 (subject replies in agentId; rescore from saved exports): tests.test_qualify_reply_agentid.ReplyKey.test_agentid_reply_is_found, tests.test_qualify_reply_agentid.ReplyKey.test_target_id_and_agent_id_still_work, tests.test_qualify_reply_agentid.ReplyKey.test_direct_sendtoagent_with_agentid_or_agent_id, tests.test_qualify_reply_agentid.ReplyKey.test_other_target_first_run_or_namespace_is_not_a_reply, tests.test_qualify_reply_agentid.ReplyKey.test_agentid_reply_on_a_real_shaped_page_short_and_elided, tests.test_qualify_reply_agentid.ReplyKey.test_payload_ok_reads_the_send_target_in_any_key, tests.test_qualify_reply_agentid.Rescore.test_stop_with_an_open_export_rescore_resume_done, tests.test_qualify_reply_agentid.Rescore.test_rescore_never_waives_a_script_check
- K09 (a plain copy of a run rehearses a resume): tests.test_qualify_reply_agentid.CopyRehearsal.test_plain_copy_resumes_like_the_original, tests.test_qualify_reply_agentid.CopyRehearsal.test_local_maps_only_paths_under_the_origin
- K10 (a re-issued export starts fresh, old pages set aside): tests.test_qualify_export_fresh.Run6Replay.test_the_second_stop_reproduces_at_the_old_kit, tests.test_qualify_export_fresh.Run6Replay.test_resume_at_the_fix_reissues_fresh_and_reaches_done, tests.test_qualify_export_fresh.SetAside.test_a_finished_attempt_moves_its_record_and_reply_too, tests.test_qualify_export_fresh.SetAside.test_nothing_kept_moves_nothing_and_logs_nothing, tests.test_qualify_export_fresh.SetAside.test_an_existing_set_aside_is_never_overwritten, tests.test_qualify_export_fresh.SetAside.test_only_export_trace_is_set_aside_on_reissue, tests.test_qualify_export_fresh.FirstAttempt.test_overlapping_pages_in_one_attempt_still_refuse
- K11 (sending the payload is not a key read; reaudit): tests.test_qualify_audit_createagent.Run6Flags.test_the_flags_reproduce_without_the_fix, tests.test_qualify_audit_createagent.Run6Flags.test_with_the_fix_the_same_run_audits_clean, tests.test_qualify_audit_createagent.StillFlags.test_createagent_sending_the_payload_passes, tests.test_qualify_audit_createagent.StillFlags.test_createagent_with_a_deny_path_the_payload_lacks_flags, tests.test_qualify_audit_createagent.StillFlags.test_a_key_name_the_payload_lacks_flags, tests.test_qualify_audit_createagent.StillFlags.test_createagent_outside_an_action_flags, tests.test_qualify_audit_createagent.StillFlags.test_reads_of_the_store_or_keys_still_flag, tests.test_qualify_audit_createagent.StillFlags.test_a_send_to_agent_naming_a_path_its_payload_lacks_flags, tests.test_qualify_audit_createagent.Reaudit.test_reaudit_at_the_fix_writes_new_files_and_rewrites_none, tests.test_qualify_audit_createagent.Reaudit.test_reaudit_refusals_change_nothing, tests.test_qualify_audit_createagent.Reaudit.test_reaudit_refuses_a_stopped_or_unfinished_run, tests.test_qualify_audit_createagent.Reaudit.test_reaudit_refuses_when_the_record_does_not_check, tests.test_qualify_audit_createagent.Reaudit.test_a_tampered_runner_export_is_refused
