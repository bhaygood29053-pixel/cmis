import unittest

from liquidity_scout.providers.solana.pyth_push import (
    SOL_USD_CURRENT_ACCOUNT,
    SOL_USD_FEED_ID,
    WSOL_MINT,
)
from liquidity_scout.providers.x1.warp_bridged_supply_evidence import (
    CONTRACT as WARP_SUPPLY_CONTRACT,
    WSOL_ROUTE_ID,
    WSOL_X_DESTINATION_MINT,
)
from liquidity_scout.providers.x1.wsolx_value_basis import (
    WSOLXValueBasisError,
    build_wsolx_value_basis,
)
from liquidity_scout.services.cmis_xdex_program_window_activity import (
    XDEXProgramWindowActivityError,
    prove_xdex_program_asset_window_activity,
)


PROGRAM = "xdex-program"
ASSET = WSOL_X_DESTINATION_MINT
START = 1_000.0
END = 87_400.0


def scan(entries, *, range_proven=True, integrity=True):
    return {
        "range_proven": range_proven,
        "integrity_verified": integrity,
        "entries": entries,
        "rpc_errors": 0,
        "bound_reached": False,
    }


def verification(signature, slot, block_time, target=False):
    return {
        "found": True,
        "succeeded": True,
        "slot": slot,
        "block_time": block_time,
        "xdex_amm_invoked": True,
        "xendex_amm_invoked": False,
        "token_deltas": (
            [{"mint": ASSET, "delta_raw": "10"}]
            if target
            else [{"mint": "OtherMint", "delta_raw": "5"}]
        ),
    }


class ProgramWindowActivityTests(unittest.TestCase):
    def test_complete_program_trace_authorizes_zero_when_target_never_moves(self):
        entries = [
            {"signature": "a", "slot": 10, "block_time": END - 10, "err": None},
            {"signature": "b", "slot": 9, "block_time": END - 20, "err": None},
            {"signature": "c", "slot": 8, "block_time": END - 30, "err": {"x": 1}},
        ]
        verifications = {
            "a": verification("a", 10, END - 10),
            "b": verification("b", 9, END - 20),
        }

        result = prove_xdex_program_asset_window_activity(
            program_id=PROGRAM,
            asset_mint=ASSET,
            start_epoch=START,
            end_epoch=END,
            scanner=lambda *args, **kwargs: scan(entries),
            fetcher=lambda signature, **kwargs: {"signature": signature},
            verifier=lambda tx, signature, **kwargs: verifications[signature],
        )

        self.assertTrue(result["window_trace_complete_verified"])
        self.assertTrue(result["program_scoped_asset_activity_zero_verified"])
        self.assertTrue(result["volume_24h_window_coverage_verified"])
        self.assertTrue(result["volume_24h_semantics_verified"])
        self.assertEqual(result["verified_volume_24h_value"], "0")
        self.assertEqual(result["verified_volume_24h_unit"], "USD")
        self.assertEqual(result["failed_window_signature_count"], 1)
        self.assertFalse(result["global_onchain_pool_discovery_proven"])
        self.assertFalse(result["execution_authorized"])

    def test_target_mint_activity_keeps_volume_unavailable(self):
        entries = [
            {"signature": "a", "slot": 10, "block_time": END - 10, "err": None},
        ]
        result = prove_xdex_program_asset_window_activity(
            program_id=PROGRAM,
            asset_mint=ASSET,
            start_epoch=START,
            end_epoch=END,
            scanner=lambda *args, **kwargs: scan(entries),
            fetcher=lambda signature, **kwargs: {},
            verifier=lambda tx, signature, **kwargs: verification(
                signature, 10, END - 10, target=True
            ),
        )
        self.assertFalse(result["program_scoped_asset_activity_zero_verified"])
        self.assertFalse(result["volume_24h_semantics_verified"])
        self.assertIsNone(result["verified_volume_24h_value"])
        self.assertEqual(result["target_mint_activity_transaction_count"], 1)

    def test_fetch_gap_blocks_zero(self):
        entries = [
            {"signature": "a", "slot": 10, "block_time": END - 10, "err": None},
        ]
        result = prove_xdex_program_asset_window_activity(
            program_id=PROGRAM,
            asset_mint=ASSET,
            start_epoch=START,
            end_epoch=END,
            scanner=lambda *args, **kwargs: scan(entries),
            fetcher=lambda signature, **kwargs: None,
        )
        self.assertFalse(result["window_trace_complete_verified"])
        self.assertFalse(result["program_scoped_asset_activity_zero_verified"])
        self.assertIsNone(result["verified_volume_24h_value"])

    def test_incomplete_range_blocks_zero(self):
        result = prove_xdex_program_asset_window_activity(
            program_id=PROGRAM,
            asset_mint=ASSET,
            start_epoch=START,
            end_epoch=END,
            scanner=lambda *args, **kwargs: scan([], range_proven=False),
        )
        self.assertFalse(result["window_trace_complete_verified"])
        self.assertFalse(result["program_scoped_asset_activity_zero_verified"])

    def test_invalid_window_rejected(self):
        with self.assertRaises(XDEXProgramWindowActivityError):
            prove_xdex_program_asset_window_activity(
                program_id=PROGRAM,
                asset_mint=ASSET,
                start_epoch=END,
                end_epoch=START,
            )


