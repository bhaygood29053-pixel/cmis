import unittest
from types import SimpleNamespace

from liquidity_scout.integrations.moltgrid_asset_cmis import format_cmis_asset_answer


class FakeGateway:
    def __init__(self):
        self.requests = []

    def dispatch(self, request):
        self.requests.append(request)
        return {
            "service": "tokenomics",
            "chain": "x1",
            "status": "partial",
            "asset": {
                "symbol": "XNT",
                "name": "XNT",
                "mint": None,
                "asset_type": "native",
            },
            "data": {
                "scope": "native_network",
                "asset_type": "native",
                "symbol": "XNT",
                "name": "XNT",
                "mint": None,
                "current_total_supply": "1067069623",
                "supply_verified": True,
                "circulating_supply": "13810247",
                "circulating_supply_verified": True,
                "maximum_supply": None,
                "maximum_supply_verified": False,
                "token_activity": {
                    "available": False,
                    "activity_verified": False,
                },
            },
            "risk": None,
            "confidence": {
                "complete": False,
                "verified_checks": 2,
                "total_checks": 3,
            },
            "sources": [
                {
                    "source": "api.x1.xyz /v1/supply/total",
                    "role": "tokenomics.network_total_supply",
                },
                {
                    "source": "api.x1.xyz /v1/supply/circulating",
                    "role": "tokenomics.network_circulating_supply",
                },
            ],
            "observed_at": None,
            "warnings": [
                {
                    "code": "maximum_supply_unverified",
                    "message": "Maximum supply is not independently verified by this service.",
                },
                {
                    "code": "native_issuance_activity_unavailable",
                    "message": "Verified native-network issuance/burn activity was not supplied to this tokenomics request.",
                },
            ],
            "errors": [],
        }


class MoltGridNativeXNTTokenomicsTests(unittest.TestCase):
    def test_xnt_is_presented_as_native_xnt_not_wrapped_xnt(self):
        gateway = FakeGateway()

        answer = format_cmis_asset_answer(
            SimpleNamespace(),
            "What are XNT tokenomics?",
            "XNT",
            gateway=gateway,
        )

        self.assertEqual(gateway.requests, [{
            "service": "tokenomics",
            "chain": "x1",
            "asset": "XNT",
            "params": {},
        }])
        self.assertIn("CMIS tokenomics — XNT", answer)
        self.assertIn("Name: XNT", answer)
        self.assertIn("Asset type: Native X1 asset", answer)
        self.assertIn("Network total supply: 1,067,069,623 XNT", answer)
        self.assertIn("Circulating supply: 13,810,247 XNT", answer)
        self.assertIn("Confidence checks: 2/3 verified", answer)
        self.assertIn("api.x1.xyz /v1/supply/total", answer)
        self.assertIn("api.x1.xyz /v1/supply/circulating", answer)
        self.assertNotIn("Wrapped XNT", answer)
        self.assertNotIn("Mint:", answer)
        self.assertNotIn("Decimals:", answer)
        self.assertNotIn("Mint authority:", answer)
        self.assertNotIn("Freeze authority:", answer)
        self.assertNotIn("Current total supply: 0 XNT", answer)


if __name__ == "__main__":
    unittest.main()
