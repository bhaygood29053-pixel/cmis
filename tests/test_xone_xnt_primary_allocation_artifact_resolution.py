from __future__ import annotations

from hashlib import sha256
import unittest

from liquidity_scout.providers.xone_xnt import (
    XONE_XNT_PRIMARY_ALLOCATION_ARTIFACT_RESOLUTION_CONTRACT_VERSION,
    XONE_XNT_PRIMARY_ARTIFACT_CANDIDATE,
    XONE_XNT_PRIMARY_ARTIFACT_NO_LEAD,
    XONE_XNT_PRIMARY_ARTIFACT_REJECTED,
    XONE_XNT_PRIMARY_ARTIFACT_RESOLVED_FOR_HANDOFF,
    XoneXntPrimaryAllocationArtifactResolutionError,
    no_lead_resolution,
    resolve_primary_allocation_artifact,
)
from liquidity_scout.providers.xone_xnt.primary_allocation_artifact_resolution import (
    HANDOFF_ALLOCATION_RECORDS,
    HANDOFF_API_VERIFICATION,
    HANDOFF_CONTENT_RETRIEVAL,
    HANDOFF_MERKLE_BINDING,
    HANDOFF_SNAPSHOT_REGISTRY,
    HANDOFF_X1_PROGRAM_RPC,
)
from liquidity_scout.providers.xone_xnt.allocation_source_provenance import (
    XONE_CONTRACT,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


PROGRAM_ID = "xen8pjUWEnRbm1eML9CGtHvmmQfruXMKUybqGjn3chv"
MERKLE_ROOT = "0x" + "ab" * 32


def _contracts(result):
    return {row["contract"] for row in result.get("candidate_handoffs", [])}


class PrimaryAllocationArtifactResolutionTests(unittest.TestCase):
    def test_no_lead_is_pass_and_performs_zero_discovery(self):
        result = no_lead_resolution(observed_at=100.0)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["resolution_state"], XONE_XNT_PRIMARY_ARTIFACT_NO_LEAD)
        self.assertFalse(result["network_discovery_performed"])
        self.assertEqual(result["network_request_count"], 0)
        self.assertFalse(result["lead_supplied"])
        self.assertFalse(result["primary_artifact_candidate_discovered"])
        self.assertFalse(result["primary_artifact_resolved_for_handoff"])
        self.assertFalse(result["execution_authorized"])

    def test_exact_xone_structured_export_resolves_for_handoff(self):
        text = (
            f"XONE XNT allocation registry for contract {XONE_CONTRACT}. "
            "Holder allocation export xone-holder-allocations.csv."
        )
        result = resolve_primary_allocation_artifact(
            {
                "source_id": "xone_allocation_export",
                "source_role": "faircrypto_xone_primary",
                "url": (
                    "https://raw.githubusercontent.com/FairCrypto/XONE/"
                    "0123456789abcdef/data/xone-holder-allocations.csv"
                ),
                "path": "data/xone-holder-allocations.csv",
                "revision": "0123456789abcdef",
                "text": text,
                "observed_at": 100.0,
            }
        )
        self.assertEqual(
            result["contract_version"],
            XONE_XNT_PRIMARY_ALLOCATION_ARTIFACT_RESOLUTION_CONTRACT_VERSION,
        )
        self.assertEqual(
            result["resolution_state"],
            XONE_XNT_PRIMARY_ARTIFACT_RESOLVED_FOR_HANDOFF,
        )
        self.assertTrue(result["locator_pinned"])
        self.assertTrue(result["locator_provenance_complete"])
        self.assertTrue(result["xone_source_binding_verified"])
        self.assertTrue(result["primary_artifact_candidate_discovered"])
        self.assertTrue(result["primary_artifact_resolved_for_handoff"])
        self.assertIn(HANDOFF_ALLOCATION_RECORDS, _contracts(result))
        self.assertFalse(result["allocation_source_provenance_verified"])
        self.assertFalse(result["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_expected_hash_match_is_preserved(self):
        text = (
            f"XONE XNT allocation registry for {XONE_CONTRACT}: "
            "xone-allocations.json"
        )
        digest = sha256(text.encode("utf-8")).hexdigest()
        result = resolve_primary_allocation_artifact(
            {
                "source_id": "hashed",
                "source_role": "faircrypto_xone_primary",
                "url": (
                    "https://raw.githubusercontent.com/FairCrypto/XONE/"
                    "abc/data/xone-allocations.json"
                ),
                "path": "data/xone-allocations.json",
                "revision": "abc",
                "text": text,
                "expected_sha256": digest,
                "observed_at": 100.0,
            }
        )
        self.assertTrue(result["expected_sha256_supplied"])
        self.assertTrue(result["expected_sha256_match"])
        self.assertTrue(result["content_integrity_verified"])
        self.assertEqual(result["artifact_sha256"], digest)

    def test_expected_hash_mismatch_fails_closed(self):
        text = (
            f"XONE XNT allocation registry for {XONE_CONTRACT}: "
            "xone-allocations.json"
        )
        with self.assertRaises(XoneXntPrimaryAllocationArtifactResolutionError):
            resolve_primary_allocation_artifact(
                {
                    "source_id": "hash_mismatch",
                    "source_role": "faircrypto_xone_primary",
                    "url": (
                        "https://raw.githubusercontent.com/FairCrypto/XONE/"
                        "abc/data/xone-allocations.json"
                    ),
                    "path": "data/xone-allocations.json",
                    "revision": "abc",
                    "text": text,
                    "expected_sha256": "0" * 64,
                    "observed_at": 100.0,
                }
            )

    def test_name_only_xone_is_candidate_not_resolved(self):
        result = resolve_primary_allocation_artifact(
            {
                "source_id": "xone_name_only",
                "source_role": "faircrypto_xone_primary",
                "url": (
                    "https://raw.githubusercontent.com/FairCrypto/XONE/"
                    "abc/data/xone-allocations.json"
                ),
                "path": "data/xone-allocations.json",
                "revision": "abc",
                "text": "XONE XNT holder allocation registry xone-allocations.json",
                "observed_at": 100.0,
            }
        )
        self.assertEqual(
            result["resolution_state"],
            XONE_XNT_PRIMARY_ARTIFACT_CANDIDATE,
        )
        self.assertTrue(result["primary_artifact_candidate_discovered"])
        self.assertFalse(result["xone_source_binding_verified"])
        self.assertFalse(result["primary_artifact_resolved_for_handoff"])
        self.assertEqual(result["handoffs"], [])
        self.assertIn(HANDOFF_ALLOCATION_RECORDS, _contracts(result))

    def test_non_xone_program_schema_is_analogue_only(self):
        result = resolve_primary_allocation_artifact(
            {
                "source_id": "xenblocks_program",
                "source_role": "x1_labs_architecture_analogue",
                "url": (
                    "https://raw.githubusercontent.com/x1-labs/"
                    "xenblocks-airdrop/abc/target/idl/"
                    "xenblocks_airdrop_tracker.json"
                ),
                "path": "target/idl/xenblocks_airdrop_tracker.json",
                "revision": "abc",
                "text": (
                    f"On-chain XNT airdrop tracker. Program ID {PROGRAM_ID}. "
                    "IDL account schema uses ETH-address keyed PDA records."
                ),
                "architecture_analogue": True,
                "observed_at": 100.0,
            }
        )
        self.assertEqual(
            result["resolution_state"],
            XONE_XNT_PRIMARY_ARTIFACT_CANDIDATE,
        )
        self.assertTrue(result["architecture_analogue"])
        self.assertFalse(result["xone_source_binding_verified"])
        self.assertFalse(result["primary_artifact_candidate_discovered"])
        self.assertFalse(result["primary_artifact_resolved_for_handoff"])
        self.assertIn(HANDOFF_X1_PROGRAM_RPC, _contracts(result))
        self.assertEqual(result["handoffs"], [])

    def test_exact_xone_merkle_and_snapshot_block_route_separately(self):
        text = (
            f"XONE XNT allocation snapshot for contract {XONE_CONTRACT}. "
            f"Merkle root {MERKLE_ROOT}. Snapshot block 18650000. "
            "Claim proof tree."
        )
        result = resolve_primary_allocation_artifact(
            {
                "source_id": "xone_merkle",
                "source_role": "faircrypto_xone_primary",
                "url": (
                    "https://raw.githubusercontent.com/FairCrypto/XONE/"
                    "abc/data/xone-merkle.json"
                ),
                "path": "data/xone-merkle.json",
                "revision": "abc",
                "text": text,
                "observed_at": 100.0,
            }
        )
        self.assertEqual(
            result["resolution_state"],
            XONE_XNT_PRIMARY_ARTIFACT_RESOLVED_FOR_HANDOFF,
        )
        self.assertEqual(result["snapshot_block_candidates"], [18650000])
        contracts = _contracts(result)
        self.assertIn(HANDOFF_MERKLE_BINDING, contracts)
        self.assertIn(HANDOFF_SNAPSHOT_REGISTRY, contracts)
        self.assertFalse(result["official_xone_snapshot_verified"])

    def test_exact_xone_program_schema_routes_to_rpc_qualification(self):
        result = resolve_primary_allocation_artifact(
            {
                "source_id": "xone_program",
                "source_role": "official_x1_documentation",
                "url": "https://docs.x1.xyz/xone-allocation-program",
                "path": "target/idl/xone_allocation.json",
                "revision": "deployment-abc",
                "text": (
                    f"XONE allocation program for contract {XONE_CONTRACT}. "
                    f"Program ID {PROGRAM_ID}. IDL account schema stores XNT claims."
                ),
                "observed_at": 100.0,
            }
        )
        self.assertTrue(result["primary_artifact_resolved_for_handoff"])
        self.assertIn(HANDOFF_X1_PROGRAM_RPC, _contracts(result))
        self.assertFalse(result["allocation_semantics_verified"])

    def test_api_route_requires_pinned_locator_for_resolution(self):
        result = resolve_primary_allocation_artifact(
            {
                "source_id": "xone_api",
                "source_role": "official_x1_documentation",
                "url": "https://docs.x1.xyz/xone-api",
                "text": (
                    f"XONE XNT allocation API for {XONE_CONTRACT}. "
                    "Endpoint https://api.x1.xyz/v1/xone/allocations"
                ),
                "observed_at": 100.0,
            }
        )
        self.assertEqual(
            result["resolution_state"],
            XONE_XNT_PRIMARY_ARTIFACT_CANDIDATE,
        )
        self.assertIn(HANDOFF_API_VERIFICATION, _contracts(result))
        self.assertFalse(result["locator_pinned"])
        self.assertFalse(result["primary_artifact_resolved_for_handoff"])

    def test_content_addressed_artifact_can_pin_locator(self):
        cid = "QmYwAPJzv5CZsnAzt8auVZRnGiE1yQbW7V3o2cJ1WfM2qk"
        result = resolve_primary_allocation_artifact(
            {
                "source_id": "xone_ipfs",
                "source_role": "faircrypto_xone_primary",
                "url": "https://xen.network/xone-allocation-manifest",
                "text": (
                    f"XONE XNT allocation registry for {XONE_CONTRACT}. "
                    f"IPFS ipfs://{cid} holder allocation artifact."
                ),
                "observed_at": 100.0,
            }
        )
        self.assertTrue(result["locator_pinned"])
        self.assertTrue(result["primary_artifact_resolved_for_handoff"])
        self.assertIn(HANDOFF_CONTENT_RETRIEVAL, _contracts(result))

    def test_ordinary_abi_is_rejected(self):
        result = resolve_primary_allocation_artifact(
            {
                "source_id": "xone_abi",
                "source_role": "faircrypto_x1_app_primary",
                "url": (
                    "https://raw.githubusercontent.com/FairCrypto/x1-app/"
                    "abc/public/abi/XONE.json"
                ),
                "path": "public/abi/XONE.json",
                "revision": "abc",
                "text": (
                    f'{{"name":"XONE","contract":"{XONE_CONTRACT}",'
                    '"name":"allocationRegistry","type":"function"}}'
                ),
                "observed_at": 100.0,
            }
        )
        self.assertEqual(
            result["resolution_state"],
            XONE_XNT_PRIMARY_ARTIFACT_REJECTED,
        )
        self.assertEqual(
            result["rejection_reason"],
            "no_concrete_allocation_source_provenance",
        )
        self.assertFalse(result["primary_artifact_resolved_for_handoff"])

    def test_generic_config_without_exact_xone_is_rejected(self):
        result = resolve_primary_allocation_artifact(
            {
                "source_id": "generic_config",
                "source_role": "x1_labs_architecture_analogue",
                "url": (
                    "https://raw.githubusercontent.com/x1-labs/"
                    "xenblocks-airdrop/abc/tsconfig.json"
                ),
                "path": "tsconfig.json",
                "revision": "abc",
                "text": '{"compilerOptions":{"rootDir":"src"}}',
                "architecture_analogue": True,
                "observed_at": 100.0,
            }
        )
        self.assertEqual(
            result["resolution_state"],
            XONE_XNT_PRIMARY_ARTIFACT_REJECTED,
        )
        self.assertEqual(
            result["rejection_reason"],
            "generic_config_without_exact_xone_binding",
        )

    def test_invalid_url_fails_closed(self):
        with self.assertRaises(XoneXntPrimaryAllocationArtifactResolutionError):
            resolve_primary_allocation_artifact(
                {
                    "source_id": "bad_url",
                    "source_role": "primary",
                    "url": "http://example.com/xone.json",
                    "path": "xone.json",
                    "revision": "abc",
                    "text": (
                        f"XONE XNT allocation registry {XONE_CONTRACT}: "
                        "xone.json"
                    ),
                    "observed_at": 100.0,
                }
            )

    def test_service_no_lead_and_lead_paths_preserve_boundaries(self):
        service = CMISXoneXntConversionIntelligenceService()
        idle = service.resolve_xone_xnt_primary_allocation_artifact(
            observed_at=100.0
        )
        self.assertTrue(idle["primary_allocation_artifact_resolution_available"])
        self.assertEqual(
            idle["primary_allocation_artifact_resolution"]["resolution_state"],
            XONE_XNT_PRIMARY_ARTIFACT_NO_LEAD,
        )
        self.assertFalse(idle["execution_authorized"])

        lead = service.resolve_xone_xnt_primary_allocation_artifact(
            {
                "source_id": "exact",
                "source_role": "faircrypto_xone_primary",
                "url": (
                    "https://raw.githubusercontent.com/FairCrypto/XONE/"
                    "abc/data/xone-allocations.csv"
                ),
                "path": "data/xone-allocations.csv",
                "revision": "abc",
                "text": (
                    f"XONE XNT allocation registry {XONE_CONTRACT}: "
                    "xone-allocations.csv"
                ),
                "observed_at": 100.0,
            }
        )
        self.assertTrue(lead["primary_allocation_artifact_resolution_available"])
        self.assertTrue(
            lead["primary_allocation_artifact_candidate_discovered"]
        )
        self.assertTrue(
            lead["primary_allocation_artifact_resolved_for_handoff"]
        )
        self.assertFalse(lead["allocation_source_provenance_verified"])
        self.assertFalse(lead["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(lead["xnt_issuance_verified"])
        self.assertFalse(lead["public_service_promoted"])
        self.assertFalse(lead["scout_reliance_promoted"])
        self.assertFalse(lead["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
