import unittest

from liquidity_scout.services import (
    ERROR,
    OK,
    PARTIAL,
    UNAVAILABLE,
    build_tokenomics_response,
)
from liquidity_scout.tokenomics import X1RPCError


MINT = "MintA"
DAY = 24 * 60 * 60
NOW = 10_000_000


def supply_record(*, decimals=6, total_supply="42.5", raw_supply="42500000"):
    return {
        "raw_supply": raw_supply,
        "decimals": decimals,
        "total_supply": total_supply,
        "supply_verified": True,
        "source": "X1 RPC getTokenSupply",
    }


def mint_record(
    *,
    decimals=6,
    mint_authority=None,
    freeze_authority=None,
    mint_verified=True,
    freeze_verified=True,
):
    return {
        "mint_authority": mint_authority,
        "mint_authority_verified": mint_verified,
        "freeze_authority": freeze_authority,
        "freeze_authority_verified": freeze_verified,
        "decimals": decimals,
        "source": "X1 RPC getAccountInfo(jsonParsed)",
    }


def activity_report(**overrides):
    report = {
        "mint": MINT,
        "decimals": 6,
        "mint_events_observed": 2,
        "burn_events_observed": 1,
        "minted_raw_observed": "3000000",
        "burned_raw_observed": "1000000",
        "minted_tokens_observed": "3",
        "burned_tokens_observed": "1",
        "coverage": {
            "signatures_scanned": 3,
            "transactions_retrieved": 3,
            "rpc_errors": 0,
            "selection_complete": True,
            "history_exhausted": False,
            "max_signatures": 3,
            "time_coverage_verified": True,
            "time_coverage_reason": None,
            "coverage_start_time": NOW - (60 * DAY),
            "coverage_end_time": NOW,
            "observed_at": NOW,
            "observation_time_semantics": (
                "newest_selected_transaction_block_time"
            ),
        },
        "coverage_scope": "bounded",
        "coverage_verified": True,
        "time_coverage_verified": True,
        "time_coverage_reason": None,
        "coverage_start_time": NOW - (60 * DAY),
        "coverage_end_time": NOW,
        "observed_at": NOW,
        "observation_time_semantics": "newest_selected_transaction_block_time",
        "activity_verified": True,
        "lifetime_coverage_verified": False,
        "lifetime_coverage_reason": "bounded_window_only",
        "net_issuance_raw": "2000000",
        "net_issuance_tokens": "2",
        "scan_id": "scan-1",
        "source": "X1 RPC parsed token instructions",
        "storage": "sqlite",
        "events": [
            {
                "kind": "mint",
                "raw_amount": "1000000",
                "block_time": NOW - 100,
            },
            {
                "kind": "mint",
                "raw_amount": "2000000",
                "block_time": NOW - 200,
            },
            {
                "kind": "burn",
                "raw_amount": "1000000",
                "block_time": NOW - 300,
            },
        ],
    }
    report.update(overrides)
    return report


