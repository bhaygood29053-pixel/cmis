import json
import os
import time
import unittest
from types import SimpleNamespace

from liquidity_scout.market.resolver import find_matches_for_term, pool_address
from liquidity_scout.providers.x1.liquidity_freshness import (
    REFERENCE_POOL_ADDRESS,
    evaluate_x1_ninja_current_pool_scope,
    evaluate_x1_ninja_liquidity_freshness,
)
from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_price_fact_time import (
    collect_ninja_price_fact_time_snapshot,
)
from liquidity_scout.providers.x1.xdex_price_history_import import WRAPPED_XNT_MINT
from liquidity_scout.services.cmis_market import build_market_report_response
from tests.test_x1_current_usdcx_usd_equivalence_live import (
    capture_current_usdcx_usd_equivalence_live_evidence,
)


RUN_LIVE = os.getenv("RUN_X1_NINJA_LIQUIDITY_FRESHNESS_LIVE") == "1"
MAX_LIVE_POOLS = int(os.getenv("X1_NINJA_LIQUIDITY_FRESHNESS_MAX_LIVE_POOLS", "12"))
MAX_ATTEMPTS = int(os.getenv("X1_NINJA_LIQUIDITY_FRESHNESS_MAX_ATTEMPTS", "3"))
RETRY_SECONDS = float(os.getenv("X1_NINJA_LIQUIDITY_FRESHNESS_RETRY_SECONDS", "5"))

SEED_POOLS = (
    "HQQYuwug6PmJQy4KYqg5jFPjx1pDJdbeLQFjj6eZLv9j",
    "HSuoZxaStxdt6akWRgjsTeMit5SvnzJymtTrkVH2oER3",
    "HYNRFcWYucxNvMRWkm6NRK9jZo4KnV9sg3SVq84WkP6Z",
    "Ha5ZmfjzdDGsEgfKBrZsHYXGxkkxRJQtSDc69hi7P5qL",
    "HeXuKcYkVoHWKvmZt84tFVQmBbAZ5KBEntvBCmRiygGA",
)


def _text(value):
    text = str(value or "").strip()
    return text or None


def _exact_matches(mint, pools):
    return [
        match
        for match in find_matches_for_term(mint, pools)
        if len(match) >= 4 and match[3] >= 90
    ]


def _addresses(matches):
    result = []
    seen = set()
    for match in matches:
        address = _text(pool_address(match[0]))
        if address and address not in seen:
            seen.add(address)
            result.append(address)
    return result


