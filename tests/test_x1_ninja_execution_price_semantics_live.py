import json
import os
import unittest

from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_execution_price_semantics import (
    aggregate_ninja_execution_price_samples,
    verify_ninja_trade_execution_price,
)
from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
from liquidity_scout.providers.x1.transaction_semantics import WXNT_MINT


RUN_LIVE = os.getenv("RUN_X1_NINJA_EXECUTION_PRICE_LIVE") == "1"


def _token_candidates(row):
    values = []
    for side_name in ("baseToken", "quoteToken"):
        side = row.get(side_name)
        if not isinstance(side, dict):
            continue
        for key in ("mint", "address", "tokenAddress", "mintAddress"):
            value = str(side.get(key) or "").strip()
            if value and value not in values:
                values.append(value)
    return values


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_EXECUTION_PRICE_LIVE=1 to run read-only evidence",
)
class NinjaExecutionPriceLiveTests(unittest.TestCase):
    def test_five_exact_xnt_swaps_match_execution_price(self):
        ninja_pools, _ = fetch_all_pools(sleep_seconds=0)
        candidates = [
            row
            for row in ninja_pools
            if isinstance(row, dict)
            and WXNT_MINT in _token_candidates(row)
            and str(row.get("address") or "").strip()
        ]
        self.assertTrue(candidates, "No current X1.Ninja XNT pools available")

        samples = []
        errors = []
        seen_signatures = set()

        for pool_row in candidates[:20]:
            if len(samples) >= 5:
                break
            pool = str(pool_row["address"]).strip()

            try:
                history = fetch_pool_trades_raw(pool)
            except Exception as exc:
                errors.append({
                    "pool_address": pool,
                    "stage": "trade_history",
                    "error": f"{type(exc).__name__}: {exc}",
                })
                continue

            trades = history["raw_response"].get("trades") or []
            for index, trade in enumerate(trades[:5]):
                if len(samples) >= 5:
                    break
                signature = str(trade.get("txHash") or "").strip()
                if not signature or signature in seen_signatures:
                    continue
                seen_signatures.add(signature)

                try:
                    result = verify_ninja_trade_execution_price(
                        pool_address=pool,
                        trade_row=trade,
                        current_pool_row=pool_row,
                    )
                except Exception as exc:
                    errors.append({
                        "pool_address": pool,
                        "transaction_signature": signature,
                        "stage": "verification",
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    continue

                if result["trade_price_native_execution_semantics_verified"]:
                    samples.append(result)
                    break

        aggregate = aggregate_ninja_execution_price_samples(samples)

        print(
            "[X1.Ninja execution-price semantic evidence] "
            + json.dumps(
                {"aggregate": aggregate, "errors": errors},
                sort_keys=True,
                default=str,
            )
        )

        self.assertEqual(aggregate["verified_swap_count"], 5)
        self.assertTrue(
            aggregate["trade_price_native_execution_semantics_verified"]
        )
        self.assertFalse(
            aggregate["universal_pool_catalog_price_native_semantics_verified"]
        )
        self.assertFalse(aggregate["provider_fact_time_verified"])
        self.assertFalse(aggregate["freshness_verified"])
        self.assertFalse(aggregate["price_usd_semantics_verified"])
        self.assertFalse(aggregate["liquidity_semantics_verified"])
        self.assertFalse(aggregate["cmis_promotable"])
        self.assertFalse(aggregate["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
