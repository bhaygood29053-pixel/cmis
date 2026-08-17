import unittest

from liquidity_scout.providers.x1.rpc_token_supply import (
    RPC_METHOD,
    X1RPCTokenSupplyError,
    fetch_token_supply_raw,
)


class Response:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class Session:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def post(self, url, *, json, timeout):
        self.calls.append((url, json, timeout))
        return Response(self.body)


def success():
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "context": {"slot": 88},
            "value": {
                "amount": "42000000",
                "decimals": 6,
                "uiAmount": 42.0,
                "uiAmountString": "42",
            },
        },
    }


class X1RPCTokenSupplyTests(unittest.TestCase):
    def test_fetches_total_mint_supply_without_circulating_or_holder_promotion(self):
        session = Session(success())
        result = fetch_token_supply_raw(
            "mint1",
            rpc_url="https://rpc.example",
            session=session,
        )

        self.assertEqual(session.calls[0][1]["method"], RPC_METHOD)
        self.assertEqual(
            session.calls[0][1]["params"],
            ["mint1", {"commitment": "confirmed"}],
        )
        self.assertEqual(result["mint"], "mint1")
        self.assertEqual(result["slot"], 88)
        self.assertEqual(result["amount"], "42000000")
        self.assertEqual(result["decimals"], 6)
        self.assertTrue(result["mint_supply_observed"])
        self.assertFalse(result["circulating_supply_verified"])
        self.assertFalse(result["holder_semantics_verified"])
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_zero_supply_is_valid_observation(self):
        body = success()
        body["result"]["value"]["amount"] = "0"
        body["result"]["value"]["uiAmount"] = 0.0
        body["result"]["value"]["uiAmountString"] = "0"

        result = fetch_token_supply_raw(
            "mint1",
            rpc_url="https://rpc.example",
            session=Session(body),
        )
        self.assertEqual(result["amount"], "0")
        self.assertTrue(result["mint_supply_observed"])
        self.assertFalse(result["cmis_promotable"])

    def test_rpc_error_fails_closed_without_echoing_provider_details(self):
        with self.assertRaisesRegex(X1RPCTokenSupplyError, "returned an error"):
            fetch_token_supply_raw(
                "mint1",
                rpc_url="https://rpc.example",
                session=Session(
                    {"jsonrpc": "2.0", "id": 1, "error": {"message": "secret-ish"}}
                ),
            )

    def test_missing_result_fails_closed(self):
        with self.assertRaisesRegex(X1RPCTokenSupplyError, "result is missing"):
            fetch_token_supply_raw(
                "mint1",
                rpc_url="https://rpc.example",
                session=Session({"jsonrpc": "2.0", "id": 1}),
            )

    def test_invalid_slot_fails_closed(self):
        body = success()
        body["result"]["context"]["slot"] = True
        with self.assertRaisesRegex(X1RPCTokenSupplyError, "slot is invalid"):
            fetch_token_supply_raw(
                "mint1",
                rpc_url="https://rpc.example",
                session=Session(body),
            )

    def test_decimal_form_amount_fails_closed(self):
        body = success()
        body["result"]["value"]["amount"] = "42.0"
        with self.assertRaisesRegex(X1RPCTokenSupplyError, "raw amount is invalid"):
            fetch_token_supply_raw(
                "mint1",
                rpc_url="https://rpc.example",
                session=Session(body),
            )

    def test_invalid_decimals_fail_closed(self):
        body = success()
        body["result"]["value"]["decimals"] = -1
        with self.assertRaisesRegex(X1RPCTokenSupplyError, "decimals are invalid"):
            fetch_token_supply_raw(
                "mint1",
                rpc_url="https://rpc.example",
                session=Session(body),
            )

    def test_empty_mint_rejected_before_transport(self):
        with self.assertRaisesRegex(ValueError, "mint must not be empty"):
            fetch_token_supply_raw(
                " ",
                rpc_url="https://rpc.example",
                session=Session(success()),
            )


if __name__ == "__main__":
    unittest.main()