def _seed_asset_mints():
    snapshot = collect_ninja_price_fact_time_snapshot(
        pool_addresses=list(SEED_POOLS)
    )
    mints = []
    seen = set()
    diagnostics = []
    for row in snapshot.get("pools") or []:
        if not isinstance(row, dict):
            continue
        rpc = row.get("rpc") if isinstance(row.get("rpc"), dict) else {}
        mint_0 = _text(rpc.get("mint_0"))
        mint_1 = _text(rpc.get("mint_1"))
        address = _text(row.get("pool_address"))
        eligible = bool(
            row.get("status") == "ok"
            and mint_0 == WRAPPED_XNT_MINT
            and mint_1
            and mint_1 != WRAPPED_XNT_MINT
        )
        diagnostics.append(
            {
                "pool_address": address,
                "mint_0": mint_0,
                "mint_1": mint_1,
                "eligible_wrapped_xnt_mint0_seed": eligible,
            }
        )
        if eligible and mint_1 not in seen:
            seen.add(mint_1)
            mints.append(mint_1)
    return mints, diagnostics


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIQUIDITY_FRESHNESS_LIVE=1 for live #459 evidence",
)
class X1NinjaLiquidityFreshnessLiveTests(unittest.TestCase):
    def test_prove_one_complete_exact_mint_aggregate_current_liquidity(self):
        self.assertGreaterEqual(MAX_LIVE_POOLS, 1)
        self.assertLessEqual(MAX_LIVE_POOLS, 150)
        self.assertGreaterEqual(MAX_ATTEMPTS, 1)
        self.assertLessEqual(MAX_ATTEMPTS, 5)
        self.assertGreaterEqual(RETRY_SECONDS, 0)

        seed_mints, seed_diagnostics = _seed_asset_mints()
        self.assertTrue(
            seed_mints,
            f"no #470 seed pool retained accepted wrapped-XNT mint_0 scope: {seed_diagnostics}",
        )

        attempts = []
        verified = None

        for attempt_index in range(MAX_ATTEMPTS):
            pools, xnt_price_usd = fetch_all_pools(sleep_seconds=0)
            candidates = []
            for mint in seed_mints:
                matches = _exact_matches(mint, pools)
                addresses = _addresses(matches)
                if not addresses or len(addresses) > MAX_LIVE_POOLS:
                    continue
                candidates.append(
                    {
                        "mint": mint,
                        "matches": matches,
                        "addresses": addresses,
                    }
                )
            candidates.sort(key=lambda row: (len(row["addresses"]), row["mint"]))

            attempt_report = {
                "attempt_index": attempt_index,
                "catalog_row_count": len(pools),
                "candidate_count": len(candidates),
                "candidates": [
                    {
                        "mint": row["mint"],
                        "pool_count": len(row["addresses"]),
                        "addresses": row["addresses"],
                    }
                    for row in candidates
                ],
                "results": [],
            }

            for candidate in candidates:
                mint = candidate["mint"]
                matches = candidate["matches"]
                catalog = SimpleNamespace(
                    xnt_price_usd=xnt_price_usd,
                    last_refresh=time.time(),
                )
                market = build_market_report_response(
                    mint,
                    matches,
                    catalog,
                    chain="x1",
                    observed_at=time.time(),
                )
                if market.get("status") not in {"ok", "partial"}:
                    attempt_report["results"].append(
                        {
                            "mint": mint,
                            "status": "market_unavailable",
                            "market_status": market.get("status"),
                        }
                    )
                    continue

                scope = evaluate_x1_ninja_current_pool_scope(
                    market_envelope=market,
                    catalog_pools=pools,
                )
                if scope.get("provider_scoped_pool_universe_verified") is not True:
                    attempt_report["results"].append(
                        {
                            "mint": mint,
                            "status": "pool_scope_unverified",
                            "scope": scope,
                        }
                    )
                    continue

                addresses = scope["market_contributing_pool_addresses"]
                requested = list(addresses)
                if REFERENCE_POOL_ADDRESS not in requested:
                    requested.append(REFERENCE_POOL_ADDRESS)
                snapshot = collect_ninja_price_fact_time_snapshot(
                    pool_addresses=requested
                )

                usdcx = capture_current_usdcx_usd_equivalence_live_evidence()
                equivalence = usdcx.get("equivalence") or {}
                result = evaluate_x1_ninja_liquidity_freshness(
                    market_envelope=market,
                    snapshot=snapshot,
                    current_usdcx_usd_equivalence=equivalence,
                    pool_scope_evidence=scope,
                    evaluated_at=time.time(),
                    max_pools=150,
                )
                attempt_report["results"].append(
                    {
                        "mint": mint,
                        "status": result.get("status"),
                        "liquidity_freshness_verified": result.get(
                            "liquidity_freshness_verified"
                        ),
                        "pool_count": len(addresses),
                        "failures": result.get("failures"),
                    }
                )

                if result.get("liquidity_freshness_verified") is True:
                    verified = {
                        "mint": mint,
                        "market": market,
                        "pool_scope": scope,
                        "snapshot": snapshot,
                        "current_usdcx_usd": usdcx,
                        "liquidity_freshness": result,
                    }
                    break

            attempts.append(attempt_report)
            if verified is not None:
                break
            if attempt_index + 1 < MAX_ATTEMPTS and RETRY_SECONDS:
                time.sleep(RETRY_SECONDS)

        evidence = {
            "schema": "x1_459_liquidity_freshness_live.v1",
            "chain": "x1",
            "seed_pools": list(SEED_POOLS),
            "seed_diagnostics": seed_diagnostics,
            "seed_asset_mints": seed_mints,
            "max_live_pools": MAX_LIVE_POOLS,
            "attempts": attempts,
            "verified_asset": verified,
            "liquidity_freshness_verified": bool(
                verified
                and verified["liquidity_freshness"].get(
                    "liquidity_freshness_verified"
                )
                is True
            ),
            "volume_24h_freshness_verified": False,
            "transactions_24h_freshness_verified": False,
            "provider_fact_time_verified_by_liquidity_gate": False,
            "source_independence_verified": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        }
        print("X1 #459 AGGREGATE LIQUIDITY FRESHNESS LIVE EVIDENCE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertIsNotNone(
            verified,
            f"no complete candidate produced current aggregate liquidity proof: {attempts}",
        )
        result = verified["liquidity_freshness"]
        self.assertTrue(
            verified["pool_scope"]["provider_scoped_pool_universe_verified"]
        )
        self.assertFalse(
            verified["pool_scope"]["global_xdex_pool_universe_verified"]
        )
        self.assertTrue(result["all_contributing_pools_corroborated"])
        self.assertTrue(result["rpc_freshness"]["rpc_block_time_fresh"])
        self.assertTrue(result["current_usdcx_usd_equivalence_verified"])
        self.assertTrue(result["current_value_reproduced_from_fresh_chain_state"])
        self.assertTrue(result["liquidity_freshness_verified"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(evidence["volume_24h_freshness_verified"])
        self.assertFalse(evidence["transactions_24h_freshness_verified"])
        self.assertFalse(evidence["public_service_promoted"])
        self.assertFalse(evidence["scout_reliance_promoted"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
