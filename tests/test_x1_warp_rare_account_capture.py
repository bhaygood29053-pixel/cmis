import base64
import unittest

from liquidity_scout.providers.x1.warp_onchain_inventory import (
    WARP_PROGRAM_ID,
    parse_program_accounts_result,
)
from liquidity_scout.providers.x1.warp_rare_account_capture import (
    CONTRACT,
    MAX_CANDIDATES_PER_CHAIN,
    RARE_ACCOUNT_SPACES,
    WarpRareAccountCaptureError,
    capture_rare_accounts_from_inventory,
    compare_rare_account_captures,
    parse_account_info_result,
    select_rare_account_candidates,
)


A = "11111111111111111111111111111111"
B = "22222222222222222222222222222222"
C = "33333333333333333333333333333333"


def inventory_account(pubkey, *, space, owner=WARP_PROGRAM_ID):
    return {
        "pubkey": pubkey,
        "account": {
            "data": ["", "base64"],
            "executable": False,
            "lamports": 1_000_000,
            "owner": owner,
            "rentEpoch": 0,
            "space": space,
        },
    }


def inventory(chain, rows):
    return parse_program_accounts_result(
        {"context": {"slot": 99}, "value": rows},
        chain=chain,
    )


def account_info(raw, *, owner=WARP_PROGRAM_ID, slot=123, executable=False):
    return {
        "context": {"slot": slot},
        "value": {
            "data": [base64.b64encode(raw).decode("ascii"), "base64"],
            "executable": executable,
            "lamports": 2_000_000,
            "owner": owner,
            "rentEpoch": 0,
        },
    }


class QueueRequester:
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


