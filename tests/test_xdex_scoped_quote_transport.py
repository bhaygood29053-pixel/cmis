import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.xdex import (
    SWAP_QUOTE_URL,
    fetch_swap_quote,
)


class _Response:
    status_code = 200
    text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "success": True,
            "data": {
                "inputMint": "mint-in",
                "outputMint": "mint-out",
                "amm_config_address": "config-1",
                "priceImpactPct": "0.1",
            },
        }


class _Session:
    def __init__(self):
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append({"url": url, "params": dict(params), "timeout": timeout})
        return _Response()


class XDEXScopedQuoteTransportTests(unittest.TestCase):
    def test_zero_slippage_and_exact_config_are_sent_on_read_only_get(self):
        session = _Session()
        result = fetch_swap_quote(
            "mint-in",
            "mint-out",
            "1.25",
            slippage=Decimal("0"),
            amm_config_address="config-1",
            session=session,
            timeout=7,
        )

        self.assertEqual(result["amm_config_address"], "config-1")
        self.assertEqual(len(session.calls), 1)
        call = session.calls[0]
        self.assertEqual(call["url"], SWAP_QUOTE_URL)
        self.assertEqual(call["timeout"], 7)
        self.assertEqual(
            call["params"],
            {
                "network": "X1 Mainnet",
                "token_in": "mint-in",
                "token_out": "mint-out",
                "token_in_amount": "1.25",
                "is_exact_amount_in": "true",
                "slippage": "0",
                "amm_config_address": "config-1",
            },
        )

    def test_existing_unscoped_call_shape_remains_compatible(self):
        session = _Session()
        fetch_swap_quote(
            "mint-in",
            "mint-out",
            2,
            session=session,
        )
        params = session.calls[0]["params"]
        self.assertNotIn("slippage", params)
        self.assertNotIn("amm_config_address", params)
        self.assertEqual(params["token_in_amount"], "2")

    def test_negative_slippage_is_rejected_before_transport(self):
        session = _Session()
        with self.assertRaisesRegex(ValueError, "slippage"):
            fetch_swap_quote(
                "mint-in",
                "mint-out",
                1,
                slippage="-0.1",
                session=session,
            )
        self.assertEqual(session.calls, [])


if __name__ == "__main__":
    unittest.main()
