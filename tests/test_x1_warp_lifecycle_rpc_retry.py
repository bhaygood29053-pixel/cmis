import unittest

from liquidity_scout.providers.x1.warp_lifecycle_rpc_retry import (
    SOLANA_PUBLIC_RPC_URL,
    resilient_get_transaction_post,
)


class FakeResponse:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self.body


class WarpLifecycleRpcRetryTests(unittest.TestCase):
    def test_solana_public_rpc_serializes_batch_members_with_pacing(self):
        calls = []
        sleeps = []

        def post(url, *, json, headers=None, timeout=None):
            calls.append(json)
            self.assertNotIsInstance(json, list)
            return FakeResponse(
                {"jsonrpc": "2.0", "id": json["id"], "result": {"slot": json["id"]}}
            )

        response = resilient_get_transaction_post(
            SOLANA_PUBLIC_RPC_URL,
            json=[
                {"jsonrpc": "2.0", "id": 1, "method": "getTransaction"},
                {"jsonrpc": "2.0", "id": 2, "method": "getTransaction"},
                {"jsonrpc": "2.0", "id": 3, "method": "getTransaction"},
            ],
            post=post,
            sleep=sleeps.append,
        )
        rows = response.json()
        self.assertEqual([row["id"] for row in rows], [1, 2, 3])
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(sleeps), 2)
        self.assertTrue(all(delay > 0 for delay in sleeps))

    def test_retries_only_failed_batch_member_on_other_rpc(self):
        calls = []

        def post(url, *, json, headers=None, timeout=None):
            calls.append(json)
            if isinstance(json, list):
                return FakeResponse(
                    [
                        {"jsonrpc": "2.0", "id": 1, "result": {"slot": 1}},
                        {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "error": {"code": -32005, "message": "busy"},
                        },
                    ]
                )
            return FakeResponse(
                {"jsonrpc": "2.0", "id": json["id"], "result": {"slot": 2}}
            )

        response = resilient_get_transaction_post(
            "https://rpc.invalid",
            json=[
                {"jsonrpc": "2.0", "id": 1, "method": "getTransaction"},
                {"jsonrpc": "2.0", "id": 2, "method": "getTransaction"},
            ],
            post=post,
            sleep=lambda _: None,
        )
        rows = response.json()
        self.assertEqual(rows[0]["result"]["slot"], 1)
        self.assertEqual(rows[1]["result"]["slot"], 2)
        self.assertEqual(len(calls), 2)
        self.assertIsInstance(calls[0], list)
        self.assertEqual(calls[1]["id"], 2)

    def test_null_result_is_retried(self):
        attempts = 0

        def post(url, *, json, headers=None, timeout=None):
            nonlocal attempts
            if isinstance(json, list):
                return FakeResponse(
                    [{"jsonrpc": "2.0", "id": 1, "result": None}]
                )
            attempts += 1
            if attempts == 1:
                return FakeResponse(
                    {"jsonrpc": "2.0", "id": 1, "result": None}
                )
            return FakeResponse(
                {"jsonrpc": "2.0", "id": 1, "result": {"slot": 9}}
            )

        response = resilient_get_transaction_post(
            "https://rpc.invalid",
            json=[{"jsonrpc": "2.0", "id": 1, "method": "getTransaction"}],
            post=post,
            sleep=lambda _: None,
        )
        self.assertEqual(response.json()[0]["result"]["slot"], 9)
        self.assertEqual(attempts, 2)

    def test_permanent_error_remains_error_after_bounded_retries(self):
        attempts = 0

        def post(url, *, json, headers=None, timeout=None):
            nonlocal attempts
            if isinstance(json, list):
                return FakeResponse(
                    [
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "error": {"code": -32000, "message": "unavailable"},
                        }
                    ]
                )
            attempts += 1
            return FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "error": {"code": -32000, "message": "unavailable"},
                }
            )

        response = resilient_get_transaction_post(
            "https://rpc.invalid",
            json=[{"jsonrpc": "2.0", "id": 1, "method": "getTransaction"}],
            post=post,
            sleep=lambda _: None,
        )
        self.assertIsNotNone(response.json()[0]["error"])
        self.assertEqual(attempts, MAX_ITEM_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
