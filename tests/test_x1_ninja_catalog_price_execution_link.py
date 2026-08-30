import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.ninja_catalog_price_execution_link import (
    aggregate_catalog_price_links,
    select_bounded_xnt_catalog_pools,
    verify_catalog_price_transition,
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


def snapshot(price, *, lower_after, upper_before, base="100", quote="50"):
    return {
        "rpc_slot_bracket": {
            "before": {"slot": lower_after - 1, "block_time": 1},
            "after": {"slot": lower_after, "block_time": 2},
        } if upper_before is None else {
            "before": {"slot": upper_before, "block_time": 3},
            "after": {"slot": upper_before + 1, "block_time": 4},
        },
        "pools": [{
            "pool_address": POOL,
            "status": "ok",
            "provider": {
                "priceNative": price,
                "pooledBase": base,
                "pooledQuote": quote,
                "lastSyncedAt_raw": "t",
                "txns1h_raw": 1,
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


def report_for(signature, slot):
    asset = token_delta(VAULT_ASSET, ASSET, "-10", "990")
    quote = token_delta(VAULT_XNT, WXNT_MINT, "0.02", "2.02")
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
        dex_protocol="XDEX",
        xdex_amm_invoked=True,
        xendex_amm_invoked=False,
        xendex_staking_invoked=False,
        program_ids=[XDEX_MAINNET_OBSERVED_PROGRAM_ID],
        token_deltas=[asset, quote],
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
    return [
        {"signature": "older", "slot": 11, "err": None},
        {"signature": "match", "slot": 12, "err": None},
        {"signature": "too_new", "slot": 14, "err": None},
    ]


def tx_fetch(signature, *, rpc_url):
    return {
        "transaction": {
            "signatures": [signature],
            "message": {"accountKeys": [], "instructions": []},
        },
        "meta": {},
    }


def verifier(tx, *, signature, rpc_url):
    if signature == "older":
        report = report_for(signature, 11)
        report.token_deltas[1] = token_delta(
            VAULT_XNT, WXNT_MINT, "0.019", "2.019"
        )
        return report
    return report_for(signature, 12)


def membership(**kwargs):
    return {"transaction_pool_membership_verified": True}


class CatalogExecutionLinkTests(unittest.TestCase):
    def test_selects_exact_xnt_candidates_without_symbols(self):
        rows = [
            {
                "address": "A",
                "baseToken": {"address": WXNT_MINT},
                "quoteToken": {"address": "X"},
                "txns1h": 2,
            },
            {
                "address": "B",
                "baseToken": {"address": "Y"},
                "quoteToken": {"address": WXNT_MINT},
                "txns1h": 5,
            },
            {
                "address": "C",
                "baseToken": {"symbol": "XNT"},
                "quoteToken": {"address": "Z"},
                "txns1h": 100,
            },
        ]
        self.assertEqual(
            select_bounded_xnt_catalog_pools(rows),
            ["B", "A"],
        )

    def test_unique_latest_swap_links_new_catalog_price(self):
        before = {
            "rpc_slot_bracket": {
                "before": {"slot": 9},
                "after": {"slot": 10},
            },
            "pools": [{
                "pool_address": POOL,
                "status": "ok",
                "provider": {
                    "priceNative": "0.0019",
                    "pooledBase": "1000",
                    "pooledQuote": "2",
                    "lastSyncedAt_raw": "a",
                },
            }],
        }
        after = {
            "rpc_slot_bracket": {
                "before": {"slot": 13},
                "after": {"slot": 14},
            },
            "pools": [{
                "pool_address": POOL,
                "status": "ok",
                "provider": {
                    "priceNative": "0.002",
                    "pooledBase": "990",
                    "pooledQuote": "2.02",
                    "lastSyncedAt_raw": "b",
                },
            }],
        }
        result = verify_catalog_price_transition(
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
        self.assertEqual(
            result["matched_transaction"]["signature"],
            "match",
        )
        self.assertTrue(result["catalog_price_execution_link_verified"])
        self.assertTrue(result["event_ordering_verified"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_unchanged_price_is_not_applicable(self):
        before = {
            "rpc_slot_bracket": {"after": {"slot": 10}},
            "pools": [{
                "pool_address": POOL,
                "status": "ok",
                "provider": {
                    "priceNative": "0.002",
                    "pooledBase": "1000",
                    "pooledQuote": "2",
                },
            }],
        }
        after = {
            "rpc_slot_bracket": {"before": {"slot": 13}},
            "pools": [{
                "pool_address": POOL,
                "status": "ok",
                "provider": {
                    "priceNative": "0.002",
                    "pooledBase": "990",
                    "pooledQuote": "2.02",
                },
            }],
        }
        result = verify_catalog_price_transition(
            before=before,
            after=after,
            pool_address=POOL,
        )
        self.assertEqual(result["status"], "not_applicable")
        self.assertFalse(result["catalog_price_execution_link_verified"])

    def test_aggregate_requires_five_unique_verified_events(self):
        events = [
            {
                "pool_address": f"Pool{i}",
                "catalog_price_execution_link_verified": True,
                "event_ordering_verified": True,
                "matched_transaction": {"signature": f"Sig{i}"},
            }
            for i in range(5)
        ]
        result = aggregate_catalog_price_links(events)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["verified_event_count"], 5)
        self.assertTrue(result["catalog_price_execution_link_verified"])
        self.assertTrue(result["event_ordering_verified"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["universal_catalog_price_semantics_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_duplicate_transaction_fails_aggregate(self):
        events = [
            {
                "pool_address": f"Pool{i}",
                "catalog_price_execution_link_verified": True,
                "event_ordering_verified": True,
                "matched_transaction": {"signature": "same"},
            }
            for i in range(5)
        ]
        result = aggregate_catalog_price_links(events)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["catalog_price_execution_link_verified"])


if __name__ == "__main__":
    unittest.main()
