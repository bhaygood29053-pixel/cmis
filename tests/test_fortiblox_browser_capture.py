import json
import unittest

from liquidity_scout.providers.web_discovery import (
    FORTIBLOX_BROWSER_CAPTURE_CONTRACT,
    capture_fortiblox_page_network,
)
from liquidity_scout.services.cmis_web_discovery import CMISWebDiscoveryService


PAGE_URL = "https://app.fortiblox.com/"
TOKENS_URL = "https://app.fortiblox.com/api/tokens"


class FakeRequest:
    def __init__(
        self,
        *,
        method="GET",
        url=TOKENS_URL,
        post_data=None,
    ):
        self.method = method
        self.url = url
        self.post_data = post_data
        self.headers = {
            "referer": PAGE_URL,
            "authorization": "raw-auth-must-not-survive",
            "payment-signature": "raw-payment-must-not-survive",
            "content-type": "application/json",
        }


class FakeResponse:
    def __init__(
        self,
        request=None,
        *,
        status=200,
        headers=None,
        body=None,
    ):
        self.request = request or FakeRequest()
        self.status = status
        self.headers = dict(
            headers
            or {
                "content-type": "application/json",
                "content-length": "100",
                "set-cookie": "raw-set-cookie-must-not-survive",
                "payment-required": "raw-payment-required-must-not-survive",
            }
        )
        payload = (
            body
            if body is not None
            else json.dumps(
                {
                    "ok": True,
                    "marker": "raw-response-marker-must-not-survive",
                }
            ).encode("utf-8")
        )
        self._body = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
        self.body_calls = 0

    def body(self):
        self.body_calls += 1
        return self._body


class FakePage:
    def __init__(self, responses):
        self.responses = list(responses)
        self.handlers = {}
        self.goto_calls = []
        self.wait_calls = []

    def on(self, event, callback):
        self.handlers[event] = callback

    def goto(self, url, *, wait_until, timeout):
        self.goto_calls.append(
            {
                "url": url,
                "wait_until": wait_until,
                "timeout": timeout,
            }
        )
        callback = self.handlers.get("response")
        if callback is not None:
            for response in self.responses:
                callback(response)

    def wait_for_timeout(self, milliseconds):
        self.wait_calls.append(milliseconds)


class FakeContext:
    def __init__(self, page):
        self.page = page
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, context):
        self.context = context
        self.new_context_kwargs = None
        self.closed = False

    def new_context(self, **kwargs):
        self.new_context_kwargs = dict(kwargs)
        return self.context

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser
        self.launch_kwargs = None

    def launch(self, **kwargs):
        self.launch_kwargs = dict(kwargs)
        return self.browser


class FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium


class FakePlaywrightManager:
    def __init__(self, playwright):
        self.playwright = playwright
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self.playwright

    def __exit__(self, exc_type, exc, tb):
        self.exited = True
        return False


def fake_stack(responses):
    page = FakePage(responses)
    context = FakeContext(page)
    browser = FakeBrowser(context)
    chromium = FakeChromium(browser)
    manager = FakePlaywrightManager(FakePlaywright(chromium))
    return manager, chromium, browser, context, page


