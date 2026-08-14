import unittest

from liquidity_scout.services import build_tokenomics_report
from liquidity_scout.tokenomics import X1RPCError


class TokenomicsServiceTests(unittest.TestCase):
    def test_verified_supply_and_active_authorities(self):
        report = build_tokenomics_report(
            "MintA",
            symbol="TEST",
            name="Test Token",
            rpc_url="https://rpc.example",
            get_token_supply=lambda mint, **kwargs: {
                "raw_supply": "42500000",
                "decimals": 6,
                "total_supply": "42.5",
                "supply_verified": True,
                "source": "X1 RPC getTokenSupply",
            },
            get_mint_info=lambda mint, **kwargs: {
                "mint_authority": "MintAuthorityA",
                "mint_authority_verified": True,
                "freeze_authority": "FreezeAuthorityA",
                "freeze_authority_verified": True,
                "source": "X1 RPC getAccountInfo(jsonParsed)",
            },
        )

        self.assertEqual(report["mint"], "MintA")
        self.assertEqual(report["symbol"], "TEST")
        self.assertEqual(report["current_total_supply"], "42.5")
        self.assertEqual(report["raw_supply"], "42500000")
        self.assertEqual(report["decimals"], 6)
        self.assertTrue(report["supply_verified"])
        self.assertEqual(report["mint_authority_state"], "active")
        self.assertEqual(report["freeze_authority_state"], "active")
        self.assertTrue(report["future_minting_possible"])
        self.assertEqual(report["unavailable_reasons"], [])

    def test_verified_null_authorities_preserve_revoked_and_none_states(self):
        report = build_tokenomics_report(
            "MintA",
            get_token_supply=lambda mint, **kwargs: {
                "raw_supply": "1000000",
                "decimals": 6,
                "total_supply": "1",
                "supply_verified": True,
                "source": "supply",
            },
            get_mint_info=lambda mint, **kwargs: {
                "mint_authority": None,
                "mint_authority_verified": True,
                "freeze_authority": None,
                "freeze_authority_verified": True,
                "source": "mint",
            },
        )

        self.assertEqual(report["mint_authority_state"], "revoked")
        self.assertEqual(report["freeze_authority_state"], "none")
        self.assertFalse(report["future_minting_possible"])

    def test_unverified_authorities_are_unavailable_not_revoked(self):
        report = build_tokenomics_report(
            "MintA",
            get_token_supply=lambda mint, **kwargs: {
                "raw_supply": "1000000",
                "decimals": 6,
                "total_supply": "1",
                "supply_verified": True,
                "source": "supply",
            },
            get_mint_info=lambda mint, **kwargs: {
                "mint_authority": None,
                "mint_authority_verified": False,
                "freeze_authority": None,
                "freeze_authority_verified": False,
                "source": "mint",
            },
        )

        self.assertEqual(report["mint_authority_state"], "unavailable")
        self.assertEqual(report["freeze_authority_state"], "unavailable")
        self.assertIsNone(report["future_minting_possible"])
        self.assertIn("mint_authority_unverified", report["unavailable_reasons"])
        self.assertIn("freeze_authority_unverified", report["unavailable_reasons"])

    def test_explicit_zero_supply_is_verified_not_missing(self):
        report = build_tokenomics_report(
            "MintZero",
            get_token_supply=lambda mint, **kwargs: {
                "raw_supply": "0",
                "decimals": 9,
                "total_supply": "0",
                "supply_verified": True,
                "source": "supply",
            },
            get_mint_info=lambda mint, **kwargs: {
                "mint_authority": None,
                "mint_authority_verified": True,
                "freeze_authority": None,
                "freeze_authority_verified": True,
                "source": "mint",
            },
        )

        self.assertEqual(report["current_total_supply"], "0")
        self.assertEqual(report["raw_supply"], "0")
        self.assertTrue(report["supply_verified"])
        self.assertNotIn("current_supply_unverified", report["unavailable_reasons"])

    def test_rpc_failures_preserve_unavailable_state(self):
        def fail_supply(mint, **kwargs):
            raise X1RPCError("supply unavailable")

        def fail_mint(mint, **kwargs):
            raise X1RPCError("mint unavailable")

        report = build_tokenomics_report(
            "MintA",
            get_token_supply=fail_supply,
            get_mint_info=fail_mint,
        )

        self.assertIsNone(report["current_total_supply"])
        self.assertFalse(report["supply_verified"])
        self.assertEqual(report["mint_authority_state"], "unavailable")
        self.assertEqual(report["freeze_authority_state"], "unavailable")
        self.assertEqual(
            report["unavailable_reasons"],
            ["current_supply_rpc_unavailable", "mint_account_rpc_unavailable"],
        )

    def test_current_supply_never_becomes_circulating_or_maximum_supply(self):
        report = build_tokenomics_report(
            "MintA",
            get_token_supply=lambda mint, **kwargs: {
                "raw_supply": "1000000",
                "decimals": 6,
                "total_supply": "1",
                "supply_verified": True,
                "source": "supply",
            },
            get_mint_info=lambda mint, **kwargs: {
                "mint_authority": None,
                "mint_authority_verified": True,
                "freeze_authority": None,
                "freeze_authority_verified": True,
                "source": "mint",
            },
        )

        self.assertIsNone(report["circulating_supply"])
        self.assertFalse(report["circulating_supply_verified"])
        self.assertIsNone(report["maximum_supply"])
        self.assertFalse(report["maximum_supply_verified"])

    def test_missing_mint_is_rejected_before_rpc(self):
        with self.assertRaisesRegex(ValueError, "Token mint is required"):
            build_tokenomics_report("   ")


if __name__ == "__main__":
    unittest.main()
