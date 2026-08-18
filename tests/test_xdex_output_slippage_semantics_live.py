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
BPS_DENOM = Decimal("10000")
HALF_PERCENT_FACTOR = Decimal("0.995")
# Wide enough for a live reserve/quote race, but narrow enough to distinguish
# a 28-bps trade-fee effect from the no-fee curve hypothesis.
ORACLE_NO_FEE_TOLERANCE_BPS = Decimal("10")


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
    if v0.get("mint") != pool["mint_0"] or v1.get("mint") != pool["mint_1"]:
        raise AssertionError("Pinned XDEX vault mint identity changed")
    r0 = int(v0["raw_amount"]) - pool["protocol_fees_0"] - pool["fund_fees_0"] - pool["creator_fees_0"]
    r1 = int(v1["raw_amount"]) - pool["protocol_fees_1"] - pool["fund_fees_1"] - pool["creator_fees_1"]
    if r0 <= 0 or r1 <= 0:
        raise AssertionError("Pinned XDEX active reserves must remain positive")
    return r0, r1


def _raw_amount(ui_amount, decimals):
    scaled = Decimal(str(ui_amount)) * (Decimal(10) ** decimals)
    if scaled != scaled.to_integral_value():
        raise AssertionError("Amount is not exactly representable in raw token units")
    return int(scaled)


def _curve_no_fee(raw_input, reserve_in, reserve_out):
    return raw_input * reserve_out // (reserve_in + raw_input)


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


def _ratio_bps_delta(value, reference):
    if not reference:
        return Decimal(0)
    return (Decimal(value) / Decimal(reference) - Decimal(1)) * BPS_DENOM


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1 to run read-only XDEX output/slippage evidence",
)
class XDEXOutputSlippageSemanticLiveTests(unittest.TestCase):
    def test_oracle_swap_quote_and_cp_curve_localize_output_adjustment(self):
        initial_pool = _pool_state()
        config = _config_state()
        self.assertEqual(initial_pool["amm_config"], AMM_CONFIG)
        self.assertEqual({initial_pool["mint_0"], initial_pool["mint_1"]}, {XENCAT, XNT})
        self.assertEqual(config["trade_fee_rate"], EXPECTED_TRADE_FEE_RATE)
        self.assertEqual(config["creator_fee_rate"], 0)

        rows = []
        for amount in (Decimal("1"), Decimal("2"), Decimal("1000"), Decimal("10000")):
            # Refresh pool fee accrual and vault balances immediately before each
            # quote comparison to minimize live-state drift.
            pool = _pool_state()
            self.assertEqual(pool["amm_config"], AMM_CONFIG)
            r0, r1 = _active_reserves(pool)
            by_mint = {
                pool["mint_0"]: (r0, pool["decimals_0"]),
                pool["mint_1"]: (r1, pool["decimals_1"]),
            }
            reserve_in, decimals_in = by_mint[XENCAT]
            reserve_out, decimals_out = by_mint[XNT]

            raw_input = _raw_amount(amount, decimals_in)
            no_fee_raw_output = _curve_no_fee(raw_input, reserve_in, reserve_out)
            fee_cp_raw_output, trade_fee_raw = _curve_exact_in(
                raw_input, reserve_in, reserve_out, config["trade_fee_rate"]
            )
            no_fee_ui_output = Decimal(no_fee_raw_output) / (Decimal(10) ** decimals_out)
            fee_cp_ui_output = Decimal(fee_cp_raw_output) / (Decimal(10) ** decimals_out)

            swap = fetch_swap_quote(XENCAT, XNT, amount, is_exact_amount_in=True)
            oracle = _oracle_sell_quote(amount)

            self.assertEqual(swap.get("inputMint"), XENCAT)
            self.assertEqual(swap.get("outputMint"), XNT)
            self.assertEqual(swap.get("amm_config_address"), AMM_CONFIG)
            self.assertEqual(oracle.get("selected_pool"), POOL)

            swap_output = Decimal(str(swap.get("outputAmount")))
            oracle_raw_output = int(str(oracle.get("amount_out_quote")))
            oracle_ui_output = Decimal(oracle_raw_output) / (Decimal(10) ** decimals_out)

            oracle_no_fee_delta_bps = _ratio_bps_delta(oracle_ui_output, no_fee_ui_output)
            oracle_fee_cp_delta_bps = _ratio_bps_delta(oracle_ui_output, fee_cp_ui_output)
            swap_fee_cp_delta_bps = _ratio_bps_delta(swap_output, fee_cp_ui_output)
            swap_oracle_delta_bps = _ratio_bps_delta(swap_output, oracle_ui_output)

            half_percent_min = fee_cp_ui_output * HALF_PERCENT_FACTOR
            residual_after_50bps = _ratio_bps_delta(swap_output, half_percent_min)

            rows.append({
                "amount_in_xencat": str(amount),
                "trade_fee_raw": trade_fee_raw,
                "protocol_fee_rate_raw": config["protocol_fee_rate"],
                "fund_fee_rate_raw": config["fund_fee_rate"],
                "creator_fee_rate_raw": config["creator_fee_rate"],
                "no_fee_cp_output_xnt": str(no_fee_ui_output),
                "fee_adjusted_cp_output_xnt": str(fee_cp_ui_output),
                "swap_output_xnt": str(swap_output),
                "oracle_output_xnt": str(oracle_ui_output),
                "oracle_vs_no_fee_cp_delta_bps": str(oracle_no_fee_delta_bps),
                "oracle_vs_fee_cp_delta_bps": str(oracle_fee_cp_delta_bps),
                "swap_vs_fee_cp_delta_bps": str(swap_fee_cp_delta_bps),
                "swap_vs_oracle_delta_bps": str(swap_oracle_delta_bps),
                "residual_after_exact_50bps_haircut_bps": str(residual_after_50bps),
                "oracle_usd_out": oracle.get("usd_out"),
                "oracle_effective_price": oracle.get("effective_price"),
                "oracle_pool_depth_usd": oracle.get("best_pool_usd_depth") or oracle.get("pool_depth_usd"),
            })

        print("XDEX output/slippage localization evidence")
        for row in rows:
            print(row)

        # Field-level evidence only. The Oracle output must stay close to the
        # independently reconstructed no-fee curve across all tested sizes.
        # This localizes the Oracle quote relative to the AMM trade fee without
        # claiming that its output is executable or fee-complete.
        self.assertTrue(rows)
        for row in rows:
            self.assertLessEqual(
                abs(Decimal(row["oracle_vs_no_fee_cp_delta_bps"])),
                ORACLE_NO_FEE_TOLERANCE_BPS,
                f"Oracle amount_out_quote no longer tracks the independently reconstructed no-fee curve: {row}",
            )
            # Preserve the unresolved swap-layer adjustment as a visible fact.
            self.assertLess(
                Decimal(row["swap_vs_fee_cp_delta_bps"]),
                Decimal("-40"),
                f"Previously observed post-trade-fee XDEX output adjustment disappeared: {row}",
            )


if __name__ == "__main__":
    unittest.main()
