import unittest
from unittest.mock import patch

from liquidity_scout.cmis.gateway import (
    SUPPORTED_SERVICES,
    CMISGateway,
)
from liquidity_scout.services.cmis_contract import build_service_envelope


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def pool(address, base, quote):
    return {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "createdAt": "2026-01-01T00:00:00Z",
        "liquidity": 5000,
        "volume24h": 100,
        "txns24h": 10,
        "holders": 1000,
        "priceUsd": 0.25,
    }


class FakeX1MarketProvider:
    chain = "x1"

    def __init__(self, pools):
        self.pools = list(pools)
        self.xnt_price_usd = None
        self.last_refresh = 123.0
        self.refresh_calls = 0

    def refresh_if_needed(self):
        self.refresh_calls += 1
        return self

    def market_catalog(self):
        return {
            "chain": "x1",
            "source": "X1.Ninja/XDEX",
            "pools": list(self.pools),
            "xnt_price_usd": self.xnt_price_usd,
            "observed_at": self.last_refresh,
        }


class CMISGatewayTests(unittest.TestCase):
    def setUp(self):
        self.agi = token("AGI", "MINT_AGI", "Artificial General Intelligence")
        self.usdc = token("USDC", "MINT_USDC", "USD Coin")
        self.provider = FakeX1MarketProvider([
            pool("P1", self.agi, self.usdc),
        ])
        self.gateway = CMISGateway(x1_market_provider=self.provider)

    def test_gateway_exposes_exact_seven_service_surface(self):
        self.assertEqual(
            SUPPORTED_SERVICES,
            (
                "asset_lookup",
                "market_report",
                "rank",
                "historical_compare",
                "tokenomics",
                "risk_check",
                "pre_trade_check",
            ),
        )

    def test_asset_lookup_collects_inside_cmis_and_returns_standard_envelope(self):
        response = self.gateway.dispatch({
            "service": "asset_lookup",
            "chain": "x1",
            "asset": "AGI",
        })

        self.assertEqual(response["service"], "asset_lookup")
        self.assertEqual(response["chain"], "x1")
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["asset"]["mint"], "MINT_AGI")
        self.assertEqual(response["observed_at"], 123.0)
        self.assertEqual(self.provider.refresh_calls, 1)

    def test_market_report_request_does_not_require_external_pool_rows(self):
        response = self.gateway.dispatch({
            "service": "market_report",
            "chain": "x1",
            "asset": "AGI",
            "params": {},
        })

        self.assertEqual(response["service"], "market_report")
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["asset"]["mint"], "MINT_AGI")
        self.assertEqual(response["data"]["liquidity_usd"], 5000)
        self.assertEqual(response["data"]["#LPs"], 1)

    def test_rank_collects_catalog_inside_gateway(self):
        response = self.gateway.dispatch({
            "service": "rank",
            "chain": "x1",
            "params": {"metric": "volume", "limit": 5},
        })

        self.assertEqual(response["service"], "rank")
        self.assertIn(response["status"], {"ok", "partial"})
        agi_row = next(
            row
            for row in response["data"]["rankings"]
            if row["mint"] == "MINT_AGI"
        )
        self.assertEqual(agi_row["#LPs"], 1)

    def test_tokenomics_resolves_symbol_then_calls_service_with_verified_mint(self):
        tokenomics_response = build_service_envelope(
            "tokenomics",
            "x1",
            "partial",
            asset={"symbol": "AGI", "mint": "MINT_AGI"},
            data={"mint": "MINT_AGI", "supply_verified": True},
        )
        with patch(
            "liquidity_scout.cmis.gateway.build_tokenomics_response",
            return_value=tokenomics_response,
        ) as build:
            response = self.gateway.dispatch({
                "service": "tokenomics",
                "chain": "x1",
                "asset": "AGI",
            })

        self.assertEqual(response, tokenomics_response)
        build.assert_called_once_with(
            "MINT_AGI",
            symbol="AGI",
            name="Artificial General Intelligence",
            chain="x1",
        )

    def test_tokenomics_accepts_explicit_mint_without_market_resolution(self):
        tokenomics_response = build_service_envelope(
            "tokenomics",
            "x1",
            "unavailable",
            asset={"mint": "DIRECT_MINT"},
        )
        with patch(
            "liquidity_scout.cmis.gateway.build_tokenomics_response",
            return_value=tokenomics_response,
        ) as build:
            response = self.gateway.dispatch({
                "service": "tokenomics",
                "chain": "x1",
                "asset": "anything",
                "params": {"mint": "DIRECT_MINT"},
            })

        self.assertEqual(response, tokenomics_response)
        self.assertEqual(self.provider.refresh_calls, 0)
        build.assert_called_once_with(
            "DIRECT_MINT",
            symbol=None,
            name=None,
            chain="x1",
        )

    def test_historical_compare_receives_structured_current_market_report(self):
        expected = build_service_envelope(
            "historical_compare",
            "x1",
            "unavailable",
        )
        with patch(
            "liquidity_scout.cmis.gateway.build_historical_compare_response",
            return_value=expected,
        ) as build:
            response = self.gateway.dispatch({
                "service": "historical_compare",
                "chain": "x1",
                "asset": "AGI",
                "params": {"question": "Has AGI liquidity fallen in 24h?"},
            })

        self.assertEqual(response, expected)
        args, kwargs = build.call_args
        self.assertEqual(args[0], "Has AGI liquidity fallen in 24h?")
        self.assertEqual(args[1]["_market_report"]["mint"], "MINT_AGI")
        self.assertEqual(kwargs["chain"], "x1")

    def test_entire_history_language_selects_all_available_mode(self):
        expected = build_service_envelope(
            "historical_compare",
            "x1",
            "partial",
        )
        with patch(
            "liquidity_scout.cmis.gateway.build_historical_compare_response",
            return_value=expected,
        ) as build:
            response = self.gateway.dispatch({
                "service": "historical_compare",
                "chain": "x1",
                "asset": "AGI",
                "params": {"question": "Show me AGI's entire history"},
            })

        self.assertEqual(response, expected)
        _, kwargs = build.call_args
        self.assertEqual(kwargs["mode"], "all_available")

    def test_all_available_pair_requires_compare_asset(self):
        response = self.gateway.dispatch({
            "service": "historical_compare",
            "chain": "x1",
            "asset": "AGI",
            "params": {"mode": "all_available_pair"},
        })

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "compare_asset_required",
        )

    def test_base_gateway_does_not_auto_record_market_history(self):
        class History:
            def __init__(self):
                self.calls = []

            def record_snapshot_if_due(self, **kwargs):
                self.calls.append(kwargs)
                return True

        history = History()
        gateway = CMISGateway(
            x1_market_provider=self.provider,
            history_backend=history,
        )

        response = gateway.dispatch({
            "service": "market_report",
            "chain": "x1",
            "asset": "AGI",
        })

        self.assertEqual(response["status"], "ok")
        self.assertEqual(history.calls, [])


    def test_risk_check_composes_market_and_tokenomics_inside_cmis(self):
        tokenomics_response = build_service_envelope(
            "tokenomics",
            "x1",
            "partial",
            asset={"symbol": "AGI", "mint": "MINT_AGI"},
            data={
                "mint": "MINT_AGI",
                "supply_verified": True,
                "mint_authority_verified": True,
                "freeze_authority_verified": True,
            },
        )
        expected = build_service_envelope(
            "risk_check",
            "x1",
            "partial",
            asset={"symbol": "AGI", "mint": "MINT_AGI"},
        )
        with patch(
            "liquidity_scout.cmis.gateway.build_tokenomics_response",
            return_value=tokenomics_response,
        ), patch(
            "liquidity_scout.cmis.gateway.build_risk_check_response",
            return_value=expected,
        ) as risk_build:
            response = self.gateway.dispatch({
                "service": "risk_check",
                "chain": "x1",
                "asset": "AGI",
                "params": {"policy": {"min_liquidity_usd": 1000}},
            })

        self.assertEqual(response, expected)
        args, kwargs = risk_build.call_args
        self.assertEqual(args[0]["mint"], "MINT_AGI")
        self.assertEqual(args[1]["mint"], "MINT_AGI")
        self.assertIsNone(args[2])
        self.assertEqual(kwargs["policy"], {"min_liquidity_usd": 1000})

    def test_pre_trade_fills_verified_identity_but_preserves_caller_trade_fields(self):
        risk = build_service_envelope(
            "risk_check",
            "x1",
            "ok",
            asset={"symbol": "AGI", "mint": "MINT_AGI"},
            risk={
                "chain": "x1",
                "asset": {"symbol": "AGI", "mint": "MINT_AGI"},
                "recommendation": "PASS",
                "confidence": {"verified_checks": 1, "total_checks": 1},
                "flags": [],
                "reasons": [],
            },
        )
        expected = build_service_envelope("pre_trade_check", "x1", "ok")
        with patch.object(self.gateway, "_risk_check", return_value=risk), patch(
            "liquidity_scout.cmis.gateway.build_pre_trade_check_response",
            return_value=expected,
        ) as pre_trade:
            response = self.gateway.dispatch({
                "service": "pre_trade_check",
                "chain": "x1",
                "asset": "AGI",
                "params": {"trade": {"side": "buy", "notional_usd": 25}},
            })

        self.assertEqual(response, expected)
        args, kwargs = pre_trade.call_args
        self.assertEqual(args[0], risk)
        self.assertEqual(args[1]["side"], "buy")
        self.assertEqual(args[1]["notional_usd"], 25)
        self.assertEqual(args[1]["chain"], "x1")
        self.assertEqual(args[1]["asset"]["mint"], "MINT_AGI")
        self.assertEqual(kwargs["chain"], "x1")

    def test_solana_is_known_but_unavailable_until_provider_exists(self):
        response = self.gateway.dispatch({
            "service": "market_report",
            "chain": "solana",
            "asset": "JUP",
        })

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["chain"], "solana")
        self.assertEqual(
            response["warnings"][0]["code"],
            "chain_provider_not_implemented",
        )
        self.assertEqual(self.provider.refresh_calls, 0)

    def test_unknown_chain_and_bad_params_fail_closed(self):
        unknown = self.gateway.dispatch({
            "service": "market_report",
            "chain": "ethereum",
            "asset": "ETH",
        })
        self.assertEqual(unknown["status"], "error")
        self.assertEqual(unknown["errors"][0]["code"], "unsupported_chain")

        bad_params = self.gateway.dispatch({
            "service": "rank",
            "chain": "x1",
            "params": "volume",
        })
        self.assertEqual(bad_params["status"], "error")
        self.assertEqual(bad_params["errors"][0]["code"], "invalid_params")


if __name__ == "__main__":
    unittest.main()
