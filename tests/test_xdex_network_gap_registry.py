import unittest

from liquidity_scout.providers.web_discovery import (
    XDEX_COVERED_READ_ONLY,
    XDEX_EXECUTION_ADJACENT_EXCLUDED,
    XDEX_NETWORK_GAP_REGISTRY_CONTRACT,
    XDEX_NETWORK_GAP_UNKNOWN,
    XDEX_READ_ONLY_GAP_CANDIDATE,
    XDEX_UI_ONLY_CANDIDATE,
    classify_xdex_network_surface,
    xdex_network_gap_report,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


class XDEXNetworkGapRegistryTests(unittest.TestCase):
    def test_four_existing_structured_api_surfaces_are_covered(self):
        urls = [
            "https://api.xdex.xyz/api/xendex/pool/list",
            "https://api.xdex.xyz/api/token-price/price",
            "https://api.xdex.xyz/api/xendex/chart/history",
            "https://api.xdex.xyz/api/xendex/swap/quote",
        ]
        for url in urls:
            with self.subTest(url=url):
                row = classify_xdex_network_surface(url)
                self.assertEqual(row["contract"], XDEX_NETWORK_GAP_REGISTRY_CONTRACT)
                self.assertEqual(row["classification"], XDEX_COVERED_READ_ONLY)
                self.assertTrue(row["direct_machine_access"])
                self.assertTrue(row["structured_discovery_covered"])
                self.assertFalse(row["browser_capture_justified"])
                self.assertFalse(row["execution_authorized"])

    def test_frontend_quote_alias_is_direct_read_only_gap(self):
        row = classify_xdex_network_surface(
            "https://api.xdex.xyz/api/xdex/swap/quote"
        )
        self.assertEqual(row["classification"], XDEX_READ_ONLY_GAP_CANDIDATE)
        self.assertEqual(row["surface_id"], "swap_quote_frontend_alias")
        self.assertTrue(row["direct_machine_access"])
        self.assertFalse(row["structured_discovery_covered"])
        self.assertEqual(
            row["recommended_next_contract"],
            "xdex_extended_readonly_structured_discovery/v1",
        )
        self.assertFalse(row["browser_capture_justified"])

    def test_oracle_price_and_sell_quote_are_direct_read_only_gaps(self):
        rows = [
            classify_xdex_network_surface(
                "https://oracle.xdex.xyz/api/v1/token/price"
            ),
            classify_xdex_network_surface(
                "https://oracle.xdex.xyz/api/v1/token/sell-quote"
            ),
        ]
        self.assertEqual(
            [row["classification"] for row in rows],
            [XDEX_READ_ONLY_GAP_CANDIDATE, XDEX_READ_ONLY_GAP_CANDIDATE],
        )
        self.assertTrue(all(row["direct_machine_access"] for row in rows))
        self.assertFalse(any(row["browser_capture_justified"] for row in rows))
        self.assertFalse(any(row["execution_authorized"] for row in rows))

    def test_prepare_routes_are_execution_adjacent_even_if_get_is_requested(self):
        for path in (
            "/api/xendex/swap/prepare",
            "/api/xdex/swap/prepare",
        ):
            for method in ("GET", "POST"):
                with self.subTest(path=path, method=method):
                    row = classify_xdex_network_surface(
                        f"https://api.xdex.xyz{path}",
                        method=method,
                    )
                    self.assertEqual(
                        row["classification"],
                        XDEX_EXECUTION_ADJACENT_EXCLUDED,
                    )
                    self.assertFalse(row["read_only"])
                    self.assertFalse(row["request_replay_authorized"])
                    self.assertFalse(row["execution_authorized"])

    def test_ui_routes_are_not_machine_readable_evidence(self):
        for url in (
            "https://app.xdex.xyz/swap",
            "https://app.xdex.xyz/liquidity",
            "https://app.xdex.xyz/alpha",
            "https://xdex.xyz/",
        ):
            with self.subTest(url=url):
                row = classify_xdex_network_surface(url)
                self.assertEqual(row["classification"], XDEX_UI_ONLY_CANDIDATE)
                self.assertFalse(row["direct_machine_access"])
                self.assertFalse(row["browser_capture_justified"])
                self.assertFalse(row["truth_state"]["cmis_verified"])

    def test_known_read_only_surface_with_wrong_method_is_unknown(self):
        row = classify_xdex_network_surface(
            "https://api.xdex.xyz/api/xendex/swap/quote",
            method="POST",
        )
        self.assertEqual(row["classification"], XDEX_NETWORK_GAP_UNKNOWN)
        self.assertEqual(row["reason"], "known_surface_wrong_transport_method")
        self.assertFalse(row["execution_authorized"])

    def test_unknown_host_and_non_https_fail_closed(self):
        unknown = classify_xdex_network_surface(
            "https://example.com/api/xendex/swap/quote"
        )
        insecure = classify_xdex_network_surface(
            "http://api.xdex.xyz/api/xendex/swap/quote"
        )
        self.assertEqual(unknown["classification"], XDEX_NETWORK_GAP_UNKNOWN)
        self.assertEqual(unknown["reason"], "unknown_xdex_surface")
        self.assertEqual(insecure["classification"], XDEX_NETWORK_GAP_UNKNOWN)
        self.assertEqual(insecure["reason"], "invalid_or_non_https_url")

    def test_gap_report_says_browser_capture_not_required_now(self):
        report = xdex_network_gap_report()

        self.assertEqual(report["contract"], XDEX_NETWORK_GAP_REGISTRY_CONTRACT)
        self.assertEqual(report["read_only_gap_count"], 3)
        self.assertEqual(
            set(report["read_only_gap_surface_ids"]),
            {
                "swap_quote_frontend_alias",
                "oracle_token_price",
                "oracle_sell_quote",
            },
        )
        self.assertTrue(report["all_known_read_only_gaps_direct_machine_access"])
        self.assertFalse(report["browser_capture_required_now"])
        self.assertEqual(
            report["recommended_next_contract"],
            "xdex_extended_readonly_structured_discovery/v1",
        )
        self.assertEqual(
            report["classification_counts"][XDEX_COVERED_READ_ONLY],
            4,
        )
        self.assertEqual(
            report["classification_counts"][XDEX_EXECUTION_ADJACENT_EXCLUDED],
            2,
        )
        self.assertFalse(report["request_replay_authorized"])
        self.assertFalse(report["background_monitoring_authorized"])
        self.assertFalse(report["execution_authorized"])

    def test_service_wrapper_preserves_authority_boundary(self):
        service = CMISWebDiscoveryService()

        result = service.xdex_network_gap_report()

        self.assertEqual(result["source_id"], "xdex")
        self.assertFalse(result["report"]["browser_capture_required_now"])
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
