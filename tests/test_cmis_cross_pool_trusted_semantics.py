import unittest

from liquidity_scout.providers.x1.cross_pool_trusted_semantics import (
    BUY_DEFINITION,
    SELL_DEFINITION,
    qualify_cross_pool_trusted_semantics,
)


PROGRAM = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"


def proven_report(
    pool,
    asset,
    *,
    program=PROGRAM,
    pool_position=3,
    asset_account=None,
    counter_account=None,
):
    asset_account = asset_account or f"asset-vault-{pool}"
    counter_account = counter_account or f"counter-vault-{pool}"
    windows = []
    for label, recognized, buy, sell in (
        ("1h", 2, 1, 1),
        ("6h", 6, 3, 3),
        ("24h", 12, 6, 6),
    ):
        windows.append(
            {
                "label": label,
                "recognized_pool_transaction_count": recognized,
                "operation_classified_pool_transaction_count": recognized,
                "proven_swap_transaction_count": recognized,
                "proven_non_swap_transaction_count": 0,
                "unknown_pool_operation_count": 0,
                "buy_transaction_count": buy,
                "sell_transaction_count": sell,
                "operation_classification_ratio": 1.0,
                "semantic_resolution_ratio": 1.0,
                "all_recognized_pool_operations_classified": True,
                "all_proven_swaps_semantically_resolved": True,
                "all_recognized_pool_transactions_semantically_resolved": True,
            }
        )

    return {
        "service": "exact_pool_leg_semantics",
        "version": "1.4.10.3",
        "chain": "x1",
        "pool_address": pool,
        "pair": f"{asset}/XNT",
        "asset_mint": asset,
        "status": "exact_pool_leg_semantics_proven",
        "canonical_vault_mapping": {
            "asset_account": asset_account,
            "counter_account": counter_account,
            "counter_mint": "So11111111111111111111111111111111111111112",
            "shared_owner": "pool-authority",
        },
        "structural_anchor": {
            "program_id": program,
            "pool_position": pool_position,
        },
        "directions": [
            {
                "side": "BUY",
                "semantic_definition": BUY_DEFINITION,
                "side_semantics_proven": True,
                "stable_structural_fingerprint": {
                    "program_id": program,
                    "pool_position": pool_position,
                    "asset_position": 7,
                    "counter_position": 6,
                },
            },
            {
                "side": "SELL",
                "semantic_definition": SELL_DEFINITION,
                "side_semantics_proven": True,
                "stable_structural_fingerprint": {
                    "program_id": program,
                    "pool_position": pool_position,
                    "asset_position": 7,
                    "counter_position": 6,
                },
            },
        ],
        "windows": windows,
        "operation_counts": {
            "recognized": 12,
            "swaps": 12,
            "add_liquidity": 0,
            "remove_liquidity": 0,
            "unknown": 0,
        },
        "summary": {
            "canonical_vault_mapping_proven": True,
            "history_range_proven": True,
            "all_successful_history_transactions_fetched": True,
            "all_required_windows_semantically_complete": True,
            "buy_semantics_proven": True,
            "sell_semantics_proven": True,
            "cross_direction_structural_anchor_consistent": True,
            "amm_operation_classification_available": True,
            "recognized_pool_operation_count": 12,
            "unknown_pool_operation_count": 0,
            "all_recognized_pool_operations_classified": True,
            "exact_pool_leg_semantics_proven": True,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "transaction_execution_enabled": False,
        },
        "proof_diagnosis": {
            "proof_outcome": "PROVEN",
            "blocking_stage": None,
            "blocking_code": None,
            "blocking_reason": "Exact semantics proven.",
            "evidence": {},
            "conflicting_evidence_observed": False,
            "retryable": False,
        },
        "transaction_execution_enabled": False,
    }


def insufficient_report(pool, asset, code="NO_POOL_ACTIVITY_IN_PROOF_WINDOW"):
    return {
        "service": "exact_pool_leg_semantics",
        "version": "1.4.10.3",
        "chain": "x1",
        "pool_address": pool,
        "pair": f"{asset}/XNT",
        "asset_mint": asset,
        "status": "canonical_vault_mapping_unproven",
        "summary": {
            "canonical_vault_mapping_proven": False,
            "exact_pool_leg_semantics_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "transaction_execution_enabled": False,
        },
        "proof_diagnosis": {
            "proof_outcome": "INSUFFICIENT_EVIDENCE",
            "blocking_stage": "vault_pair_discovery",
            "blocking_code": code,
            "blocking_reason": "Not enough current pool evidence.",
            "evidence": {},
            "conflicting_evidence_observed": False,
            "retryable": True,
        },
        "transaction_execution_enabled": False,
    }


