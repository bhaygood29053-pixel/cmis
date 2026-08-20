import unittest

from liquidity_scout.providers.x1.historical_block_comparison import (
    HistoricalBlockFact,
    compare_historical_block_facts,
    extract_historical_block_fact,
)


def payload(
    slot=100,
    blockhash="hash-100",
    previous="hash-99",
    block_height=77,
    parent_slot=None,
):
    if parent_slot is None:
        parent_slot = slot - 1
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "parentSlot": parent_slot,
            "blockhash": blockhash,
            "previousBlockhash": previous,
            "blockHeight": block_height,
            "transactions": [],
        },
    }


class HistoricalBlockComparisonTests(unittest.TestCase):
    def test_exact_same_fact_agreement_is_narrow_and_non_promotional(self):
        official = extract_historical_block_fact(
            source="official-x1-rpc", requested_slot=100, payload=payload()
        )
        secondary = extract_historical_block_fact(
            source="secondary-x1-rpc", requested_slot=100, payload=payload()
        )
        result = compare_historical_block_facts(
            official, secondary, source_independence_verified=True
        )
        self.assertEqual(result.status, "AGREEMENT")
        self.assertTrue(result.same_fact_identity_verified)
        self.assertTrue(result.source_independence_verified)
        self.assertEqual(result.conflicts, ())
        self.assertFalse(result.archival_completeness_verified)
        self.assertFalse(result.retention_verified)
        self.assertFalse(result.finality_semantics_verified)
        self.assertFalse(result.cmis_promotable)

    def test_distinct_labels_without_independence_proof_stay_unknown(self):
        official = extract_historical_block_fact(
            source="official-x1-rpc", requested_slot=100, payload=payload()
        )
        secondary = extract_historical_block_fact(
            source="secondary-x1-rpc", requested_slot=100, payload=payload()
        )
        result = compare_historical_block_facts(official, secondary)
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(result.source_independence_verified)
        self.assertFalse(result.same_fact_identity_verified)

    def test_explicit_failed_independence_stays_false(self):
        official = extract_historical_block_fact(
            source="official-x1-rpc", requested_slot=100, payload=payload()
        )
        secondary = extract_historical_block_fact(
            source="secondary-x1-rpc", requested_slot=100, payload=payload()
        )
        result = compare_historical_block_facts(
            official, secondary, source_independence_verified=False
        )
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertIs(result.source_independence_verified, False)
        self.assertFalse(result.same_fact_identity_verified)

    def test_conflicting_blockhash_is_preserved(self):
        official = extract_historical_block_fact(
            source="official-x1-rpc", requested_slot=100, payload=payload()
        )
        secondary = extract_historical_block_fact(
            source="secondary-x1-rpc",
            requested_slot=100,
            payload=payload(blockhash="different"),
        )
        result = compare_historical_block_facts(
            official, secondary, source_independence_verified=True
        )
        self.assertEqual(result.status, "CONFLICT")
        self.assertIn("blockhash", result.conflicts)
        self.assertFalse(result.cmis_promotable)

    def test_same_source_is_rejected_even_when_independence_is_claimed(self):
        official = extract_historical_block_fact(
            source="x1-rpc", requested_slot=100, payload=payload()
        )
        secondary = extract_historical_block_fact(
            source="x1-rpc", requested_slot=100, payload=payload()
        )
        result = compare_historical_block_facts(
            official, secondary, source_independence_verified=True
        )
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertIs(result.source_independence_verified, False)
        self.assertFalse(result.same_fact_identity_verified)

    def test_same_source_without_external_claim_is_explicitly_non_independent(self):
        official = extract_historical_block_fact(
            source="x1-rpc", requested_slot=100, payload=payload()
        )
        secondary = extract_historical_block_fact(
            source="x1-rpc", requested_slot=100, payload=payload()
        )
        result = compare_historical_block_facts(official, secondary)
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertIs(result.source_independence_verified, False)

    def test_different_requested_slots_are_insufficient_evidence(self):
        official = extract_historical_block_fact(
            source="official", requested_slot=100, payload=payload(slot=100)
        )
        secondary = extract_historical_block_fact(
            source="secondary", requested_slot=101, payload=payload(slot=101)
        )
        result = compare_historical_block_facts(
            official, secondary, source_independence_verified=True
        )
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertFalse(result.same_fact_identity_verified)
        self.assertTrue(result.source_independence_verified)

    def test_skipped_slots_do_not_break_request_context(self):
        fact = extract_historical_block_fact(
            source="secondary",
            requested_slot=100,
            payload=payload(slot=100, parent_slot=95),
        )
        self.assertEqual(fact.requested_slot, 100)
        self.assertEqual(fact.parent_slot, 95)

    def test_extract_rejects_parent_that_does_not_precede_request(self):
        with self.assertRaisesRegex(ValueError, "precede requested_slot"):
            extract_historical_block_fact(
                source="secondary",
                requested_slot=100,
                payload=payload(slot=100, parent_slot=100),
            )

    def test_optional_block_height_absence_is_not_fabricated_conflict(self):
        official = extract_historical_block_fact(
            source="official", requested_slot=100, payload=payload(block_height=77)
        )
        secondary = extract_historical_block_fact(
            source="secondary", requested_slot=100, payload=payload(block_height=None)
        )
        result = compare_historical_block_facts(
            official, secondary, source_independence_verified=True
        )
        self.assertEqual(result.status, "AGREEMENT")
        self.assertNotIn("block_height", result.compared_fields)
        self.assertEqual(result.conflicts, ())

    def test_extract_rejects_missing_block_identity(self):
        bad = payload()
        del bad["result"]["blockhash"]
        with self.assertRaisesRegex(ValueError, "blockhash"):
            extract_historical_block_fact(
                source="secondary", requested_slot=100, payload=bad
            )

    def test_extract_rejects_null_or_error_block(self):
        with self.assertRaisesRegex(ValueError, "structurally verified"):
            extract_historical_block_fact(
                source="secondary",
                requested_slot=100,
                payload={"jsonrpc": "2.0", "id": 1, "result": None},
            )

    def test_unverified_manual_fact_is_insufficient(self):
        official = HistoricalBlockFact(
            source="official",
            requested_slot=100,
            blockhash="a",
            previous_blockhash="b",
            parent_slot=99,
            block_height=1,
            contract_verified=False,
        )
        secondary = HistoricalBlockFact(
            source="secondary",
            requested_slot=100,
            blockhash="a",
            previous_blockhash="b",
            parent_slot=99,
            block_height=1,
            contract_verified=True,
        )
        result = compare_historical_block_facts(
            official, secondary, source_independence_verified=True
        )
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertTrue(result.source_independence_verified)

    def test_none_independence_is_accepted_as_unknown(self):
        official = extract_historical_block_fact(
            source="official", requested_slot=100, payload=payload()
        )
        secondary = extract_historical_block_fact(
            source="secondary", requested_slot=100, payload=payload()
        )
        result = compare_historical_block_facts(
            official, secondary, source_independence_verified=None
        )
        self.assertIsNone(result.source_independence_verified)

    def test_independence_flag_type_safety(self):
        official = extract_historical_block_fact(
            source="official", requested_slot=100, payload=payload()
        )
        secondary = extract_historical_block_fact(
            source="secondary", requested_slot=100, payload=payload()
        )
        with self.assertRaisesRegex(TypeError, "boolean or None"):
            compare_historical_block_facts(
                official, secondary, source_independence_verified="yes"
            )

    def test_type_safety(self):
        with self.assertRaises(TypeError):
            compare_historical_block_facts("bad", "bad")


if __name__ == "__main__":
    unittest.main()
