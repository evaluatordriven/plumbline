# Iteration 3 verdict, job 2026-10-28-custody-times-ledger-spend

Batch 3, subject f95e0d3 (maker/custody-times-ledger-spend/iter3), scored by the E-DI Evaluator.
- S1 (scheck.py @ 49d3a506f6f7): 38/39 as frozen, 2026-10-29T15:45:01.964544Z to 2026-10-29T15:56:38.110831Z;
  the one frozen FAIL is T6. Every S1 control right (57/57).
- T6 under Amendment 2 (AMENDMENT-2-t6-n1-refusal.md): score 1 (custody/evidence/T6-amend2.json; frozen verdict FAIL).
- E-GLM: J1 PASS (controls_ok True); J2 PASS (controls_ok True); J3 PASS (controls_ok True); J4 PASS (controls_ok True).
- Batch: VALID (no control wrong). Every check T1-J4 scores 1 under Amendment 2: 43/43 -> terminal state accepted.

Verified by the Orchestrator (on the box, 2026-10-29 12:28-12:34 EDT). Owner disposition 2026-10-29 12:36 EDT:
"Accept the result with disclosures 1–22." Disclosures 1-24: custody/DISCLOSURES.md (1-23 accepted 13:15 EDT).
