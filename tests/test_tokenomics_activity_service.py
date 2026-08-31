import unittest

from liquidity_scout.services import build_tokenomics_report


MINT = "MintA"
DAY = 24 * 60 * 60
NOW = 10_000_000


def supply_record(*, verified=True, decimals=6):
    if not verified:
        return {
            "raw_supply": None,
            "decimals": None,
            "total_supply": None,
            "supply_verified": False,
            "source": "X1 RPC getTokenSupply",
        }
    return {
        "raw_supply": "42500000",
        "decimals": decimals,
        "total_supply": "42.5",
        "supply_verified": True,
        "source": "X1 RPC getTokenSupply",
    }


def mint_record():
    return {
        "mint_authority": None,
        "mint_authority_verified": True,
        "freeze_authority": None,
        "freeze_authority_verified": True,
        "source": "X1 RPC getAccountInfo(jsonParsed)",
    }


def activity_report(**overrides):
    value = {
        "mint": MINT,
        "decimals": 6,
        "mint_events_observed": 2,
        "burn_events_observed": 1,
        "minted_raw_observed": "3000000",
        "burned_raw_observed": "1250000",
        "minted_tokens_observed": "3",
        "burned_tokens_observed": "1.25",
        "coverage": {
            "signatures_scanned": 2,
            "transactions_retrieved": 2,
            "rpc_errors": 0,
            "selection_complete": True,
            "history_exhausted": False,
            "max_signatures": 2,
            "coverage_scope": "bounded",
            "time_coverage_verified": True,
            "time_coverage_reason": None,
            "coverage_start_time": NOW - (60 * DAY),
            "coverage_end_time": NOW,
            "observed_at": NOW,
            "observation_time_semantics": (
                "newest_selected_transaction_block_time"
            ),
            "lifetime_coverage_verified": False,
            "lifetime_coverage_reason": "bounded_signature_window",
        },
        "coverage_scope": "bounded",
        "coverage_verified": True,
        "time_coverage_verified": True,
        "time_coverage_reason": None,
        "coverage_start_time": NOW - (60 * DAY),
        "coverage_end_time": NOW,
        "observed_at": NOW,
        "observation_time_semantics": "newest_selected_transaction_block_time",
        "lifetime_coverage_verified": False,
        "lifetime_coverage_reason": "bounded_signature_window",
        "amounts_verified": True,
        "activity_verified": True,
        "net_issuance_raw": "1750000",
        "net_issuance_tokens": "1.75",
        "scan_id": 42,
        "source": "X1 RPC parsed token instructions",
        "storage": "standalone SQLite token activity DB",
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
                "raw_amount": "1250000",
                "block_time": NOW - 300,
            },
        ],
    }
    value.update(overrides)
    return value


def report_with_activity(activity, *, supply=None):
    return build_tokenomics_report(
        MINT,
        get_token_supply=lambda mint, **kwargs: (
            supply if supply is not None else supply_record()
        ),
        get_mint_info=lambda mint, **kwargs: mint_record(),
        activity_report=activity,
    )


