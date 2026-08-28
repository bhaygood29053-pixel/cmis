import json
import pathlib
import unittest

from liquidity_scout.providers.solana.jupiter_freshness_policy import (
    FRESH,
    FUTURE,
    INVALID,
    POLICY_UNVERIFIED,
    STALE,
    UNAVAILABLE,
    accepted_solana_jupiter_freshness_policy,
    classify_solana_jupiter_freshness,
    normalize_solana_jupiter_freshness_policy,
)


POLICY_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "liquidity_scout"
    / "providers"
    / "solana"
    / "jupiter_freshness_policy.json"
)


def evidence(*, fact_time=1000.0, reference_time=1050.0, provider_verified=True):
    return {
        "chain": "solana",
        "jupiter": {
            "provider_fact_time_verified": provider_verified,
            "provider_fact_time_unix": fact_time,
            "collection_time_verified": True,
            "collection_completed_at_unix": reference_time,
            "reference_slot_verified": True,
            "block_at_or_before_reference_slot": True,
        },
    }


class SolanaJupiterFreshnessPolicyTests(unittest.TestCase):
    def test_production_policy_json_matches_accepted_runtime_policy(self):
        with POLICY_PATH.open("r", encoding="utf-8") as handle:
            file_policy = json.load(handle)

        self.assertEqual(file_policy, accepted_solana_jupiter_freshness_policy())
        normalized = normalize_solana_jupiter_freshness_policy(file_policy)
        self.assertTrue(normalized["policy_complete"])
        self.assertFalse(normalized["has_hidden_defaults"])
        self.assertEqual(normalized["max_age_seconds"], 60)
        self.assertEqual(normalized["max_future_skew_seconds"], 5)
        self.assertIn("operator governance", normalized["max_age_provenance"])
        self.assertIn("operator governance", normalized["future_skew_provenance"])
        self.assertIn("X1 Oracle V2", normalized["max_age_provenance"])
        self.assertIn("not a Jupiter or Solana SLA", normalized["future_skew_provenance"])

    def test_missing_values_or_provenance_leave_policy_unverified(self):
        result = classify_solana_jupiter_freshness(
            evidence(),
            policy={
                "policy_id": "test",
                "max_age_seconds": 60,
                "max_future_skew_seconds": 5,
            },
        )

        self.assertEqual(result["classification"], POLICY_UNVERIFIED)
        self.assertFalse(result["classification_verified"])
        self.assertFalse(result["jupiter_freshness_verified"])
        self.assertFalse(result["jupiter_current_price_eligible"])

    def test_max_age_boundary_is_inclusive(self):
        policy = accepted_solana_jupiter_freshness_policy()

        at_boundary = classify_solana_jupiter_freshness(
            evidence(fact_time=1000.0, reference_time=1060.0),
            policy=policy,
        )
        stale = classify_solana_jupiter_freshness(
            evidence(fact_time=1000.0, reference_time=1060.001),
            policy=policy,
        )

        self.assertEqual(at_boundary["classification"], FRESH)
        self.assertTrue(at_boundary["jupiter_current_price_eligible"])
        self.assertEqual(at_boundary["effective_age_seconds"], 60.0)

        self.assertEqual(stale["classification"], STALE)
        self.assertFalse(stale["jupiter_current_price_eligible"])
        self.assertGreater(stale["effective_age_seconds"], 60)

    def test_future_skew_boundary_is_inclusive(self):
        policy = accepted_solana_jupiter_freshness_policy()

        accepted = classify_solana_jupiter_freshness(
            evidence(fact_time=1005.0, reference_time=1000.0),
            policy=policy,
        )
        future = classify_solana_jupiter_freshness(
            evidence(fact_time=1005.001, reference_time=1000.0),
            policy=policy,
        )

        self.assertEqual(accepted["classification"], FRESH)
        self.assertEqual(accepted["future_offset_seconds"], 5.0)
        self.assertEqual(accepted["effective_age_seconds"], 0.0)
        self.assertTrue(accepted["jupiter_current_price_eligible"])

        self.assertEqual(future["classification"], FUTURE)
        self.assertFalse(future["jupiter_current_price_eligible"])

    def test_missing_provider_fact_time_is_unavailable(self):
        result = classify_solana_jupiter_freshness(
            evidence(provider_verified=False),
            policy=accepted_solana_jupiter_freshness_policy(),
        )

        self.assertEqual(result["classification"], UNAVAILABLE)
        self.assertFalse(result["classification_verified"])
        self.assertFalse(result["jupiter_freshness_verified"])

    def test_block_after_reference_slot_is_invalid(self):
        record = evidence()
        record["jupiter"]["block_at_or_before_reference_slot"] = False

        result = classify_solana_jupiter_freshness(
            record,
            policy=accepted_solana_jupiter_freshness_policy(),
        )

        self.assertEqual(result["classification"], INVALID)
        self.assertFalse(result["classification_verified"])
        self.assertFalse(result["jupiter_current_price_eligible"])

    def test_wrong_chain_is_invalid(self):
        record = evidence()
        record["chain"] = "x1"

        result = classify_solana_jupiter_freshness(
            record,
            policy=accepted_solana_jupiter_freshness_policy(),
        )

        self.assertEqual(result["classification"], INVALID)

    def test_stale_and_future_are_verified_classifications_not_eligible_prices(self):
        policy = accepted_solana_jupiter_freshness_policy()
        stale = classify_solana_jupiter_freshness(
            evidence(fact_time=900.0, reference_time=1000.0),
            policy=policy,
        )
        future = classify_solana_jupiter_freshness(
            evidence(fact_time=1010.0, reference_time=1000.0),
            policy=policy,
        )

        self.assertEqual(stale["classification"], STALE)
        self.assertTrue(stale["classification_verified"])
        self.assertTrue(stale["jupiter_freshness_verified"])
        self.assertFalse(stale["jupiter_current_price_eligible"])

        self.assertEqual(future["classification"], FUTURE)
        self.assertTrue(future["classification_verified"])
        self.assertTrue(future["jupiter_freshness_verified"])
        self.assertFalse(future["jupiter_current_price_eligible"])

        for result in (stale, future):
            self.assertFalse(result["dexscreener_freshness_verified"])
            self.assertFalse(result["cross_source_time_identity_verified"])
            self.assertFalse(result["current_price_promotable"])
            self.assertFalse(result["source_independence_verified"])
            self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
