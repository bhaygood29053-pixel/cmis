import unittest

from liquidity_scout.integrations.moltgrid import MoltGridXDEXCatalog
from liquidity_scout.market import XDEXCatalog as LegacyMarketCatalog
from liquidity_scout.market import fetch_all_pools as legacy_fetch_all_pools
from liquidity_scout.providers.x1 import (
    MARKET_SOURCE,
    X1Provider,
    XDEXCatalog,
    fetch_all_pools,
)


class FakeCatalog:
    def __init__(self):
        self.pools = [{"address": "P1"}, {"address": "P2"}]
        self.xnt_price_usd = "0.55"
        self.last_refresh = 0.0
        self.refresh_calls = 0
        self.refresh_if_needed_calls = 0

    def refresh(self):
        self.refresh_calls += 1
        self.last_refresh = 2000.0
        return self

    def refresh_if_needed(self):
        self.refresh_if_needed_calls += 1
        self.last_refresh = 2000.0
        return self

    def status_text(self):
        return "[catalog] fake"


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def get(self, url, params, headers, timeout):
        self.calls.append({
            "url": url,
            "params": params,
            "headers": headers,
            "timeout": timeout,
        })
        return FakeResponse(self.pages.pop(0))


class X1MarketProviderTests(unittest.TestCase):
    def test_provider_identifies_chain_and_source(self):
        provider = X1Provider(catalog=FakeCatalog())

        self.assertEqual(provider.chain, "x1")
        self.assertEqual(provider.market_source, "X1.Ninja/XDEX")
        self.assertEqual(MARKET_SOURCE, "X1.Ninja/XDEX")

    def test_provider_exposes_catalog_facts_without_recalculation(self):
        catalog = FakeCatalog()
        provider = X1Provider(catalog=catalog)

        result = provider.market_catalog()

        self.assertEqual(result["chain"], "x1")
        self.assertEqual(result["source"], "X1.Ninja/XDEX")
        self.assertEqual(result["pools"], catalog.pools)
        self.assertIsNot(result["pools"], catalog.pools)
        self.assertEqual(result["xnt_price_usd"], "0.55")
        self.assertIsNone(result["observed_at"])

    def test_provider_refresh_delegates_and_uses_actual_catalog_timestamp(self):
        catalog = FakeCatalog()
        provider = X1Provider(catalog=catalog)

        returned = provider.refresh()

        self.assertIs(returned, provider)
        self.assertEqual(catalog.refresh_calls, 1)
        self.assertEqual(provider.last_refresh, 2000.0)
        self.assertEqual(provider.market_catalog()["observed_at"], 2000.0)

    def test_provider_refresh_if_needed_delegates(self):
        catalog = FakeCatalog()
        provider = X1Provider(catalog=catalog)

        returned = provider.refresh_if_needed()

        self.assertIs(returned, provider)
        self.assertEqual(catalog.refresh_if_needed_calls, 1)
        self.assertEqual(provider.last_refresh, 2000.0)

    def test_provider_status_text_delegates(self):
        provider = X1Provider(catalog=FakeCatalog())

        self.assertEqual(provider.status_text(), "[catalog] fake")

    def test_legacy_market_imports_are_provider_compatibility_exports(self):
        self.assertIs(LegacyMarketCatalog, XDEXCatalog)
        self.assertIs(legacy_fetch_all_pools, fetch_all_pools)

    def test_moltgrid_catalog_remains_subclass_compatible(self):
        self.assertTrue(issubclass(MoltGridXDEXCatalog, XDEXCatalog))

    def test_provider_transport_preserves_existing_pagination_semantics(self):
        session = FakeSession([
            {
                "pools": [{"address": "P1"}],
                "total": 2,
                "xntPriceUsd": "0.55",
            },
            {
                "pools": [{"address": "P2"}],
                "total": 2,
                "xntPriceUsd": "0.56",
            },
        ])

        pools, xnt_price = fetch_all_pools(
            "test-key",
            session=session,
            page_size=1,
            sleep_seconds=0,
        )

        self.assertEqual([row["address"] for row in pools], ["P1", "P2"])
        self.assertEqual(xnt_price, "0.55")
        self.assertEqual(session.calls[0]["params"], {"limit": 1, "offset": 0})
        self.assertEqual(session.calls[1]["params"], {"limit": 1, "offset": 1})
        self.assertEqual(
            session.calls[0]["headers"],
            {"Authorization": "Bearer test-key"},
        )


if __name__ == "__main__":
    unittest.main()
