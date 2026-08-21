import unittest
from unittest.mock import patch

from liquidity_scout.cmis.concentration_alert import build_concentration_threshold_alert


CANONICAL_LIMITATIONS = [
    "numeric_change_does_not_establish_accumulation_or_distribution",
    "token_accounts_are_not_unique_holder_identities",
    "observed_top_account_scope_is_incomplete",
    "comparison_requires_same_source_top_n_and_observed_account_count",
    "decimal_share_is_presentation_only_exact_ratio_drives_comparison",
]


def _change():
    return {
        "schema": "cmis_top_account_concentration_change.v1",
        "chain": "x1",
        "asset_id": "mint-1",
        "source": "x1-rpc",
        "scope": "observed_top_token_accounts",
        "requested_account_limit": 20,
        "observed_account_count": 20,
        "before_observed_at": "2026-08-20T19:00:00Z",
        "after_observed_at": "2026-08-20T20:00:00Z",
        "before_share_exact": {"numerator": "1", "denominator": "5"},
        "after_share_exact": {"numerator": "21", "denominator": "100"},
        "delta_share_exact": {"numerator": "1", "denominator": "100"},
        "before_share": "0.2",
        "after_share": "0.21",
        "delta_share": "0.01",
        "delta_bps": "100",
        "direction": "INCREASE",
        "identity_verified": True,
        "scope_complete": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "behavioral_interpretation_verified": False,
        "cmis_promotable": False,
        "limitations": list(CANONICAL_LIMITATIONS),
    }


def _threshold_result(status="EXCEEDS_THRESHOLD"):
    return {
        "chain": "x1",
        "asset_id": "mint-1",
        "source": "x1-rpc",
        "scope": "observed_top_token_accounts",
        "policy": {"absolute_delta_threshold_bps": "100"},
        "direction": "INCREASE",
        "delta_bps": "100",
        "absolute_delta_bps": "100",
        "status": status,
        "threshold_exceeded": status == "EXCEEDS_THRESHOLD",
        "threshold_matched": status == "AT_THRESHOLD",
    }


