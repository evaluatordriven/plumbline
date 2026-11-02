ITERATION 2, part guide: two rules the Owner added (Owner decision, 2026-10-29 07:50 EDT)

These are additions. They do not replace anything above: keep all of your iteration-1 guide as shown, and still make
the Item G1 change (the line-27 rule "The cap counts E-DI iterations" gets its own *Story:* sub-item with the real
"cap 3 generations" incident; keep the line-33 item and its story). Keep the status line, every required rule and the
"Carried forward" section.

Add the two rules below to section 4 ("Running the loop"), each as a bold rule line with its own *Story:* sub-item
placed with it, in the same field-guide style as the rest of the guide. Write them in your own words from the facts
given here; use only these facts for the two stories and invent nothing. Paraphrase Owner decisions as Owner
decisions: no verbatim quotes of the Owner, no personal names, no email addresses, no absolute local paths, and no
commit hashes are needed.

Rule A. The best artifact is the input.
  Rule to state: once the job has produced an artifact, the next iteration's Maker is given the best artifact the job
  has produced (best, not merely the one standing), together with every known defect in it and every known workable
  solution with the measurement behind it. The standing artifact is the frontier; the best artifact is the input.
  Before that Maker call, run the e-di tool `tools/check_best_artifact_handoff.py`; it must exit 0, and a pass is
  not acceptance. Then check the built request itself: the messages that will be sent must contain the best artifact,
  byte for byte. Source: e-di Instrument rule 12 (I24); the doctrine's "carry the best work forward" (rule 9 above).
  Facts for the story (this job, iteration 2):
  - Before iteration 2, the best-artifact check passed: it recorded the iteration-1 head as the best artifact and
    accepted it as the Maker's input. That check works on the artifact, not on the request that is sent.
  - The guide part's feedback told the Maker that its iteration-1 guide was shown above and should be kept, but the
    request builder for the guide part never included the current guide. The Maker, never shown it, wrote a new guide
    from the two drafts.
  - That new guide dropped about nine accepted iteration-1 items, among them: close from a clean base checkout;
    run time versus decision time; digest the controls in place; the "E-DI Maker" author identity; and the
    **[added]** markers.
  - The Orchestrator found it by comparing the new guide with the iteration-1 guide. The fix was a pinned step that
    puts the iteration-1 guide into the request verbatim, with the built messages checked to contain it byte for byte
    before the call, and the guide part was requested again.

Rule B. Keep finished parts.
  Rule to state (Owner rule of 2026-10-28 19:00 EDT, reaffirmed by the Owner on 2026-10-29 07:42 EDT): after an
  interruption or a failed iteration, the Maker never throws away completed, acceptable work. Finished part commits
  are kept; only the unfinished or failing parts are resumed or redone, as new commits on top. No reset.
  Facts for the story (this job):
  - Iteration 1: the verifier part's first call was interrupted: no exit code, no reply and no harness-log entry.
    It was ruled LOST, which is not a failure class and does not count toward the tripwire. The ledger and emitter
    commits already made were kept, and the Maker resumed at the verifier part only: attempt 2, with byte-identical
    messages, after the Owner's own yes in the Maker's chat. It succeeded and the remaining parts followed.
  - Iteration 2: the ledger, emitter, verifier and docs parts passed and were kept as they were. Only the guide part
    was redone (see Rule A's story), as a new commit on top of the existing ones, with no reset of the branch.
