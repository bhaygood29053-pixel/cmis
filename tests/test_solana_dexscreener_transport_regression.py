import unittest

from liquidity_scout.providers.solana.dexscreener import (
    DexScreenerSolanaProvider,
    DexScreenerSourceError,
)


class DexScreenerTransportRegressionTests(unittest.TestCase):
    def test_transport_failure_drops_provider_exception_context(self):
        sensitive_url = "https://api.example.invalid/private"

        def failing_get(*args, **kwargs):
            raise RuntimeError(f"failed request to {sensitive_url}")

        provider = DexScreenerSolanaProvider(
            base_url=sensitive_url,
            get=failing_get,
        )

        with self.assertRaises(DexScreenerSourceError) as caught:
            provider.get_token_pairs("Mint111")

        message = str(caught.exception)
        self.assertIn("RuntimeError", message)
        self.assertNotIn(sensitive_url, message)
        self.assertIsNone(caught.exception.__cause__)
        self.assertIsNone(caught.exception.__context__)


if __name__ == "__main__":
    unittest.main()
