import os
import unittest
from decimal import Decimal

import requests


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
SWAP_QUOTE_URL = "https://api.xdex.xyz/api/xendex/swap/quote"
XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT = "So11111111111111111111111111111111111111112"
XNT_DECIMALS = 9
RAW_SCALE = 10**XNT_DECIMALS
BASE_PARAMS = {
    "network": "X1 Mainnet",
    "token_in": XENCAT,
    "token_out": XNT,
    "token_in_amount": "1000",
    "is_exact_amount_in": "true",
}


def _request(extra=None):
    params = dict(BASE_PARAMS)
    if extra:
        params.update(extra)
    response = requests.get(SWAP_QUOTE_URL, params=params, timeout=20)
    result = {
        "request_extra": dict(extra or {}),
        "status_code": response.status_code,
        "url": response.url,
    }
    try:
        body = response.json()
    except Exception:
        result["response_text"] = response.text[:500]
        return result

    result["body_success"] = body.get("success") if isinstance(body, dict) else None
    data = body.get("data") if isinstance(body, dict) else None
    if isinstance(data, dict):
        result["data"] = dict(data)
        result["outputAmount"] = data.get("outputAmount")
        result["priceImpactPct"] = data.get("priceImpactPct")
        result["amm_config_address"] = data.get("amm_config_address")
    else:
        result["error"] = body.get("error") if isinstance(body, dict) else body
    return result


def _raw_output(row):
    amount = Decimal(str(row["outputAmount"])) * RAW_SCALE
    if amount != amount.to_integral_value():
        raise AssertionError(f"XDEX outputAmount is not aligned to XNT raw units: {row}")
    return int(amount)


def _expected_raw_after_slippage(zero_slippage_raw, slippage_percent):
    # The tested values are exact whole basis points: 0.01% = 1 bp.
    bps = int(Decimal(str(slippage_percent)) * 100)
    return zero_slippage_raw * (10_000 - bps) // 10_000


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1 to probe read-only XDEX quote parameters",
)
class XDEXQuoteSlippageParameterLiveTests(unittest.TestCase):
    def test_slippage_parameter_is_percent_and_default_is_half_percent(self):
        # Query zero first so every other result can be compared to the service's
        # own no-slippage output rather than to our AMM reconstruction.
        zero = _request({"slippage": "0"})
        self.assertEqual(zero["status_code"], 200, zero)
        self.assertTrue(zero.get("body_success"), zero)
        zero_raw = _raw_output(zero)

        explicit = {}
        for value in ("0.01", "0.1", "0.5", "1.0"):
            row = _request({"slippage": value})
            self.assertEqual(row["status_code"], 200, row)
            self.assertTrue(row.get("body_success"), row)
            explicit[value] = row

        baseline = _request()
        self.assertEqual(baseline["status_code"], 200, baseline)
        self.assertTrue(baseline.get("body_success"), baseline)

        print("XDEX quote slippage semantic baseline/no-slippage")
        print({"zero": zero, "baseline": baseline})
        print("XDEX quote explicit slippage values")
        for value, row in explicit.items():
            print({"slippage_percent": value, "result": row})

        # For whole-basis-point values, XDEX applies the supplied number as a
        # percentage to the slippage=0 quote and floors to output raw units.
        for value, row in explicit.items():
            observed_raw = _raw_output(row)
            expected_raw = _expected_raw_after_slippage(zero_raw, value)
            self.assertLessEqual(
                abs(observed_raw - expected_raw),
                1,
                f"slippage={value} no longer follows percent/bps minimum-output semantics",
            )

        # Omitting slippage is equivalent to explicitly supplying 0.5% on the
        # same live quote contract (allow one raw unit for response serialization).
        self.assertLessEqual(
            abs(_raw_output(baseline) - _raw_output(explicit["0.5"])),
            1,
            "XDEX quote default is no longer equivalent to explicit slippage=0.5",
        )

        # The price-impact field is independent of the slippage tolerance in
        # this controlled request set; slippage changes minimum output only.
        impact_values = {
            str(zero.get("priceImpactPct")),
            str(baseline.get("priceImpactPct")),
            *(str(row.get("priceImpactPct")) for row in explicit.values()),
        }
        self.assertEqual(len(impact_values), 1, impact_values)

    def test_alternate_slippage_parameter_names_do_not_show_a_quote_effect(self):
        baseline = _request()
        self.assertEqual(baseline["status_code"], 200, baseline)
        self.assertTrue(baseline.get("body_success"), baseline)
        baseline_output = Decimal(str(baseline["outputAmount"]))

        candidates = [
            {"slippage_bps": "0"},
            {"slippage_bps": "50"},
            {"slippageBps": "50"},
            {"slippage_tolerance": "0.5"},
            {"slippageTolerance": "0.5"},
        ]
        rows = [_request(extra) for extra in candidates]

        print("XDEX alternate slippage-parameter probe")
        for row in rows:
            print(row)

        for row in rows:
            self.assertEqual(row["status_code"], 200, row)
            self.assertTrue(row.get("body_success"), row)
            self.assertEqual(Decimal(str(row["outputAmount"])), baseline_output, row)


if __name__ == "__main__":
    unittest.main()
