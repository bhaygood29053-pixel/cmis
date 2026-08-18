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
            requested_account_limit=20,
            accounts=[
                {"address": "acct-a", "amount": "250", "decimals": 6},
                {"address": "acct-b", "amount": "150", "decimals": 6},
            ],
            supply_identity_verified=True,
            account_identity_verified=True,
        )

        self.assertEqual(result["observed_balance_raw"], "400")
        self.assertEqual(
            result["observed_share_exact"],
            {"numerator": "400", "denominator": "1000"},
        )
        self.assertEqual(result["observed_share"], "0.4")
        self.assertEqual(result["observed_share_bps"], "4000")
        self.assertEqual(result["requested_account_limit"], 20)
        self.assertEqual(result["observed_account_count"], 2)
        self.assertFalse(result["scope_limit_filled"])
        self.assertTrue(result["identity_verified"])
        self.assertFalse(result["scope_complete"])
        self.assertFalse(result["holder_semantics_verified"])
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_nonterminating_decimal_preserves_exact_raw_ratio(self):
        result = build_top_account_concentration(
            chain="x1",
            asset_id="mint-1",
            source="X1 RPC",
            supply_raw=3,
            supply_decimals=0,
            requested_account_limit=1,
            accounts=[{"address": "acct-a", "amount": 1, "decimals": 0}],
            supply_identity_verified=True,
            account_identity_verified=True,
        )
        self.assertEqual(
            result["observed_share_exact"],
            {"numerator": "1", "denominator": "3"},
        )
        self.assertTrue(result["observed_share"].startswith("0.333333333333"))
        self.assertTrue(result["scope_limit_filled"])

    def test_identity_requires_both_supply_and_account_identity(self):
        result = build_top_account_concentration(
            chain="x1",
            asset_id="mint-1",
            source="X1 RPC",
            supply_raw=100,
            supply_decimals=0,
            requested_account_limit=20,
            accounts=[{"address": "acct-a", "amount": 25, "decimals": 0}],
            supply_identity_verified=True,
            account_identity_verified=False,
        )
        self.assertFalse(result["identity_verified"])

    def test_rejects_non_boolean_identity_flags(self):
        with self.assertRaisesRegex(ValueError, "supply_identity_verified"):
            build_top_account_concentration(
                chain="x1",
                asset_id="mint-1",
                source="X1 RPC",
                supply_raw=100,
                supply_decimals=0,
                requested_account_limit=20,
                accounts=[],
                supply_identity_verified="false",
                account_identity_verified=True,
            )

    def test_zero_supply_with_no_accounts_has_no_ratio(self):
        result = build_top_account_concentration(
            chain="solana",
            asset_id="mint-2",
            source="Solana RPC",
            supply_raw=0,
            supply_decimals=9,
            requested_account_limit=20,
            accounts=[],
            supply_identity_verified=True,
            account_identity_verified=True,
        )
        self.assertIsNone(result["observed_share_exact"])
        self.assertIsNone(result["observed_share"])
        self.assertIsNone(result["observed_share_bps"])
        self.assertEqual(result["observed_account_count"], 0)

    def test_positive_supply_empty_observation_is_not_zero_concentration(self):
        with self.assertRaisesRegex(ValueError, "empty evidence is not zero concentration"):
            build_top_account_concentration(
                chain="x1",
                asset_id="mint-1",
                source="X1 RPC",
                supply_raw=100,
                supply_decimals=0,
                requested_account_limit=20,
                accounts=[],
                supply_identity_verified=True,
                account_identity_verified=True,
            )

    def test_zero_supply_requires_empty_observed_set_even_for_zero_balance_row(self):
        with self.assertRaisesRegex(ValueError, "zero total supply requires an empty"):
            build_top_account_concentration(
                chain="x1",
                asset_id="mint-1",
                source="X1 RPC",
                supply_raw=0,
                supply_decimals=0,
                requested_account_limit=20,
                accounts=[{"address": "acct-a", "amount": 0, "decimals": 0}],
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
                requested_account_limit=20,
                accounts=[{"address": "acct-a", "amount": 101, "decimals": 0}],
                supply_identity_verified=True,
                account_identity_verified=True,
            )

    def test_rejects_observed_count_beyond_requested_top_n(self):
        with self.assertRaisesRegex(ValueError, "exceeds requested_account_limit"):
            build_top_account_concentration(
                chain="x1",
                asset_id="mint-1",
                source="X1 RPC",
                supply_raw=100,
                supply_decimals=0,
                requested_account_limit=1,
                accounts=[
                    {"address": "acct-a", "amount": 50, "decimals": 0},
                    {"address": "acct-b", "amount": 25, "decimals": 0},
                ],
                supply_identity_verified=True,
                account_identity_verified=True,
            )

    def test_requested_account_limit_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "positive integer"):
            build_top_account_concentration(
                chain="x1",
                asset_id="mint-1",
                source="X1 RPC",
                supply_raw=100,
                supply_decimals=0,
                requested_account_limit=0,
                accounts=[{"address": "acct-a", "amount": 50, "decimals": 0}],
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
                requested_account_limit=20,
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
                requested_account_limit=20,
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
                requested_account_limit=20,
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
                requested_account_limit=20,
                accounts=[],
                supply_identity_verified=True,
                account_identity_verified=True,
            )


if __name__ == "__main__":
    unittest.main()
