import math
import os
import struct
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.pool_state_fingerprint import fetch_account_state
from liquidity_scout.providers.x1.rpc import get_token_account_info
from liquidity_scout.providers.x1.xdex import fetch_swap_quote


RUN_LIVE = os.getenv("RUN_XDEX_PRICE_IMPACT_LIVE") == "1"
PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
AMM_CONFIG = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"
XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT = "So11111111111111111111111111111111111111112"
FEE_DENOM = 1_000_000
EXPECTED_TRADE_FEE_RATE = 2_800
IMPACT_TOLERANCE_PERCENTAGE_POINTS = Decimal("0.002")


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
        raise AssertionError("Pinned XENCAT/XNT pool no longer matches the verified XDEX 637-byte program state")
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
    if state.get("owner") != PROGRAM or len(data) < 108:
        raise AssertionError("Pinned AMM config no longer matches the verified XDEX program state")
    return {
        "trade_fee_rate": _u64(data, 12),
        "protocol_fee_rate": _u64(data, 20),
        "fund_fee_rate": _u64(data, 28),
        "creator_fee_rate": _u64(data, 108) if len(data) >= 116 else 0,
    }


def _active_reserves(pool):
    v0 = get_token_account_info(pool["vault_0"])
    v1 = get_token_account_info(pool["vault_1"])
    if not v0 or not v1 or not v0.get("identity_verified") or not v1.get("identity_verified"):
        raise AssertionError("Pinned XDEX vault identity could not be verified")
    if v0.get("mint") != pool["mint_0"] or v1.get("mint") != pool["mint_1"]:
        raise AssertionError("Pinned XDEX vault mint identity changed")

    r0 = (
        int(v0["raw_amount"])
        - pool["protocol_fees_0"]
        - pool["fund_fees_0"]
        - pool["creator_fees_0"]
    )
    r1 = (
        int(v1["raw_amount"])
        - pool["protocol_fees_1"]
        - pool["fund_fees_1"]
        - pool["creator_fees_1"]
    )
    if r0 <= 0 or r1 <= 0:
        raise AssertionError("Pinned XDEX active reserves must remain positive")
    return r0, r1


def _raw_amount(ui_amount, decimals):
    scaled = Decimal(str(ui_amount)) * (Decimal(10) ** decimals)
    if scaled != scaled.to_integral_value():
        raise AssertionError("Test amount is not exactly representable in raw token units")
    return int(scaled)


def _curve_exact_in(raw_input, reserve_in, reserve_out, trade_fee_rate):
    trade_fee = _ceil_fee(raw_input, trade_fee_rate)
    less_fees = raw_input - trade_fee
    output = less_fees * reserve_out // (reserve_in + less_fees)
    impact_pct = Decimal(less_fees) / Decimal(reserve_in + less_fees) * Decimal(100)
    return output, trade_fee, impact_pct


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_PRICE_IMPACT_LIVE=1 to run read-only XDEX price-impact semantic evidence",
)
class XDEXPriceImpactSemanticLiveTests(unittest.TestCase):
    def test_provider_price_impact_reproduces_verified_pool_curve(self):
        pool = _pool_state()
        config = _config_state()
        self.assertEqual(pool["amm_config"], AMM_CONFIG)
        self.assertEqual({pool["mint_0"], pool["mint_1"]}, {XNT, XENCAT})
        self.assertEqual(config["trade_fee_rate"], EXPECTED_TRADE_FEE_RATE)
        self.assertEqual(config["creator_fee_rate"], 0)

        r0, r1 = _active_reserves(pool)
        by_mint = {
            pool["mint_0"]: (r0, pool["decimals_0"]),
            pool["mint_1"]: (r1, pool["decimals_1"]),
        }

        cases = [
            (XNT, XENCAT, Decimal("0.25")),
            (XNT, XENCAT, Decimal("0.5")),
            (XNT, XENCAT, Decimal("1")),
            (XNT, XENCAT, Decimal("2")),
            (XENCAT, XNT, Decimal("1")),
            (XENCAT, XNT, Decimal("2")),
            (XENCAT, XNT, Decimal("1000")),
            (XENCAT, XNT, Decimal("10000")),
        ]

        evidence = []
        output_mismatch_observed = False
        for token_in, token_out, amount in cases:
            reserve_in, decimals_in = by_mint[token_in]
            reserve_out, decimals_out = by_mint[token_out]
            raw_input = _raw_amount(amount, decimals_in)
            expected_raw, trade_fee_raw, computed_impact = _curve_exact_in(
                raw_input,
                reserve_in,
                reserve_out,
                config["trade_fee_rate"],
            )

            quote = fetch_swap_quote(
                token_in,
                token_out,
                amount,
                is_exact_amount_in=True,
            )
            self.assertEqual(quote.get("inputMint"), token_in)
            self.assertEqual(quote.get("outputMint"), token_out)
            self.assertEqual(quote.get("amm_config_address"), AMM_CONFIG)

            provider_impact = Decimal(str(quote.get("priceImpactPct")))
            delta = abs(provider_impact - computed_impact)
            self.assertLessEqual(
                delta,
                IMPACT_TOLERANCE_PERCENTAGE_POINTS,
                f"priceImpactPct diverged from independently reproduced CP curve for {token_in}->{token_out} amount={amount}",
            )

            quoted_output = Decimal(str(quote.get("outputAmount")))
            reproduced_output = Decimal(expected_raw) / (Decimal(10) ** decimals_out)
            raw_output_delta = int(
                (quoted_output - reproduced_output) * (Decimal(10) ** decimals_out)
            )
            if abs(raw_output_delta) > 2:
                output_mismatch_observed = True

            evidence.append(
                {
                    "token_in": token_in,
                    "token_out": token_out,
                    "amount": str(amount),
                    "trade_fee_raw": trade_fee_raw,
                    "computed_price_impact_pct": str(computed_impact),
                    "provider_price_impact_pct": str(provider_impact),
                    "impact_delta_percentage_points": str(delta),
                    "quoted_output": str(quoted_output),
                    "reproduced_curve_output": str(reproduced_output),
                    "raw_output_delta": raw_output_delta,
                }
            )

        print("XDEX price-impact semantic evidence")
        for row in evidence:
            print(row)

        # This is a deliberate safety assertion: price-impact semantics can be
        # independently reproduced while outputAmount decomposition remains
        # unresolved. A future exact output match should require a fresh review.
        self.assertTrue(
            output_mismatch_observed,
            "The previously unresolved XDEX output adjustment disappeared; re-review outputAmount semantics before changing CMIS gates.",
        )


if __name__ == "__main__":
    unittest.main()
