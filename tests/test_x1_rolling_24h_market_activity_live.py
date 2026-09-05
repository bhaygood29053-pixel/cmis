import json
import os
import time
import unittest
from types import SimpleNamespace

from liquidity_scout.market.resolver import find_matches_for_term, pool_address
from liquidity_scout.providers.x1.liquidity_freshness import (
    evaluate_x1_ninja_current_pool_scope,
)
from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_price_fact_time import (
    collect_ninja_price_fact_time_snapshot,
)
from liquidity_scout.providers.x1.rolling_24h_market_activity import (
    evaluate_x1_rolling_24h_market_activity,
    reconstruct_x1_pool_24h_chain_activity,
)
from liquidity_scout.providers.x1.rpc import get_token_account_info
from liquidity_scout.providers.x1.xdex_price_history_import import WRAPPED_XNT_MINT
from liquidity_scout.services.cmis_market import build_market_report_response


RUN_LIVE = os.getenv("RUN_X1_ROLLING_24H_ACTIVITY_LIVE") == "1"
MAX_CANDIDATES = int(os.getenv("X1_ROLLING_24H_MAX_CANDIDATES", "12"))
MAX_SIGNATURES = int(os.getenv("X1_ROLLING_24H_MAX_SIGNATURES", "5000"))


def _text(value):
    text = str(value or "").strip()
    return text or None


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _token_mint(token):
    if not isinstance(token, dict):
        return None
    return _text(token.get("mint") or token.get("address"))


def _pool_candidate(pool, pools):
    if not isinstance(pool, dict):
        return None
    address = _text(pool_address(pool))
    if not address:
        return None

    volume = _number(pool.get("volume24h"))
    txs = _number(
        pool.get("txns24h")
        if pool.get("txns24h") is not None
        else pool.get("transactions24h")
    )
    if volume != 0.0 or txs != 0.0:
        return None

    base = _token_mint(pool.get("baseToken"))
    quote = _token_mint(pool.get("quoteToken"))
    if base == WRAPPED_XNT_MINT and quote and quote != WRAPPED_XNT_MINT:
        asset_mint = quote
    elif quote == WRAPPED_XNT_MINT and base and base != WRAPPED_XNT_MINT:
        asset_mint = base
    else:
        return None

    matches = [
        match
        for match in find_matches_for_term(asset_mint, pools)
        if len(match) >= 4 and match[3] >= 90
    ]
    addresses = []
    seen = set()
    for match in matches:
        selected = _text(pool_address(match[0]))
        if selected and selected not in seen:
            seen.add(selected)
            addresses.append(selected)
    if addresses != [address]:
        return None

    return {
        "asset_mint": asset_mint,
        "pool_address": address,
        "matches": matches,
        "provider_volume24h": volume,
        "provider_transactions24h": int(txs),
        "liquidity": _number(pool.get("liquidity")) or 0.0,
    }


def _active_pool_candidate(pool, pools):
    if not isinstance(pool, dict):
        return None
    address = _text(pool_address(pool))
    if not address:
        return None

    volume = _number(pool.get("volume24h"))
    txs = _number(
        pool.get("txns24h")
        if pool.get("txns24h") is not None
        else pool.get("transactions24h")
    )
    if (
        volume is None
        or volume <= 0
        or txs is None
        or txs <= 0
        or txs > 30
        or not float(txs).is_integer()
    ):
        return None

    base = _token_mint(pool.get("baseToken"))
    quote = _token_mint(pool.get("quoteToken"))
    if base == WRAPPED_XNT_MINT and quote and quote != WRAPPED_XNT_MINT:
        asset_mint = quote
    elif quote == WRAPPED_XNT_MINT and base and base != WRAPPED_XNT_MINT:
        asset_mint = base
    else:
        return None

    matches = [
        match
        for match in find_matches_for_term(asset_mint, pools)
        if len(match) >= 4 and match[3] >= 90
    ]
    addresses = []
    seen = set()
    for match in matches:
        selected = _text(pool_address(match[0]))
        if selected and selected not in seen:
            seen.add(selected)
            addresses.append(selected)
    if addresses != [address]:
        return None

    return {
        "asset_mint": asset_mint,
        "pool_address": address,
        "matches": matches,
        "provider_volume24h": volume,
        "provider_transactions24h": int(txs),
        "liquidity": _number(pool.get("liquidity")) or 0.0,
    }


