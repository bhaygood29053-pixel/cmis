import unittest

from liquidity_scout.services.cmis_risk import build_risk_check_response


class CMISNativeRiskWarningWordingTests(unittest.TestCase):
    def test_native_asset_uses_native_network_activity_warning(self):
        market = {
            "symbol": "XNT",
            "mint": "WrappedMarketRepresentation",
            "liquidity_usd": 100000.0,
            "volume_24h_usd": 10000.0,
            "transactions_24h": 100,
            "completeness": {
                "liquidity": True,
                "volume_24h": True,
                "transactions_24h": True,
            },
        }
        tokenomics = {
            "asset_type": "native",
            "supply_verified": True,
            "mint_authority_verified": True,
            "mint_authority_state": "not_applicable",
            "freeze_authority_verified": True,
            "freeze_authority_state": "not_applicable",
            "rpc_decimals_consistent": None,
            "token_activity": {
                "available": False,
                "activity_verified": False,
            },
        }

        response = build_risk_check_response(market, tokenomics)

        warning = next(
            item
            for item in response["warnings"]
            if item["code"] == "token_activity_unavailable"
        )
        self.assertEqual(
            warning["message"],
            "Verified native-network issuance/burn activity was not supplied.",
        )
        self.assertNotIn("bounded mint/burn", warning["message"].lower())


if __name__ == "__main__":
    unittest.main()
