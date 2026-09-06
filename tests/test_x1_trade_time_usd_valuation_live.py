import json
import os
import time
import unittest
from types import SimpleNamespace

from liquidity_scout.market.resolver import find_matches_for_term, pool_address
from liquidity_scout.providers.x1.bridge_source_provenance import (
    BridgeSourceProof,
    evaluate_bridge_source_provenance,
)
from liquidity_scout.providers.x1.liquidity_freshness import (
    evaluate_x1_ninja_current_pool_scope,
)
from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.ninja_history import fetch_pool_trades_raw
from liquidity_scout.providers.x1.rolling_24h_market_activity import (
    evaluate_x1_rolling_24h_market_activity,
    reconstruct_x1_pool_24h_chain_activity,
)
from liquidity_scout.providers.x1.trade_time_usd_valuation import (
    capture_historical_xnt_usdcx_reference_rate,
    capture_kraken_usdc_usd_fact_price,
    evaluate_historical_usdcx_parity,
    resolve_xnt_quote_usd_value,
)
from liquidity_scout.providers.x1.usdcx_destination_parity import (
    SOLANA_USDC_MINT,
    WARP_USDC_ROUTE_ID,
    X1_USDC_X_MINT,
    evaluate_usdcx_destination_parity,
)
from liquidity_scout.providers.x1.warp_bridged_supply_evidence import (
    build_warp_bridged_supply_evidence,
    capture_destination_mint_observation,
    capture_source_vault_observation,
)
from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SOURCE_URL,
    build_warp_config_route_observation,
)
from liquidity_scout.providers.x1.warp_lifecycle_rpc_retry import (
    resilient_get_transaction_post,
)
from liquidity_scout.providers.x1.warp_message_interval_retention import (
    capture_warp_message_interval_retention,
)
from liquidity_scout.providers.x1.warp_message_retention_coverage import (
    evaluate_warp_message_counter_closure,
    fetch_classified_warp_config_account,
    fetch_official_warp_config,
)
from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    capture_warp_message_state,
    normalize_warp_route_events,
)
from liquidity_scout.services.cmis_bridge_route_evidence import (
    qualify_warp_bridge_route,
)
from liquidity_scout.services.cmis_cross_chain_provenance import (
    build_cross_chain_asset_provenance,
)
from liquidity_scout.services.cmis_market import build_market_report_response
from tests.test_x1_rolling_24h_market_activity_live import (
    _identity_from_current_rpc,
)


RUN_LIVE = os.getenv("RUN_X1_ROLLING_24H_USD_VOLUME_LIVE") == "1"
TARGET_POOL = "CKtXmX82rLBqNkfpCBPUoHLmtZhgBdVWpVPW93hHHCCK"
TARGET_ASSET = "Dj7AY5CXLHtcT5gZ59Kg3nYgx4FUNMR38dZdQcGT3PA6"
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


def _endpoint(chain, mint):
    return {
        "chain": chain,
        "asset_id": mint,
        "asset_id_kind": "mint",
    }


def _build_usdc_route_observation():
    official = fetch_official_warp_config()
    source = _endpoint("solana", SOLANA_USDC_MINT)
    destination = _endpoint("x1", X1_USDC_X_MINT)
    observation = build_warp_config_route_observation(
        config_response=official,
        route_id=WARP_USDC_ROUTE_ID,
        source=source,
        destination=destination,
    )

    provenance = build_cross_chain_asset_provenance(
        canonical_asset_id="usdc",
        origin=source,
        current=destination,
        hops=[
            {
                "source": source,
                "destination": destination,
                "bridge": "Warp Bridge",
                "representation_type": "bridge_representation",
                "custody_model": "unknown",
                "bridge_route_id": WARP_USDC_ROUTE_ID,
            }
        ],
    )
    source_provenance = evaluate_bridge_source_provenance(
        url=WARP_CONFIG_SOURCE_URL,
        proofs=[
            BridgeSourceProof(
                proof_type="official_app_network_observation",
                reference="accepted exact Warp config endpoint",
                exact_url=WARP_CONFIG_SOURCE_URL,
            )
        ],
    )
    qualification = qualify_warp_bridge_route(
        provenance=provenance,
        hop_index=0,
        source_provenance=source_provenance,
        observation=observation,
        evaluated_at=observation["source_observed_at"] + 1,
    )
    if qualification.get("warp_qualified") is not True:
        raise AssertionError("exact Warp USDC route did not qualify")
    return official, observation, qualification


