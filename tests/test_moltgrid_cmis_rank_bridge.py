import unittest
from unittest.mock import patch

import xdex_rankings
from liquidity_scout.integrations import moltgrid_rank_cmis
from liquidity_scout.services import market_rankings


class FakeGateway:
    def __init__(self):
        self.requests = []

    def dispatch(self, request):
        self.requests.append(request)
        self._assert_request(request)
        metric = request["params"]["metric"]
        limit = request["params"]["limit"]

        rankings = [
            {
                "rank": 1,
                "symbol": "AAA",
                "name": "Asset A",
                "mint": "MINT_AAA",
                "metric": metric,
                "value": 50000 if metric in {"volume", "liquidity"} else 100,
                "liquidity_usd": 70000,
                "liquidity_complete": True,
                "lp_count": 3,
                "#LPs": 3,
            },
            {
                "rank": 2,
                "symbol": "XNT",
                "name": "Wrapped XNT",
                "mint": "MINT_XNT",
                "metric": metric,
                "value": 40000 if metric in {"volume", "liquidity"} else 90,
                "liquidity_usd": 40000,
                "liquidity_complete": True,
                "lp_count": 5,
                "#LPs": 5,
            },
        ]

        return {
            "service": "rank",
            "chain": "x1",
            "status": "partial",
            "asset": {},
            "data": {
                "metric": metric,
                "limit": limit,
                "rankings": rankings[:limit],
                "ranked_count": 2,
                "returned_count": min(limit, 2),
                "incomplete_count": 1,
                "excluded_non_positive_count": 0,
                "trending_basis": None,
                "unranked_incomplete": [
                    {
                        "symbol": "MISS",
                        "name": "Missing Metric",
                        "mint": "MINT_MISS",
                        "value": None,
                        "reason": "requested_metric_incomplete",
                    }
                ],
                "unranked_non_positive": [],
            },
            "risk": None,
            "confidence": {
                "complete": False,
                "verified_checks": 2,
                "total_checks": 3,
            },
            "sources": [
                {
                    "source": "X1.Ninja/XDEX",
                    "role": "rank",
                    "observed_at": 123.0,
                }
            ],
            "observed_at": 123.0,
            "warnings": [
                {
                    "code": "ranking_metric_incomplete_for_some_assets",
                    "message": "1 asset(s) were excluded because the requested ranking metric was incomplete.",
                }
            ],
            "errors": [],
        }

    def _assert_request(self, request):
        if request.get("service") != "rank":
            raise AssertionError(request)
        if request.get("chain") != "x1":
            raise AssertionError(request)
        if request.get("asset") != "":
            raise AssertionError(request)


class MoltGridCMISRankBridgeTests(unittest.TestCase):
    def test_compatibility_shim_stays_pure_outside_moltgrid_runtime(self):
        with patch.object(
            xdex_rankings,
            "_cmis_rank_runtime_enabled",
            return_value=False,
        ):
            self.assertIs(xdex_rankings.format_top, market_rankings.format_top)
            self.assertIs(
                xdex_rankings.find_asset_rank,
                market_rankings.find_asset_rank,
            )
            self.assertIs(xdex_rankings.ranking_row, market_rankings.ranking_row)

    def test_runtime_shim_selects_cmis_rank_adapters(self):
        with patch.object(
            xdex_rankings,
            "_cmis_rank_runtime_enabled",
            return_value=True,
        ):
            self.assertIs(xdex_rankings.format_top, moltgrid_rank_cmis.format_top)
            self.assertIs(
                xdex_rankings.find_asset_rank,
                moltgrid_rank_cmis.find_asset_rank,
            )
            self.assertIs(xdex_rankings.ranking_row, moltgrid_rank_cmis.ranking_row)

    def test_global_rank_calls_public_cmis_rank_service(self):
        gateway = FakeGateway()

        answer = moltgrid_rank_cmis.format_top(
            [],
            metric="volume",
            limit=10,
            gateway=gateway,
        )

        self.assertEqual(len(gateway.requests), 1)
        request = gateway.requests[0]
        self.assertEqual(request["service"], "rank")
        self.assertEqual(request["chain"], "x1")
        self.assertEqual(request["params"], {"metric": "volume", "limit": 10})
        self.assertIn("CMIS / X1.NINJA / XDEX TOP 2", answer)
        self.assertIn("Service status: PARTIAL", answer)
        self.assertIn("#LPs", answer)
        self.assertIn("XNT", answer)
        self.assertIn("Confidence checks: 2/3 verified", answer)
        self.assertIn("Source: X1.Ninja/XDEX (rank) @ 123.0", answer)
        self.assertIn("ranking_metric_incomplete_for_some_assets", answer)

    def test_asset_rank_uses_full_cmis_rank_universe_and_surfaces_partial_state(self):
        gateway = FakeGateway()

        row, total, meta = moltgrid_rank_cmis.find_asset_rank(
            [],
            "MINT_XNT",
            metric="liquidity",
            gateway=gateway,
        )

        self.assertEqual(total, 2)
        self.assertEqual(row["rank"], 2)
        self.assertEqual(row["symbol"], "XNT")
        self.assertEqual(row["pool_count"], 5)
        self.assertEqual(
            gateway.requests[0]["params"],
            {"metric": "liquidity", "limit": 100000},
        )

        visible = moltgrid_rank_cmis.ranking_row(row, "liquidity", meta)
        self.assertIn("#2", visible)
        self.assertIn("XNT", visible)
        self.assertIn("CMIS status: PARTIAL", visible)
        self.assertIn("Full-universe rank is partial", visible)
        self.assertIn("Confidence checks: 2/3 verified", visible)
        self.assertIn("Source: X1.Ninja/XDEX (rank) @ 123.0", visible)

    def test_incomplete_asset_metric_never_receives_fabricated_rank(self):
        gateway = FakeGateway()

        row, total, meta = moltgrid_rank_cmis.find_asset_rank(
            [],
            "MINT_MISS",
            metric="volume",
            gateway=gateway,
        )

        self.assertIsNone(row)
        self.assertEqual(total, 2)
        self.assertEqual(meta["query_status"], "incomplete")


if __name__ == "__main__":
    unittest.main()
