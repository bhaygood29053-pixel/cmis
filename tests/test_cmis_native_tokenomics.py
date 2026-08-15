import unittest

from liquidity_scout.services import build_native_tokenomics_response


def supply(metric, value, source):
    return {
        "chain": "x1",
        "asset": "XNT",
        "network": "mainnet",
        "metric": metric,
        "supply": value,
        "supply_verified": True,
        "representation": "provider_integer_text",
        "source": source,
    }


class CMISNativeTokenomicsTests(unittest.TestCase):
    def test_verified_native_supply_keeps_xnt_identity_and_no_mint_semantics(self):
        response = build_native_tokenomics_response(
            symbol="XNT",
            name="XNT",
            chain="x1",
            total_supply_record=supply(
                "total_supply",
                "1067069623",
                "api.x1.xyz /v1/supply/total",
            ),
            circulating_supply_record=supply(
                "circulating_supply",
                "13810247",
                "api.x1.xyz /v1/supply/circulating",
            ),
        )

        self.assertEqual(response["service"], "tokenomics")
        self.assertEqual(response["chain"], "x1")
        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["asset"]["symbol"], "XNT")
        self.assertEqual(response["asset"]["name"], "XNT")
        self.assertIsNone(response["asset"]["mint"])
        self.assertEqual(response["asset"]["asset_type"], "native")
        self.assertEqual(response["data"]["scope"], "native_network")
        self.assertEqual(response["data"]["current_total_supply"], "1067069623")
        self.assertTrue(response["data"]["supply_verified"])
        self.assertEqual(response["data"]["circulating_supply"], "13810247")
        self.assertTrue(response["data"]["circulating_supply_verified"])
        self.assertIsNone(response["data"]["maximum_supply"])
        self.assertFalse(response["data"]["maximum_supply_verified"])
        self.assertEqual(response["data"]["mint_authority_state"], "not_applicable")
        self.assertEqual(response["data"]["freeze_authority_state"], "not_applicable")
        self.assertEqual(response["confidence"]["verified_checks"], 2)
        self.assertEqual(response["confidence"]["total_checks"], 3)
        self.assertIn(
            {
                "source": "api.x1.xyz /v1/supply/total",
                "role": "tokenomics.network_total_supply",
            },
            response["sources"],
        )
        self.assertIn(
            {
                "source": "api.x1.xyz /v1/supply/circulating",
                "role": "tokenomics.network_circulating_supply",
            },
            response["sources"],
        )

    def test_missing_native_supply_is_unavailable_not_zero(self):
        response = build_native_tokenomics_response(
            symbol="XNT",
            name="XNT",
            chain="x1",
        )

        self.assertEqual(response["status"], "unavailable")
        self.assertIsNone(response["data"]["current_total_supply"])
        self.assertIsNone(response["data"]["circulating_supply"])
        self.assertFalse(response["data"]["supply_verified"])
        self.assertFalse(response["data"]["circulating_supply_verified"])
        codes = {warning["code"] for warning in response["warnings"]}
        self.assertIn("native_total_supply_unverified", codes)
        self.assertIn("native_circulating_supply_unverified", codes)


if __name__ == "__main__":
    unittest.main()
