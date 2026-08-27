import unittest
from types import SimpleNamespace

from liquidity_scout.services import (
    AMBIGUOUS,
    ERROR,
    OK,
    PARTIAL,
    UNAVAILABLE,
    build_market_report_response,
)


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
    market_cap=None,
    fdv=None,
):
    row = {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "createdAt": "2026-01-01T00:00:00Z",
    }
    values = {
        "liquidity": liquidity,
        "volume24h": volume24h,
        "txns24h": txns24h,
        "holders": holders,
        "priceUsd": price,
        "marketCap": market_cap,
        "fdv": fdv,
    }
    for key, value in values.items():
        if value is not None:
            row[key] = value
    return row


class CMISMarketContractTests(unittest.TestCase):
    def setUp(self):
        self.agi = token("AGI", "MINT_AGI", "Artificial General Intelligence")
        self.usdc = token("USDC", "MINT_USDC", "USD Coin")
        self.xnt = token("XNT", "MINT_XNT", "Wrapped XNT")

    def _complete_matches(self):
        primary = pool(
            "P1",
            self.agi,
            self.usdc,
            liquidity=5000,
            volume24h=100,
            txns24h=10,
            holders=1000,
            price=0.25,
            market_cap=12345,
            fdv=23456,
        )
        secondary = pool(
            "P2",
            self.agi,
            self.xnt,
            liquidity=1000,
            volume24h=500,
            txns24h=20,
            holders=1000,
            price=0.20,
        )
        return [
            (primary, "base", self.agi, 90),
            (secondary, "base", self.agi, 90),
        ]

    def test_provider_complete_market_report_is_partial_until_holder_semantics_are_verified(self):
        response = build_market_report_response(
            "AGI",
            self._complete_matches(),
            SimpleNamespace(xnt_price_usd=None, last_refresh=123.0),
        )

        self.assertEqual(response["service"], "market_report")
        self.assertEqual(response["chain"], "x1")
        self.assertEqual(response["status"], PARTIAL)
        self.assertEqual(response["asset"]["mint"], "MINT_AGI")
        self.assertEqual(response["data"]["lp_count"], 2)
        self.assertEqual(response["data"]["liquidity_usd"], 6000)
        self.assertEqual(response["data"]["volume_24h_usd"], 600)
        self.assertEqual(response["data"]["transactions_24h"], 30)
        self.assertIsNone(response["data"]["holders"])
        self.assertEqual(response["data"]["holders_reported"], 1000)
        self.assertFalse(response["data"]["completeness"]["holders"])
        self.assertEqual(response["confidence"]["verified_checks"], 4)
        self.assertFalse(response["confidence"]["complete"])
        self.assertEqual(response["observed_at"], 123.0)
        self.assertIn(
            {
                "source": "X1.Ninja/XDEX",
                "role": "market_report",
                "observed_at": 123.0,
            },
            response["sources"],
        )

        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("holders_incomplete", codes)
        self.assertIn("market_cap_reported_unverified", codes)
        self.assertIn("fdv_reported_unverified", codes)
        self.assertFalse(response["data"]["market_cap_verified"])
        self.assertFalse(response["data"]["fdv_verified"])

    def test_incomplete_multi_lp_coverage_is_partial_not_fabricated_zero(self):
        matches = self._complete_matches()
        matches[1][0].pop("liquidity")
        matches[0][0].pop("volume24h")

        response = build_market_report_response(
            "AGI",
            matches,
            SimpleNamespace(xnt_price_usd=None, last_refresh=456.0),
        )

        self.assertEqual(response["status"], PARTIAL)
        self.assertEqual(response["data"]["liquidity_usd"], 5000)
        self.assertFalse(response["data"]["completeness"]["liquidity"])
        self.assertEqual(response["data"]["volume_24h_usd"], 500)
        self.assertFalse(response["data"]["completeness"]["volume_24h"])
        self.assertFalse(response["confidence"]["complete"])
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("liquidity_incomplete", codes)
        self.assertIn("volume_24h_incomplete", codes)

    def test_no_resolved_matches_is_unavailable(self):
        response = build_market_report_response(
            "UNKNOWN",
            [],
            SimpleNamespace(xnt_price_usd=None, last_refresh=1.0),
        )

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertEqual(response["data"], {"query": "UNKNOWN"})
        self.assertEqual(response["warnings"][0]["code"], "asset_not_resolved")
        self.assertEqual(response["errors"], [])

    def test_multiple_asset_identities_are_ambiguous(self):
        other_agi = token("AGI", "MINT_OTHER_AGI", "Another AGI")
        pool_one = pool(
            "P1",
            self.agi,
            self.usdc,
            liquidity=1000,
            volume24h=100,
            txns24h=10,
            holders=100,
            price=1.0,
        )
        pool_two = pool(
            "P2",
            other_agi,
            self.usdc,
            liquidity=2000,
            volume24h=200,
            txns24h=20,
            holders=200,
            price=2.0,
        )

        response = build_market_report_response(
            "AGI",
            [
                (pool_one, "base", self.agi, 90),
                (pool_two, "base", other_agi, 90),
            ],
            SimpleNamespace(xnt_price_usd=None, last_refresh=1.0),
        )

        self.assertEqual(response["status"], AMBIGUOUS)
        self.assertEqual(
            response["data"]["candidate_asset_keys"],
            ["MINT_AGI", "MINT_OTHER_AGI"],
        )
        self.assertEqual(response["warnings"][0]["code"], "asset_ambiguous")
        self.assertEqual(response["asset"], {})

    def test_invalid_match_container_is_error(self):
        response = build_market_report_response(
            "AGI",
            "not resolver matches",
            SimpleNamespace(xnt_price_usd=None, last_refresh=1.0),
        )

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "invalid_market_matches")

    def test_malformed_match_is_explicit_error(self):
        response = build_market_report_response(
            "AGI",
            [("not a pool", "base", self.agi, 90)],
            SimpleNamespace(xnt_price_usd=None, last_refresh=1.0),
        )

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(
            response["errors"][0]["code"],
            "market_report_validation_error",
        )

    def test_chain_is_explicit_for_future_provider_reuse(self):
        response = build_market_report_response(
            "AGI",
            self._complete_matches(),
            SimpleNamespace(xnt_price_usd=None, last_refresh=123.0),
            chain="Solana",
        )

        self.assertEqual(response["chain"], "solana")
        self.assertEqual(response["status"], PARTIAL)

    def test_explicit_observed_at_overrides_catalog_refresh_without_mutating_source(self):
        response = build_market_report_response(
            "AGI",
            self._complete_matches(),
            SimpleNamespace(xnt_price_usd=None, last_refresh=123.0),
            observed_at="2026-08-15T10:40:00Z",
        )

        self.assertEqual(response["observed_at"], "2026-08-15T10:40:00Z")
        self.assertEqual(response["sources"][0]["observed_at"], 123.0)


if __name__ == "__main__":
    unittest.main()
