import unittest

from liquidity_scout.services import (
    ERROR,
    OK,
    PARTIAL,
    UNAVAILABLE,
    build_rank_response,
)


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def quote_token():
    # Deliberately omit a mint so the quote is not treated as a rankable asset
    # by the deterministic aggregation layer.
    return {"symbol": "QUOTE", "name": "Quote Token"}


def pool(
    address,
    asset,
    *,
    liquidity=None,
    volume24h=None,
    volume1h=None,
    txns1h=None,
    holders=None,
    change24=None,
    safety_score=None,
):
    row = {
        "address": address,
        "baseToken": asset,
        "quoteToken": quote_token(),
    }
    for key, value in {
        "liquidity": liquidity,
        "volume24h": volume24h,
        "volume1h": volume1h,
        "txns1h": txns1h,
        "holders": holders,
        "priceChange24h": change24,
        "safetyScore": safety_score,
    }.items():
        if value is not None:
            row[key] = value
    return row


class CMISRankContractTests(unittest.TestCase):
    def setUp(self):
        self.alpha = token("ALPHA", "MintAlpha", "Alpha Token")
        self.beta = token("BETA", "MintBeta", "Beta Token")
        self.gamma = token("GAMMA", "MintGamma", "Gamma Token")

    def _complete_volume_pools(self):
        return [
            pool("A1", self.alpha, liquidity=5000, volume24h=100),
            pool("A2", self.alpha, liquidity=1000, volume24h=500),
            pool("B1", self.beta, liquidity=3000, volume24h=300),
        ]

    def test_complete_volume_ranking_is_ok_and_asset_wide(self):
        response = build_rank_response(
            self._complete_volume_pools(),
            metric="volume",
            source="X1.Ninja/XDEX",
            observed_at=2000.0,
        )

        self.assertEqual(response["service"], "rank")
        self.assertEqual(response["chain"], "x1")
        self.assertEqual(response["status"], OK)
        self.assertEqual(response["asset"], {})
        self.assertEqual(response["data"]["ranked_count"], 2)
        self.assertEqual(response["data"]["returned_count"], 2)
        self.assertEqual(response["data"]["incomplete_count"], 0)

        first, second = response["data"]["rankings"]
        self.assertEqual(first["rank"], 1)
        self.assertEqual(first["symbol"], "ALPHA")
        self.assertEqual(first["mint"], "MintAlpha")
        self.assertEqual(first["value"], 600.0)
        self.assertEqual(first["liquidity_usd"], 6000.0)
        self.assertEqual(first["lp_count"], 2)
        self.assertEqual(first["#LPs"], 2)
        self.assertEqual(second["rank"], 2)
        self.assertEqual(second["symbol"], "BETA")
        self.assertEqual(second["value"], 300.0)
        self.assertEqual(second["#LPs"], 1)

        self.assertTrue(response["confidence"]["complete"])
        self.assertEqual(response["confidence"]["verified_checks"], 2)
        self.assertEqual(response["confidence"]["total_checks"], 2)
        self.assertEqual(response["confidence"]["verification_ratio"], 1.0)
        self.assertEqual(
            response["sources"],
            [{
                "source": "X1.Ninja/XDEX",
                "role": "rank",
                "observed_at": 2000.0,
            }],
        )
        self.assertEqual(response["observed_at"], 2000.0)
        self.assertEqual(response["errors"], [])

    def test_incomplete_metric_excludes_asset_and_marks_ranking_partial(self):
        pools = self._complete_volume_pools()
        pools[-1].pop("volume24h")

        response = build_rank_response(pools, metric="volume")

        self.assertEqual(response["status"], PARTIAL)
        self.assertEqual(response["data"]["ranked_count"], 1)
        self.assertEqual(response["data"]["returned_count"], 1)
        self.assertEqual(response["data"]["rankings"][0]["symbol"], "ALPHA")
        self.assertEqual(response["data"]["incomplete_count"], 1)
        self.assertEqual(
            response["data"]["unranked_incomplete"][0]["symbol"],
            "BETA",
        )
        self.assertIsNone(response["data"]["unranked_incomplete"][0]["value"])
        self.assertFalse(response["confidence"]["complete"])
        self.assertEqual(response["confidence"]["verification_ratio"], 0.5)
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("ranking_metric_incomplete_for_some_assets", codes)

    def test_verified_zero_is_excluded_explicitly_without_making_universe_partial(self):
        pools = self._complete_volume_pools() + [
            pool("G1", self.gamma, liquidity=1000, volume24h=0),
        ]

        response = build_rank_response(pools, metric="volume")

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["data"]["ranked_count"], 2)
        self.assertEqual(response["data"]["excluded_non_positive_count"], 1)
        excluded = response["data"]["unranked_non_positive"][0]
        self.assertEqual(excluded["symbol"], "GAMMA")
        self.assertEqual(excluded["value"], 0.0)
        self.assertEqual(excluded["reason"], "verified_non_positive_value")
        self.assertTrue(response["confidence"]["complete"])
        self.assertEqual(response["confidence"]["verified_checks"], 3)
        self.assertEqual(response["confidence"]["total_checks"], 3)
        self.assertEqual(response["confidence"]["verification_ratio"], 1.0)
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("ranking_verified_non_positive_assets_excluded", codes)

    def test_no_exact_rankable_assets_is_unavailable_not_zero_ranked(self):
        response = build_rank_response(
            [pool("B1", self.beta, liquidity=3000)],
            metric="volume",
        )

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertEqual(response["data"]["rankings"], [])
        self.assertEqual(response["data"]["ranked_count"], 0)
        self.assertEqual(response["data"]["incomplete_count"], 1)
        self.assertIsNone(response["data"]["unranked_incomplete"][0]["value"])
        self.assertFalse(response["confidence"]["complete"])

    def test_liquidity_ranking_preserves_multi_lp_aggregation_and_public_lp_count(self):
        response = build_rank_response(
            self._complete_volume_pools(),
            metric="liquidity",
        )

        self.assertEqual(response["status"], OK)
        first = response["data"]["rankings"][0]
        self.assertEqual(first["symbol"], "ALPHA")
        self.assertEqual(first["value"], 6000.0)
        self.assertEqual(first["#LPs"], 2)

    def test_trending_basis_is_explicit_and_uses_verified_transactions(self):
        response = build_rank_response(
            [
                pool("A1", self.alpha, liquidity=5000, volume1h=100, txns1h=5),
                pool("B1", self.beta, liquidity=3000, volume1h=500, txns1h=2),
            ],
            metric="trending",
        )

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["data"]["trending_basis"], "1h transactions")
        self.assertEqual(response["data"]["rankings"][0]["symbol"], "ALPHA")
        self.assertEqual(response["data"]["rankings"][0]["value"], 5.0)

    def test_limit_changes_returned_rows_not_full_ranked_count(self):
        response = build_rank_response(
            self._complete_volume_pools(),
            metric="volume",
            limit=1,
        )

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["data"]["ranked_count"], 2)
        self.assertEqual(response["data"]["returned_count"], 1)
        self.assertEqual(response["data"]["rankings"][0]["rank"], 1)

    def test_unsupported_metric_is_error(self):
        response = build_rank_response(self._complete_volume_pools(), metric="magic")

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "unsupported_ranking_metric")

    def test_invalid_limit_is_error(self):
        response = build_rank_response(
            self._complete_volume_pools(),
            metric="volume",
            limit=0,
        )

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "invalid_ranking_limit")

    def test_missing_catalog_is_unavailable(self):
        response = build_rank_response(None, metric="volume")

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertEqual(response["data"]["rankings"], [])
        self.assertEqual(response["warnings"][0]["code"], "ranking_catalog_unavailable")

    def test_empty_catalog_is_unavailable(self):
        response = build_rank_response([], metric="volume")

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertEqual(response["warnings"][0]["code"], "ranking_no_rankable_assets")

    def test_invalid_catalog_container_is_error(self):
        response = build_rank_response("not pools", metric="volume")

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "invalid_ranking_catalog")

    def test_malformed_pool_row_fails_closed_as_error(self):
        response = build_rank_response(["not a pool row"], metric="volume")

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "rank_validation_error")

    def test_chain_is_explicit_for_future_provider_reuse(self):
        response = build_rank_response(
            self._complete_volume_pools(),
            metric="volume",
            chain="Solana",
        )

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["chain"], "solana")

    def test_generator_catalog_is_materialized_deterministically(self):
        response = build_rank_response(
            (row for row in self._complete_volume_pools()),
            metric="volume",
        )

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["data"]["rankings"][0]["symbol"], "ALPHA")


if __name__ == "__main__":
    unittest.main()
