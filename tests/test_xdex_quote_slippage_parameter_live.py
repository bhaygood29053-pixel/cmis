import os
import unittest
from decimal import Decimal

import requests


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
SWAP_QUOTE_URL = "https://api.xdex.xyz/api/xendex/swap/quote"
XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT = "So11111111111111111111111111111111111111112"
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
        result["outputAmount"] = data.get("outputAmount")
        result["priceImpactPct"] = data.get("priceImpactPct")
        result["amm_config_address"] = data.get("amm_config_address")
    else:
        result["error"] = body.get("error") if isinstance(body, dict) else body
    return result


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1 to probe read-only XDEX quote parameters",
)
class XDEXQuoteSlippageParameterLiveTests(unittest.TestCase):
    def test_common_slippage_parameter_names_are_observed_not_assumed(self):
        baseline = _request()
        self.assertEqual(baseline["status_code"], 200, baseline)
        self.assertTrue(baseline.get("body_success"), baseline)
        self.assertIsNotNone(baseline.get("outputAmount"), baseline)
        baseline_output = Decimal(str(baseline["outputAmount"]))

        candidates = [
            {"slippage": "0"},
            {"slippage": "0.005"},
            {"slippage": "0.5"},
            {"slippage_bps": "0"},
            {"slippage_bps": "50"},
            {"slippageBps": "50"},
            {"slippage_tolerance": "0.5"},
            {"slippageTolerance": "0.5"},
        ]

        rows = []
        effects = []
        for extra in candidates:
            row = _request(extra)
            rows.append(row)
            if row.get("status_code") == 200 and row.get("body_success") and row.get("outputAmount") is not None:
                output = Decimal(str(row["outputAmount"]))
                if output != baseline_output:
                    effects.append({
                        "request_extra": extra,
                        "baseline_output": str(baseline_output),
                        "observed_output": str(output),
                    })

        print("XDEX quote slippage-parameter probe baseline")
        print(baseline)
        print("XDEX quote slippage-parameter probe candidates")
        for row in rows:
            print(row)
        print("XDEX quote slippage-parameter observed effects")
        print(effects)

        # This test intentionally does not assert that undocumented parameters
        # must be rejected or ignored. Its role is to capture whether the live
        # service visibly reacts to common candidate names without invoking any
        # transaction-preparation endpoint.
        self.assertEqual(len(rows), len(candidates))


if __name__ == "__main__":
    unittest.main()
