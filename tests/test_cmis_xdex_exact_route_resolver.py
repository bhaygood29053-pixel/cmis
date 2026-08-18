import struct
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from liquidity_scout.providers.x1.pool_state_fingerprint import decode_base58_pubkey
from liquidity_scout.providers.x1.xdex_execution_fee_evidence import (
    AMM_CONFIG,
    POOL,
    X1_PROGRAM,
    XENCAT_MINT,
    XNT_MINT,
)
from liquidity_scout.services.xdex_route_resolver import (
    PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS,
    resolve_xdex_exact_route_evidence,
)


VAULT_0 = "11111111111111111111111111111111"
VAULT_1 = "SysvarC1ock11111111111111111111111111111111"
AUTHORITY = "SysvarRent111111111111111111111111111111111"
DECIMALS_0 = 6
DECIMALS_1 = 9
FEE_DENOMINATOR = 1_000_000


def _put_pubkey(data, offset, value):
    data[offset : offset + 32] = decode_base58_pubkey(value)


def _put_u64(data, offset, value):
    struct.pack_into("<Q", data, offset, value)


def _pool_data(*, amm_config=AMM_CONFIG, mint_0=XENCAT_MINT, mint_1=XNT_MINT):
    data = bytearray(637)
    _put_pubkey(data, 8, amm_config)
    _put_pubkey(data, 72, VAULT_0)
    _put_pubkey(data, 104, VAULT_1)
    _put_pubkey(data, 168, mint_0)
    _put_pubkey(data, 200, mint_1)
    data[331] = DECIMALS_0
    data[332] = DECIMALS_1
    _put_u64(data, 341, 100)
    _put_u64(data, 349, 200)
    _put_u64(data, 357, 10)
    _put_u64(data, 365, 20)
    _put_u64(data, 397, 0)
    _put_u64(data, 405, 0)
    return bytes(data)


def _config_data(*, trade_fee_rate=2800):
    data = bytearray(116)
    _put_u64(data, 12, trade_fee_rate)
    _put_u64(data, 20, 250000)
    _put_u64(data, 28, 50000)
    _put_u64(data, 108, 0)
    return bytes(data)


def _account_state(account, data, *, owner=X1_PROGRAM, integrity=True):
    return {
        "account": account,
        "account_exists": True,
        "response_integrity_verified": integrity,
        "owner": owner,
        "data": data,
    }


def _token_account(account, mint, decimals, raw_amount, *, identity=True, authority=AUTHORITY):
    return {
        "account": account,
        "account_exists": True,
        "identity_verified": identity,
        "mint": mint,
        "decimals": decimals,
        "raw_amount": str(raw_amount),
        "token_authority": authority,
    }


def _ceil_fee(amount, rate):
    return (amount * rate + FEE_DENOMINATOR - 1) // FEE_DENOMINATOR if rate else 0


def _impact(raw_input, reserve_in, fee_rate=2800):
    net = raw_input - _ceil_fee(raw_input, fee_rate)
    return Decimal(net) / Decimal(reserve_in + net) * Decimal(100)


def _execution_fee_observation():
    return {
        "chain": "x1",
        "program": X1_PROGRAM,
        "pool": POOL,
        "amm_config": AMM_CONFIG,
        "asset_a_mint": XENCAT_MINT,
        "asset_b_mint": XNT_MINT,
        "configured_fee_ppm": 2800,
        "supported_candidate_ppm": 2800,
        "rejected_candidate_ppm": 3000,
        "swap_count": 23,
        "seed_swap_count": 2,
        "holdout_swap_count": 21,
        "first_slot": 66617613,
        "last_slot": 72301970,
        "gross_vault_balances_observed": True,
        "state_contiguous": True,
        "both_directions_observed": True,
        "opposite_direction_seed_verified": True,
        "holdout_validation_performed": True,
        "fee_accounting_model_corroborated": True,
        "initial_fee_counters_inferred": True,
        "initial_fee_counters_observed": False,
        "supported_max_abs_error_raw": 406,
        "supported_sum_abs_error_raw": 1115,
        "rejected_max_abs_error_raw": 1557603301,
        "rejected_sum_abs_error_raw": 2513561183,
        "quote_baseline_ppm": 3000,
        "quote_baseline_verified": True,
    }


