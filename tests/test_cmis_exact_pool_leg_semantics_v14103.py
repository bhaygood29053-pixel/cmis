import unittest

from liquidity_scout.providers.x1 import (
    prove_exact_pool_leg_semantics as public_prover,
)
from liquidity_scout.providers.x1.exact_pool_leg_semantics_v14103 import (
    prove_exact_pool_leg_semantics,
)


POOL = "PoolA"
MINT = "AssetMint"
END = 100000.0
START = END - 86400


class Provider:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.value


def inactive_coupling_report():
    windows = [
        {
            "label": label,
            "range_proven": True,
            "integrity_verified": True,
            "candidate_pair_count": 0,
            "stable_directional_pair_candidate_count": 0,
            "leading_family": None,
            "candidates": [],
        }
        for label in ("1h", "6h", "24h")
    ]
    return {
        "service": "canonical_pool_vault_coupling",
        "version": "1.4.9",
        "status": "no_qualified_vault_families",
        "pool_coupled_family_count": 0,
        "canonical_vault_mapping_candidate": None,
        "families": [],
        "summary": {
            "vault_family_qualification_available": True,
            "all_requested_window_ranges_proven": True,
            "qualified_family_count": 0,
            "pool_coupled_family_count": 0,
            "unique_pool_coupled_family": False,
            "canonical_vault_mapping_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
        },
        "qualification": {
            "service": "canonical_vault_family_qualification",
            "version": "1.4.8",
            "status": "no_qualified_family",
            "families": [],
            "summary": {
                "family_attribution_available": True,
                "all_requested_window_ranges_proven": True,
                "unique_qualified_family": False,
                "canonical_vault_family_qualified": False,
            },
            "family_attribution": {
                "service": "vault_pair_family_attribution",
                "version": "1.4.7",
                "status": "insufficient_family_evidence",
                "windows": windows,
                "families": [],
                "summary": {
                    "all_requested_window_ranges_proven": True,
                    "recurrent_pair_family_count": 0,
                    "recurrent_family_structural_conflict_observed": False,
                    "vault_pair_family_model_observed": False,
                },
            },
            "errors": [],
        },
        "errors": [],
    }


class ExactPoolLegSemanticsV14103Tests(unittest.TestCase):
    def test_public_export_routes_to_v14103(self):
        self.assertEqual(
            public_prover.__module__,
            "liquidity_scout.providers.x1.exact_pool_leg_semantics_v14103",
        )

    def test_boundary_scan_rows_outside_literal_window_do_not_count_as_activity(self):
        coupling = Provider(inactive_coupling_report())
        diagnostic_scanner = Provider(
            {
                "range_proven": True,
                "integrity_verified": True,
                "signature_count": 3,
                "scan_interval_signature_count": 0,
                "entries": [
                    {
                        "signature": "older-1",
                        "slot": 3,
                        "block_time": START - 1,
                        "err": None,
                    },
                    {
                        "signature": "older-2",
                        "slot": 2,
                        "block_time": START - 2,
                        "err": None,
                    },
                    {
                        "signature": "older-3",
                        "slot": 1,
                        "block_time": START - 3,
                        "err": None,
                    },
                ],
            }
        )

        result = prove_exact_pool_leg_semantics(
            pool_address=POOL,
            asset_mint=MINT,
            end_epoch=END,
            coupling_provider=coupling,
            diagnostic_scanner=diagnostic_scanner,
        )

        self.assertEqual(result["version"], "1.4.10.3")
        self.assertEqual(
            result["proof_diagnosis"]["blocking_code"],
            "NO_POOL_ACTIVITY_IN_PROOF_WINDOW",
        )
        evidence = result["proof_diagnosis"]["evidence"]
        self.assertEqual(evidence["diagnostic_24h_transaction_signature_count"], 0)
        self.assertEqual(evidence["diagnostic_24h_scanned_signature_count"], 3)
        self.assertEqual(evidence["diagnostic_24h_literal_window_signature_count"], 0)
        self.assertEqual(
            evidence["diagnostic_24h_provider_scan_interval_signature_count"],
            0,
        )
        self.assertFalse(result["summary"]["canonical_vault_mapping_promoted"])
        self.assertFalse(result["summary"]["exact_pool_leg_semantics_promoted"])
        self.assertFalse(result["transaction_execution_enabled"])

    def test_literal_window_activity_still_reports_no_vault_candidates(self):
        coupling = Provider(inactive_coupling_report())
        diagnostic_scanner = Provider(
            {
                "range_proven": True,
                "integrity_verified": True,
                "signature_count": 2,
                "scan_interval_signature_count": 1,
                "entries": [
                    {
                        "signature": "inside",
                        "slot": 2,
                        "block_time": END - 10,
                        "err": None,
                    },
                    {
                        "signature": "boundary-proof-row",
                        "slot": 1,
                        "block_time": START - 1,
                        "err": None,
                    },
                ],
            }
        )

        result = prove_exact_pool_leg_semantics(
            pool_address=POOL,
            asset_mint=MINT,
            end_epoch=END,
            coupling_provider=coupling,
            diagnostic_scanner=diagnostic_scanner,
        )

        self.assertEqual(
            result["proof_diagnosis"]["blocking_code"],
            "NO_VAULT_PAIR_CANDIDATES",
        )
        evidence = result["proof_diagnosis"]["evidence"]
        self.assertEqual(evidence["diagnostic_24h_transaction_signature_count"], 1)
        self.assertEqual(evidence["diagnostic_24h_scanned_signature_count"], 2)
        self.assertEqual(evidence["diagnostic_24h_literal_window_signature_count"], 1)


if __name__ == "__main__":
    unittest.main()