def conflicting_report(pool, asset):
    report = insufficient_report(pool, asset)
    report["status"] = "directional_structural_anchor_conflict"
    report["proof_diagnosis"] = {
        "proof_outcome": "CONFLICTING_EVIDENCE",
        "blocking_stage": "exact_pool_leg_semantics",
        "blocking_code": "DIRECTIONAL_STRUCTURAL_ANCHOR_CONFLICT",
        "blocking_reason": "BUY and SELL anchors conflict.",
        "evidence": {},
        "conflicting_evidence_observed": True,
        "retryable": True,
    }
    return report


class CrossPoolTrustedSemanticsTests(unittest.TestCase):
    def test_two_distinct_proven_pools_promote_only_internal_pool_trust(self):
        result = qualify_cross_pool_trusted_semantics(
            [
                proven_report("PoolANL", "MintANL"),
                proven_report("PoolAPEX", "MintAPEX"),
            ]
        )

        self.assertEqual(result["version"], "1.4.11")
        self.assertEqual(result["status"], "trusted_semantics_promoted")
        self.assertEqual(result["proof_diagnosis"]["proof_outcome"], "PROVEN")
        self.assertTrue(result["summary"]["canonical_vault_mapping_promoted"])
        self.assertTrue(result["summary"]["exact_pool_leg_semantics_promoted"])
        self.assertEqual(result["summary"]["promotion_scope"], "qualified_pools_only")
        self.assertEqual(len(result["trusted_pool_profiles"]), 2)
        self.assertTrue(
            result["trusted_semantics_profile"]["future_pool_requires_individual_proof"]
        )
        self.assertFalse(result["transaction_execution_enabled"])
        self.assertFalse(result["signing_enabled"])

    def test_inactive_pool_is_excluded_and_does_not_block_two_proven_pools(self):
        result = qualify_cross_pool_trusted_semantics(
            [
                proven_report("PoolANL", "MintANL"),
                proven_report("PoolAPEX", "MintAPEX"),
                insufficient_report("PoolXENCAT", "MintXENCAT"),
            ]
        )

        self.assertEqual(result["status"], "trusted_semantics_promoted")
        self.assertEqual(result["summary"]["qualified_pool_count"], 2)
        self.assertEqual(result["summary"]["excluded_insufficient_evidence_count"], 1)
        self.assertEqual(
            result["excluded_insufficient_evidence"][0]["blocking_code"],
            "NO_POOL_ACTIVITY_IN_PROOF_WINDOW",
        )
        self.assertNotIn(
            "PoolXENCAT",
            result["trusted_semantics_profile"]["qualified_pool_addresses"],
        )

    def test_one_proven_plus_one_inactive_is_insufficient_not_promoted(self):
        result = qualify_cross_pool_trusted_semantics(
            [
                proven_report("PoolANL", "MintANL"),
                insufficient_report("PoolXENCAT", "MintXENCAT"),
            ]
        )

        self.assertEqual(result["status"], "insufficient_cross_pool_evidence")
        self.assertEqual(
            result["proof_diagnosis"]["blocking_code"],
            "MINIMUM_PROVEN_POOL_COUNT_NOT_MET",
        )
        self.assertFalse(result["summary"]["exact_pool_leg_semantics_promoted"])
        self.assertIsNone(result["trusted_semantics_profile"])

    def test_conflicting_third_pool_blocks_otherwise_sufficient_bundle(self):
        result = qualify_cross_pool_trusted_semantics(
            [
                proven_report("PoolANL", "MintANL"),
                proven_report("PoolAPEX", "MintAPEX"),
                conflicting_report("PoolConflict", "MintConflict"),
            ]
        )

        self.assertEqual(result["status"], "cross_pool_evidence_blocked")
        self.assertEqual(
            result["proof_diagnosis"]["proof_outcome"],
            "CONFLICTING_EVIDENCE",
        )
        self.assertFalse(result["summary"]["canonical_vault_mapping_promoted"])
        self.assertEqual(result["trusted_pool_profiles"], [])

    def test_program_identity_disagreement_blocks_cross_pool_promotion(self):
        result = qualify_cross_pool_trusted_semantics(
            [
                proven_report("PoolANL", "MintANL", program=PROGRAM),
                proven_report("PoolOther", "MintOther", program="DifferentProgram"),
            ]
        )

        self.assertEqual(result["status"], "cross_pool_evidence_blocked")
        self.assertEqual(
            result["proof_diagnosis"]["proof_outcome"],
            "CONFLICTING_EVIDENCE",
        )
        codes = {item["blocking_code"] for item in result["blocking_evidence"]}
        self.assertIn("CROSS_POOL_PROGRAM_ID_CONFLICT", codes)

    def test_pool_positions_may_differ_because_anchors_remain_pool_specific(self):
        result = qualify_cross_pool_trusted_semantics(
            [
                proven_report("PoolANL", "MintANL", pool_position=3),
                proven_report("PoolAPEX", "MintAPEX", pool_position=4),
            ]
        )

        self.assertEqual(result["status"], "trusted_semantics_promoted")
        anchors = {
            item["pool_address"]: item["structural_anchor"]["pool_position"]
            for item in result["trusted_pool_profiles"]
        }
        self.assertEqual(anchors, {"PoolANL": 3, "PoolAPEX": 4})

    def test_duplicate_pool_report_does_not_count_twice(self):
        result = qualify_cross_pool_trusted_semantics(
            [
                proven_report("PoolANL", "MintANL"),
                proven_report("PoolANL", "MintOther"),
                proven_report("PoolAPEX", "MintAPEX"),
            ]
        )

        self.assertEqual(result["status"], "cross_pool_evidence_blocked")
        codes = {item["blocking_code"] for item in result["blocking_evidence"]}
        self.assertIn("DUPLICATE_POOL_REPORT", codes)
        self.assertFalse(result["summary"]["exact_pool_leg_semantics_promoted"])

    def test_same_asset_across_two_pools_does_not_meet_distinct_asset_gate(self):
        result = qualify_cross_pool_trusted_semantics(
            [
                proven_report("PoolOne", "MintSame"),
                proven_report("PoolTwo", "MintSame"),
            ]
        )

        self.assertEqual(result["status"], "insufficient_cross_pool_evidence")
        self.assertEqual(
            result["proof_diagnosis"]["blocking_code"],
            "MINIMUM_DISTINCT_ASSET_COUNT_NOT_MET",
        )

    def test_stale_v14101_report_is_blocked_even_if_it_claims_proven(self):
        report = proven_report("PoolANL", "MintANL")
        report["version"] = "1.4.10.1"
        result = qualify_cross_pool_trusted_semantics(
            [report, proven_report("PoolAPEX", "MintAPEX")]
        )

        self.assertEqual(result["status"], "cross_pool_evidence_blocked")
        codes = {item["blocking_code"] for item in result["blocking_evidence"]}
        self.assertIn("EXACT_REPORT_VERSION_TOO_OLD", codes)

    def test_unknown_operation_in_claimed_proven_report_fails_crosscheck(self):
        bad = proven_report("PoolANL", "MintANL")
        bad["summary"]["unknown_pool_operation_count"] = 1
        bad["operation_counts"]["unknown"] = 1
        result = qualify_cross_pool_trusted_semantics(
            [bad, proven_report("PoolAPEX", "MintAPEX")]
        )

        self.assertEqual(result["status"], "cross_pool_evidence_blocked")
        blocker = next(
            item
            for item in result["blocking_evidence"]
            if item.get("pool_address") == "PoolANL"
        )
        self.assertEqual(blocker["blocking_code"], "PROVEN_REPORT_CROSSCHECK_FAILED")
        self.assertIn("unknown_pool_operations_present", blocker["rejection_reasons"])

    def test_gate_thresholds_cannot_be_lowered_below_cross_pool_minimum(self):
        with self.assertRaises(ValueError):
            qualify_cross_pool_trusted_semantics(
                [proven_report("PoolANL", "MintANL")],
                min_proven_pools=1,
            )
        with self.assertRaises(ValueError):
            qualify_cross_pool_trusted_semantics(
                [
                    proven_report("PoolANL", "MintANL"),
                    proven_report("PoolAPEX", "MintAPEX"),
                ],
                min_distinct_assets=1,
            )


if __name__ == "__main__":
    unittest.main()