class ConcentrationThresholdAlertTests(unittest.TestCase):
    def _build(self, **overrides):
        kwargs = {
            "change": _change(),
            "policy_id": "concentration-alert",
            "policy_version": "1.0.0",
            "absolute_delta_threshold_bps": "100",
            "comparator": "GTE",
            "evaluated_at": "2026-08-20T20:05:00Z",
            "max_evidence_age_seconds": 300,
        }
        status = overrides.pop("_status", "EXCEEDS_THRESHOLD")
        kwargs.update(overrides)
        with patch(
            "liquidity_scout.cmis.concentration_alert.evaluate_concentration_threshold",
            return_value=_threshold_result(status),
        ):
            return build_concentration_threshold_alert(**kwargs)

    def test_triggered_alert_is_internal_read_only_and_non_executable(self):
        result = self._build()
        self.assertTrue(result["alert_triggered"])
        self.assertTrue(result["read_only"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["behavioral_interpretation_verified"])
        self.assertFalse(result["risk_interpretation_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_equality_does_not_trigger_gt(self):
        result = self._build(comparator="GT", _status="AT_THRESHOLD")
        self.assertEqual(result["observation"]["condition_state"], "AT_THRESHOLD")
        self.assertFalse(result["alert_triggered"])
        self.assertEqual(result["persistence"]["satisfied_observations"], 0)

    def test_equality_triggers_gte(self):
        result = self._build(comparator="GTE", _status="AT_THRESHOLD")
        self.assertTrue(result["alert_triggered"])
        self.assertEqual(result["policy"]["comparison_symbol"], ">=")

    def test_stale_evidence_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            self._build(evaluated_at="2026-08-20T20:05:00.000001Z")

    def test_freshness_equality_boundary_is_accepted(self):
        result = self._build(evaluated_at="2026-08-20T20:05:00Z")
        self.assertTrue(result["evidence"]["fresh"])
        self.assertEqual(result["evidence"]["age_seconds"], "300")

    def test_evaluation_before_observation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot be earlier"):
            self._build(evaluated_at="2026-08-20T19:59:59Z")

    def test_unsupported_comparator_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "GT or GTE"):
            self._build(comparator="EQ")

    def test_extra_behavioral_label_on_change_is_rejected(self):
        change = _change()
        change["whale"] = True
        with self.assertRaisesRegex(ValueError, "exactly the canonical"):
            self._build(change=change)

    def test_single_observation_persistence_cannot_be_inflated(self):
        result = self._build()
        persistence = result["persistence"]
        self.assertEqual(persistence["required_observations"], 1)
        self.assertEqual(persistence["satisfied_observations"], 1)
        self.assertEqual(len(persistence["evaluated_evidence_ids"]), 1)
        self.assertEqual(len(persistence["triggering_evidence_ids"]), 1)
        self.assertFalse(persistence["duplicate_evidence_can_inflate_count"])

    def test_ids_are_content_addressed_and_deterministic(self):
        first = self._build()
        second = self._build()
        self.assertEqual(first["alert_id"], second["alert_id"])
        self.assertEqual(first["evidence"]["evidence_id"], second["evidence"]["evidence_id"])
        self.assertRegex(first["alert_id"], r"^ca_[0-9a-f]{64}$")
        self.assertRegex(first["evidence"]["evidence_id"], r"^ce_[0-9a-f]{64}$")

    def test_material_policy_change_changes_alert_id_but_not_evidence_id(self):
        first = self._build(comparator="GT")
        second = self._build(comparator="GTE")
        self.assertNotEqual(first["alert_id"], second["alert_id"])
        self.assertEqual(first["evidence"]["evidence_id"], second["evidence"]["evidence_id"])

    def test_material_evidence_change_changes_evidence_and_alert_ids(self):
        first = self._build()
        changed = _change()
        changed["source"] = "x1-rpc-secondary"
        second = self._build(change=changed)
        self.assertNotEqual(first["evidence"]["evidence_id"], second["evidence"]["evidence_id"])
        self.assertNotEqual(first["alert_id"], second["alert_id"])

    def test_receipt_and_proof_ids_remain_unavailable_not_fabricated(self):
        result = self._build()
        self.assertIsNone(result["evidence"]["evidence_receipt_id"])
        self.assertIsNone(result["evidence"]["proof_score_id"])

    def test_not_triggered_has_proven_empty_triggering_evidence(self):
        result = self._build(_status="WITHIN_THRESHOLD")
        self.assertFalse(result["alert_triggered"])
        self.assertEqual(result["persistence"]["triggering_evidence_ids"], [])
        self.assertEqual(result["persistence"]["satisfied_observations"], 0)

    def test_real_existing_evaluator_integration(self):
        result = build_concentration_threshold_alert(
            change=_change(),
            policy_id="concentration-alert",
            policy_version="1.0.0",
            absolute_delta_threshold_bps="100",
            comparator="GTE",
            evaluated_at="2026-08-20T20:05:00Z",
            max_evidence_age_seconds=300,
        )
        self.assertEqual(result["observation"]["condition_state"], "AT_THRESHOLD")
        self.assertTrue(result["alert_triggered"])
        self.assertEqual(result["policy"]["absolute_delta_threshold_bps"], "100")

    def test_missing_threshold_fails_closed_through_existing_evaluator(self):
        with self.assertRaisesRegex(ValueError, "absolute_delta_threshold_bps"):
            build_concentration_threshold_alert(
                change=_change(),
                policy_id="concentration-alert",
                policy_version="1.0.0",
                absolute_delta_threshold_bps=None,
                comparator="GTE",
                evaluated_at="2026-08-20T20:05:00Z",
                max_evidence_age_seconds=300,
            )

    def test_threshold_arguments_are_delegated_to_existing_evaluator(self):
        change = _change()
        with patch(
            "liquidity_scout.cmis.concentration_alert.evaluate_concentration_threshold",
            return_value=_threshold_result(),
        ) as evaluator:
            build_concentration_threshold_alert(
                change=change,
                policy_id="concentration-alert",
                policy_version="1.2.3",
                absolute_delta_threshold_bps="55.5",
                comparator="GT",
                evaluated_at="2026-08-20T20:01:00Z",
                max_evidence_age_seconds=60,
            )
        evaluator.assert_called_once_with(
            change=change,
            policy_id="concentration-alert",
            policy_version="1.2.3",
            absolute_delta_threshold_bps="55.5",
        )


if __name__ == "__main__":
    unittest.main()
