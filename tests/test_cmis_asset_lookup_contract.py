import unittest

from liquidity_scout.services import (
    AMBIGUOUS,
    ERROR,
    OK,
    UNAVAILABLE,
    build_asset_lookup_response,
)


def token(symbol, mint=None, name=None):
    row = {
        "symbol": symbol,
        "name": name or symbol,
    }
    if mint is not None:
        row["mint"] = mint
        row["address"] = mint
    return row


def pool(address, base, quote, *, liquidity=1000.0, volume24h=100.0):
    return {
        "address": address,
        "baseToken": base,
        "quoteToken": quote,
        "liquidity": liquidity,
        "volume24h": volume24h,
    }


class CMISAssetLookupContractTests(unittest.TestCase):
    def setUp(self):
        self.ref = token("REF", "MintREF", "Reference Token")
        self.usdc = token("USDC", "MintUSDC", "USD Coin")
        self.xnt = token("XNT", "MintXNT", "Wrapped XNT")
        self.pools = [
            pool("P1", self.ref, self.usdc, liquidity=5000.0, volume24h=100.0),
            pool("P2", self.ref, self.xnt, liquidity=1000.0, volume24h=500.0),
        ]

    def test_unique_symbol_resolves_verified_mint_and_multi_lp_identity(self):
        response = build_asset_lookup_response(
            "REF",
            self.pools,
            source="X1.Ninja/XDEX",
            observed_at=2000.0,
        )

        self.assertEqual(response["service"], "asset_lookup")
        self.assertEqual(response["chain"], "x1")
        self.assertEqual(response["status"], OK)
        self.assertEqual(
            response["asset"],
            {
                "symbol": "REF",
                "name": "Reference Token",
                "mint": "MintREF",
            },
        )
        self.assertEqual(response["data"]["resolved_term"], "REF")
        self.assertEqual(response["data"]["resolved_by"], "symbol")
        self.assertEqual(response["data"]["match_quality"], 90)
        self.assertEqual(response["data"]["lp_count"], 2)
        self.assertEqual(response["data"]["identity_key"], "MintREF")
        self.assertTrue(response["confidence"]["complete"])
        self.assertEqual(response["confidence"]["verified_checks"], 1)
        self.assertEqual(
            response["sources"],
            [{
                "source": "X1.Ninja/XDEX",
                "role": "asset_lookup",
                "observed_at": 2000.0,
            }],
        )
        self.assertEqual(response["observed_at"], 2000.0)
        self.assertEqual(response["warnings"], [])
        self.assertEqual(response["errors"], [])

    def test_unique_mint_query_resolves_by_mint(self):
        response = build_asset_lookup_response("MintREF", self.pools)

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["asset"]["mint"], "MintREF")
        self.assertEqual(response["data"]["resolved_by"], "mint")
        self.assertEqual(response["data"]["lp_count"], 2)

    def test_duplicate_symbol_across_mints_is_ambiguous_not_best_liquidity_guess(self):
        other = token("REF", "MintOtherREF", "Other Reference Token")
        pools = self.pools + [
            pool("P3", other, self.usdc, liquidity=999999.0, volume24h=999999.0)
        ]

        response = build_asset_lookup_response("REF", pools)

        self.assertEqual(response["status"], AMBIGUOUS)
        self.assertEqual(response["asset"], {})
        self.assertEqual(
            response["data"]["candidate_asset_keys"],
            ["MintOtherREF", "MintREF"],
        )
        candidates = {item["mint"] for item in response["data"]["candidate_assets"]}
        self.assertEqual(candidates, {"MintREF", "MintOtherREF"})
        self.assertFalse(response["confidence"]["complete"])
        self.assertEqual(response["warnings"][0]["code"], "asset_ambiguous")
        self.assertEqual(response["errors"], [])

    def test_pool_address_is_ambiguous_between_pool_assets(self):
        response = build_asset_lookup_response("P1", self.pools)

        self.assertEqual(response["status"], AMBIGUOUS)
        self.assertEqual(
            set(response["data"]["candidate_asset_keys"]),
            {"MintREF", "MintUSDC"},
        )
        self.assertEqual(response["warnings"][0]["code"], "asset_ambiguous")

    def test_unknown_asset_is_unavailable_not_partial_match_guess(self):
        response = build_asset_lookup_response("DOES_NOT_EXIST", self.pools)

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertEqual(response["asset"], {})
        self.assertEqual(response["data"], {"query": "DOES_NOT_EXIST"})
        self.assertEqual(response["warnings"][0]["code"], "asset_not_resolved")
        self.assertFalse(response["confidence"]["checks"]["unique_mint_resolved"])

    def test_exact_symbol_without_mint_is_unavailable_but_observed_fields_are_preserved(self):
        no_mint = token("NOMINT", None, "No Mint Token")
        response = build_asset_lookup_response(
            "NOMINT",
            [pool("PN", no_mint, self.usdc)],
        )

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertEqual(
            response["asset"],
            {"symbol": "NOMINT", "name": "No Mint Token", "mint": None},
        )
        self.assertEqual(response["data"]["identity_key"], "symbol:NOMINT")
        self.assertEqual(response["warnings"][0]["code"], "asset_mint_unavailable")

    def test_missing_catalog_is_unavailable(self):
        response = build_asset_lookup_response("REF", None)

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertEqual(response["warnings"][0]["code"], "asset_catalog_unavailable")
        self.assertEqual(response["errors"], [])

    def test_empty_catalog_returns_unavailable_asset_not_resolved(self):
        response = build_asset_lookup_response("REF", [])

        self.assertEqual(response["status"], UNAVAILABLE)
        self.assertEqual(response["warnings"][0]["code"], "asset_not_resolved")

    def test_invalid_catalog_container_is_error(self):
        response = build_asset_lookup_response("REF", "not a pool collection")

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "invalid_asset_catalog")

    def test_malformed_pool_row_fails_closed_as_error(self):
        response = build_asset_lookup_response("REF", ["not a pool row"])

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "asset_lookup_validation_error")

    def test_missing_query_is_error_without_catalog_resolution(self):
        response = build_asset_lookup_response("   ", self.pools)

        self.assertEqual(response["status"], ERROR)
        self.assertEqual(response["errors"][0]["code"], "asset_query_required")

    def test_chain_is_explicit_for_future_provider_reuse(self):
        response = build_asset_lookup_response("REF", self.pools, chain="Solana")

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["chain"], "solana")
        self.assertEqual(response["asset"]["mint"], "MintREF")

    def test_generator_catalog_is_materialized_deterministically(self):
        response = build_asset_lookup_response("REF", (row for row in self.pools))

        self.assertEqual(response["status"], OK)
        self.assertEqual(response["asset"]["mint"], "MintREF")
        self.assertEqual(response["data"]["lp_count"], 2)


if __name__ == "__main__":
    unittest.main()
