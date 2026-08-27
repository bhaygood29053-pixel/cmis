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
        migrated.close()

        self.assertIn("transactions24", columns)


if __name__ == "__main__":
    unittest.main()
