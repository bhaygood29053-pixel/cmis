from copy import deepcopy
from datetime import datetime, timezone
import unittest

from liquidity_scout.cmis.wallet_activity import (
    build_wallet_activity_observation,
    summarize_wallet_activity,
)


class CMISWalletActivityPhase11Tests(unittest.TestCase):
    def base(self, activity_type="TRANSFER_IN", **overrides):
        values = {
            "chain": "x1",
            "wallet": "wallet-1",
            "activity_type": activity_type,
            "transaction_signature": "sig-1",
            "observed_at": "2026-08-18T08:00:00-04:00",
            "block_slot": 123,
            "source": "x1_rpc",
            "verification_method": "verified_activity_v1",
            "evidence_scope": "transaction_exact",
            "asset_id": "mint-1",
            "asset_amount": None,
            "asset_unit": None,
            "quote_value": None,
            "quote_unit": None,
            "counterparty": None,
            "deployer_id": None,
            "token_account": None,
            "balance_before": None,
            "balance_after": None,
            "wallet_identity_verified": True,
            "asset_identity_verified": True,
            "transaction_identity_verified": True,
            "amount_verified": False,
            "transfer_direction_verified": activity_type
            in {"TRANSFER_IN", "TRANSFER_OUT", "DEPLOYER_ORIGINATED_TRANSFER"},
            "trade_direction_verified": activity_type in {"BUY", "SELL"},
            "lp_action_verified": activity_type in {"LP_ADD", "LP_REMOVE"},
            "deployer_identity_verified": False,
            "token_account_ownership_verified": False,
            "quote_value_verified": False,
            "counterparty_verified": False,
            "limitations": [],
        }
        values.update(overrides)
        return values

    def build(self, activity_type="TRANSFER_IN", **overrides):
        return build_wallet_activity_observation(**self.base(activity_type, **overrides))

    def test_transfer_direction_timestamp_and_source_are_canonical(self):
        record = self.build(
            "TRANSFER_IN",
            asset_amount="2.5000",
            asset_unit="token",
            amount_verified=True,
        )
        self.assertEqual(record["activity_type"], "TRANSFER_IN")
        self.assertEqual(record["asset_amount"], "2.5")
        self.assertEqual(record["observed_at"], "2026-08-18T12:00:00Z")
        self.assertEqual(record["source"], "x1_rpc")
        self.assertTrue(record["observation_id"].startswith("wa_"))
        self.assertFalse(record["classification_authorized"])
        self.assertEqual(record["classification_labels"], [])

    def test_source_and_identity_fields_require_real_strings(self):
        with self.assertRaisesRegex(ValueError, "source is required"):
            self.build("TRANSFER_IN", source=" ")
        with self.assertRaisesRegex(ValueError, "source must be a string"):
            self.build("TRANSFER_IN", source=123)
        with self.assertRaisesRegex(ValueError, "wallet must be a string"):
            self.build("TRANSFER_IN", wallet=123)
        with self.assertRaisesRegex(ValueError, "asset_id must be a string"):
            self.build("TRANSFER_IN", asset_id=123)
        with self.assertRaisesRegex(ValueError, "transaction_signature must be a string"):
            self.build("TRANSFER_IN", transaction_signature=123)

    def test_transfer_requires_verified_direction_and_asset_identity(self):
        with self.assertRaisesRegex(ValueError, "verified transfer direction"):
            self.build("TRANSFER_OUT", transfer_direction_verified=False)
        with self.assertRaisesRegex(ValueError, "verified asset identity"):
            self.build("TRANSFER_IN", asset_identity_verified=False)

    def test_buy_sell_require_verified_trade_direction(self):
        with self.assertRaisesRegex(ValueError, "verified trade direction"):
            self.build("BUY", trade_direction_verified=False)
        record = self.build(
            "SELL",
            asset_amount="10",
            asset_unit="token",
            amount_verified=True,
            quote_value="25.50",
            quote_unit="USD",
            quote_value_verified=True,
        )
        self.assertEqual(record["quote_value"], "25.5")

    def test_quote_value_is_trade_only_and_positive(self):
        with self.assertRaisesRegex(ValueError, "only for BUY/SELL"):
            self.build(
                "TRANSFER_IN",
                quote_value="5",
                quote_unit="USD",
                quote_value_verified=True,
            )
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            self.build(
                "BUY",
                quote_value="0",
                quote_unit="USD",
                quote_value_verified=True,
            )

    def test_lp_action_requires_verified_semantics(self):
        with self.assertRaisesRegex(ValueError, "verified LP action semantics"):
            self.build("LP_ADD", lp_action_verified=False)
        record = self.build("LP_REMOVE")
        self.assertEqual(record["activity_type"], "LP_REMOVE")

    def test_deployer_originated_transfer_requires_named_verified_deployer(self):
        with self.assertRaisesRegex(ValueError, "verified deployer identity"):
            self.build("DEPLOYER_ORIGINATED_TRANSFER")
        with self.assertRaisesRegex(ValueError, "verified deployer as counterparty"):
            self.build(
                "DEPLOYER_ORIGINATED_TRANSFER",
                deployer_id="deployer-1",
                deployer_identity_verified=True,
                counterparty="someone-else",
                counterparty_verified=True,
            )
        record = self.build(
            "DEPLOYER_ORIGINATED_TRANSFER",
            deployer_id="deployer-1",
            deployer_identity_verified=True,
            counterparty="deployer-1",
            counterparty_verified=True,
        )
        self.assertEqual(record["deployer_id"], "deployer-1")
        self.assertEqual(record["counterparty"], "deployer-1")

    def test_balance_change_is_asset_and_token_account_bound(self):
        record = self.build(
            "BALANCE_CHANGE",
            asset_unit="token",
            token_account="token-account-1",
            balance_before="14.75",
            balance_after="10.5",
            amount_verified=True,
            token_account_ownership_verified=True,
            transfer_direction_verified=False,
        )
        self.assertEqual(record["asset_amount"], "-4.25")
        self.assertEqual(record["balance_before"], "14.75")
        self.assertEqual(record["balance_after"], "10.5")
        self.assertEqual(record["token_account"], "token-account-1")
        self.assertFalse(record["complete_wallet_history_proven"])

    def test_balance_change_requires_verified_token_account_ownership(self):
        with self.assertRaisesRegex(ValueError, "verified token-account ownership"):
            self.build(
                "BALANCE_CHANGE",
                asset_unit="token",
                token_account="token-account-1",
                balance_before="10",
                balance_after="11",
                amount_verified=True,
                token_account_ownership_verified=False,
                transfer_direction_verified=False,
            )

    def test_balance_change_rejects_negative_balances_and_supplied_delta(self):
        with self.assertRaisesRegex(ValueError, "must not be negative"):
            self.build(
                "BALANCE_CHANGE",
                asset_unit="token",
                token_account="token-account-1",
                balance_before="-1",
                balance_after="1",
                amount_verified=True,
                token_account_ownership_verified=True,
                transfer_direction_verified=False,
            )
        with self.assertRaisesRegex(ValueError, "derived and must not be supplied"):
            self.build(
                "BALANCE_CHANGE",
                asset_amount="1",
                asset_unit="token",
                token_account="token-account-1",
                balance_before="1",
                balance_after="2",
                amount_verified=True,
                token_account_ownership_verified=True,
                transfer_direction_verified=False,
            )

    def test_missing_amount_stays_unknown_and_never_zero_fills(self):
        record = self.build("TRANSFER_IN")
        self.assertIsNone(record["asset_amount"])
        self.assertIsNone(record["asset_unit"])
        summary = summarize_wallet_activity(
            chain="x1", wallet="wallet-1", observations=[record]
        )
        self.assertEqual(summary["verified_amounts_by_asset"], {})
        self.assertEqual(summary["sources"], ["x1_rpc"])

    def test_unverified_amount_fields_must_not_be_exposed(self):
        with self.assertRaisesRegex(ValueError, "unverified asset amount/unit"):
            self.build("TRANSFER_IN", asset_amount="5", asset_unit="token")
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            self.build(
                "TRANSFER_IN",
                asset_amount="0",
                asset_unit="token",
                amount_verified=True,
            )

    def test_all_verification_flags_are_strict_booleans(self):
        with self.assertRaisesRegex(ValueError, "amount_verified must be a boolean"):
            self.build("TRANSFER_IN", amount_verified="true")
        with self.assertRaisesRegex(ValueError, "counterparty_verified must be a boolean"):
            self.build("TRANSFER_IN", counterparty_verified=1)

    def test_transaction_identity_timestamp_and_slot_are_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "verified transaction identity"):
            self.build("TRANSFER_IN", transaction_identity_verified=False)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            self.build("TRANSFER_IN", observed_at="2026-08-18T12:00:00")
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            self.build("TRANSFER_IN", block_slot=-1)

    def test_summary_revalidates_content_addressed_observations(self):
        record = self.build(
            "TRANSFER_IN",
            asset_amount="2",
            asset_unit="token",
            amount_verified=True,
        )
        tampered = deepcopy(record)
        tampered["asset_amount"] = "200"
        with self.assertRaisesRegex(ValueError, "content or content-addressed id"):
            summarize_wallet_activity(
                chain="x1", wallet="wallet-1", observations=[tampered]
            )

    def test_source_provenance_is_content_addressed(self):
        record = self.build("TRANSFER_IN")
        tampered = deepcopy(record)
        tampered["source"] = "other_rpc"
        with self.assertRaisesRegex(ValueError, "content or content-addressed id"):
            summarize_wallet_activity(
                chain="x1", wallet="wallet-1", observations=[tampered]
            )

    def test_summary_orders_by_actual_canonical_time_and_deduplicates(self):
        later = self.build(
            "BUY",
            transaction_signature="sig-2",
            observed_at=datetime(2026, 8, 18, 13, 0, tzinfo=timezone.utc),
            source="x1_rpc",
            asset_amount="2",
            asset_unit="token",
            amount_verified=True,
            quote_value="20",
            quote_unit="USD",
            quote_value_verified=True,
        )
        earlier = self.build(
            "SELL",
            transaction_signature="sig-1",
            observed_at="2026-08-18T08:30:00-04:00",
            source="xdex_verified_activity",
            asset_amount="1",
            asset_unit="token",
            amount_verified=True,
            quote_value="10",
            quote_unit="USD",
            quote_value_verified=True,
        )
        summary = summarize_wallet_activity(
            chain="X1", wallet="wallet-1", observations=[later, earlier, earlier]
        )
        self.assertEqual(summary["first_observed_activity"], "2026-08-18T12:30:00Z")
        self.assertEqual(summary["last_observed_activity"], "2026-08-18T13:00:00Z")
        self.assertEqual(summary["unique_transaction_count"], 2)
        self.assertEqual(summary["observation_count"], 2)
        self.assertEqual(summary["verified_trade_volume_by_quote_unit"], {"USD": "30"})
        self.assertEqual(summary["sources"], ["x1_rpc", "xdex_verified_activity"])
        self.assertFalse(summary["classification_authorized"])
        self.assertFalse(summary["activity_window"]["continuous_coverage_proven"])
        self.assertFalse(summary["complete_wallet_history_proven"])

    def test_summary_rejects_cross_wallet_or_cross_chain_input(self):
        record = self.build("TRANSFER_IN")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            summarize_wallet_activity(chain="x1", wallet="wallet-2", observations=[record])
        with self.assertRaisesRegex(ValueError, "chain mismatch"):
            summarize_wallet_activity(chain="solana", wallet="wallet-1", observations=[record])


if __name__ == "__main__":
    unittest.main()
