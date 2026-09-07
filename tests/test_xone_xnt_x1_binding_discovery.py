from __future__ import annotations

import unittest

from liquidity_scout.providers.xone_xnt import (
    XONE_XNT_X1_BINDING_CONTRACT_VERSION,
    XONE_XNT_X1_SYSTEM_PROGRAM_ID,
    discover_x1_binding_candidates,
    extract_xone_xnt_claims,
    qualify_x1_binding_candidate,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


CANDIDATE = "sEsYH97wqmfnkzHedjNcw3zyJdPvUmsa9AixhS4b4fN"
OTHER = "Vote111111111111111111111111111111111111111"
SYSTEM = "11111111111111111111111111111111"


def claim(
    text: str,
    *,
    source_id: str = "x1report",
    url: str = "https://x1report.com/article/example",
    observed_at: float = 1.0,
):
    rows = extract_xone_xnt_claims(
        text,
        source_id=source_id,
        url=url,
        observed_at=observed_at,
    )
    if not rows:
        raise AssertionError("fixture produced no XONE/XNT claim")
    return rows[0]


class FakeRPC:
    def __init__(self):
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method == "getAccountInfo":
            return {
                "context": {"slot": 12345},
                "value": {
                    "owner": SYSTEM,
                    "executable": False,
                    "lamports": 2_000_000_000,
                    "space": 0,
                    "data": ["", "base64"],
                },
            }
        if method == "getSignaturesForAddress":
            return [
                {
                    "signature": "sig-success",
                    "slot": 12344,
                    "blockTime": 1788793000,
                    "err": None,
                    "confirmationStatus": "finalized",
                },
                {
                    "signature": "sig-failed",
                    "slot": 12343,
                    "blockTime": 1788792990,
                    "err": {"InstructionError": [0, "Custom"]},
                    "confirmationStatus": "finalized",
                },
            ]
        if method == "getTransaction":
            if params[0] != "sig-success":
                raise AssertionError("failed transaction should not be fetched")
            return {
                "slot": 12344,
                "blockTime": 1788793000,
                "meta": {
                    "err": None,
                    "preBalances": [1_000_000_000, 9_000_000_000],
                    "postBalances": [2_000_000_000, 8_000_000_000],
                    "innerInstructions": [],
                },
                "transaction": {
                    "message": {
                        "accountKeys": [
                            {"pubkey": CANDIDATE, "signer": False, "writable": True},
                            {"pubkey": OTHER, "signer": True, "writable": True},
                        ],
                        "instructions": [
                            {
                                "program": "system",
                                "programId": SYSTEM,
                                "parsed": {
                                    "type": "transfer",
                                    "info": {
                                        "source": OTHER,
                                        "destination": CANDIDATE,
                                        "lamports": 1_000_000_000,
                                    },
                                },
                            }
                        ],
                    }
                },
            }
        raise AssertionError(f"unexpected RPC method {method}")


class XoneXntX1BindingDiscoveryTests(unittest.TestCase):
    def test_discovers_exact_x1_pubkey_only_in_explicit_xone_xnt_binding_context(self):
        source_claim = claim(
            f"XONE holders may migrate to XNT using X1 account {CANDIDATE}."
        )
        result = discover_x1_binding_candidates([source_claim])
        self.assertEqual(
            result["contract_version"],
            XONE_XNT_X1_BINDING_CONTRACT_VERSION,
        )
        self.assertEqual(result["candidate_count"], 1)
        row = result["candidates"][0]
        self.assertEqual(row["candidate_pubkey"], CANDIDATE)
        self.assertEqual(
            row["candidate_role"],
            "unverified_xone_xnt_x1_binding_candidate",
        )
        self.assertTrue(row["eligible_for_history_qualification"])
        self.assertTrue(row["source_binding_language_present"])
        self.assertFalse(row["source_binding_verified"])
        self.assertFalse(row["x1_binding_identified"])
        self.assertFalse(row["xone_xnt_conversion_verified"])
        self.assertFalse(row["execution_authorized"])

    def test_xnt_only_validator_rule_is_not_binding_candidate(self):
        source_claim = {
            "claim_id": "xnt-only",
            "source_id": "x1_docs",
            "source_name": "X1 Docs",
            "source_role": "official_x1_documentation",
            "url": "https://docs.x1.xyz/example",
            "observed_at": 1.0,
            "excerpt": (
                f"Validator XNT rewards unlock after 365 days at account {CANDIDATE}."
            ),
            "topics": ["validator_rewards", "unlock"],
        }
        result = discover_x1_binding_candidates([source_claim])
        self.assertEqual(result["candidate_count"], 0)
        self.assertIn("xnt-only", result["ignored_nonbinding_claim_ids"])
        self.assertTrue(
            result[
                "zero_candidates_mean_only_no_exact_x1_binding_pubkeys_in_supplied_claims"
            ]
        )

    def test_known_infrastructure_program_is_not_history_qualified(self):
        source_claim = claim(
            f"XONE to XNT conversion references X1 program {SYSTEM}."
        )
        result = discover_x1_binding_candidates([source_claim])
        self.assertEqual(result["candidate_count"], 1)
        row = result["candidates"][0]
        self.assertEqual(row["candidate_role"], "known_x1_infrastructure_program")
        self.assertFalse(row["eligible_for_history_qualification"])

        qualification = qualify_x1_binding_candidate(
            row,
            rpc_call=lambda method, params: (_ for _ in ()).throw(
                AssertionError("RPC must not be called for built-in infrastructure")
            ),
        )
        self.assertEqual(
            qualification["qualification_state"],
            "excluded_known_x1_infrastructure_program",
        )
        self.assertFalse(qualification["x1_binding_identified"])
        self.assertFalse(qualification["execution_authorized"])

    def test_bounded_history_preserves_native_transfer_without_role_promotion(self):
        source_claim = claim(
            f"XONE holders may claim XNT through X1 account {CANDIDATE}."
        )
        candidate = discover_x1_binding_candidates([source_claim])["candidates"][0]
        rpc = FakeRPC()
        result = qualify_x1_binding_candidate(
            candidate,
            rpc_call=rpc,
            source_url="https://rpc.mainnet.x1.xyz",
            history_limit=10,
            transaction_limit=5,
        )

        self.assertTrue(result["account_state_verified"])
        self.assertTrue(result["account"]["account_exists"])
        self.assertTrue(result["bounded_history_verified"])
        self.assertEqual(result["signature_count"], 2)
        self.assertEqual(result["successful_signature_count"], 1)
        self.assertEqual(result["transaction_observation_count"], 1)
        self.assertEqual(result["native_system_transfer_observation_count"], 1)

        tx = result["transactions"][0]
        self.assertTrue(tx["candidate_referenced_in_account_keys"])
        self.assertEqual(tx["candidate_balance_delta_lamports"], 1_000_000_000)
        self.assertEqual(tx["native_system_transfer_count"], 1)
        transfer = tx["native_system_transfers_involving_candidate"][0]
        self.assertTrue(transfer["candidate_is_destination"])
        self.assertFalse(transfer["distribution_role_verified"])

        self.assertTrue(result["history_activity_does_not_prove_binding_role"])
        self.assertFalse(result["source_binding_verified"])
        self.assertFalse(result["candidate_role_verified"])
        self.assertFalse(result["x1_binding_identified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["xnt_vesting_or_unlock_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["cross_chain_correlation_verified"])
        self.assertFalse(result["execution_authorized"])

        methods = [method for method, _params in rpc.calls]
        self.assertEqual(
            methods,
            ["getAccountInfo", "getSignaturesForAddress", "getTransaction"],
        )

    def test_zero_binding_candidates_is_scoped_not_global_absence(self):
        rows = [
            claim("XONE and XNT conversion timing remains unknown."),
        ]
        result = discover_x1_binding_candidates(rows)
        self.assertEqual(result["candidate_count"], 0)
        self.assertTrue(result["x1_binding_candidate_discovery_verified"])
        self.assertTrue(
            result[
                "zero_candidates_mean_only_no_exact_x1_binding_pubkeys_in_supplied_claims"
            ]
        )
        self.assertFalse(result["x1_binding_identified"])

    def test_service_seam_preserves_nonpromotion(self):
        service = CMISXoneXntConversionIntelligenceService()
        source_claim = claim(
            f"XONE migration to XNT may reference account {CANDIDATE}."
        )
        result = service.discover_xone_xnt_x1_binding_candidates([source_claim])
        self.assertTrue(result["x1_binding_candidate_discovery_verified"])
        self.assertEqual(result["x1_binding_discovery"]["candidate_count"], 1)
        self.assertFalse(result["x1_binding_identified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["xone_xnt_conversion_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
