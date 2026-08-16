import unittest

from liquidity_scout.providers.x1.vault_pair_family_attribution import (
    evaluate_vault_pair_family_attribution,
)


POOL = "pool"
ASSET = "asset"
PROGRAM = "xdex"


def full_fp(scope, asset_pos, counter_pos):
    return {
        "program_id": PROGRAM,
        "scope": scope,
        "pool_position": 3,
        "asset_position": asset_pos,
        "counter_position": counter_pos,
    }


def direction(count, fingerprint, stable=True):
    return {
        "direction": "X",
        "transaction_count": count,
        "min_direction_occurrences": 2,
        "sufficient_sample": count >= 2,
        "dominant_instruction_fingerprint": fingerprint,
        "dominant_instruction_fingerprint_count": count,
        "dominant_instruction_fingerprint_ratio": 1.0,
        "fingerprint_stable": stable,
    }


def candidate(
    name,
    *,
    occurrences=5,
    opposite=1.0,
    coverage=0.8,
    buy=None,
    sell=None,
    stable=True,
):
    return {
        "asset_account": f"{name}-asset",
        "asset_mint": ASSET,
        "counter_account": f"{name}-counter",
        "counter_mint": f"{name}-mint",
        "shared_owner": f"{name}-owner",
        "transaction_occurrence_count": occurrences,
        "recognized_pool_instruction_transaction_ratio": coverage,
        "buy_direction_count": 0 if buy is None else buy[
            "transaction_count"
        ],
        "sell_direction_count": 0 if sell is None else sell[
            "transaction_count"
        ],
        "same_direction_or_unresolved_count": 0,
        "opposite_direction_count": occurrences,
        "opposite_direction_ratio": opposite,
        "buy_fingerprint": buy or direction(0, None, False),
        "sell_fingerprint": sell or direction(0, None, False),
        "stable_directional_pair_candidate": stable,
    }


