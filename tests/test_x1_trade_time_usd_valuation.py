import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.trade_time_usd_valuation import (
    CONTRACT,
    TradeTimeUsdValuationError,
    capture_kraken_usdc_usd_fact_price,
    evaluate_historical_usdcx_parity,
    resolve_xnt_quote_usd_value,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    USDC_X_MINT,
    WXNT_MINT,
)
from liquidity_scout.providers.x1.usdcx_destination_parity import (
    SOLANA_USDC_MINT,
    WARP_USDC_ROUTE_ID,
    X1_USDC_X_MINT,
)
from liquidity_scout.providers.x1.warp_message_interval_retention import (
    CONTRACT as INTERVAL_RETENTION_CONTRACT,
)
from liquidity_scout.providers.x1.warp_message_lifecycle_retention import (
    CONTRACT as LIFECYCLE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    CONTRACT as TRANSFER_CONTRACT,
)


FACT_TIME = 1400


def _backing():
    return {
        "route_id": WARP_USDC_ROUTE_ID,
        "decimals_verified": True,
        "observation_time_compatible": True,
        "source": {
            "chain": "solana",
            "mint": SOLANA_USDC_MINT,
            "identity_verified": True,
            "decimals": 6,
            "amount_raw": 1080,
            "observed_at": 2000,
        },
        "destination": {
            "chain": "x1",
            "mint": X1_USDC_X_MINT,
            "identity_verified": True,
            "decimals": 6,
            "raw_supply": 1070,
            "observed_at": 2001,
        },
    }


def _events():
    return {
        "contract": TRANSFER_CONTRACT,
        "route_id": WARP_USDC_ROUTE_ID,
        "pairing_semantics_verified": True,
        "settled_event_semantics_verified": True,
        "flow_event_normalization_authorized": True,
        "unresolved_counts": {},
        "events": [
            {
                "route_id": WARP_USDC_ROUTE_ID,
                "direction": "inflow",
                "amount_raw": 100,
                "decimals": 6,
                "source_timestamp": 1500,
                "settled_at": 1505,
                "lifecycle_state": "settled",
                "settlement_verified": True,
                "pairing_verified": True,
            },
            {
                "route_id": WARP_USDC_ROUTE_ID,
                "direction": "outflow",
                "amount_raw": 20,
                "decimals": 6,
                "source_timestamp": 1600,
                "settled_at": 1608,
                "lifecycle_state": "settled",
                "settlement_verified": True,
                "pairing_verified": True,
            },
        ],
    }


def _lifecycle():
    return {
        "contract": LIFECYCLE_CONTRACT,
        "requested_start": 1000,
        "as_of": 2100,
        "historical_retention_complete_verified": True,
        "requested_window_coverage_verified": True,
        "coverage_complete_verified": True,
        "missing_history_zero_authorized": True,
    }


def _interval_retention():
    return {
        "contract": INTERVAL_RETENTION_CONTRACT,
        "requested_start": 1300,
        "as_of": 2100,
        "interval_retention_complete_verified": True,
        "requested_window_coverage_verified": True,
        "coverage_complete_verified": True,
        "missing_history_zero_authorized": True,
        "sixty_day_bridge_flow_retention_promoted": False,
    }


class _Response:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._body


