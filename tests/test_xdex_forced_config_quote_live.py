import os
import time
import unittest

import requests


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
URL = "https://api.xdex.xyz/api/xdex/swap/quote"
XNT = "So11111111111111111111111111111111111111112"
USDC_X = "B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
CONFIG_2800 = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"
CONFIG_3000 = "ECVmujod2RNv98T4JrkNwTTVEiMGDMyGztTaTXsYFL4x"


def quote(token_in, token_out, amount, config):
    params = {
        "network": "X1 Mainnet",
        "token_in": token_in,
        "token_out": token_out,
        "token_in_amount": str(amount),
        "is_exact_amount_in": "true",
        "slippage": "0",
        "amm_config_address": config,
    }
    last = None
    for attempt in range(3):
        response = requests.get(
            URL,
            params=params,
            timeout=30,
            headers={"User-Agent": "LiquidityScout-XDEX-readonly-evidence/1.0"},
        )
        last = response
        if response.status_code != 429:
            break
        time.sleep(1.5 * (attempt + 1))
    try:
        body = last.json()
    except Exception:
        body = {"raw_text": last.text[:500]}
    data = body.get("data") if isinstance(body, dict) and isinstance(body.get("data"), dict) else None
    return {
        "status": last.status_code,
        "success": body.get("success") if isinstance(body, dict) else None,
        "message": body.get("message") if isinstance(body, dict) else None,
        "outputAmount": data.get("outputAmount") if data else None,
        "rate": data.get("rate") if data else None,
        "priceImpactPct": data.get("priceImpactPct") if data else None,
        "returned_amm_config_address": data.get("amm_config_address") if data else None,
    }


@unittest.skipUnless(RUN_LIVE, "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1")
class XDEXForcedConfigQuoteLiveTests(unittest.TestCase):
    def test_xnt_usdc_quote_honors_explicit_amm_config(self):
        cases = (
            (XNT, USDC_X, "0.1", "XNT->USDC.X"),
            (USDC_X, XNT, "1", "USDC.X->XNT"),
        )
        observations = []

        for token_in, token_out, amount, direction in cases:
            row = {"direction": direction, "amount": amount, "configs": {}}
            for config in (CONFIG_2800, CONFIG_3000):
                result = quote(token_in, token_out, amount, config)
                row["configs"][config] = result
                if result["status"] == 200 and result["outputAmount"] is not None:
                    self.assertEqual(result["returned_amm_config_address"], config, row)
            observations.append(row)

        print("XDEX forced-AMM-config quote evidence")
        for row in observations:
            print(row)

        successful = [
            (row, config, result)
            for row in observations
            for config, result in row["configs"].items()
            if result["status"] == 200 and result["outputAmount"] is not None
        ]
        self.assertGreaterEqual(len(successful), 2, "Too few forced-config quotes succeeded")

        both_config_cases = []
        for row in observations:
            a = row["configs"][CONFIG_2800]
            b = row["configs"][CONFIG_3000]
            if a["status"] == 200 and b["status"] == 200 and a["outputAmount"] is not None and b["outputAmount"] is not None:
                both_config_cases.append(row)
        self.assertTrue(both_config_cases, "No direction successfully quoted under both explicit configs")

        print(
            {
                "directions_with_both_configs": len(both_config_cases),
                "interpretation": (
                    "When the API returns the requested amm_config_address for both live configs, "
                    "the backend is demonstrably config-aware. Therefore a 2800-ppm pool quoting "
                    "on an effective 3000-ppm zero-slippage curve is not explained by the API simply "
                    "ignoring or being unable to identify the selected AMM config."
                ),
            }
        )


if __name__ == "__main__":
    unittest.main()
