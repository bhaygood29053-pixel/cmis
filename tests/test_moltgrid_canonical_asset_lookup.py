import unittest
from types import SimpleNamespace

from liquidity_scout.integrations.moltgrid_asset_cmis import format_cmis_asset_answer


class FakeGateway:
    def __init__(self):
        self.requests = []

    def dispatch(self, request):
        self.requests.append(request)
        return {
            "service": "asset_lookup",
            "chain": "x1",
            "status": "ok",
            "asset": {
                "canonical_id": "x1:native:XNT",
                "symbol": "XNT",
                "name": "XNT",
                "mint": None,
                "asset_type": "native",
            },
            "data": {
                "resolved_by": "symbol",
                "lp_count": 3,
                "representations": [
                    {
                        "role": "market",
                        "kind": "wrapped_token",
                        "provider": "X1.Ninja/XDEX",
                        "chain": "x1",
                        "symbol": "XNT",
                        "name": "Wrapped XNT",
                        "mint": "MINT_XNT",
                    }
                ],
            },
            "risk": None,
            "confidence": {
                "complete": True,
                "verified_checks": 1,
                "total_checks": 1,
            },
            "sources": [{"source": "X1.Ninja/XDEX", "role": "asset_lookup"}],
            "observed_at": 123,
            "warnings": [],
            "errors": [],
        }


class MoltGridCanonicalAssetLookupTests(unittest.TestCase):
    def test_native_identity_and_market_representation_are_not_conflated(self):
        gateway = FakeGateway()
        answer = format_cmis_asset_answer(
            SimpleNamespace(),
            "What is XNT?",
            "XNT",
            gateway=gateway,
        )

        self.assertIn("CMIS asset lookup — XNT", answer)
        self.assertIn("Name: XNT", answer)
        self.assertIn("Asset type: Native chain asset", answer)
        self.assertIn("X1.Ninja/XDEX representation: Wrapped XNT", answer)
        self.assertIn("X1.Ninja/XDEX representation mint: MINT_XNT", answer)
        self.assertNotIn("Name: Wrapped XNT", answer)
        self.assertNotIn("\nMint: MINT_XNT", answer)


if __name__ == "__main__":
    unittest.main()