class TradeTimeUsdValuationTests(unittest.TestCase):
    def test_historical_usdcx_parity_reverses_each_chain_action_time(self):
        result = evaluate_historical_usdcx_parity(
            fact_time=FACT_TIME,
            current_backing_evidence=_backing(),
            normalized_events=_events(),
            lifecycle_retention=_lifecycle(),
        )
        self.assertEqual(result["contract"], CONTRACT)
        self.assertEqual(result["historical_source_reserve_raw"], 1000)
        self.assertEqual(result["historical_destination_supply_raw"], 990)
        self.assertEqual(result["historical_reserve_surplus_raw"], 10)
        self.assertEqual(result["source_actions_reversed"], 2)
        self.assertEqual(result["destination_actions_reversed"], 2)
        self.assertTrue(result["historical_usdcx_value_equivalence_verified"])
        self.assertTrue(result["historical_value_equivalence_verified"])
        self.assertFalse(result["stable_name_one_dollar_assumption_used"])
        self.assertFalse(result["execution_authorized"])


    def test_historical_usdcx_parity_accepts_bounded_interval_retention(self):
        result = evaluate_historical_usdcx_parity(
            fact_time=FACT_TIME,
            current_backing_evidence=_backing(),
            normalized_events=_events(),
            lifecycle_retention=_interval_retention(),
        )
        self.assertTrue(result["lifecycle_coverage_verified"])
        self.assertTrue(result["historical_usdcx_value_equivalence_verified"])

    def test_historical_usdcx_parity_rejects_short_interval_promoted_as_60_day(self):
        retention = _interval_retention()
        retention["sixty_day_bridge_flow_retention_promoted"] = True
        with self.assertRaisesRegex(
            TradeTimeUsdValuationError,
            "must not be promoted as the 60-day gate",
        ):
            evaluate_historical_usdcx_parity(
                fact_time=FACT_TIME,
                current_backing_evidence=_backing(),
                normalized_events=_events(),
                lifecycle_retention=retention,
            )

    def test_historical_usdcx_parity_fails_closed_on_unresolved_route_event(self):
        events = _events()
        events["unresolved_counts"] = {"missing_destination_incoming": 1}
        with self.assertRaisesRegex(
            TradeTimeUsdValuationError, "unresolved USDC route events"
        ):
            evaluate_historical_usdcx_parity(
                fact_time=FACT_TIME,
                current_backing_evidence=_backing(),
                normalized_events=events,
                lifecycle_retention=_lifecycle(),
            )

    def test_historical_usdcx_parity_fails_outside_accepted_retention(self):
        lifecycle = _lifecycle()
        lifecycle["requested_start"] = 1450
        with self.assertRaisesRegex(
            TradeTimeUsdValuationError, "outside accepted lifecycle coverage"
        ):
            evaluate_historical_usdcx_parity(
                fact_time=FACT_TIME,
                current_backing_evidence=_backing(),
                normalized_events=_events(),
                lifecycle_retention=lifecycle,
            )

    def test_historical_usdcx_parity_rejects_snapshot_after_lifecycle_as_of(self):
        lifecycle = _lifecycle()
        lifecycle["as_of"] = 1999
        with self.assertRaisesRegex(
            TradeTimeUsdValuationError, "current backing observations"
        ):
            evaluate_historical_usdcx_parity(
                fact_time=FACT_TIME,
                current_backing_evidence=_backing(),
                normalized_events=_events(),
                lifecycle_retention=lifecycle,
            )

    def test_kraken_fact_price_uses_last_exact_pair_trade_before_fact(self):
        def fake_get(url, **kwargs):
            self.assertIn("PostTrade", url)
            self.assertEqual(kwargs["params"]["symbol"], "USDC/USD")
            return _Response(
                {
                    "error": [],
                    "result": {
                        "trades": [
                            {
                                "trade_id": "before-2",
                                "price": "0.9998",
                                "quantity": "100",
                                "symbol": "USDC/USD",
                                "base_asset": "USDC",
                                "quote_asset": "USD",
                                "trade_ts": "1970-01-01T00:23:15Z",
                            },
                            {
                                "trade_id": "before-1",
                                "price": "1.0001",
                                "quantity": "50",
                                "symbol": "USDC/USD",
                                "base_asset": "USDC",
                                "quote_asset": "USD",
                                "trade_ts": "1970-01-01T00:23:19Z",
                            },
                            {
                                "trade_id": "after",
                                "price": "1.0002",
                                "quantity": "25",
                                "symbol": "USDC/USD",
                                "base_asset": "USDC",
                                "quote_asset": "USD",
                                "trade_ts": "1970-01-01T00:23:21Z",
                            },
                        ]
                    },
                }
            )

        result = capture_kraken_usdc_usd_fact_price(
            fact_time=FACT_TIME,
            max_age_seconds=120,
            get=fake_get,
        )
        self.assertEqual(result["trade_id"], "before-1")
        self.assertEqual(result["price_usd_per_usdc"], "1.0001")
        self.assertEqual(result["observation_age_seconds"], "1")
        self.assertTrue(result["exact_pair_identity_verified"])
        self.assertTrue(result["fact_time_verified"])
        self.assertTrue(result["last_observation_policy_verified"])
        self.assertFalse(result["stable_name_one_dollar_assumption_used"])

    def test_kraken_fact_price_rejects_wrong_unit_identity(self):
        def fake_get(_url, **_kwargs):
            return _Response(
                {
                    "error": [],
                    "result": {
                        "trades": [
                            {
                                "trade_id": "bad",
                                "price": "1",
                                "quantity": "1",
                                "symbol": "USDC/EUR",
                                "base_asset": "USDC",
                                "quote_asset": "EUR",
                                "trade_ts": "1970-01-01T00:23:19Z",
                            }
                        ]
                    },
                }
            )

        with self.assertRaisesRegex(
            TradeTimeUsdValuationError, "no exact Kraken USDC/USD trade"
        ):
            capture_kraken_usdc_usd_fact_price(
                fact_time=FACT_TIME,
                get=fake_get,
            )

    def test_composition_uses_decimal_fact_time_legs(self):
        reference = {
            "fact_time": FACT_TIME,
            "base_mint": WXNT_MINT,
            "quote_mint": USDC_X_MINT,
            "unit": "USDC.X_per_XNT",
            "usdcx_per_xnt": "0.3725",
            "fact_time_verified": True,
            "current_price_substitution_used": False,
            "provider_usd_price_used": False,
        }
        parity = {
            "fact_time": FACT_TIME,
            "route_id": WARP_USDC_ROUTE_ID,
            "historical_usdcx_value_equivalence_verified": True,
            "historical_value_equivalence_verified": True,
            "stable_name_one_dollar_assumption_used": False,
        }
        canonical = {
            "fact_time": FACT_TIME,
            "canonical_solana_usdc_mint": SOLANA_USDC_MINT,
            "unit": "USD_per_USDC",
            "price_usd_per_usdc": "0.9999",
            "exact_pair_identity_verified": True,
            "fact_time_verified": True,
            "stable_name_one_dollar_assumption_used": False,
        }
        result = resolve_xnt_quote_usd_value(
            fact_time=FACT_TIME,
            quote_mint=WXNT_MINT,
            quote_amount="6.404425898",
            reference_rate_evidence=reference,
            historical_usdcx_parity=parity,
            canonical_usdc_usd_evidence=canonical,
        )
        expected_price = Decimal("0.3725") * Decimal("0.9999")
        expected_value = Decimal("6.404425898") * expected_price
        self.assertTrue(result["historical_usd_value_verified"])
        self.assertTrue(result["fact_time_verified"])
        self.assertEqual(
            Decimal(result["historical_xnt_usd_price"]),
            expected_price,
        )
        self.assertEqual(Decimal(result["usd_value"]), expected_value)
        self.assertFalse(result["current_price_substitution_used"])
        self.assertFalse(result["provider_usd_price_used"])
        self.assertFalse(result["stable_name_one_dollar_assumption_used"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_composition_fails_closed_if_reference_uses_current_price(self):
        result = resolve_xnt_quote_usd_value(
            fact_time=FACT_TIME,
            quote_mint=WXNT_MINT,
            quote_amount="1",
            reference_rate_evidence={
                "fact_time": FACT_TIME,
                "base_mint": WXNT_MINT,
                "quote_mint": USDC_X_MINT,
                "unit": "USDC.X_per_XNT",
                "usdcx_per_xnt": "0.37",
                "fact_time_verified": True,
                "current_price_substitution_used": True,
                "provider_usd_price_used": False,
            },
            historical_usdcx_parity={
                "fact_time": FACT_TIME,
                "route_id": WARP_USDC_ROUTE_ID,
                "historical_usdcx_value_equivalence_verified": True,
                "historical_value_equivalence_verified": True,
                "stable_name_one_dollar_assumption_used": False,
            },
            canonical_usdc_usd_evidence={
                "fact_time": FACT_TIME,
                "canonical_solana_usdc_mint": SOLANA_USDC_MINT,
                "unit": "USD_per_USDC",
                "price_usd_per_usdc": "1",
                "exact_pair_identity_verified": True,
                "fact_time_verified": True,
                "stable_name_one_dollar_assumption_used": False,
            },
        )
        self.assertFalse(result["historical_usd_value_verified"])
        self.assertFalse(result["fact_time_verified"])
        self.assertFalse(result["reference_rate_verified"])

    def test_unsupported_quote_mint_stays_unvalued(self):
        result = resolve_xnt_quote_usd_value(
            fact_time=FACT_TIME,
            quote_mint="not-xnt",
            quote_amount="1",
            reference_rate_evidence={},
            historical_usdcx_parity={},
            canonical_usdc_usd_evidence={},
        )
        self.assertFalse(result["historical_usd_value_verified"])
        self.assertEqual(result["reason"], "unsupported_historical_quote_mint")


if __name__ == "__main__":
    unittest.main()
