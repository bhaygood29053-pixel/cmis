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


XENCAT_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"

class FakeTokenMetadataProvider:
    def __init__(self, *, symbol="XENCAT", name="XENCAT", available=True):
        self.symbol = symbol
        self.name = name
        self.available = available
        self.calls = []

    def get_metadata(self, mint):
        self.calls.append(mint)
        if not self.available:
            return {
                "identity_verified": False,
                "program": {"program_executable_verified": True},
                "metadata": {"identity_verified": False, "mint": mint},
            }
        return {
            "identity_verified": True,
            "program": {
                "program_executable_verified": True,
                "context_slot": 100,
            },
            "metadata": {
                "identity_verified": True,
                "mint": mint,
                "symbol": self.symbol,
                "name": self.name,
                "uri": "https://example.invalid/token.json",
                "metadata_account": "Metadata111",
                "metadata_update_authority": "Update111",
                "is_mutable": True,
                "token_standard": "Fungible",
                "context_slot": 101,
                "program_id": "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s",
            },
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

    def test_exact_mint_resolves_metaplex_only_without_xdex_presence(self):
        metadata = FakeTokenMetadataProvider()
        gateway = CMISGateway(
            x1_market_provider=FakeX1MarketProvider([]),
            x1_token_metadata_provider=metadata,
        )
        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "x1",
            "asset": XENCAT_MINT,
        })
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["asset"]["mint"], XENCAT_MINT)
        self.assertEqual(response["asset"]["symbol"], "XENCAT")
        self.assertEqual(
            response["data"]["identity_reconciliation"]["state"],
            "metaplex_only",
        )
        self.assertTrue(
            response["data"]["normalized_identity"][
                "normalized_onchain_identity_verified"
            ]
        )
        self.assertEqual(metadata.calls, [XENCAT_MINT])

    def test_exact_mint_reconciles_matching_metaplex_and_xdex_descriptors(self):
        metadata = FakeTokenMetadataProvider()
        xdex_token = token("XENCAT", XENCAT_MINT, "XENCAT")
        gateway = CMISGateway(
            x1_market_provider=FakeX1MarketProvider([
                pool("PX", xdex_token, self.usdc),
            ]),
            x1_token_metadata_provider=metadata,
        )
        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "x1",
            "asset": XENCAT_MINT,
        })
        self.assertEqual(response["status"], "ok")
        reconciliation = response["data"]["identity_reconciliation"]
        self.assertEqual(reconciliation["state"], "agreement")
        self.assertEqual(reconciliation["conflicting_fields"], [])
        self.assertEqual(
            response["data"]["normalized_identity"]["identity_root"],
            "mint",
        )
        self.assertEqual(
            response["data"]["normalized_identity"]["descriptor_source"],
            "metaplex_token_metadata",
        )

    def test_exact_mint_descriptor_conflict_is_partial_not_ambiguous(self):
        metadata = FakeTokenMetadataProvider(symbol="XENCAT", name="XENCAT")
        xdex_token = token("CATX", XENCAT_MINT, "Different Name")
        gateway = CMISGateway(
            x1_market_provider=FakeX1MarketProvider([
                pool("PX", xdex_token, self.usdc),
            ]),
            x1_token_metadata_provider=metadata,
        )
        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "x1",
            "asset": XENCAT_MINT,
        })
        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["asset"]["mint"], XENCAT_MINT)
        self.assertEqual(response["asset"]["symbol"], "XENCAT")
        reconciliation = response["data"]["identity_reconciliation"]
        self.assertEqual(reconciliation["state"], "descriptor_conflict")
        self.assertEqual(
            set(reconciliation["conflicting_fields"]),
            {"symbol", "name"},
        )

    def test_exact_mint_metadata_unavailable_preserves_xdex_as_partial_only(self):
        metadata = FakeTokenMetadataProvider(available=False)
        xdex_token = token("XENCAT", XENCAT_MINT, "XENCAT")
        gateway = CMISGateway(
            x1_market_provider=FakeX1MarketProvider([
                pool("PX", xdex_token, self.usdc),
            ]),
            x1_token_metadata_provider=metadata,
        )
        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "x1",
            "asset": XENCAT_MINT,
        })
        self.assertEqual(response["status"], "partial")
        self.assertFalse(
            response["data"]["normalized_identity"][
                "normalized_onchain_identity_verified"
            ]
        )
        self.assertEqual(
            response["data"]["identity_reconciliation"]["state"],
            "metadata_unavailable",
        )

    def test_exact_mint_xdex_outage_is_not_reported_as_metaplex_only(self):
        metadata = FakeTokenMetadataProvider()

        class FailingMarketProvider(FakeX1MarketProvider):
            def refresh_if_needed(self):
                raise RuntimeError("offline")

        gateway = CMISGateway(
            x1_market_provider=FailingMarketProvider([]),
            x1_token_metadata_provider=metadata,
        )
        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "x1",
            "asset": XENCAT_MINT,
        })
        self.assertEqual(response["status"], "partial")
        self.assertEqual(
            response["data"]["identity_reconciliation"]["state"],
            "xdex_unavailable",
        )
        self.assertFalse(
            response["data"]["identity_reconciliation"]["xdex"]["available"]
        )
        self.assertTrue(
            any(
                warning.get("code") == "x1_market_provider_unavailable"
                for warning in response["warnings"]
            )
        )

    def test_symbol_lookup_does_not_call_token_metadata_provider(self):
        metadata = FakeTokenMetadataProvider()
        gateway = CMISGateway(
            x1_market_provider=self.provider,
            x1_token_metadata_provider=metadata,
        )
        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "x1",
            "asset": "AGI",
        })
        self.assertEqual(response["status"], "ok")
        self.assertEqual(metadata.calls, [])

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
        self.assertIs(
            kwargs["onchain_coverage_provider"],
            self.gateway.x1_rpc_provider,
        )
        self.assertEqual(kwargs["onchain_page_size"], 1000)
        self.assertEqual(kwargs["onchain_max_signatures"], 5000)


    def test_all_available_validates_onchain_scan_bounds(self):
        response = self.gateway.dispatch({
            "service": "historical_compare",
            "chain": "x1",
            "asset": "AGI",
            "params": {
                "mode": "all_available",
                "onchain_page_size": 0,
            },
        })

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "invalid_historical_tolerance",
        )


    def test_all_available_attempts_bounded_verified_provider_price_backfill(self):
        expected = build_service_envelope(
            "historical_compare",
            "x1",
            "partial",
            data={"mode": "all_available"},
        )
        backfill_result = {
            "status": "partial",
            "reason": "verified_provider_price_history_backfilled",
            "provider_history_imported": True,
            "imported_observation_count": 3,
        }

        with patch(
            "liquidity_scout.cmis.gateway.time.time",
            return_value=1_000_000,
        ), patch(
            "liquidity_scout.cmis.gateway.backfill_verified_xdex_usd_price_history",
            return_value=backfill_result,
        ) as backfill, patch(
            "liquidity_scout.cmis.gateway.build_historical_compare_response",
            return_value=expected,
        ):
            response = self.gateway.dispatch({
                "service": "historical_compare",
                "chain": "x1",
                "asset": "AGI",
                "params": {
                    "mode": "all_available",
                    "provider_history_lookback_days": 10,
                    "provider_history_min_refresh_seconds": 0,
                    "provider_history_rel_tolerance": 0.01,
                },
            })

        backfill.assert_called_once()
        args, kwargs = backfill.call_args
        self.assertEqual(args[0], "MINT_AGI")
        self.assertEqual(args[1], "AGI")
        self.assertEqual(kwargs["catalog_pools"], self.provider.pools)
        self.assertIs(kwargs["history_backend"], self.gateway.history_backend)
        self.assertEqual(kwargs["time_from"], 136000)
        self.assertEqual(kwargs["time_to"], 1_000_000)
        self.assertEqual(kwargs["rel_tolerance"], 0.01)
        self.assertEqual(kwargs["imported_at"], 1_000_000)
        self.assertEqual(
            response["data"]["provider_history_backfill"],
            backfill_result,
        )

    def test_all_available_provider_backfill_can_be_explicitly_disabled(self):
        expected = build_service_envelope(
            "historical_compare",
            "x1",
            "partial",
            data={"mode": "all_available"},
        )
        with patch(
            "liquidity_scout.cmis.gateway.backfill_verified_xdex_usd_price_history",
        ) as backfill, patch(
            "liquidity_scout.cmis.gateway.build_historical_compare_response",
            return_value=expected,
        ):
            response = self.gateway.dispatch({
                "service": "historical_compare",
                "chain": "x1",
                "asset": "AGI",
                "params": {
                    "mode": "all_available",
                    "provider_history_backfill": False,
                },
            })

        backfill.assert_not_called()
        self.assertNotIn("provider_history_backfill", response["data"])

    def test_all_available_validates_provider_backfill_bounds(self):
        response = self.gateway.dispatch({
            "service": "historical_compare",
            "chain": "x1",
            "asset": "AGI",
            "params": {
                "mode": "all_available",
                "provider_history_lookback_days": 0,
            },
        })

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "invalid_historical_tolerance",
        )

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
