import json
import os
import struct
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.candidate_pool_role import extract_pubkey_at
from liquidity_scout.providers.x1.market import fetch_all_pools
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.rpc import get_token_account_info
from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
)


RUN_LIVE = os.getenv("RUN_X1_NINJA_LIQUIDITY_ACCOUNTING_LIVE") == "1"
POOL_STATE_LENGTH = 637
VAULT_0_OFFSET = 72
VAULT_1_OFFSET = 104
MINT_0_OFFSET = 168
MINT_1_OFFSET = 200
LP_SUPPLY_OFFSET = 333
PROTOCOL_FEE_0_OFFSET = 341
PROTOCOL_FEE_1_OFFSET = 349
FUND_FEE_0_OFFSET = 357
FUND_FEE_1_OFFSET = 365
CREATOR_FEE_ON_OFFSET = 389
ENABLE_CREATOR_FEE_OFFSET = 390
CREATOR_FEE_0_OFFSET = 397
CREATOR_FEE_1_OFFSET = 405
POOL_COUNT = 5


def _text(value):
    text = str(value or "").strip()
    return text or None


def _address(row):
    return _text(
        row.get("address")
        or row.get("poolAddress")
        or row.get("pool_address")
        or row.get("id")
    )


def _token_candidates(row):
    values = []
    for side_name in ("baseToken", "quoteToken"):
        side = row.get(side_name)
        if not isinstance(side, dict):
            continue
        for key in ("mint", "address", "tokenAddress", "mintAddress"):
            value = _text(side.get(key))
            if value and value not in values:
                values.append(value)
    return values


def _positive_decimal(value, *, name):
    parsed = Decimal(str(value))
    if not parsed.is_finite() or parsed <= 0:
        raise AssertionError(f"{name} must be positive and finite")
    return parsed


def _u64(data, offset):
    return struct.unpack_from("<Q", data, offset)[0]


def _scaled(raw, decimals):
    return Decimal(raw) / (Decimal(10) ** int(decimals))


def _pool_state(address):
    state = fetch_account_state(address)
    data = state.get("data")
    if not isinstance(data, bytes) or len(data) != POOL_STATE_LENGTH:
        raise AssertionError(f"{address} does not expose accepted 637-byte pool state")

    mint_0 = extract_pubkey_at(data, MINT_0_OFFSET)
    mint_1 = extract_pubkey_at(data, MINT_1_OFFSET)
    vault_0 = extract_pubkey_at(data, VAULT_0_OFFSET)
    vault_1 = extract_pubkey_at(data, VAULT_1_OFFSET)
    v0 = get_token_account_info(vault_0)
    v1 = get_token_account_info(vault_1)
    if v0.get("identity_verified") is not True or v1.get("identity_verified") is not True:
        raise AssertionError(f"{address} vault identity unavailable")
    if _text(v0.get("mint")) != mint_0 or _text(v1.get("mint")) != mint_1:
        raise AssertionError(f"{address} vault mint mismatch")

    reserve_0_raw = int(v0["raw_amount"])
    reserve_1_raw = int(v1["raw_amount"])
    decimals_0 = int(v0["decimals"])
    decimals_1 = int(v1["decimals"])
    protocol_0 = _u64(data, PROTOCOL_FEE_0_OFFSET)
    protocol_1 = _u64(data, PROTOCOL_FEE_1_OFFSET)
    fund_0 = _u64(data, FUND_FEE_0_OFFSET)
    fund_1 = _u64(data, FUND_FEE_1_OFFSET)
    creator_0 = _u64(data, CREATOR_FEE_0_OFFSET)
    creator_1 = _u64(data, CREATOR_FEE_1_OFFSET)
    fee_0_raw = protocol_0 + fund_0 + creator_0
    fee_1_raw = protocol_1 + fund_1 + creator_1
    net_0_raw = reserve_0_raw - fee_0_raw
    net_1_raw = reserve_1_raw - fee_1_raw
    if net_0_raw <= 0 or net_1_raw <= 0:
        raise AssertionError(f"{address} candidate fee subtraction exhausts vault")

    return {
        "address": address,
        "owner": state.get("owner"),
        "context_slot": state.get("context_slot"),
        "mint_0": mint_0,
        "mint_1": mint_1,
        "vault_0": vault_0,
        "vault_1": vault_1,
        "decimals_0": decimals_0,
        "decimals_1": decimals_1,
        "gross_0": _scaled(reserve_0_raw, decimals_0),
        "gross_1": _scaled(reserve_1_raw, decimals_1),
        "net_0": _scaled(net_0_raw, decimals_0),
        "net_1": _scaled(net_1_raw, decimals_1),
        "protocol_fee_0": _scaled(protocol_0, decimals_0),
        "protocol_fee_1": _scaled(protocol_1, decimals_1),
        "fund_fee_0": _scaled(fund_0, decimals_0),
        "fund_fee_1": _scaled(fund_1, decimals_1),
        "creator_fee_0": _scaled(creator_0, decimals_0),
        "creator_fee_1": _scaled(creator_1, decimals_1),
        "total_fee_0": _scaled(fee_0_raw, decimals_0),
        "total_fee_1": _scaled(fee_1_raw, decimals_1),
        "lp_supply_raw": _u64(data, LP_SUPPLY_OFFSET),
        "creator_fee_on": data[CREATOR_FEE_ON_OFFSET],
        "enable_creator_fee": bool(data[ENABLE_CREATOR_FEE_OFFSET]),
    }


