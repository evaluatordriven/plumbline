# Job 13 — findings for the Maker (generation 1)

## The red, measured by the Orchestrator at f18c9562 with the corpus

    test_A_contradiction_is_refused_naming_both_values    FAILED   the dispose line is dropped silently
    test_C_unreadable_state_shape_is_refused_by_name      FAILED   an unreadable shape is written through
    test_B_agreement_emits_and_changes_nothing            PASSED   control
    test_A2_the_packet_and_custody_json_are_the_two_record_sources   PASSED   control
    test_D_two_real_records_with_a_disposition_block_still_emit      PASSED   control
    2 failed, 3 passed

Actual output for A: rc=0, record disposition=given, "declined" appears nowhere.
Actual output for C: rc=0, record written, terminal_state=rejected.

## Rule 12 — every known defect and its measurement

1. The dispose ledger line carries a `state` the emitter never compares to anything. `kit/emit_custody.py:1104`
   is `state = packet.get("disposition_state")`; nothing reads `ci["disposition"]["state"]` or the ledger
   line's state.
2. THE OWNER'S RULING — carry it exactly, do not re-derive it:
   - the line's `state`/`by` is NOT authoritative. `packet.disposition_state` and `ci["disposition"]` remain the
     only sources (emit_custody.py:14-15). No third source.
   - REUSE the existing `disposition.state` gap (exit 1). No new refusal kind, no corpus change, no version bump.
   - the silence ends on CONTRADICTION, not authorship:
       * a dispose line that CONTRADICTS packet.disposition_state / ci["disposition"] -> refused as a gap,
         NAMING BOTH VALUES (the line's, and the one the record would have carried). NEVER dropped with rc=0.
       * a dispose line that AGREES -> ignored, record emits, nothing changes.
       * a dispose line the emitter cannot READ AT ALL (a shape it does not recognise) -> refused by name,
         same kind.
3. **No case may require the emitter to USE the line's state.** A fix that starts treating the line's `state`
   or `by` as authority is WRONG even if the bar goes green. The record's `disposition.state` must remain the
   packet's / custody.json's value.
4. The five cases are the standard. `A` and `C` must go green; `B`, `A2`, `D` must STAY green. Do not edit
   tests/test_disposition_line_state.py or the fixture — they are frozen.

## Editable set

    kit/emit_custody.py

Nothing else. Commit is not yours — the Orchestrator commits before measuring.

## Cost

If you measured a cost, write {"amount": N} to the cost file. If you did not, do not invent it.
