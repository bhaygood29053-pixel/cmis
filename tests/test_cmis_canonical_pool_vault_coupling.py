import unittest

from liquidity_scout.providers.x1.canonical_pool_vault_coupling import (
    prove_canonical_pool_vault_coupling,
)


POOL = "PoolA"
ASSET_MINT = "AssetMint"
WINDOWS = ("1h", "6h", "24h")


def family_identity(name):
    return {
        "asset_account": f"{name}-asset",
        "counter_account": f"{name}-counter",
        "counter_mint": "WrappedXNT",
        "shared_owner": f"{name}-owner",
    }


def qualified_family(name, *, recurrent=True, conflict=False):
    return {
        "family": family_identity(name),
        "recurrent_pair_family_observed": recurrent,
        "all_requested_window_ranges_proven": True,
        "structural_layout_conflict_observed": conflict,
        "qualified_candidate": True,
        "rejection_reasons": [],
    }


def direction(
    name,
    *,
    program="AmmProgram",
    pool_position=3,
    asset_position=7,
    counter_position=6,
    evidence_windows=3,
    consistent=True,
    conflict=False,
):
    return {
        "direction": name,
        "evidence_window_count": evidence_windows,
        "structural_layout_conflict_observed": conflict,
        "cross_window_dominant_structural_layout_consistent": consistent,
        "stable_dominant_structural_fingerprint": {
            "program_id": program,
            "pool_position": pool_position,
            "asset_position": asset_position,
            "counter_position": counter_position,
        },
        "observations": [],
    }


def attribution_family(
    name,
    *,
    conflict=False,
    buy=None,
    sell=None,
):
    return {
        "family": family_identity(name),
        "observed_window_count": 3,
        "qualifying_evidence_window_count": 3,
        "recurrent_pair_family_observed": True,
        "leader_window_count": 3,
        "structural_layout_conflict_observed": conflict,
        "directions": [
            buy or direction("BUY"),
            sell
            or direction(
                "SELL",
                asset_position=4,
                counter_position=5,
            ),
        ],
    }


def candidate(
    name,
    *,
    coverage=1.0,
    stable=True,
    qualifying=True,
    leading=True,
):
    return {
        "family": family_identity(name),
        "rank": 1 if leading else 2,
        "is_leading_candidate": leading,
        "transaction_occurrence_count": 10,
        "recognized_pool_instruction_transaction_ratio": coverage,
        "opposite_direction_ratio": 1.0,
        "stable_directional_pair_candidate": stable,
        "qualifying_family_evidence": qualifying,
    }


def qualification_report(
    names,
    *,
    ranges=True,
    coverage=None,
    stable=None,
    qualifying=None,
    omit=None,
    attribution_overrides=None,
):
    coverage = coverage or {}
    stable = stable or {}
    qualifying = qualifying or {}
    omit = omit or set()
    attribution_overrides = attribution_overrides or {}

    windows = []
    for label in WINDOWS:
        rows = []
        for index, name in enumerate(names):
            if (name, label) in omit:
                continue
            rows.append(
                candidate(
                    name,
                    coverage=coverage.get((name, label), 1.0),
                    stable=stable.get((name, label), True),
                    qualifying=qualifying.get((name, label), True),
                    leading=index == 0,
                )
            )
        windows.append(
            {
                "label": label,
                "range_proven": ranges,
                "integrity_verified": ranges,
                "candidates": rows,
            }
        )

    attribution_families = []
    for name in names:
        override = attribution_overrides.get(name)
        attribution_families.append(
            override if override is not None else attribution_family(name)
        )

    return {
        "service": "canonical_vault_family_qualification",
        "version": "1.4.8",
        "chain": "x1",
        "pool_address": POOL,
        "asset_mint": ASSET_MINT,
        "status": (
            "qualified_candidate_observed"
            if len(names) == 1
            else "ambiguous_qualified_families"
        ),
        "families": [qualified_family(name) for name in names],
        "summary": {
            "family_attribution_available": True,
            "all_requested_window_ranges_proven": ranges,
            "canonical_vault_family_qualified": len(names) == 1,
        },
        "family_attribution": {
            "service": "vault_pair_family_attribution",
            "version": "1.4.7",
            "windows": windows,
            "families": attribution_families,
            "summary": {
                "all_requested_window_ranges_proven": ranges,
            },
        },
        "errors": [],
    }


