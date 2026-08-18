import struct
import unittest
from datetime import datetime, timezone

from liquidity_scout.providers.x1.candidate_pool_role import encode_base58_pubkey
from liquidity_scout.providers.x1.xdex_exact_route import (
    XDEXExactRouteError,
    collect_exact_route_snapshot,
    fetch_explicit_config_quote,
)
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import X1_PROGRAM


def key(byte):
    raw = bytes([byte]) * 32
    return raw, encode_base58_pubkey(raw)


CONFIG_RAW, CONFIG = key(2)
VAULT0_RAW, VAULT0 = key(3)
VAULT1_RAW, VAULT1 = key(4)
MINT0_RAW, MINT0 = key(5)
MINT1_RAW, MINT1 = key(6)
AUTHORITY_RAW, AUTHORITY = key(7)
OTHER_AUTHORITY_RAW, OTHER_AUTHORITY = key(8)
POOL = "TEST_POOL"


def pool_bytes():
    data = bytearray(637)
    data[8:40] = CONFIG_RAW
    data[72:104] = VAULT0_RAW
    data[104:136] = VAULT1_RAW
    data[168:200] = MINT0_RAW
    data[200:232] = MINT1_RAW
    data[331] = 6
    data[332] = 9
    struct.pack_into("<Q", data, 341, 10)
    struct.pack_into("<Q", data, 349, 20)
    struct.pack_into("<Q", data, 357, 30)
    struct.pack_into("<Q", data, 365, 40)
    struct.pack_into("<Q", data, 397, 0)
    struct.pack_into("<Q", data, 405, 0)
    return bytes(data)


def config_bytes():
    data = bytearray(116)
    struct.pack_into("<Q", data, 12, 2800)
    struct.pack_into("<Q", data, 20, 250000)
    struct.pack_into("<Q", data, 28, 50000)
    struct.pack_into("<Q", data, 108, 0)
    return bytes(data)


ROUTE = {
    "token_in_mint": MINT0,
    "token_out_mint": MINT1,
    "pool": POOL,
    "amm_config": CONFIG,
}


class FakeResponse:
    def __init__(self, body):
        self.body = body
        self.text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, body):
        self.body = body
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append({"url": url, "params": dict(params), "timeout": timeout})
        return FakeResponse(self.body)


