import os
import tempfile
import unittest

from liquidity_scout.cmis.intelligence_history import (
    IntelligenceHistoryLedger,
    build_history_observation,
)
from liquidity_scout.cmis.wallet_activity import (
    build_wallet_activity_observation,
    summarize_wallet_activity,
)


class WalletActivityPrimitiveTests(unittest.TestCase):
    def _base(self, activity_type, **overrides):
        values = {
            "chain": "x1",
            "wallet": "wallet-1",
            "activity_type": activity_type,
            "transaction_signature": f"sig-{activity_type}",
            "observed_at": "2026-08-18T09:00:00Z",
            "block_slot": 100,
            "verification_method": "x1_rpc_token_balance_delta_v1",
            "evidence_scope": "exact_transaction_wallet_asset",
            "asset_id": "mint-1",
            "asset_amount": "10",
            "asset_unit": "token_ui_units",
            "wallet_identity_verified": True,
            "asset_identity_verified": True,
            "amount_verified": True,
        }
        values.update(overrides)
        return build_wallet_activity_observation(**values)

    def test_transfer_fact_is_content_addressed_and_classification_free(self):
        first = self._base("TRANSFER_IN")
        second = self._base("TRANSFER_IN")
        self.assertEqual(first, second)
        self.assertTrue(first["observation_id"].startswith("wa_"))
        self.assertEqual(first["activity_type"], "TRANSFER_IN")
        self.assertFalse(first["classification_authorized"])
        self.assertEqual(first["classification_labels"], [])

    def test_buy_sell_require_verified_trade_direction(self):
        with self.assertRaisesRegex(ValueError, "trade direction"):
            self._base("BUY")
        buy = self._base(
            "BUY",
            trade_direction_verified=True,
            quote_value="25",
            quote_unit="USD",
            quote_value_verified=True,
        )
        self.assertEqual(buy["activity_type"], "BUY")
        self.assertEqual(buy["quote_value"], "25")

    def test_lp_action_requires_verified_semantics(self):
        with self.assertRaisesRegex(ValueError, "LP action"):
            self._base("LP_ADD")
        record = self._base("LP_REMOVE", lp_action_verified=True)
        self.assertEqual(record["activity_type"], "LP_REMOVE")

    def test_deployer_transfer_requires_verified_deployer_identity(self):
        with self.assertRaisesRegex(ValueError, "deployer identity"):
            self._base("DEPLOYER_ORIGINATED_TRANSFER")
        record = self._base(
            "DEPLOYER_ORIGINATED_TRANSFER",
            deployer_identity_verified=True,
            counterparty="verified-deployer-wallet",
            counterparty_verified=True,
        )
        self.assertTrue(record["verification"]["deployer_identity_verified"])
        self.assertEqual(record["counterparty"], "verified-deployer-wallet")

    def test_unverified_amount_is_not_exposed_or_zero_filled(self):
        record = build_wallet_activity_observation(
            chain="x1",
            wallet="wallet-1",
            activity_type="TRANSFER_OUT",
            transaction_signature="sig-unknown-amount",
            observed_at="2026-08-18T09:01:00Z",
            verification_method="bounded_transfer_identity_only",
            evidence_scope="exact_transaction_wallet_asset",
            asset_id="mint-1",
            wallet_identity_verified=True,
            asset_identity_verified=True,
            amount_verified=False,
        )
        self.assertIsNone(record["asset_amount"])
        self.assertIsNone(record["asset_unit"])

    def test_summary_exposes_requested_primitives_without_behavior_labels(self):
        observations = [
            self._base(
                "TRANSFER_IN",
                transaction_signature="sig-1",
                observed_at="2026-08-18T09:00:00Z",
                asset_amount="100",
            ),
            self._base(
                "BUY",
                transaction_signature="sig-2",
                observed_at="2026-08-18T09:05:00Z",
                asset_amount="20",
                trade_direction_verified=True,
                quote_value="5",
                quote_unit="USD",
                quote_value_verified=True,
            ),
            self._base(
                "SELL",
                transaction_signature="sig-3",
                observed_at="2026-08-18T09:10:00Z",
                asset_amount="7",
                trade_direction_verified=True,
                quote_value="2",
                quote_unit="USD",
                quote_value_verified=True,
            ),
            self._base(
                "LP_ADD",
                transaction_signature="sig-4",
                observed_at="2026-08-18T09:15:00Z",
                asset_amount="3",
                lp_action_verified=True,
            ),
        ]
        summary = summarize_wallet_activity(
            chain="x1",
            wallet="wallet-1",
            observations=observations,
        )
        self.assertEqual(summary["first_observed_activity"], "2026-08-18T09:00:00Z")
        self.assertEqual(summary["last_observed_activity"], "2026-08-18T09:15:00Z")
        self.assertEqual(summary["unique_transaction_count"], 4)
        self.assertEqual(summary["activity_counts"]["BUY"], 1)
        self.assertEqual(summary["activity_counts"]["SELL"], 1)
        self.assertEqual(
            summary["verified_amounts_by_asset"]["mint-1"]["units"]
            ["token_ui_units"]["transfer_in"],
            "100",
        )
        self.assertEqual(summary["verified_trade_volume_by_quote_unit"]["USD"], "7")
        self.assertFalse(summary["activity_window"]["continuous_coverage_proven"])
        self.assertFalse(summary["activity_window"]["complete_wallet_history_proven"])
        self.assertEqual(summary["classifications"], [])
        self.assertFalse(summary["classification_authorized"])

    def test_summary_rejects_cross_wallet_or_cross_chain_contamination(self):
        record = self._base("TRANSFER_IN")
        with self.assertRaisesRegex(ValueError, "wallet observation identity mismatch"):
            summarize_wallet_activity(
                chain="x1", wallet="different-wallet", observations=[record]
            )
        with self.assertRaisesRegex(ValueError, "chain mismatch"):
            summarize_wallet_activity(
                chain="solana", wallet="wallet-1", observations=[record]
            )


