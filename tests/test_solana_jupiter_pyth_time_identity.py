import json
import pathlib
import unittest

from liquidity_scout.providers.solana.jupiter_pyth_time_identity import (
    INVALID,
    POLICY_UNVERIFIED,
    SAME_TIME,
    SOURCE_FUTURE,
    SOURCE_STALE,
    TIME_MISMATCH,
    UNAVAILABLE,
    accepted_jupiter_pyth_time_identity_policy,
    classify_jupiter_pyth_time_identity,
    normalize_jupiter_pyth_time_identity_policy,
)


POLICY_PATH = (
    pathlib.Path(__file__).resolve().parents[1]
    / "liquidity_scout"
    / "providers"
    / "solana"
    / "jupiter_pyth_time_identity_policy.json"
)


def crosscheck(*, jupiter_time="1000", pyth_time="1004", delta="4", status="AGREEMENT"):
    return {
        "service": "solana_jupiter_pyth_price_crosscheck",
        "chain": "solana",
        "status": status,
        "identity_verified": True,
        "semantics_verified": True,
        "within_tolerance": status == "AGREEMENT",
        "jupiter_fact_time_unix": jupiter_time,
        "pyth_fact_time_unix": pyth_time,
        "fact_time_delta_seconds": delta,
    }


def jupiter_freshness(classification="FRESH", eligible=None):
    if eligible is None:
        eligible = classification == "FRESH"
    return {
        "classification": classification,
        "jupiter_freshness_verified": classification in {"FRESH", "STALE", "FUTURE"},
        "jupiter_current_price_eligible": eligible,
    }


def pyth_freshness(classification="FRESH", eligible=None):
    if eligible is None:
        eligible = classification == "FRESH"
    return {
        "classification": classification,
        "pyth_freshness_verified": classification in {"FRESH", "STALE", "FUTURE"},
        "pyth_current_price_eligible": eligible,
    }


class JupiterPythTimeIdentityPolicyTests(unittest.TestCase):
    def test_policy_json_matches_runtime_and_has_no_hidden_default(self):
        with POLICY_PATH.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        self.assertEqual(raw, accepted_jupiter_pyth_time_identity_policy())
        normalized = normalize_jupiter_pyth_time_identity_policy(raw)

        self.assertTrue(normalized["policy_complete"])
        self.assertFalse(normalized["has_hidden_defaults"])
        self.assertEqual(normalized["max_fact_time_delta_seconds"], 5)
        self.assertIn("operator comparison window", normalized["max_fact_time_delta_provenance"])
        self.assertIn("independently of observed passing samples", normalized["max_fact_time_delta_provenance"])
        self.assertIn("exact USDC mint", normalized["scope_provenance"])

    def test_missing_threshold_or_provenance_is_policy_unverified(self):
        result = classify_jupiter_pyth_time_identity(
            crosscheck(),
            jupiter_freshness(),
            pyth_freshness(),
            policy={
                "policy_id": "test",
                "scope": "test",
                "scope_provenance": "test",
            },
        )

        self.assertEqual(result["classification"], POLICY_UNVERIFIED)
        self.assertFalse(result["classification_verified"])
        self.assertFalse(result["cross_source_time_identity_verified"])
        self.assertFalse(result["same_time_candidate"])

    def test_exact_five_second_boundary_is_same_time(self):
        result = classify_jupiter_pyth_time_identity(
            crosscheck(pyth_time="1005", delta="5"),
            jupiter_freshness(),
            pyth_freshness(),
            policy=accepted_jupiter_pyth_time_identity_policy(),
        )

        self.assertEqual(result["classification"], SAME_TIME)
        self.assertTrue(result["classification_verified"])
        self.assertTrue(result["cross_source_time_identity_verified"])
        self.assertTrue(result["same_time_candidate"])
        self.assertEqual(result["fact_time_delta_seconds"], "5")

    def test_above_five_seconds_is_time_mismatch(self):
        result = classify_jupiter_pyth_time_identity(
            crosscheck(pyth_time="1005.001", delta="5.001"),
            jupiter_freshness(),
            pyth_freshness(),
            policy=accepted_jupiter_pyth_time_identity_policy(),
        )

        self.assertEqual(result["classification"], TIME_MISMATCH)
        self.assertTrue(result["classification_verified"])
        self.assertFalse(result["cross_source_time_identity_verified"])
        self.assertFalse(result["same_time_candidate"])

    def test_both_sources_must_be_fresh(self):
        stale = classify_jupiter_pyth_time_identity(
            crosscheck(),
            jupiter_freshness("STALE"),
            pyth_freshness(),
            policy=accepted_jupiter_pyth_time_identity_policy(),
        )
        future = classify_jupiter_pyth_time_identity(
            crosscheck(),
            jupiter_freshness(),
            pyth_freshness("FUTURE"),
            policy=accepted_jupiter_pyth_time_identity_policy(),
        )

        self.assertEqual(stale["classification"], SOURCE_STALE)
        self.assertFalse(stale["cross_source_time_identity_verified"])
        self.assertEqual(future["classification"], SOURCE_FUTURE)
        self.assertFalse(future["cross_source_time_identity_verified"])

    def test_unavailable_source_freshness_cannot_be_same_time(self):
        result = classify_jupiter_pyth_time_identity(
            crosscheck(),
            jupiter_freshness("UNAVAILABLE"),
            pyth_freshness(),
            policy=accepted_jupiter_pyth_time_identity_policy(),
        )

        self.assertEqual(result["classification"], UNAVAILABLE)
        self.assertFalse(result["classification_verified"])
        self.assertFalse(result["same_time_candidate"])

    def test_fresh_label_with_ineligible_source_is_invalid(self):
        result = classify_jupiter_pyth_time_identity(
            crosscheck(),
            jupiter_freshness("FRESH", eligible=False),
            pyth_freshness(),
            policy=accepted_jupiter_pyth_time_identity_policy(),
        )

        self.assertEqual(result["classification"], INVALID)
        self.assertFalse(result["cross_source_time_identity_verified"])

    def test_reported_delta_must_match_exact_fact_times(self):
        result = classify_jupiter_pyth_time_identity(
            crosscheck(pyth_time="1004", delta="3"),
            jupiter_freshness(),
            pyth_freshness(),
            policy=accepted_jupiter_pyth_time_identity_policy(),
        )

        self.assertEqual(result["classification"], INVALID)
        self.assertEqual(result["reason"], "cross_source_fact_time_delta_mismatch")

    def test_price_agreement_remains_separate_from_time_identity(self):
        conflict_same_time = classify_jupiter_pyth_time_identity(
            crosscheck(status="CONFLICT"),
            jupiter_freshness(),
            pyth_freshness(),
            policy=accepted_jupiter_pyth_time_identity_policy(),
        )

        self.assertEqual(conflict_same_time["classification"], SAME_TIME)
        self.assertTrue(conflict_same_time["cross_source_time_identity_verified"])
        self.assertFalse(conflict_same_time["numerical_price_agreement"])
        self.assertFalse(conflict_same_time["source_independence_verified"])
        self.assertFalse(conflict_same_time["price_construction_equivalence_verified"])
        self.assertFalse(conflict_same_time["current_price_promotable"])
        self.assertFalse(conflict_same_time["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
