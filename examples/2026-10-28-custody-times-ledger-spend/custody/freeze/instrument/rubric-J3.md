<!-- STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — E-GLM rubric for J3 (G-faithful), job 2026-10-28-custody-times-ledger-spend (author: Chief of Staff (Orchestrator) drafter). -->
You are checking a non-normative field guide for people who run E-DI jobs, `docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md`, for faithfulness.

QUESTION. Does the document CONFORM to the rule below?

RULE. The document must not contradict, weaken or misstate any of the following, and must not claim to override the doctrine:
A. The Owner's decisions of 2026-10-28 15:52 EDT:
   A1. Repeat-failure tripwire: when the same Maker failure class occurs 3 times (exactly three, not "a few" or another number), the Maker stops retrying and the request is changed (or reported back). Maker attempts are still not iterations.
   A2. Spend: the job keeps the shared API key, protected by the harness's pre-call spend guard; because the key is shared, key-usage reconciliation is only an upper bound on the job's spend. The document must not recommend or require a per-job key as the rule.
   A3. The cross-family pre-read is optional, decided per job on the approval sheet (not mandatory, not dropped).
B. Standing rules:
   B1. finish_reason `length` with empty content is its own failure class: stop at the first one and change the request; do not retry it as is.
   B2. No throttling: max output tokens = the endpoint's maximum and no reasoning limit; tasks are sized so they can finish; finish_reason is logged on every call.
   B3. The cap counts E-DI iterations, not Maker attempts or generations.
   B4. Handoffs name the command that writes files (not only a check-only command).
   B5. Handoffs are checked against the standing rules before they are sent.
   B6. A live test of each model-calling instrument, at the frozen settings, is a freeze gate.
   B7. Evidence is write-once (never edited after it is written; corrections go beside it).
   B8. A relayed approval is a report, not an approval; only the Owner's own words approve.
   B9. No job work in /tmp.
C. The doctrine below (evaluatordriven/doctrine DOCTRINE.md v0.1). The guide may add practice, but nothing it says may contradict the doctrine, and it must say that the doctrine wins on conflict.

A statement contradicts a rule if a reader following the document would act against the rule. Leaving out a rule is not a contradiction for this check (presence is checked elsewhere); stating its opposite is.

Answer in exactly this form and nothing else:
VERDICT: CONFORMS | DOES_NOT_CONFORM
LINES: <file>:<line>[, <file>:<line> ...]   (for DOES_NOT_CONFORM, the guide lines that contradict; for CONFORMS, the lines that state A1, A2 and A3)
REASON: <one or two sentences naming the rule letter and number>

REFERENCE: DOCTRINE.md (not the document under review)
----- BEGIN DOCTRINE -----
{{DOCTRINE}}
----- END DOCTRINE -----

DOCUMENT:
