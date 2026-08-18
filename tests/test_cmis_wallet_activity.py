import unittest

from liquidity_scout.cmis.wallet_activity import build_balance_change_observation


class WalletActivityTests(unittest.TestCase):
    def _base_kwargs(self):
        return {
            "wallet": "wallet-1",
            "mint": "mint-1",
            "token_account": "token-account-1",
            "transaction_signature": "sig-1",
            "slot": 123,
            "observed_at": "2026-08-18T04:00:00Z",
            "pre_amount": "10.5",
            "post_amount": "14.75",
            "decimals": 6,
            "source": "x1_rpc",
            "verification_method": "token_balance_delta_v1",
            "wallet_identity_verified": True,
            "asset_identity_verified": True,
            "transaction_identity_verified": True,
            "token_account_ownership_verified": True,
            "amount_semantics_verified": True,
        }

    def test_verified_inflow_balance_primitive(self):
        record = build_balance_change_observation(**self._base_kwargs())

        self.assertEqual(record["primitive"], "TOKEN_ACCOUNT_BALANCE_CHANGE")
        self.assertEqual(record["chain"], "x1")
        self.assertEqual(record["wallet"], "wallet-1")
        self.assertEqual(record["asset"], {"mint": "mint-1"})
        self.assertEqual(record["pre_amount"], "10.5")
        self.assertEqual(record["post_amount"], "14.75")
        self.assertEqual(record["delta_amount"], "4.25")
        self.assertEqual(record["absolute_delta_amount"], "4.25")
        self.assertEqual(record["direction"], "INFLOW")
        self.assertIsNone(record["activity_classification"])
        self.assertFalse(record["activity_classification_verified"])
        self.assertIsNone(record["counterparty"])
        self.assertFalse(record["counterparty_verified"])
        self.assertIsNone(record["wallet_label"])
        self.assertFalse(record["wallet_label_verified"])
        self.assertFalse(record["complete_wallet_history_proven"])
        self.assertFalse(record["observation_window_complete"])

    def test_verified_outflow_balance_primitive(self):
        kwargs = self._base_kwargs()
        kwargs["pre_amount"] = "14.75"
        kwargs["post_amount"] = "10.5"

        record = build_balance_change_observation(**kwargs)

        self.assertEqual(record["delta_amount"], "-4.25")
        self.assertEqual(record["absolute_delta_amount"], "4.25")
        self.assertEqual(record["direction"], "OUTFLOW")

    def test_unchanged_balance_is_not_activity_classification(self):
        kwargs = self._base_kwargs()
        kwargs["post_amount"] = kwargs["pre_amount"]

        record = build_balance_change_observation(**kwargs)

        self.assertEqual(record["delta_amount"], "0")
        self.assertEqual(record["direction"], "UNCHANGED")
        self.assertIsNone(record["activity_classification"])

    def test_requires_verified_wallet_identity(self):
        kwargs = self._base_kwargs()
        kwargs["wallet_identity_verified"] = False

        with self.assertRaisesRegex(ValueError, "requires verified"):
            build_balance_change_observation(**kwargs)

    def test_requires_verified_token_account_ownership(self):
        kwargs = self._base_kwargs()
        kwargs["token_account_ownership_verified"] = False

        with self.assertRaisesRegex(ValueError, "requires verified"):
            build_balance_change_observation(**kwargs)

    def test_requires_verified_amount_semantics(self):
        kwargs = self._base_kwargs()
        kwargs["amount_semantics_verified"] = False

        with self.assertRaisesRegex(ValueError, "requires verified"):
            build_balance_change_observation(**kwargs)

    def test_rejects_invalid_amounts_and_slot(self):
        kwargs = self._base_kwargs()
        kwargs["pre_amount"] = "not-a-number"
        with self.assertRaisesRegex(ValueError, "finite numeric"):
            build_balance_change_observation(**kwargs)

        kwargs = self._base_kwargs()
        kwargs["slot"] = -1
        with self.assertRaisesRegex(ValueError, "slot"):
            build_balance_change_observation(**kwargs)

        kwargs = self._base_kwargs()
        kwargs["post_amount"] = "-1"
        with self.assertRaisesRegex(ValueError, "negative"):
            build_balance_change_observation(**kwargs)

    def test_window_flag_does_not_claim_complete_wallet_history(self):
        kwargs = self._base_kwargs()
        kwargs["observation_window_complete"] = True

        record = build_balance_change_observation(**kwargs)

        self.assertTrue(record["observation_window_complete"])
        self.assertFalse(record["complete_wallet_history_proven"])
        self.assertIn("complete_wallet_history_not_proven", record["limitations"])


if __name__ == "__main__":
    unittest.main()
