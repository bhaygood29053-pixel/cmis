import base64
import unittest

from liquidity_scout.providers.x1.pool_state_fingerprint import (
    decode_base58_pubkey,
    find_pubkey_offsets,
    fingerprint_known_pool_state,
    parse_account_info_base64_result,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    WXNT_MINT,
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
)


ASSET_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"


def account_result(data, *, owner=XDEX_MAINNET_OBSERVED_PROGRAM_ID, space=None):
    return {
        "context": {"slot": 12345},
        "value": {
            "owner": owner,
            "space": len(data) if space is None else space,
            "lamports": 999,
            "executable": False,
            "rentEpoch": 0,
            "data": [base64.b64encode(data).decode("ascii"), "base64"],
        },
    }


class PoolStateFingerprintTests(unittest.TestCase):
    def test_base58_pubkeys_decode_to_32_bytes(self):
        self.assertEqual(len(decode_base58_pubkey(ASSET_MINT)), 32)
        self.assertEqual(len(decode_base58_pubkey(WXNT_MINT)), 32)
        self.assertEqual(len(decode_base58_pubkey(POOL)), 32)

    def test_find_pubkey_offsets_returns_exact_occurrences(self):
        needle = decode_base58_pubkey(ASSET_MINT)
        data = b"\x01" * 3 + needle + b"\x02" * 5 + needle
        self.assertEqual(find_pubkey_offsets(data, ASSET_MINT), [3, 40])

    def test_fingerprint_observes_asset_and_quote_identity_offsets(self):
        asset = decode_base58_pubkey(ASSET_MINT)
        quote = decode_base58_pubkey(WXNT_MINT)
        data = b"\x00" * 11 + asset + b"\xaa" * 9 + quote + b"\xff" * 13

        calls = []

        def requester(method, params, *, rpc_url):
            calls.append((method, params, rpc_url))
            return account_result(data)

        result = fingerprint_known_pool_state(
            pool_address=POOL,
            asset_mint=ASSET_MINT,
            rpc_url="rpc",
            requester=requester,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "getAccountInfo")
        self.assertEqual(calls[0][1][0], POOL)
        self.assertEqual(calls[0][1][1]["encoding"], "base64")
        self.assertTrue(result["recognized_program_owner"])
        self.assertEqual(
            result["identity_occurrences"]["asset_mint"]["offsets"],
            [11],
        )

        quote_rows = [
            row
            for name, row in result["identity_occurrences"].items()
            if name.startswith("quote_mint_")
        ]
        self.assertTrue(any(row["offsets"] == [52] for row in quote_rows))
        self.assertTrue(
            result["summary"]["pool_state_identity_coupling_observed"]
        )
        self.assertTrue(
            result["summary"]["pool_state_layout_candidate_observed"]
        )
        self.assertFalse(result["summary"]["pool_state_layout_verified"])
        self.assertNotIn("data", result["account"])
        self.assertEqual(result["account"]["space"], len(data))

    def test_unknown_program_owner_fails_closed(self):
        asset = decode_base58_pubkey(ASSET_MINT)
        quote = decode_base58_pubkey(WXNT_MINT)
        data = asset + quote

        def requester(method, params, *, rpc_url):
            return account_result(
                data,
                owner="11111111111111111111111111111111",
            )

        result = fingerprint_known_pool_state(
            pool_address=POOL,
            asset_mint=ASSET_MINT,
            requester=requester,
        )

        self.assertFalse(result["recognized_program_owner"])
        self.assertFalse(
            result["summary"]["pool_state_identity_coupling_observed"]
        )
        self.assertFalse(result["summary"]["pool_state_layout_verified"])

    def test_reported_space_mismatch_breaks_integrity(self):
        data = decode_base58_pubkey(ASSET_MINT)

        parsed = parse_account_info_base64_result(
            account_result(data, space=len(data) + 1),
            account=POOL,
        )

        self.assertEqual(parsed["data_length"], len(data))
        self.assertFalse(parsed["data_length_matches_space"])
        self.assertFalse(parsed["response_integrity_verified"])

    def test_invalid_base64_breaks_integrity_without_throwing(self):
        result = {
            "context": {"slot": 1},
            "value": {
                "owner": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                "space": 10,
                "data": ["%%%not-base64%%%", "base64"],
            },
        }

        parsed = parse_account_info_base64_result(result, account=POOL)

        self.assertIsNone(parsed["data"])
        self.assertFalse(parsed["response_integrity_verified"])


if __name__ == "__main__":
    unittest.main()
