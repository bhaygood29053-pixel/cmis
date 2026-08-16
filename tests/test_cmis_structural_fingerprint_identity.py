import unittest

from liquidity_scout.providers.x1.structural_fingerprint_identity import (
    evaluate_structural_fingerprint_identity,
)


PROGRAM = "xdex"
POOL = "pool"
ASSET = "asset"
COUNTER = "counter"
OWNER = "owner"


def fp(scope, pool_pos=3, asset_pos=6, counter_pos=7, program=PROGRAM):
    return {
        "program_id": program,
        "scope": scope,
        "pool_position": pool_pos,
        "asset_position": asset_pos,
        "counter_position": counter_pos,
    }


def direction(direction, items):
    signatures = set()
    distributions = []
    for fingerprint, sigs in items:
        signatures.update(sigs)
        distributions.append(
            {
                "fingerprint": fingerprint,
                "signature_count": len(sigs),
                "signature_ratio": 0.0,
                "signatures": list(sigs),
                "is_dominant": False,
            }
        )
    return {
        "direction": direction,
        "transaction_count": len(signatures),
        "fingerprint_distribution": distributions,
    }


def attribution(directions, leading=True):
    return {
        "leading_pair": (
            {
                "asset_account": "asset-vault",
                "asset_mint": ASSET,
                "counter_account": "counter-vault",
                "counter_mint": COUNTER,
                "shared_owner": OWNER,
                "baseline_coverage_ratio": 1.0,
                "baseline_opposite_direction_ratio": 1.0,
                "baseline_stable_directional_pair_candidate": False,
            }
            if leading else None
        ),
        "directions": directions,
        "summary": {
            "variant_legitimacy_proven": False,
            "canonical_vault_mapping_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
        },
    }


def provider(report):
    def _provider(**kwargs):
        return report
    return _provider


def run(report, **kwargs):
    return evaluate_structural_fingerprint_identity(
        pool_address=POOL,
        asset_mint=ASSET,
        start_epoch=100,
        end_epoch=200,
        attribution_provider=provider(report),
        **kwargs,
    )


class StructuralFingerprintIdentityTests(unittest.TestCase):
    def test_outer_inner_same_layout_merge_to_one_structural_identity(self):
        report = attribution([
            direction("SELL", [
                (fp("outer"), ["s1", "s2", "s3", "s4", "s5"]),
                (fp("inner"), ["s6"]),
            ])
        ])
        result = run(report)
        sell = result["directions"][0]
        self.assertEqual(
            sell["dominant_structural_fingerprint_count"], 6
        )
        self.assertEqual(
            sell["dominant_structural_fingerprint_ratio"], 1.0
        )
        self.assertTrue(sell["structural_fingerprint_stable"])

    def test_scope_is_preserved_as_execution_context(self):
        report = attribution([
            direction("SELL", [
                (fp("outer"), ["s1", "s2"]),
                (fp("inner"), ["s3"]),
            ])
        ])
        sell = run(report)["directions"][0]
        scopes = {
            item["scope"]: item["signature_count"]
            for item in sell[
                "dominant_execution_context_distribution"
            ]
        }
        self.assertEqual(scopes, {"inner": 1, "outer": 2})

    def test_scope_only_variant_observed(self):
        report = attribution([
            direction("SELL", [
                (fp("outer"), ["s1", "s2"]),
                (fp("inner"), ["s3", "s4"]),
            ])
        ])
        sell = run(report)["directions"][0]
        self.assertTrue(sell["scope_variation_observed"])
        self.assertTrue(sell["scope_only_variant_observed"])
        self.assertFalse(
            sell["non_scope_structural_variant_observed"]
        )

    def test_account_position_change_remains_structural_variant(self):
        report = attribution([
            direction("SELL", [
                (fp("outer", asset_pos=6, counter_pos=7), ["s1", "s2"]),
                (fp("inner", asset_pos=7, counter_pos=6), ["s3"]),
            ])
        ])
        sell = run(report)["directions"][0]
        self.assertTrue(
            sell["non_scope_structural_variant_observed"]
        )
        self.assertEqual(
            len(sell["structural_fingerprint_distribution"]), 2
        )

    def test_program_change_remains_structural_variant(self):
        report = attribution([
            direction("SELL", [
                (fp("outer", program=PROGRAM), ["s1", "s2"]),
                (fp("inner", program="other"), ["s3"]),
            ])
        ])
        sell = run(report)["directions"][0]
        self.assertTrue(
            sell["non_scope_structural_variant_observed"]
        )

    def test_ratio_threshold_is_not_lowered(self):
        report = attribution([
            direction("SELL", [
                (fp("outer"), ["s1", "s2", "s3", "s4"]),
                (fp("inner", asset_pos=7, counter_pos=6), ["s5"]),
            ])
        ])
        sell = run(report)["directions"][0]
        self.assertEqual(
            sell["dominant_structural_fingerprint_ratio"], 0.8
        )
        self.assertFalse(sell["structural_fingerprint_stable"])

    def test_buy_and_sell_evaluated_independently(self):
        report = attribution([
            direction("BUY", [
                (fp("outer", asset_pos=7, counter_pos=6), ["b1", "b2"]),
            ]),
            direction("SELL", [
                (fp("outer", asset_pos=6, counter_pos=7), ["s1", "s2"]),
            ]),
        ])
        result = run(report)
        self.assertEqual(len(result["directions"]), 2)
        self.assertTrue(
            result["summary"][
                "all_observed_directions_structurally_stable"
            ]
        )

    def test_one_transaction_direction_is_insufficient_by_default(self):
        report = attribution([
            direction("SELL", [
                (fp("outer"), ["s1"]),
            ])
        ])
        sell = run(report)["directions"][0]
        self.assertFalse(sell["sufficient_sample"])
        self.assertFalse(sell["structural_fingerprint_stable"])

    def test_no_candidate_pair_returns_safely(self):
        result = run(attribution([], leading=False))
        self.assertEqual(result["status"], "no_candidate_pair")
        self.assertEqual(result["directions"], [])

    def test_promotion_flags_always_false(self):
        report = attribution([
            direction("SELL", [
                (fp("outer"), ["s1", "s2"]),
            ])
        ])
        result = run(report)
        summary = result["summary"]
        self.assertFalse(summary["structural_identity_promoted"])
        self.assertFalse(summary["canonical_vault_mapping_proven"])
        self.assertFalse(
            summary["canonical_vault_mapping_promoted"]
        )
        self.assertFalse(
            summary["exact_pool_leg_semantics_promoted"]
        )


if __name__ == "__main__":
    unittest.main()
