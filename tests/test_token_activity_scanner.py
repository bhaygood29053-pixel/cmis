import sqlite3
import unittest

from liquidity_scout.tokenomics import (
    collect_signature_window,
    initialize_activity_db,
    scan_token_activity,
)


MINT = "MintA"


def signature(signature, err=None, include_err=True):
    value = {"signature": signature}
    if include_err:
        value["err"] = err
    return value


def parsed_ix(kind, amount, *, mint=MINT):
    info = {
        "mint": mint,
        "account": "TokenAccountA",
        "authority": "AuthorityA",
        "amount": str(amount),
    }
    return {"parsed": {"type": kind, "info": info}}


def transaction(*instructions, err=None, include_err=True, block_time=1700000000):
    meta = {"innerInstructions": []}
    if include_err:
        meta["err"] = err
    return {
        "blockTime": block_time,
        "meta": meta,
        "transaction": {
            "message": {
                "instructions": list(instructions),
            }
        },
    }


class FakeRPC:
    def __init__(self, signature_batches, transactions=None, failures=None):
        self.signature_batches = list(signature_batches)
        self.transactions = dict(transactions or {})
        self.failures = set(failures or [])
        self.signature_calls = 0
        self.transaction_calls = []

    def __call__(self, method, params):
        if method == "getSignaturesForAddress":
            self.signature_calls += 1
            if not self.signature_batches:
                return []
            value = self.signature_batches.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        if method == "getTransaction":
            sig = params[0]
            self.transaction_calls.append(sig)
            if sig in self.failures:
                raise RuntimeError("rpc gap")
            return self.transactions.get(sig)

        raise AssertionError(f"unexpected RPC method: {method}")


class TokenActivitySignatureWindowTests(unittest.TestCase):
    def test_bounded_window_accounts_for_failed_signatures(self):
        rpc = FakeRPC(
            [[
                signature("sig1"),
                signature("sig-failed", err={"InstructionError": [0, "x"]}),
                signature("sig2"),
            ]]
        )

        result = collect_signature_window(rpc, MINT, max_signatures=3)

        self.assertEqual(result["signatures"], ["sig1", "sig2"])
        self.assertEqual(result["history_entries_examined"], 3)
        self.assertTrue(result["selection_complete"])
        self.assertFalse(result["history_exhausted"])
        self.assertEqual(result["coverage_scope"], "bounded")
        self.assertEqual(result["newest_signature"], "sig1")
        self.assertEqual(result["oldest_signature"], "sig2")

    def test_unbounded_window_labels_rpc_history_exhaustion_not_lifetime(self):
        rpc = FakeRPC([
            [signature("sig1")],
        ])

        result = collect_signature_window(rpc, MINT)

        self.assertTrue(result["selection_complete"])
        self.assertTrue(result["history_exhausted"])
        self.assertEqual(result["coverage_scope"], "rpc_history_exhausted")
        self.assertEqual(result["signatures"], ["sig1"])

    def test_zero_length_window_has_none_scope(self):
        rpc = FakeRPC([])

        result = collect_signature_window(rpc, MINT, max_signatures=0)

        self.assertTrue(result["selection_complete"])
        self.assertFalse(result["history_exhausted"])
        self.assertEqual(result["coverage_scope"], "none")
        self.assertEqual(result["history_entries_examined"], 0)

    def test_malformed_signature_metadata_fails_closed(self):
        rpc = FakeRPC(
            [[signature("sig1", include_err=False)]]
        )

        result = collect_signature_window(rpc, MINT, max_signatures=1)

        self.assertFalse(result["selection_complete"])
        self.assertEqual(result["coverage_scope"], "incomplete")
        self.assertEqual(result["malformed_history_entries"], 1)
        self.assertEqual(result["signatures"], [])

    def test_signature_rpc_error_fails_closed(self):
        rpc = FakeRPC([RuntimeError("rate limited")])

        result = collect_signature_window(rpc, MINT, max_signatures=5)

        self.assertFalse(result["selection_complete"])
        self.assertEqual(result["coverage_scope"], "incomplete")
        self.assertEqual(result["selection_rpc_errors"], 1)
        self.assertFalse(result["history_exhausted"])


