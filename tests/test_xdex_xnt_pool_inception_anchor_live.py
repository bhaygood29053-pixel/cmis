import json
import os
import time
import unittest

from liquidity_scout.providers.x1.candidate_pool_role import (
    verify_candidate_pool_role,
)
from liquidity_scout.providers.x1.history_range import (
    scan_address_history_range,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
    account_key_info,
    collect_program_ids,
    fetch_transaction,
)
from liquidity_scout.providers.x1.xdex import fetch_price_history
from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)


RUN_LIVE = os.getenv("RUN_XDEX_XNT_POOL_INCEPTION_LIVE") == "1"
POOL = "CAJeVEoSm1QQZccnCqYu9cnNF7TTD2fcUA3E5HQoxRvR"
PROGRAM = XDEX_MAINNET_OBSERVED_PROGRAM_ID

# Boundary discovered by the accepted read-only history-boundary probe.
# This is only a provider-visible search bracket, not a trusted inception time.
BOUNDARY_SEARCH_FROM = 1767238740
BOUNDARY_SEARCH_TO = 1767411540


def _provider_first_bar():
    rows = fetch_price_history(
        WRAPPED_XNT_MINT,
        USDC_X_MINT,
        time_from=BOUNDARY_SEARCH_FROM,
        time_to=BOUNDARY_SEARCH_TO,
    )
    timestamps = sorted(
        row["t"]
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("t"), int)
        and not isinstance(row.get("t"), bool)
    )
    return {
        "returned_count": len(rows),
        "first_observed_at": timestamps[0] if timestamps else None,
        "last_observed_at": timestamps[-1] if timestamps else None,
    }


def _pool_balance_transition(tx):
    keys, _signers = account_key_info(tx)
    indices = [index for index, key in enumerate(keys) if key == POOL]
    if len(indices) != 1:
        return {
            "pool_account_index": None,
            "pool_account_key_unique": False,
            "pre_lamports": None,
            "post_lamports": None,
            "zero_to_positive_lamports": False,
        }

    index = indices[0]
    meta = tx.get("meta") or {}
    pre = meta.get("preBalances") or []
    post = meta.get("postBalances") or []
    if index >= len(pre) or index >= len(post):
        return {
            "pool_account_index": index,
            "pool_account_key_unique": True,
            "pre_lamports": None,
            "post_lamports": None,
            "zero_to_positive_lamports": False,
        }

    pre_value = pre[index]
    post_value = post[index]
    return {
        "pool_account_index": index,
        "pool_account_key_unique": True,
        "pre_lamports": pre_value,
        "post_lamports": post_value,
        "zero_to_positive_lamports": (
            isinstance(pre_value, int)
            and not isinstance(pre_value, bool)
            and isinstance(post_value, int)
            and not isinstance(post_value, bool)
            and pre_value == 0
            and post_value > 0
        ),
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_XNT_POOL_INCEPTION_LIVE=1 to run read-only XNT pool inception evidence",
)
class XDEXXNTPoolInceptionAnchorLiveTests(unittest.TestCase):
    def test_chain_pool_creation_candidate_against_provider_first_bar(self):
        structural = verify_candidate_pool_role(
            account=POOL,
            target_mint=WRAPPED_XNT_MINT,
            program_id=PROGRAM,
            signature_limit=1,
        )
        summary = structural.get("summary") or {}
        decoded = structural.get("decoded_state") or {}

        self.assertTrue(summary.get("pool_state_structural_role_verified"))
        self.assertEqual(
            {decoded.get("mint_0"), decoded.get("mint_1")},
            {WRAPPED_XNT_MINT, USDC_X_MINT},
        )

        now = int(time.time())
        scan = scan_address_history_range(
            POOL,
            start_epoch=1,
            end_epoch=now,
            page_size=1000,
            max_signatures=100000,
        )

        self.assertTrue(scan.get("integrity_verified"))
        self.assertTrue(
            scan.get("history_exhausted"),
            "pool address history did not exhaust before the 100k safety bound",
        )
        self.assertFalse(scan.get("bound_reached"))
        self.assertGreater(scan.get("signature_count") or 0, 0)

        oldest_signature = scan.get("oldest_signature")
        self.assertTrue(oldest_signature)
        oldest_tx = fetch_transaction(oldest_signature)
        self.assertIsInstance(oldest_tx, dict)

        meta = oldest_tx.get("meta") or {}
        program_ids = collect_program_ids(oldest_tx)
        balance_transition = _pool_balance_transition(oldest_tx)
        oldest_block_time = oldest_tx.get("blockTime")

        pool_creation_transaction_candidate_verified = bool(
            meta.get("err") is None
            and PROGRAM in program_ids
            and balance_transition["pool_account_key_unique"]
            and balance_transition["zero_to_positive_lamports"]
            and isinstance(oldest_block_time, int)
            and not isinstance(oldest_block_time, bool)
        )

        provider = _provider_first_bar()
        provider_first = provider.get("first_observed_at")
        provider_not_before_pool_creation = bool(
            pool_creation_transaction_candidate_verified
            and isinstance(provider_first, int)
            and provider_first >= oldest_block_time
        )
        provider_delay_seconds = (
            provider_first - oldest_block_time
            if provider_not_before_pool_creation
            else None
        )

        evidence = {
            "schema": "xdex_xnt_pool_inception_anchor_live.v1",
            "pair": f"{WRAPPED_XNT_MINT}/{USDC_X_MINT}",
            "pool": POOL,
            "program": PROGRAM,
            "current_pool_structure_verified": True,
            "rpc_history_integrity_verified": scan.get("integrity_verified"),
            "rpc_history_exhausted": scan.get("history_exhausted"),
            "rpc_signature_count": scan.get("signature_count"),
            "rpc_pages_fetched": scan.get("pages_fetched"),
            "oldest_pool_signature": oldest_signature,
            "oldest_pool_slot": scan.get("oldest_slot"),
            "oldest_pool_block_time_utc": scan.get("oldest_block_time_utc"),
            "oldest_transaction_program_ids": program_ids,
            "pool_balance_transition": balance_transition,
            "pool_creation_transaction_candidate_verified": (
                pool_creation_transaction_candidate_verified
            ),
            "provider_boundary_search_from": BOUNDARY_SEARCH_FROM,
            "provider_boundary_search_to": BOUNDARY_SEARCH_TO,
            "provider_first_bar": provider,
            "provider_not_before_pool_creation": provider_not_before_pool_creation,
            "provider_delay_seconds": provider_delay_seconds,
            "first_verified_supported_market_observation": None,
            "asset_lifetime_start_verified": False,
            "provider_range_complete_verified": False,
            "archive_exhaustion_verified": False,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
        }

        print("XDEX XNT POOL INCEPTION ANCHOR EVIDENCE")
        print(json.dumps(evidence, sort_keys=True))

        self.assertTrue(pool_creation_transaction_candidate_verified)
        self.assertIsNotNone(provider_first)
        self.assertTrue(provider_not_before_pool_creation)


if __name__ == "__main__":
    unittest.main()
