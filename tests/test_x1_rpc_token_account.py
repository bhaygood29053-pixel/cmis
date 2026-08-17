import unittest

from liquidity_scout.providers.x1.rpc_token_account import (
    ENCODING,
    RPC_METHOD,
    X1RPCTokenAccountError,
    fetch_token_account_identity_raw,
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


class X1RPCTokenAccountTests(unittest.TestCase):
    def _body(self):
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 72254502},
                "value": {
                    "data": {
                        "parsed": {
                            "info": {
                                "mint": "Mint111",
                                "owner": "Authority111",
                                "state": "initialized",
                            },
                            "type": "account",
                        },
                        "program": "spl-token",
                    },
                    "owner": "TokenProgram111",
                },
            },
        }

    def test_fetches_parsed_identity_fields_and_stays_non_promotable(self):
        session = _Session(self._body())
        result = fetch_token_account_identity_raw(
            "Vault111",
            rpc_url="https://rpc.example",
            session=session,
        )

        self.assertEqual(result["method"], RPC_METHOD)
        self.assertEqual(result["encoding"], ENCODING)
        self.assertEqual(result["account"], "Vault111")
        self.assertEqual(result["slot"], 72254502)
        self.assertEqual(result["mint"], "Mint111")
        self.assertEqual(result["authority"], "Authority111")
        self.assertEqual(result["token_state"], "initialized")
        self.assertEqual(result["parsed_program"], "spl-token")
        self.assertEqual(result["parsed_type"], "account")
        self.assertEqual(result["account_program_owner"], "TokenProgram111")
        self.assertTrue(result["token_account_fields_parsed"])
        self.assertFalse(result["expected_identity_verified"])
        self.assertFalse(result["pool_vault_identity_verified"])
        self.assertFalse(result["cmis_promotable"])

        url, payload, timeout = session.calls[0]
        self.assertEqual(url, "https://rpc.example")
        self.assertEqual(timeout, 20)
        self.assertEqual(payload["method"], RPC_METHOD)
        self.assertEqual(
            payload["params"],
            [
                "Vault111",
                {"encoding": ENCODING, "commitment": "confirmed"},
            ],
        )

    def test_rpc_error_fails_closed_without_echoing_provider_details(self):
        session = _Session(
            {"jsonrpc": "2.0", "id": 1, "error": {"message": "secret-ish"}}
        )
        with self.assertRaisesRegex(X1RPCTokenAccountError, "returned an error"):
            fetch_token_account_identity_raw(
                "Vault111",
                rpc_url="https://rpc.example",
                session=session,
            )

    def test_missing_parsed_payload_fails_closed(self):
        body = self._body()
        del body["result"]["value"]["data"]["parsed"]
        with self.assertRaisesRegex(X1RPCTokenAccountError, "payload is missing"):
            fetch_token_account_identity_raw(
                "Vault111",
                rpc_url="https://rpc.example",
                session=_Session(body),
            )

    def test_missing_mint_fails_closed(self):
        body = self._body()
        body["result"]["value"]["data"]["parsed"]["info"]["mint"] = ""
        with self.assertRaisesRegex(X1RPCTokenAccountError, "mint is missing"):
            fetch_token_account_identity_raw(
                "Vault111",
                rpc_url="https://rpc.example",
                session=_Session(body),
            )

    def test_missing_authority_fails_closed(self):
        body = self._body()
        body["result"]["value"]["data"]["parsed"]["info"]["owner"] = None
        with self.assertRaisesRegex(X1RPCTokenAccountError, "authority is missing"):
            fetch_token_account_identity_raw(
                "Vault111",
                rpc_url="https://rpc.example",
                session=_Session(body),
            )

    def test_invalid_slot_fails_closed(self):
        body = self._body()
        body["result"]["context"]["slot"] = True
        with self.assertRaisesRegex(X1RPCTokenAccountError, "slot is invalid"):
            fetch_token_account_identity_raw(
                "Vault111",
                rpc_url="https://rpc.example",
                session=_Session(body),
            )

    def test_empty_account_is_rejected_before_transport(self):
        with self.assertRaisesRegex(ValueError, "account must not be empty"):
            fetch_token_account_identity_raw(
                " ",
                rpc_url="https://rpc.example",
                session=_Session(self._body()),
            )


if __name__ == "__main__":
    unittest.main()
