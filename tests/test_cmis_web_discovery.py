from __future__ import annotations

from hashlib import sha256
import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    GitHubWebDiscoveryProvider,
    SourceBoundaryError,
    WebDiscoveryContentError,
    X1ExplorerDiscoveryProvider,
    provider_catalog,
    provider_ids,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


class FakeResponse:
    def __init__(
        self,
        body,
        *,
        url,
        status_code=200,
        content_type="text/html; charset=utf-8",
    ):
        self.content = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.encoding = "utf-8"


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


class FailingSession:
    def get(self, url, **kwargs):
        raise RuntimeError("provider unavailable")


class CMISWebDiscoveryTests(unittest.TestCase):
    def test_registry_contains_all_six_initial_sources(self):
        self.assertEqual(
            provider_ids(),
            (
                "x1_explorer",
                "xdex",
                "x1_ninja",
                "x1report",
                "x1_docs",
                "github",
            ),
        )
        catalog = provider_catalog()
        self.assertEqual(len(catalog), 6)
        self.assertTrue(all(row["read_only"] for row in catalog))
        self.assertTrue(all(row["discovery_only"] for row in catalog))
        self.assertTrue(all(row["cmis_verified"] is False for row in catalog))
        self.assertTrue(
            all(row["execution_authorized"] is False for row in catalog)
        )

    def test_source_allowlist_rejects_foreign_url(self):
        provider = X1ExplorerDiscoveryProvider(
            session=FakeSession(),
        )
        with self.assertRaises(SourceBoundaryError):
            provider.discover_url("https://example.com/tx/abc")

    def test_redirect_cannot_escape_source_allowlist(self):
        provider = X1ExplorerDiscoveryProvider(
            session=FakeSession(
                FakeResponse(
                    "<html>redirected</html>",
                    url="https://example.com/stolen",
                )
            )
        )
        with self.assertRaises(SourceBoundaryError):
            provider.discover_url("https://explorer.mainnet.x1.xyz/tx/abc")

    def test_html_discovery_is_bounded_and_never_promoted(self):
        body = b"""
        <html>
          <head><title>Pool Evidence</title></head>
          <body>
            XNT liquidity observation
            <a href="/tx/abc">transaction</a>
            <a href="https://example.com/outside">outside</a>
            <script>ignore secret-looking script content</script>
          </body>
        </html>
        """
        response = FakeResponse(
            body,
            url="https://explorer.mainnet.x1.xyz/address/pool",
        )
        provider = X1ExplorerDiscoveryProvider(
            session=FakeSession(response),
            observed_at_fn=lambda: 123.0,
        )

        result = provider.discover_url(
            "https://explorer.mainnet.x1.xyz/address/pool",
            query="XNT liquidity",
        )

        self.assertEqual(result["source"]["id"], "x1_explorer")
        self.assertEqual(result["retrieval"]["observed_at"], 123.0)
        self.assertEqual(
            result["retrieval"]["body_sha256"],
            sha256(body).hexdigest(),
        )
        self.assertEqual(result["content"]["title"], "Pool Evidence")
        self.assertIn("XNT liquidity observation", result["content"]["text_excerpt"])
        self.assertNotIn("secret-looking", result["content"]["text_excerpt"])
        self.assertEqual(
            result["content"]["links"],
            ["https://explorer.mainnet.x1.xyz/tx/abc"],
        )
        self.assertEqual(result["content"]["external_links_omitted"], 1)
        self.assertTrue(result["query"]["matched"])
        self.assertEqual(result["truth_state"]["discovery_state"], DISCOVERED)
        self.assertFalse(result["truth_state"]["web_claim_verified"])
        self.assertFalse(result["truth_state"]["cmis_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_response_larger_than_bound_fails_closed(self):
        provider = X1ExplorerDiscoveryProvider(
            session=FakeSession(
                FakeResponse(
                    b"0123456789",
                    url="https://explorer.mainnet.x1.xyz/",
                    content_type="text/plain",
                )
            ),
            max_bytes=5,
        )
        with self.assertRaisesRegex(WebDiscoveryContentError, "max_bytes=5"):
            provider.discover_url()

    def test_json_discovery_preserves_raw_shape_as_candidate_text(self):
        body = b'{"sha":"abc","verified":true,"count":0}'
        provider = GitHubWebDiscoveryProvider(
            session=FakeSession(
                FakeResponse(
                    body,
                    url="https://api.github.com/repos/example/repo",
                    content_type="application/json",
                )
            )
        )

        result = provider.discover_url(
            "https://api.github.com/repos/example/repo",
            query="sha abc",
        )

        self.assertEqual(result["content"]["kind"], "json")
        self.assertIn('"sha":"abc"', result["content"]["text_excerpt"])
        self.assertTrue(result["query"]["matched"])
        self.assertFalse(result["truth_state"]["web_claim_verified"])
        self.assertFalse(result["truth_state"]["cmis_verified"])

    def test_crawl_obeys_page_and_depth_bounds(self):
        root = "https://explorer.mainnet.x1.xyz/"
        one = "https://explorer.mainnet.x1.xyz/one"
        two = "https://explorer.mainnet.x1.xyz/two"
        session = FakeSession(
            routes={
                root: FakeResponse(
                    '<html><a href="/one">one</a><a href="/two">two</a></html>',
                    url=root,
                ),
                one: FakeResponse(
                    "<html>XNT target evidence</html>",
                    url=one,
                ),
                two: FakeResponse(
                    "<html>second candidate</html>",
                    url=two,
                ),
            }
        )
        provider = X1ExplorerDiscoveryProvider(session=session)

        result = provider.crawl(
            root,
            query="target",
            max_pages=2,
            max_depth=1,
        )

        self.assertEqual(result["pages_collected"], 2)
        self.assertEqual([page["crawl_depth"] for page in result["pages"]], [0, 1])
        self.assertEqual(result["matched_page_indexes"], [1])
        self.assertEqual(len(session.calls), 2)

    def test_internal_service_does_not_enter_public_capability_state(self):
        service = CMISWebDiscoveryService()
        result = service.sources()

        self.assertEqual(result["service_contract"], "cmis_web_discovery/v1")
        self.assertEqual(result["state"], "internal_foundation")
        self.assertEqual(len(result["sources"]), 6)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_multi_source_collection_keeps_provider_failure_visible(self):
        available = FakeSession(
            FakeResponse(
                "<html>X1 evidence</html>",
                url="https://explorer.mainnet.x1.xyz/",
            )
        )
        service = CMISWebDiscoveryService()

        result = service.discover_many(
            targets={
                "x1_explorer": None,
                "x1report": None,
            },
            query="X1",
            provider_kwargs_by_source={
                "x1_explorer": {"session": available},
                "x1report": {"session": FailingSession()},
            },
        )

        self.assertEqual(result["requested_source_count"], 2)
        by_source = {row["source_id"]: row for row in result["results"]}
        self.assertEqual(
            by_source["x1_explorer"]["availability"]["status"],
            "AVAILABLE",
        )
        self.assertEqual(
            by_source["x1report"]["availability"]["status"],
            "UNAVAILABLE",
        )
        self.assertIsNone(by_source["x1report"]["discovery"])
        self.assertFalse(by_source["x1report"]["cmis_verified"])
        self.assertFalse(by_source["x1report"]["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
