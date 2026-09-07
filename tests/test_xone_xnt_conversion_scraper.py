from __future__ import annotations

import unittest

from liquidity_scout.providers.xone_xnt import (
    DISCOVERED,
    SCRAPER_CONTRACT,
    XoneXntContentError,
    XoneXntConversionScraper,
    XoneXntSourceBoundaryError,
    extract_xone_xnt_claims,
    group_claims_for_review,
    parse_sitemap,
    source_catalog,
    source_ids,
)
from liquidity_scout.services.cmis_xone_xnt_conversion_intelligence import (
    CMISXoneXntConversionIntelligenceService,
)


class FakeResponse:
    def __init__(
        self,
        body,
        *,
        url,
        status_code=200,
        content_type="text/html; charset=utf-8",
        headers=None,
    ):
        self.content = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.headers.update(dict(headers or {}))


class FakeSession:
    def __init__(self, response=None, *, routes=None):
        self.response = response
        self.routes = dict(routes or {})
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.routes:
            response = self.routes.get(url)
            if response is None:
                raise RuntimeError(f"unexpected URL {url}")
            return response
        if self.response is None:
            raise RuntimeError("no fake response configured")
        return self.response


class XoneXntConversionScraperTests(unittest.TestCase):
    def test_registry_is_dedicated_and_never_promoted(self):
        self.assertEqual(source_ids(), ("x1_official", "x1_docs", "x1report"))
        catalog = source_catalog()
        self.assertEqual(len(catalog), 3)
        self.assertTrue(all(row["xone_xnt_only"] for row in catalog))
        self.assertTrue(all(row["read_only"] for row in catalog))
        self.assertTrue(all(row["web_claim_verified"] is False for row in catalog))
        self.assertTrue(all(row["cmis_verified"] is False for row in catalog))
        self.assertTrue(all(row["execution_authorized"] is False for row in catalog))

    def test_claim_extraction_tracks_conversion_burn_lock_and_handoffs(self):
        text_value = (
            "XONE is an Ethereum ERC-20 token. "
            "XONE holders may convert 1:1 into XNT, with 50% burned. "
            "The resulting XNT is locked until October 6, 2026."
        )
        claims = extract_xone_xnt_claims(
            text_value,
            source_id="x1report",
            url="https://x1report.com/article/example",
            observed_at=123.0,
        )
        self.assertGreaterEqual(len(claims), 1)
        merged = " ".join(claim["excerpt"] for claim in claims)
        self.assertIn("XONE", merged)
        self.assertIn("XNT", merged)
        topics = {topic for claim in claims for topic in claim["topics"]}
        self.assertIn("conversion", topics)
        self.assertIn("burn", topics)
        self.assertTrue(any("1:1" in claim["normalized_values"]["ratios"] for claim in claims))
        self.assertTrue(any("50%" in claim["normalized_values"]["percentages"] for claim in claims))
        self.assertTrue(
            any("October 6, 2026" in claim["normalized_values"]["dates"] for claim in claims)
        )
        for claim in claims:
            self.assertEqual(claim["truth_state"]["discovery_state"], DISCOVERED)
            self.assertFalse(claim["truth_state"]["web_claim_verified"])
            self.assertFalse(claim["truth_state"]["ethereum_event_verified"])
            self.assertFalse(claim["truth_state"]["x1_event_verified"])
            self.assertFalse(claim["truth_state"]["cross_chain_correlation_verified"])
            self.assertFalse(claim["execution_authorized"])
        targets = {
            handoff["target"]
            for claim in claims
            for handoff in claim["corroboration_handoff"]
        }
        self.assertIn("Ethereum RPC / verified XONE contract", targets)
        self.assertIn("X1 RPC / verified XNT distribution or vesting account", targets)
        self.assertIn("CMIS cross-chain correlator", targets)

    def test_non_xone_xnt_content_is_ignored(self):
        claims = extract_xone_xnt_claims(
            "Validator XNT unlocks on October 6, 2026. XEN Prime burns XEN.",
            source_id="x1report",
            url="https://x1report.com/article/not-xone",
            observed_at=1.0,
        )
        self.assertEqual(claims, [])

    def test_potential_conflict_is_review_flag_not_verified_conflict(self):
        first = extract_xone_xnt_claims(
            "XONE converts 1:1 to XNT.",
            source_id="x1report",
            url="https://x1report.com/article/one",
            observed_at=1.0,
        )
        second = extract_xone_xnt_claims(
            "XONE converts 2:1 to XNT.",
            source_id="x1_docs",
            url="https://docs.x1.xyz/example",
            observed_at=2.0,
        )
        groups = group_claims_for_review([*first, *second])
        conversion = next(group for group in groups if group["topic"] == "conversion")
        self.assertTrue(conversion["potential_conflict"])
        self.assertIn("ratios", conversion["conflict_dimensions"])
        self.assertFalse(conversion["conflict_verified"])
        self.assertFalse(conversion["cmis_verified"])

    def test_sitemap_ranking_finds_relevant_xnt_and_unlock_pages(self):
        sitemap = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
          <url>
            <loc>https://x1report.com/article/random-game</loc>
            <image:image><image:title>Random game</image:title></image:image>
          </url>
          <url>
            <loc>https://x1report.com/article/xnt-ratchet-analysis</loc>
            <lastmod>2026-06-30</lastmod>
            <image:image><image:title>XNT investor vesting and October 6 unlock</image:title></image:image>
          </url>
          <url>
            <loc>https://x1report.com/article/xone-conversion</loc>
            <image:image><image:title>XONE conversion to XNT</image:title></image:image>
          </url>
          <url>
            <loc>https://example.com/escape</loc>
            <image:image><image:title>XONE conversion</image:title></image:image>
          </url>
        </urlset>"""
        candidates = parse_sitemap(sitemap, source_id="x1report", max_urls=10)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["url"], "https://x1report.com/article/xone-conversion")
        self.assertGreater(candidates[0]["relevance_score"], 0)
        self.assertNotIn("https://example.com/escape", [row["url"] for row in candidates])

    def test_scrape_url_is_bounded_and_preserves_non_verification(self):
        url = "https://x1report.com/article/xone-conversion"
        body = """
        <html><body>
        <script>XONE converts 99:1 to XNT</script>
        <p>XONE on Ethereum may migrate 1:1 to XNT.</p>
        </body></html>
        """
        session = FakeSession(FakeResponse(body, url=url))
        scraper = XoneXntConversionScraper(
            session=session,
            observed_at_fn=lambda: 456.0,
        )
        result = scraper.scrape_url("x1report", url)
        self.assertEqual(result["contract"], SCRAPER_CONTRACT)
        self.assertEqual(result["retrieval"]["observed_at"], 456.0)
        self.assertEqual(result["candidate_claim_count"], 1)
        self.assertIn("1:1", result["claims"][0]["normalized_values"]["ratios"])
        self.assertNotIn("99:1", result["claims"][0]["excerpt"])
        self.assertFalse(result["truth_state"]["cmis_verified"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(len(session.calls), 1)
        self.assertFalse(session.calls[0][1]["allow_redirects"])

    def test_redirect_cannot_escape_source_boundary(self):
        url = "https://x1report.com/article/xone"
        session = FakeSession(
            FakeResponse(
                "",
                url=url,
                status_code=302,
                headers={"Location": "https://example.com/escape"},
            )
        )
        scraper = XoneXntConversionScraper(session=session)
        with self.assertRaises(XoneXntSourceBoundaryError):
            scraper.scrape_url("x1report", url)
        self.assertEqual(len(session.calls), 1)
        self.assertFalse(session.calls[0][1]["allow_redirects"])

    def test_oversized_response_fails_closed(self):
        url = "https://x1report.com/article/xone"
        scraper = XoneXntConversionScraper(
            session=FakeSession(
                FakeResponse("0123456789", url=url, content_type="text/plain")
            ),
            max_bytes=5,
        )
        with self.assertRaisesRegex(XoneXntContentError, "max_bytes=5"):
            scraper.scrape_url("x1report", url)

    def test_internal_service_normalizes_multiple_sources_without_promotion(self):
        service = CMISXoneXntConversionIntelligenceService(
            scraper=XoneXntConversionScraper(session=FakeSession())
        )
        result = service.normalize_documents(
            [
                {
                    "source_id": "x1report",
                    "url": "https://x1report.com/article/one",
                    "text": "XONE converts 1:1 to XNT on October 6, 2026.",
                },
                {
                    "source_id": "x1_docs",
                    "url": "https://docs.x1.xyz/example",
                    "text": "XONE conversion to XNT remains subject to vesting.",
                },
            ],
            observed_at=1000.0,
        )
        self.assertEqual(result["service_contract"], "xone_xnt_conversion_intelligence/v1")
        self.assertGreaterEqual(result["candidate_claim_count"], 2)
        self.assertFalse(result["web_claim_verified"])
        self.assertFalse(result["cross_chain_correlation_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
