import unittest

from liquidity_scout.cmis.assets import (
    AssetRegistry,
    DEFAULT_ASSET_REGISTRY,
    MARKET,
    MARKET_PLUS_NATIVE,
    NATIVE,
)


class CMISAssetRegistryTests(unittest.TestCase):
    def test_xnt_resolves_case_insensitively_to_canonical_native_asset(self):
        definition = DEFAULT_ASSET_REGISTRY.resolve("X1", "xnt")

        self.assertIsNotNone(definition)
        self.assertEqual(definition["canonical_id"], "x1:native:XNT")
        self.assertEqual(
            DEFAULT_ASSET_REGISTRY.public_identity(definition),
            {
                "canonical_id": "x1:native:XNT",
                "symbol": "XNT",
                "name": "XNT",
                "mint": None,
                "asset_type": "native",
            },
        )
        self.assertEqual(DEFAULT_ASSET_REGISTRY.market_query(definition), "XNT")
        self.assertEqual(DEFAULT_ASSET_REGISTRY.service_mode(definition, "market_report"), MARKET)
        self.assertEqual(DEFAULT_ASSET_REGISTRY.service_mode(definition, "tokenomics"), NATIVE)
        self.assertEqual(
            DEFAULT_ASSET_REGISTRY.service_mode(definition, "risk_check"),
            MARKET_PLUS_NATIVE,
        )

    def test_unknown_wrapped_name_is_not_canonicalized_by_heuristic(self):
        self.assertIsNone(DEFAULT_ASSET_REGISTRY.resolve("x1", "Wrapped FOO"))
        self.assertIsNone(DEFAULT_ASSET_REGISTRY.resolve("x1", "FOO"))
        self.assertIsNone(
            DEFAULT_ASSET_REGISTRY.match_representation(
                "x1",
                {"symbol": "FOO", "name": "Wrapped FOO", "mint": "MINT_FOO"},
            )
        )

    def test_provider_representation_can_be_configured_without_becoming_user_alias(self):
        registry = AssetRegistry([
            {
                "canonical_id": "solana:native:SOL",
                "chain": "solana",
                "symbol": "SOL",
                "name": "SOL",
                "asset_type": "native",
                "aliases": ["SOL"],
                "representations": {
                    "market": {
                        "kind": "wrapped_token",
                        "provider": "example_dex",
                        "query": "WSOL",
                        "symbols": ["WSOL"],
                        "names": ["Wrapped SOL"],
                    }
                },
            }
        ])

        # An explicit WSOL user query remains representation-scoped unless a
        # caller deliberately adds WSOL to canonical aliases.
        self.assertIsNone(registry.resolve("solana", "WSOL"))

        definition = registry.match_representation(
            "solana",
            {"symbol": "WSOL", "name": "Wrapped SOL", "mint": "MINT_WSOL"},
        )
        self.assertIsNotNone(definition)
        self.assertEqual(definition["canonical_id"], "solana:native:SOL")
        self.assertEqual(registry.market_query(definition), "WSOL")

    def test_canonicalization_preserves_provider_representation_separately(self):
        definition = DEFAULT_ASSET_REGISTRY.resolve("x1", "XNT")
        envelope = {
            "service": "asset_lookup",
            "chain": "x1",
            "status": "ok",
            "asset": {
                "symbol": "XNT",
                "name": "Wrapped XNT",
                "mint": "MINT_XNT",
            },
            "data": {"identity_key": "MINT_XNT"},
            "risk": None,
            "confidence": {},
            "sources": [],
            "observed_at": 123,
            "warnings": [],
            "errors": [],
        }

        result = DEFAULT_ASSET_REGISTRY.canonicalize_envelope(
            envelope,
            definition,
            identity_key="MINT_XNT",
        )

        self.assertEqual(result["asset"]["name"], "XNT")
        self.assertIsNone(result["asset"]["mint"])
        self.assertEqual(result["data"]["canonical_asset"]["canonical_id"], "x1:native:XNT")
        representation = result["data"]["representations"][0]
        self.assertEqual(representation["role"], "market")
        self.assertEqual(representation["kind"], "wrapped_token")
        self.assertEqual(representation["name"], "Wrapped XNT")
        self.assertEqual(representation["mint"], "MINT_XNT")

        # The input envelope is not mutated.
        self.assertEqual(envelope["asset"]["name"], "Wrapped XNT")
        self.assertNotIn("canonical_asset", envelope["data"])

    def test_registry_rejects_alias_collisions_in_same_chain(self):
        with self.assertRaises(ValueError):
            AssetRegistry([
                {
                    "canonical_id": "x1:native:A",
                    "chain": "x1",
                    "symbol": "A",
                    "aliases": ["SHARED"],
                },
                {
                    "canonical_id": "x1:native:B",
                    "chain": "x1",
                    "symbol": "B",
                    "aliases": ["SHARED"],
                },
            ])


if __name__ == "__main__":
    unittest.main()
