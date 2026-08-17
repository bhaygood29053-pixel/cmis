import unittest

from liquidity_scout.providers.solana.helius import (
    HeliusDASProvider,
    HeliusSourceError,
)


MINT = "Mint111"


class _Response:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class HeliusReviewRegressionTests(unittest.TestCase):
    def test_transport_failure_drops_secret_bearing_exception_context(self):
        secret_key = "secret-key"
        secret_url = "https://api.example.invalid/private"

        def failing_post(*args, **kwargs):
            raise RuntimeError(f"failed {secret_url} with {secret_key}")

        provider = HeliusDASProvider(
            base_url=secret_url,
            api_key=secret_key,
            post=failing_post,
        )

        with self.assertRaises(HeliusSourceError) as caught:
            provider.get_asset(MINT)

        message = str(caught.exception)
        self.assertIn("RuntimeError", message)
        self.assertNotIn(secret_key, message)
        self.assertNotIn(secret_url, message)
        self.assertIsNone(caught.exception.__cause__)
        self.assertIsNone(caught.exception.__context__)

    def test_token_info_symbol_fills_partial_metadata_symbol_gap(self):
        body = {
            "result": {
                "id": MINT,
                "last_indexed_slot": 123,
                "token_info": {
                    "supply": 1000000,
                    "decimals": 6,
                    "token_program": "spl-token",
                    "mint_authority": None,
                    "freeze_authority": None,
                    "symbol": "TOK",
                },
                "content": {"metadata": {"name": "Token without metadata symbol"}},
            }
        }

        def post(*args, **kwargs):
            return _Response(body)

        provider = HeliusDASProvider(api_key="test-key", post=post)
        result = provider.get_asset(MINT)

        self.assertEqual(result["name"], "Token without metadata symbol")
        self.assertEqual(result["symbol"], "TOK")


if __name__ == "__main__":
    unittest.main()
