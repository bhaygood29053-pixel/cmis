import unittest
from unittest.mock import patch

from liquidity_scout.cmis.gateway import CMISGateway
from liquidity_scout.services.cmis_contract import build_service_envelope


class ExplodingMarketProvider:
    def refresh_if_needed(self):
        raise AssertionError("native XNT tokenomics must not require XDEX resolution")


class FakeSupplyProvider:
    def __init__(self):
        self.total_calls = 0
        self.circulating_calls = 0

    def get_total_supply(self):
        self.total_calls += 1
        return {
            "chain": "x1",
            "asset": "XNT",
            "network": "mainnet",
            "metric": "total_supply",
            "supply": "1067069623",
            "supply_verified": True,
            "representation": "provider_integer_text",
            "source": "api.x1.xyz /v1/supply/total",
        }

    def get_circulating_supply(self):
        self.circulating_calls += 1
        return {
            "chain": "x1",
            "asset": "XNT",
            "network": "mainnet",
            "metric": "circulating_supply",
            "supply": "13810247",
            "supply_verified": True,
            "representation": "provider_integer_text",
            "source": "api.x1.xyz /v1/supply/circulating",
        }


class CMISXNTNativeGatewayTests(unittest.TestCase):
    def test_plain_xnt_tokenomics_uses_native_supply_provider(self):
        supply = FakeSupplyProvider()
        gateway = CMISGateway(
            x1_market_provider=ExplodingMarketProvider(),
            x1_supply_provider=supply,
        )

        response = gateway.dispatch({
            "service": "tokenomics",
            "chain": "x1",
            "asset": "XNT",
            "params": {},
        })

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["asset"]["symbol"], "XNT")
        self.assertEqual(response["asset"]["name"], "XNT")
        self.assertIsNone(response["asset"]["mint"])
        self.assertEqual(response["data"]["scope"], "native_network")
        self.assertEqual(response["data"]["current_total_supply"], "1067069623")
        self.assertEqual(response["data"]["circulating_supply"], "13810247")
        self.assertEqual(supply.total_calls, 1)
        self.assertEqual(supply.circulating_calls, 1)

    def test_lowercase_xnt_also_uses_native_identity(self):
        gateway = CMISGateway(
            x1_market_provider=ExplodingMarketProvider(),
            x1_supply_provider=FakeSupplyProvider(),
        )

        response = gateway.dispatch({
            "service": "tokenomics",
            "chain": "x1",
            "asset": "xnt",
            "params": {},
        })

        self.assertEqual(response["asset"]["name"], "XNT")
        self.assertEqual(response["data"]["asset_type"], "native")

    def test_explicit_mint_keeps_mint_scoped_tokenomics(self):
        supply = FakeSupplyProvider()
        expected = build_service_envelope(
            "tokenomics",
            "x1",
            "partial",
            asset={"symbol": "WXNT", "name": "Wrapped XNT", "mint": "MintWrapped"},
        )
        gateway = CMISGateway(
            x1_market_provider=ExplodingMarketProvider(),
            x1_supply_provider=supply,
        )

        with patch(
            "liquidity_scout.cmis.gateway.build_tokenomics_response",
            return_value=expected,
        ) as build:
            response = gateway.dispatch({
                "service": "tokenomics",
                "chain": "x1",
                "asset": "XNT",
                "params": {
                    "mint": "MintWrapped",
                    "symbol": "WXNT",
                    "name": "Wrapped XNT",
                },
            })

        self.assertEqual(response, expected)
        build.assert_called_once_with(
            "MintWrapped",
            symbol="WXNT",
            name="Wrapped XNT",
            chain="x1",
        )
        self.assertEqual(supply.total_calls, 0)
        self.assertEqual(supply.circulating_calls, 0)


if __name__ == "__main__":
    unittest.main()
