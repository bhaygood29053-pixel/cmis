import unittest

from liquidity_scout.services import (
    PARTIAL,
    UNAVAILABLE,
    build_all_available_history_profile,
    build_all_available_pair_comparison,
    build_historical_compare_response,
)


class FakeHistory:
    def __init__(self, series=None, provider_summary=None):
        self.series = {
            (mint, metric): [dict(item) for item in rows]
            for (mint, metric), rows in (series or {}).items()
        }
        self.provider_summary = dict(provider_summary or {})

    def verified_price_import_summary(self, _mint):
        if self.provider_summary:
            return dict(self.provider_summary)
        return {
            "available": False,
            "observation_count": 0,
            "first_observed_at": None,
            "last_observed_at": None,
            "last_imported_at": None,
            "sources": [],
            "provider_pairs": [],
            "quote_mints": [],
        }

    def record_snapshot_if_due(self, **kwargs):
        mint = kwargs["mint"]
        ts = kwargs.get("timestamp")
        if ts is None:
            return False
        mapping = {
            "price": "price",
            "liquidity": "liquidity",
            "volume": "volume24",
            "transactions": "transactions24",
            "holders": "holders",
            "supply": "total_supply",
        }
        for metric, field in mapping.items():
            value = kwargs.get(field)
            if value is None:
                continue
            rows = self.series.setdefault((mint, metric), [])
            point = {"timestamp": int(ts), "value": float(value)}
            if point not in rows:
                rows.append(point)
                rows.sort(key=lambda item: item["timestamp"])
        return True

    def historical_series(self, mint, metric, *, start_ts=None, end_ts=None):
        rows = [dict(item) for item in self.series.get((mint, metric), [])]
        if start_ts is not None:
            rows = [item for item in rows if item["timestamp"] >= int(start_ts)]
        if end_ts is not None:
            rows = [item for item in rows if item["timestamp"] <= int(end_ts)]
        return rows

    def historical_value_at(self, mint, metric, target_timestamp, *, tolerance_seconds=21600):
        rows = self.historical_series(mint, metric)
        if not rows:
            return None
        target = int(target_timestamp)
        row = min(rows, key=lambda item: abs(item["timestamp"] - target))
        distance = abs(row["timestamp"] - target)
        if distance > int(tolerance_seconds):
            return None
        return {
            "timestamp": row["timestamp"],
            "value": row["value"],
            "target_timestamp": target,
            "distance_seconds": distance,
        }

    @staticmethod
    def percent_change(old_value, new_value):
        if old_value == 0:
            return None
        return ((float(new_value) - float(old_value)) / float(old_value)) * 100.0



class FakeX1RPCProvider:
    def __init__(self):
        self.calls = []

    def get_first_available_block(self):
        return {
            "first_available_block": 5,
            "history_boundary_verified": True,
            "archival_completeness_verified": False,
        }

    def request(self, method, params):
        self.calls.append((method, params))
        if method != "getSignaturesForAddress":
            raise AssertionError(method)
        before = params[1].get("before")
        if before is None:
            return [
                {
                    "signature": "sig2",
                    "slot": 20,
                    "err": None,
                    "blockTime": 2000,
                    "confirmationStatus": "finalized",
                },
                {
                    "signature": "sig1",
                    "slot": 10,
                    "err": None,
                    "blockTime": 1000,
                    "confirmationStatus": "finalized",
                },
            ]
        return []


def snapshot(
    symbol,
    mint,
    *,
    observed_at,
    price,
    liquidity=1000.0,
    volume=100.0,
    transactions=25,
    holders=10,
):
    return {
        "_market_report": {
            "symbol": symbol,
            "mint": mint,
            "price_usd": price,
            "liquidity_usd": liquidity,
            "volume_24h_usd": volume,
            "transactions_24h": transactions,
            "holders": holders,
            "lp_count": 2,
            "completeness": {
                "price": True,
                "liquidity": True,
                "volume_24h": True,
                "transactions_24h": True,
                "holders": True,
            },
            "provenance": {
                "source": "X1.Ninja/XDEX",
                "catalog_last_refresh_unix": observed_at,
            },
        }
    }


