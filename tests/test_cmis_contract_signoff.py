import unittest
from types import SimpleNamespace

from liquidity_scout.services import (
    BLOCK,
    OK,
    PARTIAL,
    PASS,
    WARN,
    build_historical_compare_response,
    build_market_report_response,
    build_risk_check_response,
    build_tokenomics_response,
)


MINT = "ReferenceMint"
CANONICAL_ENVELOPE_KEYS = [
    "service",
    "chain",
    "status",
    "asset",
    "data",
    "risk",
    "confidence",
    "sources",
    "observed_at",
    "warnings",
    "errors",
]


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def pool(
    address,
    base,
    quote,
    *,
    liquidity=None,
    volume24h=None,
    txns24h=None,
    holders=None,
    price=None,
):
    row = {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "createdAt": "2026-01-01T00:00:00Z",
    }
    for key, value in {
        "liquidity": liquidity,
        "volume24h": volume24h,
        "txns24h": txns24h,
        "holders": holders,
        "priceUsd": price,
    }.items():
        if value is not None:
            row[key] = value
    return row


def supply_record():
    return {
        "raw_supply": "42500000",
        "decimals": 6,
        "total_supply": "42.5",
        "supply_verified": True,
        "source": "X1 RPC getTokenSupply",
    }


def mint_record():
    return {
        "mint_authority": None,
        "mint_authority_verified": True,
        "freeze_authority": None,
        "freeze_authority_verified": True,
        "decimals": 6,
        "source": "X1 RPC getAccountInfo(jsonParsed)",
    }


def activity_report():
    return {
        "mint": MINT,
        "decimals": 6,
        "mint_events_observed": 1,
        "burn_events_observed": 1,
        "minted_raw_observed": "1000000",
        "burned_raw_observed": "500000",
        "minted_tokens_observed": "1",
        "burned_tokens_observed": "0.5",
        "coverage": {
            "signatures_scanned": 2,
            "transactions_retrieved": 2,
            "rpc_errors": 0,
            "selection_complete": True,
            "history_exhausted": False,
            "max_signatures": 2,
        },
        "coverage_scope": "bounded",
        "coverage_verified": True,
        "activity_verified": True,
        "lifetime_coverage_verified": False,
        "lifetime_coverage_reason": "bounded_window_only",
        "net_issuance_raw": "500000",
        "net_issuance_tokens": "0.5",
        "scan_id": "scan-1",
        "source": "X1 RPC parsed token instructions",
        "storage": "sqlite",
    }


class FakeHistory:
    def __init__(self, old_value=100.0, old_timestamp=1000):
        self.old_value = old_value
        self.old_timestamp = old_timestamp
        self.recorded = []

    def parse_historical_comparison(self, _question):
        return {
            "metric": "price",
            "period": "24h",
            "period_seconds": 86400,
            "direction": None,
            "threshold": None,
            "comparator": None,
        }

    def record_snapshot(self, **kwargs):
        self.recorded.append(kwargs)

    def historical_value(self, _mint, _metric, _period_seconds):
        return {"timestamp": self.old_timestamp, "value": self.old_value}

    def percent_change(self, old_value, new_value):
        if old_value == 0:
            return None
        return ((new_value - old_value) / old_value) * 100.0

    def threshold_result(self, change, direction, threshold):
        if direction == "down":
            return change <= -abs(threshold)
        if direction == "up":
            return change >= abs(threshold)
        return abs(change) >= abs(threshold)


