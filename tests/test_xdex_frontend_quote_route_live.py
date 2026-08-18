import os
import unittest
from decimal import Decimal

import requests


RUN_LIVE = os.getenv("RUN_XDEX_OUTPUT_SLIPPAGE_LIVE") == "1"
BASE = "https://api.xdex.xyz"
FRONTEND_ROUTE = "/api/xdex/swap/quote"
RESEARCH_ROUTE = "/api/xendex/swap/quote"
NETWORK = "X1 Mainnet"
XENCAT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
XNT = "So11111111111111111111111111111111111111112"
CONFIG = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"


def fetch_quote(route, token_in, token_out, amount, slippage, include_config):
    params = {
        "network": NETWORK,
        "token_in": token_in,
        "token_out": token_out,
        "token_in_amount": str(amount),
        "is_exact_amount_in": "true",
        "slippage": str(slippage),
    }
    if include_config:
        params["amm_config_address"] = CONFIG
    response = requests.get(
        BASE + route,
        params=params,
        timeout=30,
        headers={"User-Agent": "LiquidityScout-XDEX-readonly-evidence/1.0"},
    )
    body = None
    try:
        body = response.json()
    except Exception:
        body = {"raw_text": response.text[:500]}
    return response, body


def data_from(body):
    if not isinstance(body, dict):
        return None
    data = body.get("data")
    return data if isinstance(data, dict) else None


@unittest.skipUnless(RUN_LIVE, "set RUN_XDEX_OUTPUT_SLIPPAGE_LIVE=1")
class XDEXFrontendQuoteRouteLiveTests(unittest.TestCase):
    def test_frontend_and_research_quote_routes_match(self):
        cases = (
            (XENCAT, XNT, "1000", "XENCAT->XNT"),
            (XNT, XENCAT, "0.1", "XNT->XENCAT"),
        )
        observations = []

        for token_in, token_out, amount, label in cases:
            for slippage in ("0", "0.5"):
                for include_config in (False, True):
                    row = {
                        "direction": label,
                        "amount": amount,
                        "slippage": slippage,
                        "include_config": include_config,
                    }
                    route_results = {}
                    for route in (FRONTEND_ROUTE, RESEARCH_ROUTE):
                        response, body = fetch_quote(
                            route,
                            token_in,
                            token_out,
                            amount,
                            slippage,
                            include_config,
                        )
                        data = data_from(body)
                        route_results[route] = {
                            "status": response.status_code,
                            "url": response.url,
                            "success": body.get("success") if isinstance(body, dict) else None,
                            "message": body.get("message") if isinstance(body, dict) else None,
                            "outputAmount": data.get("outputAmount") if data else None,
                            "rate": data.get("rate") if data else None,
                            "priceImpactPct": data.get("priceImpactPct") if data else None,
                            "amm_config_address": data.get("amm_config_address") if data else None,
                        }
                    row["routes"] = route_results
                    observations.append(row)

        print("XDEX deployed frontend-route vs research-route quote evidence")
        for row in observations:
            print(row)

        comparable = 0
        for row in observations:
            a = row["routes"][FRONTEND_ROUTE]
            b = row["routes"][RESEARCH_ROUTE]
            if a["status"] == 200 and b["status"] == 200 and a["outputAmount"] is not None and b["outputAmount"] is not None:
                comparable += 1
                self.assertEqual(
                    Decimal(str(a["outputAmount"])),
                    Decimal(str(b["outputAmount"])),
                    row,
                )
                self.assertEqual(a["amm_config_address"], b["amm_config_address"], row)
                if a["priceImpactPct"] is not None and b["priceImpactPct"] is not None:
                    self.assertEqual(
                        Decimal(str(a["priceImpactPct"])),
                        Decimal(str(b["priceImpactPct"])),
                        row,
                    )

        print(
            {
                "comparable_route_pairs": comparable,
                "interpretation": (
                    "If both aliases match, the deployed frontend route and the research route "
                    "expose the same quote semantics for the tested cases. This localizes the "
                    "effective 3000-ppm behavior to the backend quote service rather than a "
                    "browser-side output adjustment."
                ),
            }
        )
        self.assertGreater(comparable, 0, "No successful route-alias pair could be compared")


if __name__ == "__main__":
    unittest.main()