class TokenActivityDatabaseMigrationTests(unittest.TestCase):
    def test_existing_scan_table_gains_coverage_scope_columns(self):
        db = sqlite3.connect(":memory:")
        try:
            db.execute(
                """
                CREATE TABLE processed_token_activity (
                    mint TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    block_time INTEGER,
                    PRIMARY KEY (mint, signature)
                )
                """
            )
            db.execute(
                """
                INSERT INTO processed_token_activity (
                    mint, signature, block_time
                ) VALUES (?, ?, ?)
                """,
                (MINT, "legacy-sig", 1700000000),
            )
            db.execute(
                """
                CREATE TABLE token_activity_scans (
                    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mint TEXT NOT NULL,
                    max_signatures INTEGER,
                    history_entries_examined INTEGER NOT NULL,
                    signatures_scanned INTEGER NOT NULL,
                    transactions_retrieved INTEGER NOT NULL,
                    rpc_errors INTEGER NOT NULL,
                    selection_complete INTEGER NOT NULL,
                    history_exhausted INTEGER NOT NULL,
                    coverage_verified INTEGER NOT NULL,
                    activity_verified INTEGER NOT NULL,
                    newest_signature TEXT,
                    oldest_signature TEXT
                )
                """
            )
            db.commit()

            initialize_activity_db(db)

            columns = {
                row[1]
                for row in db.execute(
                    "PRAGMA table_info(token_activity_scans)"
                ).fetchall()
            }
            self.assertIn("coverage_scope", columns)
            self.assertIn("lifetime_coverage_verified", columns)
            self.assertIn("lifetime_coverage_reason", columns)
            self.assertIn("time_coverage_verified", columns)
            self.assertIn("time_coverage_reason", columns)
            self.assertIn("coverage_start_time", columns)
            self.assertIn("coverage_end_time", columns)
            self.assertIn("coverage_time_semantics", columns)
            self.assertIn("observed_at", columns)
            self.assertIn("observation_time_semantics", columns)

            processed_columns = {
                row[1]
                for row in db.execute(
                    "PRAGMA table_info(processed_token_activity)"
                ).fetchall()
            }
            self.assertIn("block_time_verified", processed_columns)
            self.assertIn(
                "block_time_validation_semantics",
                processed_columns,
            )
            migrated = db.execute(
                """
                SELECT block_time, block_time_verified,
                       block_time_validation_semantics
                FROM processed_token_activity
                WHERE mint = ? AND signature = ?
                """,
                (MINT, "legacy-sig"),
            ).fetchone()
            self.assertEqual(
                migrated,
                (1700000000, 0, None),
            )
        finally:
            db.close()


class TokenActivityScannerTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        initialize_activity_db(self.db)

    def tearDown(self):
        self.db.close()

    def test_verified_bounded_scan_never_claims_lifetime_coverage(self):
        rpc = FakeRPC(
            [[signature("sig1"), signature("sig2")]],
            transactions={
                "sig1": transaction(
                    parsed_ix("mintTo", "3000000"),
                    block_time=1700000100,
                ),
                "sig2": transaction(
                    parsed_ix("burn", "1250000"),
                    block_time=1700000000,
                ),
            },
        )

        report = scan_token_activity(
            rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=2,
        )

        self.assertTrue(report["activity_verified"])
        self.assertEqual(report["coverage_scope"], "bounded")
        self.assertFalse(report["lifetime_coverage_verified"])
        self.assertEqual(
            report["lifetime_coverage_reason"],
            "bounded_signature_window",
        )
        self.assertEqual(report["minted_tokens_observed"], "3")
        self.assertEqual(report["burned_tokens_observed"], "1.25")
        self.assertEqual(report["net_issuance_tokens"], "1.75")
        self.assertTrue(report["time_coverage_verified"])
        self.assertIsNone(report["time_coverage_reason"])
        self.assertEqual(report["coverage_start_time"], 1700000000)
        self.assertEqual(report["coverage_end_time"], 1700000100)
        self.assertEqual(
            report["coverage_time_semantics"],
            "start_exclusive_end_inclusive",
        )
        self.assertEqual(report["observed_at"], 1700000100)
        self.assertEqual(
            report["observation_time_semantics"],
            "newest_selected_transaction_block_time",
        )
        self.assertEqual(len(report["events"]), 2)
        self.assertEqual(
            report["coverage"]["coverage_scope"],
            "bounded",
        )
        self.assertFalse(report["coverage"]["lifetime_coverage_verified"])
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM token_activity_events"
            ).fetchone()[0],
            2,
        )
        scan = self.db.execute(
            """
            SELECT signatures_scanned, transactions_retrieved,
                   rpc_errors, coverage_verified, activity_verified,
                   newest_signature, oldest_signature, coverage_scope,
                   lifetime_coverage_verified, lifetime_coverage_reason,
                   time_coverage_verified, time_coverage_reason,
                   coverage_start_time, coverage_end_time,
                   coverage_time_semantics, observed_at,
                   observation_time_semantics
            FROM token_activity_scans
            WHERE scan_id = ?
            """,
            (report["scan_id"],),
        ).fetchone()
        self.assertEqual(
            scan,
            (
                2,
                2,
                0,
                1,
                1,
                "sig1",
                "sig2",
                "bounded",
                0,
                "bounded_signature_window",
                1,
                None,
                1700000000,
                1700000100,
                "start_exclusive_end_inclusive",
                1700000100,
                "newest_selected_transaction_block_time",
            ),
        )

    def test_missing_transaction_block_time_withholds_time_coverage(self):
        rpc = FakeRPC(
            [[signature("sig1")]],
            transactions={
                "sig1": transaction(
                    parsed_ix("burn", "500000"),
                    block_time=None,
                ),
            },
        )

        report = scan_token_activity(
            rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=1,
        )

        self.assertTrue(report["activity_verified"])
        self.assertFalse(report["time_coverage_verified"])
        self.assertEqual(
            report["time_coverage_reason"],
            "selected_transaction_block_time_unavailable",
        )
        self.assertIsNone(report["coverage_start_time"])
        self.assertIsNone(report["coverage_end_time"])
        self.assertIsNone(report["observed_at"])

    def test_boolean_block_time_is_not_coerced_by_sqlite(self):
        rpc = FakeRPC(
            [[signature("sig1")]],
            transactions={
                "sig1": transaction(
                    parsed_ix("burn", "500000"),
                    block_time=True,
                ),
            },
        )

        report = scan_token_activity(
            rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=1,
        )

        self.assertTrue(report["activity_verified"])
        self.assertFalse(report["time_coverage_verified"])
        self.assertEqual(
            report["time_coverage_reason"],
            "selected_transaction_block_time_unavailable",
        )
        stored = self.db.execute(
            """
            SELECT block_time
            FROM processed_token_activity
            WHERE mint = ? AND signature = ?
            """,
            (MINT, "sig1"),
        ).fetchone()[0]
        self.assertIsNone(stored)

    def test_numeric_string_block_time_is_not_coerced_by_sqlite(self):
        rpc = FakeRPC(
            [[signature("sig1")]],
            transactions={
                "sig1": transaction(
                    parsed_ix("burn", "500000"),
                    block_time="1700000000",
                ),
            },
        )

        report = scan_token_activity(
            rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=1,
        )

        self.assertTrue(report["activity_verified"])
        self.assertFalse(report["time_coverage_verified"])
        self.assertEqual(
            report["time_coverage_reason"],
            "selected_transaction_block_time_unavailable",
        )
        stored = self.db.execute(
            """
            SELECT block_time
            FROM processed_token_activity
            WHERE mint = ? AND signature = ?
            """,
            (MINT, "sig1"),
        ).fetchone()[0]
        self.assertIsNone(stored)

    def test_non_monotonic_selected_block_times_fail_closed(self):
        rpc = FakeRPC(
            [[signature("newer"), signature("older")]],
            transactions={
                "newer": transaction(
                    parsed_ix("burn", "500000"),
                    block_time=1700000000,
                ),
                "older": transaction(
                    parsed_ix("mintTo", "1000000"),
                    block_time=1700000100,
                ),
            },
        )

        report = scan_token_activity(
            rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=2,
        )

        self.assertTrue(report["activity_verified"])
        self.assertFalse(report["time_coverage_verified"])
        self.assertEqual(
            report["time_coverage_reason"],
            "selected_transaction_block_times_not_monotonic",
        )
        self.assertIsNone(report["observed_at"])
    def test_rpc_history_exhaustion_still_does_not_claim_lifetime(self):
        rpc = FakeRPC(
            [[signature("sig1")]],
            transactions={
                "sig1": transaction(parsed_ix("mintTo", "1000000")),
            },
        )

        report = scan_token_activity(
            rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=None,
        )

        self.assertTrue(report["activity_verified"])
        self.assertEqual(report["coverage_scope"], "rpc_history_exhausted")
        self.assertFalse(report["lifetime_coverage_verified"])
        self.assertEqual(
            report["lifetime_coverage_reason"],
            "rpc_history_exhaustion_not_independent_lifetime_proof",
        )
        self.assertEqual(report["net_issuance_tokens"], "1")

    def test_legacy_cached_timestamp_is_refetched_and_revalidated(self):
        self.db.execute(
            """
            INSERT INTO processed_token_activity (
                mint, signature, block_time, block_time_verified,
                block_time_validation_semantics
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (MINT, "legacy", 1700000000, 0, None),
        )
        self.db.execute(
            """
            INSERT INTO token_activity_events (
                mint, event_key, signature, kind, instruction_type,
                raw_amount, authority, account, block_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                MINT,
                "legacy:top:0",
                "legacy",
                "mint",
                "mintto",
                "999999",
                "AuthorityA",
                "TokenAccountA",
                1700000000,
            ),
        )
        self.db.commit()

        rpc = FakeRPC(
            [[signature("legacy")]],
            transactions={
                "legacy": transaction(
                    parsed_ix("burn", "500000"),
                    block_time=1700000100,
                ),
            },
        )

        report = scan_token_activity(
            rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=1,
        )

        self.assertEqual(rpc.transaction_calls, ["legacy"])
        self.assertTrue(report["activity_verified"])
        self.assertTrue(report["time_coverage_verified"])
        self.assertEqual(report["observed_at"], 1700000100)
        self.assertEqual(report["coverage"]["cached_transactions"], 0)
        self.assertEqual(
            report["coverage"]["unverified_cached_transactions"],
            1,
        )
        self.assertEqual(
            report["coverage"]["revalidated_cached_transactions"],
            1,
        )
        self.assertEqual(
            report["coverage"]["unrevalidated_cached_transactions"],
            0,
        )
        stored = self.db.execute(
            """
            SELECT block_time, block_time_verified,
                   block_time_validation_semantics
            FROM processed_token_activity
            WHERE mint = ? AND signature = ?
            """,
            (MINT, "legacy"),
        ).fetchone()
        self.assertEqual(
            stored,
            (
                1700000100,
                1,
                "strict_raw_rpc_nonnegative_int_v1",
            ),
        )
        rebuilt_event = self.db.execute(
            """
            SELECT kind, instruction_type, raw_amount, block_time
            FROM token_activity_events
            WHERE mint = ? AND event_key = ?
            """,
            (MINT, "legacy:top:0"),
        ).fetchone()
        self.assertEqual(
            rebuilt_event,
            ("burn", "burn", "500000", 1700000100),
        )

    def test_failed_legacy_revalidation_cannot_produce_time_coverage(self):
        self.db.execute(
            """
            INSERT INTO processed_token_activity (
                mint, signature, block_time, block_time_verified,
                block_time_validation_semantics
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (MINT, "legacy", 1700000000, 0, None),
        )
        self.db.execute(
            """
            INSERT INTO token_activity_events (
                mint, event_key, signature, kind, instruction_type,
                raw_amount, authority, account, block_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                MINT,
                "legacy:top:0",
                "legacy",
                "burn",
                "burn",
                "500000",
                "AuthorityA",
                "TokenAccountA",
                1700000000,
            ),
        )
        self.db.commit()

        rpc = FakeRPC(
            [[signature("legacy")]],
            failures={"legacy"},
        )

        report = scan_token_activity(
            rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=1,
        )

        self.assertEqual(rpc.transaction_calls, ["legacy"])
        self.assertFalse(report["coverage_verified"])
        self.assertFalse(report["activity_verified"])
        self.assertFalse(report["time_coverage_verified"])
        self.assertEqual(
            report["time_coverage_reason"],
            "selected_window_coverage_unverified",
        )
        self.assertEqual(report["coverage"]["cached_transactions"], 0)
        self.assertEqual(
            report["coverage"]["unverified_cached_transactions"],
            1,
        )
        self.assertEqual(
            report["coverage"]["revalidated_cached_transactions"],
            0,
        )
        self.assertEqual(
            report["coverage"]["unrevalidated_cached_transactions"],
            1,
        )
        stored = self.db.execute(
            """
            SELECT block_time, block_time_verified,
                   block_time_validation_semantics
            FROM processed_token_activity
            WHERE mint = ? AND signature = ?
            """,
            (MINT, "legacy"),
        ).fetchone()
        self.assertEqual(stored, (1700000000, 0, None))

    def test_cached_rerun_counts_as_retrieved_without_refetch(self):
        first_rpc = FakeRPC(
            [[signature("sig1")]],
            transactions={
                "sig1": transaction(parsed_ix("mintTo", "1000000")),
            },
        )
        first = scan_token_activity(
            first_rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=1,
        )
        self.assertTrue(first["activity_verified"])

        second_rpc = FakeRPC([[signature("sig1")]])
        second = scan_token_activity(
            second_rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=1,
        )

        self.assertTrue(second["activity_verified"])
        self.assertEqual(second["net_issuance_tokens"], "1")
        self.assertEqual(second["coverage"]["cached_transactions"], 1)
        self.assertEqual(
            second["coverage"]["unverified_cached_transactions"],
            0,
        )
        self.assertEqual(
            second["coverage"]["revalidated_cached_transactions"],
            0,
        )
        self.assertEqual(
            second["coverage"]["unrevalidated_cached_transactions"],
            0,
        )
        self.assertEqual(second["coverage"]["transactions_retrieved"], 1)
        self.assertEqual(second_rpc.transaction_calls, [])
        stored = self.db.execute(
            """
            SELECT block_time_verified, block_time_validation_semantics
            FROM processed_token_activity
            WHERE mint = ? AND signature = ?
            """,
            (MINT, "sig1"),
        ).fetchone()
        self.assertEqual(
            stored,
            (1, "strict_raw_rpc_nonnegative_int_v1"),
        )

    def test_transaction_gap_preserves_observed_totals_but_withholds_net(self):
        rpc = FakeRPC(
            [[signature("sig1"), signature("sig2")]],
            transactions={
                "sig1": transaction(parsed_ix("mintTo", "2000000")),
            },
            failures={"sig2"},
        )

        report = scan_token_activity(
            rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=2,
        )

        self.assertEqual(report["minted_tokens_observed"], "2")
        self.assertEqual(report["burned_tokens_observed"], "0")
        self.assertFalse(report["coverage_verified"])
        self.assertFalse(report["activity_verified"])
        self.assertFalse(report["lifetime_coverage_verified"])
        self.assertEqual(
            report["lifetime_coverage_reason"],
            "selected_window_coverage_unverified",
        )
        self.assertIsNone(report["net_issuance_tokens"])
        self.assertEqual(report["coverage"]["transactions_retrieved"], 1)
        self.assertEqual(report["coverage"]["transaction_errors"], 1)
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM processed_token_activity"
            ).fetchone()[0],
            1,
        )

    def test_each_report_is_restricted_to_its_selected_window(self):
        first_rpc = FakeRPC(
            [[signature("old")]],
            transactions={
                "old": transaction(parsed_ix("mintTo", "9000000")),
            },
        )
        scan_token_activity(
            first_rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=1,
        )

        second_rpc = FakeRPC(
            [[signature("new")]],
            transactions={
                "new": transaction(parsed_ix("burn", "500000")),
            },
        )
        report = scan_token_activity(
            second_rpc,
            mint=MINT,
            decimals=6,
            db=self.db,
            max_signatures=1,
        )

        self.assertEqual(report["minted_tokens_observed"], "0")
        self.assertEqual(report["burned_tokens_observed"], "0.5")
        self.assertEqual(report["net_issuance_tokens"], "-0.5")
        self.assertEqual([event["signature"] for event in report["events"]], ["new"])
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM token_activity_events"
            ).fetchone()[0],
            2,
        )


if __name__ == "__main__":
    unittest.main()
