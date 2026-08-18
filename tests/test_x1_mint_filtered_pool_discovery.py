import unittest

from liquidity_scout.providers.x1.mint_filtered_pool_discovery import (
    discover_program_state_accounts_for_mint,
)


PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
POOL_A = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
POOL_B = "GwwCyLS4VEeZXyPWPYRNiVSuVur6ntioxBmjDQHHHv9x"


def _row(pubkey, *, space=637, owner=PROGRAM):
    return {
        "pubkey": pubkey,
        "account": {
            "owner": owner,
            "space": space,
            "lamports": 1000,
            "executable": False,
            "rentEpoch": 0,
            "data": ["", "base64"],
        },
    }


class MintFilteredPoolDiscoveryTests(unittest.TestCase):
    def test_unions_both_verified_mint_offsets(self):
        calls = []

        def requester(method, params, *, rpc_url):
            calls.append((method, params, rpc_url))
            offset = params[1]["filters"][1]["memcmp"]["offset"]
            self.assertEqual(params[1]["filters"][0], {"dataSize": 637})
            self.assertEqual(params[1]["filters"][1]["memcmp"]["bytes"], MINT)
            if offset == 168:
                return [_row(POOL_A)]
            if offset == 200:
                return [_row(POOL_B), _row(POOL_A)]
            self.fail(f"unexpected offset {offset}")

        report = discover_program_state_accounts_for_mint(
            mint=MINT,
            program_id=PROGRAM,
            account_space=637,
            mint_offsets=[168, 200],
            rpc_url="https://example.invalid",
            requester=requester,
        )

        self.assertEqual(len(calls), 2)
        self.assertTrue(
            report["summary"]["all_filter_queries_integrity_verified"]
        )
        self.assertTrue(
            report["summary"]["targeted_program_family_mint_filter_observed"]
        )
        self.assertEqual(
            report["summary"]["unique_matching_program_state_account_count"],
            2,
        )
        by_pubkey = {row["pubkey"]: row for row in report["accounts"]}
        self.assertEqual(by_pubkey[POOL_A]["matched_mint_offsets"], [168, 200])
        self.assertEqual(by_pubkey[POOL_B]["matched_mint_offsets"], [200])
        self.assertFalse(
            report["summary"]["every_matching_account_is_pool_verified"]
        )
        self.assertFalse(
            report["summary"]["global_onchain_pool_discovery_proven"]
        )

    def test_wrong_space_fails_query_integrity_closed(self):
        def requester(method, params, *, rpc_url):
            offset = params[1]["filters"][1]["memcmp"]["offset"]
            if offset == 168:
                return [_row(POOL_A, space=4075)]
            return []

        report = discover_program_state_accounts_for_mint(
            mint=MINT,
            program_id=PROGRAM,
            account_space=637,
            mint_offsets=[168, 200],
            requester=requester,
        )

        self.assertFalse(
            report["summary"]["all_filter_queries_integrity_verified"]
        )
        self.assertFalse(
            report["summary"]["targeted_program_family_mint_filter_observed"]
        )
        query_168 = next(
            row for row in report["filter_queries"] if row["offset"] == 168
        )
        self.assertEqual(query_168["space_mismatch_count"], 1)

    def test_one_failed_offset_query_does_not_promote(self):
        def requester(method, params, *, rpc_url):
            offset = params[1]["filters"][1]["memcmp"]["offset"]
            if offset == 168:
                return [_row(POOL_A)]
            raise RuntimeError("filtered RPC unavailable")

        report = discover_program_state_accounts_for_mint(
            mint=MINT,
            program_id=PROGRAM,
            account_space=637,
            mint_offsets=[168, 200],
            requester=requester,
        )

        self.assertFalse(
            report["summary"]["all_filter_queries_integrity_verified"]
        )
        self.assertFalse(
            report["summary"]["targeted_program_family_mint_filter_observed"]
        )
        self.assertEqual(len(report["errors"]), 1)
        self.assertEqual(report["errors"][0]["offset"], 200)
        self.assertIn("filtered RPC unavailable", report["errors"][0]["error"])

    def test_requires_two_distinct_offsets(self):
        with self.assertRaises(ValueError):
            discover_program_state_accounts_for_mint(
                mint=MINT,
                program_id=PROGRAM,
                account_space=637,
                mint_offsets=[168, 168],
                requester=lambda *args, **kwargs: [],
            )


if __name__ == "__main__":
    unittest.main()