class TokenomicsActivityServiceTests(unittest.TestCase):
    def test_verified_bounded_activity_exposes_scope_without_lifetime_claim(self):
        report = report_with_activity(activity_report())
        activity = report["token_activity"]

        self.assertTrue(activity["available"])
        self.assertEqual(activity["coverage_scope"], "bounded")
        self.assertTrue(activity["coverage_verified"])
        self.assertFalse(activity["lifetime_coverage_verified"])
        self.assertEqual(
            activity["lifetime_coverage_reason"],
            "bounded_signature_window",
        )
        self.assertTrue(activity["scanner_activity_verified"])
        self.assertTrue(activity["activity_verified"])
        self.assertTrue(activity["net_issuance_verified"])
        self.assertEqual(activity["minted_tokens_observed"], "3")
        self.assertEqual(activity["burned_tokens_observed"], "1.25")
        self.assertEqual(activity["net_issuance_raw"], "1750000")
        self.assertEqual(activity["net_issuance_tokens"], "1.75")
        self.assertEqual(activity["scan_id"], 42)
        self.assertEqual(activity["verification_reasons"], [])
        self.assertEqual(
            report["sources"]["token_activity"],
            "X1 RPC parsed token instructions",
        )
        burn_metrics = report["burn_metrics"]
        self.assertTrue(burn_metrics["available"])
        self.assertEqual(burn_metrics["status"], "partial")
        self.assertTrue(burn_metrics["window_metrics_complete"])
        self.assertEqual(burn_metrics["observed_at"], NOW)
        self.assertFalse(burn_metrics["lifetime_total_burn_verified"])
        self.assertEqual(burn_metrics["verified_burned_observed"], "1.25")
        self.assertEqual(burn_metrics["verified_burned_raw_observed"], "1250000")
        self.assertEqual(
            burn_metrics["windows"]["24h"]["burned_tokens"],
            "1.25",
        )
        self.assertEqual(
            burn_metrics["windows"]["24h"]["minted_tokens"],
            "3",
        )
        self.assertEqual(
            burn_metrics["windows"]["24h"]["issuance_state"],
            "INFLATIONARY",
        )
        self.assertEqual(
            burn_metrics["valuation"]["status"],
            "unavailable",
        )
        self.assertEqual(
            burn_metrics["circulating_supply"]["status"],
            "unavailable",
        )

    def test_service_does_not_upgrade_scanner_lifetime_claim(self):
        activity = activity_report(
            coverage_scope="rpc_history_exhausted",
            lifetime_coverage_verified=True,
            lifetime_coverage_reason=None,
        )
        activity["coverage"] = dict(activity["coverage"])
        activity["coverage"]["coverage_scope"] = "rpc_history_exhausted"
        activity["coverage"]["lifetime_coverage_verified"] = True

        report = report_with_activity(activity)["token_activity"]

        self.assertEqual(report["coverage_scope"], "rpc_history_exhausted")
        self.assertTrue(report["coverage_verified"])
        self.assertTrue(report["activity_verified"])
        self.assertFalse(report["lifetime_coverage_verified"])
        self.assertEqual(
            report["lifetime_coverage_reason"],
            "token_activity_lifetime_claim_not_independently_verified",
        )

    def test_incomplete_coverage_preserves_observed_totals_but_withholds_net(self):
        activity = activity_report(
            coverage_verified=False,
            activity_verified=False,
            net_issuance_raw="1500000",
            net_issuance_tokens="1.5",
        )

        report = report_with_activity(activity)["token_activity"]

        self.assertTrue(report["available"])
        self.assertEqual(report["minted_raw_observed"], "3000000")
        self.assertEqual(report["burned_raw_observed"], "1250000")
        self.assertEqual(report["minted_tokens_observed"], "3")
        self.assertEqual(report["burned_tokens_observed"], "1.25")
        self.assertFalse(report["activity_verified"])
        self.assertFalse(report["net_issuance_verified"])
        self.assertIsNone(report["net_issuance_raw"])
        self.assertIsNone(report["net_issuance_tokens"])
        self.assertIn(
            "token_activity_coverage_unverified",
            report["verification_reasons"],
        )
        self.assertIn(
            "token_activity_scanner_unverified",
            report["verification_reasons"],
        )

    def test_missing_time_coverage_withholds_burn_metrics(self):
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

        report = report_with_activity(activity)

        self.assertTrue(report["token_activity"]["activity_verified"])
        self.assertFalse(report["token_activity"]["time_coverage_verified"])
        self.assertFalse(report["burn_metrics"]["available"])
        self.assertEqual(
            report["burn_metrics"]["reason"],
            "selected_transaction_block_time_unavailable",
        )

    def test_conflicting_time_metadata_withholds_burn_metrics(self):
        activity = activity_report()
        activity["coverage"] = dict(activity["coverage"])
        activity["coverage"]["observed_at"] = NOW - 1

        report = report_with_activity(activity)

        self.assertFalse(report["token_activity"]["time_coverage_verified"])
        self.assertEqual(
            report["token_activity"]["time_coverage_reason"],
            "token_activity_time_coverage_malformed",
        )
        self.assertFalse(report["burn_metrics"]["available"])

    def test_missing_nested_coverage_withholds_time_contract(self):
        activity = activity_report(coverage=None)

        report = report_with_activity(activity)

        self.assertFalse(report["token_activity"]["time_coverage_verified"])
        self.assertEqual(
            report["token_activity"]["time_coverage_reason"],
            "token_activity_time_coverage_malformed",
        )
        self.assertFalse(report["burn_metrics"]["available"])
    def test_missing_event_payload_withholds_burn_metrics(self):
        activity = activity_report()
        activity.pop("events")

        report = report_with_activity(activity)

        self.assertTrue(report["token_activity"]["time_coverage_verified"])
        self.assertFalse(report["burn_metrics"]["available"])
        self.assertEqual(
            report["burn_metrics"]["reason"],
            "token_activity_events_not_supplied",
        )
    def test_event_summary_mismatch_withholds_burn_metrics(self):
        activity = activity_report(
            burned_raw_observed="999999",
        )

        report = report_with_activity(activity)

        self.assertTrue(report["token_activity"]["activity_verified"])
        self.assertFalse(report["burn_metrics"]["available"])
        self.assertEqual(
            report["burn_metrics"]["reason"],
            "token_activity_event_summary_mismatch",
        )
    def test_activity_for_different_mint_is_rejected_fail_closed(self):
        report = report_with_activity(
            activity_report(mint="OtherMint")
        )["token_activity"]

        self.assertFalse(report["available"])
        self.assertFalse(report["activity_verified"])
        self.assertFalse(report["net_issuance_verified"])
        self.assertFalse(report["lifetime_coverage_verified"])
        self.assertIsNone(report["minted_raw_observed"])
        self.assertIsNone(report["net_issuance_tokens"])
        self.assertEqual(
            report["verification_reasons"],
            ["token_activity_mint_mismatch"],
        )

    def test_decimal_mismatch_preserves_raw_observations_only(self):
        report = report_with_activity(
            activity_report(
                decimals=9,
                minted_tokens_observed="0.003",
                burned_tokens_observed="0.00125",
                net_issuance_tokens="0.00175",
            )
        )["token_activity"]

        self.assertTrue(report["available"])
        self.assertEqual(report["minted_raw_observed"], "3000000")
        self.assertEqual(report["burned_raw_observed"], "1250000")
        self.assertIsNone(report["minted_tokens_observed"])
        self.assertIsNone(report["burned_tokens_observed"])
        self.assertFalse(report["activity_verified"])
        self.assertFalse(report["net_issuance_verified"])
        self.assertIsNone(report["net_issuance_tokens"])
        self.assertIn(
            "token_activity_decimals_mismatch",
            report["verification_reasons"],
        )

    def test_verified_zero_net_issuance_is_not_treated_as_missing(self):
        report = report_with_activity(
            activity_report(
                minted_raw_observed="1000000",
                burned_raw_observed="1000000",
                minted_tokens_observed="1",
                burned_tokens_observed="1",
                net_issuance_raw="0",
                net_issuance_tokens="0",
            )
        )["token_activity"]

        self.assertTrue(report["activity_verified"])
        self.assertTrue(report["net_issuance_verified"])
        self.assertEqual(report["net_issuance_raw"], "0")
        self.assertEqual(report["net_issuance_tokens"], "0")

    def test_activity_not_supplied_does_not_change_existing_rpc_unavailable_reasons(self):
        report = build_tokenomics_report(
            MINT,
            get_token_supply=lambda mint, **kwargs: supply_record(),
            get_mint_info=lambda mint, **kwargs: mint_record(),
        )

        self.assertEqual(report["unavailable_reasons"], [])
        self.assertFalse(report["token_activity"]["available"])
        self.assertFalse(report["token_activity"]["lifetime_coverage_verified"])
        self.assertEqual(
            report["token_activity"]["verification_reasons"],
            ["token_activity_not_supplied"],
        )

    def test_unverified_rpc_decimals_prevent_verified_activity_claim(self):
        report = report_with_activity(
            activity_report(),
            supply=supply_record(verified=False),
        )["token_activity"]

        self.assertTrue(report["available"])
        self.assertEqual(report["minted_raw_observed"], "3000000")
        self.assertEqual(report["burned_raw_observed"], "1250000")
        self.assertIsNone(report["minted_tokens_observed"])
        self.assertIsNone(report["burned_tokens_observed"])
        self.assertFalse(report["activity_verified"])
        self.assertFalse(report["net_issuance_verified"])
        self.assertIsNone(report["net_issuance_tokens"])
        self.assertIn(
            "token_activity_rpc_decimals_unverified",
            report["verification_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
