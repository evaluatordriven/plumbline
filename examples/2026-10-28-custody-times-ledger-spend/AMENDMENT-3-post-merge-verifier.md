# Amendment 3 (post-close, Owner): the post-merge, non-gating verifier run on this job's own record, job 2026-10-28-custody-times-ledger-spend

| Field | Value |
|---|---|
| Decided by | Steve Moitozo II (Owner, Buyer, Specialist-adopter), acting as Owner |
| Pre-commitment | custody/bar.md lines 145–157 ("Own record and the new verifier (item 29, effect on item 23)"): after the merge, the merged verifier is run once on this job's record **post hoc and non-gating**; expected result **exit 4** (`schema`); the result is filed as an amendment beside the frozen set. Echoed in custody/x-plumbline.json `post_merge_verifier`. |
| Filing approval words, verbatim | "You can get that done" |
| Filing approval when / channel | 2026-10-31, at or before 14:52 EDT (America/New_York, UTC-4) = 18:52Z. Steve's message in the Grok Bot chat with Chief of Staff (Orchestrator), answering the Orchestrator's proposal to file this amendment after an outside review of main @ `5c7a1c5` found it missing. Witnessed by the Orchestrator; relayed word for word to the helper that ran the check and filed this file, which did not witness it. No message id relayed; seconds not relayed. |
| Amends | Nothing about the disposition. It files the result the bar promised and was not filed at close. It does not change the frozen bytes, the record, the sidecar or the ledger. |
| Frozen set | This amendment is not in the frozen set. custody/bar.md (sha256 `72e92dc7580e2447f19dfff66aaac02d8484157a6283dcfdda6c7bb2de7561c6`), custody/MANIFEST.sha256 (`acdf764b32bab5e0fa4615590714c49162cbbaecddd00c03c6d8121b59b85d98`) and every MANIFEST-listed file are unchanged; `(cd custody && sha256sum --quiet -c MANIFEST.sha256)` is silent (re-run at filing). custody/record.custody.json (`d7dc783a54b58c47569bc265432ad613e6c8801389a2db31fc59a2366f792f6e`) and inputs/custody-events.jsonl (`b8b4723c38ce647561a296525256333b2bb9598fc20db6c257ee1ac562a7cef2`) are unchanged. |

## Why
The bar stated in advance that this job's own record, emitted by base tooling @ `3df1ce5`, would be refused by the
verifier the job built: base tooling writes no `x-plumbline.schema` and no `x-plumbline.hand_times`, and the
Plumbline-only facts went to the sidecar custody/x-plumbline.json instead. The run is a live check that the
verifier refuses a real legacy record. The job closed accepted on 2026-10-29; the run was not filed then.

## The run (2026-10-31 14:53:24 EDT = 2026-10-31T18:53:24Z, no model calls)
- **Verifier:** `kit/plumbline_verify.py` from smoitozo/plumbline main @ `5c7a1c50c72abe191479fb3f2e503f6c5e34c2f6`
  (file sha256 `e82192a153693ad5be9d37157ef2fad56844f7c95239e42cee7c3851ee5ae6f5`; schema
  `schemas/x-plumbline/x-plumbline-v1.schema.json` sha256
  `548e09eb1e8d5dfe67ccf1e8735d145dcd097f1deed81134a21eb5f8aa9b5d86`). The verifier as it stood at `912828a`
  (sha256 `052b408341233ee7ecb827ec27ed1f1b1a95f2e3ba848f117586ebe61d833dbb`) gives the same exit and the same
  five lines.
- **Custody:** a checkout of evaluatordriven/custody @ `3e3ca58de5631bdc58291564303a2e9d25a8653e`, clean;
  `checker/check.py` sha256 `aaeb7e0532c950ee1736207b0a91ff9d810533fccecdb2c7708312408e5bcd18`, which is the pin in
  tools/pin.json.
- **Subject (`--files`):** `git archive 912828a` (the job branch tip, `912828ac3af78de13661f8b6328cbf0a9f4c0e35`,
  tree `875670fff86945ce4ac6e58c04a46e2dc9ecd351`) extracted to an empty directory. Those are the bytes the record's
  subject digests name.
