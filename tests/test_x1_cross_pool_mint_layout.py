import base64
import unittest

from liquidity_scout.providers.x1.cross_pool_mint_layout import (
    verify_cross_pool_mint_layout,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
)


ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(payload):
    number = int.from_bytes(payload, "big")
    chars = []
    while number:
        number, remainder = divmod(number, 58)
        chars.append(ALPHABET[remainder])
    leading = len(payload) - len(payload.lstrip(b"\x00"))
    encoded = "".join(reversed(chars)) if chars else ""
    return ("1" * leading) + encoded


def mint(seed):
    return b58encode(bytes([seed]) * 32)


def account_result(data, *, owner=XDEX_MAINNET_OBSERVED_PROGRAM_ID, slot=123):
    return {
        "context": {"slot": slot},
        "value": {
            "owner": owner,
            "space": len(data),
            "lamports": 1000,
            "executable": False,
            "rentEpoch": 0,
            "data": [base64.b64encode(data).decode("ascii"), "base64"],
        },
    }


def pool_state(base_mint, quote_mint, *, base_offset=200, quote_offset=168, space=637):
    from liquidity_scout.providers.x1.pool_state_fingerprint import decode_base58_pubkey

    data = bytearray(space)
    base = decode_base58_pubkey(base_mint)
    quote = decode_base58_pubkey(quote_mint)
    data[base_offset:base_offset + 32] = base
    data[quote_offset:quote_offset + 32] = quote
    return bytes(data)


class FakeRequester:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def __call__(self, method, params, *, rpc_url):
        self.calls.append((method, params, rpc_url))
        self.assert_method(method)
        return self.rows[params[0]]

    @staticmethod
    def assert_method(method):
        if method != "getAccountInfo":
            raise AssertionError(method)


class CrossPoolMintLayoutTests(unittest.TestCase):
    def make_pools(self, count=3):
        pools = []
        rows = {}
        for index in range(count):
            base = mint(10 + index * 2)
            quote = mint(11 + index * 2)
            address = f"pool-{index}"
            pools.append({
                "pool_address": address,
                "pair": f"A{index}/Q{index}",
                "base_mint": base,
                "quote_mint": quote,
            })
            rows[address] = account_result(pool_state(base, quote))
        return pools, rows

    def test_three_independent_pools_verify_stable_mint_pair_offsets(self):
        pools, rows = self.make_pools(3)
        requester = FakeRequester(rows)

        result = verify_cross_pool_mint_layout(
            pools,
            rpc_url="rpc",
            min_verification_pools=3,
            requester=requester,
        )

        self.assertTrue(result["summary"]["pool_mint_pair_layout_verified"])
        self.assertEqual(result["summary"]["verified_mint_pair_layout_family_count"], 1)
        family = result["families"][0]
        self.assertEqual(family["space"], 637)
        self.assertEqual(family["sample_count"], 3)
        self.assertEqual(family["stable_mint_offsets"], [168, 200])
        self.assertTrue(family["mint_pair_layout_verified"])
        self.assertFalse(family["pool_state_layout_verified"])
        self.assertFalse(result["summary"]["global_onchain_pool_discovery_proven"])

    def test_one_offset_outlier_fails_closed(self):
        pools, rows = self.make_pools(3)
        third = pools[2]
        rows[third["pool_address"]] = account_result(
            pool_state(
                third["base_mint"],
                third["quote_mint"],
                quote_offset=160,
            )
        )

        result = verify_cross_pool_mint_layout(
            pools,
            rpc_url="rpc",
            min_verification_pools=3,
            requester=FakeRequester(rows),
        )

        self.assertFalse(result["summary"]["pool_mint_pair_layout_verified"])
        family = result["families"][0]
        self.assertEqual(family["observed_mint_offset_sets"], [[160, 200], [168, 200]])
        self.assertFalse(family["mint_pair_layout_verified"])

    def test_fewer_than_three_pools_cannot_verify_layout(self):
        pools, rows = self.make_pools(2)

        result = verify_cross_pool_mint_layout(
            pools,
            rpc_url="rpc",
            min_verification_pools=3,
            requester=FakeRequester(rows),
        )

        self.assertFalse(result["summary"]["pool_mint_pair_layout_verified"])
        family = result["families"][0]
        self.assertFalse(family["enough_independent_pool_samples"])
        self.assertEqual(family["stable_mint_offsets"], [168, 200])

    def test_unrecognized_program_owner_invalidates_sample_family(self):
        pools, rows = self.make_pools(3)
        address = pools[1]["pool_address"]
        data = pool_state(pools[1]["base_mint"], pools[1]["quote_mint"])
        rows[address] = account_result(data, owner="11111111111111111111111111111111")

        result = verify_cross_pool_mint_layout(
            pools,
            rpc_url="rpc",
            min_verification_pools=3,
            requester=FakeRequester(rows),
        )

        self.assertFalse(result["summary"]["pool_mint_pair_layout_verified"])
        self.assertTrue(any(
            observation["recognized_program_owner"] is False
            for observation in result["observations"]
        ))


if __name__ == "__main__":
    unittest.main()