def _target_market(pools, xnt_price_usd):
    rows = [
        row
        for row in pools
        if isinstance(row, dict) and _text(pool_address(row)) == TARGET_POOL
    ]
    if len(rows) != 1:
        raise AssertionError("accepted #504 target pool is unavailable")
    row = rows[0]
    volume = _number(row.get("volume24h"))
    txs = _number(
        row.get("txns24h")
        if row.get("txns24h") is not None
        else row.get("transactions24h")
    )
    if volume is None or volume <= 0 or txs is None or txs <= 0:
        raise AssertionError(
            "accepted #504 target no longer has nonzero provider 24h activity"
        )

    matches = [
        match
        for match in find_matches_for_term(TARGET_ASSET, pools)
        if len(match) >= 4 and match[3] >= 90
    ]
    addresses = []
    seen = set()
    for match in matches:
        address = _text(pool_address(match[0]))
        if address and address not in seen:
            seen.add(address)
            addresses.append(address)
    if addresses != [TARGET_POOL]:
        raise AssertionError(
            f"accepted #504 target pool scope changed: {addresses}"
        )

    catalog = SimpleNamespace(
        xnt_price_usd=xnt_price_usd,
        last_refresh=time.time(),
    )
    market = build_market_report_response(
        TARGET_ASSET,
        matches,
        catalog,
        chain="x1",
        observed_at=time.time(),
    )
    if market.get("status") not in {"ok", "partial"}:
        raise AssertionError("accepted #504 target market report unavailable")
    return market


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_ROLLING_24H_USD_VOLUME_LIVE=1 for live #504 evidence",
)
class X1Rolling24hUsdVolumeLiveTests(unittest.TestCase):
    def test_prove_nonzero_trade_time_usd_volume(self):
        pools, xnt_price_usd = fetch_all_pools(sleep_seconds=0)
        self.assertTrue(pools, "X1.Ninja returned no current pool catalog")
        market = _target_market(pools, xnt_price_usd)
        scope = evaluate_x1_ninja_current_pool_scope(
            market_envelope=market,
            catalog_pools=pools,
        )
        self.assertTrue(scope["provider_scoped_pool_universe_verified"])
        pool_identity = _identity_from_current_rpc(TARGET_POOL, TARGET_ASSET)

        # First reconstruct the exact target window without USD valuation. This
        # independently proves the swap set and gives the oldest transaction
        # fact time. The retention proof below is then scoped to exactly the
        # interval that historical parity reconstruction needs, rather than
        # re-running #441's separate 60-day Bridge Flow gate.
        end_epoch = int(time.time())
        start_epoch = end_epoch - 86400
        unvalued_window = reconstruct_x1_pool_24h_chain_activity(
            pool_identity=pool_identity,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            max_signatures=MAX_SIGNATURES,
        )
        self.assertTrue(unvalued_window["history_range_proven"])
        self.assertTrue(unvalued_window["history_integrity_verified"])
        self.assertTrue(unvalued_window["all_successful_transactions_verified"])
        self.assertTrue(unvalued_window["all_pool_relevant_transactions_classified"])
        self.assertGreater(unvalued_window["verified_transactions_24h"], 0)
        swap_times = [
            int(row["block_time"])
            for row in unvalued_window["transactions"]
            if row.get("classification") == "EXACT_POOL_SWAP"
        ]
        self.assertTrue(swap_times, "nonzero target has no exact swap fact time")
        oldest_swap_fact_time = min(swap_times)

        # Capture exact current reserve/supply observations first. The
        # subsequently captured retained message universe covers these
        # observation times and lets the evaluator reverse route actions to each
        # individual swap fact time.
        official, route_observation, qualification = _build_usdc_route_observation()
        source_vault = capture_source_vault_observation(
            source_mint=SOLANA_USDC_MINT,
        )
        destination_mint = capture_destination_mint_observation(
            destination_mint=X1_USDC_X_MINT,
        )
        backing = build_warp_bridged_supply_evidence(
            route_observation=route_observation,
            source_vault=source_vault,
            destination_mint=destination_mint,
            evaluated_at=time.time(),
        )
        current_parity = evaluate_usdcx_destination_parity(backing)
        self.assertTrue(current_parity["current_reserve_backing_verified"])

        message_state = capture_warp_message_state()
        normalized = normalize_warp_route_events(
            route_observation=route_observation,
            message_state=message_state,
        )
        self.assertTrue(normalized["pairing_semantics_verified"])
        self.assertTrue(normalized["settled_event_semantics_verified"])
        self.assertTrue(normalized["flow_event_normalization_authorized"])

        classified = {
            "solana": fetch_classified_warp_config_account(chain="solana"),
            "x1": fetch_classified_warp_config_account(chain="x1"),
        }
        counter_closure = evaluate_warp_message_counter_closure(
            config_response=official,
            classified_configs=classified,
            message_state=message_state,
        )
        self.assertTrue(counter_closure["counter_account_closure_verified"])
        self.assertTrue(counter_closure["current_message_universe_count_closed"])

        interval_retention = capture_warp_message_interval_retention(
            counter_closure=counter_closure,
            message_state=message_state,
            requested_start=oldest_swap_fact_time,
            as_of=int(time.time()),
            post=resilient_get_transaction_post,
        )
        self.assertTrue(
            interval_retention["interval_retention_complete_verified"]
        )
        self.assertTrue(interval_retention["requested_window_coverage_verified"])
        self.assertTrue(interval_retention["coverage_complete_verified"])
        self.assertTrue(interval_retention["missing_history_zero_authorized"])
        self.assertFalse(
            interval_retention["sixty_day_bridge_flow_retention_promoted"]
        )

        cache = {}
        historical_parity_cache = {}

        def usd_quote_resolver(
            *,
            block_time,
            quote_mint,
            quote_amount,
            pool_identity,
            transaction,
            verification_report,
        ):
            del pool_identity, verification_report
            fact_time = int(block_time)
            fact_slot = transaction.get("slot")
            key = (fact_time, fact_slot, quote_mint, str(quote_amount))
            if key in cache:
                return cache[key]

            reference = capture_historical_xnt_usdcx_reference_rate(
                fact_time=fact_time,
                fact_slot=fact_slot,
            )
            historical_parity = evaluate_historical_usdcx_parity(
                fact_time=fact_time,
                current_backing_evidence=backing,
                normalized_events=normalized,
                lifecycle_retention=interval_retention,
            )
            historical_parity_cache[key] = historical_parity
            canonical = capture_kraken_usdc_usd_fact_price(
                fact_time=fact_time,
            )
            resolved = resolve_xnt_quote_usd_value(
                fact_time=fact_time,
                quote_mint=quote_mint,
                quote_amount=quote_amount,
                reference_rate_evidence=reference,
                historical_usdcx_parity=historical_parity,
                canonical_usdc_usd_evidence=canonical,
            )
            cache[key] = resolved
            return resolved

        pool_window = reconstruct_x1_pool_24h_chain_activity(
            pool_identity=pool_identity,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            max_signatures=MAX_SIGNATURES,
            usd_quote_resolver=usd_quote_resolver,
        )
        rolling = evaluate_x1_rolling_24h_market_activity(
            market_envelope=market,
            pool_scope_evidence=scope,
            pool_windows=[pool_window],
            evaluated_at=end_epoch,
        )

        # Diagnostic-only provider trade rows.  The raw X1.Ninja trade-history
        # structure is an already-observed transport contract, but amount/price
        # financial semantics remain unpromoted.  Match only the exact
        # RPC-verified swap signatures so #504 can test the provider's stored
        # USD valuation hypothesis without using those values as valuation
        # inputs.
        provider_history = fetch_pool_trades_raw(TARGET_POOL)
        raw_provider_trades = (
            provider_history.get("raw_response", {}).get("trades", [])
        )
        exact_swap_signatures = {
            row["signature"]
            for row in pool_window["transactions"]
            if row.get("classification") == "EXACT_POOL_SWAP"
            and row.get("signature")
        }
        provider_trade_rows = [
            dict(row)
            for row in raw_provider_trades
            if isinstance(row, dict) and row.get("txHash") in exact_swap_signatures
        ]

        evidence = {
            "schema": "x1_504_nonzero_trade_time_usd_volume_live.v1",
            "target_pool": TARGET_POOL,
            "target_asset": TARGET_ASSET,
            "route_qualification_verified": qualification["warp_qualified"],
            "current_usdcx_reserve_backing_verified": current_parity[
                "current_reserve_backing_verified"
            ],
            "current_usdc_reserve_raw": current_parity["source_amount_raw"],
            "current_usdcx_supply_raw": current_parity["destination_supply_raw"],
            "current_reserve_surplus_raw": current_parity["reserve_surplus_raw"],
            "interval_retention_complete_verified": interval_retention[
                "interval_retention_complete_verified"
            ],
            "retention_requested_start": interval_retention["requested_start"],
            "retention_as_of": interval_retention["as_of"],
            "sixty_day_bridge_flow_retention_promoted": interval_retention[
                "sixty_day_bridge_flow_retention_promoted"
            ],
            "normalized_usdc_route_event_count": len(normalized["events"]),
            "normalized_usdc_route_unresolved_counts": normalized[
                "unresolved_counts"
            ],
            "normalized_usdc_route_unresolved_records": normalized.get(
                "unresolved_records", []
            ),
            "verified_transactions_24h": pool_window[
                "verified_transactions_24h"
            ],
            "verified_quote_volume_24h": pool_window[
                "verified_quote_volume_24h"
            ],
            "verified_quote_volume_unit": pool_window[
                "verified_quote_volume_unit"
            ],
            "reconstructed_volume_24h_usd": pool_window[
                "verified_volume_24h_usd"
            ],
            "provider_volume_24h_usd": rolling["provider_volume_24h_usd"],
            "volume_24h_comparison": rolling["volume_24h_comparison"],
            "transactions_24h_freshness_verified": rolling[
                "transactions_24h_freshness_verified"
            ],
            "volume_24h_freshness_verified": rolling[
                "volume_24h_freshness_verified"
            ],
            "nonzero_volume_usd_semantics_verified": rolling[
                "nonzero_volume_usd_semantics_verified"
            ],
            "provider_fact_time_verified": rolling[
                "provider_fact_time_verified"
            ],
            "source_independence_verified": rolling[
                "source_independence_verified"
            ],
            "public_service_promoted": rolling["public_service_promoted"],
            "scout_reliance_promoted": rolling["scout_reliance_promoted"],
            "execution_authorized": rolling["execution_authorized"],
            "historical_parity_evidence": [
                historical_parity_cache[key]
                for key in sorted(historical_parity_cache, key=str)
            ],
            "provider_trade_rows_for_exact_swaps": provider_trade_rows,
            "provider_trade_row_financial_semantics_promoted": False,
            "transactions": pool_window["transactions"],
        }
        print("X1 #504 NONZERO TRADE-TIME USD VOLUME LIVE EVIDENCE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        self.assertGreater(pool_window["verified_transactions_24h"], 0)
        self.assertTrue(pool_window["history_range_proven"])
        self.assertTrue(pool_window["history_integrity_verified"])
        self.assertTrue(pool_window["all_successful_transactions_verified"])
        self.assertTrue(pool_window["all_pool_relevant_transactions_classified"])
        self.assertTrue(pool_window["usd_valuation_coverage_verified"])
        self.assertTrue(pool_window["nonzero_volume_usd_semantics_verified"])
        self.assertTrue(pool_window["volume_24h_value_verified"])
        self.assertIsNotNone(pool_window["verified_volume_24h_usd"])

        for transaction in pool_window["transactions"]:
            if transaction.get("classification") != "EXACT_POOL_SWAP":
                continue
            self.assertTrue(transaction["historical_usd_value_verified"])
            usd = transaction["usd_evidence"]
            self.assertTrue(usd["historical_usd_value_verified"])
            self.assertTrue(usd["fact_time_verified"])
            self.assertFalse(usd["current_price_substitution_used"])
            self.assertFalse(usd["provider_usd_price_used"])
            self.assertFalse(usd["stable_name_one_dollar_assumption_used"])

        self.assertTrue(rolling["transactions_24h_freshness_verified"])
        self.assertTrue(rolling["volume_24h_window_coverage_verified"])
        self.assertTrue(rolling["volume_24h_semantics_verified"])
        self.assertTrue(rolling["volume_24h_freshness_verified"])
        self.assertTrue(rolling["nonzero_volume_usd_semantics_verified"])
        self.assertTrue(rolling["volume_24h_comparison"]["within_tolerance"])
        self.assertFalse(rolling["provider_fact_time_verified"])
        self.assertFalse(rolling["source_independence_verified"])
        self.assertFalse(rolling["public_service_promoted"])
        self.assertFalse(rolling["scout_reliance_promoted"])
        self.assertFalse(rolling["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
