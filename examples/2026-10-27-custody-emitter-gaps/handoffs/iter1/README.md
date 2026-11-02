# iter1 inputs
- `maker-messages.json` (sha256 `fbe8215d…1bd2`): the Maker's call-1 prompt for generations 1 and 2 (unified-diff
  OUTPUT CONTRACT). It was built by `../build_maker_messages.py` as of commit 3db8413. The current script builds the
  gen-3 prompt; to reproduce this file, run the script from 3db8413.
- `maker-messages-gen3.json` (sha256 `10193b5c…bb57`): the call-1 prompt for generation 3 (whole-file OUTPUT
  CONTRACT, DECISIONS D6), built by the current `../build_maker_messages.py`. The user content is identical to
  the gen-1 prompt except the final line ("Return your files now…").
- Both prompts are built from: the frozen bar (N1-N9 rows and the operator rule); custody SPEC CL1-9/CL1-15
  (verbatim, @3e3ca58); source files at base `ff350e3` (kit/emit_custody.py, kit/custody_history.py,
  kit/custody_ledger.py, tools/pack_stranger_bundle.py, docs/custody-emission.md, two fixture READMEs); and the
  frozen harness `or_call.py`. Neither contains any held-out control or fixture.
- `MANIFEST.sha256`: digests of every handoff file.
