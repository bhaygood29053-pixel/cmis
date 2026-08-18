import struct
import unittest

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.xdex_direct_route_discovery import discover_direct_route
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


def row(pool, *, base=MINT_A, quote=MINT_B):
    return {
        "address": pool,
        "baseToken": {"address": "API_BASE", "mint": base, "symbol": "A"},
        "quoteToken": {"address": "API_QUOTE", "mint": quote, "symbol": "B"},
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

    def test_zero_candidates_is_unavailable_without_route(self):
        result = discover_direct_route(
            MINT_A,
            MINT_B,
            pool_fetcher=lambda: [row("OTHER", base="C", quote="D")],
            account_state_fetcher=lambda address: self.fail("RPC must not be called"),
            token_account_fetcher=lambda address: self.fail("vault RPC must not be called"),
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["route"])
        self.assertEqual(result["catalog_candidate_count"], 0)
        self.assertEqual(result["verified_candidate_count"], 0)
        self.assertFalse(result["best_route_claimed"])
        self.assertFalse(result["execution_authorized"])

    def test_one_verified_candidate_returns_unique_exact_directional_route(self):
        result = discover_direct_route(
            MINT_A,
            MINT_B,
            pool_fetcher=lambda: [row(POOL_1)],
            account_state_fetcher=self.account_fetcher({POOL_1}),
            token_account_fetcher=self.token_account,
        )

        self.assertEqual(result["status"], "verified_unique")
        self.assertEqual(result["selection_claim"], "unique_verified_direct_candidate")
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

    def test_two_verified_candidates_is_ambiguous_and_selects_nothing(self):
        result = discover_direct_route(
            MINT_A,
            MINT_B,
            pool_fetcher=lambda: [row(POOL_1), row(POOL_2)],
            account_state_fetcher=self.account_fetcher({POOL_1, POOL_2}),
            token_account_fetcher=self.token_account,
        )

        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["route"])
        self.assertIsNone(result["selection_claim"])
        self.assertEqual(result["verified_candidate_count"], 2)
        self.assertEqual({candidate["pool"] for candidate in result["candidates"]}, {POOL_1, POOL_2})
        self.assertFalse(result["best_route_claimed"])

    def test_duplicate_catalog_rows_do_not_create_false_ambiguity(self):
        result = discover_direct_route(
            MINT_A,
            MINT_B,
            pool_fetcher=lambda: [row(POOL_1), row(POOL_1)],
            account_state_fetcher=self.account_fetcher({POOL_1}),
            token_account_fetcher=self.token_account,
        )

        self.assertEqual(result["catalog_candidate_count"], 1)
        self.assertEqual(result["verified_candidate_count"], 1)
        self.assertEqual(result["status"], "verified_unique")

    def test_catalog_pair_mismatch_never_reaches_chain_verification(self):
        calls = []
        result = discover_direct_route(
            MINT_A,
            MINT_B,
            pool_fetcher=lambda: [row(POOL_1, base=MINT_A, quote="WRONG")],
            account_state_fetcher=lambda address: calls.append(address),
            token_account_fetcher=self.token_account,
        )
        self.assertEqual(calls, [])
        self.assertEqual(result["status"], "unavailable")

    def test_onchain_pair_mismatch_rejects_candidate(self):
        wrong_mint_raw, _ = key(9)
        def fetch(address):
            if address == POOL_1:
                return {"owner": X1_PROGRAM, "data": pool_bytes(CONFIG_1_RAW, mint_1=wrong_mint_raw)}
            self.fail(f"config should not be reached: {address}")

        result = discover_direct_route(
            MINT_A,
            MINT_B,
            pool_fetcher=lambda: [row(POOL_1)],
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
            pool_fetcher=lambda: [row(POOL_1)],
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
            pool_fetcher=lambda: [row(POOL_1)],
            account_state_fetcher=self.account_fetcher({POOL_1}),
            token_account_fetcher=empty_token_account,
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("active reserves", result["rejected_candidates"][0]["reason"])

    def test_reverse_direction_preserves_requested_token_direction(self):
        result = discover_direct_route(
            MINT_B,
            MINT_A,
            pool_fetcher=lambda: [row(POOL_1)],
            account_state_fetcher=self.account_fetcher({POOL_1}),
            token_account_fetcher=self.token_account,
        )
        self.assertEqual(result["status"], "verified_unique")
        self.assertEqual(result["route"]["token_in_mint"], MINT_B)
        self.assertEqual(result["route"]["token_out_mint"], MINT_A)


if __name__ == "__main__":
    unittest.main()
