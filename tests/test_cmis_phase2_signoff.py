import unittest
from types import SimpleNamespace

from liquidity_scout.services import (
    AMBIGUOUS,
    BLOCK,
    OK,
    PARTIAL,
    PASS,
    SERVICE_STATUSES,
    WARN,
    build_asset_lookup_response,
    build_historical_compare_response,
    build_market_report_response,
    build_pre_trade_check_response,
    build_rank_response,
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
EXPECTED_SERVICE_STATUSES = {
    "ok",
    "partial",
    "unavailable",
    "ambiguous",
    "error",
}


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


def ranking_pool(address, asset, *, liquidity=None, volume24h=None):
    # A quote without a mint is intentionally not a rankable asset. This keeps
    # the ranking universe focused on the two base assets under test.
    quote = {"symbol": "QUOTE", "name": "Quote Token"}
    row = {
        "address": address,
        "baseToken": asset,
        "quoteToken": quote,
    }
    if liquidity is not None:
        row["liquidity"] = liquidity
    if volume24h is not None:
        row["volume24h"] = volume24h
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


class CMISPhase2SevenServiceSignoffTests(unittest.TestCase):
    def setUp(self):
        self.asset = token("REF", MINT, "Reference Token")
        self.usdc = token("USDC", "MintUSDC", "USD Coin")
        self.xnt = token("XNT", "MintXNT", "Wrapped XNT")
        self.beta = token("BETA", "MintBeta", "Beta Token")

    def _market_pools(
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
        return [primary, secondary]

    def _asset_lookup_response(self, pools):
        return build_asset_lookup_response(
            "REF",
            pools,
            chain="x1",
            source="X1.Ninja/XDEX",
            observed_at=2000.0,
        )

    def _market_response(self, pools):
        return build_market_report_response(
            "REF",
            [
                (pools[0], "base", self.asset, 90),
                (pools[1], "base", self.asset, 90),
            ],
            SimpleNamespace(xnt_price_usd=None, last_refresh=2000.0),
            chain="x1",
        )

    def _rank_response(self, *, beta_volume=300.0):
        pools = [
            ranking_pool("R1", self.asset, liquidity=5000.0, volume24h=100.0),
            ranking_pool("R2", self.asset, liquidity=1000.0, volume24h=500.0),
            ranking_pool("R3", self.beta, liquidity=3000.0, volume24h=beta_volume),
        ]
        if beta_volume is None:
            pools[-1].pop("volume24h", None)
        return build_rank_response(
            pools,
            metric="volume",
            limit=10,
            chain="x1",
            source="X1.Ninja/XDEX",
            observed_at=2000.0,
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

    def _risk_response(self, market, tokenomics, historical):
        return build_risk_check_response(
            market["data"],
            tokenomics["data"],
            historical["data"],
            chain="x1",
            observed_at=2000.0,
        )

    def _pre_trade_response(self, risk):
        return build_pre_trade_check_response(
            risk,
            {
                "side": "buy",
                "chain": "x1",
                "asset": {"symbol": "REF", "mint": MINT},
                "notional_usd": 1000.0,
            },
            chain="x1",
        )

    def _complete_surface(self):
        pools = self._market_pools()
        lookup = self._asset_lookup_response(pools)
        market = self._market_response(pools)
        rank = self._rank_response()
        tokenomics = self._tokenomics_response()
        historical = self._historical_response(market)
        risk = self._risk_response(market, tokenomics, historical)
        pre_trade = self._pre_trade_response(risk)
        return lookup, market, rank, historical, tokenomics, risk, pre_trade

    def test_supported_service_status_vocabulary_is_exact(self):
        self.assertEqual(set(SERVICE_STATUSES), EXPECTED_SERVICE_STATUSES)

    def test_all_seven_public_services_use_one_canonical_envelope(self):
        responses = self._complete_surface()

        self.assertEqual(
            [response["service"] for response in responses],
            [
                "asset_lookup",
                "market_report",
                "rank",
                "historical_compare",
                "tokenomics",
                "risk_check",
                "pre_trade_check",
            ],
        )
        for response in responses:
            self.assertEqual(list(response), CANONICAL_ENVELOPE_KEYS)
            self.assertEqual(response["chain"], "x1")
            self.assertEqual(response["status"], OK)
            self.assertIsInstance(response["asset"], dict)
            self.assertIsInstance(response["data"], dict)
            self.assertIsInstance(response["confidence"], dict)
            self.assertIsInstance(response["sources"], list)
            self.assertIsInstance(response["warnings"], list)
            self.assertIsInstance(response["errors"], list)

    def test_asset_identity_is_consistent_across_all_asset_scoped_services(self):
        lookup, market, _rank, historical, tokenomics, risk, pre_trade = (
            self._complete_surface()
        )

        scoped = [lookup, market, historical, tokenomics, risk, pre_trade]
        self.assertTrue(all(response["asset"]["mint"] == MINT for response in scoped))
        self.assertEqual(lookup["asset"]["symbol"], "REF")
        self.assertEqual(market["asset"]["symbol"], "REF")
        self.assertEqual(risk["asset"]["symbol"], "REF")
        self.assertEqual(pre_trade["asset"]["symbol"], "REF")

    def test_rank_is_asset_wide_and_preserves_public_lp_count(self):
        rank = self._rank_response()

        self.assertEqual(rank["status"], OK)
        self.assertEqual(rank["data"]["ranked_count"], 2)
        first = rank["data"]["rankings"][0]
        self.assertEqual(first["symbol"], "REF")
        self.assertEqual(first["mint"], MINT)
        self.assertEqual(first["rank"], 1)
        self.assertEqual(first["value"], 600.0)
        self.assertEqual(first["lp_count"], 2)
        self.assertEqual(first["#LPs"], 2)

    def test_risk_to_pre_trade_cmis_handoff_preserves_provenance(self):
        _lookup, market, _rank, historical, tokenomics, risk, pre_trade = (
            self._complete_surface()
        )

        self.assertEqual(risk["status"], OK)
        self.assertEqual(risk["risk"]["recommendation"], PASS)
        self.assertEqual(pre_trade["status"], OK)
        self.assertEqual(pre_trade["risk"]["recommendation"], PASS)
        self.assertEqual(pre_trade["observed_at"], 2000.0)

        expected_sources = [
            {
                "source": "X1.Ninja/XDEX",
                "role": "market_report",
                "observed_at": 2000.0,
            },
            {
                "source": "X1 RPC getTokenSupply",
                "role": "tokenomics.current_supply",
            },
            {
                "source": "X1 RPC parsed token instructions",
                "role": "tokenomics.token_activity",
            },
            {
                "source": "historical_db",
                "role": "historical_compare",
                "observed_at": 2000.0,
            },
            {"source": "risk_engine", "role": "risk_check"},
            {"source": "pre_trade_engine", "role": "pre_trade_check"},
        ]
        for source in expected_sources:
            self.assertIn(source, pre_trade["sources"])

        # These are the exact structured objects used upstream; no adapter is
        # required between historical -> risk or risk envelope -> pre-trade.
        self.assertEqual(historical["data"]["change_pct"], 5.0)
        self.assertEqual(market["data"]["liquidity_usd"], 6000.0)
        self.assertTrue(tokenomics["data"]["supply_verified"])

    def test_partial_upstream_evidence_remains_partial_through_pre_trade(self):
        pools = self._market_pools(second_volume=None)
        market = self._market_response(pools)
        tokenomics = self._tokenomics_response(include_activity=False)
        historical = self._historical_response(market)
        risk = self._risk_response(market, tokenomics, historical)
        pre_trade = self._pre_trade_response(risk)
        rank = self._rank_response(beta_volume=None)

        self.assertEqual(market["status"], PARTIAL)
        self.assertEqual(tokenomics["status"], PARTIAL)
        self.assertEqual(historical["status"], OK)
        self.assertEqual(rank["status"], PARTIAL)
        self.assertEqual(risk["status"], PARTIAL)
        self.assertEqual(risk["risk"]["recommendation"], WARN)
        self.assertEqual(pre_trade["status"], PARTIAL)
        self.assertEqual(pre_trade["risk"]["recommendation"], WARN)
        self.assertIn("risk_evidence_incomplete", pre_trade["risk"]["flags"])
        self.assertIn("volume_24h_unverified", risk["risk"]["flags"])
        self.assertIn("token_activity_unavailable", risk["risk"]["flags"])

    def test_verified_block_is_ok_service_finding_through_pre_trade(self):
        pools = self._market_pools(
            primary_liquidity=0.0,
            secondary_liquidity=0.0,
        )
        market = self._market_response(pools)
        tokenomics = self._tokenomics_response()
        historical = self._historical_response(market)
        risk = self._risk_response(market, tokenomics, historical)
        pre_trade = self._pre_trade_response(risk)

        self.assertEqual(market["status"], OK)
        self.assertEqual(market["data"]["liquidity_usd"], 0.0)
        self.assertEqual(risk["status"], OK)
        self.assertEqual(risk["risk"]["recommendation"], BLOCK)
        self.assertIn("zero_verified_liquidity", risk["risk"]["flags"])
        self.assertEqual(pre_trade["status"], OK)
        self.assertEqual(pre_trade["risk"]["recommendation"], BLOCK)
        self.assertIn("risk_check_block", pre_trade["risk"]["flags"])

    def test_pre_trade_is_analysis_only_even_when_every_check_passes(self):
        *_, pre_trade = self._complete_surface()

        self.assertEqual(pre_trade["risk"]["recommendation"], PASS)
        self.assertTrue(pre_trade["data"]["analysis_only"])
        self.assertFalse(pre_trade["data"]["execution_authorized"])
        self.assertTrue(pre_trade["risk"]["analysis_only"])
        self.assertFalse(pre_trade["risk"]["execution_authorized"])
        self.assertEqual(
            pre_trade["risk"]["authorization_reason"],
            "pre_trade_check_analysis_only",
        )

    def test_asset_lookup_ambiguity_is_preserved_instead_of_liquidity_guess(self):
        other = token("REF", "DifferentMint", "Different Reference Token")
        pools = self._market_pools() + [
            pool(
                "P3",
                other,
                self.usdc,
                liquidity=999999.0,
                volume24h=999999.0,
                txns24h=999,
                holders=9999,
                price=999.0,
            )
        ]

        lookup = build_asset_lookup_response(
            "REF",
            pools,
            chain="x1",
            source="X1.Ninja/XDEX",
            observed_at=2000.0,
        )

        self.assertEqual(lookup["status"], AMBIGUOUS)
        self.assertEqual(lookup["asset"], {})
        self.assertEqual(
            set(lookup["data"]["candidate_asset_keys"]),
            {MINT, "DifferentMint"},
        )
        self.assertEqual(lookup["warnings"][0]["code"], "asset_ambiguous")


if __name__ == "__main__":
    unittest.main()
