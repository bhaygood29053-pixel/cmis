import unittest

from liquidity_scout.cmis.wallet_activity import build_balance_change_observation


class WalletActivityObservationTests(unittest.TestCase):
    def test_verified_positive_delta_is_inflow_without_trade_label(self):
        result = build_balance_change_observation(
            chain="x1",
            account_id="acct-1",
            asset_id="mint-1",
            before_amount="10.00",
            after_amount="12.5",
            unit="token_base_units",
            observed_at="2026-08-18T10:00:00Z",
            source="x1_rpc",
            block_slot=123,
            transaction_id="sig-1",
            account_identity_verified=True,
            asset_identity_verified=True,
            amount_semantics_verified=True,
        )
        self.assertEqual(result["delta_amount"], "2.5")
        self.assertEqual(result["direction"], "INFLOW")
        self.assertFalse(result["trade_direction_verified"])
        self.assertIsNone(result["wallet_classification"])
        self.assertFalse(result["cmis_promotable"])

    def test_verified_negative_delta_is_outflow(self):
        result = build_balance_change_observation(
            chain="solana", account_id="a", asset_id="m",
            before_amount="5", after_amount="1.25", unit="base_units",
            observed_at=None, source="solana_rpc", amount_semantics_verified=True,
        )
        self.assertEqual(result["delta_amount"], "-3.75")
        self.assertEqual(result["direction"], "OUTFLOW")

    def test_unverified_amount_semantics_never_assigns_direction(self):
        result = build_balance_change_observation(
            chain="x1", account_id="a", asset_id="m",
            before_amount="1", after_amount="9", unit="provider_units",
            observed_at=None, source="provider", amount_semantics_verified=False,
        )
        self.assertEqual(result["direction"], "UNVERIFIED")
        self.assertEqual(result["delta_amount"], "8")

    def test_zero_delta_is_unchanged_when_semantics_verified(self):
        result = build_balance_change_observation(
            chain="x1", account_id="a", asset_id="m",
            before_amount="1.0", after_amount="1", unit="base_units",
            observed_at=None, source="rpc", amount_semantics_verified=True,
        )
        self.assertEqual(result["direction"], "UNCHANGED")
        self.assertEqual(result["delta_amount"], "0")

    def test_rejects_nonfinite_and_boolean_amounts(self):
        common = dict(chain="x1", account_id="a", asset_id="m", unit="u", observed_at=None, source="rpc")
        for value in (True, "NaN", "Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    build_balance_change_observation(before_amount=value, after_amount="1", **common)

    def test_requires_explicit_identity_and_unit_strings(self):
        with self.assertRaises(ValueError):
            build_balance_change_observation(
                chain="x1", account_id=" ", asset_id="m", before_amount="0",
                after_amount="1", unit="u", observed_at=None, source="rpc",
            )


if __name__ == "__main__":
    unittest.main()
