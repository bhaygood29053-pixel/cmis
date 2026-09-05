import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    XDEX_COVERAGE_RECONCILIATION_CONTRACT,
    xdex_coverage_reconciliation,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


class XDEXCoverageReconciliationTests(unittest.TestCase):
    def test_known_direct_readonly_inventory_is_fully_covered(self):
        report = xdex_coverage_reconciliation()

        self.assertEqual(
            report["contract"],
            XDEX_COVERAGE_RECONCILIATION_CONTRACT,
        )
        self.assertEqual(
            report["scope"],
            "known_repository_owned_xdex_surface_inventory",
        )
        self.assertEqual(report["known_direct_readonly_surface_count"], 7)
        self.assertEqual(report["known_direct_readonly_gap_count"], 0)
        self.assertEqual(report["known_direct_readonly_gaps"], [])
        self.assertTrue(
            report["xdex_direct_machine_coverage_complete_for_known_inventory"]
        )
        self.assertFalse(report["universal_xdex_endpoint_completeness_verified"])

    def test_v5_and_v7_own_the_known_direct_surface_set(self):
        report = xdex_coverage_reconciliation()
        rows = report["known_direct_readonly_surfaces"]

        v5 = [
            row
            for row in rows
            if row["coverage_contract"] == "xdex_structured_discovery/v1"
        ]
        v7 = [
            row
            for row in rows
            if row["coverage_contract"]
            == "xdex_extended_readonly_structured_discovery/v1"
        ]

        self.assertEqual(len(v5), 4)
        self.assertEqual(len(v7), 3)
        self.assertTrue(
            all(row["covered_by_structured_contract"] for row in rows)
        )
        self.assertTrue(all(row["structured_route_verified"] for row in rows))
        self.assertFalse(any(row["provider_response_verified"] for row in rows))
        self.assertFalse(
            any(row["semantic_verification_complete"] for row in rows)
        )

    def test_all_three_former_v6_gaps_are_closed_by_v7(self):
        report = xdex_coverage_reconciliation()
        former = [
            row
            for row in report["known_direct_readonly_surfaces"]
            if row["former_v6_gap_candidate"]
        ]

        self.assertEqual(report["former_v6_gap_candidate_count"], 3)
        self.assertEqual(
            {row["surface_id"] for row in former},
            {
                "swap_quote_frontend_alias",
                "oracle_token_price",
                "oracle_sell_quote",
            },
        )
        self.assertTrue(report["former_v6_gap_candidates_covered_by_v7"])
        self.assertTrue(
            all(
                row["coverage_contract"]
                == "xdex_extended_readonly_structured_discovery/v1"
                for row in former
            )
        )

    def test_prepare_exclusions_remain_intact(self):
        report = xdex_coverage_reconciliation()

        self.assertEqual(report["known_execution_exclusion_count"], 2)
        self.assertTrue(report["execution_exclusions_intact"])
        for row in report["known_execution_exclusions"]:
            self.assertTrue(row["excluded"])
            self.assertFalse(row["read_only"])
            self.assertFalse(row["execution_authorized"])

    def test_ui_only_boundary_does_not_trigger_browser_capture(self):
        report = xdex_coverage_reconciliation()

        self.assertEqual(report["known_ui_only_surface_count"], 1)
        self.assertTrue(report["ui_only_boundary_intact"])
        self.assertFalse(report["browser_capture_required_now"])
        for row in report["known_ui_only_surfaces"]:
            self.assertTrue(row["ui_only"])
            self.assertFalse(row["direct_machine_access"])
            self.assertFalse(row["browser_capture_justified"])

    def test_documentation_surface_remains_covered(self):
        report = xdex_coverage_reconciliation()
        self.assertTrue(report["documentation_surface_covered"])

    def test_next_source_is_x1_ninja(self):
        report = xdex_coverage_reconciliation()

        self.assertEqual(report["recommended_next_source"], "x1_ninja")
        self.assertIn(
            "X1.Ninja",
            report["recommended_next_action"],
        )

    def test_reconciliation_preserves_truth_and_authority_boundaries(self):
        report = xdex_coverage_reconciliation()

        self.assertEqual(
            report["truth_state"]["discovery_state"],
            DISCOVERED,
        )
        self.assertFalse(report["truth_state"]["provider_response_verified"])
        self.assertFalse(
            report["truth_state"]["semantic_verification_complete"]
        )
        self.assertFalse(report["truth_state"]["source_independence_verified"])
        self.assertFalse(report["truth_state"]["cmis_verified"])
        self.assertFalse(report["request_replay_authorized"])
        self.assertFalse(report["background_monitoring_authorized"])
        self.assertFalse(report["public_service_promoted"])
        self.assertFalse(report["scout_reliance_promoted"])
        self.assertFalse(report["cmis_promotable"])
        self.assertFalse(report["execution_authorized"])

    def test_service_wrapper_preserves_internal_discovery_boundary(self):
        service = CMISWebDiscoveryService()
        result = service.xdex_coverage_reconciliation()

        self.assertEqual(result["source_id"], "xdex")
        self.assertEqual(result["report"]["known_direct_readonly_gap_count"], 0)
        self.assertEqual(
            result["report"]["recommended_next_source"],
            "x1_ninja",
        )
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