class XDEXExactRouteProviderTests(unittest.TestCase):
    def account_state(self, address):
        if address == POOL:
            data = pool_bytes()
        elif address == CONFIG:
            data = config_bytes()
        else:
            raise AssertionError(address)
        return {
            "account": address,
            "account_exists": True,
            "response_integrity_verified": True,
            "owner": X1_PROGRAM,
            "data": data,
        }

    def token_account(self, address):
        if address == VAULT0:
            mint, decimals, raw = MINT0, 6, "5000000000"
        elif address == VAULT1:
            mint, decimals, raw = MINT1, 9, "9000000000"
        else:
            raise AssertionError(address)
        return {
            "account": address,
            "account_exists": True,
            "identity_verified": True,
            "mint": mint,
            "decimals": decimals,
            "raw_amount": raw,
            "token_authority": AUTHORITY,
        }

    def quote(self, token_in, token_out, amount, config):
        self.assertEqual((token_in, token_out, config), (MINT0, MINT1, CONFIG))
        self.assertEqual(str(amount), "1000")
        return {
            "inputMint": MINT0,
            "outputMint": MINT1,
            "amm_config_address": CONFIG,
            "outputAmount": "123.45",
            "rate": "0.12345",
            "priceImpactPct": "16.6249721754",
        }

    def collect(self, **overrides):
        kwargs = {
            "route": ROUTE,
            "token_in_amount": "1000",
            "account_state_fetcher": self.account_state,
            "token_account_fetcher": self.token_account,
            "quote_fetcher": self.quote,
            "clock": lambda: datetime(2026, 8, 18, 22, 0, tzinfo=timezone.utc),
        }
        kwargs.update(overrides)
        return collect_exact_route_snapshot(**kwargs)

    def test_collects_exact_verified_route_snapshot_read_only(self):
        snapshot = self.collect()

        self.assertEqual(snapshot["schema"], "xdex_exact_route_snapshot.v1")
        self.assertEqual(snapshot["route"], ROUTE)
        self.assertEqual(snapshot["trade_fee_rate_ppm"], 2800)
        self.assertEqual(snapshot["raw_input_amount"], 1_000_000_000)
        self.assertEqual(snapshot["active_reserve_in_raw"], 4_999_999_960)
        self.assertEqual(snapshot["active_reserve_out_raw"], 8_999_999_940)
        self.assertEqual(snapshot["observed_at"], "2026-08-18T22:00:00Z")
        self.assertTrue(snapshot["quote_identity_verified"])
        self.assertTrue(snapshot["active_reserves_verified"])
        self.assertTrue(snapshot["read_only"])
        self.assertFalse(snapshot["execution_authorized"])

    def test_pool_account_identity_mismatch_fails_closed(self):
        def wrong_account(address):
            record = dict(self.account_state(address))
            if address == POOL:
                record["account"] = "OTHER_POOL"
            return record

        with self.assertRaisesRegex(XDEXExactRouteError, "account identity"):
            self.collect(account_state_fetcher=wrong_account)

    def test_pool_response_integrity_must_be_verified(self):
        def wrong_account(address):
            record = dict(self.account_state(address))
            if address == POOL:
                record["response_integrity_verified"] = False
            return record

        with self.assertRaisesRegex(XDEXExactRouteError, "response integrity"):
            self.collect(account_state_fetcher=wrong_account)

    def test_config_response_integrity_must_be_verified(self):
        def wrong_account(address):
            record = dict(self.account_state(address))
            if address == CONFIG:
                record["response_integrity_verified"] = False
            return record

        with self.assertRaisesRegex(XDEXExactRouteError, "response integrity"):
            self.collect(account_state_fetcher=wrong_account)

    def test_quote_config_identity_mismatch_fails_closed(self):
        def wrong_quote(token_in, token_out, amount, config):
            result = self.quote(token_in, token_out, amount, config)
            result["amm_config_address"] = "WRONG_CONFIG"
            return result

        with self.assertRaisesRegex(XDEXExactRouteError, "quote AMM config"):
            self.collect(quote_fetcher=wrong_quote)

    def test_pool_route_pair_mismatch_fails_closed(self):
        wrong = dict(ROUTE)
        wrong["token_out_mint"] = "WRONG_MINT"
        with self.assertRaisesRegex(XDEXExactRouteError, "pool mint pair"):
            collect_exact_route_snapshot(
                wrong,
                "1000",
                account_state_fetcher=self.account_state,
                token_account_fetcher=self.token_account,
                quote_fetcher=self.quote,
            )

    def test_vault_identity_mismatch_fails_closed(self):
        def wrong_vault(address):
            record = dict(self.token_account(address))
            if address == VAULT0:
                record["mint"] = "WRONG_MINT"
            return record

        with self.assertRaisesRegex(XDEXExactRouteError, "vault mint identity"):
            self.collect(token_account_fetcher=wrong_vault)

    def test_vault_account_identity_mismatch_fails_closed(self):
        def wrong_vault(address):
            record = dict(self.token_account(address))
            if address == VAULT0:
                record["account"] = VAULT1
            return record

        with self.assertRaisesRegex(XDEXExactRouteError, "vault account identity"):
            self.collect(token_account_fetcher=wrong_vault)

    def test_vault_decimals_mismatch_fails_closed(self):
        def wrong_vault(address):
            record = dict(self.token_account(address))
            if address == VAULT0:
                record["decimals"] = 9
            return record

        with self.assertRaisesRegex(XDEXExactRouteError, "vault decimals"):
            self.collect(token_account_fetcher=wrong_vault)

    def test_noncanonical_vault_raw_amount_fails_closed(self):
        def wrong_vault(address):
            record = dict(self.token_account(address))
            if address == VAULT0:
                record["raw_amount"] = "05000000000"
            return record

        with self.assertRaisesRegex(XDEXExactRouteError, "canonical non-negative integer string"):
            self.collect(token_account_fetcher=wrong_vault)

    def test_vaults_must_share_verified_authority(self):
        def wrong_vault(address):
            record = dict(self.token_account(address))
            if address == VAULT1:
                record["token_authority"] = OTHER_AUTHORITY
            return record

        with self.assertRaisesRegex(XDEXExactRouteError, "same token authority"):
            self.collect(token_account_fetcher=wrong_vault)

    def test_explicit_config_quote_transport_sets_zero_slippage_and_config(self):
        session = FakeSession(
            {
                "success": True,
                "data": {
                    "inputMint": MINT0,
                    "outputMint": MINT1,
                    "amm_config_address": CONFIG,
                    "priceImpactPct": "1.0",
                },
            }
        )
        result = fetch_explicit_config_quote(
            MINT0,
            MINT1,
            "1.25",
            CONFIG,
            session=session,
            timeout=9,
        )

        self.assertEqual(result["amm_config_address"], CONFIG)
        params = session.calls[0]["params"]
        self.assertEqual(params["is_exact_amount_in"], "true")
        self.assertEqual(params["slippage"], "0")
        self.assertEqual(params["amm_config_address"], CONFIG)
        self.assertEqual(params["token_in_amount"], "1.25")
        self.assertEqual(session.calls[0]["timeout"], 9)


if __name__ == "__main__":
    unittest.main()
