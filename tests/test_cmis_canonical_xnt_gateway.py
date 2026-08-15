import unittest

from liquidity_scout.cmis.gateway import CMISGateway


def token(symbol, mint, name=None):
    return {
        "symbol": symbol,
        "name": name or symbol,
        "mint": mint,
        "address": mint,
    }


def pool(address, base, quote):
    return {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "createdAt": "2026-01-01T00:00:00Z",
        "liquidity": 100000,
        "volume24h": 10000,
        "txns24h": 250,
        "holders": 1000,
        "priceUsd": 0.5,
    }


class FakeX1MarketProvider:
    chain = "x1"

    def __init__(self):
        self.xnt = token("XNT", "MINT_XNT", "Wrapped XNT")
        self.usdc = token("USDC", "MINT_USDC", "USD Coin")
        self.pools = [pool("P_XNT", self.xnt, self.usdc)]
        self.xnt_price_usd = 0.5
        self.last_refresh = 123.0
        self.refresh_calls = 0

    def refresh_if_needed(self):
        self.refresh_calls += 1
        return self

    def market_catalog(self):
        return {
            "chain": "x1",
            "source": "X1.Ninja/XDEX",
            "pools": list(self.pools),
            "xnt_price_usd": self.xnt_price_usd,
            "observed_at": self.last_refresh,
        }


class FakeSupplyProvider:
    def get_total_supply(self):
        return {
            "chain": "x1",
            "asset": "XNT",
            "network": "mainnet",
            "metric": "total_supply",
            "supply": "1067069623",
            "supply_verified": True,
            "source": "api.x1.xyz /v1/supply/total",
        }

    def get_circulating_supply(self):
        return {
            "chain": "x1",
            "asset": "XNT",
            "network": "mainnet",
            "metric": "circulating_supply",
            "supply": "13810247",
            "supply_verified": True,
            "source": "api.x1.xyz /v1/supply/circulating",
        }


class CMISCanonicalXNTGatewayTests(unittest.TestCase):
    def setUp(self):
        self.market = FakeX1MarketProvider()
        self.gateway = CMISGateway(
            x1_market_provider=self.market,
            x1_supply_provider=FakeSupplyProvider(),
        )

    def test_asset_lookup_exposes_canonical_xnt_and_traces_wrapped_market_representation(self):
        response = self.gateway.dispatch({
            "service": "asset_lookup",
            "chain": "x1",
            "asset": "XNT",
            "params": {},
        })

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["asset"]["canonical_id"], "x1:native:XNT")
        self.assertEqual(response["asset"]["name"], "XNT")
        self.assertEqual(response["asset"]["asset_type"], "native")
        self.assertIsNone(response["asset"]["mint"])

        representation = response["data"]["representations"][0]
        self.assertEqual(representation["role"], "market")
        self.assertEqual(representation["name"], "Wrapped XNT")
        self.assertEqual(representation["mint"], "MINT_XNT")

    def test_market_report_keeps_market_mint_in_data_but_not_as_canonical_identity(self):
        response = self.gateway.dispatch({
            "service": "market_report",
            "chain": "x1",
            "asset": "xnt",
            "params": {},
        })

        self.assertIn(response["status"], {"ok", "partial"})
        self.assertEqual(response["asset"]["name"], "XNT")
        self.assertIsNone(response["asset"]["mint"])
        self.assertEqual(response["data"]["mint"], "MINT_XNT")
        self.assertEqual(
            response["data"]["representations"][0]["mint"],
            "MINT_XNT",
        )

    def test_risk_uses_native_tokenomics_while_retaining_market_representation_identity(self):
        response = self.gateway.dispatch({
            "service": "risk_check",
            "chain": "x1",
            "asset": "XNT",
            "params": {},
        })

        self.assertEqual(response["asset"]["name"], "XNT")
        self.assertIsNone(response["asset"]["mint"])
        self.assertEqual(response["risk"]["asset"]["mint"], "MINT_XNT")
        self.assertNotIn("mint_authority_unverified", response["risk"]["flags"])
        self.assertNotIn("freeze_authority_unverified", response["risk"]["flags"])
        sources = {item.get("source") for item in response["sources"]}
        self.assertIn("api.x1.xyz /v1/supply/total", sources)
        self.assertIn("api.x1.xyz /v1/supply/circulating", sources)

    def test_pre_trade_uses_market_mint_for_internal_identity_gate_then_returns_canonical_asset(self):
        response = self.gateway.dispatch({
            "service": "pre_trade_check",
            "chain": "x1",
            "asset": "XNT",
            "params": {
                "trade": {
                    "side": "buy",
                    "chain": "x1",
                    "notional_usd": 1000,
                }
            },
        })

        self.assertEqual(response["asset"]["name"], "XNT")
        self.assertIsNone(response["asset"]["mint"])
        identity = response["risk"]["components"]["identity"]
        self.assertEqual(identity["status"], "PASS")
        self.assertEqual(identity["evidence"]["trade_mint"], "MINT_XNT")
        self.assertEqual(identity["evidence"]["risk_mint"], "MINT_XNT")
        self.assertTrue(identity["evidence"]["mint_match"])
        self.assertNotIn("trade_asset_mint_unverified", response["risk"]["flags"])
        self.assertNotIn("risk_asset_mint_unverified", response["risk"]["flags"])
        self.assertFalse(response["risk"]["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
