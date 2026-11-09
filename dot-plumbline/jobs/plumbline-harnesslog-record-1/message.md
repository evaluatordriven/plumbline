The frozen bar is tests/test_evaluator_harness_log.py. Run it:

    python3 tests/test_evaluator_harness_log.py

It is red: Ran 12 tests, FAILED (failures=2). Ten pass. Two fail, and both are the capability:

  D4 test_d4_record_check_time_comes_from_the_log -- the emitter writes a record with 0 checks and
     "note x-plumbline.verdict: no §5 record in the job". No check time is taken from the harness log.
  D8 test_d8_reversed_times_refused_naming_the_entry -- handed a log whose received_at precedes sent_at, the
     emitter writes a record anyway and says "note external: no harness log (CL1-15) for model evaluator".
     It must REFUSE and name the entry.

YOUR EDITABLE SET -- exactly two files, both inside this worktree, both in the dispatch `files` list:

  kit/evaluator_harness_log.py   (new: the module that gives the emitter one reading of a harness log)
  kit/emit_custody.py            (existing: use it, and refuse instead of noting)

WHAT IS NOT YOURS -- a declared deployment step, deliberately out of your reach:

  /home/jarbis1/.hermes/profiles/plumbline-conductor/bin/route-eval

  That is the profile-side route. It is outside this worktree, run-aider refuses absolute paths, and the bar
  already declares it a deployment step. Do NOT try to edit it, do not shell out to it, and do not write to the
  profile directory. The Orchestrator performs that wiring and records it separately. You build the in-repo
  module the route will call.

WHAT THE BAR ENCODES:

  - a real evaluator call writes one log entry per call carrying sent_at, received_at, the model and the endpoint
    actually used (or_call.py already writes these -- or_call.py:553-559, 577; its log is a JSON LIST, not JSONL,
    append_entry at 255-271);
  - the custody record's check times come FROM that log, and the record names the log path;
  - a MODEL evaluator with no harness log REFUSES the record -- it must not degrade to a note and write anyway;
  - a log that is malformed, partial, or has received_at before sent_at REFUSES, naming the offending entry;
  - a DETERMINISTIC evaluator carrying no log is NOT refused -- keep the refusal narrow, or it can be satisfied
    by refusing everything.

Rule 12 applies: the red above is what the bar reports, and the bar is the standard.

Do not edit tests/, schemas/, tools/, kit/conductor_loop.py, kit/custody_ledger.py, or any other file.
