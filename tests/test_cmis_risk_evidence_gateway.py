import unittest
from unittest.mock import patch

from liquidity_scout.cmis.risk_evidence_gateway import (
    DEFAULT_RISK_HISTORICAL_QUESTION,
    EvidenceAwareCMISGateway,
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

    def refresh_if_needed(self):
        return self

    def market_catalog(self):
        return {
            "chain": "x1",
            "source": "X1.Ninja/XDEX",
            "pools": list(self.pools),
            "xnt_price_usd": self.xnt_price_usd,
            "observed_at": self.last_refresh,
        }


class FakeScanner:
    source = "X1 RPC parsed token instructions"

    def __init__(self, *, error=None):
        self.error = error
        self.calls = []

    def scan(self, *, mint, decimals, db, max_signatures=None):
        self.calls.append(
            {
                "mint": mint,
                "decimals": decimals,
                "max_signatures": max_signatures,
            }
        )
        if self.error is not None:
            raise self.error
        return {
            "mint": mint,
            "decimals": decimals,
            "coverage_verified": True,
            "activity_verified": True,
            "coverage_scope": "bounded",
            "lifetime_coverage_verified": False,
            "lifetime_coverage_reason": "bounded_signature_window",
            "mint_events_observed": 0,
            "burn_events_observed": 0,
            "minted_raw_observed": "0",
            "burned_raw_observed": "0",
            "minted_tokens_observed": "0",
            "burned_tokens_observed": "0",
            "net_issuance_raw": "0",
            "net_issuance_tokens": "0",
            "source": self.source,
        }


class FakeSupplyProvider:
    def get_total_supply(self):
        return {
            "chain": "x1",
            "asset": "XNT",
            "network": "mainnet",
            "metric": "total_supply",
            "supply": "1067069623",
            "supply_verified": True,
            "source": "api.x1.xyz /v1/supply/total",
        }

    def get_circulating_supply(self):
        return {
            "chain": "x1",
            "asset": "XNT",
            "network": "mainnet",
            "metric": "circulating_supply",
            "supply": "13810247",
            "supply_verified": True,
            "source": "api.x1.xyz /v1/supply/circulating",
        }


def tokenomics_envelope(*, decimals=9, activity_verified=False):
    return build_service_envelope(
        "tokenomics",
        "x1",
        "ok" if activity_verified else "partial",
        asset={"symbol": "AGI", "mint": "MINT_AGI"},
        data={
            "mint": "MINT_AGI",
            "symbol": "AGI",
            "name": "Artificial General Intelligence",
            "decimals": decimals,
            "supply_verified": True,
            "mint_authority_verified": True,
            "freeze_authority_verified": True,
            "token_activity": {
                "available": activity_verified,
                "activity_verified": activity_verified,
            },
        },
    )


class EvidenceAwareCMISGatewayTests(unittest.TestCase):
    def setUp(self):
        self.agi = token("AGI", "MINT_AGI", "Artificial General Intelligence")
        self.usdc = token("USDC", "MINT_USDC", "USD Coin")
        self.provider = FakeX1MarketProvider([pool("P1", self.agi, self.usdc)])

    def gateway(self, scanner):
        return EvidenceAwareCMISGateway(
            x1_market_provider=self.provider,
            x1_activity_scanner=scanner,
            activity_db_path=":memory:",
            risk_activity_max_signatures=7,
        )

    def test_risk_check_scans_bounded_activity_and_reattaches_it_to_tokenomics(self):
        scanner = FakeScanner()
        gateway = self.gateway(scanner)
        base = tokenomics_envelope()
        enriched = tokenomics_envelope(activity_verified=True)
        history_unavailable = build_service_envelope(
            "historical_compare", "x1", "unavailable"
        )
        expected = build_service_envelope("risk_check", "x1", "partial")

        with patch(
            "liquidity_scout.cmis.risk_evidence_gateway.build_tokenomics_response",
            side_effect=[base, enriched],
        ) as tokenomics_build, patch.object(
            gateway,
            "_historical_from_market",
            return_value=history_unavailable,
        ) as history, patch(
            "liquidity_scout.cmis.risk_evidence_gateway.build_risk_check_response",
            return_value=expected,
        ) as risk_build:
            response = gateway.dispatch(
                {"service": "risk_check", "chain": "x1", "asset": "AGI", "params": {}}
            )

        self.assertEqual(response, expected)
        self.assertEqual(
            scanner.calls,
            [{"mint": "MINT_AGI", "decimals": 9, "max_signatures": 7}],
        )
        self.assertEqual(tokenomics_build.call_count, 2)
        activity_report = tokenomics_build.call_args_list[1].kwargs["activity_report"]
        self.assertTrue(activity_report["activity_verified"])
        self.assertEqual(activity_report["coverage_scope"], "bounded")
        history.assert_called_once()
        self.assertEqual(history.call_args.args[0], DEFAULT_RISK_HISTORICAL_QUESTION)
        self.assertIsNone(risk_build.call_args.args[2])

    def test_scanner_failure_remains_explicit_warning_without_fabrication(self):
        scanner = FakeScanner(error=RuntimeError("rpc unavailable"))
        gateway = self.gateway(scanner)
        base = tokenomics_envelope()
        history_unavailable = build_service_envelope(
            "historical_compare", "x1", "unavailable"
        )
        expected = build_service_envelope("risk_check", "x1", "partial")

        with patch(
            "liquidity_scout.cmis.risk_evidence_gateway.build_tokenomics_response",
            return_value=base,
        ) as tokenomics_build, patch.object(
            gateway,
            "_historical_from_market",
            return_value=history_unavailable,
        ), patch(
            "liquidity_scout.cmis.risk_evidence_gateway.build_risk_check_response",
            return_value=expected,
        ):
            response = gateway.dispatch(
                {"service": "risk_check", "chain": "x1", "asset": "AGI", "params": {}}
            )

        self.assertEqual(tokenomics_build.call_count, 1)
        codes = {item.get("code") for item in response["warnings"]}
        self.assertIn("token_activity_collection_failed", codes)

    def test_default_historical_price_comparison_is_passed_when_verified(self):
        scanner = FakeScanner()
        gateway = self.gateway(scanner)
        base = tokenomics_envelope(decimals=None)
        historical_data = {
            "metric": "price",
            "current_value": 0.25,
            "historical_value": 0.20,
            "current_verified": True,
            "historical_verified": True,
        }
        historical = build_service_envelope(
            "historical_compare",
            "x1",
            "ok",
            data=historical_data,
        )
        expected = build_service_envelope("risk_check", "x1", "partial")

        with patch(
            "liquidity_scout.cmis.risk_evidence_gateway.build_tokenomics_response",
            return_value=base,
        ), patch.object(
            gateway,
            "_historical_from_market",
            return_value=historical,
        ) as history, patch(
            "liquidity_scout.cmis.risk_evidence_gateway.build_risk_check_response",
            return_value=expected,
        ) as risk_build:
            gateway.dispatch(
                {"service": "risk_check", "chain": "x1", "asset": "AGI", "params": {}}
            )

        self.assertEqual(history.call_args.args[0], DEFAULT_RISK_HISTORICAL_QUESTION)
        self.assertEqual(risk_build.call_args.args[2], historical_data)
        self.assertEqual(scanner.calls, [])

    def test_explicit_historical_question_overrides_default(self):
        scanner = FakeScanner()
        gateway = self.gateway(scanner)
        base = tokenomics_envelope(decimals=None)
        unavailable = build_service_envelope("historical_compare", "x1", "unavailable")
        expected = build_service_envelope("risk_check", "x1", "partial")
        question = "Has price changed in the last 7 days?"

        with patch(
            "liquidity_scout.cmis.risk_evidence_gateway.build_tokenomics_response",
            return_value=base,
        ), patch.object(
            gateway,
            "_historical_from_market",
            return_value=unavailable,
        ) as history, patch(
            "liquidity_scout.cmis.risk_evidence_gateway.build_risk_check_response",
            return_value=expected,
        ):
            gateway.dispatch(
                {
                    "service": "risk_check",
                    "chain": "x1",
                    "asset": "AGI",
                    "params": {"historical_question": question},
                }
            )

        self.assertEqual(history.call_args.args[0], question)

    def test_native_risk_does_not_run_token_program_activity_scanner(self):
        xnt = token("XNT", "MINT_XNT", "Wrapped XNT")
        provider = FakeX1MarketProvider([pool("P_XNT", xnt, self.usdc)])
        provider.xnt_price_usd = 0.25
        scanner = FakeScanner(error=AssertionError("native asset must not scan"))
        gateway = EvidenceAwareCMISGateway(
            x1_market_provider=provider,
            x1_supply_provider=FakeSupplyProvider(),
            x1_activity_scanner=scanner,
            activity_db_path=":memory:",
        )
        history_unavailable = build_service_envelope(
            "historical_compare", "x1", "unavailable"
        )
        expected = build_service_envelope("risk_check", "x1", "partial")

        with patch.object(
            gateway,
            "_historical_from_market",
            return_value=history_unavailable,
        ), patch(
            "liquidity_scout.cmis.risk_evidence_gateway.build_risk_check_response",
            return_value=expected,
        ):
            gateway.dispatch(
                {"service": "risk_check", "chain": "x1", "asset": "XNT", "params": {}}
            )

        self.assertEqual(scanner.calls, [])

    def test_invalid_activity_bound_fails_closed(self):
        scanner = FakeScanner()
        gateway = self.gateway(scanner)
        base = tokenomics_envelope()

        with patch(
            "liquidity_scout.cmis.risk_evidence_gateway.build_tokenomics_response",
            return_value=base,
        ):
            response = gateway.dispatch(
                {
                    "service": "risk_check",
                    "chain": "x1",
                    "asset": "AGI",
                    "params": {"activity_max_signatures": 0},
                }
            )

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "invalid_activity_max_signatures",
        )
        self.assertEqual(scanner.calls, [])


if __name__ == "__main__":
    unittest.main()
