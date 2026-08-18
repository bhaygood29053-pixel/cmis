import unittest

from liquidity_scout.cmis.concentration import build_top_account_concentration


class CMISTopAccountConcentrationTests(unittest.TestCase):
    def test_builds_exact_observed_share_without_holder_promotion(self):
        result = build_top_account_concentration(
            chain="x1",
            asset_id="mint-1",
            source="X1 RPC",
            supply_raw="1000",
            supply_decimals=6,
            accounts=[
                {"address": "acct-a", "amount": "250", "decimals": 6},
                {"address": "acct-b", "amount": "150", "decimals": 6},
            ],
            supply_identity_verified=True,
            account_identity_verified=True,
        )

        self.assertEqual(result["observed_balance_raw"], "400")
        self.assertEqual(result["observed_share"], "0.4")
        self.assertEqual(result["observed_share_bps"], "4000.0")
        self.assertEqual(result["observed_account_count"], 2)
        self.assertTrue(result["identity_verified"])
        self.assertFalse(result["scope_complete"])
        self.assertFalse(result["holder_semantics_verified"])
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_identity_requires_both_supply_and_account_identity(self):
        result = build_top_account_concentration(
            chain="x1",
            asset_id="mint-1",
            source="X1 RPC",
            supply_raw=100,
            supply_decimals=0,
            accounts=[{"address": "acct-a", "amount": 25, "decimals": 0}],
            supply_identity_verified=True,
            account_identity_verified=False,
        )
        self.assertFalse(result["identity_verified"])

    def test_zero_supply_with_no_accounts_has_no_ratio(self):
        result = build_top_account_concentration(
            chain="solana",
            asset_id="mint-2",
            source="Solana RPC",
            supply_raw=0,
            supply_decimals=9,
            accounts=[],
            supply_identity_verified=True,
            account_identity_verified=True,
        )
        self.assertIsNone(result["observed_share"])
        self.assertIsNone(result["observed_share_bps"])

    def test_rejects_positive_balance_against_zero_supply(self):
        with self.assertRaisesRegex(ValueError, "zero total supply"):
            build_top_account_concentration(
                chain="x1",
                asset_id="mint-1",
                source="X1 RPC",
                supply_raw=0,
                supply_decimals=0,
                accounts=[{"address": "acct-a", "amount": 1, "decimals": 0}],
                supply_identity_verified=True,
                account_identity_verified=True,
            )

    def test_rejects_accounts_exceeding_total_supply(self):
        with self.assertRaisesRegex(ValueError, "exceed total supply"):
            build_top_account_concentration(
                chain="x1",
                asset_id="mint-1",
                source="X1 RPC",
                supply_raw=100,
                supply_decimals=0,
                accounts=[{"address": "acct-a", "amount": 101, "decimals": 0}],
                supply_identity_verified=True,
                account_identity_verified=True,
            )

    def test_rejects_duplicate_addresses(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_top_account_concentration(
                chain="x1",
                asset_id="mint-1",
                source="X1 RPC",
                supply_raw=100,
                supply_decimals=0,
                accounts=[
                    {"address": "acct-a", "amount": 50, "decimals": 0},
                    {"address": "acct-a", "amount": 25, "decimals": 0},
                ],
                supply_identity_verified=True,
                account_identity_verified=True,
            )

    def test_rejects_wrong_order_and_decimal_mismatch(self):
        with self.assertRaisesRegex(ValueError, "ordered by descending"):
            build_top_account_concentration(
                chain="x1",
                asset_id="mint-1",
                source="X1 RPC",
                supply_raw=100,
                supply_decimals=0,
                accounts=[
                    {"address": "acct-a", "amount": 10, "decimals": 0},
                    {"address": "acct-b", "amount": 20, "decimals": 0},
                ],
                supply_identity_verified=True,
                account_identity_verified=True,
            )
        with self.assertRaisesRegex(ValueError, "decimals must match"):
            build_top_account_concentration(
                chain="x1",
                asset_id="mint-1",
                source="X1 RPC",
                supply_raw=100,
                supply_decimals=6,
                accounts=[{"address": "acct-a", "amount": 10, "decimals": 9}],
                supply_identity_verified=True,
                account_identity_verified=True,
            )

    def test_rejects_boolean_numeric_inputs(self):
        with self.assertRaisesRegex(ValueError, "supply_raw"):
            build_top_account_concentration(
                chain="x1",
                asset_id="mint-1",
                source="X1 RPC",
                supply_raw=True,
                supply_decimals=0,
                accounts=[],
                supply_identity_verified=True,
                account_identity_verified=True,
            )


if __name__ == "__main__":
    unittest.main()