def _identity_from_current_rpc(pool_address_value, asset_mint):
    snapshot = collect_ninja_price_fact_time_snapshot(
        pool_addresses=[pool_address_value]
    )
    rows = [
        row
        for row in snapshot.get("pools") or []
        if isinstance(row, dict)
        and _text(row.get("pool_address")) == pool_address_value
    ]
    if len(rows) != 1 or rows[0].get("status") != "ok":
        raise AssertionError("current pool RPC snapshot unavailable")

    rpc = rows[0].get("rpc")
    if not isinstance(rpc, dict) or rpc.get("rpc_reserve_ratio_verified") is not True:
        raise AssertionError("current pool RPC identity unavailable")

    mint_0 = _text(rpc.get("mint_0"))
    mint_1 = _text(rpc.get("mint_1"))
    vault_0 = _text(rpc.get("vault_0"))
    vault_1 = _text(rpc.get("vault_1"))
    if not all([mint_0, mint_1, vault_0, vault_1]):
        raise AssertionError("decoded pool mint/vault identity incomplete")

    v0 = get_token_account_info(vault_0)
    v1 = get_token_account_info(vault_1)
    if (
        not isinstance(v0, dict)
        or not isinstance(v1, dict)
        or v0.get("identity_verified") is not True
        or v1.get("identity_verified") is not True
    ):
        raise AssertionError("current vault token-account identity unavailable")
    owner_0 = _text(v0.get("token_authority"))
    owner_1 = _text(v1.get("token_authority"))
    if not owner_0 or owner_0 != owner_1:
        raise AssertionError("current vault shared authority unverified")

    if mint_0 == asset_mint:
        asset_vault = vault_0
        counter_mint = mint_1
        counter_vault = vault_1
    elif mint_1 == asset_mint:
        asset_vault = vault_1
        counter_mint = mint_0
        counter_vault = vault_0
    else:
        raise AssertionError("decoded pool does not contain selected asset mint")

    return {
        "chain": "x1",
        "pool_address": pool_address_value,
        "asset_mint": asset_mint,
        "asset_vault": asset_vault,
        "counter_mint": counter_mint,
        "counter_vault": counter_vault,
        "shared_owner": owner_0,
        "identity_verified": True,
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_ROLLING_24H_ACTIVITY_LIVE=1 for live #502 evidence",
)
class X1Rolling24hMarketActivityLiveTests(unittest.TestCase):
    def test_prove_one_exact_zero_24h_market_from_x1_rpc(self):
        self.assertGreaterEqual(MAX_CANDIDATES, 1)
        self.assertLessEqual(MAX_CANDIDATES, 30)
        self.assertGreaterEqual(MAX_SIGNATURES, 100)
        self.assertLessEqual(MAX_SIGNATURES, 100000)

        pools, xnt_price_usd = fetch_all_pools(sleep_seconds=0)
        self.assertTrue(pools, "X1.Ninja returned no current pool catalog")

        candidates = []
        seen = set()
        for pool in pools:
            candidate = _pool_candidate(pool, pools)
            if not candidate:
                continue
            address = candidate["pool_address"]
            if address in seen:
                continue
            seen.add(address)
            candidates.append(candidate)

        candidates.sort(
            key=lambda row: (
                row["liquidity"],
                row["pool_address"],
            )
        )
        candidates = candidates[:MAX_CANDIDATES]
        self.assertTrue(
            candidates,
            "no exact single-pool wrapped-XNT market currently reports provider 24h volume=0 and transactions=0",
        )

        attempts = []
        verified = None

        for candidate in candidates:
            asset_mint = candidate["asset_mint"]
            address = candidate["pool_address"]
            report = {
                "asset_mint": asset_mint,
                "pool_address": address,
                "provider_volume24h": candidate["provider_volume24h"],
                "provider_transactions24h": candidate["provider_transactions24h"],
                "liquidity": candidate["liquidity"],
            }
            try:
                catalog = SimpleNamespace(
                    xnt_price_usd=xnt_price_usd,
                    last_refresh=time.time(),
                )
                market = build_market_report_response(
                    asset_mint,
                    candidate["matches"],
                    catalog,
                    chain="x1",
                    observed_at=time.time(),
                )
                report["market_status"] = market.get("status")
                if market.get("status") not in {"ok", "partial"}:
                    report["result"] = "market_unavailable"
                    attempts.append(report)
                    continue

                data = market.get("data") if isinstance(market.get("data"), dict) else {}
                if (
                    data.get("volume_24h_usd") != 0
                    or data.get("transactions_24h") != 0
                    or (data.get("completeness") or {}).get("volume_24h") is not True
                    or (data.get("completeness") or {}).get("transactions_24h") is not True
                ):
                    report["result"] = "aggregate_provider_zero_not_preserved"
                    attempts.append(report)
                    continue

                scope = evaluate_x1_ninja_current_pool_scope(
                    market_envelope=market,
                    catalog_pools=pools,
                )
                report["pool_scope_verified"] = scope.get(
                    "provider_scoped_pool_universe_verified"
                )
                if scope.get("provider_scoped_pool_universe_verified") is not True:
                    report["result"] = "pool_scope_unverified"
                    attempts.append(report)
                    continue

                pool_identity = _identity_from_current_rpc(address, asset_mint)
                end_epoch = int(time.time())
                start_epoch = end_epoch - 86400
                pool_window = reconstruct_x1_pool_24h_chain_activity(
                    pool_identity=pool_identity,
                    start_epoch=start_epoch,
                    end_epoch=end_epoch,
                    max_signatures=MAX_SIGNATURES,
                )
                report["history_range_proven"] = pool_window.get(
                    "history_range_proven"
                )
                report["window_signature_count"] = pool_window.get(
                    "window_signature_count"
                )
                report["classification_ambiguity_count"] = pool_window.get(
                    "classification_ambiguity_count"
                )
                report["chain_transactions_24h"] = pool_window.get(
                    "verified_transactions_24h"
                )
                report["chain_volume_24h_usd"] = pool_window.get(
                    "verified_volume_24h_usd"
                )

                rolling = evaluate_x1_rolling_24h_market_activity(
                    market_envelope=market,
                    pool_scope_evidence=scope,
                    pool_windows=[pool_window],
                    evaluated_at=end_epoch,
                )
                report["rolling_status"] = rolling.get("status")
                report["rolling_failures"] = rolling.get("failures")
                report["transactions_24h_freshness_verified"] = rolling.get(
                    "transactions_24h_freshness_verified"
                )
                report["volume_24h_freshness_verified"] = rolling.get(
                    "volume_24h_freshness_verified"
                )
                attempts.append(report)

                if (
                    rolling.get("transactions_24h_freshness_verified") is True
                    and rolling.get("volume_24h_freshness_verified") is True
                ):
                    verified = {
                        "candidate": candidate,
                        "market": market,
                        "pool_scope": scope,
                        "pool_identity": pool_identity,
                        "pool_window": pool_window,
                        "rolling_activity": rolling,
                    }
                    break
            except Exception as exc:
                report["result"] = "exception"
                report["error"] = f"{type(exc).__name__}: {exc}"
                attempts.append(report)

        evidence = {
            "schema": "x1_502_rolling_24h_live.v1",
            "chain": "x1",
            "candidate_count": len(candidates),
            "attempts": attempts,
            "verified_market": verified,
            "zero_activity_value_scope_only": True,
            "universal_nonzero_usd_volume_semantics_verified": False,
            "provider_fact_time_verified": False,
            "source_independence_verified": False,
            "public_service_promoted": False,
            "scout_reliance_promoted": False,
            "execution_authorized": False,
        }
        print("X1 #502 ROLLING 24H LIVE EVIDENCE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertIsNotNone(
            verified,
            f"no exact zero provider market reproduced as zero over a complete X1 RPC 24h chain window: {attempts}",
        )
        rolling = verified["rolling_activity"]
        window = verified["pool_window"]
        self.assertTrue(window["history_range_proven"])
        self.assertTrue(window["history_integrity_verified"])
        self.assertTrue(window["all_successful_transactions_verified"])
        self.assertTrue(window["all_pool_relevant_transactions_classified"])
        self.assertEqual(window["verified_transactions_24h"], 0)
        self.assertEqual(window["verified_volume_24h_usd"], "0")
        self.assertEqual(
            window["usd_valuation_basis"],
            "exact_zero_swap_volume_requires_no_price_conversion",
        )
        self.assertTrue(rolling["transactions_24h_window_coverage_verified"])
        self.assertTrue(rolling["transactions_24h_semantics_verified"])
        self.assertTrue(rolling["transactions_24h_freshness_verified"])
        self.assertTrue(rolling["volume_24h_window_coverage_verified"])
        self.assertTrue(rolling["volume_24h_semantics_verified"])
        self.assertTrue(rolling["volume_24h_freshness_verified"])
        self.assertFalse(rolling["provider_fact_time_verified"])
        self.assertFalse(rolling["source_independence_verified"])
        self.assertFalse(rolling["execution_authorized"])


    def test_prove_one_active_market_transaction_count_from_x1_rpc(self):
        pools, xnt_price_usd = fetch_all_pools(sleep_seconds=0)
        self.assertTrue(pools, "X1.Ninja returned no current pool catalog")

        candidates = []
        seen = set()
        for pool in pools:
            candidate = _active_pool_candidate(pool, pools)
            if not candidate:
                continue
            address = candidate["pool_address"]
            if address in seen:
                continue
            seen.add(address)
            candidates.append(candidate)

        candidates.sort(
            key=lambda row: (
                row["provider_transactions24h"],
                -row["liquidity"],
                row["pool_address"],
            )
        )
        candidates = candidates[:MAX_CANDIDATES]
        self.assertTrue(
            candidates,
            "no exact single-pool wrapped-XNT active market with <=30 provider transactions is available",
        )

        attempts = []
        verified = None

        for candidate in candidates:
            asset_mint = candidate["asset_mint"]
            address = candidate["pool_address"]
            report = {
                "asset_mint": asset_mint,
                "pool_address": address,
                "provider_volume24h": candidate["provider_volume24h"],
                "provider_transactions24h": candidate["provider_transactions24h"],
                "liquidity": candidate["liquidity"],
            }
            try:
                catalog = SimpleNamespace(
                    xnt_price_usd=xnt_price_usd,
                    last_refresh=time.time(),
                )
                market = build_market_report_response(
                    asset_mint,
                    candidate["matches"],
                    catalog,
                    chain="x1",
                    observed_at=time.time(),
                )
                report["market_status"] = market.get("status")
                if market.get("status") not in {"ok", "partial"}:
                    report["result"] = "market_unavailable"
                    attempts.append(report)
                    continue

                scope = evaluate_x1_ninja_current_pool_scope(
                    market_envelope=market,
                    catalog_pools=pools,
                )
                report["pool_scope_verified"] = scope.get(
                    "provider_scoped_pool_universe_verified"
                )
                if scope.get("provider_scoped_pool_universe_verified") is not True:
                    report["result"] = "pool_scope_unverified"
                    attempts.append(report)
                    continue

                pool_identity = _identity_from_current_rpc(address, asset_mint)
                end_epoch = int(time.time())
                start_epoch = end_epoch - 86400
                pool_window = reconstruct_x1_pool_24h_chain_activity(
                    pool_identity=pool_identity,
                    start_epoch=start_epoch,
                    end_epoch=end_epoch,
                    max_signatures=MAX_SIGNATURES,
                )
                rolling = evaluate_x1_rolling_24h_market_activity(
                    market_envelope=market,
                    pool_scope_evidence=scope,
                    pool_windows=[pool_window],
                    evaluated_at=end_epoch,
                )
                report["history_range_proven"] = pool_window.get(
                    "history_range_proven"
                )
                report["window_signature_count"] = pool_window.get(
                    "window_signature_count"
                )
                report["classification_ambiguity_count"] = pool_window.get(
                    "classification_ambiguity_count"
                )
                report["chain_transactions_24h"] = pool_window.get(
                    "verified_transactions_24h"
                )
                report["transactions_24h_freshness_verified"] = rolling.get(
                    "transactions_24h_freshness_verified"
                )
                report["volume_24h_freshness_verified"] = rolling.get(
                    "volume_24h_freshness_verified"
                )
                report["rolling_failures"] = rolling.get("failures")
                attempts.append(report)

                if (
                    rolling.get("transactions_24h_freshness_verified") is True
                    and (pool_window.get("verified_transactions_24h") or 0) > 0
                ):
                    verified = {
                        "candidate": candidate,
                        "pool_window": pool_window,
                        "rolling_activity": rolling,
                    }
                    break
            except Exception as exc:
                report["result"] = "exception"
                report["error"] = f"{type(exc).__name__}: {exc}"
                attempts.append(report)

        evidence = {
            "schema": "x1_502_nonzero_transaction_count_live.v1",
            "chain": "x1",
            "candidate_count": len(candidates),
            "attempts": attempts,
            "verified_market": verified,
            "nonzero_transaction_count_semantics_verified": verified is not None,
            "nonzero_usd_volume_semantics_verified": False,
            "provider_fact_time_verified": False,
            "source_independence_verified": False,
            "execution_authorized": False,
        }
        print("X1 #502 NONZERO TRANSACTION COUNT LIVE EVIDENCE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertIsNotNone(
            verified,
            f"no active exact market reproduced the provider transaction count from a complete X1 RPC 24h chain window: {attempts}",
        )
        rolling = verified["rolling_activity"]
        window = verified["pool_window"]
        self.assertTrue(window["history_range_proven"])
        self.assertTrue(window["all_successful_transactions_verified"])
        self.assertTrue(window["all_pool_relevant_transactions_classified"])
        self.assertGreater(window["verified_transactions_24h"], 0)
        self.assertTrue(rolling["transactions_24h_window_coverage_verified"])
        self.assertTrue(rolling["transactions_24h_semantics_verified"])
        self.assertTrue(rolling["transactions_24h_freshness_verified"])
        self.assertFalse(rolling["volume_24h_freshness_verified"])
        self.assertFalse(rolling["provider_fact_time_verified"])
        self.assertFalse(rolling["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
