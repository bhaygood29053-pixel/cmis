import unittest

from liquidity_scout.providers.x1.rpc_largest_token_accounts import (
    RPC_METHOD,
    X1RPCLargestTokenAccountsError,
    fetch_largest_token_accounts_raw,
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


def success(values=None):
    if values is None:
        values = [
            {
                "address": "acct1",
                "amount": "5000",
                "decimals": 6,
                "uiAmount": 0.005,
                "uiAmountString": "0.005",
            },
            {
                "address": "acct2",
                "amount": "4000",
                "decimals": 6,
                "uiAmount": 0.004,
                "uiAmountString": "0.004",
            },
        ]
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"context": {"slot": 77}, "value": values},
    }


class X1RPCLargestTokenAccountsTests(unittest.TestCase):
    def test_preserves_raw_top_accounts_without_holder_promotion(self):
        session = Session(success())
        result = fetch_largest_token_accounts_raw(
            "mint1", rpc_url="https://rpc.example", session=session
        )
        self.assertEqual(session.calls[0][1]["method"], RPC_METHOD)
        self.assertEqual(
            session.calls[0][1]["params"],
            ["mint1", {"commitment": "confirmed"}],
        )
        self.assertEqual(result["slot"], 77)
        self.assertEqual(result["account_count_observed"], 2)
        self.assertEqual(result["accounts"][0]["amount"], "5000")
        self.assertTrue(result["descending_amount_order_verified"])
        self.assertFalse(result["holder_semantics_verified"])
        self.assertFalse(result["holder_coverage_verified"])
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_empty_result_is_valid_but_not_holder_coverage(self):
        result = fetch_largest_token_accounts_raw(
            "mint1", rpc_url="https://rpc.example", session=Session(success([]))
        )
        self.assertEqual(result["accounts"], [])
        self.assertTrue(result["descending_amount_order_verified"])
        self.assertFalse(result["holder_coverage_verified"])

    def test_equal_amounts_preserve_valid_descending_order(self):
        values = [
            {"address": "acct1", "amount": "5", "decimals": 6},
            {"address": "acct2", "amount": "5", "decimals": 6},
            {"address": "acct3", "amount": "4", "decimals": 6},
        ]
        result = fetch_largest_token_accounts_raw(
            "mint1",
            rpc_url="https://rpc.example",
            session=Session(success(values)),
        )
        self.assertTrue(result["descending_amount_order_verified"])

    def test_unsorted_amounts_fail_closed(self):
        values = [
            {"address": "acct1", "amount": "5", "decimals": 6},
            {"address": "acct2", "amount": "6", "decimals": 6},
        ]
        with self.assertRaisesRegex(
            X1RPCLargestTokenAccountsError,
            "not ordered by descending raw amount",
        ):
            fetch_largest_token_accounts_raw(
                "mint1",
                rpc_url="https://rpc.example",
                session=Session(success(values)),
            )

    def test_rpc_error_fails_closed(self):
        with self.assertRaisesRegex(
            X1RPCLargestTokenAccountsError,
            "returned an error",
        ):
            fetch_largest_token_accounts_raw(
                "mint1",
                rpc_url="https://rpc.example",
                session=Session({"error": {"code": -1}}),
            )

    def test_invalid_slot_fails_closed(self):
        body = success()
        body["result"]["context"]["slot"] = True
        with self.assertRaisesRegex(
            X1RPCLargestTokenAccountsError,
            "slot is invalid",
        ):
            fetch_largest_token_accounts_raw(
                "mint1",
                rpc_url="https://rpc.example",
                session=Session(body),
            )

    def test_invalid_amount_fails_closed(self):
        values = [{"address": "acct1", "amount": "1.5", "decimals": 6}]
        with self.assertRaisesRegex(
            X1RPCLargestTokenAccountsError,
            "amount is invalid",
        ):
            fetch_largest_token_accounts_raw(
                "mint1",
                rpc_url="https://rpc.example",
                session=Session(success(values)),
            )

    def test_duplicate_accounts_fail_closed(self):
        values = [
            {"address": "acct1", "amount": "5", "decimals": 6},
            {"address": "acct1", "amount": "4", "decimals": 6},
        ]
        with self.assertRaisesRegex(
            X1RPCLargestTokenAccountsError,
            "duplicate accounts",
        ):
            fetch_largest_token_accounts_raw(
                "mint1",
                rpc_url="https://rpc.example",
                session=Session(success(values)),
            )

    def test_inconsistent_decimals_fail_closed(self):
        values = [
            {"address": "acct1", "amount": "5", "decimals": 6},
            {"address": "acct2", "amount": "4", "decimals": 9},
        ]
        with self.assertRaisesRegex(
            X1RPCLargestTokenAccountsError,
            "decimals are inconsistent",
        ):
            fetch_largest_token_accounts_raw(
                "mint1",
                rpc_url="https://rpc.example",
                session=Session(success(values)),
            )

    def test_empty_mint_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mint must not be empty"):
            fetch_largest_token_accounts_raw(
                "",
                rpc_url="https://rpc.example",
                session=Session(success()),
            )


if __name__ == "__main__":
    unittest.main()