class Provider:
    def __init__(self, report):
        self.report = report
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self.report


def run(report):
    provider = Provider(report)
    result = prove_canonical_pool_vault_coupling(
        pool_address=POOL,
        asset_mint=ASSET_MINT,
        end_epoch=100000,
        qualifier_provider=provider,
    )
    return result, provider


class CanonicalPoolVaultCouplingTests(unittest.TestCase):
    def test_single_fully_coupled_family_proves_mapping(self):
        result, provider = run(qualification_report(["A"]))

        self.assertEqual(result["status"], "canonical_pool_vault_coupling_proven")
        self.assertEqual(result["pool_coupled_family_count"], 1)
        self.assertEqual(
            result["canonical_vault_mapping_candidate"],
            family_identity("A"),
        )
        self.assertTrue(result["summary"]["canonical_vault_mapping_proven"])
        self.assertEqual(provider.calls[0]["pool_address"], POOL)

    def test_live_shape_many_rpc_valid_families_selects_only_full_coverage_family(self):
        coverage = {}
        for name in ("B", "C", "D"):
            for label in WINDOWS:
                coverage[(name, label)] = 0.05

        result, _ = run(
            qualification_report(
                ["A", "B", "C", "D"],
                coverage=coverage,
            )
        )

        self.assertEqual(result["status"], "canonical_pool_vault_coupling_proven")
        self.assertEqual(result["pool_coupled_family_count"], 1)
        self.assertEqual(
            result["canonical_vault_mapping_candidate"],
            family_identity("A"),
        )
        rejected = {item["family"]["asset_account"]: item for item in result["families"]}
        self.assertIn(
            "1h_pool_instruction_coverage_incomplete",
            rejected["B-asset"]["rejection_reasons"],
        )

    def test_incomplete_pool_instruction_coverage_rejects_family(self):
        report = qualification_report(
            ["A"],
            coverage={("A", "6h"): 0.999},
        )
        result, _ = run(report)

        self.assertEqual(result["status"], "no_pool_vault_coupling_proven")
        self.assertIn(
            "6h_pool_instruction_coverage_incomplete",
            result["families"][0]["rejection_reasons"],
        )

    def test_missing_required_window_candidate_rejects_family(self):
        result, _ = run(
            qualification_report(["A"], omit={("A", "1h")})
        )

        self.assertIn(
            "1h_candidate_missing",
            result["families"][0]["rejection_reasons"],
        )
        self.assertFalse(result["summary"]["canonical_vault_mapping_proven"])

    def test_unstable_directional_pair_in_any_window_rejects_family(self):
        result, _ = run(
            qualification_report(
                ["A"],
                stable={("A", "24h"): False},
            )
        )

        self.assertIn(
            "24h_directional_pair_unstable",
            result["families"][0]["rejection_reasons"],
        )

    def test_scope_only_full_fingerprint_instability_uses_structural_stability(self):
        report = qualification_report(
            ["A"],
            stable={("A", "6h"): False},
        )

        six_hour_window = next(
            row
            for row in report["family_attribution"]["windows"]
            if row["label"] == "6h"
        )
        six_hour_candidate = six_hour_window["candidates"][0]
        six_hour_candidate[
            "stable_structural_directional_pair_candidate"
        ] = True

        result, _ = run(report)

        self.assertEqual(
            result["status"],
            "canonical_pool_vault_coupling_proven",
        )

        six_hour = next(
            row
            for row in result["families"][0]["window_coupling"]
            if row["window"] == "6h"
        )

        self.assertFalse(
            six_hour["stable_directional_pair_candidate"]
        )
        self.assertTrue(
            six_hour["stable_structural_directional_pair_candidate"]
        )
        self.assertTrue(
            six_hour["pool_instruction_coupled"]
        )

    def test_unqualified_opposite_flow_in_any_window_rejects_family(self):
        result, _ = run(
            qualification_report(
                ["A"],
                qualifying={("A", "6h"): False},
            )
        )

        self.assertIn(
            "6h_opposite_flow_unqualified",
            result["families"][0]["rejection_reasons"],
        )

    def test_cross_window_structural_conflict_rejects_family(self):
        override = attribution_family("A", conflict=True)
        result, _ = run(
            qualification_report(
                ["A"],
                attribution_overrides={"A": override},
            )
        )

        self.assertIn(
            "structural_layout_conflict",
            result["families"][0]["rejection_reasons"],
        )

    def test_inconsistent_pool_position_across_directions_rejects_family(self):
        override = attribution_family(
            "A",
            sell=direction(
                "SELL",
                pool_position=9,
                asset_position=4,
                counter_position=5,
            ),
        )
        result, _ = run(
            qualification_report(
                ["A"],
                attribution_overrides={"A": override},
            )
        )

        self.assertIn(
            "pool_position_inconsistent",
            result["families"][0]["rejection_reasons"],
        )

    def test_inconsistent_program_across_directions_rejects_family(self):
        override = attribution_family(
            "A",
            sell=direction(
                "SELL",
                program="OtherProgram",
                asset_position=4,
                counter_position=5,
            ),
        )
        result, _ = run(
            qualification_report(
                ["A"],
                attribution_overrides={"A": override},
            )
        )

        self.assertIn(
            "recognized_program_inconsistent",
            result["families"][0]["rejection_reasons"],
        )

    def test_two_fully_coupled_families_fail_closed_as_ambiguous(self):
        result, _ = run(qualification_report(["A", "B"]))

        self.assertEqual(result["status"], "ambiguous_pool_vault_coupling")
        self.assertEqual(result["pool_coupled_family_count"], 2)
        self.assertIsNone(result["canonical_vault_mapping_candidate"])
        self.assertFalse(result["summary"]["canonical_vault_mapping_proven"])

    def test_unproven_history_blocks_mapping(self):
        result, _ = run(qualification_report(["A"], ranges=False))

        self.assertEqual(result["status"], "insufficient_coupling_evidence")
        self.assertFalse(result["summary"]["canonical_vault_mapping_proven"])

    def test_no_v1_4_8_qualified_families_is_explicit(self):
        report = qualification_report([])
        result, _ = run(report)

        self.assertEqual(result["status"], "no_qualified_vault_families")
        self.assertEqual(result["pool_coupled_family_count"], 0)

    def test_qualifier_exception_is_explicit_and_fails_closed(self):
        def broken(**_kwargs):
            raise RuntimeError("qualification unavailable")

        result = prove_canonical_pool_vault_coupling(
            pool_address=POOL,
            asset_mint=ASSET_MINT,
            end_epoch=100000,
            qualifier_provider=broken,
        )

        self.assertEqual(
            result["status"],
            "vault_family_qualification_unavailable",
        )
        self.assertFalse(
            result["summary"]["vault_family_qualification_available"]
        )
        self.assertEqual(result["errors"][0]["stage"], "vault_family_qualification")

    def test_mapping_proof_does_not_promote_execution_semantics(self):
        result, _ = run(qualification_report(["A"]))
        summary = result["summary"]
        family = result["families"][0]

        self.assertTrue(summary["canonical_vault_mapping_proven"])
        self.assertFalse(summary["canonical_vault_mapping_promoted"])
        self.assertFalse(summary["exact_pool_leg_semantics_promoted"])
        self.assertTrue(family["canonical_vault_mapping_proven"])
        self.assertFalse(family["canonical_vault_mapping_promoted"])
        self.assertFalse(family["exact_pool_leg_semantics_promoted"])

    def test_leading_rank_is_not_used_as_the_proof_gate(self):
        report = qualification_report(["A"])
        for window in report["family_attribution"]["windows"]:
            window["candidates"][0]["is_leading_candidate"] = False
            window["candidates"][0]["rank"] = 7

        result, _ = run(report)

        self.assertEqual(result["status"], "canonical_pool_vault_coupling_proven")
        self.assertTrue(result["summary"]["canonical_vault_mapping_proven"])


if __name__ == "__main__":
    unittest.main()
