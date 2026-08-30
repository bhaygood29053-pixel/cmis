import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.ninja_delayed_catalog_price_link import (
    DEFAULT_LOOKBACK_SECONDS,
    aggregate_delayed_catalog_price_links,
    verify_delayed_catalog_price_transition,
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


def snapshot(price, *, start_slot, end_slot, observed_start, observed_end):
    return {
        "observed_at_start": observed_start,
        "observed_at_end": observed_end,
        "rpc_slot_bracket": {
            "before": {"slot": start_slot},
            "after": {"slot": end_slot},
        },
        "provider_timestamp_candidates": {
            "global_lastUpdated_raw": "global",
        },
        "pools": [{
            "pool_address": POOL,
            "status": "ok",
            "provider": {
                "priceNative": price,
                "pooledBase": "100",
                "pooledQuote": "50",
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


def token_delta(account, mint, delta):
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
        post_ui=Decimal("1"),
    )


def report(signature, slot, block_time, quote_delta="0.02"):
    return VerificationReport(
        signature=signature,
        rpc_url="rpc",
        found=True,
        succeeded=True,
        slot=slot,
        block_time=block_time,
        block_time_iso=None,
        fee_lamports=1,
        primary_signer="Signer",
        dex_protocol="XDEX",
        xdex_amm_invoked=True,
        xendex_amm_invoked=False,
        xendex_staking_invoked=False,
        program_ids=[XDEX_MAINNET_OBSERVED_PROGRAM_ID],
        token_deltas=[
            token_delta(VAULT_ASSET, ASSET, "-10"),
            token_delta(VAULT_XNT, WXNT_MINT, quote_delta),
        ],
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


def signatures(address, *, limit, rpc_url):
    rows = [
        {
            "signature": "match",
            "slot": 95,
            "err": None,
            "block_time": 1000,
        },
        {
            "signature": "older",
            "slot": 90,
            "err": None,
            "block_time": 950,
        },
    ]
    return rows


def tx_fetch(signature, *, rpc_url):
    return {
        "transaction": {
            "signatures": [signature],
            "message": {"accountKeys": [], "instructions": []},
        },
        "meta": {},
    }


def verifier(tx, *, signature, rpc_url):
    if signature == "match":
        return report(signature, 95, 1000, "0.02")
    return report(signature, 90, 950, "0.019")


def membership(**kwargs):
    return {"transaction_pool_membership_verified": True}


class DelayedCatalogPriceLinkTests(unittest.TestCase):
    def test_verifies_unique_latest_delayed_adoption(self):
        before = snapshot(
            "0.0019",
            start_slot=100,
            end_slot=101,
            observed_start=1050,
            observed_end=1051,
        )
        after = snapshot(
            "0.002",
            start_slot=110,
            end_slot=111,
            observed_start=1060,
            observed_end=1061,
        )

        result = verify_delayed_catalog_price_transition(
            before=before,
            after=after,
            pool_address=POOL,
            structural_verifier=structural,
            signature_fetcher=signatures,
            transaction_fetcher=tx_fetch,
            transaction_verifier=verifier,
            membership_prover=membership,
            recognized_program_ids=(XDEX_MAINNET_OBSERVED_PROGRAM_ID,),
            rpc_url="rpc",
        )

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["matched_transaction"]["signature"], "match")
        self.assertTrue(
            result["delayed_catalog_price_execution_link_verified"]
        )
        self.assertTrue(result["incorporation_lag_observed"])
        self.assertEqual(
            result["incorporation_lag"][
                "minimum_observed_incorporation_lag_seconds"
            ],
            "51",
        )
        self.assertEqual(
            result["incorporation_lag"][
                "maximum_observed_incorporation_lag_seconds"
            ],
            "61",
        )
        self.assertFalse(result["incorporation_lag_policy_verified"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_candidate_must_predate_before_request_start(self):
        def later(address, *, limit, rpc_url):
            return [{
                "signature": "match",
                "slot": 105,
                "err": None,
                "block_time": 1055,
            }]

        before = snapshot(
            "0.0019",
            start_slot=100,
            end_slot=101,
            observed_start=1050,
            observed_end=1051,
        )
        after = snapshot(
            "0.002",
            start_slot=110,
            end_slot=111,
            observed_start=1060,
            observed_end=1061,
        )
        result = verify_delayed_catalog_price_transition(
            before=before,
            after=after,
            pool_address=POOL,
            structural_verifier=structural,
            signature_fetcher=later,
            transaction_fetcher=tx_fetch,
            transaction_verifier=verifier,
            membership_prover=membership,
            recognized_program_ids=(XDEX_MAINNET_OBSERVED_PROGRAM_ID,),
            rpc_url="rpc",
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(
            result["delayed_catalog_price_execution_link_verified"]
        )

    def test_fixed_lookback_cannot_be_widened(self):
        before = snapshot(
            "0.0019",
            start_slot=100,
            end_slot=101,
            observed_start=1050,
            observed_end=1051,
        )
        after = snapshot(
            "0.002",
            start_slot=110,
            end_slot=111,
            observed_start=1060,
            observed_end=1061,
        )
        with self.assertRaisesRegex(ValueError, "fixed"):
            verify_delayed_catalog_price_transition(
                before=before,
                after=after,
                pool_address=POOL,
                lookback_seconds=DEFAULT_LOOKBACK_SECONDS + 1,
            )

    def test_aggregate_accepts_five_unique_delayed_examples(self):
        events = [
            {
                "pool_address": f"Pool{i}",
                "status": "verified",
                "history_complete_for_lookback": True,
                "verified_swap_candidate_count": 1,
                "delayed_catalog_price_execution_link_verified": True,
                "incorporation_lag_observed": True,
                "incorporation_lag": {
                    "minimum_observed_incorporation_lag_seconds": "10",
                    "maximum_observed_incorporation_lag_seconds": "20",
                },
                "matched_transaction": {"signature": f"Sig{i}"},
            }
            for i in range(5)
        ]
        result = aggregate_delayed_catalog_price_links(events)
        self.assertEqual(result["status"], "verified")
        self.assertTrue(
            result["delayed_catalog_price_execution_link_verified"]
        )
        self.assertTrue(result["incorporation_lag_observed"])
        self.assertFalse(result["incorporation_lag_policy_verified"])
        self.assertFalse(result["universal_catalog_price_semantics_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_complete_contradiction_blocks_aggregate(self):
        events = [
            {
                "pool_address": f"Pool{i}",
                "status": "verified",
                "history_complete_for_lookback": True,
                "verified_swap_candidate_count": 1,
                "delayed_catalog_price_execution_link_verified": True,
                "incorporation_lag_observed": True,
                "incorporation_lag": {},
                "matched_transaction": {"signature": f"Sig{i}"},
            }
            for i in range(5)
        ]
        events.append({
            "pool_address": "Contradiction",
            "status": "partial",
            "history_complete_for_lookback": True,
            "verified_swap_candidate_count": 2,
            "delayed_catalog_price_execution_link_verified": False,
            "incorporation_lag_observed": False,
        })
        result = aggregate_delayed_catalog_price_links(events)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(
            result["delayed_catalog_price_execution_link_verified"]
        )


if __name__ == "__main__":
    unittest.main()
