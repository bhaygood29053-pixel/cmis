import unittest

from liquidity_scout.providers.x1.xdex_price_history_import import (
    USDC_X_MINT,
    WRAPPED_XNT_MINT,
    backfill_verified_xdex_usd_price_history,
)


ASSET = "ASSET_MINT"
POOL_DIRECT = "POOL_DIRECT"
POOL_NATIVE = "POOL_NATIVE"
POOL_XNT_USD = "POOL_XNT_USD"


def token(mint):
    return {"mint": mint}


def pool(address, base, quote, liquidity=1000):
    return {
        "address": address,
        "baseToken": token(base),
        "quoteToken": token(quote),
        "liquidity": liquidity,
    }


class FakeHistory:
    def __init__(self):
        self.rows = []

    def record_verified_price_observation(self, **kwargs):
        key = (
            kwargs["mint"],
            kwargs["timestamp"],
            kwargs["source"],
            kwargs["provider_pair"],
        )
        if any(
            (
                row["mint"],
                row["timestamp"],
                row["source"],
                row["provider_pair"],
            ) == key
            for row in self.rows
        ):
            return False
        self.rows.append(dict(kwargs))
        return True

    def verified_price_import_summary(self, mint):
        rows = sorted(
            [row for row in self.rows if row["mint"] == mint],
            key=lambda row: row["timestamp"],
        )
        if not rows:
            return {
                "available": False,
                "observation_count": 0,
                "first_observed_at": None,
                "last_observed_at": None,
            }
        return {
            "available": True,
            "observation_count": len(rows),
            "first_observed_at": rows[0]["timestamp"],
            "last_observed_at": rows[-1]["timestamp"],
        }


def bars(values):
    return [
        {"t": 100, "c": values[0], "o": values[0], "h": values[0], "l": values[0], "v": 0},
        {"t": 160, "c": values[1], "o": values[1], "h": values[1], "l": values[1], "v": 0},
        {"t": 220, "c": values[2], "o": values[2], "h": values[2], "l": values[2], "v": 0},
    ]


def ninja_observation(pool_address, base, quote, values, *, times=(100, 160, 220)):
    candles = [
        {
            "time": ts,
            "open": value,
            "high": value,
            "low": value,
            "close": value,
            "volume": 0,
        }
        for ts, value in zip(times, values)
    ]
    return {
        "pool_address": pool_address,
        "contract": {
            "request_contract_verified": True,
            "response_contract_verified": True,
            "candle_schema_verified": True,
            "request_scope_verified": True,
        },
        "raw_response": {
            "poolAddress": pool_address,
            "baseToken": token(base),
            "quoteToken": token(quote),
            "ohlcv": candles,
        },
    }


