import unittest

from liquidity_scout.providers.x1.exact_pool_leg_semantics_v14104 import (
    prove_exact_pool_leg_semantics,
    refine_per_window_coupling_diagnosis,
)


POOL = "ApexPool"
MINT = "ApexMint"
END = 100000.0
FAMILY = {
    "asset_account": "AssetVault",
    "counter_account": "CounterVault",
    "counter_mint": "WrappedXNT",
    "shared_owner": "PoolAuthority",
}


class Provider:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.value


def window_row(label, *, failure=None):
    row = {
        "window": label,
        "candidate_present": True,
        "range_proven": True,
        "integrity_verified": True,
        "transaction_occurrence_count": 3,
        "recognized_pool_instruction_transaction_ratio": 1.0,
        "required_pool_instruction_transaction_ratio": 1.0,
        "full_pool_instruction_coverage": True,
        "stable_directional_pair_candidate": True,
        "qualifying_family_evidence": True,
        "pool_instruction_coupled": True,
    }
    if failure == "candidate_missing":
        row.update(
            {
                "candidate_present": False,
                "transaction_occurrence_count": 0,
                "recognized_pool_instruction_transaction_ratio": None,
                "full_pool_instruction_coverage": False,
                "stable_directional_pair_candidate": False,
                "qualifying_family_evidence": False,
                "pool_instruction_coupled": False,
            }
        )
    elif failure == "history_unproven":
        row.update({"range_proven": False, "pool_instruction_coupled": False})
    elif failure == "coverage":
        row.update(
            {
                "recognized_pool_instruction_transaction_ratio": 0.8,
                "full_pool_instruction_coverage": False,
                "pool_instruction_coupled": False,
            }
        )
    elif failure == "unstable":
        row.update(
            {
                "stable_directional_pair_candidate": False,
                "pool_instruction_coupled": False,
            }
        )
    elif failure == "flow":
        row.update(
            {
                "qualifying_family_evidence": False,
                "pool_instruction_coupled": False,
            }
        )
    return row


def apex_like_report(*, failures=None, qualified_family_count=1):
    failures = failures or {"1h": "candidate_missing"}
    window_rows = [
        window_row(label, failure=failures.get(label))
        for label in ("1h", "6h", "24h")
    ]
    candidate_counts = {
        label: (0 if failures.get(label) == "candidate_missing" else 3)
        for label in ("1h", "6h", "24h")
    }
    return {
        "service": "exact_pool_leg_semantics",
        "version": "1.4.10.3",
        "chain": "x1",
        "pool_address": POOL,
        "asset_mint": MINT,
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
            "blocking_stage": "canonical_pool_vault_coupling",
            "blocking_code": "CANONICAL_POOL_VAULT_COUPLING_UNPROVEN",
            "blocking_reason": "generic",
            "evidence": {
                "coupling_status": "no_pool_vault_coupling_proven",
                "candidate_pair_counts": candidate_counts,
            },
            "conflicting_evidence_observed": False,
            "retryable": True,
        },
        "coupling": {
            "status": "no_pool_vault_coupling_proven",
            "summary": {
                "qualified_family_count": qualified_family_count,
                "canonical_vault_mapping_proven": False,
            },
            "families": [
                {
                    "family": FAMILY,
                    "v1_4_8_qualified": True,
                    "window_coupling": window_rows,
                    "canonical_pool_vault_coupling_proven": False,
                    "rejection_reasons": [
                        f"{label}_candidate_missing"
                        for label, failure in failures.items()
                        if failure == "candidate_missing"
                    ],
                }
            ],
            "qualification": {
                "status": "qualified_candidate_observed",
                "family_attribution": {
                    "status": "recurrent_pair_family_observed",
                    "windows": [
                        {
                            "label": label,
                            "candidate_pair_count": candidate_counts[label],
                            "range_proven": True,
                            "integrity_verified": True,
                        }
                        for label in ("1h", "6h", "24h")
                    ],
                },
            },
        },
        "transaction_execution_enabled": False,
    }


