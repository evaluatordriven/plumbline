# SYNTHETIC FAILURE FIXTURES — invented, not copied from any real job

Each folder is an OVERLAY on `../job-rejected` (the clean synthetic fixture): `tests/validate_schemas.py` copies
`job-rejected`, copies the overlay's files over it, and expects `kit/emit_custody.py` to REFUSE (exit 3) and write
nothing (except `routing-unpinned`, below). Each carries one kind of defect, modeled on a failure seen in real custody runs (2026-10-27) but written
from scratch with invented names, hosts and times:

| overlay           | the defect                                                                                  | refusal kinds          |
|-------------------|---------------------------------------------------------------------------------------------|------------------------|
| `hand-times`      | startedAt/producedAt/pass time typed to the minute, minutes off the harness log; the        | `time`, `order`        |
|                   | specialist approval typed after the maker's first call                                       |                        |
| `after-emit`      | an approval and the disposition dated 2099; a control call logged after the job's close     | `after-emit`, `order`  |
| `router-endpoint` | vendor hosts typed in; the logs show every call went via an aggregator: the maker's served  | `endpoint`             |
|                   | by a provider other than its pin (DeepInfra), the evaluator with no pin declared at all      |                        |
| `pin-fallback`    | maker pinned to DeepInfra; the log shows Together served the call (a fallback)               | `endpoint`             |
| `pin-provider-missing` | maker pinned; the log names no serving provider (no `provider`, metadata or generation) | `endpoint`             |
| `pin-late`        | the maker's pin event logged at 11:05, after its first call at 11:00 (and differing from    | `order`, `time`        |
|                   | the declaredAt typed into custody.json)                                                     |                        |
| `routing-unpinned`| NOT a refusal: the request's `provider.order` lists two slugs with no `allow_fallbacks:false`| exit 1, hard gap       |
|                   | and no ZDR. The record is written with gap `routing.maker.request`                           | `routing.maker.request`|
| `agent-approval`  | the orchestrating agent recorded as the Specialist, `adopted: null`                         | `approval`             |

The dirty-tree and revision-mismatch refusals need a git checkout, not a job folder; the test builds them in a
throwaway clean copy of the tree.
