import struct
import unittest

from liquidity_scout.providers.x1.pool_state_fingerprint import decode_base58_pubkey
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import X1_PROGRAM
from liquidity_scout.providers.x1.xdex_multi_hop import PARSED_SCHEMA
from liquidity_scout.providers.x1.xdex_multi_hop_onchain import (
    VERIFICATION_SCHEMA,
    XDEXMultiHopOnchainError,
    verify_multi_hop_quote_onchain,
)

TOKEN_A = "So11111111111111111111111111111111111111112"
TOKEN_B = "33kzreZb3DnzBrcbdeiWhGtdc8aU1uxqb2mMTii2hNGq"
TOKEN_C = "GdgA3rcAzWsrtt8QkyNXNTrrvfRPeAYiJPyyxSku8pzk"
POOL_1 = "FqZJXKZ92mbLzyZ3u6Mfb9WxsDpCnvSvq433m9qXUCLs"
POOL_2 = "DYjBdDGvMQ4rkFSWP5ZzF3weJNSx3tc639QehAnUyCkp"
CONFIG = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"
VAULT_1A = "2U5t2Z5bfVaXrcDtMNuGE7XRr2EPcwci12KQ7ZveYgL6"
VAULT_1B = "5NRbRmg6sYxt4fCtrj2TEZxqHRgiEezNJwocMYEnjW2Q"
VAULT_2A = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
VAULT_2B = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
AUTHORITY = X1_PROGRAM


def _put_pubkey(raw, offset, address):
    raw[offset : offset + 32] = decode_base58_pubkey(address)


def pool_bytes(config, vault_0, vault_1, mint_0, mint_1):
    raw = bytearray(637)
    _put_pubkey(raw, 8, config)
    _put_pubkey(raw, 72, vault_0)
    _put_pubkey(raw, 104, vault_1)
    _put_pubkey(raw, 168, mint_0)
    _put_pubkey(raw, 200, mint_1)
    raw[331] = 9
    raw[332] = 9
    raw[389] = 0
    raw[390] = 0
    return bytes(raw)


def config_bytes(trade_fee=2800, creator_fee=0):
    raw = bytearray(116)
    struct.pack_into("<Q", raw, 12, trade_fee)
    struct.pack_into("<Q", raw, 20, 120000)
    struct.pack_into("<Q", raw, 28, 40000)
    struct.pack_into("<Q", raw, 108, creator_fee)
    return bytes(raw)


def parsed_quote():
    return {
        "schema": PARSED_SCHEMA,
        "chain": "x1",
        "source": "XDEX multi-hop public quote API",
        "request": {},
        "input_mint": TOKEN_A,
        "output_mint": TOKEN_C,
        "input_amount_raw": 1_000_000_000,
        "output_amount_gross_raw": 10_526_643,
        "output_amount_raw": 10_474_009,
        "provider_fee_bps": 50,
        "provider_fee_amount_raw": 52_633,
        "provider_fee_floor_rounding_delta_raw": 1,
        "hop_count": 2,
        "path": [TOKEN_A, TOKEN_B, TOKEN_C],
        "hops": [
            {
                "index": 0,
                "pool": POOL_1,
                "venue": "xdex",
                "token_in_mint": TOKEN_A,
                "token_out_mint": TOKEN_B,
                "amount_in_raw": 1_000_000_000,
                "amount_out_raw": 10_668_504_732,
                "provider_reserve_in_raw": 1_416_758_715,
                "provider_reserve_out_raw": 25_825_641_771,
                "provider_trade_fee_rate_ppm": 2800,
                "provider_curve_output_raw": 10_668_504_732,
            },
            {
                "index": 1,
                "pool": POOL_2,
                "venue": "xdex",
                "token_in_mint": TOKEN_B,
                "token_out_mint": TOKEN_C,
                "amount_in_raw": 10_668_504_732,
                "amount_out_raw": 10_526_643,
                "provider_reserve_in_raw": 1_000_000_000_000,
                "provider_reserve_out_raw": 1_000_000_000,
                "provider_trade_fee_rate_ppm": 2800,
                "provider_curve_output_raw": 10_526_643,
            },
        ],
        "provider_venues": ["xdex"],
        "provider_schema_verified": True,
        "provider_route_identity_verified": True,
        "provider_hop_continuity_verified": True,
        "provider_hop_curve_arithmetic_verified": True,
        "provider_fee_transform_verified": True,
        "provider_fee_business_semantics_verified": False,
        "provider_cross_dex_route_quoted": False,
        "cross_dex_execution_observed": False,
        "route_optimality_verified": False,
        "provider_semantics_promoted": False,
        "prepare_called": False,
        "read_only": True,
        "execution_authorized": False,
    }