class IntelligenceHistoryTests(unittest.TestCase):
    def _observation(self, *, value, observed_at, scope="asset_wide_verified", metric="liquidity_usd"):
        return build_history_observation(
            chain="x1",
            category="liquidity",
            subject_id="mint-1",
            metric=metric,
            value=value,
            unit="USD",
            observed_at=observed_at,
            source="cmis_market_report",
            verification_method="verified_asset_market_aggregation_v1",
            evidence_scope=scope,
            receipt_id="er_" + "a" * 64,
            proof_strength="STRONG",
            identity_verified=True,
            semantics_verified=True,
            freshness_verified=True,
            scope_complete=True,
        )

    def test_history_observation_requires_identity_and_semantics_proof(self):
        with self.assertRaisesRegex(ValueError, "verified subject identity"):
            build_history_observation(
                chain="x1",
                category="price",
                subject_id="mint-1",
                metric="price_usd",
                value="1.2",
                unit="USD_PER_TOKEN",
                observed_at="2026-08-18T09:00:00Z",
                source="provider",
                verification_method="test",
                evidence_scope="asset",
                semantics_verified=True,
            )

    def test_store_is_idempotent_and_content_addressed(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = IntelligenceHistoryLedger(os.path.join(directory, "history.db"))
            observation = self._observation(
                value="1000", observed_at="2026-08-18T09:00:00Z"
            )
            first = ledger.store(observation, recorded_at=1)
            second = ledger.store(observation, recorded_at=2)
            self.assertTrue(first["inserted"])
            self.assertFalse(second["inserted"])
            self.assertEqual(first["observation_id"], second["observation_id"])
            self.assertTrue(first["observation_id"].startswith("ih_"))

    def test_compare_first_last_reports_sparse_observed_change_only(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = IntelligenceHistoryLedger(os.path.join(directory, "history.db"))
            ledger.store(
                self._observation(value="1000", observed_at="2026-08-18T09:00:00Z"),
                recorded_at=1,
            )
            ledger.store(
                self._observation(value="1250", observed_at="2026-08-18T10:00:00Z"),
                recorded_at=2,
            )
            comparison = ledger.compare_first_last(
                chain="x1",
                category="liquidity",
                subject_id="mint-1",
                metric="liquidity_usd",
                unit="USD",
            )
            self.assertEqual(comparison["status"], "OBSERVED_CHANGE")
            self.assertEqual(comparison["absolute_change"], "250")
            self.assertEqual(comparison["percent_change"], "25")
            self.assertFalse(comparison["continuous_coverage_proven"])
            self.assertFalse(comparison["archival_completeness_proven"])

    def test_comparison_fails_closed_on_scope_change(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = IntelligenceHistoryLedger(os.path.join(directory, "history.db"))
            ledger.store(
                self._observation(value="1000", observed_at="2026-08-18T09:00:00Z"),
                recorded_at=1,
            )
            ledger.store(
                self._observation(
                    value="1250",
                    observed_at="2026-08-18T10:00:00Z",
                    scope="selected_pools_only",
                ),
                recorded_at=2,
            )
            comparison = ledger.compare_first_last(
                chain="x1",
                category="liquidity",
                subject_id="mint-1",
                metric="liquidity_usd",
                unit="USD",
            )
            self.assertEqual(comparison["status"], "INCOMPATIBLE_SCOPE")
            self.assertIsNone(comparison["absolute_change"])
            self.assertIsNone(comparison["percent_change"])

    def test_history_categories_support_wallet_price_supply_and_activity(self):
        categories = [
            ("wallet", "wallet-1", "verified_volume", "7", "USD"),
            ("price", "mint-1", "price_usd", "1.2", "USD_PER_TOKEN"),
            ("supply", "mint-1", "total_supply", "1000000", "token_ui_units"),
            ("activity", "mint-1", "verified_transaction_count", "12", "count"),
        ]
        for category, subject, metric, value, unit in categories:
            observation = build_history_observation(
                chain="x1",
                category=category,
                subject_id=subject,
                metric=metric,
                value=value,
                unit=unit,
                observed_at="2026-08-18T09:00:00Z",
                source="cmis",
                verification_method="accepted_contract",
                evidence_scope="observed_scope",
                identity_verified=True,
                semantics_verified=True,
            )
            self.assertEqual(observation["category"], category)
            self.assertFalse(observation["continuous_coverage_proven"])
            self.assertFalse(observation["archival_completeness_proven"])


if __name__ == "__main__":
    unittest.main()
