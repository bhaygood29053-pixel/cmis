import unittest

from liquidity_scout.providers.solana.rpc import (
    CANONICAL_TOKEN_LARGEST_ACCOUNT_LIMIT,
    SolanaRPCError,
    SolanaRPCProvider,
)


class _Response:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def _post_with(body):
    def post(*args, **kwargs):
        return _Response(body)

    return post


def _largest_body(amounts):
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "context": {"slot": 12345},
            "value": [
                {
                    "address": f"Account{index:03d}",
                    "amount": str(amount),
                    "decimals": 6,
                    "uiAmount": None,
                    "uiAmountString": str(amount),
                }
                for index, amount in enumerate(amounts)
            ],
        },
    }


class SolanaLargestAccountCardinalityTests(unittest.TestCase):
    def test_provider_extended_result_is_normalized_to_canonical_top_20(self):
        provider = SolanaRPCProvider(
            "https://rpc.example.invalid",
            post=_post_with(_largest_body(range(1000, 900, -1))),
        )

        result = provider.get_token_largest_accounts("Mint111")

        self.assertEqual(CANONICAL_TOKEN_LARGEST_ACCOUNT_LIMIT, 20)
        self.assertEqual(result["account_count_observed"], 20)
        self.assertEqual(result["provider_account_count_returned"], 100)
        self.assertEqual(result["canonical_account_limit"], 20)
        self.assertTrue(result["provider_extended_result_truncated"])
        self.assertEqual(len(result["accounts"]), 20)
        self.assertEqual(result["accounts"][0]["address"], "Account000")
        self.assertEqual(result["accounts"][-1]["address"], "Account019")
        self.assertEqual(result["counted_entity"], "token_accounts")
        self.assertEqual(result["coverage"], "largest_token_accounts_only")
        self.assertFalse(result["total_holder_count_verified"])
        self.assertIn("does not establish total holder", result["warning"])
        self.assertIn("normalized", result["warning"])

    def test_canonical_or_shorter_result_is_not_marked_truncated(self):
        provider = SolanaRPCProvider(
            "https://rpc.example.invalid",
            post=_post_with(_largest_body([100, 50, 25])),
        )

        result = provider.get_token_largest_accounts("Mint111")

        self.assertEqual(result["account_count_observed"], 3)
        self.assertEqual(result["provider_account_count_returned"], 3)
        self.assertFalse(result["provider_extended_result_truncated"])
        self.assertEqual(len(result["accounts"]), 3)

    def test_unsorted_provider_result_fails_closed(self):
        provider = SolanaRPCProvider(
            "https://rpc.example.invalid",
            post=_post_with(_largest_body([100, 101, 50])),
        )

        with self.assertRaisesRegex(SolanaRPCError, "non-increasing raw amount"):
            provider.get_token_largest_accounts("Mint111")


if __name__ == "__main__":
    unittest.main()