def fixture_fetchers(*, fee_rate=2800, reserve_delta=0):
    account_rows = {
        POOL_1: {
            "account": POOL_1,
            "account_exists": True,
            "response_integrity_verified": True,
            "owner": X1_PROGRAM,
            "data": pool_bytes(CONFIG, VAULT_1A, VAULT_1B, TOKEN_A, TOKEN_B),
            "context_slot": 101,
        },
        POOL_2: {
            "account": POOL_2,
            "account_exists": True,
            "response_integrity_verified": True,
            "owner": X1_PROGRAM,
            "data": pool_bytes(CONFIG, VAULT_2A, VAULT_2B, TOKEN_B, TOKEN_C),
            "context_slot": 101,
        },
        CONFIG: {
            "account": CONFIG,
            "account_exists": True,
            "response_integrity_verified": True,
            "owner": X1_PROGRAM,
            "data": config_bytes(fee_rate),
            "context_slot": 101,
        },
    }
    token_rows = {
        VAULT_1A: (TOKEN_A, 1_416_758_715 + reserve_delta),
        VAULT_1B: (TOKEN_B, 25_825_641_771),
        VAULT_2A: (TOKEN_B, 1_000_000_000_000),
        VAULT_2B: (TOKEN_C, 1_000_000_000),
    }

    def account_fetcher(address):
        return account_rows[address]

    def token_fetcher(address):
        mint, amount = token_rows[address]
        return {
            "account": address,
            "account_exists": True,
            "identity_verified": True,
            "mint": mint,
            "decimals": 9,
            "token_authority": AUTHORITY,
            "raw_amount": str(amount),
        }

    return account_fetcher, token_fetcher


class XDEXMultiHopOnchainTests(unittest.TestCase):
    def test_independently_verifies_every_hop_and_reconstructs_outputs(self):
        account_fetcher, token_fetcher = fixture_fetchers()
        slots = iter([100, 102])
        result = verify_multi_hop_quote_onchain(
            parsed_quote(),
            account_state_fetcher=account_fetcher,
            token_account_fetcher=token_fetcher,
            slot_fetcher=lambda: next(slots),
        )
        self.assertEqual(result["schema"], VERIFICATION_SCHEMA)
        self.assertEqual(result["hop_count"], 2)
        self.assertEqual(result["verification_slot_span"], 2)
        self.assertTrue(result["route_structure_verified"])
        self.assertTrue(result["pool_identity_verified"])
        self.assertTrue(result["pool_state_verified"])
        self.assertTrue(result["fee_math_verified"])
        self.assertTrue(result["reserve_math_verified"])
        self.assertTrue(result["current_state_alignment_verified"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["route_optimality_verified"])
        self.assertFalse(result["cross_dex_execution_observed"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(result["hops"][0]["reconstructed_output_raw"], 10_668_504_732)
        self.assertEqual(result["hops"][1]["reconstructed_output_raw"], 10_526_643)
        self.assertEqual(result["hops"][0]["trade_fee_rate_ppm"], 2800)

    def test_reserve_mismatch_fails_closed(self):
        account_fetcher, token_fetcher = fixture_fetchers(reserve_delta=1)
        slots = iter([100, 101])
        with self.assertRaisesRegex(XDEXMultiHopOnchainError, "reserves"):
            verify_multi_hop_quote_onchain(
                parsed_quote(),
                account_state_fetcher=account_fetcher,
                token_account_fetcher=token_fetcher,
                slot_fetcher=lambda: next(slots),
            )

    def test_decoded_fee_rate_mismatch_fails_closed(self):
        account_fetcher, token_fetcher = fixture_fetchers(fee_rate=3000)
        slots = iter([100, 101])
        with self.assertRaisesRegex(XDEXMultiHopOnchainError, "trade_fee_rate"):
            verify_multi_hop_quote_onchain(
                parsed_quote(),
                account_state_fetcher=account_fetcher,
                token_account_fetcher=token_fetcher,
                slot_fetcher=lambda: next(slots),
            )

    def test_non_xdex_hop_fails_closed(self):
        source = parsed_quote()
        source["hops"][1]["venue"] = "degen"
        account_fetcher, token_fetcher = fixture_fetchers()
        slots = iter([100, 101])
        with self.assertRaisesRegex(XDEXMultiHopOnchainError, "non-XDEX"):
            verify_multi_hop_quote_onchain(
                source,
                account_state_fetcher=account_fetcher,
                token_account_fetcher=token_fetcher,
                slot_fetcher=lambda: next(slots),
            )

    def test_excessive_slot_span_fails_closed(self):
        account_fetcher, token_fetcher = fixture_fetchers()
        slots = iter([100, 120])
        with self.assertRaisesRegex(XDEXMultiHopOnchainError, "slot-alignment"):
            verify_multi_hop_quote_onchain(
                parsed_quote(),
                account_state_fetcher=account_fetcher,
                token_account_fetcher=token_fetcher,
                slot_fetcher=lambda: next(slots),
                max_slot_span=8,
            )


if __name__ == "__main__":
    unittest.main()