def _orient_xnt(state, expected_asset=None):
    if state["mint_0"] == WRAPPED_XNT_MINT and state["mint_1"] != WRAPPED_XNT_MINT:
        asset = state["mint_1"]
        return {
            "asset_mint": asset,
            "gross_xnt": state["gross_0"],
            "gross_asset": state["gross_1"],
            "net_xnt": state["net_0"],
            "net_asset": state["net_1"],
            "fee_xnt": state["total_fee_0"],
            "fee_asset": state["total_fee_1"],
        }
    if state["mint_1"] == WRAPPED_XNT_MINT and state["mint_0"] != WRAPPED_XNT_MINT:
        asset = state["mint_0"]
        return {
            "asset_mint": asset,
            "gross_xnt": state["gross_1"],
            "gross_asset": state["gross_0"],
            "net_xnt": state["net_1"],
            "net_asset": state["net_0"],
            "fee_xnt": state["total_fee_1"],
            "fee_asset": state["total_fee_0"],
        }
    raise AssertionError("pool does not contain exactly one wrapped-XNT mint")


def _pct_gap(observed, expected):
    return (expected - observed) / expected * Decimal(100)


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NINJA_LIQUIDITY_ACCOUNTING_LIVE=1 for read-only chain accounting evidence",
)
class X1NinjaLiquidityAccountingLiveTests(unittest.TestCase):
    def test_fee_excluded_reserves_explain_461_liquidity_gap(self):
        ninja_pools, provider_xnt_price_usd = fetch_all_pools(sleep_seconds=0)
        by_address = {
            _address(row): row
            for row in ninja_pools
            if isinstance(row, dict) and _address(row)
        }
        usable = [
            row for row in ninja_pools
            if isinstance(row, dict)
            and _address(row)
            and WRAPPED_XNT_MINT in _token_candidates(row)
            and Decimal(str(row.get("liquidity") or 0)) > 0
        ]
        reference_candidates = [
            row for row in usable if USDC_X_MINT in _token_candidates(row)
        ]
        self.assertTrue(reference_candidates, "no XNT/USDC.X reference pool")
        reference = max(
            reference_candidates,
            key=lambda row: Decimal(str(row.get("liquidity") or 0)),
        )
        reference_address = _address(reference)
        reference_state = _pool_state(reference_address)
        reference_oriented = _orient_xnt(reference_state)
        self.assertEqual(reference_oriented["asset_mint"], USDC_X_MINT)

        gross_xnt_usdcx = (
            reference_oriented["gross_asset"] / reference_oriented["gross_xnt"]
        )
        net_xnt_usdcx = (
            reference_oriented["net_asset"] / reference_oriented["net_xnt"]
        )

        candidates = [
            row for row in usable
            if _address(row) != reference_address
            and USDC_X_MINT not in _token_candidates(row)
        ]
        candidates.sort(
            key=lambda row: Decimal(str(row.get("liquidity") or 0)),
            reverse=True,
        )
        selected = candidates[:POOL_COUNT]
        self.assertEqual(len(selected), POOL_COUNT)

        rows = []
        for provider in selected:
            address = _address(provider)
            state = _pool_state(address)
            oriented = _orient_xnt(state)
            ninja_liquidity = _positive_decimal(
                provider.get("liquidity"),
                name=f"{address} Ninja liquidity",
            )

            gross_value = Decimal(2) * oriented["gross_xnt"] * gross_xnt_usdcx
            net_value_gross_ref = Decimal(2) * oriented["net_xnt"] * gross_xnt_usdcx
            net_value_net_ref = Decimal(2) * oriented["net_xnt"] * net_xnt_usdcx
            gross_gap = _pct_gap(ninja_liquidity, gross_value)
            net_gap_gross_ref = _pct_gap(ninja_liquidity, net_value_gross_ref)
            net_gap_net_ref = _pct_gap(ninja_liquidity, net_value_net_ref)

            rows.append({
                "pool_address": address,
                "asset_mint": oriented["asset_mint"],
                "ninja_liquidity": format(ninja_liquidity, "f"),
                "gross_xnt_reserve": format(oriented["gross_xnt"], "f"),
                "fee_excluded_xnt_reserve": format(oriented["net_xnt"], "f"),
                "candidate_fee_xnt": format(oriented["fee_xnt"], "f"),
                "candidate_fee_asset": format(oriented["fee_asset"], "f"),
                "candidate_fee_xnt_pct_of_gross": format(
                    oriented["fee_xnt"] / oriented["gross_xnt"] * Decimal(100),
                    "f",
                ),
                "gross_two_sided_value": format(gross_value, "f"),
                "fee_excluded_value_gross_reference": format(net_value_gross_ref, "f"),
                "fee_excluded_value_net_reference": format(net_value_net_ref, "f"),
                "gross_gap_pct": format(gross_gap, "f"),
                "fee_excluded_gap_pct_gross_reference": format(net_gap_gross_ref, "f"),
                "fee_excluded_gap_pct_net_reference": format(net_gap_net_ref, "f"),
                "protocol_fee_0": format(state["protocol_fee_0"], "f"),
                "protocol_fee_1": format(state["protocol_fee_1"], "f"),
                "fund_fee_0": format(state["fund_fee_0"], "f"),
                "fund_fee_1": format(state["fund_fee_1"], "f"),
                "creator_fee_0": format(state["creator_fee_0"], "f"),
                "creator_fee_1": format(state["creator_fee_1"], "f"),
                "creator_fee_on": state["creator_fee_on"],
                "enable_creator_fee": state["enable_creator_fee"],
                "lp_supply_raw": state["lp_supply_raw"],
                "pool_state_slot": state["context_slot"],
            })

        evidence = {
            "schema": "x1_liquidity_461_fee_accounting_candidate.v1",
            "chain": "x1",
            "real_network_calls": True,
            "candidate_layout": "Raydium CP-Swap compatible 637-byte PoolState",
            "fee_counter_offsets_semantics_verified_for_xdex": False,
            "reference_pool": reference_address,
            "gross_xnt_usdcx": format(gross_xnt_usdcx, "f"),
            "fee_excluded_xnt_usdcx": format(net_xnt_usdcx, "f"),
            "ninja_xntPriceUsd_diagnostic": provider_xnt_price_usd,
            "reference_candidate_fee_xnt": format(reference_oriented["fee_xnt"], "f"),
            "reference_candidate_fee_usdcx": format(reference_oriented["fee_asset"], "f"),
            "samples": rows,
            "liquidity_accounting_adjustment_verified": False,
            "liquidity_freshness_verified": False,
            "cmis_promotable": False,
            "execution_authorized": False,
        }
        print("X1 #461 FEE-EXCLUDED POOL ACCOUNTING EVIDENCE")
        print(json.dumps(evidence, sort_keys=True, default=str))

        # Diagnostic job: never promote merely because candidate offsets fit.
        self.assertFalse(evidence["fee_counter_offsets_semantics_verified_for_xdex"])
        self.assertFalse(evidence["liquidity_accounting_adjustment_verified"])
        self.assertFalse(evidence["liquidity_freshness_verified"])
        self.assertFalse(evidence["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
