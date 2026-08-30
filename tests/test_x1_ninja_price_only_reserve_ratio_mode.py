import unittest

from liquidity_scout.providers.x1.ninja_price_only_reserve_ratio_mode import (
    ADOPTION,
    ALREADY,
    DEPARTURE,
    NEITHER,
    aggregate_price_only_reserve_ratio_events,
    verify_price_only_reserve_ratio_event,
)


POOL = "Pool111"


def snapshot():
    return {
        "observed_at_start": 1000,
        "observed_at_end": 1001,
    }


def base_evidence(before_price, after_price, *, xnt_slot=0):
    return {
        "service": "x1_ninja_vault_activity_transition",
        "status": "verified",
        "pool_address": POOL,
        "price_changed": True,
        "provider_reserve_changed": False,
        "vault_history_complete_for_window": True,
        "transaction_coverage_complete": True,
        "unique_vault_history_signature_count": 0,
        "verified_vault_transaction_count": 0,
        "price_only_update_observed": True,
        "identity": {
            "xnt_slot": xnt_slot,
        },
        "before_provider": {
            "priceNative": before_price,
            "pooledBase": "100",
            "pooledQuote": "50",
            "lastSyncedAt_raw": "before-sync",
        },
        "after_provider": {
            "priceNative": after_price,
            "pooledBase": "100",
            "pooledQuote": "50",
            "lastSyncedAt_raw": "after-sync",
        },
        "provider_timestamp_candidates": {
            "before_global_lastUpdated_raw": "before-global",
            "after_global_lastUpdated_raw": "after-global",
        },
        "safe_slot_window": {
            "exclusive_lower_slot": 10,
            "inclusive_upper_slot": 20,
        },
    }


def verifier_for(base):
    def verifier(**kwargs):
        return dict(base)
    return verifier


class PriceOnlyReserveRatioModeTests(unittest.TestCase):
    def classify(self, before_price, after_price, **kwargs):
        return verify_price_only_reserve_ratio_event(
            before=snapshot(),
            after=snapshot(),
            pool_address=POOL,
            vault_activity_verifier=verifier_for(
                base_evidence(before_price, after_price, **kwargs)
            ),
        )

    def test_adoption_requires_before_mismatch_after_match(self):
        result = self.classify("0.6", "0.5")
        self.assertEqual(result["classification"], ADOPTION)
        self.assertTrue(result["price_only_update_verified"])
        self.assertTrue(result["gross_reserve_ratio_adoption_verified"])
        self.assertFalse(result["gross_reserve_ratio_departure_observed"])
        self.assertFalse(result["reconciliation_mode_verified"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_departure_is_separate_outcome(self):
        result = self.classify("0.5", "0.6")
        self.assertEqual(result["classification"], DEPARTURE)
        self.assertFalse(result["gross_reserve_ratio_adoption_verified"])
        self.assertTrue(result["gross_reserve_ratio_departure_observed"])

    def test_neither_side_match_is_separate_outcome(self):
        result = self.classify("0.6", "0.7")
        self.assertEqual(result["classification"], NEITHER)
        self.assertTrue(result["non_reserve_price_only_update_observed"])

    def test_already_at_ratio_is_not_adoption(self):
        result = self.classify("0.5000000005", "0.500000001")
        self.assertEqual(result["classification"], ALREADY)
        self.assertTrue(result["already_at_gross_reserve_ratio_observed"])
        self.assertFalse(result["gross_reserve_ratio_adoption_verified"])

    def test_xnt_slot_one_reverses_ratio_orientation(self):
        base = base_evidence("1.5", "2", xnt_slot=1)
        result = verify_price_only_reserve_ratio_event(
            before=snapshot(),
            after=snapshot(),
            pool_address=POOL,
            vault_activity_verifier=verifier_for(base),
        )
        self.assertEqual(
            result["gross_reserve_ratio_native_per_asset"],
            "2",
        )
        self.assertEqual(result["classification"], ADOPTION)

    def test_non_price_only_event_is_not_applicable(self):
        base = base_evidence("0.6", "0.5")
        base["price_only_update_observed"] = False
        base["provider_reserve_changed"] = True
        result = verify_price_only_reserve_ratio_event(
            before=snapshot(),
            after=snapshot(),
            pool_address=POOL,
            vault_activity_verifier=verifier_for(base),
        )
        self.assertEqual(result["status"], "not_applicable")
        self.assertFalse(result["price_only_update_verified"])

    def test_incomplete_vault_history_is_unavailable(self):
        base = base_evidence("0.6", "0.5")
        base["vault_history_complete_for_window"] = False
        result = verify_price_only_reserve_ratio_event(
            before=snapshot(),
            after=snapshot(),
            pool_address=POOL,
            vault_activity_verifier=verifier_for(base),
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["price_only_update_verified"])

    def test_aggregate_promotes_bounded_mode_only_for_five_adoptions(self):
        events = []
        for i in range(5):
            row = self.classify("0.6", "0.5")
            row["pool_address"] = f"Pool{i}"
            row["event_key"] = f"Pool{i}:10:20"
            events.append(row)

        result = aggregate_price_only_reserve_ratio_events(events)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["verified_price_only_event_count"], 5)
        self.assertEqual(result["distinct_event_count"], 5)
        self.assertTrue(result["price_only_update_verified"])
        self.assertTrue(result["gross_reserve_ratio_adoption_verified"])
        self.assertTrue(result["reconciliation_mode_verified"])
        self.assertTrue(result["no_complete_counterexample"])
        self.assertFalse(result["provider_fact_time_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_complete_departure_blocks_reconciliation_mode(self):
        events = []
        for i in range(4):
            row = self.classify("0.6", "0.5")
            row["pool_address"] = f"Pool{i}"
            row["event_key"] = f"Pool{i}:10:20"
            events.append(row)
        departure = self.classify("0.5", "0.6")
        departure["pool_address"] = "Pool4"
        departure["event_key"] = "Pool4:10:20"
        events.append(departure)

        result = aggregate_price_only_reserve_ratio_events(events)
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["price_only_update_verified"])
        self.assertTrue(result["gross_reserve_ratio_departure_observed"])
        self.assertFalse(result["gross_reserve_ratio_adoption_verified"])
        self.assertFalse(result["reconciliation_mode_verified"])
        self.assertFalse(result["no_complete_counterexample"])

    def test_duplicate_event_key_blocks_structural_verification(self):
        events = []
        for i in range(5):
            row = self.classify("0.6", "0.5")
            row["pool_address"] = f"Pool{i}"
            row["event_key"] = "duplicate"
            events.append(row)

        result = aggregate_price_only_reserve_ratio_events(events)
        self.assertFalse(result["price_only_update_verified"])
        self.assertFalse(result["reconciliation_mode_verified"])

    def test_minimum_must_be_five(self):
        with self.assertRaises(ValueError):
            aggregate_price_only_reserve_ratio_events(
                [],
                minimum_verified_events=4,
            )


if __name__ == "__main__":
    unittest.main()
