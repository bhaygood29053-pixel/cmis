from __future__ import annotations

from hashlib import sha256
import unittest

from liquidity_scout.providers.ethereum import XONE_CONTRACT
from liquidity_scout.providers.xone_xnt import (
    XONE_SNAPSHOT_ARCHIVED_ASSET_GRAPH_CONTRACT_VERSION,
    XoneSnapshotArchivedAssetGraphError,
    annotate_retrieved_asset_capture,
    build_asset_graph_edges,
    classify_archived_asset_kind,
    extract_archived_asset_references,
    extract_asset_provenance_candidates,
    summarize_archived_asset_graph,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


ROOT_URL = "https://x1.xyz/"
ROOT_CAPTURE_ID = "root-capture"
ASSET_URL = "https://x1.xyz/_next/static/chunks/app-123.js"


def root_capture():
    return {
        "capture_id": ROOT_CAPTURE_ID,
        "timestamp": "20251006120000",
        "original": ROOT_URL,
        "mimetype": "text/html",
        "statuscode": 200,
        "digest": "ROOTDIGEST",
        "length": 1000,
        "replay_url": (
            "https://web.archive.org/web/20251006120000id_/https://x1.xyz/"
        ),
        "archival_capture_discovered": True,
        "archival_capture_retrieved": True,
        "execution_authorized": False,
    }


def asset_capture(url=ASSET_URL):
    return {
        "capture_id": "asset-capture",
        "timestamp": "20251006120100",
        "original": url,
        "mimetype": "application/javascript",
        "statuscode": 200,
        "digest": "ASSETDIGEST",
        "length": 2000,
        "replay_url": (
            "https://web.archive.org/web/20251006120100id_/" + url
        ),
        "archival_capture_discovered": True,
        "archival_capture_retrieved": False,
        "execution_authorized": False,
    }


class ArchivedAssetGraphTests(unittest.TestCase):
    def test_classifies_application_asset_kinds(self):
        self.assertEqual(
            classify_archived_asset_kind(
                "https://x1.xyz/_next/static/chunks/app-1.js"
            ),
            "javascript",
        )
        self.assertEqual(
            classify_archived_asset_kind(
                "https://x1.xyz/_next/static/buildManifest.js"
            ),
            "manifest",
        )
        self.assertEqual(
            classify_archived_asset_kind(
                "https://x1.xyz/_next/data/build/xone.json"
            ),
            "json",
        )
        self.assertEqual(
            classify_archived_asset_kind("https://x1.xyz/data/holders.csv"),
            "data",
        )
        self.assertEqual(
            classify_archived_asset_kind("https://x.com/mrJackLevin/status/12345"),
            "x_status",
        )
        self.assertEqual(
            classify_archived_asset_kind("ipfs://QmExample/xone.json"),
            "ipfs",
        )

    def test_html_extracts_scripts_manifest_json_social_and_ipfs(self):
        text = f"""
        <html>
          <script src="/_next/static/chunks/app-123.js"></script>
          <link rel="manifest" href="/manifest.json">
          <a href="/data/xone-holder-registry.json">registry</a>
          <a href="https://x.com/mrJackLevin/status/1234567890">post</a>
          ipfs://QmExample/xone-holders.json
        </html>
        """
        rows = extract_archived_asset_references(
            text,
            parent_original_url=ROOT_URL,
            content_type="text/html",
            max_references=20,
        )
        by_url = {row["url"]: row for row in rows}
        self.assertIn(ASSET_URL, by_url)
        self.assertTrue(by_url[ASSET_URL]["same_origin"])
        self.assertTrue(by_url[ASSET_URL]["traversable_via_wayback"])
        self.assertIn("https://x1.xyz/manifest.json", by_url)
        self.assertIn("https://x1.xyz/data/xone-holder-registry.json", by_url)
        self.assertTrue(
            by_url["https://x.com/mrJackLevin/status/1234567890"][
                "stable_primary_social_url"
            ]
        )
        self.assertTrue(
            by_url["ipfs://QmExample/xone-holders.json"][
                "content_addressed_pointer"
            ]
        )
        self.assertFalse(
            by_url["ipfs://QmExample/xone-holders.json"][
                "traversable_via_wayback"
            ]
        )

    def test_js_and_manifest_nested_asset_strings_are_discovered(self):
        text = """
        self.__BUILD_MANIFEST={
          x:["/_next/static/chunks/xone-abc.js"],
          data:"/_next/data/build/xone.json"
        };
        const map="/_next/static/chunks/xone-abc.js.map";
        const exportPath="/assets/xone-holder-export.csv";
        """
        rows = extract_archived_asset_references(
            text,
            parent_original_url=ASSET_URL,
            content_type="application/javascript",
            max_references=20,
        )
        urls = {row["url"] for row in rows}
        self.assertIn(
            "https://x1.xyz/_next/static/chunks/xone-abc.js",
            urls,
        )
        self.assertIn(
            "https://x1.xyz/_next/data/build/xone.json",
            urls,
        )
        self.assertIn(
            "https://x1.xyz/_next/static/chunks/xone-abc.js.map",
            urls,
        )
        self.assertIn(
            "https://x1.xyz/assets/xone-holder-export.csv",
            urls,
        )

    def test_unsafe_schemes_and_cross_origin_assets_do_not_traverse(self):
        text = """
        <script src="javascript:alert(1)"></script>
        <a href="data:text/plain,xone">bad</a>
        <script src="https://cdn.example/app.js"></script>
        """
        rows = extract_archived_asset_references(
            text,
            parent_original_url=ROOT_URL,
            content_type="text/html",
        )
        by_url = {row["url"]: row for row in rows}
        self.assertNotIn("javascript:alert(1)", by_url)
        self.assertNotIn("data:text/plain,xone", by_url)
        self.assertIn("https://cdn.example/app.js", by_url)
        self.assertFalse(by_url["https://cdn.example/app.js"]["same_origin"])
        self.assertFalse(
            by_url["https://cdn.example/app.js"]["traversable_via_wayback"]
        )

    def test_graph_edge_preserves_root_and_parent_archive_provenance(self):
        root = root_capture()
        refs = extract_archived_asset_references(
            '<script src="/_next/static/chunks/app-123.js"></script>',
            parent_original_url=ROOT_URL,
            content_type="text/html",
        )
        edges = build_asset_graph_edges(root, refs, depth=1)
        self.assertEqual(len(edges), 1)
        edge = edges[0]
        self.assertEqual(edge["root_capture_id"], ROOT_CAPTURE_ID)
        self.assertEqual(edge["parent_capture_id"], ROOT_CAPTURE_ID)
        self.assertEqual(edge["parent_archive_timestamp"], "20251006120000")
        self.assertEqual(edge["asset_original"], ASSET_URL)
        self.assertFalse(edge["asset_capture_retrieved"])
        self.assertFalse(edge["execution_authorized"])

    def test_unretrieved_parent_cannot_create_graph_edge(self):
        parent = root_capture()
        parent["archival_capture_retrieved"] = False
        with self.assertRaises(XoneSnapshotArchivedAssetGraphError):
            build_asset_graph_edges(
                parent,
                [{"url": ASSET_URL}],
                depth=1,
            )

    def test_retrieved_asset_annotation_preserves_original_authority(self):
        body = b"console.log('xone')"
        row = annotate_retrieved_asset_capture(
            asset_capture(),
            root_capture_id=ROOT_CAPTURE_ID,
            parent_capture_id=ROOT_CAPTURE_ID,
            depth=1,
            retrieved_bytes=len(body),
            retrieved_content_type="application/javascript",
            content_sha256=sha256(body).hexdigest(),
        )
        self.assertTrue(row["asset_capture_retrieved"])
        self.assertTrue(row["original_host_authoritative"])
        self.assertEqual(row["original_source_role"], "x1_official")
        self.assertEqual(row["root_capture_id"], ROOT_CAPTURE_ID)
        self.assertFalse(row["execution_authorized"])

    def test_archived_authoritative_asset_exact_block_is_candidate_not_truth(self):
        body = (
            "The XONE holder snapshot was taken at Ethereum block 23500000. "
            f"The XONE contract is {XONE_CONTRACT}. "
            "This registry is for XNT allocation."
        )
        annotated = annotate_retrieved_asset_capture(
            asset_capture("https://x1.xyz/_next/static/xone-snapshot.json"),
            root_capture_id=ROOT_CAPTURE_ID,
            parent_capture_id=ROOT_CAPTURE_ID,
            depth=1,
            retrieved_bytes=len(body.encode()),
            retrieved_content_type="application/json",
            content_sha256=sha256(body.encode()).hexdigest(),
        )
        rows = extract_asset_provenance_candidates(
            body,
            asset_capture=annotated,
            observed_at=1.0,
        )
        self.assertGreaterEqual(len(rows), 1)
        exact = next(
            row for row in rows
            if row["authoritative_exact_snapshot_block_discovered"] is True
        )
        self.assertTrue(exact["direct_primary_archival_source_recovered"])
        self.assertEqual(exact["snapshot_block_candidates"], [23_500_000])
        self.assertTrue(exact["asset_semantic_candidate_discovered"])
        self.assertFalse(exact["official_xone_snapshot_verified"])
        self.assertFalse(exact["xone_snapshot_xnt_allocation_binding_verified"])

    def test_ordinary_xone_abi_asset_is_not_snapshot_semantics(self):
        body = (
            '{"contractName":"XONE","abi":['
            '{"type":"function","name":"balanceOf"},'
            '{"type":"function","name":"transfer"}]}'
        )
        annotated = annotate_retrieved_asset_capture(
            asset_capture("https://x1.xyz/public/abi/XONE.json"),
            root_capture_id=ROOT_CAPTURE_ID,
            parent_capture_id=ROOT_CAPTURE_ID,
            depth=1,
            retrieved_bytes=len(body.encode()),
            retrieved_content_type="application/json",
            content_sha256=sha256(body.encode()).hexdigest(),
        )
        rows = extract_asset_provenance_candidates(
            body,
            asset_capture=annotated,
            observed_at=1.0,
        )
        self.assertEqual(rows, [])

    def test_summary_keeps_zero_result_scoped(self):
        root = root_capture()
        refs = extract_archived_asset_references(
            '<script src="/_next/static/chunks/app-123.js"></script>',
            parent_original_url=ROOT_URL,
            content_type="text/html",
        )
        edges = build_asset_graph_edges(root, refs, depth=1)
        summary = summarize_archived_asset_graph(
            [root],
            edges,
            [],
            [],
        )
        self.assertEqual(
            summary["contract_version"],
            XONE_SNAPSHOT_ARCHIVED_ASSET_GRAPH_CONTRACT_VERSION,
        )
        self.assertTrue(summary["asset_graph_traversal_verified"])
        self.assertEqual(summary["asset_edge_count"], 1)
        self.assertEqual(summary["asset_semantic_candidate_count"], 0)
        self.assertTrue(
            summary["zero_semantic_candidates_are_scoped_asset_graph_evidence_only"]
        )
        self.assertFalse(summary["private_or_unpublished_snapshot_absence_proven"])
        self.assertFalse(summary["official_xone_snapshot_verified"])
        self.assertFalse(summary["execution_authorized"])

    def test_service_seam_preserves_snapshot_authority_boundary(self):
        root = root_capture()
        result = CMISXoneXntConversionIntelligenceService().resolve_xone_snapshot_archived_asset_graph(
            [root],
            [
                {
                    "parent_capture_id": ROOT_CAPTURE_ID,
                    "depth": 1,
                    "text": '<script src="/_next/static/chunks/app-123.js"></script>',
                    "content_type": "text/html",
                }
            ],
            observed_at=1.0,
        )
        self.assertTrue(
            result["xone_snapshot_archived_asset_graph_resolution_verified"]
        )
        self.assertTrue(result["archived_asset_graph_traversal_verified"])
        self.assertTrue(result["archived_asset_reference_discovered"])
        self.assertFalse(result["archived_asset_capture_retrieved"])
        self.assertFalse(result["official_xone_snapshot_verified"])
        self.assertFalse(result["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
