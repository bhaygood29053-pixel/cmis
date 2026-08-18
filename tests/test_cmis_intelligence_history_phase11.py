from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from liquidity_scout.cmis.intelligence_history import (
    CATEGORIES,
    IntelligenceHistoryLedger,
    build_history_observation,
)


class CMISIntelligenceHistoryPhase11Tests(unittest.TestCase):
    def base(self, **overrides):
        values = {
            "chain": "x1",
            "category": "price",
            "subject_id": "mint-1",
            "metric": "price_usd",
            "value": "0.0012300",
            "unit": "USD",
            "observed_at": "2026-08-18T08:00:00-04:00",
            "source": "X1.Ninja",
            "verification_method": "verified_market_price_v1",
            "evidence_scope": "asset_exact",
            "block_slot": 123,
            "identity_verified": True,
            "semantics_verified": True,
            "freshness_verified": True,
            "scope_complete": False,
            "limitations": [],
        }
        values.update(overrides)
        return values

    def build(self, **overrides):
        return build_history_observation(**self.base(**overrides))

    def ledger(self, directory):
        return IntelligenceHistoryLedger(str(Path(directory) / "history.sqlite3"))

    def test_supported_categories_include_phase11_concentration_and_wallet(self):
        self.assertEqual(
            CATEGORIES,
            {"concentration", "wallet", "price", "liquidity", "supply", "activity"},
        )

    def test_builder_canonicalizes_time_and_content_addresses(self):
        record = self.build()
        self.assertEqual(record["value"], "0.00123")
        self.assertEqual(record["observed_at"], "2026-08-18T12:00:00Z")
        self.assertIsInstance(record["observed_at_epoch"], float)
        self.assertTrue(record["observation_id"].startswith("ih_"))
        self.assertFalse(record["continuous_coverage_proven"])
        self.assertFalse(record["archival_completeness_proven"])
        self.assertFalse(record["interpolation_performed"])
        self.assertFalse(record["missing_samples_filled"])

    def test_requires_verified_identity_and_semantics_with_strict_booleans(self):
        with self.assertRaisesRegex(ValueError, "identity_verified must be verified"):
            self.build(identity_verified=False)
        with self.assertRaisesRegex(ValueError, "semantics_verified must be verified"):
            self.build(semantics_verified=False)
        with self.assertRaisesRegex(ValueError, "identity_verified must be a boolean"):
            self.build(identity_verified=1)
        with self.assertRaisesRegex(ValueError, "freshness_verified"):
            self.build(freshness_verified=1)
        with self.assertRaisesRegex(ValueError, "scope_complete"):
            self.build(scope_complete="false")

    def test_rejects_naive_time_bad_slot_and_non_string_identity_fields(self):
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            self.build(observed_at="2026-08-18T12:00:00")
        with self.assertRaisesRegex(ValueError, "block_slot"):
            self.build(block_slot=-1)
        with self.assertRaisesRegex(ValueError, "subject_id must be a string"):
            self.build(subject_id=123)
        with self.assertRaisesRegex(ValueError, "source must be a string"):
            self.build(source={"name": "provider"})

    def test_nonnegative_categories_reject_negative_but_wallet_can_store_delta(self):
        for category in ("price", "liquidity", "supply", "activity"):
            with self.subTest(category=category):
                with self.assertRaisesRegex(ValueError, "must not be negative"):
                    self.build(category=category, value="-1")
        wallet = self.build(
            category="wallet",
            metric="verified_token_balance_delta",
            value="-4.25",
            unit="token",
            verification_method="verified_wallet_balance_delta_v1",
            evidence_scope="transaction_exact",
        )
        self.assertEqual(wallet["value"], "-4.25")

    def test_concentration_requires_exact_ratio_and_ratio_unit(self):
        with self.assertRaisesRegex(ValueError, "exact_ratio"):
            self.build(category="concentration", metric="top_account_share", value="0.4", unit="ratio")
        with self.assertRaisesRegex(ValueError, "unit must be 'ratio'"):
            self.build(
                category="concentration",
                metric="top_account_share",
                value="0.4",
                unit="percent",
                exact_ratio={"numerator": 2, "denominator": 5},
            )
        record = self.build(
            category="concentration",
            metric="top_account_share",
            value="0.3333333333333333333333333333",
            unit="ratio",
            evidence_scope="top_20_token_accounts",
            exact_ratio={"numerator": 1, "denominator": 3},
        )
        self.assertEqual(record["exact_ratio"], {"numerator": "1", "denominator": "3"})

    def test_concentration_rejects_forged_presentation_ratio(self):
        with self.assertRaisesRegex(ValueError, "does not match exact_ratio"):
            self.build(
                category="concentration",
                metric="top_account_share",
                value="0.9",
                unit="ratio",
                exact_ratio={"numerator": 1, "denominator": 3},
            )

    def test_proof_metadata_is_bounded_and_atomic(self):
        receipt = "er_" + "a" * 64
        record = self.build(
            evidence_receipt_id=receipt,
            proof_strength="strong",
            proof_percent="87.50",
            proof_score_method="deterministic_category_evidence_v1",
        )
        self.assertEqual(record["evidence_receipt_id"], receipt)
        self.assertEqual(record["proof_strength"], "STRONG")
        self.assertEqual(record["proof_percent"], "87.5")
        with self.assertRaisesRegex(ValueError, "content-addressed CMIS receipt"):
            self.build(evidence_receipt_id="er_not_a_hash")
        with self.assertRaisesRegex(ValueError, "supplied together"):
            self.build(proof_strength="WEAK")
        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            self.build(
                proof_strength="WEAK",
                proof_percent="101",
                proof_score_method="deterministic_category_evidence_v1",
            )

    def test_store_is_idempotent_and_rejects_tampering(self):
        with TemporaryDirectory() as directory:
            ledger = self.ledger(directory)
            record = self.build()
            first = ledger.store(record, recorded_at=1000)
            second = ledger.store(record, recorded_at=2000)
            self.assertTrue(first["inserted"])
            self.assertFalse(second["inserted"])
            tampered = deepcopy(record)
            tampered["value"] = "999"
            with self.assertRaisesRegex(ValueError, "content or content-addressed id"):
                ledger.store(tampered)

    def test_find_orders_by_observation_time_not_recording_time(self):
        with TemporaryDirectory() as directory:
            ledger = self.ledger(directory)
            later = self.build(
                value="2",
                observed_at="2026-08-18T13:00:00Z",
                block_slot=200,
            )
            earlier = self.build(
                value="1",
                observed_at="2026-08-18T12:00:00Z",
                block_slot=100,
            )
            ledger.store(later, recorded_at=1)
            ledger.store(earlier, recorded_at=999)
            rows = ledger.find(
                chain="x1",
                category="price",
                subject_id="mint-1",
                metric="price_usd",
            )
            self.assertEqual([row["observation"]["value"] for row in rows], ["1", "2"])

    def test_compare_requires_exact_series_scope_source_unit_and_method(self):
        with TemporaryDirectory() as directory:
            ledger = self.ledger(directory)
            ledger.store(self.build(value="10", observed_at="2026-08-18T12:00:00Z"))
            ledger.store(self.build(value="15", observed_at="2026-08-18T13:00:00Z"))
            ledger.store(
                self.build(
                    value="999",
                    observed_at="2026-08-18T14:00:00Z",
                    source="other-provider",
                )
            )
            result = ledger.compare_first_last(
                chain="x1",
                category="price",
                subject_id="mint-1",
                metric="price_usd",
                unit="USD",
                evidence_scope="asset_exact",
                source="X1.Ninja",
                verification_method="verified_market_price_v1",
            )
            self.assertEqual(result["status"], "OBSERVED_CHANGE")
            self.assertEqual(result["sample_count"], 2)
            self.assertEqual(result["absolute_change"], "5")
            self.assertEqual(result["percent_change"], "50")
            self.assertEqual(result["observed_window"]["start"], "2026-08-18T12:00:00Z")
            self.assertEqual(result["observed_window"]["end"], "2026-08-18T13:00:00Z")
            self.assertFalse(result["continuous_coverage_proven"])
            self.assertFalse(result["archival_completeness_proven"])

    def test_sparse_history_never_interpolates_or_zero_fills(self):
        with TemporaryDirectory() as directory:
            ledger = self.ledger(directory)
            ledger.store(self.build(value="0", observed_at="2026-08-18T12:00:00Z"))
            ledger.store(self.build(value="5", observed_at="2026-08-20T12:00:00Z"))
            result = ledger.compare_first_last(
                chain="x1",
                category="price",
                subject_id="mint-1",
                metric="price_usd",
                unit="USD",
                evidence_scope="asset_exact",
                source="X1.Ninja",
                verification_method="verified_market_price_v1",
            )
            self.assertEqual(result["status"], "OBSERVED_CHANGE")
            self.assertEqual(result["absolute_change"], "5")
            self.assertIsNone(result["percent_change"])
            self.assertFalse(result["interpolation_performed"])
            self.assertFalse(result["missing_samples_filled"])
            self.assertIn("sparse_observation_comparison_only", result["limitations"])

    def test_same_time_boundary_is_ambiguous_not_arbitrarily_ordered(self):
        with TemporaryDirectory() as directory:
            ledger = self.ledger(directory)
            ledger.store(self.build(value="1", observed_at="2026-08-18T12:00:00Z", block_slot=100))
            ledger.store(self.build(value="2", observed_at="2026-08-18T12:00:00Z", block_slot=101))
            result = ledger.compare_first_last(
                chain="x1",
                category="price",
                subject_id="mint-1",
                metric="price_usd",
                unit="USD",
                evidence_scope="asset_exact",
                source="X1.Ninja",
                verification_method="verified_market_price_v1",
            )
            self.assertEqual(result["status"], "AMBIGUOUS_BOUNDARY")
            self.assertIsNone(result["absolute_change"])

    def test_concentration_change_uses_exact_rational_evidence(self):
        with TemporaryDirectory() as directory:
            ledger = self.ledger(directory)
            ledger.store(
                self.build(
                    category="concentration",
                    metric="top_account_share",
                    value="0.3333333333333333333333333333",
                    unit="ratio",
                    observed_at="2026-08-18T12:00:00Z",
                    evidence_scope="top_20_token_accounts",
                    verification_method="verified_top_account_concentration_v1",
                    exact_ratio={"numerator": 1, "denominator": 3},
                )
            )
            ledger.store(
                self.build(
                    category="concentration",
                    metric="top_account_share",
                    value="0.6666666666666666666666666667",
                    unit="ratio",
                    observed_at="2026-08-18T13:00:00Z",
                    evidence_scope="top_20_token_accounts",
                    verification_method="verified_top_account_concentration_v1",
                    exact_ratio={"numerator": 2, "denominator": 3},
                )
            )
            result = ledger.compare_first_last(
                chain="x1",
                category="concentration",
                subject_id="mint-1",
                metric="top_account_share",
                unit="ratio",
                evidence_scope="top_20_token_accounts",
                source="X1.Ninja",
                verification_method="verified_top_account_concentration_v1",
            )
            self.assertEqual(result["status"], "OBSERVED_CHANGE")
            self.assertEqual(result["exact_ratio_change"], {"numerator": "1", "denominator": "3"})
            self.assertEqual(result["percent_change"], "100")

    def test_datetime_input_is_supported_and_canonical(self):
        record = self.build(observed_at=datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(record["observed_at"], "2026-08-18T12:00:00Z")


if __name__ == "__main__":
    unittest.main()
