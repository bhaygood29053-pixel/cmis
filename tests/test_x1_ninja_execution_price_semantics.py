import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.ninja_execution_price_semantics import (
    aggregate_ninja_execution_price_samples,
    verify_ninja_trade_execution_price,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    TokenDelta,
    VerificationReport,
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    WXNT_MINT,
)


POOL = "Pool111"
ASSET = "Asset111"
VAULT_ASSET = "AssetVault111"
VAULT_XNT = "XntVault111"
OWNER = "Owner111"
SIG = "Sig111"


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


def tx_fetch(signature, **kwargs):
    return {
        "transaction": {
            "signatures": [signature],
            "message": {
                "accountKeys": ["Signer", POOL, VAULT_XNT, VAULT_ASSET],
                "instructions": [
                    {
                        "programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                        "accounts": ["Signer", POOL, VAULT_XNT, VAULT_ASSET],
                    }
                ],
            },
        },
        "meta": {"innerInstructions": []},
    }


def token_delta(account, mint, delta, post):
    return TokenDelta(
        account_index=1,
        account=account,
        owner=OWNER,
        mint=mint,
        decimals=9,
        pre_amount_raw=0,
        post_amount_raw=0,
        delta_raw=int(Decimal(delta) * Decimal(1_000_000_000)),
        delta_ui=Decimal(delta),
        post_ui=Decimal(post),
    )


def verification(tx, **kwargs):
    side = "BUY"
    if side == "BUY":
        asset = token_delta(VAULT_ASSET, ASSET, "-45.585834357", "337267.374174613")
        quote = token_delta(VAULT_XNT, WXNT_MINT, "0.019692091", "145.316639876")
    else:
        asset = token_delta(VAULT_ASSET, ASSET, "10", "337277.374174613")
        quote = token_delta(VAULT_XNT, WXNT_MINT, "-0.004", "145.312639876")

    class Leg:
        amount_match = True
        asset_account = VAULT_ASSET
        quote_account = VAULT_XNT

    return VerificationReport(
        signature=kwargs["signature"],
        rpc_url=kwargs["rpc_url"],
        found=True,
        succeeded=True,
        slot=123,
        block_time=456,
        block_time_iso=None,
        fee_lamports=1,
        primary_signer="Signer",
        dex_protocol="XDEX",
        xdex_amm_invoked=True,
        xendex_amm_invoked=False,
        xendex_staking_invoked=False,
        program_ids=[XDEX_MAINNET_OBSERVED_PROGRAM_ID],
        token_deltas=[asset, quote],
        signer_token_deltas=[],
        signer_native_xnt_delta=None,
        signer_native_xnt_delta_before_fee=None,
        inferred_side=side,
        inferred_asset_mint=ASSET,
        inferred_quote_mint=WXNT_MINT,
        inferred_quote_amount=abs(quote.delta_ui),
        pool_leg_match=Leg(),
        verification_basis="EXACT_POOL_LEG_AMOUNTS",
        inference_reason="fixture",
        expected_side=side,
        expected_mint=ASSET,
        expectation_match=True,
        verification_level="PROVIDER_SIDE_ONCHAIN_CONFIRMED",
    )


def membership(**kwargs):
    return {
        "transaction_pool_membership_verified": True,
        "rejection_reasons": [],
    }


class NinjaExecutionPriceTests(unittest.TestCase):
    def test_trade_price_matches_execution_not_post_reserve_ratio(self):
        row = {
            "poolAddress": POOL,
            "txHash": SIG,
            "type": "BUY",
            "amountToken": "45.585834357",
            "amountNative": "0.019692091",
            "priceNative": "0.0004319782949633428",
            "slot": 123,
            "timestamp": 456,
        }
        result = verify_ninja_trade_execution_price(
            pool_address=POOL,
            trade_row=row,
            current_pool_row={
                "address": POOL,
                "priceNative": "0.0004319782949633428",
            },
            structural_verifier=structural,
            transaction_fetcher=tx_fetch,
            transaction_verifier=verification,
            membership_prover=membership,
            recognized_program_ids=(XDEX_MAINNET_OBSERVED_PROGRAM_ID,),
        )

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["provider_amounts_match_exact_pool_leg"])
        self.assertTrue(result["trade_price_native_execution_semantics_verified"])
        self.assertTrue(
            result["comparisons"]["trade_priceNative_vs_execution_price"]["within_tolerance"]
        )
        self.assertFalse(
            result["comparisons"]["trade_priceNative_vs_post_trade_reserve_ratio"]["within_tolerance"]
        )
        self.assertTrue(
            result["current_pool_price_native_selected_trade_match_observed"]
        )
        self.assertFalse(
            result["current_pool_price_native_latest_trade_link_verified"]
        )
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_wrong_vault_sign_fails_closed(self):
        def wrong(tx, **kwargs):
            report = verification(tx, **kwargs)
            report.token_deltas[0] = token_delta(
                VAULT_ASSET,
                ASSET,
                "45.585834357",
                "337358.545843327",
            )
            return report

        with self.assertRaisesRegex(ValueError, "two-sided swap"):
            verify_ninja_trade_execution_price(
                pool_address=POOL,
                trade_row={
                    "poolAddress": POOL,
                    "txHash": SIG,
                    "type": "BUY",
                    "amountToken": "45.585834357",
                    "amountNative": "0.019692091",
                    "priceNative": "0.0004319782949633428",
                },
                structural_verifier=structural,
                transaction_fetcher=tx_fetch,
                transaction_verifier=wrong,
                membership_prover=membership,
                recognized_program_ids=(XDEX_MAINNET_OBSERVED_PROGRAM_ID,),
            )

    def test_aggregate_requires_five_verified_swaps(self):
        samples = [
            {
                "pool_address": f"Pool{i}",
                "onchain_side": "BUY" if i % 2 == 0 else "SELL",
                "trade_price_native_execution_semantics_verified": True,
                "current_pool_price_native_latest_trade_link_verified": False,
            }
            for i in range(5)
        ]
        result = aggregate_ninja_execution_price_samples(samples)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["verified_swap_count"], 5)
        self.assertTrue(result["trade_price_native_execution_semantics_verified"])
        self.assertTrue(result["both_swap_directions_observed"])
        self.assertFalse(result["current_pool_price_native_latest_trade_link_verified"])
        self.assertFalse(result["universal_pool_catalog_price_native_semantics_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_aggregate_fails_closed_on_bad_sample(self):
        samples = [
            {
                "pool_address": "Pool",
                "onchain_side": "BUY",
                "trade_price_native_execution_semantics_verified": True,
                "current_pool_price_native_latest_trade_link_verified": False,
            }
            for _ in range(5)
        ]
        samples[2]["trade_price_native_execution_semantics_verified"] = False
        result = aggregate_ninja_execution_price_samples(samples)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["trade_price_native_execution_semantics_verified"])

    def test_minimum_must_be_five(self):
        with self.assertRaises(ValueError):
            aggregate_ninja_execution_price_samples([], minimum_verified_swaps=4)


if __name__ == "__main__":
    unittest.main()
