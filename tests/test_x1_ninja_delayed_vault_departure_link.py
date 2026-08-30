import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.ninja_delayed_vault_departure_link import (
    DEFAULT_LOOKBACK_SECONDS,
    DELAYED_LATEST_SWAP_LINK,
    LATEST_SWAP_MATCHES_BEFORE,
    LATEST_SWAP_MATCHES_NEITHER,
    SAME_SLOT_AMBIGUITY,
    aggregate_delayed_vault_departure_links,
    verify_delayed_vault_departure_link,
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


def snapshot(*, observed_start=2000, observed_end=2001, start_slot=200):
    return {
        "observed_at_start": observed_start,
        "observed_at_end": observed_end,
        "rpc_slot_bracket": {
            "before": {"slot": start_slot},
            "after": {"slot": start_slot + 1},
        },
    }


def departure(before_price="0.5", after_price="0.002"):
    return {
        "service": "x1_ninja_price_only_reserve_ratio_event",
        "status": "verified",
        "pool_address": POOL,
        "event_key": "Pool111:201:210",
        "classification": "gross_reserve_ratio_departure",
        "price_only_update_verified": True,
        "gross_reserve_ratio_departure_observed": True,
        "provider_timestamp_candidates": {
            "before_lastSyncedAt_raw": "before-row",
            "after_lastSyncedAt_raw": "after-row",
            "before_global_lastUpdated_raw": "before-global",
            "after_global_lastUpdated_raw": "after-global",
        },
        "base_evidence": {
            "vault_history_complete_for_window": True,
            "transaction_coverage_complete": True,
            "unique_vault_history_signature_count": 0,
            "verified_vault_transaction_count": 0,
            "provider_reserve_changed": False,
            "price_changed": True,
            "identity": {
                "chain": "x1",
                "pool_address": POOL,
                "mint_0": WXNT_MINT,
                "mint_1": ASSET,
                "vault_0": VAULT_XNT,
                "vault_1": VAULT_ASSET,
                "asset_mint": ASSET,
                "asset_vault": VAULT_ASSET,
                "counter_mint": WXNT_MINT,
                "counter_vault": VAULT_XNT,
                "shared_owner": OWNER,
                "xnt_slot": 0,
                "identity_verified": True,
            },
            "before_provider": {
                "priceNative": before_price,
                "pooledBase": "100",
                "pooledQuote": "50",
            },
            "after_provider": {
                "priceNative": after_price,
                "pooledBase": "100",
                "pooledQuote": "50",
            },
        },
    }


def departure_verifier_for(result):
    def verifier(**kwargs):
        return dict(result)
    return verifier


def token_delta(account, mint, amount):
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


def report(signature, *, slot, block_time, execution_price="0.002"):
    asset_delta = Decimal("-10")
    quote_delta = abs(asset_delta) * Decimal(execution_price)
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
            token_delta(VAULT_ASSET, ASSET, str(asset_delta)),
            token_delta(VAULT_XNT, WXNT_MINT, str(quote_delta)),
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


def tx_fetch(signature, *, rpc_url):
    return {
        "transaction": {
            "signatures": [signature],
            "message": {"instructions": []},
        },
        "meta": {"innerInstructions": []},
    }


def membership(**kwargs):
    return {
        "transaction_pool_membership_verified": True,
        "recognized_amm_instruction_count": 1,
        "selected_pool_instruction_count": 1,
    }


def history_rows(*rows):
    values = list(rows)
    def fetcher(address, *, limit, rpc_url):
        return list(values)
    return fetcher


def history(signature="swap", slot=190, block_time=1500):
    return {
        "signature": signature,
        "slot": slot,
        "err": None,
        "block_time": block_time,
        "confirmation_status": "confirmed",
    }


class DelayedVaultDepartureLinkTests(unittest.TestCase):
    def run_case(
        self,
        *,
        departure_result=None,
        rows=None,
        price_by_signature=None,
        membership_prover=membership,
    ):
        departure_result = departure_result or departure()
        rows = rows or [history()]
        price_by_signature = price_by_signature or {"swap": "0.002"}

        def verifier(tx, *, signature, rpc_url):
            row = next(item for item in rows if item["signature"] == signature)
            return report(
                signature,
                slot=row["slot"],
                block_time=row["block_time"],
                execution_price=price_by_signature[signature],
            )

        return verify_delayed_vault_departure_link(
            before=snapshot(),
            after=snapshot(
                observed_start=2010,
                observed_end=2011,
                start_slot=210,
            ),
            pool_address=POOL,
            departure_verifier=departure_verifier_for(departure_result),
            signature_fetcher=history_rows(*rows),
            transaction_fetcher=tx_fetch,
            transaction_verifier=verifier,
            membership_prover=membership_prover,
            recognized_program_ids=(XDEX_MAINNET_OBSERVED_PROGRAM_ID,),
            rpc_url="rpc",
        )

    def test_links_unique_latest_swap_to_after_departure_price(self):
        result = self.run_case()
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["outcome"], DELAYED_LATEST_SWAP_LINK)
        self.assertTrue(result["price_only_reserve_ratio_departure_verified"])
        self.assertTrue(result["delayed_vault_swap_execution_link_verified"])
        self.assertTrue(result["departure_lag_observed"])
        self.assertEqual(result["latest_exact_swap"]["signature"], "swap")
        self.assertEqual(
            result["departure_lag"][
                "minimum_observed_departure_lag_seconds"
            ],
            "501",
        )
        self.assertEqual(
            result["departure_lag"][
                "maximum_observed_departure_lag_seconds"
            ],
            "511",
        )
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_latest_swap_matching_before_is_separate_outcome(self):
        result = self.run_case(price_by_signature={"swap": "0.5"})
        self.assertEqual(result["outcome"], LATEST_SWAP_MATCHES_BEFORE)
        self.assertFalse(result["delayed_vault_swap_execution_link_verified"])

    def test_does_not_cherry_pick_older_after_price_match(self):
        rows = [
            history("latest", slot=195, block_time=1600),
            history("older", slot=190, block_time=1500),
        ]
        result = self.run_case(
            rows=rows,
            price_by_signature={
                "latest": "0.003",
                "older": "0.002",
            },
        )
        self.assertEqual(result["latest_exact_swap"]["signature"], "latest")
        self.assertEqual(result["outcome"], LATEST_SWAP_MATCHES_NEITHER)
        self.assertFalse(result["delayed_vault_swap_execution_link_verified"])

    def test_same_slot_multiple_exact_swaps_fail_closed(self):
        rows = [
            history("swap-a", slot=195, block_time=1600),
            history("swap-b", slot=195, block_time=1600),
        ]
        result = self.run_case(
            rows=rows,
            price_by_signature={
                "swap-a": "0.002",
                "swap-b": "0.0021",
            },
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["outcome"], SAME_SLOT_AMBIGUITY)
        self.assertFalse(result["delayed_vault_swap_execution_link_verified"])

    def test_incomplete_vault_history_fails_closed(self):
        rows = [
            history(f"sig-{i}", slot=190 - i, block_time=1900 - i)
            for i in range(100)
        ]
        result = self.run_case(
            rows=rows,
            price_by_signature={
                row["signature"]: "0.002"
                for row in rows
            },
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIn(
            "vault_history_does_not_cover_fixed_pre_before_lookback",
            result["warnings"],
        )

    def test_full_history_page_ending_at_inclusive_cutoff_fails_closed(self):
        rows = [
            history(
                f"sig-{i}",
                slot=190 - i,
                block_time=1199 - i,
            )
            for i in range(100)
        ]
        self.assertEqual(rows[-1]["block_time"], 1100)

        result = self.run_case(rows=rows)

        self.assertEqual(result["status"], "unavailable")
        self.assertIn(
            "vault_history_does_not_cover_fixed_pre_before_lookback",
            result["warnings"],
        )

    def test_multi_amm_candidate_fails_closed(self):
        def routed(**kwargs):
            return {
                "transaction_pool_membership_verified": True,
                "recognized_amm_instruction_count": 2,
                "selected_pool_instruction_count": 1,
            }

        result = self.run_case(membership_prover=routed)
        self.assertEqual(result["status"], "unavailable")
        self.assertTrue(result["rejections"])
        self.assertIn(
            "routed_or_multi_amm_instruction_ambiguity",
            result["rejections"][0]["error"],
        )

    def test_requires_accepted_departure_prerequisite(self):
        not_departure = departure()
        not_departure["classification"] = "gross_reserve_ratio_adoption"
        not_departure["gross_reserve_ratio_departure_observed"] = False
        result = self.run_case(departure_result=not_departure)
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(
            result["price_only_reserve_ratio_departure_verified"]
        )

    def test_fixed_lookback_cannot_be_widened(self):
        with self.assertRaisesRegex(ValueError, "fixed"):
            verify_delayed_vault_departure_link(
                before=snapshot(),
                after=snapshot(
                    observed_start=2010,
                    observed_end=2011,
                    start_slot=210,
                ),
                pool_address=POOL,
                lookback_seconds=DEFAULT_LOOKBACK_SECONDS + 1,
            )

    def test_aggregate_promotes_only_five_unique_delayed_departures(self):
        events = [
            {
                "event_key": f"Pool{i}:1:2",
                "pool_address": f"Pool{i}",
                "status": "verified",
                "outcome": DELAYED_LATEST_SWAP_LINK,
                "price_only_reserve_ratio_departure_verified": True,
                "delayed_vault_swap_execution_link_verified": True,
                "departure_lag_observed": True,
                "departure_lag": {
                    "minimum_observed_departure_lag_seconds": "10",
                    "maximum_observed_departure_lag_seconds": "20",
                },
                "latest_exact_swap": {"signature": f"Sig{i}"},
            }
            for i in range(5)
        ]
        result = aggregate_delayed_vault_departure_links(events)
        self.assertEqual(result["status"], "verified")
        self.assertTrue(
            result["price_only_reserve_ratio_departure_verified"]
        )
        self.assertTrue(
            result["delayed_vault_swap_execution_link_verified"]
        )
        self.assertTrue(result["departure_pattern_verified"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_complete_counterexample_blocks_pattern(self):
        events = [
            {
                "event_key": f"Pool{i}:1:2",
                "status": "verified",
                "outcome": DELAYED_LATEST_SWAP_LINK,
                "price_only_reserve_ratio_departure_verified": True,
                "delayed_vault_swap_execution_link_verified": True,
                "departure_lag_observed": True,
                "departure_lag": {},
                "latest_exact_swap": {"signature": f"Sig{i}"},
            }
            for i in range(5)
        ]
        events.append({
            "event_key": "Counter:1:2",
            "status": "partial",
            "outcome": LATEST_SWAP_MATCHES_BEFORE,
            "price_only_reserve_ratio_departure_verified": True,
            "delayed_vault_swap_execution_link_verified": False,
            "departure_lag_observed": False,
        })
        result = aggregate_delayed_vault_departure_links(events)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["departure_pattern_verified"])
        self.assertEqual(
            result["outcome_counts"][LATEST_SWAP_MATCHES_BEFORE],
            1,
        )


if __name__ == "__main__":
    unittest.main()
