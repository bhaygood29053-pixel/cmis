import struct
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from liquidity_scout.providers.x1.pool_state_fingerprint import decode_base58_pubkey
from liquidity_scout.services.pre_trade_route_evidence import evaluate_route_evidence
from liquidity_scout.services.xdex_exact_route_evidence import (
    PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS,
    XDEXExactRouteEvidenceError,
    resolve_xdex_exact_route_evidence_with_audit,
)


PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
POOL = "6oTV8xMRP6w592xK79Untuq8vqCttFDHZnw3bN5Suxry"
CONFIG = "2eFPWosizV6nSAGeSvi5tRgXLoqhjnSesra23ALA248c"
MINT_0 = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
MINT_1 = "So11111111111111111111111111111111111111112"
VAULT_0 = "9ojBC34QUrubQASb1ktqkNn3kdFiUnqaBnLLgSeWbRm7"
VAULT_1 = "9Dpjw2pB5kXJr6ZTHiqzEMfJPic3om9jgNacnwpLCoaU"
AUTHORITY = POOL
TRADE_FEE_RATE = 2_800
FEE_DENOM = 1_000_000
NOW = datetime(2026, 8, 18, 21, 0, tzinfo=timezone.utc)

ROUTE = {
    "token_in_mint": MINT_1,
    "token_out_mint": MINT_0,
    "pool": POOL,
    "amm_config": CONFIG,
}


def _put_pubkey(data, offset, value):
    raw = decode_base58_pubkey(value)
    data[offset : offset + 32] = raw


def _pool_state(*, config=CONFIG, owner=PROGRAM, integrity=True):
    data = bytearray(637)
    _put_pubkey(data, 8, config)
    _put_pubkey(data, 72, VAULT_0)
    _put_pubkey(data, 104, VAULT_1)
    _put_pubkey(data, 168, MINT_0)
    _put_pubkey(data, 200, MINT_1)
    data[331] = 6
    data[332] = 9
    for offset, value in (
        (341, 100),
        (349, 100),
        (357, 50),
        (365, 50),
        (397, 25),
        (405, 25),
    ):
        struct.pack_into("<Q", data, offset, value)
    return {
        "owner": owner,
        "data": bytes(data),
        "response_integrity_verified": integrity,
    }


def _config_state(*, fee=TRADE_FEE_RATE, owner=PROGRAM, integrity=True):
    data = bytearray(116)
    struct.pack_into("<Q", data, 12, fee)
    return {
        "owner": owner,
        "data": bytes(data),
        "response_integrity_verified": integrity,
    }


def _vaults(*, wrong_mint=False, identity=True):
    records = {
        VAULT_0: {
            "account": VAULT_0,
            "identity_verified": identity,
            "mint": MINT_1 if wrong_mint else MINT_0,
            "token_authority": AUTHORITY,
            "raw_amount": "2000000000",
            "decimals": 6,
        },
        VAULT_1: {
            "account": VAULT_1,
            "identity_verified": identity,
            "mint": MINT_1,
            "token_authority": AUTHORITY,
            "raw_amount": "5000000000",
            "decimals": 9,
        },
    }
    return lambda account: records[account]


def _expected_impact(amount=Decimal("1"), fee=TRADE_FEE_RATE):
    raw_input = int(amount * Decimal(10**9))
    active_reserve = 5_000_000_000 - 100 - 50 - 25
    trade_fee = (raw_input * fee + FEE_DENOM - 1) // FEE_DENOM
    less_fees = raw_input - trade_fee
    return Decimal(less_fees) / Decimal(active_reserve + less_fees) * Decimal(100)


def _quote(*, impact=None, input_mint=MINT_1, output_mint=MINT_0, config=CONFIG):
    return {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amm_config_address": config,
        "priceImpactPct": str(_expected_impact() if impact is None else impact),
        "outputAmount": "123.456",
    }


