import json
import pathlib
import unittest

from liquidity_scout.providers.solana.pyth_freshness_policy import (
    FRESH,
    FUTURE,
    INVALID,
    POLICY_UNVERIFIED,
    STALE,
    UNAVAILABLE,
    accepted_pyth_freshness_policy,
    classify_pyth_freshness,
    normalize_pyth_freshness_policy,
)


POLICY_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "liquidity_scout"
    / "providers"
    / "solana"
    / "pyth_freshness_policy.json"
)


def record(
    *,
    publish_time=1000,
    reference_time=1050.0,
    integrity=True,
    mapping=True,
    fact_time=True,
):
    return {
        "chain": "solana",
        "source": "pyth_core_solana_push",
        "mapping_verified": mapping,
        "fact_time_verified": fact_time,
        "collection_time_verified": True,
        "price_integrity_verified": integrity,
        "publish_time_unix": publish_time,
        "collection_completed_at_unix": reference_time,
    }


class PythFreshnessPolicyTests(unittest.TestCase):
    def test_policy_file_matches_runtime_policy(self):
        with POLICY_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        self.assertEqual(raw, accepted_pyth_freshness_policy())
        normalized = normalize_pyth_freshness_policy(raw)
        self.assertTrue(normalized["policy_complete"])
        self.assertFalse(normalized["has_hidden_defaults"])
        self.assertEqual(normalized["max_age_seconds"], 60)
        self.assertEqual(normalized["max_future_skew_seconds"], 5)
        self.assertIn("1-minute heartbeat", normalized["max_age_provenance"])
        self.assertIn("not a Pyth or Solana SLA", normalized["future_skew_provenance"])

    def test_policy_missing_provenance_is_unverified(self):
        result = classify_pyth_freshness(
            record(),
            policy={
                "policy_id": "test",
                "max_age_seconds": 60,
                "max_future_skew_seconds": 5,
            },
        )

        self.assertEqual(result["classification"], POLICY_UNVERIFIED)
        self.assertFalse(result["classification_verified"])
        self.assertFalse(result["pyth_freshness_verified"])
        self.assertFalse(result["pyth_current_price_eligible"])

    def test_max_age_boundary_is_inclusive(self):
        policy = accepted_pyth_freshness_policy()
        fresh = classify_pyth_freshness(
            record(publish_time=1000, reference_time=1060),
            policy=policy,
        )
        stale = classify_pyth_freshness(
            record(publish_time=1000, reference_time=1060.001),
            policy=policy,
        )

        self.assertEqual(fresh["classification"], FRESH)
        self.assertTrue(fresh["pyth_current_price_eligible"])
        self.assertEqual(fresh["effective_age_seconds"], 60)

        self.assertEqual(stale["classification"], STALE)
        self.assertFalse(stale["pyth_current_price_eligible"])

    def test_future_skew_boundary_is_inclusive(self):
        policy = accepted_pyth_freshness_policy()
        fresh = classify_pyth_freshness(
            record(publish_time=1005, reference_time=1000),
            policy=policy,
        )
        future = classify_pyth_freshness(
            record(publish_time=1005.001, reference_time=1000),
            policy=policy,
        )

        self.assertEqual(fresh["classification"], FRESH)
        self.assertEqual(fresh["future_offset_seconds"], 5)
        self.assertTrue(fresh["pyth_current_price_eligible"])

        self.assertEqual(future["classification"], FUTURE)
        self.assertFalse(future["pyth_current_price_eligible"])

    def test_missing_exact_mapping_is_unavailable(self):
        result = classify_pyth_freshness(
            record(mapping=False),
            policy=accepted_pyth_freshness_policy(),
        )
        self.assertEqual(result["classification"], UNAVAILABLE)

    def test_missing_publish_time_is_unavailable(self):
        result = classify_pyth_freshness(
            record(fact_time=False),
            policy=accepted_pyth_freshness_policy(),
        )
        self.assertEqual(result["classification"], UNAVAILABLE)

    def test_unverified_price_integrity_is_invalid(self):
        result = classify_pyth_freshness(
            record(integrity=False),
            policy=accepted_pyth_freshness_policy(),
        )
        self.assertEqual(result["classification"], INVALID)
        self.assertFalse(result["pyth_current_price_eligible"])

    def test_fresh_pyth_never_promotes_cross_source_or_execution_authority(self):
        result = classify_pyth_freshness(
            record(),
            policy=accepted_pyth_freshness_policy(),
        )

        self.assertEqual(result["classification"], FRESH)
        self.assertTrue(result["pyth_freshness_verified"])
        self.assertTrue(result["pyth_current_price_eligible"])
        self.assertFalse(result["current_price_promotable"])
        self.assertFalse(result["cross_source_time_identity_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
