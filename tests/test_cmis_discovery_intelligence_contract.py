import copy
import unittest

from liquidity_scout.services.cmis_discovery_intelligence import (
    CONTRACT_VERSION,
    SERVICE,
    build_discovery_intelligence_response,
)
from liquidity_scout.services.cmis_contract import build_service_envelope


MINT = "7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER"


def identity():
    return build_service_envelope(
        "asset_lookup",
        "x1",
        "ok",
        asset={"mint": MINT, "symbol": "AGI", "name": "AGI"},
        data={"identity_contract": "x1_asset_identity/v1"},
        confidence={"identity_verified": True},
    )


def observation(content_id, fact_time, source):
    return {
        "content_id": content_id,
        "mint": MINT,
        "observation_kind": "market_verified",
        "fact_time_unix": fact_time,
        "fact_time_verified": True,
        "verification_state": "verified",
        "source_id": source,
        "execution_authorized": False,
    }


def projection():
    first = observation("do_first", 100, "x1_rpc")
    recent = observation("do_recent", 220, "xdex")
    return {
        "available": True,
        "mint": MINT,
        "observation_kind": None,
        "verified_observation_count": 2,
        "first_verified_observation": first,
        "most_recent_verified_observation": recent,
        "coverage": {
            "start_fact_time_unix": 100,
            "end_fact_time_unix": 220,
            "elapsed_observed_seconds": 120,
            "continuous_coverage_verified": False,
            "archive_completeness_verified": False,
        },
        "token_launch_time": None,
        "token_launch_time_verified": False,
        "sources": [{"source": "x1_rpc"}, {"source": "xdex"}],
        "observed_at": 220,
    }


class DiscoveryIntelligenceContractTests(unittest.TestCase):
    def test_projects_bounded_verified_history_without_launch_inference(self):
        source = projection()
        before = copy.deepcopy(source)

        response = build_discovery_intelligence_response(identity(), source)

        self.assertEqual(response["service"], SERVICE)
        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["data"]["contract_version"], CONTRACT_VERSION)
        self.assertEqual(response["data"]["verified_observation_count"], 2)
        self.assertEqual(response["data"]["coverage"]["elapsed_observed_seconds"], 120)
        self.assertIsNone(response["data"]["token_launch_time"])
        self.assertFalse(response["data"]["token_launch_time_verified"])
        self.assertFalse(response["execution_authorized"])
        self.assertEqual(source, before)

    def test_empty_verified_scope_is_unavailable_without_zero_time_claims(self):
        source = projection()
        source.update({
            "available": False,
            "verified_observation_count": 0,
            "first_verified_observation": None,
            "most_recent_verified_observation": None,
            "coverage": {
                "start_fact_time_unix": None,
                "end_fact_time_unix": None,
                "elapsed_observed_seconds": None,
                "continuous_coverage_verified": False,
                "archive_completeness_verified": False,
            },
            "sources": [],
            "observed_at": None,
        })

        response = build_discovery_intelligence_response(identity(), source)

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["data"]["verified_observation_count"], 0)
        self.assertIsNone(response["data"]["coverage"]["elapsed_observed_seconds"])

    def test_mismatched_identity_or_inconsistent_bounds_fail_closed(self):
        wrong = projection()
        wrong["mint"] = "So11111111111111111111111111111111111111112"
        response = build_discovery_intelligence_response(identity(), wrong)
        self.assertEqual(response["status"], "error")

        wrong = projection()
        wrong["coverage"]["elapsed_observed_seconds"] = 999
        response = build_discovery_intelligence_response(identity(), wrong)
        self.assertEqual(response["status"], "error")

    def test_launch_time_promotion_fails_closed(self):
        wrong = projection()
        wrong["token_launch_time"] = 100
        wrong["token_launch_time_verified"] = True

        response = build_discovery_intelligence_response(identity(), wrong)

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "discovery_intelligence_contract_violation",
        )


if __name__ == "__main__":
    unittest.main()
