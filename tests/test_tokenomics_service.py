import unittest

from liquidity_scout.services import build_tokenomics_report
from liquidity_scout.tokenomics import CIRCULATION_CONTRACT, X1RPCError


def circulation_report(*, total_raw="1000000", excluded_raw="250000"):
    return {
        "mint": "MintA",
        "decimals": 6,
        "contract": CIRCULATION_CONTRACT,
        "contract_verified": True,
        "contract_source": "verified exclusion policy registry",
        "exclusion_universe_complete": True,
        "exclusion_universe_source": "complete exclusion inventory",
        "total_supply_verified": True,
        "total_supply_raw": total_raw,
        "total_supply_source": "X1 RPC getTokenSupply",
        "observation_slot": 123456,
        "observed_at": 1700000000,
        "observation_time_verified": True,
        "source": "CMIS circulation evidence",
        "exclusions": [
            {
                "account": "ExcludedA",
                "mint": "MintA",
                "raw_balance": excluded_raw,
                "account_identity_verified": True,
                "balance_verified": True,
                "circulation_exclusion_verified": True,
                "exclusion_reason": "verified_non_circulating_treasury",
                "observation_slot": 123456,
                "source": "X1 RPC token account evidence",
            },
        ],
    }


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
                "decimals": 6,
                "source": "X1 RPC getAccountInfo(jsonParsed)",
            },
        )

        self.assertEqual(report["mint"], "MintA")
        self.assertEqual(report["symbol"], "TEST")
        self.assertEqual(report["current_total_supply"], "42.5")
        self.assertEqual(report["raw_supply"], "42500000")
        self.assertEqual(report["decimals"], 6)
        self.assertTrue(report["supply_verified"])
        self.assertTrue(report["current_total_supply_verified"])
        self.assertTrue(report["rpc_decimals_consistent"])
        self.assertEqual(
            report["rpc_decimal_sources"],
            {"token_supply": 6, "mint_account": 6},
        )
        self.assertEqual(report["mint_authority_state"], "active")
        self.assertEqual(report["freeze_authority_state"], "active")
        self.assertTrue(report["future_minting_possible"])
        self.assertEqual(report["unavailable_reasons"], [])

    def test_conflicting_rpc_decimals_withhold_scaled_supply_and_activity(self):
        activity_report = {
            "mint": "MintA",
            "decimals": 6,
            "mint_events_observed": 1,
            "burn_events_observed": 0,
            "minted_raw_observed": "1000000",
            "burned_raw_observed": "0",
            "minted_tokens_observed": "1",
            "burned_tokens_observed": "0",
            "coverage": {
                "signatures_scanned": 1,
                "transactions_retrieved": 1,
                "rpc_errors": 0,
                "selection_complete": True,
                "history_exhausted": False,
                "max_signatures": 1,
            },
            "coverage_verified": True,
            "activity_verified": True,
            "net_issuance_raw": "1000000",
            "net_issuance_tokens": "1",
            "source": "X1 RPC parsed token instructions",
        }

        report = build_tokenomics_report(
            "MintA",
            get_token_supply=lambda mint, **kwargs: {
                "raw_supply": "42500000",
                "decimals": 6,
                "total_supply": "42.5",
                "supply_verified": True,
                "source": "X1 RPC getTokenSupply",
            },
            get_mint_info=lambda mint, **kwargs: {
                "mint_authority": None,
                "mint_authority_verified": True,
                "freeze_authority": None,
                "freeze_authority_verified": True,
                "decimals": 9,
                "source": "X1 RPC getAccountInfo(jsonParsed)",
            },
            activity_report=activity_report,
        )

        self.assertFalse(report["rpc_decimals_consistent"])
        self.assertEqual(
            report["rpc_decimal_sources"],
            {"token_supply": 6, "mint_account": 9},
        )
        self.assertFalse(report["supply_verified"])
        self.assertIsNone(report["current_total_supply"])
        self.assertEqual(report["raw_supply"], "42500000")
        self.assertIsNone(report["decimals"])
        self.assertIn("rpc_decimals_mismatch", report["unavailable_reasons"])
        self.assertIn("current_supply_unverified", report["unavailable_reasons"])

        activity = report["token_activity"]
        self.assertTrue(activity["available"])
        self.assertEqual(activity["minted_raw_observed"], "1000000")
        self.assertIsNone(activity["minted_tokens_observed"])
        self.assertFalse(activity["activity_verified"])
        self.assertFalse(activity["net_issuance_verified"])
        self.assertIsNone(activity["net_issuance_tokens"])
        self.assertIn(
            "token_activity_rpc_decimals_unverified",
            activity["verification_reasons"],
        )

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
        self.assertIsNone(report["rpc_decimals_consistent"])

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

    def test_verified_exclusion_contract_exposes_circulating_supply(self):
        report = build_tokenomics_report(
            "MintA",
            get_token_supply=lambda mint, **kwargs: {
                "raw_supply": "1000000",
                "decimals": 6,
                "total_supply": "1",
                "supply_verified": True,
                "source": "X1 RPC getTokenSupply",
            },
            get_mint_info=lambda mint, **kwargs: {
                "mint_authority": None,
                "mint_authority_verified": True,
                "freeze_authority": None,
                "freeze_authority_verified": True,
                "decimals": 6,
                "source": "X1 RPC getAccountInfo(jsonParsed)",
            },
            circulating_supply_report=circulation_report(),
        )

        self.assertTrue(report["current_total_supply_verified"])
        self.assertTrue(report["circulating_supply_verified"])
        self.assertEqual(report["circulating_supply_raw"], "750000")
        self.assertEqual(report["circulating_supply"], "0.75")
        self.assertEqual(
            report["circulating_to_total_supply_ratio"],
            "0.75",
        )
        details = report["circulating_supply_details"]
        self.assertTrue(details["exclusion_universe_complete"])
        self.assertEqual(details["excluded_supply_raw"], "250000")
        self.assertEqual(details["exclusion_count"], 1)
        self.assertEqual(details["observation_slot"], 123456)
        self.assertEqual(details["observed_at"], 1700000000)
        self.assertIn(
            "X1 RPC token account evidence",
            details["sources"],
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
        self.assertEqual(
            report["circulating_supply_details"]["reason"],
            "circulating_supply_contract_not_supplied",
        )
        self.assertIsNone(report["maximum_supply"])
        self.assertFalse(report["maximum_supply_verified"])

    def test_missing_mint_is_rejected_before_rpc(self):
        with self.assertRaisesRegex(ValueError, "Token mint is required"):
            build_tokenomics_report("   ")


if __name__ == "__main__":
    unittest.main()
