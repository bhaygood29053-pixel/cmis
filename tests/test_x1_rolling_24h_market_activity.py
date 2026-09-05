import unittest

from liquidity_scout.providers.x1.rolling_24h_market_activity import (
    CONTRACT_VERSION,
    POOL_WINDOW_CONTRACT,
    evaluate_x1_rolling_24h_market_activity,
    reconstruct_x1_pool_24h_chain_activity,
)


POOL = "Pool111111111111111111111111111111111111111"
ASSET = "Asset11111111111111111111111111111111111111"
ASSET_VAULT = "AssetVault111111111111111111111111111111111"
QUOTE = "So11111111111111111111111111111111111111112"
QUOTE_VAULT = "QuoteVault111111111111111111111111111111111"
OWNER = "Owner1111111111111111111111111111111111111"
START = 1000
END = START + 86400


def identity():
    return {
        "chain": "x1",
        "pool_address": POOL,
        "asset_mint": ASSET,
        "asset_vault": ASSET_VAULT,
        "counter_mint": QUOTE,
        "counter_vault": QUOTE_VAULT,
        "shared_owner": OWNER,
        "identity_verified": True,
    }


def market(*, volume=0, transactions=0):
    return {
        "chain": "x1",
        "asset": {"mint": ASSET, "symbol": "TST"},
        "data": {
            "mint": ASSET,
            "volume_24h_usd": volume,
            "transactions_24h": transactions,
            "lp_count": 1,
            "contributing_pools": [
                {
                    "address": POOL,
                    "volume_24h_usd": volume,
                    "transactions_24h": transactions,
                }
            ],
            "completeness": {
                "volume_24h": True,
                "transactions_24h": True,
            },
        },
    }


def scope():
    return {
        "contract_version": "x1_ninja_current_pool_scope/v1",
        "chain": "x1",
        "asset_mint": ASSET,
        "market_contributing_pool_addresses": [POOL],
        "current_catalog_exact_mint_pool_addresses": [POOL],
        "market_pool_count": 1,
        "current_catalog_exact_mint_pool_count": 1,
        "provider_scoped_pool_universe_verified": True,
        "global_xdex_pool_universe_verified": False,
        "execution_authorized": False,
    }


def zero_window():
    return {
        "contract_version": POOL_WINDOW_CONTRACT,
        "chain": "x1",
        "pool_address": POOL,
        "asset_mint": ASSET,
        "counter_mint": QUOTE,
        "requested_window": {
            "start_epoch": str(START),
            "end_epoch": str(END),
            "duration_seconds": "86400",
        },
        "history_range_proven": True,
        "history_integrity_verified": True,
        "all_successful_transactions_verified": True,
        "all_pool_relevant_transactions_classified": True,
        "transactions_24h_window_coverage_verified": True,
        "swap_count_semantics_verified": True,
        "verified_transactions_24h": 0,
        "quote_volume_semantics_verified": True,
        "verified_quote_volume_24h": "0",
        "verified_quote_volume_unit": QUOTE,
        "usd_valuation_coverage_verified": True,
        "nonzero_volume_usd_semantics_verified": False,
        "usd_valuation_basis": "exact_zero_swap_volume_requires_no_price_conversion",
        "verified_volume_24h_usd": "0",
        "volume_24h_value_verified": True,
        "provider_fact_time_verified": False,
        "source_independence_verified": False,
        "execution_authorized": False,
    }


def nonzero_window_without_usd():
    row = zero_window()
    row.update(
        {
            "verified_transactions_24h": 1,
            "verified_quote_volume_24h": "2",
            "usd_valuation_coverage_verified": False,
            "usd_valuation_basis": "historical_quote_usd_valuation_incomplete",
            "verified_volume_24h_usd": None,
            "volume_24h_value_verified": False,
        }
    )
    return row


