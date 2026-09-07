from __future__ import annotations

import json
import unittest

from liquidity_scout.providers.xone_xnt import (
    XONE_XNT_X1_ALLOCATION_RECORD_CONTRACT_VERSION,
    XONE_XNT_X1_ALLOCATION_RECORD_XONE_CONTRACT,
    XoneXntX1AllocationRecordDiscoveryError,
    extract_x1_allocation_records,
    normalize_ethereum_address,
    qualify_x1_allocation_candidate,
    summarize_x1_allocation_records,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


ETH = "0x1111111111111111111111111111111111111111"
ETH2 = "0x2222222222222222222222222222222222222222"
X1 = "11111111111111111111111111111111"
OWNER = "Vote111111111111111111111111111111111111111"
URL = "https://raw.githubusercontent.com/FairCrypto/x1-app/main/data/xone-allocations.json"


class FakeRPC:
    def __init__(self, value, *, slot=123):
        self.value = value
        self.slot = slot
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, params))
        if method != "getAccountInfo":
            raise AssertionError(f"unexpected RPC method {method}")
        return {"context": {"slot": self.slot}, "value": self.value}


class X1AllocationRecordDiscoveryTests(unittest.TestCase):
    def test_normalize_ethereum_address(self):
        self.assertEqual(
            normalize_ethereum_address(ETH.upper().replace("0X", "0x")),
            ETH,
        )
        with self.assertRaises(XoneXntX1AllocationRecordDiscoveryError):
            normalize_ethereum_address("0x1234")

    def test_extracts_exact_structured_xone_allocation_record(self):
        payload = {
            "contract": XONE_XNT_X1_ALLOCATION_RECORD_XONE_CONTRACT,
            "type": "XONE XNT allocation registry",
            "records": [
                {
                    "ethereumAddress": ETH,
                    "x1Pubkey": X1,
                    "allocationAmount": 5000,
                    "claimState": "unclaimed",
                    "unlockAt": 1791244800,
                }
            ],
        }
        records = extract_x1_allocation_records(
            json.dumps(payload),
            source_id="faircrypto_x1_app_file",
            source_role="faircrypto_x1_app_primary",
            url=URL,
            observed_at=100.0,
            path="data/xone-allocations.json",
            revision="abc123",
        )
        self.assertEqual(len(records), 1)
        row = records[0]
        self.assertEqual(
            row["contract_version"],
            XONE_XNT_X1_ALLOCATION_RECORD_CONTRACT_VERSION,
        )
        self.assertEqual(row["ethereum_address"], ETH)
        self.assertEqual(row["x1_pubkey"], X1)
        self.assertTrue(row["ethereum_address_verified"])
        self.assertTrue(row["x1_pubkey_verified"])
        self.assertTrue(row["xone_specific_context"])
        self.assertTrue(row["xone_identity_binding_verified"])
        self.assertTrue(row["xnt_amount_field_present"])
        self.assertIn("claimstate", row["structured_claim_fields"])
        self.assertIn("unlockat", row["structured_vesting_fields"])
        self.assertFalse(row["allocation_semantics_verified"])
        self.assertFalse(row["snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(row["xnt_issuance_verified"])
        self.assertFalse(row["execution_authorized"])

    def test_xone_contract_address_is_identity_metadata_not_holder_key(self):
        text = (
            f"XONE XNT allocation registry contract "
            f"{XONE_XNT_X1_ALLOCATION_RECORD_XONE_CONTRACT}; "
            f"holder {ETH} maps to X1 {X1}; amount 100 XNT."
        )
        records = extract_x1_allocation_records(
            text,
            source_id="x1_official_xone_allocation",
            source_role="official_x1_web",
            url="https://x1.xyz/xone-allocation",
            observed_at=100.0,
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["ethereum_address"], ETH)
        self.assertNotEqual(
            records[0]["ethereum_address"],
            XONE_XNT_X1_ALLOCATION_RECORD_XONE_CONTRACT.casefold(),
        )

    def test_equivalent_text_and_structured_amounts_do_not_conflict(self):
        payload = {
            "type": "XONE allocation",
            "contract": XONE_XNT_X1_ALLOCATION_RECORD_XONE_CONTRACT,
            "ethereumAddress": ETH,
            "x1Pubkey": X1,
            "allocationAmount": "100",
            "note": "100 XNT",
        }
        records = extract_x1_allocation_records(
            json.dumps(payload),
            source_id="faircrypto_x1_app_file",
            source_role="faircrypto_x1_app_primary",
            url=URL,
            observed_at=100.0,
            path="data/xone-allocations.json",
        )
        summary = summarize_x1_allocation_records(records)
        self.assertEqual(summary["candidate_count"], 1)
        self.assertEqual(summary["amount_conflict_candidate_count"], 0)
        self.assertFalse(summary["candidates"][0]["amount_conflict"])

    def test_rejects_ordinary_xone_abi_artifact(self):
        abi_like = (
            f'{{"name":"XONE","address":"{ETH}",'
            '"bytecode":"0x6000518481527f8c5be1e5ebec7d5bd14f71427d1e84f3dd00",'
            '"name":"allocation"}}'
        )
        records = extract_x1_allocation_records(
            abi_like,
            source_id="faircrypto_x1_app_file",
            source_role="faircrypto_x1_app_primary",
            url=URL,
            observed_at=100.0,
            path="public/abi/XONE.json",
        )
        self.assertEqual(records, [])

    def test_does_not_slice_x1_pubkey_from_long_hex_bytecode(self):
        text = (
            f"XONE allocation holder {ETH}; "
            "bytecode 0x6000518481527f8c5be1e5ebec7d5bd14f71427d1e84f3dd00 "
            "for XNT claim logic."
        )
        records = extract_x1_allocation_records(
            text,
            source_id="source_code",
            source_role="faircrypto_x1_app_primary",
            url="https://raw.githubusercontent.com/FairCrypto/x1-app/main/src/xone.ts",
            observed_at=100.0,
            path="src/xone.ts",
        )
        self.assertEqual(records, [])

    def test_rejects_generic_cross_chain_address_pair_without_xone(self):
        payload = {
            "type": "generic allocation registry",
            "records": [
                {
                    "ethereumAddress": ETH,
                    "x1Pubkey": X1,
                    "allocationAmount": 5000,
                }
            ],
        }
        records = extract_x1_allocation_records(
            json.dumps(payload),
            source_id="generic_registry",
            source_role="x1_labs_source",
            url="https://raw.githubusercontent.com/x1-labs/example/main/allocations.json",
            observed_at=100.0,
            path="allocations.json",
        )
        self.assertEqual(records, [])

    def test_xone_name_only_is_candidate_not_exact_identity_binding(self):
        text = (
            f"XONE holder allocation to XNT: Ethereum {ETH} maps to X1 {X1} "
            "with 250 XNT claimable after vesting."
        )
        records = extract_x1_allocation_records(
            text,
            source_id="x1_official_xone_allocation",
            source_role="official_x1_web",
            url="https://x1.xyz/xone-allocation",
            observed_at=100.0,
        )
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0]["xone_specific_context"])
        self.assertFalse(records[0]["xone_identity_binding_verified"])
        self.assertTrue(records[0]["xnt_amount_field_present"])
        self.assertFalse(records[0]["allocation_semantics_verified"])

    def test_summary_groups_duplicate_pair_and_preserves_amount_conflict(self):
        first = extract_x1_allocation_records(
            (
                f"XONE allocation {ETH} -> {X1}: 100 XNT. "
                f"Contract {XONE_XNT_X1_ALLOCATION_RECORD_XONE_CONTRACT}"
            ),
            source_id="source_a",
            source_role="official_x1_web",
            url="https://x1.xyz/a",
            observed_at=100.0,
        )[0]
        second = extract_x1_allocation_records(
            (
                f"XONE allocation {ETH} -> {X1}: 200 XNT. "
                f"Contract {XONE_XNT_X1_ALLOCATION_RECORD_XONE_CONTRACT}"
            ),
            source_id="source_b",
            source_role="faircrypto_x1_app_primary",
            url="https://raw.githubusercontent.com/FairCrypto/x1-app/main/b.txt",
            observed_at=101.0,
        )[0]
        summary = summarize_x1_allocation_records([first, second])
        self.assertEqual(summary["candidate_count"], 1)
        self.assertEqual(summary["xone_specific_candidate_count"], 1)
        self.assertEqual(
            summary["exact_xone_identity_bound_candidate_count"],
            1,
        )
        self.assertEqual(summary["amount_conflict_candidate_count"], 1)
        candidate = summary["candidates"][0]
        self.assertEqual(len(candidate["record_ids"]), 2)
        self.assertTrue(candidate["amount_conflict"])
        self.assertFalse(summary["snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(summary["execution_authorized"])

    def test_zero_result_is_scoped_not_global_absence(self):
        summary = summarize_x1_allocation_records([])
        self.assertEqual(summary["candidate_count"], 0)
        self.assertTrue(
            summary["zero_candidates_are_scoped_public_source_evidence_only"]
        )
        self.assertFalse(
            summary["private_or_unpublished_allocation_registry_absence_proven"]
        )

    def test_rpc_qualification_proves_account_state_only(self):
        candidate = {
            "ethereum_address": ETH2,
            "x1_pubkey": X1,
        }
        value = {
            "owner": OWNER,
            "executable": False,
            "lamports": 123456,
            "space": 80,
            "data": {
                "program": "system",
                "parsed": {"type": "account"},
            },
        }
        proof = qualify_x1_allocation_candidate(
            candidate,
            rpc_call=FakeRPC(value),
            source_url="https://rpc.mainnet.x1.xyz",
        )
        self.assertTrue(proof["account_state_verified"])
        self.assertTrue(proof["account_exists"])
        self.assertEqual(proof["owner"], OWNER)
        self.assertTrue(
            proof["account_existence_does_not_prove_allocation_role"]
        )
        self.assertFalse(proof["allocation_semantics_verified"])
        self.assertFalse(proof["snapshot_eligibility_verified"])
        self.assertFalse(proof["xnt_issuance_verified"])
        self.assertFalse(proof["execution_authorized"])

    def test_service_handoff_preserves_authority_boundary(self):
        service = CMISXoneXntConversionIntelligenceService()
        result = service.discover_xone_xnt_x1_allocation_records(
            [
                {
                    "source_id": "faircrypto_x1_app_file",
                    "source_role": "faircrypto_x1_app_primary",
                    "url": URL,
                    "path": "data/xone-allocations.json",
                    "revision": "abc123",
                    "text": (
                        f"XONE XNT allocation {ETH} maps to X1 {X1}; "
                        f"contract {XONE_XNT_X1_ALLOCATION_RECORD_XONE_CONTRACT}; "
                        "amount 100 XNT."
                    ),
                }
            ],
            observed_at=100.0,
        )
        self.assertTrue(result["x1_allocation_record_discovery_verified"])
        self.assertTrue(result["x1_allocation_record_candidate_discovered"])
        self.assertEqual(
            result["allocation_record_discovery"]["candidate_count"],
            1,
        )
        self.assertFalse(result["x1_allocation_semantics_verified"])
        self.assertFalse(result["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