def bridged_supply():
    return {
        "contract": WARP_SUPPLY_CONTRACT,
        "route_id": WSOL_ROUTE_ID,
        "current_backing_closure_verified": True,
        "bridged_supply_verified": True,
        "source_native_destination_wrapped_verified": True,
        "decimals_verified": True,
        "source_vault_balance_equals_destination_supply": True,
        "source": {
            "mint": WSOL_MINT,
            "identity_verified": True,
            "decimals": 9,
        },
        "destination": {
            "mint": WSOL_X_DESTINATION_MINT,
            "identity_verified": True,
            "decimals": 9,
        },
    }


def pyth_record(*, price="150", publish=10_000.0, completed=10_020.0):
    return {
        "chain": "solana",
        "source": "pyth_core_solana_push",
        "mint": WSOL_MINT,
        "mapping_verified": True,
        "feed_alias": "SOL/USD",
        "feed_id": SOL_USD_FEED_ID,
        "feed_id_verified": True,
        "account_address": SOL_USD_CURRENT_ACCOUNT,
        "account_owner_verified": True,
        "write_authority_matches_feed_account": True,
        "full_verification": True,
        "price_available": True,
        "price_usd": price,
        "publish_time_unix": publish,
        "fact_time_verified": True,
        "collection_started_at_unix": completed - 1,
        "collection_completed_at_unix": completed,
        "collection_time_verified": True,
        "price_integrity_verified": True,
        "unit": "USD_per_SOL",
        "price_subject": "SOL",
        "execution_authorized": False,
    }


class WSOLXValueBasisTests(unittest.TestCase):
    def test_builds_fresh_route_scoped_value_basis(self):
        result = build_wsolx_value_basis(
            bridged_supply=bridged_supply(),
            pyth_sol_usd=pyth_record(),
        )
        self.assertEqual(result["asset_mint"], WSOL_X_DESTINATION_MINT)
        self.assertEqual(result["source_asset_mint"], WSOL_MINT)
        self.assertEqual(result["price_per_token"], "150")
        self.assertEqual(result["unit"], "USD")
        self.assertTrue(result["comparable_value_basis_verified"])
        self.assertTrue(result["price_semantics_verified"])
        self.assertTrue(result["price_freshness_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["global_current_price_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_stale_pyth_price_rejected(self):
        with self.assertRaisesRegex(WSOLXValueBasisError, "not fresh"):
            build_wsolx_value_basis(
                bridged_supply=bridged_supply(),
                pyth_sol_usd=pyth_record(publish=10_000, completed=10_061),
            )

    def test_wrong_source_mint_rejected(self):
        bad = bridged_supply()
        bad["source"]["mint"] = "Wrong"
        with self.assertRaisesRegex(WSOLXValueBasisError, "canonical wrapped SOL"):
            build_wsolx_value_basis(
                bridged_supply=bad,
                pyth_sol_usd=pyth_record(),
            )

    def test_wrong_feed_rejected(self):
        bad = pyth_record()
        bad["feed_id"] = "00" * 32
        with self.assertRaisesRegex(WSOLXValueBasisError, "feed id mismatch"):
            build_wsolx_value_basis(
                bridged_supply=bridged_supply(),
                pyth_sol_usd=bad,
            )


if __name__ == "__main__":
    unittest.main()