class X1Rolling24hMarketActivityTests(unittest.TestCase):
    def test_reconstructs_exact_zero_window_without_price_conversion(self):
        def scanner(*_args, **_kwargs):
            return {
                "range_proven": True,
                "integrity_verified": True,
                "entries": [],
            }

        result = reconstruct_x1_pool_24h_chain_activity(
            pool_identity=identity(),
            start_epoch=START,
            end_epoch=END,
            scanner=scanner,
        )

        self.assertEqual(result["contract_version"], POOL_WINDOW_CONTRACT)
        self.assertTrue(result["transactions_24h_window_coverage_verified"])
        self.assertEqual(result["verified_transactions_24h"], 0)
        self.assertTrue(result["usd_valuation_coverage_verified"])
        self.assertTrue(result["volume_24h_value_verified"])
        self.assertEqual(result["verified_volume_24h_usd"], "0")
        self.assertEqual(
            result["usd_valuation_basis"],
            "exact_zero_swap_volume_requires_no_price_conversion",
        )
        self.assertFalse(result["execution_authorized"])

    def test_nonzero_swap_count_is_verified_while_usd_volume_fails_closed(self):
        signature = "Sig111111111111111111111111111111111111111111111"
        transaction = {
            "transaction": {"signatures": [signature]},
        }

        def scanner(*_args, **_kwargs):
            return {
                "range_proven": True,
                "integrity_verified": True,
                "entries": [
                    {
                        "signature": signature,
                        "slot": 10,
                        "err": None,
                        "block_time": START + 100,
                    }
                ],
            }

        def fetcher(sig, *, rpc_url):
            self.assertEqual(sig, signature)
            self.assertTrue(rpc_url)
            return transaction

        def verifier(tx, *, signature, rpc_url, asset_mint):
            self.assertIs(tx, transaction)
            self.assertEqual(asset_mint, ASSET)
            return {
                "found": True,
                "succeeded": True,
                "slot": 10,
                "block_time": START + 100,
                "token_deltas": [
                    {
                        "account": ASSET_VAULT,
                        "mint": ASSET,
                        "owner": OWNER,
                        "delta_raw": -100,
                        "delta_ui": "-1",
                    },
                    {
                        "account": QUOTE_VAULT,
                        "mint": QUOTE,
                        "owner": OWNER,
                        "delta_raw": 200,
                        "delta_ui": "2",
                    },
                ],
            }

        def membership_prover(*, verification_report, pool_identity, transaction):
            return {
                "contract_version": "x1_transaction_pool_membership/v3",
                "transaction_signature": signature,
                "pool_address": POOL,
                "transaction_pool_membership_verified": True,
                "recognized_amm_invoked": True,
                "rejection_reasons": [],
            }

        result = reconstruct_x1_pool_24h_chain_activity(
            pool_identity=identity(),
            start_epoch=START,
            end_epoch=END,
            scanner=scanner,
            fetcher=fetcher,
            verifier=verifier,
            membership_prover=membership_prover,
        )

        self.assertTrue(result["transactions_24h_window_coverage_verified"])
        self.assertEqual(result["verified_transactions_24h"], 1)
        self.assertEqual(result["verified_quote_volume_24h"], "2")
        self.assertFalse(result["usd_valuation_coverage_verified"])
        self.assertFalse(result["volume_24h_value_verified"])
        self.assertIsNone(result["verified_volume_24h_usd"])

    def test_exact_zero_provider_values_verify_both_rolling_fields(self):
        result = evaluate_x1_rolling_24h_market_activity(
            market_envelope=market(volume=0, transactions=0),
            pool_scope_evidence=scope(),
            pool_windows=[zero_window()],
            evaluated_at=END,
        )

        self.assertEqual(result["contract_version"], CONTRACT_VERSION)
        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["transactions_24h_window_coverage_verified"])
        self.assertTrue(result["transactions_24h_semantics_verified"])
        self.assertTrue(result["transactions_24h_freshness_verified"])
        self.assertEqual(result["reconstructed_transactions_24h"], 0)
        self.assertTrue(result["volume_24h_window_coverage_verified"])
        self.assertTrue(result["volume_24h_semantics_verified"])
        self.assertTrue(result["volume_24h_freshness_verified"])
        self.assertEqual(result["reconstructed_volume_24h_usd"], "0")
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_nonzero_transaction_count_can_verify_while_volume_remains_unverified(self):
        result = evaluate_x1_rolling_24h_market_activity(
            market_envelope=market(volume=20, transactions=1),
            pool_scope_evidence=scope(),
            pool_windows=[nonzero_window_without_usd()],
            evaluated_at=END,
        )

        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["transactions_24h_freshness_verified"])
        self.assertFalse(result["volume_24h_freshness_verified"])
        self.assertIn(
            "historical_quote_usd_valuation_incomplete",
            result["pool_windows"][0]["usd_valuation_basis"],
        )

    def test_provider_transaction_count_mismatch_fails_closed(self):
        result = evaluate_x1_rolling_24h_market_activity(
            market_envelope=market(volume=0, transactions=1),
            pool_scope_evidence=scope(),
            pool_windows=[zero_window()],
            evaluated_at=END,
        )

        self.assertFalse(result["transactions_24h_freshness_verified"])
        self.assertIn(
            "provider_transactions_24h_does_not_match_chain_swap_count",
            result["failures"],
        )

    def test_stale_window_fails_both_fields(self):
        result = evaluate_x1_rolling_24h_market_activity(
            market_envelope=market(volume=0, transactions=0),
            pool_scope_evidence=scope(),
            pool_windows=[zero_window()],
            evaluated_at=END + 1000,
        )

        self.assertFalse(result["transactions_24h_freshness_verified"])
        self.assertFalse(result["volume_24h_freshness_verified"])
        self.assertIn(
            "rolling_window_not_current_exact_24h",
            result["failures"],
        )


if __name__ == "__main__":
    unittest.main()
