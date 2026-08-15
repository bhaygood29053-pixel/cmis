import unittest

from liquidity_scout.services import build_tokenomics_report
from liquidity_scout.tokenomics import X1RPCError


MINT = "ReferenceMint"


def supply_record(*, decimals=6, total_supply="100", raw_supply="100000000"):
    return {
        "raw_supply": raw_supply,
        "decimals": decimals,
        "total_supply": total_supply,
        "supply_verified": True,
        "source": "X1 RPC getTokenSupply",
    }


def mint_record(*, mint_authority=None, freeze_authority=None, decimals=6):
    return {
        "mint_authority": mint_authority,
        "mint_authority_verified": True,
        "freeze_authority": freeze_authority,
        "freeze_authority_verified": True,
        "decimals": decimals,
        "source": "X1 RPC getAccountInfo(jsonParsed)",
    }


def activity_record(
    *,
    minted_raw="1000000",
    burned_raw="2500000",
    minted_tokens="1",
    burned_tokens="2.5",
    net_raw="-1500000",
    net_tokens="-1.5",
    coverage_verified=True,
    activity_verified=True,
    coverage_scope="bounded",
):
    return {
        "mint": MINT,
        "decimals": 6,
        "mint_events_observed": 1,
        "burn_events_observed": 1,
        "minted_raw_observed": minted_raw,
        "burned_raw_observed": burned_raw,
        "minted_tokens_observed": minted_tokens,
        "burned_tokens_observed": burned_tokens,
        "coverage": {
            "signatures_scanned": 2,
            "transactions_retrieved": 2 if coverage_verified else 1,
            "rpc_errors": 0 if coverage_verified else 1,
            "selection_complete": coverage_verified,
            "history_exhausted": False,
            "max_signatures": 2,
            "coverage_scope": coverage_scope,
        },
        "coverage_scope": coverage_scope,
        "coverage_verified": coverage_verified,
        "activity_verified": activity_verified,
        "lifetime_coverage_verified": False,
        "lifetime_coverage_reason": "scanner_window_is_not_lifetime_proof",
        "net_issuance_raw": net_raw,
        "net_issuance_tokens": net_tokens,
        "scan_id": 1,
        "source": "X1 RPC parsed token instructions",
        "storage": "standalone SQLite token activity DB",
    }


def report(*, supply=None, mint=None, activity=None):
    return build_tokenomics_report(
        MINT,
        get_token_supply=lambda _mint, **kwargs: (
            supply if supply is not None else supply_record()
        ),
        get_mint_info=lambda _mint, **kwargs: (
            mint if mint is not None else mint_record()
        ),
        activity_report=activity,
    )


class Phase3TokenomicsSignoffTests(unittest.TestCase):
    """Deterministic Phase 3 acceptance profiles; not live-token assertions."""

    def test_revoked_authority_burn_heavy_profile(self):
        result = report(activity=activity_record())

        self.assertTrue(result["supply_verified"])
        self.assertEqual(result["mint_authority_state"], "revoked")
        self.assertFalse(result["future_minting_possible"])
        self.assertTrue(result["token_activity"]["activity_verified"])
        self.assertTrue(result["token_activity"]["net_issuance_verified"])
        self.assertEqual(result["token_activity"]["net_issuance_tokens"], "-1.5")
        self.assertEqual(result["token_activity"]["coverage_scope"], "bounded")
        self.assertFalse(result["token_activity"]["lifetime_coverage_verified"])

    def test_active_authority_mint_and_burn_profile(self):
        result = report(
            mint=mint_record(mint_authority="ActiveMintAuthority"),
            activity=activity_record(
                minted_raw="5000000",
                burned_raw="1250000",
                minted_tokens="5",
                burned_tokens="1.25",
                net_raw="3750000",
                net_tokens="3.75",
            ),
        )

        self.assertEqual(result["mint_authority_state"], "active")
        self.assertTrue(result["future_minting_possible"])
        self.assertTrue(result["token_activity"]["net_issuance_verified"])
        self.assertEqual(result["token_activity"]["net_issuance_tokens"], "3.75")
        self.assertFalse(result["token_activity"]["lifetime_coverage_verified"])

    def test_incomplete_scanner_coverage_preserves_observed_but_withholds_net(self):
        result = report(
            activity=activity_record(
                coverage_verified=False,
                activity_verified=False,
            )
        )
        activity = result["token_activity"]

        self.assertTrue(activity["available"])
        self.assertEqual(activity["minted_raw_observed"], "1000000")
        self.assertEqual(activity["burned_raw_observed"], "2500000")
        self.assertFalse(activity["coverage_verified"])
        self.assertFalse(activity["activity_verified"])
        self.assertFalse(activity["net_issuance_verified"])
        self.assertIsNone(activity["net_issuance_raw"])
        self.assertIsNone(activity["net_issuance_tokens"])
        self.assertIn(
            "token_activity_coverage_unverified",
            activity["verification_reasons"],
        )

    def test_rpc_unavailable_profile_fails_closed(self):
        def unavailable(_mint, **kwargs):
            raise X1RPCError("RPC unavailable")

        result = build_tokenomics_report(
            MINT,
            get_token_supply=unavailable,
            get_mint_info=unavailable,
        )

        self.assertFalse(result["supply_verified"])
        self.assertIsNone(result["current_total_supply"])
        self.assertEqual(result["mint_authority_state"], "unavailable")
        self.assertEqual(result["freeze_authority_state"], "unavailable")
        self.assertIsNone(result["future_minting_possible"])
        self.assertEqual(
            result["unavailable_reasons"],
            ["current_supply_rpc_unavailable", "mint_account_rpc_unavailable"],
        )

    def test_conflicting_rpc_decimals_profile_fails_closed(self):
        result = report(
            supply=supply_record(decimals=6),
            mint=mint_record(decimals=9),
            activity=activity_record(),
        )

        self.assertFalse(result["rpc_decimals_consistent"])
        self.assertFalse(result["supply_verified"])
        self.assertIsNone(result["current_total_supply"])
        self.assertEqual(result["raw_supply"], "100000000")
        self.assertIsNone(result["decimals"])
        self.assertIn("rpc_decimals_mismatch", result["unavailable_reasons"])

        activity = result["token_activity"]
        self.assertEqual(activity["minted_raw_observed"], "1000000")
        self.assertIsNone(activity["minted_tokens_observed"])
        self.assertFalse(activity["activity_verified"])
        self.assertFalse(activity["net_issuance_verified"])
        self.assertIsNone(activity["net_issuance_tokens"])
        self.assertIn(
            "token_activity_rpc_decimals_unverified",
            activity["verification_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
