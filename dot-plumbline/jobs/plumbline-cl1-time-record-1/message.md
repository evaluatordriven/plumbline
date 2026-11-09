The frozen bar is tests/test_packet_cl1_time_source.py. Run it:

    PYTHONPATH=. python3 tests/test_packet_cl1_time_source.py

It is red: Ran 6 tests, FAILED (failures=2). Two failures, both about a time that no act stamped:

  test_cl1_typed_disposition_at_is_refused
      AssertionError: 'disposition.at' not found in ''

  and the sibling case for a typed bar.approvals[].at, which likewise produces no gap.

Your editable file is kit/emit_packet.py — and only that file. The bar is your read-only reference:
read it and implement what its tests demand. Plant nothing in it.

The rule, in the bar's own words: a CL1 packet may carry role, by and barDigest on an approval, and
by and state on a disposition, but NOT a typed `at`. Times come from inputs/custody-events.jsonl —
the approve event for an approval, the dispose event for a disposition, each line stamped by its
writer. A typed time must be reported as a gap.

Rule 12 applies: the red above is what the bar reports, and the bar is the standard.

Do not edit tests/, schemas/, tools/, or kit/custody_ledger.py.