class XDEXExactRouteResolverTests(unittest.TestCase):
    def setUp(self):
        self.route = {
            "token_in_mint": XENCAT_MINT,
            "token_out_mint": XNT_MINT,
            "pool": POOL,
            "amm_config": AMM_CONFIG,
        }
        self.pool_data = _pool_data()
        self.config_data = _config_data()
        self.vault0_raw = 1_000_000_000
        self.vault1_raw = 2_000_000_000_000
        self.quote_calls = []

    def pool_fetcher(self, account):
        if account == POOL:
            return _account_state(account, self.pool_data)
        if account == AMM_CONFIG:
            return _account_state(account, self.config_data)
        raise AssertionError(f"unexpected account fetch: {account}")

    def token_fetcher(self, account):
        if account == VAULT_0:
            return _token_account(account, XENCAT_MINT, DECIMALS_0, self.vault0_raw)
        if account == VAULT_1:
            return _token_account(account, XNT_MINT, DECIMALS_1, self.vault1_raw)
        raise AssertionError(f"unexpected token-account fetch: {account}")

    def quote_fetcher(self, token_in, token_out, amount, **kwargs):
        self.quote_calls.append((token_in, token_out, amount, kwargs))
        reserve_in = self.vault0_raw - 100 - 10
        raw_input = 1_000_000
        impact = _impact(raw_input, reserve_in)
        return {
            "inputMint": token_in,
            "outputMint": token_out,
            "amm_config_address": AMM_CONFIG,
            "priceImpactPct": str(impact),
            # Deliberately nonsensical. The resolver must not use outputAmount
            # as a fee/fill/slippage/execution-quality fact.
            "outputAmount": "999999999999999999999999999",
        }

    def resolve(self, **overrides):
        kwargs = {
            "route": self.route,
            "token_in_amount": "1",
            "pool_state_fetcher": self.pool_fetcher,
            "token_account_fetcher": self.token_fetcher,
            "quote_fetcher": self.quote_fetcher,
            "now_fn": lambda: datetime(2026, 8, 18, 22, 0, 0, tzinfo=timezone.utc),
        }
        kwargs.update(overrides)
        return resolve_xdex_exact_route_evidence(**kwargs)

    def test_exact_route_emits_only_verified_price_impact_by_default(self):
        result = self.resolve()

        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["source"], "cmis_xdex_route_resolver")
        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["route"], self.route)
        self.assertEqual(result["observed_at"], "2026-08-18T22:00:00Z")
        self.assertEqual(set(result["capabilities"]), {"price_impact"})
        price_impact = result["capabilities"]["price_impact"]
        self.assertEqual(price_impact["status"], "verified")
        self.assertEqual(price_impact["semantic"], "route_price_impact_percent")
        self.assertEqual(price_impact["unit"], "percent")
        self.assertEqual(
            set(price_impact["proof_basis"]),
            {
                "verified_direct_cp_route",
                "verified_pool_reserves",
                "verified_price_impact_semantics",
            },
        )
        self.assertNotIn("slippage", result["capabilities"])
        self.assertNotIn("fees", result["capabilities"])
        self.assertEqual(len(self.quote_calls), 1)
        _, _, amount, kwargs = self.quote_calls[0]
        self.assertEqual(amount, "1")
        self.assertTrue(kwargs["is_exact_amount_in"])
        self.assertEqual(kwargs["slippage"], Decimal("0"))
        self.assertEqual(kwargs["amm_config_address"], AMM_CONFIG)

    def test_bounded_fee_is_emitted_only_with_accepted_historical_evidence(self):
        result = self.resolve(execution_fee_observation=_execution_fee_observation())
        fees = result["capabilities"]["fees"]
        self.assertEqual(fees["status"], "verified")
        self.assertEqual(fees["semantic"], "route_execution_fee_estimate")
        self.assertEqual(fees["unit"], "structured")
        self.assertEqual(
            fees["value"],
            {
                "amm_trade_fee_rate_percent": 0.28,
                "bounded_historical_execution_model_fee_percent": 0.28,
            },
        )
        self.assertNotIn("quote_effective_curve_deduction_percent", fees["value"])

    def test_pool_program_owner_mismatch_fails_closed(self):
        def fetcher(account):
            if account == POOL:
                return _account_state(account, self.pool_data, owner="other-program")
            return self.pool_fetcher(account)

        with self.assertRaisesRegex(ValueError, "accepted XDEX program"):
            self.resolve(pool_state_fetcher=fetcher)

    def test_pool_layout_length_mismatch_fails_closed(self):
        def fetcher(account):
            if account == POOL:
                return _account_state(account, self.pool_data[:-1])
            return self.pool_fetcher(account)

        with self.assertRaisesRegex(ValueError, "data length must be 637"):
            self.resolve(pool_state_fetcher=fetcher)

    def test_pool_config_mismatch_fails_closed(self):
        self.pool_data = _pool_data(amm_config=POOL)
        with self.assertRaisesRegex(ValueError, "AMM config"):
            self.resolve()

    def test_pool_mint_pair_mismatch_fails_closed(self):
        self.pool_data = _pool_data(mint_1=AMM_CONFIG)
        with self.assertRaisesRegex(ValueError, "mint pair"):
            self.resolve()

    def test_vault_identity_must_be_verified(self):
        def token_fetcher(account):
            if account == VAULT_0:
                return _token_account(
                    account, XENCAT_MINT, DECIMALS_0, self.vault0_raw, identity=False
                )
            return self.token_fetcher(account)

        with self.assertRaisesRegex(ValueError, "identity is not verified"):
            self.resolve(token_account_fetcher=token_fetcher)

    def test_vault_mint_must_match_pool_state(self):
        def token_fetcher(account):
            if account == VAULT_0:
                return _token_account(account, XNT_MINT, DECIMALS_0, self.vault0_raw)
            return self.token_fetcher(account)

        with self.assertRaisesRegex(ValueError, "vault mint identity mismatch"):
            self.resolve(token_account_fetcher=token_fetcher)

    def test_vault_decimals_must_match_pool_state(self):
        def token_fetcher(account):
            if account == VAULT_0:
                return _token_account(account, XENCAT_MINT, 9, self.vault0_raw)
            return self.token_fetcher(account)

        with self.assertRaisesRegex(ValueError, "vault decimals mismatch"):
            self.resolve(token_account_fetcher=token_fetcher)

    def test_vaults_must_share_verified_authority(self):
        def token_fetcher(account):
            if account == VAULT_1:
                return _token_account(
                    account,
                    XNT_MINT,
                    DECIMALS_1,
                    self.vault1_raw,
                    authority=X1_PROGRAM,
                )
            return self.token_fetcher(account)

        with self.assertRaisesRegex(ValueError, "same verified token authority"):
            self.resolve(token_account_fetcher=token_fetcher)

    def test_fee_counters_cannot_make_active_reserve_nonpositive(self):
        data = bytearray(self.pool_data)
        _put_u64(data, 341, self.vault0_raw)
        self.pool_data = bytes(data)
        with self.assertRaisesRegex(ValueError, "active reserves must both be positive"):
            self.resolve()

    def test_input_amount_must_be_exact_in_raw_units(self):
        with self.assertRaisesRegex(ValueError, "exactly representable"):
            self.resolve(token_in_amount="0.0000001")

    def test_quote_input_identity_mismatch_fails_closed(self):
        def quote_fetcher(token_in, token_out, amount, **kwargs):
            result = self.quote_fetcher(token_in, token_out, amount, **kwargs)
            result["inputMint"] = XNT_MINT
            return result

        with self.assertRaisesRegex(ValueError, "inputMint"):
            self.resolve(quote_fetcher=quote_fetcher)

    def test_quote_output_identity_mismatch_fails_closed(self):
        def quote_fetcher(token_in, token_out, amount, **kwargs):
            result = self.quote_fetcher(token_in, token_out, amount, **kwargs)
            result["outputMint"] = XENCAT_MINT
            return result

        with self.assertRaisesRegex(ValueError, "outputMint"):
            self.resolve(quote_fetcher=quote_fetcher)

    def test_quote_config_identity_mismatch_fails_closed(self):
        def quote_fetcher(token_in, token_out, amount, **kwargs):
            result = self.quote_fetcher(token_in, token_out, amount, **kwargs)
            result["amm_config_address"] = POOL
            return result

        with self.assertRaisesRegex(ValueError, "quote AMM config"):
            self.resolve(quote_fetcher=quote_fetcher)

    def test_malformed_price_impact_fails_closed(self):
        def quote_fetcher(token_in, token_out, amount, **kwargs):
            result = self.quote_fetcher(token_in, token_out, amount, **kwargs)
            result["priceImpactPct"] = "not-a-number"
            return result

        with self.assertRaisesRegex(ValueError, "priceImpactPct"):
            self.resolve(quote_fetcher=quote_fetcher)

    def test_price_impact_outside_tolerance_fails_closed(self):
        def quote_fetcher(token_in, token_out, amount, **kwargs):
            result = self.quote_fetcher(token_in, token_out, amount, **kwargs)
            result["priceImpactPct"] = str(
                Decimal(str(result["priceImpactPct"]))
                + PRICE_IMPACT_TOLERANCE_PERCENTAGE_POINTS
                + Decimal("0.000001")
            )
            return result

        with self.assertRaisesRegex(ValueError, "reconstruction tolerance"):
            self.resolve(quote_fetcher=quote_fetcher)

    def test_unverified_historical_fee_evidence_is_rejected_when_explicitly_supplied(self):
        observation = _execution_fee_observation()
        observation["state_contiguous"] = False
        with self.assertRaisesRegex(ValueError, "not strongly corroborated"):
            self.resolve(execution_fee_observation=observation)

    def test_current_config_fee_must_match_bounded_historical_fee(self):
        self.config_data = _config_data(trade_fee_rate=3000)
        # The independently reconstructed quote impact is adjusted so the only
        # failure under test is the bounded historical/current-config mismatch.
        def quote_fetcher(token_in, token_out, amount, **kwargs):
            reserve_in = self.vault0_raw - 100 - 10
            raw_input = 1_000_000
            return {
                "inputMint": token_in,
                "outputMint": token_out,
                "amm_config_address": AMM_CONFIG,
                "priceImpactPct": str(_impact(raw_input, reserve_in, 3000)),
                "outputAmount": "1",
            }

        with self.assertRaisesRegex(ValueError, "does not match current verified config fee"):
            self.resolve(
                quote_fetcher=quote_fetcher,
                execution_fee_observation=_execution_fee_observation(),
            )

    def test_naive_observation_clock_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            self.resolve(now_fn=lambda: datetime(2026, 8, 18, 22, 0, 0))

    def test_route_rejects_extra_fields_instead_of_ignoring_them(self):
        route = dict(self.route)
        route["router"] = "unverified"
        with self.assertRaisesRegex(ValueError, "route fields mismatch"):
            self.resolve(route=route)


if __name__ == "__main__":
    unittest.main()
