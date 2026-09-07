from __future__ import annotations

from hashlib import sha256
import unittest

from liquidity_scout.providers.xone_xnt import (
    XONE_XNT_ALLOCATION_SOURCE_PROVENANCE_CONTRACT_VERSION,
    XONE_XNT_ALLOCATION_SOURCE_XONE_CONTRACT,
    XoneXntAllocationSourceProvenanceError,
    extract_allocation_source_provenance,
    provenance_path_score,
    summarize_allocation_source_provenance,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


XONE = XONE_XNT_ALLOCATION_SOURCE_XONE_CONTRACT
PROGRAM_ID = "xen8pjUWEnRbm1eML9CGtHvmmQfruXMKUybqGjn3chv"
MERKLE_ROOT = "0x" + "ab" * 32


class AllocationSourceProvenanceTests(unittest.TestCase):
    def test_exact_xone_structured_allocation_export_candidate(self):
        text = (
            f"XONE XNT allocation registry for contract {XONE}. "
            "Download holder allocations from "
            "https://x1.xyz/data/xone-xnt-allocations.csv"
        )
        rows = extract_allocation_source_provenance(
            text,
            source_id="faircrypto_xone_export",
            source_role="faircrypto_xone_primary",
            url="https://raw.githubusercontent.com/FairCrypto/XONE/main/data/xone-xnt-allocations.csv",
            observed_at=100.0,
            path="data/xone-xnt-allocations.csv",
            revision="abc123",
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(
            row["contract_version"],
            XONE_XNT_ALLOCATION_SOURCE_PROVENANCE_CONTRACT_VERSION,
        )
        self.assertTrue(row["qualifying_xone_allocation_source_candidate"])
        self.assertTrue(row["xone_source_binding_verified"])
        self.assertTrue(row["source_provenance_fields_verified"])
        self.assertIn("structured_allocation_file", row["source_classes"])
        self.assertIn("registry_export_artifact", row["source_classes"])
        self.assertFalse(row["allocation_source_provenance_verified"])
        self.assertFalse(row["snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(row["xnt_issuance_verified"])
        self.assertFalse(row["execution_authorized"])

    def test_name_only_xone_source_remains_unverified_binding(self):
        rows = extract_allocation_source_provenance(
            "XONE holder allocation export: xone-allocations.json for XNT claims.",
            source_id="xone_name_only",
            source_role="official_x1_web",
            url="https://x1.xyz/xone",
            observed_at=100.0,
            path="data/xone-allocations.json",
            revision="abc123",
        )
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["qualifying_xone_allocation_source_candidate"])
        self.assertTrue(rows[0]["xone_semantic_binding_discovered"])
        self.assertFalse(rows[0]["xone_source_binding_verified"])
        self.assertFalse(rows[0]["authoritative_allocation_source_verified"])

    def test_api_endpoint_candidate(self):
        text = (
            f"XONE allocation API for {XONE}. XNT claim eligibility endpoint: "
            "https://api.x1.xyz/v1/xone/allocations"
        )
        rows = extract_allocation_source_provenance(
            text,
            source_id="official_api_reference",
            source_role="official_x1_documentation",
            url="https://docs.x1.xyz/xone",
            observed_at=100.0,
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("api_endpoint", rows[0]["source_classes"])
        self.assertEqual(
            rows[0]["api_urls"],
            ["https://api.x1.xyz/v1/xone/allocations"],
        )

    def test_merkle_root_candidate(self):
        text = (
            f"XONE allocation snapshot for contract {XONE}; "
            f"Merkle root {MERKLE_ROOT}; XNT claim proof tree."
        )
        rows = extract_allocation_source_provenance(
            text,
            source_id="merkle_manifest",
            source_role="faircrypto_x1_app_primary",
            url="https://raw.githubusercontent.com/FairCrypto/x1-app/main/data/xone-merkle.json",
            observed_at=100.0,
            path="data/xone-merkle.json",
            revision="abc123",
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("merkle_artifact", rows[0]["source_classes"])
        self.assertEqual(rows[0]["merkle_roots"], [MERKLE_ROOT])

    def test_content_addressed_candidate(self):
        cid = "QmYwAPJzv5CZsnAzt8auVZRnGiE1yQbW7V3o2cJ1WfM2qk"
        arid = "a" * 43
        text = (
            f"XONE XNT allocation registry for {XONE}. "
            f"IPFS ipfs://{cid} and Arweave ar://{arid} holder export."
        )
        rows = extract_allocation_source_provenance(
            text,
            source_id="content_addressed_manifest",
            source_role="official_x1_web",
            url="https://x1.xyz/xone-registry",
            observed_at=100.0,
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("content_addressed_artifact", rows[0]["source_classes"])
        self.assertEqual(rows[0]["ipfs_cids"], [cid])
        self.assertEqual(rows[0]["arweave_ids"], [arid])

    def test_exact_xone_program_schema_candidate(self):
        text = (
            f"XONE allocation program for contract {XONE}. "
            f"Program ID {PROGRAM_ID}. IDL account schema stores XNT claim state."
        )
        rows = extract_allocation_source_provenance(
            text,
            source_id="xone_program_schema",
            source_role="official_x1_documentation",
            url="https://docs.x1.xyz/xone-program",
            observed_at=100.0,
            path="target/idl/xone_allocation.json",
            revision="abc123",
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("x1_program_schema", rows[0]["source_classes"])
        self.assertIn(PROGRAM_ID, rows[0]["x1_program_ids"])
        self.assertTrue(rows[0]["xone_source_binding_verified"])
        self.assertFalse(rows[0]["allocation_semantics_verified"])

    def test_xenblocks_program_schema_is_architecture_analogue_only(self):
        text = (
            f"On-chain airdrop tracker program. Program ID {PROGRAM_ID}. "
            "IDL account schema uses ETH-address keyed PDA records for XNT airdrop."
        )
        rows = extract_allocation_source_provenance(
            text,
            source_id="x1_labs_xenblocks_airdrop_idl",
            source_role="x1_labs_architecture_analogue",
            url="https://raw.githubusercontent.com/x1-labs/xenblocks-airdrop/main/target/idl/xenblocks_airdrop_tracker.json",
            observed_at=100.0,
            path="target/idl/xenblocks_airdrop_tracker.json",
            revision="fc20337",
            architecture_analogue=True,
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row["architecture_analogue"])
        self.assertFalse(row["xone_named"])
        self.assertFalse(row["xone_source_binding_verified"])
        self.assertFalse(row["qualifying_xone_allocation_source_candidate"])
        self.assertIn("x1_program_schema", row["source_classes"])

    def test_generic_airdrop_without_xone_is_not_candidate(self):
        rows = extract_allocation_source_provenance(
            f"Generic airdrop program ID {PROGRAM_ID}. IDL account schema.",
            source_id="generic_airdrop",
            source_role="x1_labs_source",
            url="https://raw.githubusercontent.com/x1-labs/example/main/idl.json",
            observed_at=100.0,
            path="target/idl/generic_airdrop.json",
            revision="abc123",
        )
        self.assertEqual(rows, [])

    def test_ordinary_abi_is_rejected(self):
        rows = extract_allocation_source_provenance(
            (
                f'{{"name":"XONE","contract":"{XONE}",'
                '"name":"allocationRegistry","type":"function"}}'
            ),
            source_id="faircrypto_x1_app_abi",
            source_role="faircrypto_x1_app_primary",
            url="https://raw.githubusercontent.com/FairCrypto/x1-app/main/public/abi/XONE.json",
            observed_at=100.0,
            path="public/abi/XONE.json",
            revision="abc123",
        )
        self.assertEqual(rows, [])

    def test_container_registry_is_not_allocation_registry(self):
        rows = extract_allocation_source_provenance(
            "XONE container registry image published to ghcr.io/FairCrypto/x1-app.",
            source_id="publish_workflow",
            source_role="faircrypto_x1_app_primary",
            url="https://raw.githubusercontent.com/FairCrypto/x1-app/main/.github/workflows/publish.yml",
            observed_at=100.0,
            path=".github/workflows/publish.yml",
            revision="abc123",
        )
        self.assertEqual(rows, [])

    def test_release_asset_classification(self):
        text = (
            f"Release includes XONE XNT allocation export for {XONE}: "
            "xone-holder-allocations.csv"
        )
        rows = extract_allocation_source_provenance(
            text,
            source_id="faircrypto_xone_release",
            source_role="faircrypto_xone_primary",
            url="https://github.com/FairCrypto/XONE/releases/tag/v1",
            observed_at=100.0,
            release_name="v1",
            release_asset=True,
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("release_asset", rows[0]["source_classes"])
        self.assertIn("structured_allocation_file", rows[0]["source_classes"])

    def test_body_hash_is_verified_fail_closed(self):
        text = f"XONE allocation export for {XONE}: allocations.csv"
        digest = sha256(text.encode("utf-8")).hexdigest()
        rows = extract_allocation_source_provenance(
            text,
            source_id="hashed_export",
            source_role="faircrypto_xone_primary",
            url="https://raw.githubusercontent.com/FairCrypto/XONE/main/allocations.csv",
            observed_at=100.0,
            path="allocations.csv",
            revision="abc123",
            body_sha256=digest,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["body_sha256"], digest)
        with self.assertRaises(XoneXntAllocationSourceProvenanceError):
            extract_allocation_source_provenance(
                text,
                source_id="hashed_export",
                source_role="faircrypto_xone_primary",
                url="https://raw.githubusercontent.com/FairCrypto/XONE/main/allocations.csv",
                observed_at=100.0,
                path="allocations.csv",
                revision="abc123",
                body_sha256="0" * 64,
            )

    def test_summary_separates_xone_candidates_and_analogues(self):
        exact = extract_allocation_source_provenance(
            f"XONE XNT allocation registry {XONE}: allocations.csv",
            source_id="exact",
            source_role="faircrypto_xone_primary",
            url="https://raw.githubusercontent.com/FairCrypto/XONE/main/allocations.csv",
            observed_at=100.0,
            path="allocations.csv",
            revision="abc123",
        )[0]
        analogue = extract_allocation_source_provenance(
            f"Airdrop program ID {PROGRAM_ID}; IDL account schema for XNT records.",
            source_id="analogue",
            source_role="x1_labs_architecture_analogue",
            url="https://raw.githubusercontent.com/x1-labs/xenblocks-airdrop/main/target/idl/xenblocks_airdrop_tracker.json",
            observed_at=100.0,
            path="target/idl/xenblocks_airdrop_tracker.json",
            revision="abc123",
            architecture_analogue=True,
        )[0]
        summary = summarize_allocation_source_provenance([exact, analogue, exact])
        self.assertEqual(summary["candidate_count"], 2)
        self.assertEqual(summary["qualifying_xone_candidate_count"], 1)
        self.assertEqual(summary["exact_xone_source_bound_candidate_count"], 1)
        self.assertEqual(summary["architecture_analogue_candidate_count"], 1)
        self.assertFalse(summary["allocation_source_provenance_verified"])
        self.assertFalse(summary["execution_authorized"])

    def test_zero_summary_is_scoped_only(self):
        summary = summarize_allocation_source_provenance([])
        self.assertTrue(
            summary[
                "zero_qualifying_candidates_are_scoped_public_source_evidence_only"
            ]
        )
        self.assertFalse(
            summary["private_or_unpublished_allocation_source_absence_proven"]
        )

    def test_path_score_prioritizes_source_shaped_paths_and_rejects_abi(self):
        self.assertGreater(
            provenance_path_score("data/xone-holder-allocations.csv"),
            provenance_path_score("config/projects.ts"),
        )
        self.assertEqual(provenance_path_score("public/abi/XONE.json"), -1)

    def test_service_handoff_preserves_fail_closed_boundaries(self):
        service = CMISXoneXntConversionIntelligenceService()
        result = service.discover_xone_xnt_allocation_source_provenance(
            [
                {
                    "source_id": "exact",
                    "source_role": "faircrypto_xone_primary",
                    "url": "https://raw.githubusercontent.com/FairCrypto/XONE/main/allocations.csv",
                    "path": "data/xone-allocations.csv",
                    "revision": "abc123",
                    "text": (
                        f"XONE XNT allocation registry {XONE}: "
                        "xone-allocations.csv"
                    ),
                }
            ],
            observed_at=100.0,
        )
        self.assertTrue(
            result["allocation_source_provenance_discovery_verified"]
        )
        self.assertTrue(result["allocation_source_candidate_discovered"])
        self.assertFalse(result["allocation_source_provenance_verified"])
        self.assertFalse(result["authoritative_allocation_source_verified"])
        self.assertFalse(result["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
