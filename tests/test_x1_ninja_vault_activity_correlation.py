import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.ninja_vault_activity_correlation import (
    aggregate_vault_activity_evidence,
    verify_vault_activity_transition,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    TokenDelta,
    VerificationReport,
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    WXNT_MINT,
)


POOL = "Pool111"
ASSET = "Asset111"
VAULT_XNT = "VaultXnt111"
VAULT_ASSET = "VaultAsset111"
OWNER = "Owner111"


def snapshot(price, base, quote, *, lower=None, upper=None):
    if lower is not None:
        bracket = {
            "before": {"slot": lower - 1},
            "after": {"slot": lower},
        }
    else:
        bracket = {
            "before": {"slot": upper},
            "after": {"slot": upper + 1},
        }
    return {
        "rpc_slot_bracket": bracket,
        "provider_timestamp_candidates": {
            "global_lastUpdated_raw": "global",
        },
        "pools": [{
            "pool_address": POOL,
            "status": "ok",
            "provider": {
                "priceNative": price,
                "pooledBase": base,
                "pooledQuote": quote,
                "lastSyncedAt_raw": "row",
            },
        }],
    }


def structural(**kwargs):
    return {
        "decoded_state": {
            "mint_0": WXNT_MINT,
            "mint_1": ASSET,
            "vault_0": VAULT_XNT,
            "vault_1": VAULT_ASSET,
        },
        "shared_vault_authority": OWNER,
        "summary": {"pool_state_structural_role_verified": True},
    }


def delta(account, mint, amount):
    value = Decimal(amount)
    return TokenDelta(
        account_index=1,
        account=account,
        owner=OWNER,
        mint=mint,
        decimals=9,
        pre_amount_raw=0,
        post_amount_raw=0,
        delta_raw=int(value * Decimal(1_000_000_000)),
        delta_ui=value,
        post_ui=Decimal("1"),
    )


def report(signature, *, asset="0", xnt="0", xdex=False, slot=12):
    deltas = []
    if Decimal(asset) != 0:
        deltas.append(delta(VAULT_ASSET, ASSET, asset))
    if Decimal(xnt) != 0:
        deltas.append(delta(VAULT_XNT, WXNT_MINT, xnt))
    return VerificationReport(
        signature=signature,
        rpc_url="rpc",
        found=True,
        succeeded=True,
        slot=slot,
        block_time=1000 + slot,
        block_time_iso=None,
        fee_lamports=1,
        primary_signer="Signer",
        dex_protocol="XDEX" if xdex else "UNKNOWN",
        xdex_amm_invoked=xdex,
        xendex_amm_invoked=False,
        xendex_staking_invoked=False,
        program_ids=[XDEX_MAINNET_OBSERVED_PROGRAM_ID] if xdex else [],
        token_deltas=deltas,
        signer_token_deltas=[],
        signer_native_xnt_delta=None,
        signer_native_xnt_delta_before_fee=None,
        inferred_side="UNKNOWN",
        inferred_asset_mint=None,
        inferred_quote_mint=None,
        inferred_quote_amount=None,
        pool_leg_match=None,
        verification_basis="TRANSACTION_ONLY",
        inference_reason="fixture",
        expected_side=None,
        expected_mint=None,
        expectation_match=None,
        verification_level="ONCHAIN_CONFIRMED",
    )


def membership(**kwargs):
    return {
        "transaction_pool_membership_verified": True,
        "recognized_amm_instruction_count": 1,
        "selected_pool_instruction_count": 1,
    }


