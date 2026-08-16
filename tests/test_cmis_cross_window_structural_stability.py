import unittest

from liquidity_scout.providers.x1.cross_window_structural_stability import (
    evaluate_cross_window_structural_stability,
)


POOL = "pool"
ASSET = "asset"
PROGRAM = "xdex"


def fp(asset_pos, counter_pos):
    return {
        "program_id": PROGRAM,
        "pool_position": 3,
        "asset_position": asset_pos,
        "counter_position": counter_pos,
    }


def leading(suffix=""):
    return {
        "asset_account": "asset-vault" + suffix,
        "counter_account": "counter-vault" + suffix,
        "counter_mint": "counter-mint",
        "shared_owner": "owner" + suffix,
    }


def report(
    *,
    pair_suffix="",
    buy=None,
    sell=None,
    range_proven=True,
):
    directions = []
    if buy is not None:
        count, fingerprint, stable = buy
        directions.append({
            "direction": "BUY",
            "transaction_count": count,
            "sufficient_sample": count >= 2,
            "dominant_structural_fingerprint": fingerprint,
            "structural_fingerprint_stable": stable,
            "scope_variation_observed": False,
            "scope_only_variant_observed": False,
            "non_scope_structural_variant_observed": False,
        })
    if sell is not None:
        count, fingerprint, stable = sell
        directions.append({
            "direction": "SELL",
            "transaction_count": count,
            "sufficient_sample": count >= 2,
            "dominant_structural_fingerprint": fingerprint,
            "structural_fingerprint_stable": stable,
            "scope_variation_observed": False,
            "scope_only_variant_observed": False,
            "non_scope_structural_variant_observed": False,
        })
    return {
        "status": "stable_structural_identity_observed",
        "leading_pair": leading(pair_suffix),
        "directions": directions,
        "summary": {},
        "source_attribution": {
            "baseline": {
                "range_proven": range_proven,
                "integrity_verified": range_proven,
            },
            "proof_scan": {
                "range_proven": range_proven,
            },
        },
    }


class Provider:
    def __init__(self, reports):
        self.reports = list(reports)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.reports[len(self.calls) - 1]


def run(reports, **kwargs):
    provider = Provider(reports)
    result = evaluate_cross_window_structural_stability(
        pool_address=POOL,
        asset_mint=ASSET,
        end_epoch=100000,
        structural_provider=provider,
        **kwargs,
    )
    return result, provider


