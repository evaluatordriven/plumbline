<!-- STATUS: FROZEN-BUILD 2026-10-28T20:36:28Z — E-GLM rubric for J4 (G-story), job 2026-10-28-custody-times-ledger-spend (author: Chief of Staff (Orchestrator) drafter). -->
You are checking a field guide for people who run E-DI jobs, `docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md`, for its field-guide form.

QUESTION. Does the document CONFORM to the rule below?

RULE. Every one of the rules listed here that the document states must be paired with its real story: a concrete incident from a real job or review (what happened, and what it cost or showed), placed with the rule (directly under it or in the same item). A bare reason, a hypothetical ("if you did X, Y could happen"), or a pointer elsewhere is not a story. The rules:
1. the repeat-failure tripwire (same failure class 3 times, then change the request);
2. the shared key behind the harness pre-call spend guard, with key-usage reconciliation as an upper bound;
3. the cross-family pre-read, optional and decided per job on the approval sheet;
4. finish_reason `length` with empty content as its own failure class (stop at the first one);
5. no throttling (endpoint maximum, no reasoning limit), sized tasks, finish_reason logged;
6. the cap counts E-DI iterations;
7. handoffs name the command that writes files;
8. check handoffs against standing rules;
9. a live test of each model instrument is a freeze gate;
10. write-once evidence;
11. relayed approvals are not approvals;
12. no /tmp.
The document CONFORMS if each of these rules that appears in it has its own story with it. One story may serve two rules only if it is told with both.

Answer in exactly this form and nothing else:
VERDICT: CONFORMS | DOES_NOT_CONFORM
LINES: <file>:<line>[, <file>:<line> ...]   (for DOES_NOT_CONFORM, the line of each rule that has no story; for CONFORMS, the line of each rule)
REASON: <one or two sentences naming the rule numbers>

DOCUMENT:
