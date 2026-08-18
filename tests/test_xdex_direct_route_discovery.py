import struct
import unittest

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.xdex_direct_route_discovery import (
    XDEXDirectRouteDiscoveryError,
    discover_direct_route,
    discover_pair_program_accounts,
)
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import X1_PROGRAM


def key(byte):
    raw = bytes([byte]) * 32
    return raw, encode_base58_pubkey(raw)


MINT_A_RAW, MINT_A = key(1)
MINT_B_RAW, MINT_B = key(2)
VAULT_A_RAW, VAULT_A = key(3)
VAULT_B_RAW, VAULT_B = key(4)
CONFIG_1_RAW, CONFIG_1 = key(5)
CONFIG_2_RAW, CONFIG_2 = key(6)
POOL_1 = "POOL_1"
POOL_2 = "POOL_2"


def pool_bytes(config_raw, *, mint_0=MINT_A_RAW, mint_1=MINT_B_RAW):
    data = bytearray(637)
    data[8:40] = config_raw
    data[72:104] = VAULT_A_RAW
    data[104:136] = VAULT_B_RAW
    data[168:200] = mint_0
    data[200:232] = mint_1
    struct.pack_into("<Q", data, 341, 10)
    struct.pack_into("<Q", data, 349, 20)
    struct.pack_into("<Q", data, 357, 30)
    struct.pack_into("<Q", data, 365, 40)
    struct.pack_into("<Q", data, 397, 0)
    struct.pack_into("<Q", data, 405, 0)
    return bytes(data)


def config_bytes(rate=2800):
    data = bytearray(116)
    struct.pack_into("<Q", data, 12, rate)
    return bytes(data)


def candidate_report(*pools, complete=True):
    return {
        "program_id": X1_PROGRAM,
        "accounts": [
            {"pubkey": pool, "owner": X1_PROGRAM, "space": 637}
            for pool in pools
        ],
        "summary": {
            "accepted_xdex_program_family_pair_enumeration_complete": complete,
            "recognized_program_registry_globally_exhaustive": False,
            "all_x1_dex_pair_enumeration_complete": False,
        },
    }