def report(candidates, range_proven=True):
    return {
        "range_proven": range_proven,
        "integrity_verified": range_proven,
        "candidate_pairs": candidates,
        "summary": {
            "candidate_pair_count": len(candidates),
            "stable_directional_pair_candidate_count": sum(
                1
                for item in candidates
                if item["stable_directional_pair_candidate"]
            ),
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
    result = evaluate_vault_pair_family_attribution(
        pool_address=POOL,
        asset_mint=ASSET,
        end_epoch=100000,
        directional_provider=provider,
        **kwargs,
    )
    return result, provider


BUY = direction(3, full_fp("outer", 7, 6))
SELL_OUTER = direction(3, full_fp("outer", 6, 7))
SELL_INNER = direction(3, full_fp("inner", 6, 7))


class VaultPairFamilyAttributionTests(unittest.TestCase):
    def test_same_family_across_windows_is_recurrent(self):
        reports = [
            report([candidate("A", buy=BUY, sell=SELL_OUTER)]),
            report([candidate("A", buy=BUY, sell=SELL_OUTER)]),
            report([candidate("A", buy=BUY, sell=SELL_OUTER)]),
        ]
        result, _ = run(reports)
        family = result["families"][0]
        self.assertTrue(family["recurrent_pair_family_observed"])
        self.assertEqual(
            family["qualifying_evidence_window_count"], 3
        )

    def test_multiple_recurring_families_are_preserved(self):
        reports = [
            report([
                candidate("A", buy=BUY, sell=SELL_OUTER),
                candidate("B", buy=BUY, sell=SELL_OUTER),
            ]),
            report([
                candidate("A", buy=BUY, sell=SELL_OUTER),
                candidate("B", buy=BUY, sell=SELL_OUTER),
            ]),
            report([
                candidate("B", buy=BUY, sell=SELL_OUTER),
                candidate("A", buy=BUY, sell=SELL_OUTER),
            ]),
        ]
        result, _ = run(reports)
        self.assertEqual(
            result["summary"]["recurrent_pair_family_count"], 2
        )
        self.assertTrue(
            result["summary"][
                "multiple_recurrent_pair_families_observed"
            ]
        )

    def test_leader_change_can_be_explained_by_recurrent_families(self):
        reports = [
            report([
                candidate("A", buy=BUY, sell=SELL_OUTER),
                candidate("B", buy=BUY, sell=SELL_OUTER),
            ]),
            report([
                candidate("A", buy=BUY, sell=SELL_OUTER),
                candidate("B", buy=BUY, sell=SELL_OUTER),
            ]),
            report([
                candidate("B", buy=BUY, sell=SELL_OUTER),
                candidate("A", buy=BUY, sell=SELL_OUTER),
            ]),
        ]
        result, _ = run(reports)
        summary = result["summary"]
        self.assertTrue(
            summary["leading_family_changes_across_windows"]
        )
        self.assertTrue(
            summary[
                "leading_change_explained_by_recurrent_families"
            ]
        )

    def test_leader_change_not_explained_by_one_off_family(self):
        reports = [
            report([candidate("A", buy=BUY, sell=SELL_OUTER)]),
            report([candidate("A", buy=BUY, sell=SELL_OUTER)]),
            report([
                candidate("B", buy=BUY, sell=SELL_OUTER),
                candidate("A", buy=BUY, sell=SELL_OUTER),
            ]),
        ]
        result, _ = run(reports)
        self.assertTrue(
            result["summary"][
                "leading_family_changes_across_windows"
            ]
        )
        self.assertFalse(
            result["summary"][
                "leading_change_explained_by_recurrent_families"
            ]
        )

    def test_outer_inner_scope_does_not_create_structural_conflict(self):
        reports = [
            report([candidate("A", sell=SELL_OUTER)]),
            report([candidate("A", sell=SELL_INNER)]),
            report([candidate("A", sell=SELL_OUTER)]),
        ]
        result, _ = run(reports)
        family = result["families"][0]
        sell = family["directions"][1]
        self.assertFalse(
            sell["structural_layout_conflict_observed"]
        )
        self.assertTrue(
            sell[
                "cross_window_dominant_structural_layout_consistent"
            ]
        )

    def test_account_position_change_is_structural_conflict(self):
        changed = direction(3, full_fp("outer", 5, 4))
        reports = [
            report([candidate("A", sell=SELL_OUTER)]),
            report([candidate("A", sell=SELL_OUTER)]),
            report([candidate("A", sell=changed)]),
        ]
        result, _ = run(reports)
        family = result["families"][0]
        self.assertTrue(
            family["structural_layout_conflict_observed"]
        )

    def test_low_opposite_ratio_does_not_qualify_family_evidence(self):
        reports = [
            report([candidate("A", opposite=0.5, sell=SELL_OUTER)]),
            report([candidate("A", opposite=0.5, sell=SELL_OUTER)]),
            report([candidate("A", opposite=0.5, sell=SELL_OUTER)]),
        ]
        result, _ = run(reports)
        self.assertFalse(
            result["families"][0]["recurrent_pair_family_observed"]
        )

    def test_one_window_family_is_not_recurrent(self):
        reports = [
            report([candidate("A", sell=SELL_OUTER)]),
            report([]),
            report([]),
        ]
        result, _ = run(reports)
        self.assertFalse(
            result["families"][0]["recurrent_pair_family_observed"]
        )

    def test_shared_end_time_is_used_for_all_windows(self):
        reports = [report([]), report([]), report([])]
        _result, provider = run(reports)
        self.assertEqual(
            {call["end_epoch"] for call in provider.calls},
            {100000.0},
        )
        self.assertEqual(
            [call["start_epoch"] for call in provider.calls],
            [96400.0, 78400.0, 13600.0],
        )

    def test_unproven_range_blocks_family_model(self):
        reports = [
            report([candidate("A", sell=SELL_OUTER)]),
            report([candidate("A", sell=SELL_OUTER)]),
            report(
                [candidate("A", sell=SELL_OUTER)],
                range_proven=False,
            ),
        ]
        result, _ = run(reports)
        self.assertFalse(
            result["summary"]["all_requested_window_ranges_proven"]
        )
        self.assertFalse(
            result["summary"]["vault_pair_family_model_observed"]
        )

    def test_promotion_flags_always_false(self):
        reports = [
            report([candidate("A", sell=SELL_OUTER)]),
            report([candidate("A", sell=SELL_OUTER)]),
            report([candidate("A", sell=SELL_OUTER)]),
        ]
        result, _ = run(reports)
        summary = result["summary"]
        self.assertFalse(summary["vault_pair_family_model_promoted"])
        self.assertFalse(summary["canonical_vault_mapping_proven"])
        self.assertFalse(
            summary["canonical_vault_mapping_promoted"]
        )
        self.assertFalse(
            summary["exact_pool_leg_semantics_promoted"]
        )


if __name__ == "__main__":
    unittest.main()
