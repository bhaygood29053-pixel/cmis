from __future__ import annotations

import unittest

from liquidity_scout.providers.ethereum import XONE_CONTRACT
from liquidity_scout.providers.xone_xnt import (
    XONE_SNAPSHOT_ARCHIVAL_RECOVERY_CONTRACT_VERSION,
    XoneSnapshotArchivalRecoveryError,
    archival_url_relevance_score,
    build_wayback_replay_url,
    extract_archival_provenance_candidates,
    original_host_is_authoritative,
    parse_cdx_json,
    rank_archival_captures,
    recover_stable_x_urls,
    select_diverse_archival_captures,
    source_role_for_original_url,
    summarize_archival_recovery,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


class XoneSnapshotArchivalRecoveryTests(unittest.TestCase):
    def _capture(self, original="https://xen.network/xone/snapshot"):
        rows = parse_cdx_json(
            [
                [
                    "timestamp",
                    "original",
                    "mimetype",
                    "statuscode",
                    "digest",
                    "length",
                ],
                [
                    "20240102030405",
                    original,
                    "text/html",
                    "200",
                    "ABCDEF123",
                    "1234",
                ],
            ]
        )
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_parse_cdx_preserves_capture_provenance(self):
        capture = self._capture()
        self.assertTrue(capture["archival_capture_discovered"])
        self.assertFalse(capture["archival_capture_retrieved"])
        self.assertEqual(capture["timestamp"], "20240102030405")
        self.assertEqual(capture["digest"], "ABCDEF123")
        self.assertEqual(capture["statuscode"], 200)
        self.assertTrue(capture["original_host_authoritative"])
        self.assertEqual(
            capture["original_source_role"], "faircrypto_xone_primary"
        )
        self.assertIn("20240102030405id_", capture["replay_url"])
        self.assertFalse(capture["execution_authorized"])

    def test_parse_cdx_rejects_missing_fields(self):
        with self.assertRaises(XoneSnapshotArchivalRecoveryError):
            parse_cdx_json([["timestamp", "original"], ["20240102030405", "https://x1.xyz/"]])

    def test_parse_cdx_filters_failed_and_malformed_rows(self):
        rows = parse_cdx_json(
            [
                list(("timestamp", "original", "mimetype", "statuscode", "digest", "length")),
                ["20240102030405", "https://x1.xyz/", "text/html", "404", "A", "1"],
                ["bad", "https://x1.xyz/", "text/html", "200", "B", "2"],
                ["20240102030405", "ftp://x1.xyz/", "text/html", "200", "C", "3"],
            ]
        )
        self.assertEqual(rows, [])

    def test_replay_url_fails_closed(self):
        url = build_wayback_replay_url(
            timestamp="20240102030405",
            original_url="https://x1.xyz/xone",
        )
        self.assertTrue(url.startswith("https://web.archive.org/web/20240102030405id_/"))
        with self.assertRaises(XoneSnapshotArchivalRecoveryError):
            build_wayback_replay_url(
                timestamp="2024-01-02",
                original_url="https://x1.xyz/xone",
            )
        with self.assertRaises(XoneSnapshotArchivalRecoveryError):
            build_wayback_replay_url(
                timestamp="20240102030405",
                original_url="javascript:alert(1)",
            )

    def test_original_host_controls_authority_not_archive_host(self):
        self.assertTrue(original_host_is_authoritative("https://x1.xyz/xone"))
        self.assertTrue(original_host_is_authoritative("https://xen.network/xone"))
        self.assertFalse(original_host_is_authoritative("https://example.com/xone"))
        self.assertEqual(
            source_role_for_original_url("https://x1.xyz/xone"), "x1_official"
        )
        self.assertEqual(
            source_role_for_original_url("https://example.com/xone"),
            "secondary_report",
        )

    def test_stable_x_status_and_space_urls_are_recovered_without_content_promotion(self):
        rows = recover_stable_x_urls(
            "Mirror links https://twitter.com/mrJackLevin/status/123456789012345 "
            "and https://x.com/i/spaces/1DXxyExample."
        )
        self.assertEqual(len(rows), 2)
        status = next(row for row in rows if row["kind"] == "x_status")
        self.assertEqual(
            status["url"],
            "https://x.com/mrJackLevin/status/123456789012345",
        )
        self.assertTrue(status["jack_levin_account_match"])
        self.assertTrue(status["stable_primary_url_recovered"])
        self.assertFalse(status["direct_primary_source_recovered"])

    def test_archived_primary_exact_snapshot_block_is_candidate_not_official_truth(self):
        capture = self._capture()
        capture["archival_capture_retrieved"] = True
        text = (
            "The XONE holder snapshot was taken at Ethereum block 23500000. "
            f"The XONE contract is {XONE_CONTRACT}. "
            "This snapshot registry will be used for XNT allocation."
        )
        rows = extract_archival_provenance_candidates(
            text,
            capture=capture,
            observed_at=1.0,
        )
        self.assertGreaterEqual(len(rows), 1)
        row = next(
            item
            for item in rows
            if item["authoritative_exact_snapshot_block_discovered"] is True
        )
        self.assertTrue(row["archival_capture_discovered"])
        self.assertTrue(row["archival_capture_retrieved"])
        self.assertTrue(row["original_host_authoritative"])
        self.assertTrue(row["direct_primary_archival_source_recovered"])
        self.assertEqual(row["snapshot_block_candidates"], [23_500_000])
        self.assertFalse(row["official_xone_snapshot_verified"])
        self.assertFalse(row["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(row["execution_authorized"])

    def test_archived_secondary_claim_cannot_be_authoritative(self):
        capture = self._capture("https://example.com/report/xone-snapshot")
        capture["archival_capture_retrieved"] = True
        rows = extract_archival_provenance_candidates(
            (
                "XONE holders were reportedly snapshotted at Ethereum block "
                f"23500000 for contract {XONE_CONTRACT}."
            ),
            capture=capture,
            observed_at=1.0,
        )
        self.assertGreaterEqual(len(rows), 1)
        self.assertFalse(
            any(
                row["authoritative_exact_snapshot_block_discovered"] is True
                for row in rows
            )
        )
        self.assertFalse(
            any(
                row["direct_primary_archival_source_recovered"] is True
                for row in rows
            )
        )

    def test_rank_archival_captures_prefers_snapshot_paths(self):
        root = self._capture("https://x1.xyz/")
        snap = self._capture("https://x1.xyz/xone-holder-snapshot.json")
        ranked = rank_archival_captures([root, snap])
        self.assertEqual(ranked[0]["original"], snap["original"])
        self.assertGreater(
            archival_url_relevance_score(snap["original"]),
            archival_url_relevance_score(root["original"]),
        )

    def test_diverse_selector_spreads_replays_across_original_hosts(self):
        rows = []
        for host in ("xen.network", "x1.xyz", "docs.x1.xyz"):
            for month in range(1, 7):
                capture = self._capture(
                    f"https://{host}/"
                )
                capture["capture_id"] = f"{host}-{month}"
                capture["timestamp"] = f"2024{month:02d}02030405"
                capture["replay_url"] = build_wayback_replay_url(
                    timestamp=capture["timestamp"],
                    original_url=capture["original"],
                )
                rows.append(capture)

        selected = select_diverse_archival_captures(
            rows,
            max_captures=9,
        )
        hosts = {
            __import__("urllib.parse", fromlist=["urlparse"]).urlparse(
                row["original"]
            ).hostname
            for row in selected
        }
        self.assertEqual(
            hosts,
            {"xen.network", "x1.xyz", "docs.x1.xyz"},
        )
        self.assertEqual(len(selected), 9)

    def test_summary_keeps_zero_result_scoped(self):
        capture = self._capture()
        result = summarize_archival_recovery(
            [capture],
            [],
            stable_primary_urls=[],
        )
        self.assertEqual(
            result["contract_version"],
            XONE_SNAPSHOT_ARCHIVAL_RECOVERY_CONTRACT_VERSION,
        )
        self.assertEqual(result["archival_capture_count"], 1)
        self.assertEqual(result["archival_capture_retrieved_count"], 0)
        self.assertTrue(
            result["zero_authoritative_blocks_are_scoped_archival_evidence_only"]
        )
        self.assertFalse(result["private_or_unpublished_snapshot_absence_proven"])
        self.assertFalse(result["official_xone_snapshot_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_service_preserves_snapshot_authority_boundary(self):
        capture = self._capture("https://example.com/xone-snapshot")
        capture["text"] = (
            "XONE was reportedly snapshotted at Ethereum block 23500000."
        )
        service = CMISXoneXntConversionIntelligenceService()
        result = service.recover_xone_snapshot_archival_sources(
            [capture],
            observed_at=1.0,
        )
        self.assertTrue(result["xone_snapshot_archival_source_recovery_verified"])
        self.assertTrue(result["archival_capture_discovered"])
        self.assertTrue(result["archival_capture_retrieved"])
        self.assertFalse(result["direct_primary_archival_source_recovered"])
        self.assertFalse(result["official_xone_snapshot_verified"])
        self.assertFalse(result["official_registry_artifact_verified"])
        self.assertFalse(result["xone_snapshot_eligibility_verified"])
        self.assertFalse(result["xone_snapshot_xnt_allocation_binding_verified"])
        self.assertFalse(result["xnt_issuance_verified"])
        self.assertFalse(result["cross_chain_correlation_verified"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
