import copy
import unittest

from liquidity_scout.services.cmis_burn_intelligence import (
    CONTRACT_VERSION,
    SERVICE,
    build_burn_intelligence_response,
)
from liquidity_scout.services.cmis_contract import build_service_envelope


MINT = "7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER"


def window(label, *, burned="10", percent="25"):
    value = {
        "status": "ok",
        "coverage_verified": True,
        "burned_raw": burned,
        "burned_tokens": burned,
        "burn_events": 2,
        "minted_raw": "20",
        "minted_tokens": "20",
        "mint_events": 1,
        "burn_to_emission_ratio": "0.5",
        "net_issuance_raw": "10",
        "net_issuance_tokens": "10",
        "issuance_state": "INFLATIONARY",
    }
    if label != "1h":
        value["period_over_period"] = {
            "status": "ok",
            "prior_start_exclusive": 0,
            "prior_end_inclusive": 100,
            "prior_burned_raw": "8",
            "prior_burned_tokens": "8",
            "percent_change": percent,
            "change_state": "AVAILABLE",
        }
    return value


def tokenomics_envelope():
    return build_service_envelope(
        "tokenomics",
        "x1",
        "partial",
        asset={"symbol": "AGI", "name": "AGI", "mint": MINT},
        data={
            "mint": MINT,
            "symbol": "AGI",
            "name": "AGI",
            "burn_metrics": {
                "available": True,
                "status": "partial",
                "burn_events_observed": 7,
                "verified_burned_raw_observed": "70",
                "verified_burned_observed": "70",
                "lifetime_total_burn_verified": False,
                "coverage_verified": True,
                "time_buckets_verified": True,
                "observed_event_totals_verified": True,
                "coverage_start_time": 0,
                "coverage_end_time": 200,
                "observed_at": 200,
                "windows": {
                    "1h": window("1h"),
                    "24h": window("24h"),
                    "7d": window("7d"),
                    "30d": window("30d"),
                },
                "valuation": {
                    "status": "partial",
                    "valuation_coverage_complete": False,
                    "usd": {"verified_value_destroyed": "1.50"},
                },
                "circulating_supply": {
                    "status": "ok",
                    "circulating_supply_verified": True,
                    "circulating_supply": "900",
                },
            },
        },
        confidence={"status": "partial"},
        sources=[{"source": "x1_rpc"}],
        observed_at=200,
        warnings=[{"code": "lifetime_total_not_verified"}],
    )


class BurnIntelligenceContractTests(unittest.TestCase):
    def test_projects_first_class_burn_contract_without_recomputation(self):
        source = tokenomics_envelope()
        before = copy.deepcopy(source)
        response = build_burn_intelligence_response(source)

        self.assertEqual(response["service"], SERVICE)
        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["data"]["contract_version"], CONTRACT_VERSION)
        self.assertEqual(response["data"]["mint"], MINT)
        self.assertEqual(
            response["data"]["burn_metrics"],
            source["data"]["burn_metrics"],
        )
        self.assertEqual(
            response["data"]["windows"]["24h"]["burned_tokens"],
            "10",
        )
        self.assertEqual(
            response["data"]["windows"]["7d"]["period_over_period"]["percent_change"],
            "25",
        )
        self.assertEqual(
            response["data"]["cumulative"]["verified_burned_observed"],
            "70",
        )
        self.assertFalse(
            response["data"]["cumulative"]["lifetime_total_burn_verified"]
        )
        self.assertFalse(response["execution_authorized"])
        self.assertEqual(source, before)

    def test_new_burn_activity_preserves_null_percent_semantics(self):
        source = tokenomics_envelope()
        comparison = source["data"]["burn_metrics"]["windows"]["24h"]["period_over_period"]
        comparison["prior_burned_raw"] = "0"
        comparison["prior_burned_tokens"] = "0"
        comparison["percent_change"] = None
        comparison["change_state"] = "NEW_BURN_ACTIVITY"

        response = build_burn_intelligence_response(source)
        projected = response["data"]["windows"]["24h"]["period_over_period"]
        self.assertIsNone(projected["percent_change"])
        self.assertEqual(projected["change_state"], "NEW_BURN_ACTIVITY")

    def test_unavailable_burn_metrics_remain_unavailable_without_zero_fill(self):
        source = tokenomics_envelope()
        source["data"]["burn_metrics"] = {
            "available": False,
            "status": "unavailable",
            "reason": "token_activity_not_supplied",
            "lifetime_total_burn_verified": False,
        }

        response = build_burn_intelligence_response(source)
        self.assertEqual(response["status"], "unavailable")
        self.assertFalse(response["data"]["burn_metrics"]["available"])
        self.assertNotIn("windows", response["data"]["burn_metrics"])
        self.assertFalse(response["execution_authorized"])

    def test_wrong_or_mismatched_identity_fails_closed(self):
        source = tokenomics_envelope()
        source["asset"]["mint"] = "AGI"
        response = build_burn_intelligence_response(source)
        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][-1]["code"],
            "burn_intelligence_contract_violation",
        )

        source = tokenomics_envelope()
        source["data"]["mint"] = "So11111111111111111111111111111111111111112"
        response = build_burn_intelligence_response(source)
        self.assertEqual(response["status"], "error")

    def test_wrong_upstream_service_fails_closed(self):
        source = tokenomics_envelope()
        source["service"] = "market_report"
        response = build_burn_intelligence_response(source)
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "wrong_upstream_service")


if __name__ == "__main__":
    unittest.main()