class VerifiedXDEXPriceHistoryImportTests(unittest.TestCase):
    def test_direct_stable_quote_imports_only_cross_verified_price_rows(self):
        history = FakeHistory()
        pools = [
            pool(POOL_DIRECT, ASSET, USDC_X_MINT),
        ]

        def xdex_fetcher(base, quote, **_kwargs):
            self.assertEqual((base, quote), (ASSET, USDC_X_MINT))
            return bars((1.0, 1.1, 1.2))

        def ninja_fetcher(address, *, timeframe, limit):
            self.assertEqual(address, POOL_DIRECT)
            self.assertEqual(timeframe, "1m")
            self.assertGreaterEqual(limit, 3)
            return ninja_observation(
                POOL_DIRECT,
                ASSET,
                USDC_X_MINT,
                (1.0, 1.1, 1.2),
            )

        result = backfill_verified_xdex_usd_price_history(
            ASSET,
            "TOK",
            catalog_pools=pools,
            history_backend=history,
            time_from=100,
            time_to=220,
            xdex_fetcher=xdex_fetcher,
            ninja_fetcher=ninja_fetcher,
            imported_at=999,
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["method"], "direct_configured_usd_stable_quote")
        self.assertEqual(result["imported_observation_count"], 3)
        self.assertEqual(result["first_imported_observed_at"], 100)
        self.assertEqual(result["last_imported_observed_at"], 220)
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["provider_range_complete_verified"])
        self.assertFalse(result["full_asset_lifetime_verified"])
        self.assertFalse(result["historical_stable_quote_peg_verified"])
        self.assertEqual(
            [row["price_usd"] for row in history.rows],
            [1.0, 1.1, 1.2],
        )
        self.assertTrue(
            all(
                row["evidence"]["schema"] == "xdex_verified_price_backfill.v1"
                for row in history.rows
            )
        )

    def test_two_leg_asset_xnt_times_xnt_usdc_backfills_usd_price(self):
        history = FakeHistory()
        pools = [
            pool(POOL_NATIVE, ASSET, WRAPPED_XNT_MINT, liquidity=2000),
            pool(POOL_XNT_USD, WRAPPED_XNT_MINT, USDC_X_MINT, liquidity=5000),
        ]

        def xdex_fetcher(base, quote, **_kwargs):
            if (base, quote) == (ASSET, WRAPPED_XNT_MINT):
                return bars((2.0, 3.0, 4.0))
            if (base, quote) == (WRAPPED_XNT_MINT, USDC_X_MINT):
                return bars((0.5, 0.5, 0.5))
            raise AssertionError((base, quote))

        def ninja_fetcher(address, *, timeframe, limit):
            self.assertEqual(timeframe, "1m")
            if address == POOL_NATIVE:
                return ninja_observation(
                    POOL_NATIVE,
                    ASSET,
                    WRAPPED_XNT_MINT,
                    (2.0, 3.0, 4.0),
                )
            if address == POOL_XNT_USD:
                return ninja_observation(
                    POOL_XNT_USD,
                    WRAPPED_XNT_MINT,
                    USDC_X_MINT,
                    (0.5, 0.5, 0.5),
                )
            raise AssertionError(address)

        result = backfill_verified_xdex_usd_price_history(
            ASSET,
            "TOK",
            catalog_pools=pools,
            history_backend=history,
            time_from=100,
            time_to=220,
            xdex_fetcher=xdex_fetcher,
            ninja_fetcher=ninja_fetcher,
            imported_at=999,
        )

        self.assertEqual(
            result["method"],
            "two_leg_xnt_to_configured_usd_stable_quote",
        )
        self.assertEqual(
            [row["price_usd"] for row in history.rows],
            [1.0, 1.5, 2.0],
        )
        self.assertIn("*", result["provider_pair"])

    def test_close_mismatch_is_not_imported(self):
        history = FakeHistory()
        pools = [pool(POOL_DIRECT, ASSET, USDC_X_MINT)]

        def xdex_fetcher(_base, _quote, **_kwargs):
            return bars((1.0, 1.1, 1.2))

        def ninja_fetcher(_address, *, timeframe, limit):
            return ninja_observation(
                POOL_DIRECT,
                ASSET,
                USDC_X_MINT,
                (1.0, 9.9, 1.2),
            )

        result = backfill_verified_xdex_usd_price_history(
            ASSET,
            "TOK",
            catalog_pools=pools,
            history_backend=history,
            time_from=100,
            time_to=220,
            xdex_fetcher=xdex_fetcher,
            ninja_fetcher=ninja_fetcher,
            imported_at=999,
        )

        self.assertEqual(result["imported_observation_count"], 2)
        self.assertEqual(
            [row["timestamp"] for row in history.rows],
            [100, 220],
        )

    def test_pair_scope_mismatch_fails_closed(self):
        history = FakeHistory()
        pools = [pool(POOL_DIRECT, ASSET, USDC_X_MINT)]

        result = backfill_verified_xdex_usd_price_history(
            ASSET,
            "TOK",
            catalog_pools=pools,
            history_backend=history,
            time_from=100,
            time_to=220,
            xdex_fetcher=lambda *_args, **_kwargs: bars((1.0, 1.1, 1.2)),
            ninja_fetcher=lambda *_args, **_kwargs: ninja_observation(
                POOL_DIRECT,
                "WRONG_BASE",
                USDC_X_MINT,
                (1.0, 1.1, 1.2),
            ),
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["provider_history_imported"])
        self.assertEqual(history.rows, [])

    def test_unverified_writer_or_price_path_remains_unavailable(self):
        no_writer = backfill_verified_xdex_usd_price_history(
            ASSET,
            "TOK",
            catalog_pools=[],
            history_backend=object(),
            time_from=100,
            time_to=220,
        )
        self.assertEqual(
            no_writer["reason"],
            "verified_price_history_writer_unavailable",
        )

        history = FakeHistory()
        no_path = backfill_verified_xdex_usd_price_history(
            ASSET,
            "TOK",
            catalog_pools=[],
            history_backend=history,
            time_from=100,
            time_to=220,
        )
        self.assertEqual(
            no_path["reason"],
            "verified_provider_usd_price_path_unavailable",
        )
        self.assertEqual(history.rows, [])


if __name__ == "__main__":
    unittest.main()
