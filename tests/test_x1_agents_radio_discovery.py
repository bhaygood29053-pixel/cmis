from __future__ import annotations

import unittest

from liquidity_scout.providers.web_discovery import (
    DISCOVERED,
    SourceBoundaryError,
    X1_AGENTS_RADIO_SOURCE,
    X1AgentsRadioDiscoveryProvider,
    provider_catalog,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


BOOTSTRAP = "https://x1radio.vercel.app/api/bootstrap"
CURRENT_BOOTSTRAP = "https://x1agentsradio.xyz/api/bootstrap"


class FakeResponse:
    def __init__(
        self,
        body,
        *,
        url,
        status_code=200,
        content_type="application/json",
        headers=None,
    ):
        self.content = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        self.headers.update(dict(headers or {}))
        self.encoding = "utf-8"


class FakeSession:
    def __init__(self, *, routes):
        self.routes = dict(routes)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.routes.get(url)
        if response is None:
            raise RuntimeError(f"unexpected URL {url}")
        return response


class X1AgentsRadioDiscoveryTests(unittest.TestCase):
    def test_source_registration_is_discovery_only(self):
        self.assertEqual(X1_AGENTS_RADIO_SOURCE.source_id, "x1_agents_radio")
        self.assertEqual(
            X1_AGENTS_RADIO_SOURCE.allowed_hosts,
            ("x1radio.vercel.app", "x1agentsradio.xyz"),
        )
        self.assertEqual(X1_AGENTS_RADIO_SOURCE.default_url, BOOTSTRAP)

        row = next(
            item
            for item in provider_catalog()
            if item["source_id"] == "x1_agents_radio"
        )
        self.assertTrue(row["read_only"])
        self.assertTrue(row["discovery_only"])
        self.assertFalse(row["cmis_verified"])
        self.assertFalse(row["public_service_promoted"])
        self.assertFalse(row["scout_reliance_promoted"])
        self.assertFalse(row["execution_authorized"])

    def test_bootstrap_json_remains_candidate_metadata(self):
        body = (
            '{"programs":[{"program_id":"abc","name":"Example",'
            '"category":"dex"}],"watcher":{"healthy":true}}'
        )
        provider = X1AgentsRadioDiscoveryProvider(
            session=FakeSession(
                routes={
                    BOOTSTRAP: FakeResponse(body, url=BOOTSTRAP),
                }
            ),
            observed_at_fn=lambda: 789.0,
        )

        result = provider.discover_url(query="Example dex")

        self.assertEqual(result["source"]["id"], "x1_agents_radio")
        self.assertEqual(result["retrieval"]["method"], "HTTP_GET")
        self.assertEqual(result["retrieval"]["observed_at"], 789.0)
        self.assertEqual(result["content"]["kind"], "json")
        self.assertTrue(result["query"]["matched"])
        self.assertEqual(
            result["truth_state"]["discovery_state"],
            DISCOVERED,
        )
        self.assertFalse(result["truth_state"]["web_claim_verified"])
        self.assertFalse(result["truth_state"]["cmis_verified"])
        self.assertFalse(result["truth_state"]["source_independence_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_legacy_redirect_to_current_host_is_allowed_but_not_promoted(self):
        session = FakeSession(
            routes={
                BOOTSTRAP: FakeResponse(
                    "",
                    url=BOOTSTRAP,
                    status_code=308,
                    content_type="text/plain",
                    headers={"Location": CURRENT_BOOTSTRAP},
                ),
                CURRENT_BOOTSTRAP: FakeResponse(
                    '{"programs":[]}',
                    url=CURRENT_BOOTSTRAP,
                ),
            }
        )
        provider = X1AgentsRadioDiscoveryProvider(session=session)

        result = provider.discover_url(BOOTSTRAP)

        self.assertEqual(result["retrieval"]["final_url"], CURRENT_BOOTSTRAP)
        self.assertEqual(len(result["retrieval"]["redirects"]), 1)
        self.assertFalse(result["truth_state"]["cmis_verified"])
        self.assertFalse(result["execution_authorized"])

    def test_subscriber_and_foreign_routes_fail_closed(self):
        provider = X1AgentsRadioDiscoveryProvider(
            session=FakeSession(routes={}),
        )

        with self.assertRaises(SourceBoundaryError):
            provider.discover_url("https://x1radio.vercel.app/api/programs")

        with self.assertRaises(SourceBoundaryError):
            provider.discover_url("https://x1agentsradio.xyz/api/digest/latest")

        with self.assertRaises(SourceBoundaryError):
            provider.discover_url("https://example.com/api/bootstrap")

    def test_service_discovers_radio_without_public_promotion(self):
        service = CMISWebDiscoveryService()
        result = service.discover(
            "x1_agents_radio",
            provider_kwargs={
                "session": FakeSession(
                    routes={
                        BOOTSTRAP: FakeResponse(
                            '{"deployments":[]}',
                            url=BOOTSTRAP,
                        ),
                    }
                )
            },
        )

        self.assertEqual(result["source_id"], "x1_agents_radio")
        self.assertTrue(result["read_only"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
