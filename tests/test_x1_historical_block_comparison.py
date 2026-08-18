import unittest

from liquidity_scout.providers.x1.historical_block_comparison import (
    HistoricalBlockFact,
    compare_historical_block_facts,
    extract_historical_block_fact,
)


def payload(slot=100, blockhash="hash-100", previous="hash-99", block_height=77):
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "parentSlot": slot - 1,
            "blockhash": blockhash,
            "previousBlockhash": previous,
            "blockHeight": block_height,
            "transactions": [],
        },
    }


class HistoricalBlockComparisonTests(unittest.TestCase):
    def test_exact_same_fact_agreement_is_narrow_and_non_promotional(self):
        official = extract_historical_block_fact(source="official-x1-rpc", requested_slot=100, payload=payload())
        secondary = extract_historical_block_fact(source="secondary-x1-rpc", requested_slot=100, payload=payload())
        result = compare_historical_block_facts(official, secondary)
        self.assertEqual(result.status, "AGREEMENT")
        self.assertTrue(result.same_fact_identity_verified)
        self.assertTrue(result.source_independence_verified)
        self.assertEqual(result.conflicts, ())
        self.assertFalse(result.archival_completeness_verified)
        self.assertFalse(result.retention_verified)
        self.assertFalse(result.finality_semantics_verified)
        self.assertFalse(result.cmis_promotable)

    def test_conflicting_blockhash_is_preserved(self):
        official = extract_historical_block_fact(source="official-x1-rpc", requested_slot=100, payload=payload())
        secondary = extract_historical_block_fact(source="secondary-x1-rpc", requested_slot=100, payload=payload(blockhash="different"))
        result = compare_historical_block_facts(official, secondary)
        self.assertEqual(result.status, "CONFLICT")
        self.assertIn("blockhash", result.conflicts)
        self.assertFalse(result.cmis_promotable)

    def test_same_source_is_insufficient_evidence(self):
        official = extract_historical_block_fact(source="x1-rpc", requested_slot=100, payload=payload())
        secondary = extract_historical_block_fact(source="x1-rpc", requested_slot=100, payload=payload())
        result = compare_historical_block_facts(official, secondary)
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertFalse(result.source_independence_verified)
        self.assertFalse(result.same_fact_identity_verified)

    def test_different_requested_slots_are_insufficient_evidence(self):
        official = extract_historical_block_fact(source="official", requested_slot=100, payload=payload(slot=100))
        secondary = extract_historical_block_fact(source="secondary", requested_slot=101, payload=payload(slot=101))
        result = compare_historical_block_facts(official, secondary)
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")
        self.assertFalse(result.same_fact_identity_verified)

    def test_extract_rejects_wrong_slot_binding(self):
        with self.assertRaisesRegex(ValueError, "requested_slot"):
            extract_historical_block_fact(source="secondary", requested_slot=101, payload=payload(slot=100))

    def test_extract_rejects_missing_block_identity(self):
        bad = payload()
        del bad["result"]["blockhash"]
        with self.assertRaisesRegex(ValueError, "blockhash"):
            extract_historical_block_fact(source="secondary", requested_slot=100, payload=bad)

    def test_extract_rejects_null_or_error_block(self):
        with self.assertRaisesRegex(ValueError, "structurally verified"):
            extract_historical_block_fact(source="secondary", requested_slot=100, payload={"jsonrpc": "2.0", "id": 1, "result": None})

    def test_unverified_manual_fact_is_insufficient(self):
        official = HistoricalBlockFact(source="official", requested_slot=100, blockhash="a", previous_blockhash="b", parent_slot=99, block_height=1, contract_verified=False)
        secondary = HistoricalBlockFact(source="secondary", requested_slot=100, blockhash="a", previous_blockhash="b", parent_slot=99, block_height=1, contract_verified=True)
        result = compare_historical_block_facts(official, secondary)
        self.assertEqual(result.status, "INSUFFICIENT_EVIDENCE")

    def test_type_safety(self):
        with self.assertRaises(TypeError):
            compare_historical_block_facts("bad", "bad")


if __name__ == "__main__":
    unittest.main()
