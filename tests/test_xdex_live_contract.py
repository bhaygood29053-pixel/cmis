import os
import unittest

from liquidity_scout.providers.x1 import XDEXReadOnlyProvider


RUN_LIVE = os.getenv("RUN_XDEX_LIVE_TESTS") == "1"
AGI_MINT = os.getenv(
    "XDEX_LIVE_TOKEN",
    "7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER",
)
QUOTE_TOKEN_IN = os.getenv(
    "XDEX_LIVE_QUOTE_TOKEN_IN",
    "So11111111111111111111111111111111111111112",
)
QUOTE_TOKEN_OUT = os.getenv(
    "XDEX_LIVE_QUOTE_TOKEN_OUT",
    "AvNDf423kEmWNP6AZHFV7DkNG4YRgt6qbdyyryjaa4PQ",
)


@unittest.skipUnless(
    RUN_LIVE,
    "Set RUN_XDEX_LIVE_TESTS=1 to probe the live read-only XDEX contract.",
)
class XDEXLiveContractTests(unittest.TestCase):
    def setUp(self):
        self.provider = XDEXReadOnlyProvider(timeout=20)

    def test_live_token_price_returns_mapping(self):
        data = self.provider.token_price(AGI_MINT)

        self.assertIsInstance(data, dict)
        self.assertTrue(data)

    def test_live_history_exposes_candidate_timestamp_and_price_fields(self):
        points = self.provider.price_history(AGI_MINT, days=7)

        self.assertIsInstance(points, list)
        self.assertTrue(
            points,
            "XDEX returned no history points; cannot verify history field semantics.",
        )
        for point in points[:10]:
            self.assertTrue(
                "timestamp" in point or "time" in point,
                f"history point lacks timestamp/time: {point}",
            )
            self.assertIn(
                "price",
                point,
                f"history point lacks price: {point}",
            )

    def test_live_quote_exposes_candidate_read_only_fields(self):
        data = self.provider.swap_quote(
            QUOTE_TOKEN_IN,
            QUOTE_TOKEN_OUT,
            1,
            is_exact_amount_in=True,
        )

        self.assertIn("outputAmount", data)
        self.assertIn("rate", data)
        if "priceImpactPct" in data:
            self.assertIsNotNone(data["priceImpactPct"])


if __name__ == "__main__":
    unittest.main()
