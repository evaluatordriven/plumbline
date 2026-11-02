# Owner approval record: job 2026-10-28-custody-times-ledger-spend

Approved sheet: `OWNER-APPROVAL.md` as ratified, sha256 `e41aae4452ed52ce1d2500b5b4d036747576285350d274711df84fdfcc81fe1a`
(kept byte for byte as `OWNER-APPROVAL.e41aae44.md`; the current `OWNER-APPROVAL.md` adds item 30, see §3 item 10 and §4).
Approver: Steve Moitozo II (S2: Owner, Buyer, Specialist), in his own chat with the Orchestrator (Chief of Staff).
Recorded by the drafter from the Orchestrator's verbatim relay; this file records his words, it is not itself an approval.

## 1. Ratification — 2026-10-28 14:50 EDT, message t92u, answering card t91s517
Verbatim: "Ratified proceed"

Card t91s517's recommended options, which this ratification accepts:
- Item 29: approved as recommended (separate `kit/plumbline_verify.py`, gates close, no grandfathering).
- Item 28: add T7 to this job.
- Item 23: sidecar one last time OK; run the verifier once after merge, non-gating.
- Item 19: live-test the new spend guard.
- Time bound: keep 8 hours.
- Remaining items: approved as recommended.

## 2. Explicit confirmation — 2026-10-28 15:17 EDT, message t93u
Verbatim: "Item 29 - (A) approved as recommended; Item 28 - (B) fix it in this job; Item 23 - (A); Item 19 - (A); Time (B); Remaining - (A) approved as recommended"

Mapping to card t91s517's option order (Orchestrator's mapping, relayed):
- 29 (A) = approved as recommended.
- 28 (B) = "fix it in this job" (his words; T7 included).
- 23 (A) = sidecar one last time OK, run the verifier once after merge, non-gating.
- 19 (A) = live-test the new spend guard.
- Time (B) = keep 8 hours.
- Remaining (A) = approved as recommended.

This matches the interpretation of the 14:50 "Ratified proceed". No change to scope.