class CMISCrossServiceContractSignoffTests(unittest.TestCase):
    def setUp(self):
        self.asset = token("REF", MINT, "Reference Token")
        self.usdc = token("USDC", "MintUSDC", "USD Coin")
        self.xnt = token("XNT", "MintXNT", "Wrapped XNT")

    def _market_response(
        self,
        *,
        second_volume=500.0,
        primary_liquidity=5000.0,
        secondary_liquidity=1000.0,
    ):
        primary = pool(
            "P1",
            self.asset,
            self.usdc,
            liquidity=primary_liquidity,
            volume24h=100.0,
            txns24h=10,
            holders=1000,
            price=105.0,
        )
        secondary = pool(
            "P2",
            self.asset,
            self.xnt,
            liquidity=secondary_liquidity,
            volume24h=second_volume,
            txns24h=20,
            holders=1000,
            price=104.0,
        )
        if second_volume is None:
            secondary.pop("volume24h", None)
        return build_market_report_response(
            "REF",
            [
                (primary, "base", self.asset, 90),
                (secondary, "base", self.asset, 90),
            ],
            SimpleNamespace(xnt_price_usd=None, last_refresh=2000.0),
            chain="x1",
        )

    def _tokenomics_response(self, *, include_activity=True):
        return build_tokenomics_response(
            MINT,
            symbol="REF",
            name="Reference Token",
            chain="x1",
            get_token_supply=lambda mint, **kwargs: supply_record(),
            get_mint_info=lambda mint, **kwargs: mint_record(),
            activity_report=activity_report() if include_activity else None,
        )

    def _historical_response(self, market_response):
        market = market_response["data"]
        snapshot = {
            "symbol": market.get("symbol"),
            "token_address": market.get("mint"),
            "_market_report": market,
        }
        return build_historical_compare_response(
            "How has REF price changed in 24h?",
            snapshot,
            history_backend=FakeHistory(old_value=100.0, old_timestamp=1000),
            chain="x1",
        )

    def test_complete_four_service_pipeline_uses_one_envelope_and_identity(self):
        market = self._market_response()
        tokenomics = self._tokenomics_response()
        historical = self._historical_response(market)
        risk = build_risk_check_response(
            market["data"],
            tokenomics["data"],
            historical["data"],
            chain="x1",
        )

        responses = [market, tokenomics, historical, risk]
        self.assertEqual(
            [response["service"] for response in responses],
            ["market_report", "tokenomics", "historical_compare", "risk_check"],
        )
        for response in responses:
            self.assertEqual(list(response), CANONICAL_ENVELOPE_KEYS)
            self.assertEqual(response["chain"], "x1")
            self.assertEqual(response["status"], OK)
            self.assertEqual(response["asset"]["mint"], MINT)
            self.assertIsInstance(response["confidence"], dict)
            self.assertIsInstance(response["sources"], list)
            self.assertIsInstance(response["warnings"], list)
            self.assertIsInstance(response["errors"], list)

        self.assertEqual(market["data"]["lp_count"], 2)
        self.assertEqual(market["data"]["liquidity_usd"], 6000.0)
        self.assertEqual(market["data"]["volume_24h_usd"], 600.0)
        self.assertEqual(historical["data"]["change_pct"], 5.0)
        self.assertEqual(risk["risk"]["recommendation"], PASS)

    def test_cross_service_sources_remain_traceable_in_final_risk_response(self):
        market = self._market_response()
        tokenomics = self._tokenomics_response()
        historical = self._historical_response(market)
        risk = build_risk_check_response(
            market["data"],
            tokenomics["data"],
            historical["data"],
            chain="x1",
        )

        sources = risk["sources"]
        self.assertIn(
            {
                "source": "X1.Ninja/XDEX",
                "role": "market_report",
                "observed_at": 2000.0,
            },
            sources,
        )
        self.assertIn(
            {
                "source": "X1 RPC getTokenSupply",
                "role": "tokenomics.current_supply",
            },
            sources,
        )
        self.assertIn(
            {
                "source": "X1 RPC parsed token instructions",
                "role": "tokenomics.token_activity",
            },
            sources,
        )
        self.assertIn(
            {
                "source": "historical_db",
                "role": "historical_compare",
                "observed_at": 2000.0,
            },
            sources,
        )
        self.assertIn(
            {"source": "risk_engine", "role": "risk_check"},
            sources,
        )

    def test_partial_upstream_verification_stays_partial_and_warns_downstream(self):
        market = self._market_response(second_volume=None)
        tokenomics = self._tokenomics_response(include_activity=False)
        historical = self._historical_response(market)
        risk = build_risk_check_response(
            market["data"],
            tokenomics["data"],
            historical["data"],
            chain="x1",
        )

        self.assertEqual(market["status"], PARTIAL)
        self.assertEqual(tokenomics["status"], PARTIAL)
        self.assertEqual(historical["status"], OK)
        self.assertEqual(risk["status"], PARTIAL)
        self.assertEqual(risk["risk"]["recommendation"], WARN)
        self.assertIn("volume_24h_unverified", risk["risk"]["flags"])
        self.assertIn("token_activity_unavailable", risk["risk"]["flags"])
        self.assertLess(
            risk["confidence"]["verified_checks"],
            risk["confidence"]["total_checks"],
        )

    def test_verified_block_is_service_ok_across_complete_contract_pipeline(self):
        market = self._market_response(
            primary_liquidity=0.0,
            secondary_liquidity=0.0,
        )
        self.assertEqual(market["data"]["liquidity_usd"], 0.0)
        self.assertEqual(market["status"], OK)

        tokenomics = self._tokenomics_response()
        historical = self._historical_response(market)
        risk = build_risk_check_response(
            market["data"],
            tokenomics["data"],
            historical["data"],
            chain="x1",
        )

        self.assertEqual(risk["status"], OK)
        self.assertEqual(risk["risk"]["recommendation"], BLOCK)
        self.assertIn("zero_verified_liquidity", risk["risk"]["flags"])

    def test_underlying_data_objects_are_directly_composable_without_adapters(self):
        market = self._market_response()
        tokenomics = self._tokenomics_response()
        historical = self._historical_response(market)

        risk = build_risk_check_response(
            market_report=market["data"],
            tokenomics_report=tokenomics["data"],
            historical_report=historical["data"],
            chain=market["chain"],
            policy={"historical_price_warn_abs_change_pct": 5.0},
        )

        self.assertEqual(risk["status"], OK)
        self.assertEqual(risk["asset"]["mint"], MINT)
        self.assertEqual(risk["risk"]["recommendation"], WARN)
        self.assertIn(
            "historical_price_move_exceeds_warn_threshold",
            risk["risk"]["flags"],
        )
        self.assertEqual(
            risk["risk"]["components"]["history"]["evidence"]["change_pct"],
            5.0,
        )


if __name__ == "__main__":
    unittest.main()
