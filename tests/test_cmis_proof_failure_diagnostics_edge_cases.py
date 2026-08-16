import unittest

from liquidity_scout.providers.x1.proof_failure_diagnostics import (
    INSUFFICIENT_EVIDENCE,
    diagnose_exact_pool_leg_semantics,
)


class Provider:
    def __init__(self, value):
        self.value = value

    def __call__(self, *args, **kwargs):
        return self.value


def report():
    windows = [
        {
            "label": label,
            "range_proven": True,
            "integrity_verified": True,
            "candidate_pair_count": 0,
        }
        for label in ("1h", "6h", "24h")
    ]
    return {
        "status": "canonical_vault_mapping_unproven",
        "summary": {"exact_pool_leg_semantics_proven": False},
        "errors": [
            {
                "stage": "canonical_pool_vault_coupling",
                "error": "mapping prerequisite unproven",
            }
        ],
        "coupling": {
            "status": "no_qualified_vault_families",
            "families": [],
            "summary": {"canonical_vault_mapping_proven": False},
            "errors": [],
            "qualification": {
                "status": "no_qualified_family",
                "family_attribution": {
                    "status": "insufficient_family_evidence",
                    "windows": windows,
                    "families": [],
                    "summary": {
                        "all_requested_window_ranges_proven": True,
                        "recurrent_family_structural_conflict_observed": False,
                    },
                },
            },
        },
    }


class ProofFailureDiagnosticsEdgeCases(unittest.TestCase):
    def test_unproven_diagnostic_scan_does_not_claim_pool_activity(self):
        diagnosis = diagnose_exact_pool_leg_semantics(
            report(),
            pool_address="PoolA",
            asset_mint="AssetMint",
            end_epoch=100000.0,
            scanner=Provider(
                {
                    "range_proven": False,
                    "integrity_verified": False,
                    "entries": [],
                }
            ),
        )
        self.assertEqual(diagnosis["proof_outcome"], INSUFFICIENT_EVIDENCE)
        self.assertEqual(
            diagnosis["blocking_code"],
            "DIAGNOSTIC_HISTORY_RANGE_UNPROVEN",
        )
        self.assertNotIn("Pool activity exists", diagnosis["blocking_reason"])


if __name__ == "__main__":
    unittest.main()