## 3. Bytes that must change before freeze (for Steve's separate digest approval)
The sheet above is approved as is. The bar and brief change as follows at freeze; these changes are listed for his
digest approval and are not covered by the approvals above:
1. `bar.md` line 3: `STATUS: DRAFT …` becomes `STATUS: FROZEN-BUILD <freeze time>`.
2. `bar.md` Time line: the placeholder becomes the clock time open + 8 h, with zone (EDT).
3. `bar.md` Maker output contract: the markers become job 1's extractor markers
   `<<<PLUMBLINE-FILE path=…>>>` / `<<<PLUMBLINE-END …>>>` / `<<<PLUMBLINE-DONE files=N>>>`
   (the draft's `=== FILE: <path> ===` does not match `extract_files.py`).
4. `bar.md` references the frozen `INTERFACE.md` (command, line-field, refusal, verifier and tools/edi interfaces the
   checks read); `INTERFACE.md` is added to the frozen set.
5. `bar.md` pins: harness sha256, ZDR snapshot endpoints and max_tokens, controls-manifest sha256, instrument shas.
6. `brief.json`: `proposed.status` (draft → approved/opened text) and the provider orders (the `<re-read …>`
   placeholders become `["deepinfra/fp8"]` and `["z-ai/fp8"]` after the pre-freeze ZDR re-read, 2026-10-28 16:30 EDT).
   As in job 1, the clock time itself is written in the frozen bar and `custody/bounds` only; the brief says "open + 8 h"
   because the packet is emitted from the brief at open, before the open time is known.
7. Interpretation disclosed in the controls README: F1 refusal detection accepts `REFUSED:` on stdout or stderr
   (base commands print on stdout; INTERFACE.md asks new refusals on stderr).
8. **Tripwire (Steve's standing rule, 2026-10-28 15:52 EDT, card t95s532, verbatim: "Adopt the tripwire: after the
   same Maker failure 3 times, stop and change the request.").** `bar.md` Cap line: "Maker calls and retries inside an
   iteration are unlimited, within the money and time bounds." becomes "limited only by the money bound, the
   clock-time bound, and the tripwire …: after the same Maker failure class 3 times in a row within an iteration, the
   Maker stops and reports to the Orchestrator so the request can be changed. A reply with `finish_reason` `length`
   and empty content is a failure class of its own: stop, don't retry. Every attempt is logged with its
   `finish_reason`." `brief.json` `proposed.maker_retries` changes to match. This narrows approved item 5 ("Maker
   retries inside an iteration are unlimited within the money and time bounds") of the approved sheet; the sheet
   itself (OWNER-APPROVAL.md, sha e41aae44…fe1a) is not edited.
9. **Harness (item 6 said "copied with only JOB_ID, BOUND_USD, RESERVE_USD and the price table changed").** To log
   `finish_reason` on every call, the job harness `or_call.py` also gains: a top-level `finish_reason` (null when no
   reply came back) and `content_empty` on every log entry, `finish_reason` in its stdout line, and exit 10 (logged,
   settled, no reply written) for `finish_reason` = `length` with empty content. 4 offline tests added (25/25 pass).
   Diff: `harness-finish-reason.diff` in the job work dir.
10. **Item 30, the Orchestrator field guide (Steve, 2026-10-28 16:03 EDT, card t96s542; §4).**
    - `OWNER-APPROVAL.md` gains row ☐ 30 and its check counts go from 37 to 43. Its sha256 changes from the ratified
      `e41aae44…fe1a` (that version is kept byte for byte as `OWNER-APPROVAL.e41aae44.md`) to the sha256 given in the
      freeze report. Items 1–29 are unchanged.
    - `bar.md`: the Scope line names item 30. Two Pins rows are added: the two Maker inputs by sha256 (prompt inputs
      only, never committed), and `freeze/instrument/fg_rules.json`. The New-files allow-list gains exactly
      `docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md`. The Maker output contract says the guide is its own request,
      separate from the code files. A new section adds S1 checks G4 (file and allow-list), G5 (status line), G6
      (anchored rule phrases) and G7 (leak scan with a denylist of his quoted phrases). J3 (G-faithful, read against the
      15:52 EDT decisions, the item-30 rules and DOCTRINE.md v0.1 @ dc61854) and J4 (G-story) are added to the J table,
      each batch with one clean and one planted held-out control.
    - `brief.json`: the path, deliverable, instrument dimensions (J3, J4), standard_ref, the check count (43), and a
      `proposed.field_guide` entry with both input paths and sha256s.
    - Frozen instrument: G4–G7 code, `fg_rules.json`, `rubric-J3.md`, `rubric-J4.md`, the J3/J4 listing and batch
      support, and a verbatim CC BY 4.0 copy of DOCTRINE.md @ dc61854 with its LICENSE (for the J3 prompt).
    - Bounds are unchanged: under US$5.00, an 8 h clock, and a cap of 3.
11. **Disclosed corrections found while live-testing (no change to what any check means).**
    - Instrument: the G1 allow-list in `scheck`/`judges` was looser than the bar's allow-list and is aligned to it
      (G1 controls re-run on the aligned code); G6 now normalizes its anchors the same way as the text; G7 fails when
      the guide is missing; F8d's price lookup TypeError is fixed (F8d re-run live).
    - Frozen-header rule (P5): `fg_rules.json` gains a first key `_status` carrying its `FROZEN-BUILD` stamp (ignored by
      the checks); the verbatim DOCTRINE.md copy and its LICENSE move to `freeze/instrument/fixtures/doctrine/`
      (third-party bytes carry no header; P5 exempts fixtures, as for the harness's recorded API replies).
    - Maker handoff tooling (not the bar): each Maker request is one part (ledger, emitter, verifier, edi, docs, guide),
      and `extract_files.py --part` accepts only that part's allow-listed paths (a subset of the bar's allow-list) and
      refuses to rewrite any fixture that exists at base. A Maker-side `run_tests.py` runs the same suite as G2.
    - Model-check batch tool (`jbatch.py`): when the harness exits 5 (no generation stats) or 10 it prints no stdout
      line, so the batch row's `finish_reason` was recorded as null; it now falls back to the harness log entry for that
      call (which always carries `finish_reason`). The harness is unchanged by this; the J3/J4 request bytes are
      identical before and after (checked by request sha256).
    - ZDR endpoints re-read before freeze (2026-10-28 16:30 EDT): same providers, prices and max_tokens (131072) as the
      14:55 EDT snapshot the harness price table cites; both snapshots are frozen.

## 4. Item 30 decided — 2026-10-28 16:03 EDT, answering card t96s542
Channel: Steve's own chat with the Orchestrator. This is relayed to the drafter by the Orchestrator, which states
that it witnessed the answer. Verbatim:
- "Item 30: the Maker writes the field guide in this job, with bar checks for it."
- "Paraphrase my words as Owner decisions; no verbatim quotes in the doc."

Scope as relayed by the Orchestrator (its wording, not his):
- The Maker writes the new file `docs/PLUMBLINE-ORCHESTRATOR-FIELD-GUIDE.md`, and nothing else, for this item.
- It merges the Owner's draft (`owner-draft.md`, sha256 `fbf070f5…e344`) with `orchestrator-guide.md`
  (sha256 `01fe4e16…7e13`). Both are given as prompt inputs only and are never committed.
- Requirements (a)–(f): a status line; the 15:52 EDT decisions; the standing rules; a story for each rule; no
  quotes, names, emails, local paths or key material; and a "carried forward" list.
- Script checks and model checks G-faithful and G-story, each with one clean and one planted held-out control,
  live-tested before freeze.
- The guide is a separate Maker request. Bounds stay as ratified.

These bar, brief and sheet changes (§3 item 10) need his digest approval before the job runs. This record is not
that approval.

## 5. Frozen digest approval (appended by APPROVE-apply.sh --apply, from Steve's own words)
Frozen bar sha256 `72e92dc7580e2447f19dfff66aaac02d8484157a6283dcfdda6c7bb2de7561c6`, MANIFEST.sha256 sha256 `acdf764b32bab5e0fa4615590714c49162cbbaecddd00c03c6d8121b59b85d98` (freeze event 2026-10-28T20:47:58Z). OWNER-APPROVAL.md at freeze: sha256 `20d5ff994e946eb938c859e928b80d116bd34f232e2b119a62d92fa9f8307c1c`.
- 2026-10-28T17:39:00-04:00 = time received by Orchestrator; card answered earlier, exact time not visible (answered between 16:50 EDT, when the card was sent, and 17:39 EDT) (card t96s548, Grok Bot chat with Chief of Staff, witnessed), S2, approves the frozen digest: "I approve bar digest 72e92dc7580e2447f19dfff66aaac02d8484157a6283dcfdda6c7bb2de7561c6 with manifest acdf764b32bab5e0fa4615590714c49162cbbaecddd00c03c6d8121b59b85d98 as Buyer and as Specialist adopting Owner sheet items 1-30 OWNER-APPROVAL.md 20d5ff99… + DOCTRINE.md v0.1 @ dc61854, including the 15:52 EDT tripwire, the harness finish_reason changes, item 30, the marker fix and the disclosed corrections; run iterations 1-3 within US$5.00 and by 2026-10-29 00:34 EDT."
  - Decision-time note (deviation): Steve answered card t96s548 at some point between 16:50 EDT (card sent) and 17:39 EDT. His answer arrived in an Orchestrator turn that was cut off, so the exact answer time is not visible; 17:39 EDT is when the Orchestrator received it. The ledger approve events carry the logging time 2026-10-28T21:41:23Z (17:41:23 EDT), not the decision time. The returned text is recorded exactly as the card gave it; it lacks the parentheses of the offered wording, and nothing else differs.
