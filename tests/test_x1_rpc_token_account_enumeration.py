import unittest
from unittest.mock import Mock

from liquidity_scout.providers.x1.rpc_token_account_enumeration import (
    X1RPCTokenAccountEnumerationError,
    fetch_token_accounts_by_mint_raw,
)


MINT = "Mint111"
PROGRAM = "TokenProgram111"
RPC = "https://rpc.example.invalid"


def parsed_account(address, *, mint=MINT, program=PROGRAM, owner="Owner111"):
    return {
        "pubkey": address,
        "account": {
            "owner": program,
            "data": {
                "program": "spl-token",
                "parsed": {
                    "type": "account",
                    "info": {
                        "mint": mint,
                        "owner": owner,
                        "state": "initialized",
                    },
                },
            },
        },
    }


def session_for(body):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = body
    session = Mock()
    session.post.return_value = response
    return session


class X1RPCTokenAccountEnumerationTests(unittest.TestCase):
    def test_requests_exact_program_and_mint_filter_but_keeps_total_coverage_unverified(self):
        session = session_for({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 12345},
                "value": [parsed_account("Acct1"), parsed_account("Acct2")],
            },
        })

        result = fetch_token_accounts_by_mint_raw(
            MINT,
            token_program_id=PROGRAM,
            rpc_url=RPC,
            session=session,
        )

        payload = session.post.call_args.kwargs["json"]
        self.assertEqual(payload["method"], "getProgramAccounts")
        self.assertEqual(payload["params"][0], PROGRAM)
        config = payload["params"][1]
        self.assertEqual(config["encoding"], "jsonParsed")
        self.assertTrue(config["withContext"])
        self.assertEqual(
            config["filters"],
            [{"memcmp": {"offset": 0, "bytes": MINT}}],
        )
        self.assertEqual(result["account_count_candidate"], 2)
        self.assertEqual(result["slot"], 12345)
        self.assertTrue(result["returned_account_identity_verified"])
        self.assertTrue(result["token_account_semantics_verified"])
        self.assertFalse(result["enumeration_complete"])
        self.assertFalse(result["truncation_absent_verified"])
        self.assertEqual(result["coverage"], "unverified")
        self.assertFalse(result["total_count_eligible"])
        self.assertFalse(result["holder_semantics_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_empty_success_is_zero_candidate_not_verified_total_zero(self):
        session = session_for({
            "result": {"context": {"slot": 10}, "value": []},
        })
        result = fetch_token_accounts_by_mint_raw(
            MINT,
            token_program_id=PROGRAM,
            rpc_url=RPC,
            session=session,
        )
        self.assertEqual(result["account_count_candidate"], 0)
        self.assertFalse(result["total_count_eligible"])
        self.assertEqual(result["coverage"], "unverified")

    def test_rejects_wrong_mint_wrong_program_duplicate_or_non_account_parse(self):
        cases = (
            [parsed_account("A", mint="OtherMint")],
            [parsed_account("A", program="OtherProgram")],
            [parsed_account("A"), parsed_account("A")],
            [{
                "pubkey": "A",
                "account": {
                    "owner": PROGRAM,
                    "data": {"parsed": {"type": "mint", "info": {"mint": MINT}}},
                },
            }],
        )
        for values in cases:
            with self.subTest(values=values):
                session = session_for({
                    "result": {"context": {"slot": 10}, "value": values},
                })
                with self.assertRaises(X1RPCTokenAccountEnumerationError):
                    fetch_token_accounts_by_mint_raw(
                        MINT,
                        token_program_id=PROGRAM,
                        rpc_url=RPC,
                        session=session,
                    )

    def test_rejects_malformed_result_slot_and_provider_error_without_leaking_body(self):
        cases = (
            {"result": []},
            {"result": {"context": {"slot": True}, "value": []}},
            {"result": {"context": {"slot": -1}, "value": []}},
            {"error": {"message": "secret provider detail"}},
        )
        for body in cases:
            with self.subTest(body=body):
                session = session_for(body)
                with self.assertRaises(X1RPCTokenAccountEnumerationError) as ctx:
                    fetch_token_accounts_by_mint_raw(
                        MINT,
                        token_program_id=PROGRAM,
                        rpc_url=RPC,
                        session=session,
                    )
                self.assertNotIn("secret provider detail", str(ctx.exception))

    def test_transport_failures_are_sanitized(self):
        session = Mock()
        session.post.side_effect = RuntimeError("credential-shaped transport detail")
        with self.assertRaises(X1RPCTokenAccountEnumerationError) as ctx:
            fetch_token_accounts_by_mint_raw(
                MINT,
                token_program_id=PROGRAM,
                rpc_url=RPC,
                session=session,
            )
        self.assertNotIn("credential-shaped transport detail", str(ctx.exception))
        self.assertNotIn(RPC, str(ctx.exception))

    def test_empty_identifiers_fail_before_network(self):
        with self.assertRaises(ValueError):
            fetch_token_accounts_by_mint_raw("", token_program_id=PROGRAM, rpc_url=RPC)
        with self.assertRaises(ValueError):
            fetch_token_accounts_by_mint_raw(MINT, token_program_id="", rpc_url=RPC)


if __name__ == "__main__":
    unittest.main()