class CMISTokenomicsContractTests(unittest.TestCase):
    def _complete_response(self, **kwargs):
        return build_tokenomics_response(
            MINT,
            symbol="TEST",
            name="Test Token",
            get_token_supply=lambda mint, **call_kwargs: supply_record(),
            get_mint_info=lambda mint, **call_kwargs: mint_record(),
            activity_report=activity_report(),
            **kwargs,
        )

    def test_complete_bounded_tokenomics_is_ok_without_claiming_lifetime_coverage(self):
        response = self._complete_response()

        self.assertEqual(response["service"], "tokenomics")
        self.assertEqual(response["chain"], "x1")
        self.assertEqual(response["status"], OK)
        self.assertEqual(
            response["asset"],
            {"symbol": "TEST", "name": "Test Token", "mint": MINT},
        )
        self.assertEqual(response["data"]["current_total_supply"], "42.5")
        self.assertTrue(response["data"]["supply_verified"])
        self.assertEqual(response["data"]["mint_authority_state"], "revoked")
        self.assertEqual(response["data"]["freeze_authority_state"], "none")
        self.assertTrue(response["data"]["token_activity"]["activity_verified"])
        self.assertTrue(response["data"]["token_activity"]["time_coverage_verified"])
        self.assertEqual(response["data"]["token_activity"]["observed_at"], NOW)
        self.assertEqual(response["data"]["token_activity"]["coverage_scope"], "bounded")
        self.assertFalse(
            response["data"]["token_activity"]["lifetime_coverage_verified"]
        )
        burn_metrics = response["data"]["burn_metrics"]
        self.assertTrue(burn_metrics["available"])
        self.assertEqual(burn_metrics["status"], "partial")
        self.assertTrue(burn_metrics["window_metrics_complete"])
        self.assertEqual(burn_metrics["verified_burned_observed"], "1")
        self.assertEqual(burn_metrics["observed_at"], NOW)
        self.assertEqual(
            burn_metrics["windows"]["24h"]["burned_tokens"],
            "1",
        )
        self.assertEqual(
            burn_metrics["windows"]["24h"]["burn_to_emission_ratio"],
            "0.3333333333333333333333333333333333333333",
        )
        self.assertEqual(
            burn_metrics["windows"]["24h"]["issuance_state"],
            "INFLATIONARY",
        )
        self.assertEqual(response["confidence"]["verified_checks"], 4)
        self.assertEqual(response["confidence"]["total_checks"], 4)
        self.assertTrue(response["confidence"]["complete"])
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("lifetime_coverage_unverified", codes)
        self.assertIn("burn_metrics_partial", codes)
        self.assertIn("circulating_supply_unverified", codes)
        self.assertIn("maximum_supply_unverified", codes)

    def test_verified_active_authorities_are_still_successful_tokenomics_facts(self):
        response = build_tokenomics_response(
            MINT,
            get_token_supply=lambda mint, **kwargs: supply_record(),
            get_mint_info=lambda mint, **kwargs: mint_record(
                mint_authority="MintAuthorityA",
                freeze_authority="FreezeAuthorityA",
            ),
            activity_report=activity_report(),
        )

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["data"]["mint_authority_state"], "active")
        self.assertEqual(response["data"]["freeze_authority_state"], "active")
        self.assertTrue(response["data"]["future_minting_possible"])

    def test_missing_activity_is_partial_not_fabricated_zero_activity(self):
        response = build_tokenomics_response(
            MINT,
            get_token_supply=lambda mint, **kwargs: supply_record(),
            get_mint_info=lambda mint, **kwargs: mint_record(),
        )

        self.assertEqual(response["status"], PARTIAL)
        self.assertEqual(response["confidence"]["verified_checks"], 3)
        self.assertFalse(response["confidence"]["checks"]["token_activity_verified"])
        activity = response["data"]["token_activity"]
        self.assertFalse(activity["available"])
        self.assertIsNone(activity["mint_events_observed"])
        self.assertIsNone(activity["burn_events_observed"])
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("token_activity_not_supplied", codes)

    def test_conflicting_rpc_decimals_is_partial_and_withholds_scaled_facts(self):
        response = build_tokenomics_response(
            MINT,
            get_token_supply=lambda mint, **kwargs: supply_record(decimals=6),
            get_mint_info=lambda mint, **kwargs: mint_record(decimals=9),
            activity_report=activity_report(decimals=6),
        )

        self.assertEqual(response["status"], PARTIAL)
        self.assertFalse(response["data"]["supply_verified"])
        self.assertIsNone(response["data"]["current_total_supply"])
        self.assertEqual(response["data"]["raw_supply"], "42500000")
        self.assertFalse(response["data"]["rpc_decimals_consistent"])
        self.assertFalse(response["data"]["token_activity"]["activity_verified"])
        self.assertFalse(response["data"]["token_activity"]["net_issuance_verified"])
        self.assertIsNone(response["data"]["token_activity"]["net_issuance_tokens"])
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("rpc_decimals_mismatch", codes)
        self.assertIn("token_activity_rpc_decimals_unverified", codes)

    def test_missing_scanner_time_contract_keeps_burn_metrics_unavailable(self):
        activity = activity_report(
            time_coverage_verified=False,
            time_coverage_reason="selected_transaction_block_time_unavailable",
            coverage_start_time=None,
            coverage_end_time=None,
            observed_at=None,
            observation_time_semantics=None,
        )
        activity["coverage"] = dict(activity["coverage"])
        activity["coverage"].update({
            "time_coverage_verified": False,
            "time_coverage_reason": "selected_transaction_block_time_unavailable",
            "coverage_start_time": None,
            "coverage_end_time": None,
            "observed_at": None,
            "observation_time_semantics": None,
        })

        response = build_tokenomics_response(
            MINT,
            get_token_supply=lambda mint, **kwargs: supply_record(),
            get_mint_info=lambda mint, **kwargs: mint_record(),
            activity_report=activity,
        )

        self.assertEqual(response["status"], OK)
        self.assertFalse(response["data"]["burn_metrics"]["available"])
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("burn_metrics_unavailable", codes)
    def test_rpc_failure_with_no_verified_activity_is_unavailable(self):
        def fail_supply(mint, **kwargs):
            raise X1RPCError("supply unavailable")

        def fail_mint(mint, **kwargs):
            raise X1RPCError("mint unavailable")

        response = build_tokenomics_response(
            MINT,
            get_token_supply=fail_supply,
            get_mint_info=fail_mint,
        )

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertEqual(response["confidence"]["verified_checks"], 0)
        self.assertIsNone(response["data"]["current_total_supply"])
        self.assertEqual(response["data"]["mint_authority_state"], "unavailable")
        self.assertEqual(response["data"]["freeze_authority_state"], "unavailable")
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("current_supply_rpc_unavailable", codes)
        self.assertIn("mint_account_rpc_unavailable", codes)

    def test_sources_preserve_rpc_and_scanner_traceability(self):
        response = self._complete_response()

        self.assertIn(
            {"source": "X1 RPC getTokenSupply", "role": "tokenomics.current_supply"},
            response["sources"],
        )
        self.assertIn(
            {
                "source": "X1 RPC getAccountInfo(jsonParsed)",
                "role": "tokenomics.mint_account",
            },
            response["sources"],
        )
        self.assertIn(
            {
                "source": "X1 RPC parsed token instructions",
                "role": "tokenomics.token_activity",
            },
            response["sources"],
        )
        self.assertIsNone(response["observed_at"])

    def test_missing_mint_is_explicit_error_without_rpc_call(self):
        response = build_tokenomics_response("   ")

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "token_mint_required")
        self.assertEqual(response["data"], {})

    def test_chain_and_explicit_observed_at_are_preserved(self):
        response = self._complete_response(
            chain="Solana",
            observed_at="2026-08-15T10:45:00Z",
        )

        self.assertEqual(response["chain"], "solana")
        self.assertEqual(response["observed_at"], "2026-08-15T10:45:00Z")
        self.assertEqual(response["status"], OK)


if __name__ == "__main__":
    unittest.main()
