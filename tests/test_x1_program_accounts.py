import unittest

from liquidity_scout.providers.x1.program_accounts import (
    inventory_program_accounts,
    inventory_recognized_amm_programs,
    parse_program_accounts_result,
)


PROGRAM_A = "Program1111111111111111111111111111111111"
PROGRAM_B = "Program2222222222222222222222222222222222"


def account(pubkey, owner, *, space=128):
    return {
        "pubkey": pubkey,
        "account": {
            "owner": owner,
            "space": space,
            "lamports": 123,
            "executable": False,
            "rentEpoch": 1,
            "data": ["", "base64"],
        },
    }


class ProgramAccountInventoryTests(unittest.TestCase):
    def test_parser_preserves_program_owned_account_metadata(self):
        result = parse_program_accounts_result(
            [
                account("acct-a", PROGRAM_A, space=128),
                account("acct-b", PROGRAM_A, space=256),
            ],
            program_id=PROGRAM_A,
        )

        self.assertEqual(result["returned_row_count"], 2)
        self.assertEqual(result["unique_account_count"], 2)
        self.assertEqual(result["account_size_counts"], {"128": 1, "256": 1})
        self.assertTrue(result["response_integrity_verified"])
        self.assertTrue(result["program_account_enumeration_observed"])
        self.assertFalse(result["program_inventory_exhaustive_promoted"])
        self.assertFalse(result["pool_state_layout_verified"])

    def test_parser_fails_closed_on_duplicate_and_owner_mismatch(self):
        result = parse_program_accounts_result(
            [
                account("acct-a", PROGRAM_A),
                account("acct-a", PROGRAM_A),
                account("acct-b", PROGRAM_B),
                {"bad": "row"},
            ],
            program_id=PROGRAM_A,
        )

        self.assertEqual(result["duplicate_pubkey_count"], 1)
        self.assertEqual(result["owner_mismatch_count"], 1)
        self.assertEqual(result["malformed_row_count"], 1)
        self.assertFalse(result["response_integrity_verified"])
        self.assertFalse(result["program_inventory_exhaustive_promoted"])

    def test_context_wrapped_response_is_supported(self):
        result = parse_program_accounts_result(
            {
                "context": {"slot": 12345},
                "value": [account("acct-a", PROGRAM_A)],
            },
            program_id=PROGRAM_A,
        )
        self.assertEqual(result["context_slot"], 12345)
        self.assertTrue(result["response_integrity_verified"])

    def test_inventory_uses_bounded_data_slice(self):
        calls = []

        def requester(method, params, **kwargs):
            calls.append((method, params, kwargs))
            return [account("acct-a", PROGRAM_A)]

        result = inventory_program_accounts(
            PROGRAM_A,
            rpc_url="https://rpc.example",
            data_slice_length=0,
            requester=requester,
        )

        self.assertEqual(len(calls), 1)
        method, params, kwargs = calls[0]
        self.assertEqual(method, "getProgramAccounts")
        self.assertEqual(params[0], PROGRAM_A)
        self.assertEqual(params[1]["encoding"], "base64")
        self.assertEqual(params[1]["dataSlice"], {"offset": 0, "length": 0})
        self.assertEqual(kwargs["rpc_url"], "https://rpc.example")
        self.assertEqual(result["unique_account_count"], 1)
        self.assertFalse(result["program_inventory_exhaustive_promoted"])

    def test_recognized_program_inventory_deduplicates_pubkeys_but_never_promotes_global_discovery(self):
        def requester(method, params, **kwargs):
            program = params[0]
            if program == PROGRAM_A:
                return [
                    account("shared", PROGRAM_A),
                    account("a-only", PROGRAM_A),
                ]
            return [
                account("shared", PROGRAM_B),
                account("b-only", PROGRAM_B),
            ]

        result = inventory_recognized_amm_programs(
            rpc_url="rpc",
            program_ids=(PROGRAM_A, PROGRAM_B),
            requester=requester,
        )

        self.assertEqual(result["recognized_program_count"], 2)
        self.assertEqual(
            result["summary"]["unique_program_owned_account_count"],
            3,
        )
        self.assertTrue(
            result["summary"]["all_responses_integrity_verified"]
        )
        self.assertFalse(
            result["summary"]["recognized_program_registry_globally_exhaustive"]
        )
        self.assertFalse(
            result["summary"]["global_onchain_pool_discovery_proven"]
        )

    def test_invalid_data_slice_bound_is_rejected(self):
        with self.assertRaises(ValueError):
            inventory_program_accounts(
                PROGRAM_A,
                data_slice_length=257,
                requester=lambda *args, **kwargs: [],
            )


if __name__ == "__main__":
    unittest.main()
