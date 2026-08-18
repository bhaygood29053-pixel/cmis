import os
import struct
import unittest
from decimal import Decimal

import requests

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.rpc import get_token_account_info
from liquidity_scout.providers.x1.xdex import fetch_swap_quote


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
AMM_CONFIG = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"
XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT = "So11111111111111111111111111111111111111112"
ORACLE_SELL_QUOTE = "https://oracle.xdex.xyz/api/v1/token/sell-quote"
FEE_DENOM = 1_000_000
EXPECTED_TRADE_FEE_RATE = 2_800


def _u64(data, offset):
    return struct.unpack_from("<Q", data, offset)[0]


def _pubkey(data, offset):
    return encode_base58_pubkey(data[offset : offset + 32])


def _ceil_fee(amount, rate):
    return (amount * rate + FEE_DENOM - 1) // FEE_DENOM if rate else 0


def _pool_state():
    state = fetch_account_state(POOL)
    data = state["data"]
    if state.get("owner") != PROGRAM or len(data) != 637:
        raise AssertionError("Pinned XENCAT/XNT pool no longer matches verified XDEX state")
    return {
        "amm_config": _pubkey(data, 8),
        "vault_0": _pubkey(data, 72),
        "vault_1": _pubkey(data, 104),
        "mint_0": _pubkey(data, 168),
        "mint_1": _pubkey(data, 200),
        "decimals_0": data[331],
        "decimals_1": data[332],
        "protocol_fees_0": _u64(data, 341),
        "protocol_fees_1": _u64(data, 349),
        "fund_fees_0": _u64(data, 357),
        "fund_fees_1": _u64(data, 365),
        "creator_fees_0": _u64(data, 397),
        "creator_fees_1": _u64(data, 405),
    }


def _config_state():
    state = fetch_account_state(AMM_CONFIG)
    data = state["data"]
    if state.get("owner") != PROGRAM or len(data) < 116:
        raise AssertionError("Pinned AMM config no longer matches verified XDEX state")
    return {
        "trade_fee_rate": _u64(data, 12),
        "protocol_fee_rate": _u64(data, 20),
        "fund_fee_rate": _u64(data, 28),
        "creator_fee_rate": _u64(data, 108),
    }


def _active_reserves(pool):
    v0 = get_token_account_info(pool["vault_0"])
    v1 = get_token_account_info(pool["vault_1"])
    if not v0 or not v1 or not v0.get("identity_verified") or not v1.get("identity_verified"):
        raise AssertionError("Pinned XDEX vault identity could not be verified")
    r0 = int(v0["raw_amount"]) - pool["protocol_fees_0"] - pool["fund_fees_0"] - pool["creator_fees_0"]
    r1 = int(v1["raw_amount"]) - pool["protocol_fees_1"] - pool["fund_fees_1"] - pool["creator_fees_1"]
    return r0, r1


def _raw_amount(ui_amount, decimals):
    scaled = Decimal(str(ui_amount)) * (Decimal(10) ** decimals)
    if scaled != scaled.to_integral_value():
        raise AssertionError("Amount is not exactly representable in raw token units")
    return int(scaled)


def _curve_exact_in(raw_input, reserve_in, reserve_out, trade_fee_rate):
    trade_fee = _ceil_fee(raw_input, trade_fee_rate)
    net_input = raw_input - trade_fee
    raw_output = net_input * reserve_out // (reserve_in + net_input)
    return raw_output, trade_fee