class VaultActivityCorrelationTests(unittest.TestCase):
    def test_direct_transfer_matches_provider_reserve_delta(self):
        before = snapshot("0.5", "100", "50", lower=10)
        after = snapshot("0.5", "110", "50", upper=13)

        def history(address, *, limit, rpc_url):
            if address == VAULT_ASSET:
                return [{
                    "signature": "transfer",
                    "slot": 12,
                    "err": None,
                    "block_time": 1012,
                    "confirmation_status": "confirmed",
                }]
            return []

        def tx_fetch(signature, *, rpc_url):
            return {
                "transaction": {
                    "signatures": [signature],
                    "message": {
                        "instructions": [{
                            "program": "spl-token",
                            "parsed": {
                                "type": "transferChecked",
                                "info": {
                                    "source": "UserToken",
                                    "destination": VAULT_ASSET,
                                },
                            },
                        }],
                    },
                },
                "meta": {"innerInstructions": []},
            }

        def verifier(tx, *, signature, rpc_url):
            return report(signature, asset="10", slot=12)

        result = verify_vault_activity_transition(
            before=before,
            after=after,
            pool_address=POOL,
            structural_verifier=structural,
            signature_fetcher=history,
            transaction_fetcher=tx_fetch,
            transaction_verifier=verifier,
            membership_prover=membership,
            recognized_program_ids=(XDEX_MAINNET_OBSERVED_PROGRAM_ID,),
            rpc_url="rpc",
        )

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["vault_activity_correlated"])
        self.assertTrue(
            result["provider_reserve_delta_matches_vault_delta"]
        )
        self.assertEqual(
            result["transaction_classification_counts"],
            {"direct_token_transfer": 1},
        )
        self.assertFalse(result["price_only_update_observed"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_price_only_update_requires_no_vault_activity(self):
        before = snapshot("0.5", "100", "50", lower=10)
        after = snapshot("0.51", "100", "50", upper=13)

        def history(address, *, limit, rpc_url):
            return []

        result = verify_vault_activity_transition(
            before=before,
            after=after,
            pool_address=POOL,
            structural_verifier=structural,
            signature_fetcher=history,
            recognized_program_ids=(XDEX_MAINNET_OBSERVED_PROGRAM_ID,),
            rpc_url="rpc",
        )

        self.assertTrue(result["price_only_update_observed"])
        self.assertFalse(result["vault_activity_correlated"])
        self.assertEqual(result["verified_vault_transaction_count"], 0)
        self.assertFalse(result["catalog_price_active_reserve_link_verified"])

    def test_exact_xdex_swap_links_execution_price_and_reserve_deltas(self):
        before = snapshot("0.0019", "100", "50", lower=10)
        after = snapshot("0.002", "90", "50.02", upper=13)

        def history(address, *, limit, rpc_url):
            return [{
                "signature": "swap",
                "slot": 12,
                "err": None,
                "block_time": 1012,
                "confirmation_status": "confirmed",
            }]

        def tx_fetch(signature, *, rpc_url):
            return {
                "transaction": {
                    "signatures": [signature],
                    "message": {"instructions": []},
                },
                "meta": {"innerInstructions": []},
            }

        def verifier(tx, *, signature, rpc_url):
            return report(
                signature,
                asset="-10",
                xnt="0.02",
                xdex=True,
                slot=12,
            )

        result = verify_vault_activity_transition(
            before=before,
            after=after,
            pool_address=POOL,
            structural_verifier=structural,
            signature_fetcher=history,
            transaction_fetcher=tx_fetch,
            transaction_verifier=verifier,
            membership_prover=membership,
            recognized_program_ids=(XDEX_MAINNET_OBSERVED_PROGRAM_ID,),
            rpc_url="rpc",
        )

        self.assertTrue(result["vault_activity_correlated"])
        self.assertTrue(
            result["provider_reserve_delta_matches_vault_delta"]
        )
        self.assertEqual(
            result["transaction_classification_counts"],
            {"exact_xdex_swap": 1},
        )
        self.assertTrue(result["catalog_price_execution_link_verified"])
        self.assertEqual(result["catalog_price_execution_match_count"], 1)
        self.assertFalse(
            result["catalog_price_reserve_ratio_link_verified"]
        )

    def test_after_price_can_match_gross_reserve_ratio_independently(self):
        before = snapshot("0.49", "100", "50", lower=10)
        after = snapshot("0.5", "100", "50", upper=13)

        def history(address, *, limit, rpc_url):
            return []

        result = verify_vault_activity_transition(
            before=before,
            after=after,
            pool_address=POOL,
            structural_verifier=structural,
            signature_fetcher=history,
            recognized_program_ids=(XDEX_MAINNET_OBSERVED_PROGRAM_ID,),
            rpc_url="rpc",
        )

        self.assertTrue(
            result["catalog_price_reserve_ratio_link_verified"]
        )
        self.assertTrue(result["price_only_update_observed"])
        self.assertFalse(result["catalog_price_execution_link_verified"])

    def test_incomplete_vault_history_fails_closed(self):
        before = snapshot("0.5", "100", "50", lower=10)
        after = snapshot("0.51", "100", "50", upper=13)

        def history(address, *, limit, rpc_url):
            return [
                {
                    "signature": f"sig{i}",
                    "slot": 1000 + i,
                    "err": None,
                    "block_time": 2000 + i,
                }
                for i in range(limit)
            ]

        result = verify_vault_activity_transition(
            before=before,
            after=after,
            pool_address=POOL,
            structural_verifier=structural,
            signature_fetcher=history,
            recognized_program_ids=(XDEX_MAINNET_OBSERVED_PROGRAM_ID,),
            rpc_url="rpc",
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["vault_history_complete_for_window"])
        self.assertFalse(result["price_only_update_observed"])

    def test_aggregate_preserves_scoped_counts_without_price_promotion(self):
        events = [
            {
                "vault_history_complete_for_window": True,
                "vault_activity_correlated": i < 2,
                "provider_reserve_delta_matches_vault_delta": i < 3,
                "price_only_update_observed": i == 3,
                "catalog_price_execution_link_verified": i == 0,
                "catalog_price_reserve_ratio_link_verified": i == 4,
            }
            for i in range(5)
        ]
        result = aggregate_vault_activity_evidence(events)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["vault_activity_correlated_event_count"], 2)
        self.assertEqual(result["price_only_update_event_count"], 1)
        self.assertTrue(result["vault_activity_correlated_observed"])
        self.assertTrue(result["provider_reserve_delta_match_observed"])
        self.assertFalse(result["vault_activity_correlated"])
        self.assertFalse(
            result["provider_reserve_delta_matches_vault_delta"]
        )
        self.assertTrue(result["price_only_update_observed"])
        self.assertFalse(result["catalog_price_execution_link_verified"])
        self.assertFalse(
            result["catalog_price_reserve_ratio_link_verified"]
        )
        self.assertFalse(result["freshness_verified"])


if __name__ == "__main__":
    unittest.main()
