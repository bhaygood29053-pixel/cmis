import unittest

from liquidity_scout.providers.x1.xdex import (
    POOL_LIST_URL,
    XDEXAPIError,
    XDEXReadOnlyProvider,
    fetch_pool_list,
)


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append(
            {
                "url": url,
                "params": dict(params),
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


class XDEXPoolListTests(unittest.TestCase):
    def test_pool_list_uses_public_mainnet_contract_and_preserves_addresses(self):
        row = {
            "address": "POOL_PUBLIC_ADDRESS",
            "baseToken": {
                "symbol": "AAA",
                "address": "AAA_PUBLIC_ADDRESS",
                "mint": "AAA_MINT_METADATA",
            },
            "quoteToken": {
                "symbol": "BBB",
                "address": "BBB_PUBLIC_ADDRESS",
                "mint": "BBB_MINT_METADATA",
            },
        }
        session = FakeSession(
            [
                FakeResponse(
                    {
                        "success": True,
                        "total": 1,
                        "data": [row],
                    }
                )
            ]
        )

        pools = fetch_pool_list(session=session)

        self.assertEqual(session.calls[0]["url"], POOL_LIST_URL)
        self.assertEqual(session.calls[0]["params"], {"network": "mainnet"})
        self.assertEqual(pools, [row])
        self.assertIsNot(pools[0], row)
        self.assertEqual(
            pools[0]["baseToken"]["address"],
            "AAA_PUBLIC_ADDRESS",
        )

    def test_pool_list_allows_verified_empty_market_without_fabricating_pool(self):
        session = FakeSession(
            [FakeResponse({"success": True, "total": 0, "data": []})]
        )

        self.assertEqual(fetch_pool_list(session=session), [])

    def test_pool_list_rejects_non_mapping_rows(self):
        session = FakeSession(
            [FakeResponse({"success": True, "data": [{"address": "P1"}, 5]})]
        )

        with self.assertRaisesRegex(
            XDEXAPIError,
            "pool list item 1 must be a JSON object",
        ):
            fetch_pool_list(session=session)

    def test_provider_keeps_pool_network_separate_from_trade_network(self):
        session = FakeSession([FakeResponse({"success": True, "data": []})])
        provider = XDEXReadOnlyProvider(session=session, timeout=9)

        self.assertEqual(provider.network, "X1 Mainnet")
        self.assertEqual(provider.pool_network, "mainnet")
        self.assertEqual(provider.pool_list(), [])
        self.assertEqual(session.calls[0]["params"], {"network": "mainnet"})
        self.assertEqual(session.calls[0]["timeout"], 9)


if __name__ == "__main__":
    unittest.main()