class XDEXExactRouteEvidenceTests(unittest.TestCase):
    def _resolve(self, **overrides):
        kwargs = {
            "route": ROUTE,
            "token_in_amount": "1",
            "pool_state_fetcher": lambda account: _pool_state(),
            "config_state_fetcher": lambda account: _config_state(),
            "token_account_fetcher": _vaults(),
            "quote_fetcher": lambda token_in, token_out, amount, config: _quote(),
            "clock": lambda: NOW,
        }
        kwargs.update(overrides)
        return resolve_xdex_exact_route_evidence_with_audit(**kwargs)

    def test_exact_verified_route_emits_only_price_impact(self):
        result = self._resolve()
        evidence = result["route_evidence"]
        audit = result["audit"]

        self.assertEqual(evidence["source"], "cmis_xdex_route_resolver")
        self.assertEqual(evidence["chain"], "x1")
        self.assertEqual(evidence["route"], ROUTE)
        self.assertEqual(set(evidence["capabilities"]), {"price_impact"})
        capability = evidence["capabilities"]["price_impact"]
        self.assertEqual(capability["status"], "verified")
        self.assertEqual(capability["semantic"], "route_price_impact_percent")
        self.assertEqual(capability["unit"], "percent")
        self.assertEqual(
            set(capability["proof_basis"]),
            {
                "verified_direct_cp_route",
                "verified_pool_reserves",
                "verified_price_impact_semantics",
            },
        )
        self.assertTrue(audit["price_impact_semantics_verified"])
        self.assertFalse(audit["fees_verified"])
        self.assertFalse(audit["expected_execution_slippage_verified"])

        accepted = evaluate_route_evidence(
            evidence,
            target_chain="x1",
            trade_route=ROUTE,
            evaluated_at="2026-08-18T21:00:10Z",
            max_age_seconds=60,
        )
        self.assertEqual(set(accepted["overrides"]), {"price_impact"})

    def test_quote_price_impact_mismatch_fails_closed(self):
        result = self._resolve(
            quote_fetcher=lambda *args: _quote(
                impact=_expected_impact() + PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS + Decimal("0.001")
            )
        )
        self.assertEqual(result["route_evidence"]["capabilities"], {})
        self.assertEqual(
            result["audit"]["failure_reason"],
            "xdex_quote_price_impact_not_independently_reproduced",
        )

    def test_quote_identity_mismatch_fails_closed(self):
        result = self._resolve(quote_fetcher=lambda *args: _quote(config=POOL))
        self.assertEqual(result["route_evidence"]["capabilities"], {})
        self.assertEqual(result["audit"]["failure_reason"], "xdex_quote_amm_config_mismatch")

    def test_pool_config_mismatch_fails_before_quote(self):
        called = []
        result = self._resolve(
            pool_state_fetcher=lambda account: _pool_state(config=POOL),
            quote_fetcher=lambda *args: called.append(args),
        )
        self.assertEqual(called, [])
        self.assertEqual(result["route_evidence"]["capabilities"], {})
        self.assertEqual(result["audit"]["failure_reason"], "pool_amm_config_mismatch")

    def test_unrecognized_pool_owner_fails_closed(self):
        result = self._resolve(
            pool_state_fetcher=lambda account: _pool_state(owner=CONFIG),
        )
        self.assertEqual(result["route_evidence"]["capabilities"], {})
        self.assertEqual(result["audit"]["failure_reason"], "pool_program_owner_unrecognized")

    def test_unverified_vault_identity_fails_closed(self):
        result = self._resolve(token_account_fetcher=_vaults(identity=False))
        self.assertEqual(result["route_evidence"]["capabilities"], {})
        self.assertEqual(result["audit"]["failure_reason"], "pool_vault_identity_unverified")

    def test_wrong_vault_mint_fails_closed(self):
        result = self._resolve(token_account_fetcher=_vaults(wrong_mint=True))
        self.assertEqual(result["route_evidence"]["capabilities"], {})
        self.assertEqual(result["audit"]["failure_reason"], "pool_vault_mint_mismatch")

    def test_transport_exception_is_sanitized(self):
        result = self._resolve(
            quote_fetcher=lambda *args: (_ for _ in ()).throw(RuntimeError("secret provider detail"))
        )
        self.assertEqual(result["route_evidence"]["capabilities"], {})
        self.assertEqual(
            result["audit"]["failure_reason"],
            "read_only_route_evidence_collection_failed",
        )
        self.assertNotIn("secret provider detail", str(result))

    def test_invalid_internal_route_rejected_before_providers(self):
        with self.assertRaisesRegex(XDEXExactRouteEvidenceError, "route must contain exactly"):
            self._resolve(route={"token_in_mint": MINT_1})

    def test_nonrepresentable_input_rejected(self):
        with self.assertRaisesRegex(XDEXExactRouteEvidenceError, "exactly representable"):
            self._resolve(token_in_amount="0.0000000001")

    def test_default_quote_transport_forces_zero_slippage_and_exact_config(self):
        class Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"success": True, "data": _quote()}

        calls = []

        def fake_get(url, *, params, timeout, headers):
            calls.append((url, params, timeout, headers))
            return Response()

        with patch("liquidity_scout.services.xdex_exact_route_evidence.requests.get", fake_get):
            result = resolve_xdex_exact_route_evidence_with_audit(
                route=ROUTE,
                token_in_amount="1",
                pool_state_fetcher=lambda account: _pool_state(),
                config_state_fetcher=lambda account: _config_state(),
                token_account_fetcher=_vaults(),
                clock=lambda: NOW,
            )

        self.assertEqual(set(result["route_evidence"]["capabilities"]), {"price_impact"})
        self.assertEqual(len(calls), 1)
        _, params, _, _ = calls[0]
        self.assertEqual(params["network"], "X1 Mainnet")
        self.assertEqual(params["is_exact_amount_in"], "true")
        self.assertEqual(params["slippage"], "0")
        self.assertEqual(params["amm_config_address"], CONFIG)
        self.assertEqual(params["token_in"], MINT_1)
        self.assertEqual(params["token_out"], MINT_0)


if __name__ == "__main__":
    unittest.main()