class AllAvailableHistoryTests(unittest.TestCase):
    def test_profile_summarizes_every_stored_verified_observation_without_claiming_lifetime(self):
        history = FakeHistory(
            {
                ("AGI_MINT", "price"): [
                    {"timestamp": 1000, "value": 1.0},
                    {"timestamp": 2000, "value": 2.0},
                ],
                ("AGI_MINT", "liquidity"): [
                    {"timestamp": 1000, "value": 100.0},
                    {"timestamp": 2000, "value": 200.0},
                ],
            }
        )

        profile = build_all_available_history_profile(
            snapshot(
                "AGI",
                "AGI_MINT",
                observed_at=4000,
                price=1.5,
                liquidity=150.0,
            ),
            history_backend=history,
            metrics=["price", "liquidity"],
            gap_threshold_seconds=1500,
        )

        self.assertEqual(profile["status"], "partial")
        self.assertEqual(profile["mode"], "all_available")
        self.assertEqual(
            profile["coverage_scope"],
            "cmis_stored_verified_observations",
        )
        self.assertFalse(profile["full_asset_lifetime_verified"])
        self.assertFalse(profile["continuous_coverage_verified"])
        self.assertEqual(profile["first_verified_observed_at"], 1000)
        self.assertEqual(profile["last_verified_observed_at"], 4000)

        price = profile["metrics"]["price"]
        self.assertEqual(price["observation_count"], 3)
        self.assertEqual(price["first_value"], 1.0)
        self.assertEqual(price["last_value"], 1.5)
        self.assertEqual(price["total_change_pct"], 50.0)
        self.assertEqual(price["maximum_value"], 2.0)
        self.assertEqual(price["sampled_max_drawdown_pct"], -25.0)
        self.assertEqual(price["observed_gap_count"], 1)

        liquidity = profile["metrics"]["liquidity"]
        self.assertEqual(liquidity["total_change_pct"], 50.0)
        self.assertIsNone(liquidity["sampled_max_drawdown_pct"])

    def test_cmis_wrapper_returns_partial_with_explicit_lifetime_warning(self):
        history = FakeHistory(
            {
                ("AGI_MINT", "price"): [
                    {"timestamp": 1000, "value": 1.0},
                    {"timestamp": 2000, "value": 2.0},
                ]
            }
        )

        response = build_historical_compare_response(
            None,
            snapshot("AGI", "AGI_MINT", observed_at=3000, price=3.0),
            history_backend=history,
            mode="all_available",
            metrics=["price"],
        )

        self.assertEqual(response["service"], "historical_compare")
        self.assertEqual(response["status"], PARTIAL)
        self.assertEqual(response["data"]["mode"], "all_available")
        self.assertFalse(response["confidence"]["complete"])
        warning_codes = {item["code"] for item in response["warnings"]}
        self.assertIn("asset_lifetime_coverage_unverified", warning_codes)
        self.assertIn(
            "all_available_means_all_verified_observations_currently_stored_by_cmis",
            warning_codes,
        )


    def test_all_available_response_separates_market_and_onchain_coverage(self):
        history = FakeHistory(
            {
                ("AGI_MINT", "price"): [
                    {"timestamp": 1000, "value": 1.0},
                    {"timestamp": 2000, "value": 2.0},
                ]
            }
        )
        rpc = FakeX1RPCProvider()

        response = build_historical_compare_response(
            None,
            snapshot("AGI", "AGI_MINT", observed_at=3000, price=3.0),
            history_backend=history,
            mode="all_available",
            metrics=["price"],
            onchain_coverage_provider=rpc,
            onchain_page_size=1000,
            onchain_max_signatures=5000,
        )

        coverage = response["data"]["coverage"]
        self.assertEqual(
            coverage["market"]["coverage_scope"],
            "cmis_stored_verified_observations",
        )
        self.assertEqual(coverage["onchain"]["status"], "full")
        self.assertEqual(
            coverage["onchain"]["coverage_scope"],
            "x1_rpc_visible_mint_address_history",
        )
        self.assertTrue(
            coverage["onchain"]["rpc_visible_mint_history_complete"]
        )
        self.assertFalse(coverage["onchain"]["asset_wide_activity_verified"])
        self.assertFalse(coverage["onchain"]["full_asset_lifetime_verified"])

        warning_codes = {item["code"] for item in response["warnings"]}
        self.assertIn(
            "mint_address_history_is_not_asset_wide_transfer_history",
            warning_codes,
        )
        self.assertIn(
            "asset_lifetime_coverage_unverified",
            warning_codes,
        )
        onchain_sources = [
            item for item in response["sources"]
            if item.get("role") == "historical_compare.onchain_coverage"
        ]
        self.assertEqual(len(onchain_sources), 1)
        self.assertEqual(onchain_sources[0]["source"], "X1 RPC")


    def test_onchain_coverage_can_be_intentionally_omitted_without_provider_warning(self):
        history = FakeHistory(
            {
                ("AGI_MINT", "price"): [
                    {"timestamp": 1000, "value": 1.0},
                    {"timestamp": 2000, "value": 2.0},
                ]
            }
        )

        response = build_historical_compare_response(
            None,
            snapshot("AGI", "AGI_MINT", observed_at=3000, price=3.0),
            history_backend=history,
            mode="all_available",
            metrics=["price"],
            onchain_coverage_provider=None,
        )

        onchain = response["data"]["coverage"]["onchain"]
        self.assertEqual(onchain["status"], "not_requested")
        self.assertEqual(onchain["reason"], "onchain_coverage_not_requested")
        warning_codes = {item["code"] for item in response["warnings"]}
        self.assertNotIn("x1_rpc_provider_not_configured", warning_codes)
        self.assertNotIn("onchain_coverage_not_requested", warning_codes)


    def test_verified_provider_price_backfill_expands_market_history_without_lifetime_promotion(self):
        history = FakeHistory(
            {
                ("AGI_MINT", "price"): [
                    {"timestamp": 500, "value": 0.5},
                    {"timestamp": 1000, "value": 1.0},
                ]
            },
            provider_summary={
                "available": True,
                "observation_count": 1,
                "first_observed_at": 500,
                "last_observed_at": 500,
                "last_imported_at": 1500,
                "sources": ["XDEX public API + X1.Ninja OHLCV"],
                "provider_pairs": ["AGI_MINT/USDCX"],
                "quote_mints": ["USDCX"],
            },
        )

        response = build_historical_compare_response(
            None,
            snapshot("AGI", "AGI_MINT", observed_at=2000, price=2.0),
            history_backend=history,
            mode="all_available",
            metrics=["price"],
        )

        data = response["data"]
        self.assertEqual(response["status"], PARTIAL)
        self.assertTrue(data["provider_history_imported"])
        self.assertEqual(data["first_verified_observed_at"], 500)
        self.assertEqual(
            data["metrics"]["price"]["provider_backfill_observation_count"],
            1,
        )
        self.assertTrue(
            data["coverage"]["market"]["provider_history_imported"]
        )
        self.assertFalse(data["full_asset_lifetime_verified"])
        self.assertFalse(data["continuous_coverage_verified"])

        roles = {item.get("role") for item in response["sources"]}
        self.assertIn("historical_compare.provider_price_backfill", roles)
        warning_codes = {item["code"] for item in response["warnings"]}
        self.assertIn("verified_provider_price_backfill_is_price_only", warning_codes)
        self.assertIn("provider_source_independence_not_verified", warning_codes)
        self.assertIn("asset_lifetime_coverage_unverified", warning_codes)

    def test_pair_comparison_uses_only_overlapping_verified_window(self):
        history = FakeHistory(
            {
                ("XNT_MINT", "price"): [
                    {"timestamp": 1000, "value": 1.0},
                    {"timestamp": 2000, "value": 1.5},
                ],
                ("ANL_MINT", "price"): [
                    {"timestamp": 2000, "value": 10.0},
                    {"timestamp": 3000, "value": 8.0},
                ],
            }
        )

        comparison = build_all_available_pair_comparison(
            snapshot("XNT", "XNT_MINT", observed_at=4000, price=2.0),
            snapshot("ANL", "ANL_MINT", observed_at=4000, price=5.0),
            history_backend=history,
            metrics=["price"],
            anchor_tolerance_seconds=1,
        )

        self.assertEqual(comparison["status"], "partial")
        self.assertFalse(comparison["full_asset_lifetime_verified"])
        price = comparison["common_window_metrics"]["price"]
        self.assertEqual(price["status"], "ok")
        self.assertEqual(price["start_observed_at"], 2000)
        self.assertEqual(price["end_observed_at"], 4000)
        self.assertAlmostEqual(price["primary_change_pct"], 33.3333333333)
        self.assertEqual(price["secondary_change_pct"], -50.0)
        self.assertAlmostEqual(
            price["performance_difference_pct_points"],
            83.3333333333,
        )

    def test_pair_comparison_fails_closed_without_aligned_common_anchors(self):
        history = FakeHistory(
            {
                ("A", "price"): [
                    {"timestamp": 1000, "value": 1.0},
                    {"timestamp": 4000, "value": 2.0},
                ],
                ("B", "price"): [
                    {"timestamp": 2500, "value": 10.0},
                    {"timestamp": 4000, "value": 5.0},
                ],
            }
        )

        comparison = build_all_available_pair_comparison(
            snapshot("A", "A", observed_at=4000, price=2.0),
            snapshot("B", "B", observed_at=4000, price=5.0),
            history_backend=history,
            metrics=["price"],
            anchor_tolerance_seconds=100,
        )

        self.assertEqual(comparison["status"], UNAVAILABLE)
        self.assertEqual(
            comparison["common_window_metrics"]["price"]["reason"],
            "aligned_common_window_anchors_unavailable",
        )

    def test_invalid_mode_is_explicit_error(self):
        response = build_historical_compare_response(
            None,
            snapshot("AGI", "AGI_MINT", observed_at=3000, price=3.0),
            history_backend=FakeHistory(),
            mode="everything_forever",
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "historical_mode_invalid",
        )


if __name__ == "__main__":
    unittest.main()
