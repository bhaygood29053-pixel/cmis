import unittest

from liquidity_scout.cmis.capabilities import (
    CMIS_CONTRACT_VERSION,
    build_capability_manifest,
    service_capability,
    validate_capability_contract,
)
from liquidity_scout.cmis.gateway import KNOWN_CHAINS, SUPPORTED_CHAINS
from liquidity_scout.cmis.runtime_gateway import SUPPORTED_SERVICES


class CMISCapabilityContractTests(unittest.TestCase):
    def test_runtime_surface_matches_capability_manifest(self):
        validate_capability_contract(
            runtime_services=SUPPORTED_SERVICES,
            known_chains=KNOWN_CHAINS,
        )

        manifest = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )

        self.assertEqual(manifest["contract_version"], CMIS_CONTRACT_VERSION)
        self.assertEqual(set(manifest["chains"]), {"x1", "solana"})
        self.assertEqual(
            set(manifest["chains"]["x1"]["services"]),
            set(SUPPORTED_SERVICES),
        )
        self.assertEqual(
            set(manifest["chains"]["solana"]["services"]),
            set(SUPPORTED_SERVICES),
        )

    def test_new_runtime_service_without_manifest_classification_fails_loudly(self):
        with self.assertRaisesRegex(RuntimeError, "service drift"):
            validate_capability_contract(
                runtime_services=(*SUPPORTED_SERVICES, "future_service"),
                known_chains=KNOWN_CHAINS,
            )

    def test_new_known_chain_without_manifest_classification_fails_loudly(self):
        with self.assertRaisesRegex(RuntimeError, "chain drift"):
            validate_capability_contract(
                runtime_services=SUPPORTED_SERVICES,
                known_chains=(*KNOWN_CHAINS, "ethereum"),
            )

    def test_chain_service_lookup_never_guesses_unknown_capability(self):
        manifest = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )

        x1_pretrade = service_capability(
            manifest,
            chain="x1",
            service="pre_trade_check",
        )
        solana_pretrade = service_capability(
            manifest,
            chain="solana",
            service="pre_trade_check",
        )
        unknown = service_capability(
            manifest,
            chain="ethereum",
            service="market_report",
        )

        self.assertEqual(x1_pretrade["state"], "bounded")
        self.assertTrue(x1_pretrade["callable"])
        self.assertEqual(solana_pretrade["state"], "unavailable")
        self.assertFalse(solana_pretrade["callable"])
        self.assertIsNone(unknown)

    def test_manifest_build_returns_fresh_nested_data(self):
        first = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        first["chains"]["x1"]["services"]["risk_check"]["state"] = "unavailable"

        second = build_capability_manifest(
            runtime_services=SUPPORTED_SERVICES,
            legacy_supported_chains=SUPPORTED_CHAINS,
            known_chains=KNOWN_CHAINS,
        )
        self.assertEqual(
            second["chains"]["x1"]["services"]["risk_check"]["state"],
            "supported",
        )


if __name__ == "__main__":
    unittest.main()
