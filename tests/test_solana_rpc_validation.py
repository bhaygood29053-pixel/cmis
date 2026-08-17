import unittest

from liquidity_scout.providers.solana.rpc import (
    SPL_TOKEN_PROGRAM_ID,
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


def _provider(body):
    def post(*args, **kwargs):
        return _Response(body)

    return SolanaRPCProvider("https://rpc.example.invalid", post=post)


def _supply_body(*, amount="1", decimals=6, slot=1):
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "context": {"slot": slot},
            "value": {
                "amount": amount,
                "decimals": decimals,
                "uiAmountString": "0.000001",
            },
        },
    }


class SolanaRPCValidationTests(unittest.TestCase):
    def test_numeric_amount_is_rejected_instead_of_string_coercion(self):
        provider = _provider(_supply_body(amount=1))

        with self.assertRaisesRegex(SolanaRPCError, "unsigned integer string"):
            provider.get_token_supply("Mint111")

    def test_float_decimals_are_rejected_instead_of_int_coercion(self):
        provider = _provider(_supply_body(decimals=6.0))

        with self.assertRaisesRegex(SolanaRPCError, "non-negative integer"):
            provider.get_token_supply("Mint111")

    def test_decimals_must_fit_u8(self):
        provider = _provider(_supply_body(decimals=256))

        with self.assertRaisesRegex(SolanaRPCError, "fit in u8"):
            provider.get_token_supply("Mint111")

    def test_float_context_slot_is_rejected(self):
        provider = _provider(_supply_body(slot=1.0))

        with self.assertRaisesRegex(SolanaRPCError, "context slot"):
            provider.get_token_supply("Mint111")

    def test_non_string_mint_input_is_rejected(self):
        provider = _provider(_supply_body())

        with self.assertRaisesRegex(SolanaRPCError, "mint must be a non-empty string"):
            provider.get_token_supply(12345)  # type: ignore[arg-type]

    def test_boolean_slot_is_rejected(self):
        provider = _provider(_supply_body(slot=True))

        with self.assertRaisesRegex(SolanaRPCError, "context slot"):
            provider.get_token_supply("Mint111")

    def test_non_object_json_rpc_result_is_rejected(self):
        provider = _provider({"jsonrpc": "2.0", "id": 1, "result": []})

        with self.assertRaisesRegex(SolanaRPCError, "malformed result"):
            provider.get_token_supply("Mint111")

    def test_parsed_non_mint_account_is_rejected(self):
        provider = _provider(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "context": {"slot": 1},
                    "value": {
                        "owner": SPL_TOKEN_PROGRAM_ID,
                        "data": {
                            "program": "spl-token",
                            "parsed": {
                                "type": "account",
                                "info": {},
                            },
                        },
                    },
                },
            }
        )

        with self.assertRaisesRegex(SolanaRPCError, "parsed mint data"):
            provider.get_mint_account("Mint111")


if __name__ == "__main__":
    unittest.main()
