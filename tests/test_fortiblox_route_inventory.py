import unittest

from liquidity_scout.providers.web_discovery import (
    FORTIBLOX_ROUTE_INVENTORY_CONTRACT,
    capture_fortiblox_route_inventory,
    discover_fortiblox_navigation_routes,
    normalize_fortiblox_navigation_urls,
)


ROOT = "https://app.fortiblox.com/"


class FakePage:
    def __init__(self, hrefs):
        self.hrefs = list(hrefs)
        self.goto_calls = []
        self.wait_calls = []
        self.eval_calls = []

    def goto(self, url, *, wait_until, timeout):
        self.goto_calls.append((url, wait_until, timeout))

    def wait_for_timeout(self, milliseconds):
        self.wait_calls.append(milliseconds)

    def eval_on_selector_all(self, selector, expression):
        self.eval_calls.append((selector, expression))
        return list(self.hrefs)


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
        self.kwargs = None
        self.closed = False

    def new_context(self, **kwargs):
        self.kwargs = dict(kwargs)
        return self.context

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser
        self.kwargs = None

    def launch(self, **kwargs):
        self.kwargs = dict(kwargs)
        return self.browser


class FakePlaywright:
    def __init__(self, chromium):
        self.chromium = chromium


class FakeManager:
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


def fake_stack(hrefs):
    page = FakePage(hrefs)
    context = FakeContext(page)
    browser = FakeBrowser(context)
    chromium = FakeChromium(browser)
    manager = FakeManager(FakePlaywright(chromium))
    return manager, chromium, browser, context, page


class FortiBloxRouteInventoryTests(unittest.TestCase):
    def test_navigation_normalization_is_same_host_bounded_and_page_only(self):
        routes = normalize_fortiblox_navigation_urls(
            ROOT,
            [
                "/swap",
                "/bridge",
                "https://app.fortiblox.com/swap",
                "/ramp?ref=campaign",
                "/api/tokens",
                "/llms.txt",
                "https://example.com/foreign",
                "#fragment",
            ],
            max_routes=20,
        )

        self.assertEqual(
            routes,
            [
                "https://app.fortiblox.com/",
                "https://app.fortiblox.com/swap",
                "https://app.fortiblox.com/bridge",
            ],
        )

    def test_route_discovery_reads_anchors_without_clicks(self):
        manager, chromium, browser, context, page = fake_stack(
            ["/swap", "/bridge", "/api/tokens"]
        )

        result = discover_fortiblox_navigation_routes(
            ROOT,
            dwell_seconds=1.5,
            playwright_factory=lambda: manager,
        )

        self.assertEqual(
            result["navigation_routes"],
            [ROOT, ROOT + "swap", ROOT + "bridge"],
        )
        self.assertEqual(chromium.kwargs, {"headless": True})
        self.assertEqual(
            browser.kwargs,
            {"accept_downloads": False, "service_workers": "block"},
        )
        self.assertEqual(page.goto_calls, [(ROOT, "domcontentloaded", 20000)])
        self.assertEqual(page.wait_calls, [1500])
        self.assertEqual(page.eval_calls[0][0], "a[href]")
        self.assertTrue(context.closed)
        self.assertTrue(browser.closed)
        self.assertTrue(manager.entered)
        self.assertTrue(manager.exited)
        self.assertEqual(result["clicks_performed"], 0)
        self.assertEqual(result["forms_submitted"], 0)
        self.assertFalse(result["execution_authorized"])

    def test_inventory_aggregates_only_sanitized_capture_results(self):
        def route_discovery_fn(page_url, **kwargs):
            return {
                "contract": "fortiblox_navigation_route_discovery/v1",
                "navigation_routes": [ROOT, ROOT + "swap", ROOT + "bridge"],
                "execution_authorized": False,
            }

        captures = {
            ROOT: {
                "network_events_seen": 10,
                "observation_count": 1,
                "observations": [
                    {
                        "source_url": ROOT + "api/tokens",
                        "route": {"qualification": "allowed_read_only"},
                        "execution_authorized": False,
                    }
                ],
            },
            ROOT + "swap": {
                "network_events_seen": 15,
                "observation_count": 2,
                "observations": [
                    {
                        "source_url": ROOT + "api/ramp/availability",
                        "route": {"qualification": "allowed_read_only"},
                        "execution_authorized": False,
                    },
                    {
                        "source_url": ROOT + "api/new-surface",
                        "route": {"qualification": "unqualified_get_candidate"},
                        "execution_authorized": False,
                    },
                ],
            },
        }

        def capture_fn(route, **kwargs):
            return captures[route]

        result = capture_fortiblox_route_inventory(
            ROOT,
            max_pages=2,
            route_discovery_fn=route_discovery_fn,
            capture_fn=capture_fn,
        )

        self.assertEqual(result["contract"], FORTIBLOX_ROUTE_INVENTORY_CONTRACT)
        self.assertEqual(result["pages_attempted"], 2)
        self.assertEqual(result["sanitized_observation_count"], 3)
        self.assertEqual(
            result["qualification_counts"],
            {"allowed_read_only": 2, "unqualified_get_candidate": 1},
        )
        self.assertEqual(
            result["unqualified_get_candidates"],
            [ROOT + "api/new-surface"],
        )
        self.assertFalse(result["raw_har_retained"])
        self.assertFalse(result["request_replay_authorized"])
        self.assertFalse(result["payment_authorized"])
        self.assertFalse(result["execution_authorized"])

    def test_inventory_keeps_per_page_failure_visible(self):
        def route_discovery_fn(page_url, **kwargs):
            return {
                "navigation_routes": [ROOT, ROOT + "broken"],
            }

        def capture_fn(route, **kwargs):
            if route.endswith("broken"):
                raise RuntimeError("navigation failed")
            return {
                "network_events_seen": 1,
                "observation_count": 0,
                "observations": [],
            }

        result = capture_fortiblox_route_inventory(
            ROOT,
            route_discovery_fn=route_discovery_fn,
            capture_fn=capture_fn,
        )

        self.assertEqual(result["page_results"][0]["status"], "AVAILABLE")
        self.assertEqual(result["page_results"][1]["status"], "UNAVAILABLE")
        self.assertEqual(
            result["page_results"][1]["error_type"],
            "RuntimeError",
        )
        self.assertFalse(result["execution_authorized"])

    def test_bounds_fail_closed(self):
        with self.assertRaises(ValueError):
            normalize_fortiblox_navigation_urls(ROOT, [], max_routes=21)
        with self.assertRaises(ValueError):
            capture_fortiblox_route_inventory(ROOT, max_pages=11)
        with self.assertRaises(ValueError):
            capture_fortiblox_route_inventory(
                ROOT,
                max_network_events_per_page=151,
            )


if __name__ == "__main__":
    unittest.main()