- **Command** (from the repository root; `J=dot-plumbline/jobs/2026-10-28-custody-times-ledger-spend`):

      python3 kit/plumbline_verify.py --record $J/custody/record.custody.json \
        --files <git archive 912828a> --evidence $J/custody/evidence \
        --ledger $J/inputs/custody-events.jsonl --custody <custody @ 3e3ca58> --json <out>

- **Result: exit 4.** The standard layer passed (custody's check.py, CL1, with the job's bar). Plumbline's layer
  failed with kind `schema` only. stdout, exactly (`<repo>` is the checkout the verifier ran from):

      FAIL schema $.predicate.x-plumbline.schema <repo>/schemas/x-plumbline/x-plumbline-v1.schema.json:0
      FAIL schema $.predicate.x-plumbline.hand_times <repo>/schemas/x-plumbline/x-plumbline-v1.schema.json:0
      FAIL schema x-plumbline.schema <repo>/schemas/x-plumbline/x-plumbline-v1.schema.json:0
      FAIL schema x-plumbline.hand_times <repo>/schemas/x-plumbline/x-plumbline-v1.schema.json:0
      FAIL schema x-plumbline.schema dot-plumbline/jobs/2026-10-28-custody-times-ledger-spend/custody/record.custody.json:0

  stderr was empty.
- **Against the prediction:** it matches. The bar predicted exit 4, kind `schema`, because base tooling writes no
  `x-plumbline.schema`; the missing `hand_times` is the same cause. The bar also named the hand-appended ledger
  lines' missing allowance; no `allowance` line is printed because the verifier stops after schema failures
  (kit/plumbline_verify.py @ `5c7a1c5`, lines 952–954: exit 4 before any later kind is checked), so that check is
  not reached. Nothing about the disposition depends on this run.
- **Against main instead (one line):** with `--files` at the repository root of main @ `5c7a1c5` the same command
  exits 3 (`CL1-14 FAILED: docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md does not match its subject digest`); that is
  expected, because the field guide is in this record's subject and has changed five times since `912828a`, and a
  record binds the bytes its job produced, not later ones.

## Raw output (kept out of the job folder)
As with Amendment 2, the run's files live on the Orchestrator's box in
`/workspace/edi-work/2026-10-28-custody-times-ledger-spend/amendment-3/` and are not in this repository. sha256:
- `verify-912828a.stdout`: `84fe2c5c27bad65076802f624ae1c7894d9dd15a5f98fdb9dc31c854f4f27c1e`
- `verify-912828a.json` (`--json`): `bf63e2320fc7bdba3695402c899e7a68ce69374e121453e012c971dad9260e42`
- `verify-912828a.exit` (`4`): `7de1555df0c2700329e815b93b32c571c3ea54dc967b89e81ab73b9972b72d1d`
- `verify-912828a.stderr` (empty): `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `verify-main.stdout`: `3a80fdf2c29a2a5763bbb2395c5a08ec2cce0360a537b400e2e41d3a28952cf0`
- `verify-main.json`: `02f59c9c7c825a11bbec4e5a055ead841008af5d7901b85200bf3a506ad59b36`
- `verify-main.exit` (`3`): `1121cfccd5913f0a63fec40a6ffd44ea64f9dc135c66634ba001d10bcf4302a2`
- `verify-main.stderr` (empty): `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- `run-at-utc.txt` (`2026-10-31T18:53:24Z`): `fcf7e24c31bbbcd4a4893d83db405dd9b661a873f58443512255479356010cd1`

The stdout and json files carry the absolute path of the checkout the verifier ran from, which the quote above
replaces with `<repo>`; nothing else differs.

## Ledger
**No ledger line is appended**, unlike Amendments 1 and 2. This amendment is filed after the close, and the filing
is additions only: no existing file of this job is changed, the ledger included. The ledger stays at sha256
`b8b4723c38ce647561a296525256333b2bb9598fc20db6c257ee1ac562a7cef2` (the record's `x-plumbline.events_log` and the
sidecar's `ledger_sha256_after_import` name earlier states of it, as at their writing; neither is touched). This
file is the only filing.

## Unchanged
The disposition (closed accepted), every check, threshold, control, pin, seat, the frozen set, the record, the
sidecar, DISCLOSURES.md and the ledger.
