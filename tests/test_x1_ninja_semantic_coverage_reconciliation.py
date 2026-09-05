import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    X1_NINJA_SEMANTIC_BLOCKED,
    X1_NINJA_SEMANTIC_COVERAGE_CONTRACT,
    X1_NINJA_SEMANTIC_PARTIAL,
    X1_NINJA_SEMANTIC_UNAVAILABLE,
    X1_NINJA_SEMANTIC_VERIFIED,
    x1_ninja_semantic_coverage_reconciliation,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


class X1NinjaSemanticCoverageReconciliationTests(unittest.TestCase):
    def _families(self):
        report = x1_ninja_semantic_coverage_reconciliation()
        return {
            row["family_id"]: row
            for row in report["semantic_families"]
        }

    def test_registry_uses_only_four_allowed_statuses(self):
        report = x1_ninja_semantic_coverage_reconciliation()

        self.assertEqual(
            report["contract"],
            X1_NINJA_SEMANTIC_COVERAGE_CONTRACT,
        )
        self.assertEqual(
            set(report["allowed_statuses"]),
            {
                X1_NINJA_SEMANTIC_VERIFIED,
                X1_NINJA_SEMANTIC_PARTIAL,
                X1_NINJA_SEMANTIC_BLOCKED,
                X1_NINJA_SEMANTIC_UNAVAILABLE,
            },
        )
        self.assertEqual(report["semantic_family_count"], 13)
        self.assertEqual(
            report["status_counts"],
            {
                X1_NINJA_SEMANTIC_VERIFIED: 2,
                X1_NINJA_SEMANTIC_PARTIAL: 4,
                X1_NINJA_SEMANTIC_BLOCKED: 3,
                X1_NINJA_SEMANTIC_UNAVAILABLE: 4,
            },
        )

    def test_verified_families_are_bounded_and_named(self):
        families = self._families()

        reserve = families["pooled_reserve_roles_units"]
        fact_time = families["liquidity_fact_time"]

        self.assertEqual(reserve["status"], X1_NINJA_SEMANTIC_VERIFIED)
        self.assertIn("Issue #341", reserve["evidence_handoffs"])
        self.assertIn(
            "pooledBase_maps_to_rpc_vault_1_mint_1_scaled_reserve",
            reserve["verified_claims"],
        )
        self.assertIn("exact", reserve["scope"].lower())
        self.assertIn("pool", reserve["scope"].lower())

        self.assertEqual(fact_time["status"], X1_NINJA_SEMANTIC_VERIFIED)
        self.assertIn("PR #465", fact_time["evidence_handoffs"])
        self.assertIn(
            "liquidity_fact_time_verified",
            fact_time["verified_claims"],
        )
        self.assertIn(
            "liquidity_freshness_verified",
            fact_time["unverified_claims"],
        )

    def test_price_native_remains_partial_under_open_345(self):
        row = self._families()["price_native_semantics"]

        self.assertEqual(row["status"], X1_NINJA_SEMANTIC_PARTIAL)
        self.assertEqual(row["blocking_issue"], 345)
        self.assertIn("Issue #343", row["evidence_handoffs"])
        self.assertIn("Issue #345", row["evidence_handoffs"])
        self.assertIn(
            "universal_current_price_native_semantics",
            row["unverified_claims"],
        )
        self.assertIn(
            "provider_update_source_semantics",
            row["unverified_claims"],
        )

    def test_liquidity_usd_is_blocked_by_461_and_470(self):
        report = x1_ninja_semantic_coverage_reconciliation()
        row = self._families()["liquidity_usd_semantics"]

        self.assertEqual(row["status"], X1_NINJA_SEMANTIC_BLOCKED)
        self.assertEqual(row["blocking_issue"], 461)
        self.assertEqual(row["blocking_pr"], 470)
        self.assertEqual(
            report["liquidity_usd_semantics_status"],
            X1_NINJA_SEMANTIC_BLOCKED,
        )
        self.assertEqual(report["liquidity_usd_blocking_issue"], 461)
        self.assertEqual(report["liquidity_usd_blocking_pr"], 470)
        self.assertIn(
            "x1_ninja_liquidity_usd_semantics_verified",
            row["unverified_claims"],
        )

    def test_freshness_stays_blocked_under_459(self):
        report = x1_ninja_semantic_coverage_reconciliation()
        families = self._families()

        liquidity = families["liquidity_freshness"]
        rolling = families["rolling_24h_volume_transaction_freshness"]

        self.assertEqual(liquidity["status"], X1_NINJA_SEMANTIC_BLOCKED)
        self.assertEqual(rolling["status"], X1_NINJA_SEMANTIC_BLOCKED)
        self.assertEqual(liquidity["blocking_issue"], 459)
        self.assertEqual(rolling["blocking_issue"], 459)
        self.assertEqual(report["liquidity_freshness_blocking_issue"], 459)

    def test_holder_total_is_unavailable_but_label_guard_is_accepted(self):
        row = self._families()["holder_total_semantics"]

        self.assertEqual(row["status"], X1_NINJA_SEMANTIC_UNAVAILABLE)
        self.assertIn(
            "holder_labeling_guard_accepted",
            row["verified_claims"],
        )
        self.assertIn(
            "verified_asset_wide_holder_total",
            row["unverified_claims"],
        )
        self.assertIn(
            "beneficial_ownership",
            row["unverified_claims"],
        )

    def test_trade_history_and_ohlcv_are_partial_not_globally_verified(self):
        families = self._families()
        trades = families["trade_history_semantics"]
        ohlcv = families["ohlcv_history_semantics"]

        self.assertEqual(trades["status"], X1_NINJA_SEMANTIC_PARTIAL)
        self.assertIn(
            "bounded_sample_transaction_identity_crosscheck_available",
            trades["verified_claims"],
        )
        self.assertIn(
            "history_exhaustive_verified",
            trades["unverified_claims"],
        )
        self.assertIn(
            "finality_verified",
            trades["unverified_claims"],
        )

        self.assertEqual(ohlcv["status"], X1_NINJA_SEMANTIC_PARTIAL)
        self.assertIn(
            "bounded_exact_pair_time_close_crosscheck_used_by_history_backfill",
            ohlcv["verified_claims"],
        )
        self.assertIn(
            "full_asset_lifetime_verified",
            ohlcv["unverified_claims"],
        )
        self.assertIn(
            "continuous_coverage_verified",
            ohlcv["unverified_claims"],
        )

    def test_delayed_vault_is_partial_event_level_evidence(self):
        row = self._families()["delayed_vault_update_behavior"]

        self.assertEqual(row["status"], X1_NINJA_SEMANTIC_PARTIAL)
        self.assertIn("Issue #363", row["evidence_handoffs"])
        self.assertIn(
            "event_level_exact_delayed_link_can_be_verified",
            row["verified_claims"],
        )
        self.assertIn(
            "departure_pattern_verified_longitudinally",
            row["unverified_claims"],
        )
        self.assertIn(
            "provider_update_source_semantics",
            row["unverified_claims"],
        )

    def test_stream_price_usd_and_source_independence_are_unavailable(self):
        families = self._families()

        for family_id in (
            "trade_stream_event_semantics",
            "price_usd_semantics",
            "source_independence",
        ):
            with self.subTest(family_id=family_id):
                self.assertEqual(
                    families[family_id]["status"],
                    X1_NINJA_SEMANTIC_UNAVAILABLE,
                )

        stream = families["trade_stream_event_semantics"]
        self.assertIn("HTTP 403", stream["scope"])
        self.assertIn(
            "event_schema_verified",
            stream["unverified_claims"],
        )

    def test_route_coverage_is_complete_but_semantics_are_not_globally_complete(self):
        report = x1_ninja_semantic_coverage_reconciliation()

        self.assertTrue(
            report["route_discovery_complete_for_known_documented_api"]
        )
        self.assertEqual(report["known_documented_api_route_gap_count"], 0)
        self.assertFalse(report["browser_capture_required_now"])
        self.assertTrue(report["semantic_reconciliation_complete"])
        self.assertFalse(
            report["truth_state"]["semantic_verification_complete_globally"]
        )

    def test_recommended_next_actions_keep_470_then_459_then_345_order(self):
        report = x1_ninja_semantic_coverage_reconciliation()
        actions = report["recommended_next_actions"]

        self.assertEqual(
            [row["priority"] for row in actions],
            [1, 2, 3],
        )
        self.assertEqual(actions[0]["issue"], 461)
        self.assertEqual(actions[0]["pull_request"], 470)
        self.assertEqual(actions[1]["issue"], 459)
        self.assertEqual(actions[2]["issue"], 345)

    def test_authority_boundaries_remain_closed(self):
        report = x1_ninja_semantic_coverage_reconciliation()

        self.assertEqual(
            report["truth_state"]["discovery_state"],
            DISCOVERED,
        )
        self.assertFalse(report["truth_state"]["source_independence_verified"])
        self.assertFalse(report["public_service_promotion_authorized"])
        self.assertFalse(report["public_service_promoted"])
        self.assertFalse(report["scout_reliance_promoted"])
        self.assertFalse(report["event_body_consumption_authorized"])
        self.assertFalse(report["request_replay_authorized"])
        self.assertFalse(report["background_monitoring_authorized"])
        self.assertFalse(report["cmis_promotable"])
        self.assertFalse(report["execution_authorized"])

    def test_service_wrapper_preserves_internal_discovery_boundary(self):
        service = CMISWebDiscoveryService()
        result = service.x1_ninja_semantic_coverage_reconciliation()

        self.assertEqual(result["source_id"], "x1_ninja")
        self.assertEqual(
            result["report"]["semantic_family_count"],
            13,
        )
        self.assertFalse(result["cmis_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
