import unittest

from liquidity_scout.providers.x1.rpc_token_account import (
    ENCODING,
    RPC_METHOD,
    RPC_SOURCE,
)
from liquidity_scout.providers.x1.rpc_token_identity import (
    verify_x1_rpc_token_account_identity,
)


ACCOUNT = "Vault111"
MINT = "Mint111"
AUTHORITY = "Authority111"


def observation():
    return {
        "chain": "x1",
        "source": RPC_SOURCE,
        "method": RPC_METHOD,
        "encoding": ENCODING,
        "account": ACCOUNT,
        "slot": 72254502,
        "mint": MINT,
        "authority": AUTHORITY,
        "token_account_fields_parsed": True,
        "cmis_promotable": False,
    }


class X1RPCTokenIdentityTests(unittest.TestCase):
    def test_exact_expected_identity_verifies_without_auto_promotion(self):
        result = verify_x1_rpc_token_account_identity(
            observation(),
            expected_account=ACCOUNT,
            expected_mint=MINT,
            expected_authority=AUTHORITY,
        )

        self.assertTrue(result["account_verified"])
        self.assertTrue(result["mint_verified"])
        self.assertTrue(result["authority_verified"])
        self.assertTrue(result["slot_verified"])
        self.assertTrue(result["identity_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["rejection_reasons"], [])
        self.assertEqual(result["slot"], 72254502)

    def test_account_mismatch_fails_closed(self):
        item = observation()
        item["account"] = "OtherVault"
        result = verify_x1_rpc_token_account_identity(
            item,
            expected_account=ACCOUNT,
            expected_mint=MINT,
            expected_authority=AUTHORITY,
        )

        self.assertFalse(result["identity_verified"])
        self.assertIn("account_identity_mismatch", result["rejection_reasons"])

    def test_mint_mismatch_fails_closed(self):
        item = observation()
        item["mint"] = "OtherMint"
        result = verify_x1_rpc_token_account_identity(
            item,
            expected_account=ACCOUNT,
            expected_mint=MINT,
            expected_authority=AUTHORITY,
        )

        self.assertFalse(result["mint_verified"])
        self.assertFalse(result["identity_verified"])
        self.assertIn("mint_identity_mismatch", result["rejection_reasons"])

    def test_authority_mismatch_fails_closed(self):
        item = observation()
        item["authority"] = "OtherAuthority"
        result = verify_x1_rpc_token_account_identity(
            item,
            expected_account=ACCOUNT,
            expected_mint=MINT,
            expected_authority=AUTHORITY,
        )

        self.assertFalse(result["authority_verified"])
        self.assertFalse(result["identity_verified"])
        self.assertIn("authority_identity_mismatch", result["rejection_reasons"])

    def test_wrong_rpc_source_fails_closed(self):
        item = observation()
        item["source"] = "Other RPC"
        result = verify_x1_rpc_token_account_identity(
            item,
            expected_account=ACCOUNT,
            expected_mint=MINT,
            expected_authority=AUTHORITY,
        )

        self.assertFalse(result["identity_verified"])
        self.assertIn("rpc_source_mismatch", result["rejection_reasons"])

    def test_wrong_rpc_method_fails_closed(self):
        item = observation()
        item["method"] = "getBalance"
        result = verify_x1_rpc_token_account_identity(
            item,
            expected_account=ACCOUNT,
            expected_mint=MINT,
            expected_authority=AUTHORITY,
        )

        self.assertFalse(result["identity_verified"])
        self.assertIn("rpc_method_mismatch", result["rejection_reasons"])

    def test_wrong_encoding_fails_closed(self):
        item = observation()
        item["encoding"] = "base64"
        result = verify_x1_rpc_token_account_identity(
            item,
            expected_account=ACCOUNT,
            expected_mint=MINT,
            expected_authority=AUTHORITY,
        )

        self.assertFalse(result["identity_verified"])
        self.assertIn("rpc_encoding_mismatch", result["rejection_reasons"])

    def test_invalid_slot_fails_closed(self):
        item = observation()
        item["slot"] = True
        result = verify_x1_rpc_token_account_identity(
            item,
            expected_account=ACCOUNT,
            expected_mint=MINT,
            expected_authority=AUTHORITY,
        )

        self.assertFalse(result["slot_verified"])
        self.assertFalse(result["identity_verified"])
        self.assertIn("rpc_slot_invalid", result["rejection_reasons"])

    def test_unparsed_observation_fails_closed(self):
        item = observation()
        item["token_account_fields_parsed"] = False
        result = verify_x1_rpc_token_account_identity(
            item,
            expected_account=ACCOUNT,
            expected_mint=MINT,
            expected_authority=AUTHORITY,
        )

        self.assertFalse(result["identity_verified"])
        self.assertIn("token_account_fields_unparsed", result["rejection_reasons"])

    def test_expected_identity_values_are_required(self):
        with self.assertRaisesRegex(ValueError, "expected_mint must not be empty"):
            verify_x1_rpc_token_account_identity(
                observation(),
                expected_account=ACCOUNT,
                expected_mint=" ",
                expected_authority=AUTHORITY,
            )

    def test_observation_must_be_mapping(self):
        with self.assertRaisesRegex(TypeError, "observation must be a mapping"):
            verify_x1_rpc_token_account_identity(
                [],
                expected_account=ACCOUNT,
                expected_mint=MINT,
                expected_authority=AUTHORITY,
            )


if __name__ == "__main__":
    unittest.main()
