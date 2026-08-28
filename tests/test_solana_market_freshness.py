import unittest

from liquidity_scout.providers.solana.market_freshness import (
    DEXSCREENER_SCHEMA_PROVENANCE,
    JUPITER_BLOCK_ID_PROVENANCE,
    build_solana_market_freshness_evidence,
)

MINT = "Mint111"


def jupiter(**overrides):
    record = {
        "chain": "solana",
        "source": "jupiter_price_v3",
        "mint": MINT,
        "price_available": True,
        "usd_price": "1.25",
        "block_id": 2000,
        "token_created_at": "2024-01-01T00:00:00Z",
        "collection_started_at_unix": 2100.0,
        "collection_completed_at_unix": 2101.0,
        "collection_time_verified": True,
        "freshness_verified": False,
    }
    record.update(overrides)
    return record


def dex(**overrides):
    record = {
        "chain": "solana",
        "source": "dexscreener_token_pairs_v1",
        "mint": MINT,
        "pairs_available": True,
        "pairs": [
            {
                "pair_address": "PairA",
                "pair_created_at_ms": 1700000000000,
            }
        ],
        "collection_started_at_unix": 2101.0,
        "collection_completed_at_unix": 2102.0,
        "collection_time_verified": True,
        "freshness_verified": False,
    }
    record.update(overrides)
    return record


def block_time(block_id=2000, timestamp=2000):
    return {
        "chain": "solana",
        "source": "solana_rpc",
        "method": "getBlockTime",
        "block_id": block_id,
        "block_time_available": True,
        "block_time_unix": timestamp,
        "block_time_verified": True,
        "finality_verified": False,
    }


def reference_slot(slot=2010, commitment="confirmed"):
    return {
        "chain": "solana",
        "source": "solana_rpc",
        "method": "getSlot",
        "slot": slot,
        "commitment": commitment,
        "slot_verified": True,
    }


class SolanaMarketFreshnessTests(unittest.TestCase):
    def test_jupiter_block_time_is_fact_time_candidate_not_freshness_promotion(self):
        result = build_solana_market_freshness_evidence(
            jupiter(),
            dex(),
            block_time_record=block_time(),
            reference_slot_record=reference_slot(),
        )

        self.assertTrue(result["identity_verified"])
        self.assertTrue(result["jupiter"]["block_id_semantics_verified"])
        self.assertEqual(
            result["jupiter"]["block_id_semantics_provenance"],
            JUPITER_BLOCK_ID_PROVENANCE,
        )
        self.assertTrue(result["jupiter"]["chain_block_identity_verified"])
        self.assertTrue(result["jupiter"]["provider_fact_time_verified"])
        self.assertEqual(result["jupiter"]["provider_fact_time_unix"], 2000)
        self.assertTrue(result["jupiter"]["fact_age_computable"])
        self.assertEqual(result["jupiter"]["fact_age_seconds_candidate"], 101.0)
        self.assertEqual(result["jupiter"]["reference_commitment"], "confirmed")
        self.assertTrue(result["jupiter"]["block_at_or_before_reference_slot"])
        self.assertFalse(result["jupiter"]["finality_verified"])

        self.assertFalse(result["freshness_policy_complete"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["current_price_promotable"])
        self.assertIsNone(result["max_age_seconds"])
        self.assertIsNone(result["max_future_skew_seconds"])

    def test_token_and_pair_creation_times_are_never_used_for_freshness(self):
        result = build_solana_market_freshness_evidence(
            jupiter(),
            dex(),
            block_time_record=block_time(),
            reference_slot_record=reference_slot(),
        )

        self.assertFalse(result["jupiter"]["token_created_at_used_for_freshness"])
        self.assertFalse(result["dexscreener"]["pair_created_at_used_for_freshness"])
        self.assertFalse(
            result["dexscreener"]["market_fact_timestamp_semantics_verified"]
        )
        self.assertFalse(result["dexscreener"]["provider_fact_time_verified"])
        self.assertIsNone(result["dexscreener"]["provider_fact_time_unix"])
        self.assertEqual(
            result["dexscreener"]["schema_provenance"],
            DEXSCREENER_SCHEMA_PROVENANCE,
        )
        self.assertIn(
            "dexscreener_market_fact_timestamp_unavailable",
            result["limitations"],
        )

    def test_block_time_mismatch_fails_closed(self):
        result = build_solana_market_freshness_evidence(
            jupiter(),
            dex(),
            block_time_record=block_time(block_id=1999),
            reference_slot_record=reference_slot(),
        )

        self.assertTrue(result["jupiter"]["block_id_semantics_verified"])
        self.assertFalse(result["jupiter"]["block_time_verified"])
        self.assertFalse(result["jupiter"]["chain_block_identity_verified"])
        self.assertFalse(result["jupiter"]["provider_fact_time_verified"])
        self.assertIsNone(result["jupiter"]["provider_fact_time_unix"])
        self.assertFalse(result["freshness_verified"])

    def test_missing_rpc_time_evidence_remains_explicitly_unverified(self):
        result = build_solana_market_freshness_evidence(jupiter(), dex())

        self.assertTrue(result["jupiter"]["block_id_semantics_verified"])
        self.assertFalse(result["jupiter"]["block_time_verified"])
        self.assertFalse(result["jupiter"]["reference_slot_verified"])
        self.assertFalse(result["jupiter"]["provider_fact_time_verified"])
        self.assertIn("solana_reference_slot_unavailable", result["limitations"])
        self.assertFalse(result["freshness_verified"])

    def test_block_after_reference_slot_is_not_silently_accepted(self):
        result = build_solana_market_freshness_evidence(
            jupiter(block_id=3000),
            dex(),
            block_time_record=block_time(block_id=3000, timestamp=2000),
            reference_slot_record=reference_slot(slot=2999),
        )

        self.assertFalse(result["jupiter"]["block_at_or_before_reference_slot"])
        self.assertIn("jupiter_block_after_reference_slot", result["limitations"])
        self.assertFalse(result["freshness_verified"])

    def test_future_block_time_relative_to_collection_does_not_create_negative_age(self):
        result = build_solana_market_freshness_evidence(
            jupiter(),
            dex(),
            block_time_record=block_time(timestamp=2200),
            reference_slot_record=reference_slot(),
        )

        self.assertTrue(result["jupiter"]["provider_fact_time_verified"])
        self.assertFalse(result["jupiter"]["fact_age_computable"])
        self.assertIsNone(result["jupiter"]["fact_age_seconds_candidate"])
        self.assertIn(
            "jupiter_block_time_after_collection_clock",
            result["limitations"],
        )
        self.assertFalse(result["freshness_verified"])

    def test_invalid_collection_order_is_not_verified(self):
        result = build_solana_market_freshness_evidence(
            jupiter(
                collection_started_at_unix=2102.0,
                collection_completed_at_unix=2101.0,
            ),
            dex(),
            block_time_record=block_time(),
            reference_slot_record=reference_slot(),
        )

        self.assertFalse(result["jupiter"]["collection_time_verified"])
        self.assertFalse(result["jupiter"]["fact_age_computable"])


if __name__ == "__main__":
    unittest.main()
