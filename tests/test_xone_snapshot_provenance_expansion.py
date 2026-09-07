from __future__ import annotations

import unittest

from liquidity_scout.providers.ethereum import XONE_CONTRACT
from liquidity_scout.providers.xone_xnt import (
    XONE_SNAPSHOT_PROVENANCE_CONTRACT_VERSION,
    XoneSnapshotProvenanceError,
    discover_repository_path_candidates,
    extract_provenance_candidates,
    rank_provenance_candidates,
    validate_provenance_url,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


class XoneSnapshotProvenanceTests(unittest.TestCase):
    def test_primary_exact_snapshot_block_is_high_priority_but_not_official(self):
        text = (
            "The XONE holder snapshot was taken at Ethereum block 23500000. "
            f"The token is {XONE_CONTRACT}. "
            "The holder registry will be used for XNT allocation."
        )
        rows = extract_provenance_candidates(
            text,
            source_id="faircrypto_xone_release",
            source_role="faircrypto_xone_primary",
            url="https://github.com/FairCrypto/XONE/releases/tag/example",
            observed_at=1.0,
            revision="abc",
        )
        self.assertGreaterEqual(len(rows), 1)
        row = next(
            item
            for item in rows
            if item["authoritative_exact_snapshot_block_discovered"] is True
        )
        self.assertEqual(row["candidate_kind"], "snapshot_statement")
        self.assertTrue(row["direct_primary_source_recovered"])
        self.assertTrue(row["authoritative_exact_snapshot_block_discovered"])
        self.assertEqual(row["snapshot_block_candidates"], [23_500_000])
        self.assertTrue(row["exact_xone_contract_mentioned"])
        self.assertTrue(
            any(
                item["xnt_allocation_binding_language_present"] is True
                for item in rows
            )
        )
        self.assertFalse(row["official_xone_snapshot_verified"])
        self.assertFalse(row["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(row["execution_authorized"])

    def test_mirror_xone_mint_space_is_context_only(self):
        rows = extract_provenance_candidates(
            "Cyphereus Prime X1 — XONE mint is live — Nov 20, 2023.",
            source_id="xspacegpt_jack_index",
            source_role="indexed_mirror",
            url="https://www.twitterspacegpt.com/hosts/mrJackLevin",
            observed_at=1.0,
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["candidate_kind"], "historical_context")
        self.assertFalse(row["direct_primary_source_recovered"])
        self.assertFalse(row["snapshot_artifact_candidate_discovered"])
        self.assertFalse(row["authoritative_exact_snapshot_block_discovered"])

    def test_secondary_snapshot_statement_cannot_be_authoritative(self):
        rows = extract_provenance_candidates(
            "XONE was reportedly snapshotted at Ethereum block 23500000 for XNT.",
            source_id="x1report_article",
            source_role="x1_report",
            url="https://x1report.com/article/example",
            observed_at=1.0,
        )
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["direct_primary_source_recovered"])
        self.assertFalse(rows[0]["authoritative_exact_snapshot_block_discovered"])

    def test_path_only_artifact_is_never_primary_proof(self):
        rows = discover_repository_path_candidates(
            [
                {"path": "public/xone-holder-snapshot.json", "type": "blob"},
                {"path": "src/app.ts", "type": "blob"},
            ],
            source_id="faircrypto_x1_app_tree",
            source_role="faircrypto_x1_app_primary",
            repository_url="https://github.com/FairCrypto/x1-app",
            revision="abc",
            observed_at=1.0,
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["path"], "public/xone-holder-snapshot.json")
        self.assertTrue(row["path_only_candidate"])
        self.assertTrue(row["snapshot_artifact_candidate_discovered"])
        self.assertFalse(row["direct_primary_source_recovered"])
        self.assertFalse(row["authoritative_exact_snapshot_block_discovered"])

    def test_plain_xone_abi_json_is_not_snapshot_provenance(self):
        rows = extract_provenance_candidates(
            '{"contractName":"XONE","type":"function","name":"transfer"}',
            source_id="faircrypto_x1_app_file",
            source_role="faircrypto_x1_app_primary",
            url="https://raw.githubusercontent.com/FairCrypto/x1-app/abc/public/abi/XONE.json",
            path="public/abi/XONE.json",
            revision="abc",
            observed_at=1.0,
        )
        self.assertEqual(rows, [])

    def test_generic_xnt_airdrop_without_xone_is_rejected(self):
        rows = extract_provenance_candidates(
            "ETH-address keyed wallets can receive a one-time native XNT airdrop.",
            source_id="x1_labs_airdrop",
            source_role="x1_labs_source",
            url="https://github.com/x1-labs/xenblocks-airdrop",
            observed_at=1.0,
        )
        self.assertEqual(rows, [])

    def test_holder_count_without_snapshot_artifact_context_is_rejected(self):
        rows = extract_provenance_candidates(
            "XONE has 12,000 holders on Ethereum.",
            source_id="secondary",
            source_role="secondary_report",
            url="https://example.test",
            observed_at=1.0,
        )
        self.assertEqual(rows, [])

    def test_merkle_artifact_is_ranked_but_not_verified(self):
        root = "0x" + ("ab" * 32)
        rows = extract_provenance_candidates(
            (
                "XONE holder registry Merkle root "
                f"{root} is published at ipfs://QmExample for XNT claims."
            ),
            source_id="faircrypto_x1_app_artifact",
            source_role="faircrypto_x1_app_primary",
            url="https://github.com/FairCrypto/x1-app/blob/abc/public/xone.json",
            path="public/xone-holder-registry.json",
            revision="abc",
            observed_at=1.0,
        )
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row["snapshot_artifact_candidate_discovered"])
        self.assertIn("merkle", row["artifact_indicators"])
        self.assertIn("json", row["artifact_indicators"])
        self.assertEqual(row["hash_candidates"], [root])
        self.assertFalse(row["official_registry_artifact_verified"])

    def test_ranking_preserves_authoritative_block_without_promoting_snapshot(self):
        primary = extract_provenance_candidates(
            (
                "XONE holder snapshot was taken at Ethereum block 23500000 "
                f"for contract {XONE_CONTRACT}."
            ),
            source_id="direct",
            source_role="x1_official",
            url="https://x1.xyz/example",
            observed_at=1.0,
        )[0]
        mirror = extract_provenance_candidates(
            "XONE mint is live Nov 20, 2023.",
            source_id="mirror",
            source_role="indexed_mirror",
            url="https://mirror.example",
            observed_at=1.0,
        )[0]
        result = rank_provenance_candidates([mirror, primary])
        self.assertEqual(
            result["contract_version"],
            XONE_SNAPSHOT_PROVENANCE_CONTRACT_VERSION,
        )
        self.assertEqual(result["authoritative_exact_snapshot_block_candidates"], [23_500_000])
        self.assertTrue(result["authoritative_exact_snapshot_block_discovered"])
        self.assertEqual(result["candidates"][0]["source_id"], "direct")
        self.assertFalse(result["official_xone_snapshot_verified"])
        self.assertFalse(result["xone_snapshot_xnt_allocation_binding_verified"])

    def test_url_allowlist_fails_closed(self):
        self.assertEqual(
            validate_provenance_url(
                "https://github.com/FairCrypto/XONE",
                allowed_hosts=["github.com"],
            ),
            "https://github.com/FairCrypto/XONE",
        )
        with self.assertRaises(XoneSnapshotProvenanceError):
            validate_provenance_url(
                "http://github.com/FairCrypto/XONE",
                allowed_hosts=["github.com"],
            )
        with self.assertRaises(XoneSnapshotProvenanceError):
            validate_provenance_url(
                "https://evil.example/FairCrypto/XONE",
                allowed_hosts=["github.com"],
            )

    def test_service_preserves_authority_boundaries(self):
        service = CMISXoneXntConversionIntelligenceService()
        result = service.expand_xone_snapshot_provenance(
            [
                {
                    "source_id": "mirror",
                    "source_role": "indexed_mirror",
                    "url": "https://www.twitterspacegpt.com/hosts/mrJackLevin",
                    "text": "XONE mint is live Nov 20, 2023.",
                }
            ],
            observed_at=1.0,
        )
        self.assertTrue(result["xone_snapshot_provenance_expansion_verified"])
        self.assertTrue(result["provenance_candidate_discovered"])
        self.assertFalse(result["direct_primary_source_recovered"])
        self.assertFalse(result["authoritative_exact_snapshot_block_discovered"])
        self.assertFalse(result["official_xone_snapshot_verified"])
        self.assertFalse(result["official_registry_artifact_verified"])
        self.assertFalse(result["xone_snapshot_eligibility_verified"])
        self.assertFalse(result["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
