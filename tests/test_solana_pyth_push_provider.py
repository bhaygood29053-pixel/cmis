import struct
import unittest

from liquidity_scout.providers.solana.pyth_push import (
    PRICE_UPDATE_V2_DISCRIMINATOR,
    PYTH_CORE_RECEIVER_PROGRAM_ID,
    PythSolanaPushProvider,
    PythSolanaSourceError,
    SOL_USD_CURRENT_ACCOUNT,
    SOL_USD_FEED_ID,
    USDC_MINT,
    USDC_USD_CURRENT_ACCOUNT,
    USDC_USD_FEED_ID,
    WSOL_MINT,
)


_BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_decode(value):
    number = 0
    for char in value:
        number = number * 58 + _BASE58.index(char)
    payload = b"" if number == 0 else number.to_bytes((number.bit_length() + 7) // 8, "big")
    return b"\x00" * (len(value) - len(value.lstrip("1"))) + payload


def price_account_bytes(
    *,
    feed_id=USDC_USD_FEED_ID,
    price=100_012_345,
    conf=12_345,
    exponent=-8,
    publish_time=2_000_000_000,
    prev_publish_time=1_999_999_999,
    ema_price=100_000_000,
    ema_conf=10_000,
    posted_slot=123456,
    verification="full",
    num_signatures=5,
    discriminator=PRICE_UPDATE_V2_DISCRIMINATOR,
    write_authority=None,
):
    authority = (
        base58_decode(USDC_USD_CURRENT_ACCOUNT)
        if write_authority is None
        else write_authority
    )
    assert len(authority) == 32
    payload = bytearray()
    payload += discriminator
    payload += authority
    if verification == "partial":
        payload += bytes([0, num_signatures])
    elif verification == "full":
        payload += bytes([1])
    else:
        payload += bytes([verification])
    payload += bytes.fromhex(feed_id)
    payload += struct.pack("<q", price)
    payload += struct.pack("<Q", conf)
    payload += struct.pack("<i", exponent)
    payload += struct.pack("<q", publish_time)
    payload += struct.pack("<q", prev_publish_time)
    payload += struct.pack("<q", ema_price)
    payload += struct.pack("<Q", ema_conf)
    payload += struct.pack("<Q", posted_slot)
    if len(payload) < 134:
        payload += b"\x00" * (134 - len(payload))
    return bytes(payload)


class FakeRPC:
    chain = "solana"

    def __init__(self, *, data=None, owner=PYTH_CORE_RECEIVER_PROGRAM_ID):
        self.data = data if data is not None else price_account_bytes()
        self.owner = owner
        self.calls = []

    def get_account_data(self, address):
        self.calls.append(address)
        return {
            "chain": "solana",
            "source": "solana_rpc",
            "method": "getAccountInfo(base64)",
            "address": address,
            "context_slot": 123500,
            "owner": self.owner,
            "executable": False,
            "lamports": 1,
            "data": self.data,
            "data_length": len(self.data),
            "commitment": "confirmed",
        }


class PythSolanaPushProviderTests(unittest.TestCase):
    def test_exact_usdc_fixture_decodes_verified_pyth_price(self):
        rpc = FakeRPC()
        ticks = iter([2_000_000_010.0, 2_000_000_011.25])
        provider = PythSolanaPushProvider(rpc, clock=lambda: next(ticks))

        result = provider.get_price(USDC_MINT)

        self.assertEqual(rpc.calls, [USDC_USD_CURRENT_ACCOUNT])
        self.assertEqual(result["chain"], "solana")
        self.assertEqual(result["source"], "pyth_core_solana_push")
        self.assertTrue(result["mapping_verified"])
        self.assertEqual(result["feed_alias"], "USDC/USD")
        self.assertEqual(result["feed_id"], USDC_USD_FEED_ID)
        self.assertTrue(result["feed_id_verified"])
        self.assertTrue(result["account_owner_verified"])
        self.assertTrue(result["write_authority_matches_feed_account"])
        self.assertEqual(result["verification_level"], "full")
        self.assertTrue(result["full_verification"])
        self.assertTrue(result["price_integrity_verified"])
        self.assertEqual(result["price_raw"], 100_012_345)
        self.assertEqual(result["conf_raw"], 12_345)
        self.assertEqual(result["exponent"], -8)
        self.assertEqual(result["price_usd"], "1.00012345")
        self.assertEqual(result["confidence_usd"], "0.00012345")
        self.assertEqual(result["publish_time_unix"], 2_000_000_000)
        self.assertEqual(result["posted_slot"], 123456)
        self.assertTrue(result["fact_time_verified"])
        self.assertEqual(result["collection_started_at_unix"], 2_000_000_010.0)
        self.assertEqual(result["collection_completed_at_unix"], 2_000_000_011.25)
        self.assertTrue(result["collection_time_verified"])
        self.assertFalse(result["symbol_discovery_used"])
        self.assertFalse(result["hermes_used"])
        self.assertFalse(result["current_price_promotable"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_exact_wsol_fixture_decodes_verified_sol_usd_price(self):
        data = price_account_bytes(
            feed_id=SOL_USD_FEED_ID,
            price=15_012_345_678,
            conf=123_456,
            exponent=-8,
            publish_time=2_000_000_100,
            prev_publish_time=2_000_000_099,
            write_authority=base58_decode(SOL_USD_CURRENT_ACCOUNT),
        )
        rpc = FakeRPC(data=data)
        ticks = iter([2_000_000_110.0, 2_000_000_111.0])
        result = PythSolanaPushProvider(
            rpc,
            clock=lambda: next(ticks),
        ).get_price(WSOL_MINT)

        self.assertEqual(rpc.calls, [SOL_USD_CURRENT_ACCOUNT])
        self.assertEqual(result["mint"], WSOL_MINT)
        self.assertEqual(result["feed_alias"], "SOL/USD")
        self.assertEqual(result["feed_id"], SOL_USD_FEED_ID)
        self.assertEqual(result["price_subject"], "SOL")
        self.assertEqual(result["unit"], "USD_per_SOL")
        self.assertEqual(result["price_usd"], "150.12345678")
        self.assertTrue(result["mapping_verified"])
        self.assertTrue(result["feed_id_verified"])
        self.assertTrue(result["full_verification"])
        self.assertTrue(result["price_integrity_verified"])
        self.assertFalse(result["current_price_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_unsupported_mint_never_queries_rpc_or_symbol_matches(self):
        rpc = FakeRPC()
        result = PythSolanaPushProvider(rpc).get_price(
            "UnsupportedMint111111111111111111111111111111"
        )

        self.assertEqual(rpc.calls, [])
        self.assertFalse(result["price_available"])
        self.assertFalse(result["mapping_verified"])
        self.assertEqual(
            result["reason"],
            "pyth_exact_mint_feed_mapping_unavailable",
        )

    def test_wrong_account_owner_fails_closed(self):
        provider = PythSolanaPushProvider(
            FakeRPC(owner="WrongOwner111111111111111111111111111111111")
        )

        with self.assertRaisesRegex(PythSolanaSourceError, "owner mismatch"):
            provider.get_price(USDC_MINT)

    def test_feed_id_mismatch_fails_closed(self):
        wrong = "00" * 32
        provider = PythSolanaPushProvider(
            FakeRPC(data=price_account_bytes(feed_id=wrong))
        )

        with self.assertRaisesRegex(PythSolanaSourceError, "feed ID mismatch"):
            provider.get_price(USDC_MINT)

    def test_discriminator_mismatch_fails_closed(self):
        provider = PythSolanaPushProvider(
            FakeRPC(data=price_account_bytes(discriminator=b"12345678"))
        )

        with self.assertRaisesRegex(PythSolanaSourceError, "discriminator mismatch"):
            provider.get_price(USDC_MINT)

    def test_partial_verification_is_preserved_and_not_integrity_verified(self):
        result = PythSolanaPushProvider(
            FakeRPC(data=price_account_bytes(verification="partial", num_signatures=5))
        ).get_price(USDC_MINT)

        self.assertEqual(result["verification_level"], "partial")
        self.assertEqual(result["verification_num_signatures"], 5)
        self.assertFalse(result["full_verification"])
        self.assertFalse(result["price_integrity_verified"])
        self.assertTrue(result["fact_time_verified"])
        self.assertFalse(result["current_price_promotable"])

    def test_write_authority_mismatch_fails_closed(self):
        provider = PythSolanaPushProvider(
            FakeRPC(data=price_account_bytes(write_authority=b"\x01" * 32))
        )

        with self.assertRaisesRegex(PythSolanaSourceError, "write authority mismatch"):
            provider.get_price(USDC_MINT)

    def test_invalid_publish_time_order_fails_closed(self):
        provider = PythSolanaPushProvider(
            FakeRPC(
                data=price_account_bytes(
                    publish_time=100,
                    prev_publish_time=101,
                )
            )
        )

        with self.assertRaisesRegex(PythSolanaSourceError, "prev_publish_time"):
            provider.get_price(USDC_MINT)

    def test_non_positive_fixture_price_is_preserved_but_not_available(self):
        result = PythSolanaPushProvider(
            FakeRPC(data=price_account_bytes(price=0))
        ).get_price(USDC_MINT)

        self.assertFalse(result["price_available"])
        self.assertIsNone(result["price_usd"])
        self.assertFalse(result["price_integrity_verified"])


if __name__ == "__main__":
    unittest.main()