def _oracle_sell_quote(amount):
    response = requests.get(
        ORACLE_SELL_QUOTE,
        params={"token_address": XENCAT, "amount_in": str(amount), "details": "true"},
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("success") or not isinstance(body.get("data"), dict):
        raise AssertionError(f"Unexpected XDEX Oracle sell-quote response: {body}")
    return body["data"]


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1 to run read-only XDEX output/slippage evidence",
)
class XDEXOutputSlippageSemanticLiveTests(unittest.TestCase):
    def test_oracle_swap_quote_and_cp_curve_localize_output_adjustment(self):
        pool = _pool_state()
        config = _config_state()
        self.assertEqual(pool["amm_config"], AMM_CONFIG)
        self.assertEqual(config["trade_fee_rate"], EXPECTED_TRADE_FEE_RATE)
        self.assertEqual(config["creator_fee_rate"], 0)

        r0, r1 = _active_reserves(pool)
        by_mint = {
            pool["mint_0"]: (r0, pool["decimals_0"]),
            pool["mint_1"]: (r1, pool["decimals_1"]),
        }
        reserve_in, decimals_in = by_mint[XENCAT]
        reserve_out, decimals_out = by_mint[XNT]

        rows = []
        for amount in (Decimal("1"), Decimal("2"), Decimal("1000"), Decimal("10000")):
            raw_input = _raw_amount(amount, decimals_in)
            cp_raw_output, trade_fee_raw = _curve_exact_in(
                raw_input, reserve_in, reserve_out, config["trade_fee_rate"]
            )
            cp_ui_output = Decimal(cp_raw_output) / (Decimal(10) ** decimals_out)

            swap = fetch_swap_quote(XENCAT, XNT, amount, is_exact_amount_in=True)
            oracle = _oracle_sell_quote(amount)

            self.assertEqual(swap.get("inputMint"), XENCAT)
            self.assertEqual(swap.get("outputMint"), XNT)
            self.assertEqual(swap.get("amm_config_address"), AMM_CONFIG)
            self.assertEqual(oracle.get("selected_pool"), POOL)

            swap_output = Decimal(str(swap.get("outputAmount")))
            oracle_raw_output = int(str(oracle.get("amount_out_quote")))
            oracle_ui_output = Decimal(oracle_raw_output) / (Decimal(10) ** decimals_out)

            swap_to_cp = swap_output / cp_ui_output if cp_ui_output else Decimal(0)
            oracle_to_cp = oracle_ui_output / cp_ui_output if cp_ui_output else Decimal(0)
            swap_to_oracle = swap_output / oracle_ui_output if oracle_ui_output else Decimal(0)

            # Diagnostic hypothesis only. 0.995 is exactly a 0.5% haircut.
            swap_vs_half_percent_min = swap_output / (cp_ui_output * Decimal("0.995"))
            oracle_vs_half_percent_min = oracle_ui_output / (cp_ui_output * Decimal("0.995"))

            rows.append({
                "amount_in_xencat": str(amount),
                "trade_fee_raw": trade_fee_raw,
                "protocol_fee_rate_raw": config["protocol_fee_rate"],
                "fund_fee_rate_raw": config["fund_fee_rate"],
                "creator_fee_rate_raw": config["creator_fee_rate"],
                "cp_output_xnt": str(cp_ui_output),
                "swap_output_xnt": str(swap_output),
                "oracle_output_xnt": str(oracle_ui_output),
                "swap_to_cp_ratio": str(swap_to_cp),
                "oracle_to_cp_ratio": str(oracle_to_cp),
                "swap_to_oracle_ratio": str(swap_to_oracle),
                "swap_vs_exact_0_5pct_min_ratio": str(swap_vs_half_percent_min),
                "oracle_vs_exact_0_5pct_min_ratio": str(oracle_vs_half_percent_min),
                "oracle_usd_out": oracle.get("usd_out"),
                "oracle_effective_price": oracle.get("effective_price"),
                "oracle_pool_depth_usd": oracle.get("best_pool_usd_depth") or oracle.get("pool_depth_usd"),
            })

        print("XDEX output/slippage localization evidence")
        for row in rows:
            print(row)

        # Safety assertions: this test is evidence collection, not semantic promotion.
        self.assertTrue(rows)
        self.assertTrue(all(Decimal(r["swap_to_cp_ratio"]) > 0 for r in rows))
        self.assertTrue(all(Decimal(r["oracle_to_cp_ratio"]) > 0 for r in rows))


if __name__ == "__main__":
    unittest.main()
