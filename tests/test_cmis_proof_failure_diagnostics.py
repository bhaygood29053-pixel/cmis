import unittest

from liquidity_scout.providers.x1.proof_failure_diagnostics import (
    AMBIGUOUS,
    CONFLICTING_EVIDENCE,
    DATA_OR_TRANSPORT_ERROR,
    INSUFFICIENT_EVIDENCE,
    PROVEN,
    diagnose_exact_pool_leg_semantics,
)


POOL = "PoolA"
MINT = "AssetMint"
END = 100000.0


class Provider:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.value


def mapping_failure_report(
    *,
    coupling_status="no_qualified_vault_families",
    qualification_status="no_qualified_family",
    attribution_status="insufficient_family_evidence",
    candidate_count=0,
    structural_conflict=False,
):
    windows = [
        {
            "label": label,
            "range_proven": True,
            "integrity_verified": True,
            "candidate_pair_count": candidate_count,
        }
        for label in ("1h", "6h", "24h")
    ]
    return {
        "service": "exact_pool_leg_semantics",
        "version": "1.4.10.1",
        "status": "canonical_vault_mapping_unproven",
        "summary": {
            "canonical_vault_mapping_proven": False,
            "exact_pool_leg_semantics_proven": False,
        },
        "coupling": {
            "status": coupling_status,
            "pool_coupled_family_count": 0,
            "families": [],
            "summary": {
                "canonical_vault_mapping_proven": False,
                "qualified_family_count": 0,
            },
            "qualification": {
                "status": qualification_status,
                "families": [],
                "family_attribution": {
                    "status": attribution_status,
                    "windows": windows,
                    "families": [],
                    "summary": {
                        "all_requested_window_ranges_proven": True,
                        "recurrent_family_structural_conflict_observed": structural_conflict,
                    },
                },
            },
            "errors": [],
        },
        "errors": [
            {
                "stage": "canonical_pool_vault_coupling",
                "error": (
                    "v1.4.9 did not expose exactly one proven mapping with a "
                    "stable pool structural anchor"
                ),
            }
        ],
    }


def diagnose(report, scanner):
    return diagnose_exact_pool_leg_semantics(
        report,
        pool_address=POOL,
        asset_mint=MINT,
        end_epoch=END,
        scanner=scanner,
    )


class ProofFailureDiagnosticsTests(unittest.TestCase):
    def test_proven_result_has_no_blocker(self):
        scanner = Provider({"entries": []})
        result = diagnose(
            {
                "status": "exact_pool_leg_semantics_proven",
                "summary": {
                    "exact_pool_leg_semantics_proven": True,
                    "recognized_pool_operation_count": 12,
                    "unknown_pool_operation_count": 0,
                    "buy_semantics_proven": True,
                    "sell_semantics_proven": True,
                },
            },
            scanner,
        )
        self.assertEqual(result["proof_outcome"], PROVEN)
        self.assertIsNone(result["blocking_stage"])
        self.assertIsNone(result["blocking_code"])
        self.assertFalse(result["retryable"])
        self.assertEqual(scanner.calls, [])

    def test_zero_activity_is_explained_as_insufficient_evidence(self):
        scanner = Provider(
            {
                "range_proven": True,
                "integrity_verified": True,
                "entries": [],
            }
        )
        report = mapping_failure_report()
        # The v1.4.10 unavailable envelope records the mapping prerequisite as
        # an explanatory error. Diagnostics must inspect the nested coupling
        # evidence before treating that expected fail-closed marker as transport.
        report["errors"] = []
        result = diagnose(report, scanner)

        self.assertEqual(result["proof_outcome"], INSUFFICIENT_EVIDENCE)
        self.assertEqual(result["blocking_stage"], "vault_pair_discovery")
        self.assertEqual(result["blocking_code"], "NO_POOL_ACTIVITY_IN_PROOF_WINDOW")
        self.assertEqual(
            result["evidence"]["diagnostic_24h_transaction_signature_count"],
            0,
        )
        self.assertTrue(result["retryable"])
        self.assertEqual(len(scanner.calls), 1)

    def test_active_pool_without_pair_candidates_is_distinguished(self):
        scanner = Provider(
            {
                "range_proven": True,
                "integrity_verified": True,
                "entries": [
                    {"signature": "sig-1", "slot": 1, "block_time": END - 10, "err": None}
                ],
            }
        )
        report = mapping_failure_report()
        report["errors"] = []
        result = diagnose(report, scanner)

        self.assertEqual(result["proof_outcome"], INSUFFICIENT_EVIDENCE)
        self.assertEqual(result["blocking_code"], "NO_VAULT_PAIR_CANDIDATES")
        self.assertEqual(
            result["evidence"]["diagnostic_24h_transaction_signature_count"],
            1,
        )

    def test_ambiguous_mapping_is_explicit(self):
        scanner = Provider({"entries": []})
        report = mapping_failure_report(
            coupling_status="ambiguous_pool_vault_coupling",
            qualification_status="ambiguous_qualified_families",
            candidate_count=2,
        )
        report["errors"] = []
        result = diagnose(report, scanner)

        self.assertEqual(result["proof_outcome"], AMBIGUOUS)
        self.assertEqual(result["blocking_code"], "AMBIGUOUS_CANONICAL_VAULT_FAMILIES")
        self.assertEqual(scanner.calls, [])

    def test_structural_conflict_is_not_called_insufficient_activity(self):
        scanner = Provider({"entries": []})
        report = mapping_failure_report(
            attribution_status="family_structural_conflict_observed",
            candidate_count=1,
            structural_conflict=True,
        )
        report["errors"] = []
        result = diagnose(report, scanner)

        self.assertEqual(result["proof_outcome"], CONFLICTING_EVIDENCE)
        self.assertEqual(result["blocking_code"], "STRUCTURAL_VAULT_FAMILY_CONFLICT")
        self.assertTrue(result["conflicting_evidence_observed"])
        self.assertEqual(scanner.calls, [])

    def test_diagnostic_scan_failure_is_data_error(self):
        scanner = Provider(error=RuntimeError("rpc unavailable"))
        report = mapping_failure_report()
        report["errors"] = []
        result = diagnose(report, scanner)

        self.assertEqual(result["proof_outcome"], DATA_OR_TRANSPORT_ERROR)
        self.assertEqual(result["blocking_code"], "DIAGNOSTIC_HISTORY_SCAN_UNAVAILABLE")
        self.assertTrue(result["retryable"])

    def test_unknown_operation_is_explicit_insufficient_evidence(self):
        scanner = Provider({"entries": []})
        result = diagnose(
            {
                "status": "amm_operation_classification_incomplete_or_conflicting",
                "summary": {
                    "exact_pool_leg_semantics_proven": False,
                    "unknown_pool_operation_count": 1,
                },
                "errors": [],
            },
            scanner,
        )
        self.assertEqual(result["proof_outcome"], INSUFFICIENT_EVIDENCE)
        self.assertEqual(result["blocking_code"], "UNKNOWN_AMM_OPERATION")
        self.assertEqual(result["evidence"]["unknown_pool_operation_count"], 1)


if __name__ == "__main__":
    unittest.main()