class ExactPoolLegSemanticsV14104Tests(unittest.TestCase):
    def test_apex_shape_reports_missing_1h_candidate_precisely(self):
        provider = Provider(apex_like_report())
        result = prove_exact_pool_leg_semantics(
            pool_address=POOL,
            asset_mint=MINT,
            end_epoch=END,
            base_provider=provider,
        )

        self.assertEqual(result["version"], "1.4.10.4")
        diagnosis = result["proof_diagnosis"]
        self.assertEqual(
            diagnosis["blocking_code"],
            "REQUIRED_WINDOW_VAULT_CANDIDATE_MISSING",
        )
        self.assertEqual(diagnosis["evidence"]["blocking_windows"], ["1h"])
        self.assertEqual(
            diagnosis["evidence"]["candidate_pair_counts"],
            {"1h": 0, "6h": 3, "24h": 3},
        )
        self.assertEqual(
            diagnosis["evidence"]["qualified_family"],
            FAMILY,
        )
        self.assertFalse(diagnosis["conflicting_evidence_observed"])
        self.assertTrue(diagnosis["retryable"])
        self.assertFalse(result["summary"]["canonical_vault_mapping_promoted"])
        self.assertFalse(result["summary"]["exact_pool_leg_semantics_promoted"])
        self.assertFalse(result["transaction_execution_enabled"])
        self.assertFalse(result["signing_enabled"])

    def test_missing_candidate_in_multiple_windows_lists_each_window(self):
        result = refine_per_window_coupling_diagnosis(
            apex_like_report(
                failures={"1h": "candidate_missing", "6h": "candidate_missing"}
            )
        )
        self.assertEqual(
            result["blocking_code"],
            "REQUIRED_WINDOW_VAULT_CANDIDATE_MISSING",
        )
        self.assertEqual(result["evidence"]["blocking_windows"], ["1h", "6h"])

    def test_incomplete_instruction_coverage_has_distinct_code(self):
        result = refine_per_window_coupling_diagnosis(
            apex_like_report(failures={"1h": "coverage"})
        )
        self.assertEqual(
            result["blocking_code"],
            "REQUIRED_WINDOW_POOL_INSTRUCTION_COVERAGE_INCOMPLETE",
        )
        self.assertEqual(result["evidence"]["blocking_windows"], ["1h"])

    def test_unstable_directional_pair_has_distinct_code(self):
        result = refine_per_window_coupling_diagnosis(
            apex_like_report(failures={"1h": "unstable"})
        )
        self.assertEqual(
            result["blocking_code"],
            "REQUIRED_WINDOW_DIRECTIONAL_PAIR_UNSTABLE",
        )

    def test_scope_only_full_fingerprint_instability_does_not_block_structural_coupling(self):
        report = apex_like_report(
            failures={"1h": "unstable"}
        )

        rows = report["coupling"]["families"][0]["window_coupling"]

        for row in rows:
            if row["window"] == "1h":
                row[
                    "stable_structural_directional_pair_candidate"
                ] = False
            elif row["window"] == "6h":
                row["stable_directional_pair_candidate"] = False
                row[
                    "stable_structural_directional_pair_candidate"
                ] = True
                row["pool_instruction_coupled"] = True
            elif row["window"] == "24h":
                row[
                    "stable_structural_directional_pair_candidate"
                ] = True

        result = refine_per_window_coupling_diagnosis(report)

        self.assertEqual(
            result["blocking_code"],
            "REQUIRED_WINDOW_DIRECTIONAL_PAIR_UNSTABLE",
        )
        self.assertEqual(
            result["evidence"]["blocking_windows"],
            ["1h"],
        )

        failures = result["evidence"]["window_failures"]
        self.assertEqual(
            [item["window"] for item in failures],
            ["1h"],
        )

    def test_opposite_flow_failure_has_distinct_code(self):
        result = refine_per_window_coupling_diagnosis(
            apex_like_report(failures={"1h": "flow"})
        )
        self.assertEqual(
            result["blocking_code"],
            "REQUIRED_WINDOW_OPPOSITE_FLOW_UNQUALIFIED",
        )

    def test_mixed_window_failures_use_combined_fail_closed_code(self):
        result = refine_per_window_coupling_diagnosis(
            apex_like_report(
                failures={"1h": "candidate_missing", "6h": "coverage"}
            )
        )
        self.assertEqual(
            result["blocking_code"],
            "REQUIRED_WINDOW_COUPLING_GATES_UNMET",
        )
        self.assertEqual(result["evidence"]["blocking_windows"], ["1h", "6h"])

    def test_xencat_no_activity_diagnosis_is_not_rewritten(self):
        report = apex_like_report()
        report["proof_diagnosis"] = {
            "proof_outcome": "INSUFFICIENT_EVIDENCE",
            "blocking_stage": "vault_pair_discovery",
            "blocking_code": "NO_POOL_ACTIVITY_IN_PROOF_WINDOW",
            "blocking_reason": "inactive",
            "evidence": {"diagnostic_24h_transaction_signature_count": 0},
            "conflicting_evidence_observed": False,
            "retryable": True,
        }
        original = dict(report["proof_diagnosis"])
        self.assertEqual(refine_per_window_coupling_diagnosis(report), original)

    def test_multiple_qualified_families_do_not_get_single_family_diagnosis(self):
        report = apex_like_report(qualified_family_count=2)
        self.assertEqual(
            refine_per_window_coupling_diagnosis(report)["blocking_code"],
            "CANONICAL_POOL_VAULT_COUPLING_UNPROVEN",
        )

    def test_base_provider_receives_proof_arguments(self):
        provider = Provider(apex_like_report())
        prove_exact_pool_leg_semantics(
            pool_address=POOL,
            asset_mint=MINT,
            end_epoch=END,
            pair="APEX/XNT",
            rpc_url="http://rpc",
            page_size=321,
            max_signatures=654,
            base_provider=provider,
            diagnostic_scanner="sentinel",
        )
        _, kwargs = provider.calls[0]
        self.assertEqual(kwargs["pair"], "APEX/XNT")
        self.assertEqual(kwargs["rpc_url"], "http://rpc")
        self.assertEqual(kwargs["page_size"], 321)
        self.assertEqual(kwargs["max_signatures"], 654)
        self.assertEqual(kwargs["diagnostic_scanner"], "sentinel")


if __name__ == "__main__":
    unittest.main()
