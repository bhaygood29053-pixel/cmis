import os
import tempfile
import unittest

import historical_metrics


class HistoricalMetricsAllAvailableTests(unittest.TestCase):
    def setUp(self):
        self.original_db = historical_metrics.DB_FILE
        self.tempdir = tempfile.TemporaryDirectory()
        historical_metrics.DB_FILE = os.path.join(
            self.tempdir.name,
            "history.db",
        )

    def tearDown(self):
        historical_metrics.DB_FILE = self.original_db
        self.tempdir.cleanup()

    def test_series_and_explicit_timestamp_lookup_include_transactions(self):
        historical_metrics.record_snapshot(
            "MINT",
            "TOK",
            price=1.0,
            liquidity=100.0,
            volume24=10.0,
            transactions24=20,
            timestamp=1000,
        )
        historical_metrics.record_snapshot(
            "MINT",
            "TOK",
            price=2.0,
            liquidity=200.0,
            volume24=30.0,
            transactions24=40,
            timestamp=2000,
        )

        self.assertEqual(
            historical_metrics.historical_series("MINT", "price"),
            [
                {"timestamp": 1000, "value": 1.0},
                {"timestamp": 2000, "value": 2.0},
            ],
        )
        self.assertEqual(
            historical_metrics.historical_series("MINT", "transactions"),
            [
                {"timestamp": 1000, "value": 20.0},
                {"timestamp": 2000, "value": 40.0},
            ],
        )

        point = historical_metrics.historical_value_at(
            "MINT",
            "price",
            1900,
            tolerance_seconds=200,
        )
        self.assertEqual(point["timestamp"], 2000)
        self.assertEqual(point["value"], 2.0)
        self.assertEqual(point["distance_seconds"], 100)

    def test_snapshot_if_due_prevents_high_frequency_duplicate_rows(self):
        first = historical_metrics.record_snapshot_if_due(
            mint="MINT",
            symbol="TOK",
            price=1.0,
            timestamp=1000,
            min_interval_seconds=300,
        )
        skipped = historical_metrics.record_snapshot_if_due(
            mint="MINT",
            symbol="TOK",
            price=1.1,
            timestamp=1100,
            min_interval_seconds=300,
        )
        second = historical_metrics.record_snapshot_if_due(
            mint="MINT",
            symbol="TOK",
            price=1.2,
            timestamp=1400,
            min_interval_seconds=300,
        )

        self.assertTrue(first)
        self.assertFalse(skipped)
        self.assertTrue(second)
        self.assertEqual(
            historical_metrics.historical_series("MINT", "price"),
            [
                {"timestamp": 1000, "value": 1.0},
                {"timestamp": 1400, "value": 1.2},
            ],
        )


    def test_verified_provider_price_history_preserves_provenance_and_merges_into_price_series(self):
        inserted = historical_metrics.record_verified_price_observation(
            mint="MINT",
            symbol="TOK",
            timestamp=500,
            price_usd=0.5,
            source="XDEX public API + X1.Ninja OHLCV",
            provider_pair="MINT/USDCX",
            quote_mint="USDCX",
            evidence={
                "schema": "xdex_verified_price_backfill.v1",
                "source_independence_verified": False,
            },
            imported_at=900,
        )
        duplicate = historical_metrics.record_verified_price_observation(
            mint="MINT",
            symbol="TOK",
            timestamp=500,
            price_usd=0.5,
            source="XDEX public API + X1.Ninja OHLCV",
            provider_pair="MINT/USDCX",
            quote_mint="USDCX",
            evidence={"schema": "duplicate"},
            imported_at=901,
        )
        historical_metrics.record_snapshot(
            "MINT",
            "TOK",
            price=1.0,
            timestamp=1000,
        )

        self.assertTrue(inserted)
        self.assertFalse(duplicate)
        self.assertEqual(
            historical_metrics.historical_series("MINT", "price"),
            [
                {"timestamp": 500, "value": 0.5},
                {"timestamp": 1000, "value": 1.0},
            ],
        )

        rows = historical_metrics.verified_price_observations("MINT")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "XDEX public API + X1.Ninja OHLCV")
        self.assertEqual(rows[0]["provider_pair"], "MINT/USDCX")
        self.assertEqual(rows[0]["quote_mint"], "USDCX")
        self.assertEqual(
            rows[0]["evidence"]["schema"],
            "xdex_verified_price_backfill.v1",
        )

        summary = historical_metrics.verified_price_import_summary("MINT")
        self.assertTrue(summary["available"])
        self.assertEqual(summary["observation_count"], 1)
        self.assertEqual(summary["stored_row_count"], 1)
        self.assertEqual(summary["usable_observation_count"], 1)
        self.assertEqual(summary["conflicting_timestamp_count"], 0)
        self.assertEqual(summary["first_observed_at"], 500)
        self.assertEqual(summary["last_observed_at"], 500)
        self.assertEqual(summary["last_imported_at"], 900)

    def test_snapshot_price_wins_exact_timestamp_tie_over_provider_backfill(self):
        historical_metrics.record_verified_price_observation(
            mint="MINT",
            symbol="TOK",
            timestamp=1000,
            price_usd=0.5,
            source="provider",
            provider_pair="MINT/USDCX",
            quote_mint="USDCX",
            imported_at=900,
        )
        historical_metrics.record_snapshot(
            "MINT",
            "TOK",
            price=0.75,
            timestamp=1000,
        )

        self.assertEqual(
            historical_metrics.historical_series("MINT", "price"),
            [{"timestamp": 1000, "value": 0.75}],
        )


    def test_conflicting_provider_prices_at_same_timestamp_are_excluded(self):
        historical_metrics.record_verified_price_observation(
            mint="MINT",
            symbol="TOK",
            timestamp=1000,
            price_usd=1.0,
            source="provider-a",
            provider_pair="MINT/USDCX",
            quote_mint="USDCX",
            imported_at=2000,
        )
        historical_metrics.record_verified_price_observation(
            mint="MINT",
            symbol="TOK",
            timestamp=1000,
            price_usd=2.0,
            source="provider-b",
            provider_pair="MINT/XNT*XNT/USDCX",
            quote_mint="USDCX",
            imported_at=2001,
        )

        self.assertEqual(
            historical_metrics.historical_series("MINT", "price"),
            [],
        )
        summary = historical_metrics.verified_price_import_summary("MINT")
        self.assertFalse(summary["available"])
        self.assertEqual(summary["observation_count"], 0)
        self.assertEqual(summary["stored_row_count"], 2)
        self.assertEqual(summary["conflicting_timestamp_count"], 1)
        self.assertIsNone(summary["first_observed_at"])
        self.assertIsNone(summary["last_observed_at"])

    def test_historical_value_at_can_use_verified_provider_price_backfill(self):
        historical_metrics.record_verified_price_observation(
            mint="MINT",
            symbol="TOK",
            timestamp=1000,
            price_usd=1.25,
            source="provider",
            provider_pair="MINT/USDCX",
            quote_mint="USDCX",
            imported_at=2000,
        )

        point = historical_metrics.historical_value_at(
            "MINT",
            "price",
            1010,
            tolerance_seconds=20,
        )
        self.assertEqual(point["timestamp"], 1000)
        self.assertEqual(point["value"], 1.25)
        self.assertEqual(point["distance_seconds"], 10)

    def test_existing_schema_is_migrated_with_transactions_column(self):
        db = historical_metrics.open_db()
        db.execute("DROP TABLE snapshots")
        db.execute(
            """
            CREATE TABLE snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mint TEXT NOT NULL,
                symbol TEXT NOT NULL,
                ts INTEGER NOT NULL,
                price REAL,
                liquidity REAL,
                volume24 REAL,
                holders REAL,
                total_supply REAL,
                pool_count INTEGER
            )
            """
        )
        db.commit()
        db.close()

        migrated = historical_metrics.open_db()
        columns = {
            row[1]
            for row in migrated.execute("PRAGMA table_info(snapshots)").fetchall()
        }
        tables = {
            row[0]
            for row in migrated.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        migrated.close()

        self.assertIn("transactions24", columns)
        self.assertIn("verified_price_observations", tables)


if __name__ == "__main__":
    unittest.main()