class CrossWindowStructuralStabilityTests(unittest.TestCase):
    def stable_reports(self):
        return [
            report(
                buy=(2, fp(7, 6), True),
                sell=(3, fp(6, 7), True),
            ),
            report(
                buy=(5, fp(7, 6), True),
                sell=(8, fp(6, 7), True),
            ),
            report(
                buy=(9, fp(7, 6), True),
                sell=(12, fp(6, 7), True),
            ),
        ]

    def test_same_pair_and_fingerprints_across_windows_are_stable(self):
        result, _ = run(self.stable_reports())
        self.assertTrue(
            result["summary"][
                "cross_window_structural_stability_observed"
            ]
        )
        self.assertTrue(
            result["pair_identity"][
                "cross_window_pair_identity_stable"
            ]
        )

    def test_all_windows_share_exact_end_time(self):
        result, provider = run(self.stable_reports())
        self.assertEqual(len(provider.calls), 3)
        self.assertEqual(
            {call["end_epoch"] for call in provider.calls},
            {100000.0},
        )
        self.assertEqual(
            [call["start_epoch"] for call in provider.calls],
            [96400.0, 78400.0, 13600.0],
        )

    def test_pair_identity_change_is_conflict(self):
        reports = self.stable_reports()
        reports[2] = report(
            pair_suffix="-other",
            buy=(9, fp(7, 6), True),
            sell=(12, fp(6, 7), True),
        )
        result, _ = run(reports)
        self.assertTrue(
            result["pair_identity"][
                "pair_identity_conflict_observed"
            ]
        )
        self.assertEqual(
            result["status"], "cross_window_conflict_observed"
        )

    def test_directional_fingerprint_change_is_conflict(self):
        reports = self.stable_reports()
        reports[2] = report(
            buy=(9, fp(8, 5), True),
            sell=(12, fp(6, 7), True),
        )
        result, _ = run(reports)
        buy = result["directions"][0]
        self.assertTrue(
            buy["structural_fingerprint_conflict_observed"]
        )
        self.assertFalse(
            buy["cross_window_structural_fingerprint_stable"]
        )

    def test_missing_direction_in_one_window_is_not_conflict(self):
        reports = [
            report(sell=(3, fp(6, 7), True)),
            report(
                buy=(5, fp(7, 6), True),
                sell=(8, fp(6, 7), True),
            ),
            report(
                buy=(9, fp(7, 6), True),
                sell=(12, fp(6, 7), True),
            ),
        ]
        result, _ = run(reports)
        buy = result["directions"][0]
        self.assertEqual(buy["evidence_window_count"], 2)
        self.assertTrue(
            buy["cross_window_structural_fingerprint_stable"]
        )

    def test_one_window_direction_is_insufficient_not_conflict(self):
        reports = [
            report(sell=(3, fp(6, 7), True)),
            report(sell=(8, fp(6, 7), True)),
            report(
                buy=(9, fp(7, 6), True),
                sell=(12, fp(6, 7), True),
            ),
        ]
        result, _ = run(reports)
        buy = result["directions"][0]
        self.assertEqual(buy["evidence_window_count"], 1)
        self.assertFalse(
            buy["sufficient_cross_window_evidence"]
        )
        self.assertFalse(
            buy["structural_fingerprint_conflict_observed"]
        )

    def test_unstable_window_blocks_direction_stability(self):
        reports = self.stable_reports()
        reports[1] = report(
            buy=(5, fp(7, 6), False),
            sell=(8, fp(6, 7), True),
        )
        result, _ = run(reports)
        buy = result["directions"][0]
        self.assertFalse(
            buy["all_observed_windows_structurally_stable"]
        )
        self.assertFalse(
            buy["cross_window_structural_fingerprint_stable"]
        )

    def test_unproven_range_blocks_overall_stability(self):
        reports = self.stable_reports()
        reports[2] = report(
            buy=(9, fp(7, 6), True),
            sell=(12, fp(6, 7), True),
            range_proven=False,
        )
        result, _ = run(reports)
        self.assertFalse(
            result["summary"][
                "all_requested_window_ranges_proven"
            ]
        )
        self.assertFalse(
            result["summary"][
                "cross_window_structural_stability_observed"
            ]
        )

    def test_min_evidence_windows_three_is_enforced(self):
        reports = [
            report(sell=(3, fp(6, 7), True)),
            report(
                buy=(5, fp(7, 6), True),
                sell=(8, fp(6, 7), True),
            ),
            report(
                buy=(9, fp(7, 6), True),
                sell=(12, fp(6, 7), True),
            ),
        ]
        result, _ = run(reports, min_evidence_windows=3)
        buy = result["directions"][0]
        self.assertFalse(
            buy["sufficient_cross_window_evidence"]
        )
        sell = result["directions"][1]
        self.assertTrue(
            sell["sufficient_cross_window_evidence"]
        )

    def test_promotion_flags_always_false(self):
        result, _ = run(self.stable_reports())
        summary = result["summary"]
        self.assertFalse(summary["cross_window_identity_promoted"])
        self.assertFalse(summary["canonical_vault_mapping_proven"])
        self.assertFalse(
            summary["canonical_vault_mapping_promoted"]
        )
        self.assertFalse(
            summary["exact_pool_leg_semantics_promoted"]
        )


if __name__ == "__main__":
    unittest.main()
