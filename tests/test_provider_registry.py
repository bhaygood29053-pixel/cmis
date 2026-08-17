import unittest

from liquidity_scout.providers.registry import (
    ChainProviderRegistry,
    build_default_chain_provider_registry,
)


class _Provider:
    def __init__(self, chain: str):
        self.chain = chain


class ChainProviderRegistryTests(unittest.TestCase):
    def test_default_registry_preserves_injected_x1_provider_objects(self):
        market = _Provider("x1")
        supply = _Provider("x1")
        registry = build_default_chain_provider_registry(
            x1_market_provider=market,
            x1_supply_provider=supply,
        )

        market_result = registry.resolve(chain="x1", component="market")
        supply_result = registry.resolve(chain="x1", component="supply")

        self.assertEqual(market_result.status, "selected")
        self.assertIs(market_result.provider, market)
        self.assertEqual(supply_result.status, "selected")
        self.assertIs(supply_result.provider, supply)

    def test_solana_is_known_but_unconfigured_by_default(self):
        registry = build_default_chain_provider_registry(
            x1_market_provider=_Provider("x1"),
            x1_supply_provider=_Provider("x1"),
        )

        result = registry.resolve(chain="solana", component="market")

        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.chain, "solana")
        self.assertIsNone(result.provider)
        self.assertIn("not configured", result.reason.lower())

    def test_solana_never_falls_back_to_x1(self):
        x1_market = _Provider("x1")
        registry = build_default_chain_provider_registry(
            x1_market_provider=x1_market,
            x1_supply_provider=_Provider("x1"),
        )

        solana_result = registry.resolve(chain="solana", component="market")

        self.assertEqual(solana_result.status, "unavailable")
        self.assertIsNone(solana_result.provider)
        self.assertIsNot(solana_result.provider, x1_market)

    def test_unknown_chain_is_distinct_from_known_unconfigured_chain(self):
        registry = build_default_chain_provider_registry(
            x1_market_provider=_Provider("x1"),
            x1_supply_provider=_Provider("x1"),
        )

        result = registry.resolve(chain="base", component="market")

        self.assertEqual(result.status, "unknown_chain")
        self.assertEqual(result.chain, "base")
        self.assertIsNone(result.provider)

    def test_verified_future_solana_component_can_be_injected_explicitly(self):
        registry = ChainProviderRegistry()
        solana_market = _Provider("solana")
        registry.mark_chain_unavailable(
            "solana",
            reason="Solana provider is not configured by default.",
        )
        registry.register(
            chain="solana",
            component="market",
            provider=solana_market,
        )

        result = registry.resolve(chain="solana", component="market")

        self.assertEqual(result.status, "selected")
        self.assertIs(result.provider, solana_market)

    def test_provider_chain_mismatch_fails_closed(self):
        registry = ChainProviderRegistry()

        with self.assertRaisesRegex(ValueError, "provider chain mismatch"):
            registry.register(
                chain="solana",
                component="market",
                provider=_Provider("x1"),
            )

    def test_duplicate_component_registration_is_rejected(self):
        registry = ChainProviderRegistry()
        registry.register(
            chain="x1",
            component="market",
            provider=_Provider("x1"),
        )

        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(
                chain="x1",
                component="market",
                provider=_Provider("x1"),
            )

    def test_unknown_component_is_rejected(self):
        registry = ChainProviderRegistry()

        with self.assertRaisesRegex(ValueError, "unsupported provider component"):
            registry.resolve(chain="x1", component="execution")


if __name__ == "__main__":
    unittest.main()