class WarpRareAccountCaptureTests(unittest.TestCase):
    def test_selects_only_accepted_rare_families(self):
        inv = inventory(
            "solana",
            [
                inventory_account(A, space=170),
                inventory_account(B, space=106),
                inventory_account(C, space=335),
            ],
        )

        selected = select_rare_account_candidates(inv)

        self.assertEqual(
            [(item["inventory_space"], item["pubkey"]) for item in selected],
            [(170, A), (335, C)],
        )
        self.assertTrue(
            all(item["semantic_role_verified"] is False for item in selected)
        )

    def test_selection_requires_verified_inventory_integrity(self):
        inv = inventory(
            "x1",
            [
                inventory_account(
                    A,
                    space=170,
                    owner="DifferentProgram111111111111111111111111",
                )
            ],
        )
        self.assertFalse(inv["response_integrity_verified"])

        with self.assertRaisesRegex(
            WarpRareAccountCaptureError,
            "integrity",
        ):
            select_rare_account_candidates(inv)

    def test_selection_fails_closed_above_bounded_ceiling(self):
        rows = [
            inventory_account(f"RareAccount{i:02d}111111111111111111111111111", space=170)
            for i in range(MAX_CANDIDATES_PER_CHAIN + 1)
        ]
        inv = inventory("solana", rows)

        with self.assertRaisesRegex(
            WarpRareAccountCaptureError,
            "exceeds bounded maximum",
        ):
            select_rare_account_candidates(inv)

    def test_selection_fails_when_no_rare_candidates_exist(self):
        inv = inventory("x1", [inventory_account(A, space=106)])
        with self.assertRaisesRegex(
            WarpRareAccountCaptureError,
            "no selected rare",
        ):
            select_rare_account_candidates(inv)

    def test_parse_account_hashes_full_bytes_without_retaining_raw_by_default(self):
        raw = bytes(range(170))
        result = parse_account_info_result(
            account_info(raw),
            chain="solana",
            pubkey=A,
            expected_space=170,
        )

        self.assertEqual(result["contract"], CONTRACT)
        self.assertEqual(result["data_length"], 170)
        self.assertTrue(result["data_length_verified"])
        self.assertEqual(result["prefix_hex"], raw[:32].hex())
        self.assertEqual(result["suffix_hex"], raw[-32:].hex())
        self.assertIsNone(result["data_base64"])
        self.assertFalse(result["raw_material_retained"])
        self.assertTrue(result["owner_verified"])
        self.assertTrue(result["non_executable_verified"])
        self.assertFalse(result["semantic_role_verified"])
        self.assertFalse(result["binary_layout_verified"])
        self.assertFalse(result["semantic_contract_accepted"])
        self.assertFalse(result["execution_authorized"])

    def test_raw_base64_requires_explicit_ephemeral_opt_in(self):
        raw = b"x" * 236
        encoded = base64.b64encode(raw).decode("ascii")
        result = parse_account_info_result(
            account_info(raw),
            chain="x1",
            pubkey=A,
            expected_space=236,
            include_raw_base64=True,
        )

        self.assertEqual(result["data_base64"], encoded)
        self.assertTrue(result["raw_material_retained"])

    def test_parse_rejects_owner_mismatch(self):
        with self.assertRaisesRegex(
            WarpRareAccountCaptureError,
            "owner",
        ):
            parse_account_info_result(
                account_info(
                    b"x" * 170,
                    owner="DifferentProgram111111111111111111111111",
                ),
                chain="x1",
                pubkey=A,
                expected_space=170,
            )

    def test_parse_rejects_executable_account(self):
        with self.assertRaisesRegex(
            WarpRareAccountCaptureError,
            "non-executable",
        ):
            parse_account_info_result(
                account_info(b"x" * 170, executable=True),
                chain="solana",
                pubkey=A,
                expected_space=170,
            )

    def test_parse_rejects_length_mismatch(self):
        with self.assertRaisesRegex(
            WarpRareAccountCaptureError,
            "byte length",
        ):
            parse_account_info_result(
                account_info(b"x" * 169),
                chain="solana",
                pubkey=A,
                expected_space=170,
            )

    def test_expected_space_must_be_accepted_rare_family(self):
        self.assertNotIn(106, RARE_ACCOUNT_SPACES)
        with self.assertRaisesRegex(ValueError, "accepted rare family"):
            parse_account_info_result(
                account_info(b"x" * 106),
                chain="x1",
                pubkey=A,
                expected_space=106,
            )

    def test_capture_requests_exact_candidate_accounts(self):
        inv = inventory(
            "x1",
            [
                inventory_account(B, space=236),
                inventory_account(A, space=170),
                inventory_account(C, space=106),
            ],
        )
        requester = QueueRequester(
            [
                account_info(b"a" * 170, slot=500),
                account_info(b"b" * 236, slot=501),
            ]
        )

        result = capture_rare_accounts_from_inventory(
            inv,
            rpc_url="https://rpc.example.invalid",
            requester=requester,
        )

        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["capture_count"], 2)
        self.assertEqual(
            [call["params"][0] for call in requester.calls],
            [A, B],
        )
        self.assertTrue(
            all(call["method"] == "getAccountInfo" for call in requester.calls)
        )
        self.assertTrue(result["all_owner_verified"])
        self.assertTrue(result["all_data_lengths_verified"])
        self.assertTrue(result["all_non_executable_verified"])
        self.assertFalse(result["raw_material_retained"])
        self.assertFalse(result["account_role_verified"])
        self.assertFalse(result["binary_layout_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_compare_exact_overlap_does_not_promote_semantics(self):
        sol = {
            "chain": "solana",
            "captures": [
                {
                    "pubkey": A,
                    "inventory_space": 170,
                    "data_sha256": "same",
                    "prefix_hex": "aa",
                    "suffix_hex": "bb",
                },
                {
                    "pubkey": B,
                    "inventory_space": 236,
                    "data_sha256": "sol-only",
                    "prefix_hex": "cc",
                    "suffix_hex": "dd",
                },
            ],
        }
        x1 = {
            "chain": "x1",
            "captures": [
                {
                    "pubkey": A,
                    "inventory_space": 170,
                    "data_sha256": "same",
                    "prefix_hex": "aa",
                    "suffix_hex": "bb",
                },
                {
                    "pubkey": C,
                    "inventory_space": 335,
                    "data_sha256": "x1-only",
                    "prefix_hex": "ee",
                    "suffix_hex": "ff",
                },
            ],
        }

        result = compare_rare_account_captures(sol, x1)

        self.assertEqual(result["exact_pubkey_overlap_count"], 1)
        overlap = result["exact_pubkey_overlaps"][0]
        self.assertEqual(overlap["pubkey"], A)
        self.assertTrue(overlap["same_space"])
        self.assertTrue(overlap["same_data_sha256"])
        self.assertTrue(overlap["same_prefix_hex"])
        self.assertTrue(overlap["same_suffix_hex"])
        self.assertFalse(overlap["semantic_role_equivalence_verified"])
        self.assertFalse(result["same_bytes_imply_same_semantics"])
        self.assertFalse(result["binary_layout_verified"])
        self.assertFalse(result["semantic_contract_accepted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