class XDEXDirectRouteDiscoveryTests(unittest.TestCase):
    def token_account(self, address):
        if address == VAULT_A:
            return {"identity_verified": True, "mint": MINT_A, "raw_amount": 5_000_000}
        if address == VAULT_B:
            return {"identity_verified": True, "mint": MINT_B, "raw_amount": 9_000_000}
        raise AssertionError(address)

    def account_fetcher(self, pools):
        def fetch(address):
            if address == POOL_1 and POOL_1 in pools:
                return {"owner": X1_PROGRAM, "data": pool_bytes(CONFIG_1_RAW)}
            if address == POOL_2 and POOL_2 in pools:
                return {"owner": X1_PROGRAM, "data": pool_bytes(CONFIG_2_RAW)}
            if address == CONFIG_1:
                return {"owner": X1_PROGRAM, "data": config_bytes(2800)}
            if address == CONFIG_2:
                return {"owner": X1_PROGRAM, "data": config_bytes(3000)}
            raise AssertionError(address)
        return fetch

    def test_pair_program_enumerator_queries_both_exact_mint_orientations(self):
        calls = []

        def requester(method, params, rpc_url):
            self.assertEqual(method, "getProgramAccounts")
            calls.append(params)
            filters = params[1]["filters"]
            mint0 = filters[1]["memcmp"]["bytes"]
            mint1 = filters[2]["memcmp"]["bytes"]
            rows = []
            if (mint0, mint1) == (MINT_A, MINT_B):
                rows = [{
                    "pubkey": POOL_1,
                    "account": {
                        "owner": X1_PROGRAM,
                        "space": 637,
                        "lamports": 1,
                        "executable": False,
                        "rentEpoch": 0,
                    },
                }]
            return {"context": {"slot": 123}, "value": rows}

        result = discover_pair_program_accounts(
            MINT_A,
            MINT_B,
            rpc_url="https://rpc.example",
            requester=requester,
        )

        self.assertEqual(len(calls), 2)
        first_filters = calls[0][1]["filters"]
        second_filters = calls[1][1]["filters"]
        self.assertEqual(first_filters[0], {"dataSize": 637})
        self.assertEqual(first_filters[1], {"memcmp": {"offset": 168, "bytes": MINT_A}})
        self.assertEqual(first_filters[2], {"memcmp": {"offset": 200, "bytes": MINT_B}})
        self.assertEqual(second_filters[1], {"memcmp": {"offset": 168, "bytes": MINT_B}})
        self.assertEqual(second_filters[2], {"memcmp": {"offset": 200, "bytes": MINT_A}})
        self.assertEqual([row["pubkey"] for row in result["accounts"]], [POOL_1])
        self.assertTrue(
            result["summary"]["accepted_xdex_program_family_pair_enumeration_complete"]
        )
        self.assertFalse(
            result["summary"]["recognized_program_registry_globally_exhaustive"]
        )

    def test_pair_program_enumerator_fails_if_one_orientation_fails(self):
        calls = 0

        def requester(method, params, rpc_url):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("rpc failed")
            return {"value": []}

        with self.assertRaisesRegex(
            XDEXDirectRouteDiscoveryError,
            "one mint orientation",
        ):
            discover_pair_program_accounts(
                MINT_A,
                MINT_B,
                rpc_url="https://rpc.example",
                requester=requester,
            )

    def test_zero_enumerated_candidates_is_unavailable_without_route(self):
        result = discover_direct_route(
            MINT_A,
            MINT_B,
            candidate_provider=lambda a, b: candidate_report(),
            account_state_fetcher=lambda address: self.fail("RPC must not be called"),
            token_account_fetcher=lambda address: self.fail("vault RPC must not be called"),
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["route"])
        self.assertEqual(result["enumerated_candidate_count"], 0)
        self.assertEqual(result["verified_candidate_count"], 0)
        self.assertTrue(result["program_family_pair_enumeration_complete"])
        self.assertFalse(result["recognized_program_registry_globally_exhaustive"])
        self.assertFalse(result["best_route_claimed"])
        self.assertFalse(result["execution_authorized"])

    def test_one_verified_candidate_returns_unique_exact_directional_route(self):
        result = discover_direct_route(
            MINT_A,
            MINT_B,
            candidate_provider=lambda a, b: candidate_report(POOL_1),
            account_state_fetcher=self.account_fetcher({POOL_1}),
            token_account_fetcher=self.token_account,
        )

        self.assertEqual(result["status"], "verified_unique")
        self.assertEqual(
            result["selection_claim"],
            "unique_verified_direct_candidate_in_accepted_xdex_program_family",
        )
        self.assertEqual(result["route"], {
            "token_in_mint": MINT_A,
            "token_out_mint": MINT_B,
            "pool": POOL_1,
            "amm_config": CONFIG_1,
        })
        self.assertEqual(result["verified_candidate_count"], 1)
        self.assertGreater(result["candidates"][0]["active_reserve_in_raw"], 0)
        self.assertGreater(result["candidates"][0]["active_reserve_out_raw"], 0)
        self.assertFalse(result["global_optimality_claimed"])
        self.assertFalse(result["all_x1_dex_pair_enumeration_complete"])

    def test_two_verified_candidates_is_ambiguous_and_selects_nothing(self):
        result = discover_direct_route(
            MINT_A,
            MINT_B,
            candidate_provider=lambda a, b: candidate_report(POOL_1, POOL_2),
            account_state_fetcher=self.account_fetcher({POOL_1, POOL_2}),
            token_account_fetcher=self.token_account,
        )

        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["route"])
        self.assertIsNone(result["selection_claim"])
        self.assertEqual(result["verified_candidate_count"], 2)
        self.assertEqual(
            {candidate["pool"] for candidate in result["candidates"]},
            {POOL_1, POOL_2},
        )
        self.assertFalse(result["best_route_claimed"])

    def test_duplicate_enumeration_rows_do_not_create_false_ambiguity(self):
        result = discover_direct_route(
            MINT_A,
            MINT_B,
            candidate_provider=lambda a, b: candidate_report(POOL_1, POOL_1),
            account_state_fetcher=self.account_fetcher({POOL_1}),
            token_account_fetcher=self.token_account,
        )

        self.assertEqual(result["enumerated_candidate_count"], 1)
        self.assertEqual(result["verified_candidate_count"], 1)
        self.assertEqual(result["status"], "verified_unique")

    def test_incomplete_enumeration_cannot_produce_unique_route(self):
        with self.assertRaisesRegex(
            XDEXDirectRouteDiscoveryError,
            "completeness was not verified",
        ):
            discover_direct_route(
                MINT_A,
                MINT_B,
                candidate_provider=lambda a, b: candidate_report(POOL_1, complete=False),
                account_state_fetcher=self.account_fetcher({POOL_1}),
                token_account_fetcher=self.token_account,
            )

    def test_onchain_pair_mismatch_rejects_candidate(self):
        wrong_mint_raw, _ = key(9)

        def fetch(address):
            if address == POOL_1:
                return {
                    "owner": X1_PROGRAM,
                    "data": pool_bytes(CONFIG_1_RAW, mint_1=wrong_mint_raw),
                }
            self.fail(f"config should not be reached: {address}")

        result = discover_direct_route(
            MINT_A,
            MINT_B,
            candidate_provider=lambda a, b: candidate_report(POOL_1),
            account_state_fetcher=fetch,
            token_account_fetcher=self.token_account,
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["verified_candidate_count"], 0)
        self.assertIn("mint pair", result["rejected_candidates"][0]["reason"])

    def test_wrong_program_owner_rejects_candidate(self):
        def fetch(address):
            if address == POOL_1:
                return {"owner": "WRONG_PROGRAM", "data": pool_bytes(CONFIG_1_RAW)}
            self.fail(f"unexpected fetch: {address}")

        result = discover_direct_route(
            MINT_A,
            MINT_B,
            candidate_provider=lambda a, b: candidate_report(POOL_1),
            account_state_fetcher=fetch,
            token_account_fetcher=self.token_account,
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("owner", result["rejected_candidates"][0]["reason"])

    def test_inactive_reserves_reject_candidate(self):
        def empty_token_account(address):
            record = dict(self.token_account(address))
            if address == VAULT_A:
                record["raw_amount"] = 40
            return record

        result = discover_direct_route(
            MINT_A,
            MINT_B,
            candidate_provider=lambda a, b: candidate_report(POOL_1),
            account_state_fetcher=self.account_fetcher({POOL_1}),
            token_account_fetcher=empty_token_account,
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("active reserves", result["rejected_candidates"][0]["reason"])

    def test_reverse_direction_preserves_requested_token_direction(self):
        result = discover_direct_route(
            MINT_B,
            MINT_A,
            candidate_provider=lambda a, b: candidate_report(POOL_1),
            account_state_fetcher=self.account_fetcher({POOL_1}),
            token_account_fetcher=self.token_account,
        )
        self.assertEqual(result["status"], "verified_unique")
        self.assertEqual(result["route"]["token_in_mint"], MINT_B)
        self.assertEqual(result["route"]["token_out_mint"], MINT_A)


if __name__ == "__main__":
    unittest.main()
