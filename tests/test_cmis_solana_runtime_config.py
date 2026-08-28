import os
import tempfile
import unittest

from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.cmis.solana_observation_ledger import SolanaObservationLedger
from liquidity_scout.cmis.solana_runtime_config import (
    build_solana_runtime_dependencies,
)
from liquidity_scout.providers.solana.dexscreener import DexScreenerSolanaProvider
from liquidity_scout.providers.solana.helius import HeliusDASProvider
from liquidity_scout.providers.solana.jupiter import JupiterSourceProvider
from liquidity_scout.providers.solana.pyth_push import PythSolanaPushProvider
from liquidity_scout.providers.solana.rpc import SolanaRPCProvider


class SolanaRuntimeConfigTests(unittest.TestCase):
    def test_disabled_by_default_constructs_no_solana_dependencies(self):
        dependencies, status = build_solana_runtime_dependencies({})
        self.assertEqual(dependencies, {})
        self.assertFalse(status["enabled"])
        self.assertTrue(status["read_only"])
        self.assertFalse(status["execution_authorized"])

    def test_enabled_minimal_runtime_constructs_rpc_pyth_dex_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = os.path.join(directory, "solana.db")
            dependencies, status = build_solana_runtime_dependencies({
                "CMIS_SOLANA_PROVIDER_ENABLED": "1",
                "SOLANA_RPC_URL": "https://rpc.example.invalid",
                "CMIS_SOLANA_OBSERVATION_DB": db_path,
            })

        self.assertIsInstance(
            dependencies["solana_rpc_provider"], SolanaRPCProvider
        )
        self.assertIsInstance(
            dependencies["solana_pyth_provider"],
            PythSolanaPushProvider,
        )
        self.assertIsInstance(
            dependencies["solana_dexscreener_provider"],
            DexScreenerSolanaProvider,
        )
        self.assertIsInstance(
            dependencies["solana_observation_ledger"], SolanaObservationLedger
        )
        self.assertNotIn("solana_jupiter_provider", dependencies)
        self.assertNotIn("solana_helius_provider", dependencies)
        self.assertNotIn("solana_price_max_relative_difference", dependencies)
        self.assertTrue(status["enabled"])
        self.assertTrue(status["rpc_configured"])
        self.assertTrue(status["pyth_configured"])
        self.assertTrue(status["dexscreener_configured"])
        self.assertTrue(status["observation_ledger_configured"])
        self.assertFalse(status["jupiter_configured"])
        self.assertFalse(status["helius_configured"])
        self.assertFalse(status["price_crosscheck_policy_configured"])

    def test_blank_price_policy_does_not_create_a_hidden_default(self):
        with tempfile.TemporaryDirectory() as directory:
            dependencies, status = build_solana_runtime_dependencies({
                "CMIS_SOLANA_PROVIDER_ENABLED": "1",
                "CMIS_SOLANA_PRICE_MAX_RELATIVE_DIFFERENCE": "   ",
                "CMIS_SOLANA_OBSERVATION_DB": os.path.join(directory, "history.db"),
            })

        self.assertNotIn("solana_price_max_relative_difference", dependencies)
        self.assertFalse(status["price_crosscheck_policy_configured"])

    def test_optional_keyed_sources_and_policies_are_environment_owned(self):
        with tempfile.TemporaryDirectory() as directory:
            dependencies, status = build_solana_runtime_dependencies({
                "CMIS_SOLANA_PROVIDER_ENABLED": "true",
                "SOLANA_RPC_URL": "https://rpc.example.invalid/keyed-secret",
                "JUPITER_API_KEY": "jupiter-secret",
                "HELIUS_API_KEY": "helius-secret",
                "CMIS_SOLANA_PRICE_MAX_RELATIVE_DIFFERENCE": "0.03",
                "CMIS_SOLANA_SUPPLY_MAX_INDEX_SLOT_LAG": "150",
                "CMIS_SOLANA_HISTORY_MAX_DISTANCE_SECONDS": "900",
                "CMIS_SOLANA_OBSERVATION_DB": os.path.join(directory, "history.db"),
            })

        self.assertIsInstance(
            dependencies["solana_jupiter_provider"], JupiterSourceProvider
        )
        self.assertIsInstance(
            dependencies["solana_helius_provider"], HeliusDASProvider
        )
        self.assertEqual(
            dependencies["solana_price_max_relative_difference"], "0.03"
        )
        self.assertEqual(
            dependencies["solana_supply_max_index_slot_lag"], 150
        )
        self.assertEqual(
            dependencies["solana_history_max_distance_seconds"], 900.0
        )
        self.assertTrue(status["jupiter_configured"])
        self.assertTrue(status["helius_configured"])
        self.assertTrue(status["price_crosscheck_policy_configured"])
        self.assertTrue(status["supply_crosscheck_policy_configured"])
        self.assertTrue(status["history_distance_policy_configured"])

        rendered = repr(status)
        self.assertNotIn("jupiter-secret", rendered)
        self.assertNotIn("helius-secret", rendered)
        self.assertNotIn("keyed-secret", rendered)

    def test_invalid_enable_flag_fails_closed(self):
        with self.assertRaises(ValueError):
            build_solana_runtime_dependencies({
                "CMIS_SOLANA_PROVIDER_ENABLED": "sometimes"
            })

    def test_invalid_supply_lag_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                build_solana_runtime_dependencies({
                    "CMIS_SOLANA_PROVIDER_ENABLED": "1",
                    "CMIS_SOLANA_SUPPLY_MAX_INDEX_SLOT_LAG": "-1",
                    "CMIS_SOLANA_OBSERVATION_DB": os.path.join(
                        directory, "history.db"
                    ),
                })

    def test_runtime_gateway_auto_composes_when_enabled(self):
        with tempfile.TemporaryDirectory() as directory:
            gateway = RuntimeCMISGateway(
                verification_evidence_db_path=":memory:",
                solana_runtime_env={
                    "CMIS_SOLANA_PROVIDER_ENABLED": "yes",
                    "SOLANA_RPC_URL": "https://rpc.example.invalid",
                    "CMIS_SOLANA_OBSERVATION_DB": os.path.join(
                        directory, "history.db"
                    ),
                },
            )

        self.assertIsInstance(gateway.solana_rpc_provider, SolanaRPCProvider)
        self.assertIsInstance(gateway.solana_pyth_provider, PythSolanaPushProvider)
        self.assertIsInstance(
            gateway.solana_dexscreener_provider, DexScreenerSolanaProvider
        )
        self.assertIsInstance(
            gateway.solana_observation_ledger, SolanaObservationLedger
        )
        self.assertIsNone(gateway.solana_jupiter_provider)
        self.assertIsNone(gateway.solana_helius_provider)
        self.assertTrue(gateway.solana_runtime_configuration["enabled"])

    def test_explicit_provider_injection_remains_authoritative(self):
        sentinel = object()
        gateway = RuntimeCMISGateway(
            verification_evidence_db_path=":memory:",
            solana_runtime_env={},
            solana_rpc_provider=sentinel,
        )
        self.assertIs(gateway.solana_rpc_provider, sentinel)
        self.assertFalse(gateway.solana_runtime_configuration["enabled"])


if __name__ == "__main__":
    unittest.main()