class FortiBloxBrowserCaptureTests(unittest.TestCase):
    def test_passive_capture_emits_only_sanitized_observation(self):
        response = FakeResponse()
        manager, chromium, browser, context, page = fake_stack([response])

        result = capture_fortiblox_page_network(
            PAGE_URL,
            navigation_timeout_ms=12_000,
            dwell_seconds=2.5,
            max_network_events=10,
            playwright_factory=lambda: manager,
        )

        self.assertEqual(result["contract"], FORTIBLOX_BROWSER_CAPTURE_CONTRACT)
        self.assertEqual(result["requested_page_url"], PAGE_URL)
        self.assertEqual(result["source_id"], "fortiblox_app")
        self.assertEqual(result["observation_count"], 1)
        self.assertEqual(result["network_events_seen"], 1)
        self.assertEqual(
            result["observations"][0]["route"]["qualification"],
            "allowed_read_only",
        )

        serialized = json.dumps(result)
        self.assertNotIn("raw-auth-must-not-survive", serialized)
        self.assertNotIn("raw-payment-must-not-survive", serialized)
        self.assertNotIn("raw-set-cookie-must-not-survive", serialized)
        self.assertNotIn("raw-payment-required-must-not-survive", serialized)
        self.assertNotIn("raw-response-marker-must-not-survive", serialized)

        self.assertFalse(result["raw_har_retained"])
        self.assertFalse(result["raw_network_records_retained"])
        self.assertFalse(result["raw_request_bodies_retained"])
        self.assertFalse(result["raw_response_bodies_retained"])
        self.assertFalse(result["request_replay_authorized"])
        self.assertFalse(result["payment_performed"])
        self.assertFalse(result["execution_authorized"])

    def test_capture_uses_ephemeral_one_page_context(self):
        manager, chromium, browser, context, page = fake_stack([FakeResponse()])

        result = capture_fortiblox_page_network(
            PAGE_URL,
            headless=False,
            dwell_seconds=1.25,
            playwright_factory=lambda: manager,
        )

        self.assertEqual(chromium.launch_kwargs, {"headless": False})
        self.assertEqual(
            browser.new_context_kwargs,
            {
                "accept_downloads": False,
                "service_workers": "block",
            },
        )
        self.assertEqual(
            page.goto_calls,
            [
                {
                    "url": PAGE_URL,
                    "wait_until": "domcontentloaded",
                    "timeout": 20_000,
                }
            ],
        )
        self.assertEqual(page.wait_calls, [1250])
        self.assertTrue(context.closed)
        self.assertTrue(browser.closed)
        self.assertTrue(manager.entered)
        self.assertTrue(manager.exited)

        self.assertTrue(result["capture_bounds"]["one_page"])
        self.assertTrue(result["browser_context_ephemeral"])
        self.assertFalse(result["browser_storage_state_supplied"])
        self.assertFalse(result["downloads_allowed"])
        self.assertEqual(result["clicks_performed"], 0)
        self.assertEqual(result["forms_submitted"], 0)
        self.assertFalse(result["wallet_interaction_performed"])
        self.assertFalse(result["authentication_performed"])

    def test_foreign_page_is_rejected_before_browser_launch(self):
        manager, chromium, browser, context, page = fake_stack([])

        with self.assertRaises(Exception):
            capture_fortiblox_page_network(
                "https://example.com/",
                playwright_factory=lambda: manager,
            )

        self.assertFalse(manager.entered)
        self.assertIsNone(chromium.launch_kwargs)
        self.assertIsNone(browser.new_context_kwargs)
        self.assertFalse(context.closed)
        self.assertEqual(page.goto_calls, [])

    def test_foreign_network_target_is_not_read_or_returned(self):
        foreign = FakeResponse(
            request=FakeRequest(url="https://example.com/api/tokens")
        )
        manager, _, _, _, _ = fake_stack([foreign])

        result = capture_fortiblox_page_network(
            PAGE_URL,
            dwell_seconds=0,
            playwright_factory=lambda: manager,
        )

        self.assertEqual(result["network_events_seen"], 1)
        self.assertEqual(result["observation_count"], 0)
        self.assertEqual(foreign.body_calls, 0)

    def test_execution_route_is_not_read_or_returned(self):
        request = FakeRequest(
            method="POST",
            url="https://app.fortiblox.com/api/tx/build",
            post_data=json.dumps({"transaction": "never-read"}),
        )
        response = FakeResponse(request=request)
        manager, _, _, _, _ = fake_stack([response])

        result = capture_fortiblox_page_network(
            PAGE_URL,
            dwell_seconds=0,
            playwright_factory=lambda: manager,
        )

        self.assertEqual(result["network_events_seen"], 1)
        self.assertEqual(result["observation_count"], 0)
        self.assertEqual(response.body_calls, 0)
        self.assertFalse(result["execution_authorized"])

    def test_non_data_asset_is_not_read(self):
        html = FakeResponse(
            request=FakeRequest(url="https://app.fortiblox.com/swap"),
            headers={"content-type": "text/html"},
            body=b"<html>raw page</html>",
        )
        manager, _, _, _, _ = fake_stack([html])

        result = capture_fortiblox_page_network(
            PAGE_URL,
            dwell_seconds=0,
            playwright_factory=lambda: manager,
        )

        self.assertEqual(result["observation_count"], 0)
        self.assertEqual(html.body_calls, 0)

    def test_network_event_limit_is_enforced(self):
        responses = [FakeResponse() for _ in range(5)]
        manager, _, _, _, _ = fake_stack(responses)

        result = capture_fortiblox_page_network(
            PAGE_URL,
            max_network_events=2,
            dwell_seconds=0,
            playwright_factory=lambda: manager,
        )

        self.assertEqual(result["network_events_seen"], 2)
        self.assertEqual(result["observation_count"], 2)
        self.assertEqual(
            [item["capture_event_index"] for item in result["observations"]],
            [0, 1],
        )
        self.assertEqual(
            [response.body_calls for response in responses],
            [1, 1, 0, 0, 0],
        )

    def test_bounds_fail_closed_before_browser_launch(self):
        manager, _, _, _, _ = fake_stack([])

        invalid_kwargs = [
            {"navigation_timeout_ms": 999},
            {"navigation_timeout_ms": 30_001},
            {"dwell_seconds": -0.1},
            {"dwell_seconds": 10.1},
            {"max_network_events": 0},
            {"max_network_events": 251},
        ]
        for kwargs in invalid_kwargs:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    capture_fortiblox_page_network(
                        PAGE_URL,
                        playwright_factory=lambda: manager,
                        **kwargs,
                    )
        self.assertFalse(manager.entered)

    def test_service_wrapper_preserves_authority_boundaries(self):
        manager, _, _, _, _ = fake_stack([FakeResponse()])
        service = CMISWebDiscoveryService()

        result = service.capture_fortiblox_browser(
            PAGE_URL,
            dwell_seconds=0,
            playwright_factory=lambda: manager,
        )

        self.assertEqual(result["source_id"], "fortiblox_app")
        self.assertEqual(result["capture"]["observation_count"], 1)
        self.assertFalse(result["request_replay_authorized"])
        self.assertFalse(result["background_monitoring_authorized"])
        self.assertFalse(result["payment_authorized"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
