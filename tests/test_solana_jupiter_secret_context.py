import unittest

from liquidity_scout.providers.solana.jupiter import (
    JupiterSourceError,
    JupiterSourceProvider,
)


class JupiterSecretContextRegressionTests(unittest.TestCase):
    def test_transport_failure_drops_secret_bearing_exception_context(self):
        secret_key = "secret-key"
        secret_url = "https://api.example.invalid/private"

        def failing_get(*args, **kwargs):
            raise RuntimeError(f"failed {secret_url} with {secret_key}")

        provider = JupiterSourceProvider(
            base_url=secret_url,
            api_key=secret_key,
            get=failing_get,
        )

        with self.assertRaises(JupiterSourceError) as caught:
            provider.get_price("Mint111")

        message = str(caught.exception)
        self.assertIn("RuntimeError", message)
        self.assertNotIn(secret_key, message)
        self.assertNotIn(secret_url, message)
        self.assertIsNone(caught.exception.__cause__)
        self.assertIsNone(caught.exception.__context__)


if __name__ == "__main__":
    unittest.main()
