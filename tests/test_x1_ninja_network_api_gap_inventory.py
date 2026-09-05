import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    X1_NINJA_ACCESS_LIMITED_ROUTE,
    X1_NINJA_CAPABILITY_WITHOUT_MACHINE_CONTRACT,
    X1_NINJA_COVERED_READ_ONLY_ROUTE,
    X1_NINJA_NETWORK_API_GAP_INVENTORY_CONTRACT,
    X1_NINJA_SEMANTIC_GAP_NOT_ROUTE_GAP,
    x1_ninja_network_api_gap_inventory,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


class X1NinjaNetworkAPIGapInventoryTests(unittest.TestCase):
    def test_all_five_documented_routes_are_covered_by_v9(self):
        report = x1_ninja_network_api_gap_inventory()

        self.assertEqual(
            report["contract"],
            X1_NINJA_NETWORK_API_GAP_INVENTORY_CONTRACT,
        )
        self.assertEqual(report["known_documented_api_route_count"], 5)
        self.assertEqual(report["known_documented_api_route_gap_count"], 0)
        self.assertEqual(report["known_documented_api_route_gaps"], [])
        self.assertTrue(report["all_known_documented_api_routes_covered_by_v9"])
        self.assertFalse(
            report["universal_x1_ninja_endpoint_completeness_verified"]
        )

    def test_route_inventory_contains_expected_surfaces(self):
        report = x1_ninja_network_api_gap_inventory()
        rows = report["known_documented_api_routes"]

        self.assertEqual(
            {row["surface_id"] for row in rows},
            {
                "pool_catalog",
                "pool_detail",
                "trade_history",
                "ohlcv",
                "trade_stream_access",
            },
        )
        self.assertTrue(all(row["covered_by_v9"] for row in rows))
        self.assertTrue(all(row["structured_route_verified"] for row in rows))
        self.assertFalse(any(row["provider_response_verified"] for row in rows))
        self.assertFalse(
            any(row["semantic_verification_complete"] for row in rows)
        )

    def test_four_routes_are_plain_covered_readonly_and_stream_is_access_limited(self):
        report = x1_ninja_network_api_gap_inventory()
        rows = report["known_documented_api_routes"]

        covered = [
            row
            for row in rows
            if row["classification"] == X1_NINJA_COVERED_READ_ONLY_ROUTE
        ]
        access_limited = [
            row
            for row in rows
            if row["classification"] == X1_NINJA_ACCESS_LIMITED_ROUTE
        ]

        self.assertEqual(len(covered), 4)
        self.assertEqual(len(access_limited), 1)
        self.assertEqual(access_limited[0]["surface_id"], "trade_stream_access")
        self.assertEqual(
            access_limited[0]["repository_evidence_access_state"],
            "access_denied",
        )
        self.assertEqual(
            access_limited[0]["repository_evidence_http_status"],
            403,
        )
        self.assertFalse(access_limited[0]["live_current_access_verified"])
        self.assertFalse(
            access_limited[0]["event_body_consumption_authorized"]
        )
        self.assertFalse(access_limited[0]["access_limitation_is_route_gap"])
        self.assertFalse(report["access_limitations_are_route_gaps"])

    def test_semantic_gaps_are_explicitly_not_route_gaps(self):
        report = x1_ninja_network_api_gap_inventory()

        self.assertGreater(report["semantic_gap_count"], 0)
        self.assertFalse(report["semantic_gaps_are_route_gaps"])
        self.assertTrue(
            all(
                row["classification"]
                == X1_NINJA_SEMANTIC_GAP_NOT_ROUTE_GAP
                for row in report["semantic_gaps"]
            )
        )
        self.assertEqual(
            {row["gap_id"] for row in report["semantic_gaps"]},
            {
                "pool_identity_reserve_holder_semantics",
                "trade_history_semantics",
                "ohlcv_semantics",
                "liquidity_usd_fact_time_freshness",
                "delayed_vault_departure_semantics",
                "trade_stream_event_semantics",
            },
        )

    def test_advertised_wallet_capabilities_do_not_become_invented_endpoints(self):
        report = x1_ninja_network_api_gap_inventory()
        capabilities = report["capabilities_without_machine_contract"]

        self.assertEqual(report["capability_without_machine_contract_count"], 2)
        self.assertEqual(
            {row["capability_id"] for row in capabilities},
            {"general_wallet_indexer", "wallet_metrics"},
        )
        self.assertTrue(
            all(
                row["classification"]
                == X1_NINJA_CAPABILITY_WITHOUT_MACHINE_CONTRACT
                for row in capabilities
            )
        )
        self.assertTrue(
            all(row["invented_endpoint_authorized"] is False for row in capabilities)
        )
        self.assertFalse(report["invented_endpoint_authorized"])

    def test_browser_capture_is_not_required_now(self):
        report = x1_ninja_network_api_gap_inventory()

        self.assertFalse(report["browser_capture_required_now"])
        self.assertEqual(
            report["recommended_next_contract"],
            "x1_ninja_semantic_coverage_reconciliation/v1",
        )
        self.assertEqual(
            report["recommended_next_task"],
            "x1_ninja_semantic_coverage_reconciliation",
        )

    def test_truth_and_authority_boundaries_remain_closed(self):
        report = x1_ninja_network_api_gap_inventory()

        self.assertEqual(report["truth_state"]["discovery_state"], DISCOVERED)
        self.assertFalse(report["truth_state"]["provider_response_verified"])
        self.assertFalse(
            report["truth_state"]["semantic_verification_complete"]
        )
        self.assertFalse(report["truth_state"]["freshness_verified"])
        self.assertFalse(report["truth_state"]["source_independence_verified"])
        self.assertFalse(report["truth_state"]["cmis_verified"])
        self.assertFalse(report["event_body_consumption_authorized"])
        self.assertFalse(report["request_replay_authorized"])
        self.assertFalse(report["background_monitoring_authorized"])
        self.assertFalse(report["public_service_promoted"])
        self.assertFalse(report["scout_reliance_promoted"])
        self.assertFalse(report["cmis_promotable"])
        self.assertFalse(report["execution_authorized"])

    def test_service_wrapper_preserves_internal_discovery_boundary(self):
        service = CMISWebDiscoveryService()
        result = service.x1_ninja_network_api_gap_inventory()

        self.assertEqual(result["source_id"], "x1_ninja")
        self.assertEqual(result["report"]["known_documented_api_route_gap_count"], 0)
        self.assertFalse(result["report"]["browser_capture_required_now"])
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
