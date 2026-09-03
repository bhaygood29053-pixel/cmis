import unittest

from liquidity_scout.providers.x1.warp_onchain_inventory import (
    CONTRACT,
    SOLANA_RPC_URL,
    WARP_PROGRAM_ID,
    X1_RPC_URL,
    WarpOnchainInventoryError,
    compare_warp_inventories,
    inventory_warp_both_chains,
    inventory_warp_program_accounts,
    parse_program_accounts_result,
)


A = "11111111111111111111111111111111"
B = "22222222222222222222222222222222"
C = "33333333333333333333333333333333"


def account(pubkey, *, owner=WARP_PROGRAM_ID, space=128, lamports=1_000_000):
    return {
        "pubkey": pubkey,
        "account": {
            "data": ["", "base64"],
            "executable": False,
            "lamports": lamports,
            "owner": owner,
            "rentEpoch": 18446744073709551615,
            "space": space,
        },
    }


class RecordingRequester:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def __call__(self, method, params, *, rpc_url, timeout):
        self.calls.append(
            {
                "method": method,
                "params": params,
                "rpc_url": rpc_url,
                "timeout": timeout,
            }
        )
        return self.results.pop(0)


class WarpOnchainInventoryTests(unittest.TestCase):
    def test_parse_inventory_records_exact_owner_and_no_semantic_roles(self):
        result = parse_program_accounts_result(
            {
                "context": {"slot": 123},
                "value": [
                    account(B, space=64, lamports=22),
                    account(A, space=128, lamports=11),
                ],
            },
            chain="solana",
        )

        self.assertEqual(result["contract"], CONTRACT)
        self.assertEqual(result["program_id"], WARP_PROGRAM_ID)
        self.assertEqual(result["context_slot"], 123)
        self.assertEqual(result["unique_account_count"], 2)
        self.assertEqual(result["account_size_counts"], {"128": 1, "64": 1})
        self.assertTrue(result["response_integrity_verified"])
        self.assertEqual([item["pubkey"] for item in result["accounts"]], [A, B])
        self.assertTrue(all(item["owner_matches_program"] for item in result["accounts"]))
        self.assertTrue(all(item["semantic_role"] is None for item in result["accounts"]))
        self.assertFalse(result["account_binary_layout_verified"])
        self.assertFalse(result["semantic_contract_accepted"])
        self.assertFalse(result["execution_authorized"])

    def test_inventory_hash_is_deterministic_across_row_order(self):
        first = parse_program_accounts_result(
            {"context": {"slot": 5}, "value": [account(A), account(B)]},
            chain="x1",
        )
        second = parse_program_accounts_result(
            {"value": [account(B), account(A)], "context": {"slot": 5}},
            chain="x1",
        )

        self.assertEqual(first["inventory_sha256"], second["inventory_sha256"])
        self.assertEqual(
            first["structural_inventory_sha256"],
            second["structural_inventory_sha256"],
        )

    def test_owner_mismatch_fails_integrity_without_silent_drop(self):
        result = parse_program_accounts_result(
            {
                "value": [
                    account(A),
                    account(B, owner="DifferentProgram111111111111111111111111"),
                ]
            },
            chain="x1",
        )

        self.assertEqual(result["unique_account_count"], 2)
        self.assertEqual(result["owner_mismatch_count"], 1)
        self.assertFalse(result["response_integrity_verified"])
        self.assertFalse(result["accounts"][1]["owner_matches_program"])

    def test_duplicate_and_malformed_rows_are_visible(self):
        result = parse_program_accounts_result(
            {
                "value": [
                    account(A),
                    account(A),
                    {"pubkey": B},
                    "bad",
                ]
            },
            chain="solana",
        )

        self.assertEqual(result["unique_account_count"], 1)
        self.assertEqual(result["duplicate_pubkey_count"], 1)
        self.assertEqual(result["malformed_row_count"], 2)
        self.assertFalse(result["response_integrity_verified"])

    def test_chain_must_be_exact(self):
        with self.assertRaisesRegex(ValueError, "solana or x1"):
            parse_program_accounts_result([], chain="ethereum")

    def test_non_list_result_fails_closed(self):
        with self.assertRaises(WarpOnchainInventoryError):
            parse_program_accounts_result({"not": "accounts"}, chain="x1")

    def test_inventory_request_is_zero_byte_read_only_by_default(self):
        requester = RecordingRequester(
            [
                {
                    "context": {"slot": 999},
                    "value": [account(A)],
                }
            ]
        )

        result = inventory_warp_program_accounts(
            chain="x1",
            requester=requester,
        )

        self.assertEqual(result["rpc_url"], X1_RPC_URL)
        self.assertEqual(result["data_slice_length"], 0)
        self.assertEqual(len(requester.calls), 1)
        call = requester.calls[0]
        self.assertEqual(call["method"], "getProgramAccounts")
        self.assertEqual(call["params"][0], WARP_PROGRAM_ID)
        self.assertEqual(
            call["params"][1],
            {
                "encoding": "base64",
                "commitment": "confirmed",
                "dataSlice": {"offset": 0, "length": 0},
                "withContext": True,
            },
        )
        self.assertFalse(result["execution_authorized"])

    def test_data_slice_is_bounded(self):
        requester = RecordingRequester([{"value": []}])
        inventory_warp_program_accounts(
            chain="solana",
            data_slice_length=256,
            requester=requester,
        )
        self.assertEqual(requester.calls[0]["rpc_url"], SOLANA_RPC_URL)

        with self.assertRaises(ValueError):
            inventory_warp_program_accounts(
                chain="solana",
                data_slice_length=257,
                requester=requester,
            )

    def test_compare_preserves_only_exact_pubkey_overlap(self):
        solana = parse_program_accounts_result(
            {
                "context": {"slot": 100},
                "value": [
                    account(A, space=128),
                    account(B, space=256),
                ],
            },
            chain="solana",
        )
        x1 = parse_program_accounts_result(
            {
                "context": {"slot": 200},
                "value": [
                    account(B, space=999),
                    account(C, space=128),
                ],
            },
            chain="x1",
        )

        result = compare_warp_inventories(solana, x1)

        self.assertEqual(result["exact_pubkey_overlap"], [B])
        self.assertEqual(result["exact_pubkey_overlap_count"], 1)
        self.assertFalse(result["same_size_implies_same_role"])
        self.assertFalse(result["cross_chain_role_equivalence_verified"])
        self.assertFalse(result["semantic_contract_accepted"])
        self.assertFalse(result["execution_authorized"])

    def test_both_chain_inventory_uses_independent_rpc_urls(self):
        requester = RecordingRequester(
            [
                {"context": {"slot": 100}, "value": [account(A)]},
                {"context": {"slot": 200}, "value": [account(B)]},
            ]
        )

        result = inventory_warp_both_chains(requester=requester)

        self.assertEqual(
            [call["rpc_url"] for call in requester.calls],
            [SOLANA_RPC_URL, X1_RPC_URL],
        )
        self.assertEqual(result["solana_inventory"]["chain"], "solana")
        self.assertEqual(result["x1_inventory"]["chain"], "x1")
        self.assertFalse(result["semantic_contract_accepted"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
