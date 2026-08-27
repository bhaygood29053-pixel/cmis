import unittest

from liquidity_scout.services.cmis_x1_asset_identity import (
    IDENTITY_CONTRACT,
    build_exact_mint_identity_response,
    exact_xdex_descriptors,
    is_exact_x1_public_key,
)


XENCAT_MINT = "DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
OTHER_MINT = "11111111111111111111111111111111"


def metadata_evidence(*, mint=XENCAT_MINT, symbol="XENCAT", name="XENCAT"):
    return {
        "identity_verified": True,
        "program": {
            "program_executable_verified": True,
            "context_slot": 100,
        },
        "metadata": {
            "identity_verified": True,
            "mint": mint,
            "symbol": symbol,
            "name": name,
            "uri": "https://example.invalid/token.json",
            "metadata_account": "Metadata111",
            "metadata_update_authority": "Update111",
            "is_mutable": True,
            "token_standard": "Fungible",
            "context_slot": 101,
            "program_id": "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s",
        },
    }


class CMISX1AssetIdentityTests(unittest.TestCase):
    def test_exact_public_key_requires_32_decoded_bytes(self):
        self.assertTrue(is_exact_x1_public_key(XENCAT_MINT))
        self.assertTrue(is_exact_x1_public_key(OTHER_MINT))
        self.assertFalse(is_exact_x1_public_key("AGI"))
        self.assertFalse(is_exact_x1_public_key("not-a-base58-key"))

    def test_metaplex_only_is_complete_mint_rooted_identity(self):
        response = build_exact_mint_identity_response(
            XENCAT_MINT,
            metadata_evidence=metadata_evidence(),
            xdex_pools=[],
        )

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"]["identity_contract"], IDENTITY_CONTRACT)
        self.assertEqual(
            response["data"]["identity_reconciliation"]["state"],
            "metaplex_only",
        )
        normalized = response["data"]["normalized_identity"]
        self.assertEqual(normalized["mint"], XENCAT_MINT)
        self.assertEqual(normalized["identity_root"], "mint")
        self.assertTrue(normalized["normalized_onchain_identity_verified"])

    def test_xdex_different_mint_never_reconciles_by_same_symbol(self):
        pools = [{
            "baseToken": {
                "mint": OTHER_MINT,
                "symbol": "XENCAT",
                "name": "XENCAT",
            },
            "quoteToken": {
                "mint": "AnotherMint",
                "symbol": "USDC",
                "name": "USD Coin",
            },
        }]

        variants = exact_xdex_descriptors(XENCAT_MINT, pools)
        self.assertEqual(variants, [])

        response = build_exact_mint_identity_response(
            XENCAT_MINT,
            metadata_evidence=metadata_evidence(),
            xdex_pools=pools,
        )
        self.assertEqual(
            response["data"]["identity_reconciliation"]["state"],
            "metaplex_only",
        )

    def test_same_mint_descriptor_conflict_preserves_metaplex_labels(self):
        pools = [{
            "baseToken": {
                "mint": XENCAT_MINT,
                "symbol": "CATX",
                "name": "Different Name",
            },
            "quoteToken": {
                "mint": OTHER_MINT,
                "symbol": "OTHER",
                "name": "Other",
            },
        }]
        response = build_exact_mint_identity_response(
            XENCAT_MINT,
            metadata_evidence=metadata_evidence(),
            xdex_pools=pools,
            xdex_source="X1.Ninja/XDEX",
            xdex_observed_at=123.0,
        )

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["asset"]["mint"], XENCAT_MINT)
        self.assertEqual(response["asset"]["symbol"], "XENCAT")
        reconciliation = response["data"]["identity_reconciliation"]
        self.assertEqual(reconciliation["state"], "descriptor_conflict")
        self.assertEqual(
            set(reconciliation["conflicting_fields"]),
            {"symbol", "name"},
        )

    def test_xdex_unavailable_is_partial_not_metaplex_only(self):
        response = build_exact_mint_identity_response(
            XENCAT_MINT,
            metadata_evidence=metadata_evidence(),
            xdex_pools=[],
            xdex_available=False,
        )
        self.assertEqual(response["status"], "partial")
        reconciliation = response["data"]["identity_reconciliation"]
        self.assertEqual(reconciliation["state"], "xdex_unavailable")
        self.assertFalse(reconciliation["xdex"]["available"])

    def test_decoded_metaplex_mint_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "does not equal requested"):
            build_exact_mint_identity_response(
                XENCAT_MINT,
                metadata_evidence=metadata_evidence(mint=OTHER_MINT),
                xdex_pools=[],
            )


if __name__ == "__main__":
    unittest.main()
