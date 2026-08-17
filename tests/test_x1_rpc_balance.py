import unittest

from liquidity_scout.providers.x1.rpc_balance import (
    RPC_METHOD,
    X1RPCBalanceError,
    fetch_token_account_balance_raw,
)


class _Response:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class _Session:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def post(self, url, *, json, timeout):
        self.calls.append((url, json, timeout))
        return _Response(self.body)


class X1RPCBalanceTests(unittest.TestCase):
    def _body(self):
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 123456},
                "value": {
                    "amount": "42000000",
                    "decimals": 6,
                    "uiAmount": 42.0,
                    "uiAmountString": "42",
                },
            },
        }

    def test_fetches_raw_balance_and_stays_non_promotable(self):
        session = _Session(self._body())
        result = fetch_token_account_balance_raw(
            "Vault111",
            rpc_url="https://rpc.example",
            session=session,
        )

        self.assertEqual(result["method"], RPC_METHOD)
        self.assertEqual(result["account"], "Vault111")
        self.assertEqual(result["slot"], 123456)
        self.assertEqual(result["amount"], "42000000")
        self.assertEqual(result["decimals"], 6)
        self.assertFalse(result["identity_verified"])
        self.assertFalse(result["reserve_semantics_verified"])
        self.assertFalse(result["cmis_promotable"])

        url, payload, timeout = session.calls[0]
        self.assertEqual(url, "https://rpc.example")
        self.assertEqual(timeout, 20)
        self.assertEqual(payload["method"], RPC_METHOD)
        self.assertEqual(payload["params"], ["Vault111", {"commitment": "confirmed"}])

    def test_rpc_error_fails_closed_without_echoing_provider_details(self):
        session = _Session({"jsonrpc": "2.0", "id": 1, "error": {"message": "secret-ish"}})
        with self.assertRaisesRegex(X1RPCBalanceError, "returned an error"):
            fetch_token_account_balance_raw(
                "Vault111",
                rpc_url="https://rpc.example",
                session=session,
            )

    def test_missing_result_fails_closed(self):
        with self.assertRaisesRegex(X1RPCBalanceError, "result is missing"):
            fetch_token_account_balance_raw(
                "Vault111",
                rpc_url="https://rpc.example",
                session=_Session({"jsonrpc": "2.0", "id": 1}),
            )

    def test_invalid_raw_amount_fails_closed(self):
        body = self._body()
        body["result"]["value"]["amount"] = 42.0
        with self.assertRaisesRegex(X1RPCBalanceError, "raw amount is invalid"):
            fetch_token_account_balance_raw(
                "Vault111",
                rpc_url="https://rpc.example",
                session=_Session(body),
            )

    def test_invalid_slot_fails_closed(self):
        body = self._body()
        body["result"]["context"]["slot"] = True
        with self.assertRaisesRegex(X1RPCBalanceError, "slot is invalid"):
            fetch_token_account_balance_raw(
                "Vault111",
                rpc_url="https://rpc.example",
                session=_Session(body),
            )

    def test_empty_account_is_rejected_before_transport(self):
        with self.assertRaisesRegex(ValueError, "account must not be empty"):
            fetch_token_account_balance_raw(
                " ",
                rpc_url="https://rpc.example",
                session=_Session(self._body()),
            )


if __name__ == "__main__":
    unittest.main()
