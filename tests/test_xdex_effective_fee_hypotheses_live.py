import os
import unittest
from decimal import Decimal

from tests.test_xdex_second_pool_effective_fee_live import (
    KNOWN_CONFIG,
    MAX_DIFFERENT_CONFIG_TOKEN_PROBES,
    OBSERVED_QUOTE_BASELINE_RATE,
    XNT,
    _active_reserves,
    _curve_exact_in,
    _decode_config,
    _decode_pool,
    _discover_pair_pools,
    _discover_xnt_pools,
    _quote,
    _raw_amount,
)


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
ADDITIVE_CANDIDATE_PPM = 200


def _evaluate_hypotheses(pool, config, quote, token_in, token_out, amount):
    r0, r1 = _active_reserves(pool)
    by_mint = {
        pool["mint_0"]: (r0, pool["decimals_0"]),
        pool["mint_1"]: (r1, pool["decimals_1"]),
    }
    reserve_in, decimals_in = by_mint[token_in]
    reserve_out, decimals_out = by_mint[token_out]
    raw_input = _raw_amount(amount, decimals_in)

    config_rate = int(config["trade_fee_rate"])
    additive_rate = config_rate + ADDITIVE_CANDIDATE_PPM
    floor_rate = max(config_rate, OBSERVED_QUOTE_BASELINE_RATE)

    cp_config = _curve_exact_in(raw_input, reserve_in, reserve_out, config_rate)
    cp_additive = _curve_exact_in(raw_input, reserve_in, reserve_out, additive_rate)
    cp_floor = _curve_exact_in(raw_input, reserve_in, reserve_out, floor_rate)

    observed_decimal = Decimal(str(quote["outputAmount"])) * (Decimal(10) ** decimals_out)
    if observed_decimal != observed_decimal.to_integral_value():
        raise AssertionError(f"Quote output is not raw-unit exact: {quote}")
    observed = int(observed_decimal)

    return {
        "pool": pool["pool"],
        "amm_config": pool["amm_config"],
        "direction": f"{token_in[:6]}->{token_out[:6]}",
        "amount": str(amount),
        "config_rate_ppm": config_rate,
        "candidate_additive_rate_ppm": additive_rate,
        "candidate_floor_rate_ppm": floor_rate,
        "observed_raw": observed,
        "cp_config_raw": cp_config,
        "cp_additive_raw": cp_additive,
        "cp_floor_raw": cp_floor,
        "delta_additive_raw": observed - cp_additive,
        "delta_floor_raw": observed - cp_floor,
        "candidate_padding_creator_fee_rate_raw": int(config.get("creator_fee_rate") or 0),
    }


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1 for XDEX effective-fee hypothesis evidence",
)
class XDEXEffectiveFeeHypothesisLiveTests(unittest.TestCase):
    def test_universal_plus_200_ppm_is_falsified_by_3000_ppm_config(self):
        # A 2800-ppm config cannot distinguish +200 from a 3000-ppm floor because
        # both candidates equal 3000. First establish that baseline on XNT/USDC.X.
        pair_pools = _discover_pair_pools()
        self.assertTrue(pair_pools, "No live XNT/USDC.X pools discovered")
        baseline_quote = _quote(XNT, pair_pools[0]["mint_1"] if pair_pools[0]["mint_0"] == XNT else pair_pools[0]["mint_0"], Decimal("0.1"))
        self.assertIsNotNone(baseline_quote, "No live quote for baseline 2800-ppm route")

        baseline_selected = str(baseline_quote.get("amm_config_address") or "")
        baseline_rows = []
        for candidate in pair_pools:
            if candidate["amm_config"] != baseline_selected:
                continue
            pool = _decode_pool(candidate["pool"])
            other_mint = pool["mint_1"] if pool["mint_0"] == XNT else pool["mint_0"]
            if other_mint not in {baseline_quote.get("inputMint"), baseline_quote.get("outputMint")}:
                continue
            config = _decode_config(pool["amm_config"])
            baseline_rows.append(
                _evaluate_hypotheses(pool, config, baseline_quote, XNT, other_mint, Decimal("0.1"))
            )

        self.assertTrue(baseline_rows, "No structurally matched baseline route")
        self.assertTrue(any(row["config_rate_ppm"] == 2800 for row in baseline_rows), baseline_rows)

        # Now find a live route whose selected config is already 3000 ppm. Under
        # a universal +200-ppm model it should quote like 3200 ppm. Under a
        # 3000-ppm minimum/floor model it should remain at 3000 ppm.
        xnt_pools = _discover_xnt_pools()
        by_other_mint = {}
        for candidate in xnt_pools:
            if candidate["amm_config"] == KNOWN_CONFIG:
                continue
            other = candidate["mint_1"] if candidate["mint_0"] == XNT else candidate["mint_0"]
            by_other_mint.setdefault(other, []).append(candidate)

        tested_3000 = []
        diagnostics = []
        for other_mint, candidates in list(by_other_mint.items())[:MAX_DIFFERENT_CONFIG_TOKEN_PROBES]:
            quote = _quote(XNT, other_mint, Decimal("0.01"))
            if not quote:
                diagnostics.append({"other_mint": other_mint, "quote": "unavailable"})
                continue
            selected = str(quote.get("amm_config_address") or "")
            for candidate in candidates:
                if candidate["amm_config"] != selected:
                    continue
                pool = _decode_pool(candidate["pool"])
                config = _decode_config(selected)
                if int(config["trade_fee_rate"]) != OBSERVED_QUOTE_BASELINE_RATE:
                    continue
                row = _evaluate_hypotheses(pool, config, quote, XNT, other_mint, Decimal("0.01"))
                tested_3000.append(row)
                if abs(row["delta_floor_raw"]) <= 1:
                    break
            if any(abs(row["delta_floor_raw"]) <= 1 for row in tested_3000):
                break

        print("XDEX effective-fee hypothesis evidence")
        print({"baseline_2800_rows": baseline_rows})
        print({"tested_3000_rows": tested_3000})
        print({"diagnostics": diagnostics})
        print(
            "Interpretation boundary: a universal config+200-ppm fee model is falsified "
            "if a route already configured at 3000 ppm matches 3000 rather than 3200. "
            "A max(config, 3000) model is only a best-fitting candidate over the currently "
            "observed 2800/3000 config set; it is not promoted as an authoritative XDEX formula."
        )

        self.assertTrue(tested_3000, "No live 3000-ppm selected-config route was tested")
        matching_floor = [row for row in tested_3000 if abs(row["delta_floor_raw"]) <= 1]
        self.assertTrue(matching_floor, tested_3000)
        for row in matching_floor:
            self.assertNotEqual(
                row["cp_additive_raw"],
                row["observed_raw"],
                f"Unexpectedly observed a universal +200-ppm result on a 3000-ppm config: {row}",
            )
            self.assertEqual(row["candidate_padding_creator_fee_rate_raw"], 0, row)


if __name__ == "__main__":
    unittest.main()
