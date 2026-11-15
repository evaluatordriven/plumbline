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
`S2.request.md` and `S6.request.md` (Evaluator), `kickoff.md` (the conduit's one message) and `header.txt` (the
script-issued header). Suites, keys and runs stay out of this repository.

1. The conduit writes `runs/<ver>/<date>-runN/request.json`, creates `Qualify Runner (<ver>, run N)` with
   `runner.md` as its instructions, reads them back, records `runner`, and sends `qualify.py kickoff <run>`.
2. The runner loops: `python3 kit/qualify.py next <run>` prints an action file; it performs that action, writes
   `actions/NNNN.receipt.json` and runs `python3 kit/qualify.py verify <run> NNNN`.
3. At the end `next` prints `STOP <run>/STOP.md` or `DONE <run>/summary.json`, which the runner sends to Steve
   verbatim. `qualify.py stop <run> "<reason>"` records a stop the runner saw. Exit: 0 action or DONE, 3 STOP,
   4 rejected receipt, 2 usage.

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
`log.jsonl` has one line per event (`at` with zone, `stage`, `action`, `payload_sha256`, `event`).
`actions/NNNN.intent.json` holds `{kind, target, payload_path, payload_sha256, allowed_tools}` (plus `reply_to`,
`like`); `actions/NNNN.payload.md` a seat message; `actions/NNNN.receipt.json` `{action_id, done_at,
platform_ids, reply_verbatim_path, reply_sha256, tools_called, sent_unedited: true}`. When `next` replays, a
verified receipt is passed over, an intent with no receipt stops (never resend blind), and neither means act.
`replies/` keeps every reply, readback and export verbatim; `steps/<name>.json` what the script ran itself, once.
Then `S1.checks.txt`, `review.json`, `SUBJECTS-<ver>.txt` (case, subject, bot id, list order), `scores.json`,
`runner-audit.txt`, `summary.json` and `SHA256SUMS`, or `STOP.md` (stage, failing check, evidence path and
sha256, what was not done, seat words verbatim).

Key custody: the key lives only in the Evaluator's own store, never under `/workspace` and never in the script's
inputs, outputs or logs. The script knows only its sha256. The runner, the conduit and the subjects never read
the key or a store; the deny list and the runner audit enforce this.

## Decisions where the spec is silent

1. Commands beyond `next` and `verify`: `kickoff` and `stop`.
2. A receipt that fails verification is `REJECTED`; the runner may correct it once as `NNNN.receipt.2.json` with
   `"supersedes"`; a second failure stops. An off-list tool in `tools_called`, `sent_unedited` not true or an
   edited payload is a runner deviation and stops at once.
3. `request.json` adds `ver`, `seats`, `deny_paths` (Q7 (a): the repo holds the rule and generic patterns, the
   box paths come from here) and `known_defects` (S1, SPEC L80).
4. "Trailing newline stripped" strips every trailing LF, for the candidate and every readback.
5. `sha256sum -c` runs in-process, same format; `SHA256SUMS` covers the run dir but itself and `.tmp/`.
6. A pin passes when the remote names, for `ref`, a commit starting with the pinned sha (7+ hex).
7. `reply_to` names where a reply is saved; `like` names the live bot whose bounds, teammates and skill a subject
   copies. A seat message is the header, a blank line and the body ("Request sha256" is the body's). A subject
   gets `PROMPT.md` itself.
8. Times are platform times from receipts (`sent_at`, `reply_at`, `done_at`). An `await_reply` receipt with no
   reply waits again unless its `done_at` is past the limit: 24 h for the Architect (stop), the window for a case
   (`timeout`). The Evaluator has no limit.
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
14. An export is JSON `{bot_id, start_of_transcript, events}` (shape in `runner.md`). A subject export without
    the footer stops the run; a runner export without it voids the audit.
15. The runner exports its own transcript as the last S5 action, since S6 sends the audit result (SPEC L140,
    L241) and the conduit cannot wake the runner after the kickoff (L67-69). Later acts are not in it; the
    conduit's full export after the run (L229) is there for the Evaluator, who may void the run.
16. The audit maps a call to the action whose window (intent logged to receipt `done_at`) holds it. Shell may
    only run `kit/qualify.py`, `sha256sum` or write a receipt; Read stays in the run dir and suite; the first-run
    turn may hold only Read. The readback tool is `cursor.GetAgent` (SPEC names none).
17. A replacement subject is `... subject NN-r1`, listed in `SUBJECTS-<ver>.r1.txt`.
18. Verdicts: a deny-list hit voids, a timeout fails, a side-effect failure turns a pass into a fail, a case with
    no score is `not_run`. A `pass_rule` other than `all` stops at S0. The live bot is read back at S0 and S7.
19. S4 waits per subject before its scan (SPEC L110) with the five methods and the L205-216 tools only: it repeats
    `export_trace` (cursor ReadTranscript) for the subject, each export its own action and reply file
    (`replies/subject-NN.first-run.K.json`), until an export receipt's `done_at` is 10 minutes or more after the
    subject's `created_at` (the platform creation time from the `create_subject` receipt). It scans that last
    export only and logs its file (`first_run_scanned`); it does not stop earlier on a finished turn. A turn still
    running then is scanned as it stands, and a hit retires the subject. Later events reach the S5 case trace
    scan, where a hit voids the case. A replacement subject waits the same way.

The prompt rule (SPEC L136-137: no "do not message any person or bot", name the outbox) is a suite-authoring rule:
`S1.request.md` states it, and the script does not check it (Q10).

## Coverage list (bar.md K2)

- T01: tests.test_qualify.Loop.test_intent_without_receipt_stops
- T02: tests.test_qualify.Loop.test_verified_receipt_is_not_reissued
- T03: tests.test_qualify.Loop.test_bad_receipt_sha_is_rejected
- T04: tests.test_qualify.Subjects.test_subject_sha_mismatch_stops
- T05: tests.test_qualify.Subjects.test_first_run_contamination_retires_subject, tests.test_qualify.Subjects.test_export_waits_for_first_turn_or_10_minutes
- T06: tests.test_qualify.Cases.test_deny_hit_voids_case
- T07: tests.test_qualify.Cases.test_late_notice_is_not_a_timeout, tests.test_qualify.Cases.test_reply_after_deadline_is_timeout
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
