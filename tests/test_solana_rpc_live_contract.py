"""Opt-in read-only live acceptance for the Solana Phase 10 runtime.

Normal CI skips this module. The required live gate exercises the canonical RPC
facts used by promoted CMIS services: getTokenSupply and
getAccountInfo(jsonParsed). The concentration-only getTokenLargestAccounts
probe remains available behind a second flag because shared public Solana RPC
endpoints may block/rate-limit that heavier method and no promoted Phase 10
service depends on it.

When ``SOLANA_LIVE_REQUIRE_TOKEN_2022=1`` the probe is additionally bound to the
repository-approved Token-2022 fixture and fails closed if the exact mint,
program identity, decimals, or extension parsing drift.

No test accepts a signing keypair or constructs/broadcasts a transaction.
"""

import os
import tempfile
import unittest

from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.providers.solana.live_fixture import SOLANA_TOKEN_2022_LIVE_FIXTURE
from liquidity_scout.providers.solana.rpc import SolanaRPCProvider


RUN_LIVE = os.getenv("RUN_SOLANA_LIVE_TESTS") == "1"
RUN_LARGEST = os.getenv("RUN_SOLANA_LARGEST_ACCOUNTS_LIVE_TESTS") == "1"
REQUIRE_TOKEN_2022 = os.getenv("SOLANA_LIVE_REQUIRE_TOKEN_2022") == "1"


@unittest.skipUnless(RUN_LIVE, "RUN_SOLANA_LIVE_TESTS=1 is required")
class SolanaRPCLiveContractTests(unittest.TestCase):
    def setUp(self):
        mint = os.getenv("SOLANA_LIVE_TEST_MINT", "").strip()
        if not mint:
            self.skipTest("SOLANA_LIVE_TEST_MINT is required for token RPC probes")
        if REQUIRE_TOKEN_2022 and mint != SOLANA_TOKEN_2022_LIVE_FIXTURE.mint:
            self.fail(
                "Token-2022 live acceptance requires the repository-approved exact fixture mint"
            )
        self.mint = mint
        self.provider = SolanaRPCProvider()

    def test_required_canonical_token_rpc_contracts(self):
        supply = self.provider.get_token_supply(self.mint)
        mint_account = self.provider.get_mint_account(self.mint)

        self.assertEqual(supply["chain"], "solana")
        self.assertEqual(supply["source"], "solana_rpc")
        self.assertEqual(supply["mint"], self.mint)
        self.assertTrue(supply["supply_verified"])
        self.assertGreaterEqual(supply["context_slot"], 0)
        self.assertTrue(supply["amount_raw"].isdigit())

        self.assertEqual(mint_account["chain"], "solana")
        self.assertEqual(mint_account["source"], "solana_rpc")
        self.assertEqual(mint_account["mint"], self.mint)
        self.assertTrue(mint_account["program_identity_verified"])
        self.assertTrue(mint_account["mint_state_verified"])
        self.assertGreaterEqual(mint_account["context_slot"], 0)
        self.assertTrue(mint_account["amount_raw"].isdigit())

        # The methods may observe different slots. Decimals are stable mint
        # identity semantics, but supply values are not compared across calls
        # until CMIS has an explicit shared observation-scope contract.
        self.assertEqual(supply["decimals"], mint_account["decimals"])

        if REQUIRE_TOKEN_2022:
            fixture = SOLANA_TOKEN_2022_LIVE_FIXTURE
            self.assertEqual(mint_account["owner_program_id"], fixture.program_id)
            self.assertEqual(mint_account["program_kind"], fixture.program_kind)
            self.assertEqual(mint_account["decimals"], fixture.decimals)
            self.assertEqual(supply["decimals"], fixture.decimals)
            self.assertIsInstance(mint_account["extension_names"], list)
            self.assertTrue(mint_account["extension_names"])
            self.assertTrue(
                all(
                    isinstance(name, str) and bool(name.strip())
                    for name in mint_account["extension_names"]
                )
            )

    @unittest.skipUnless(
        RUN_LARGEST,
        "RUN_SOLANA_LARGEST_ACCOUNTS_LIVE_TESTS=1 is required",
    )
    def test_optional_largest_token_accounts_concentration_contract(self):
        largest = self.provider.get_token_largest_accounts(self.mint)

        self.assertEqual(largest["chain"], "solana")
        self.assertEqual(largest["source"], "solana_rpc")
        self.assertEqual(largest["mint"], self.mint)
        self.assertEqual(largest["coverage"], "largest_token_accounts_only")
        self.assertFalse(largest["total_holder_count_verified"])
        self.assertGreaterEqual(largest["context_slot"], 0)
        self.assertLessEqual(largest["account_count_observed"], 20)

    def test_production_runtime_exact_mint_identity_and_tokenomics(self):
        rpc_url = os.getenv("SOLANA_RPC_URL", "").strip()
        with tempfile.TemporaryDirectory() as directory:
            gateway = RuntimeCMISGateway(
                verification_evidence_db_path=":memory:",
                solana_runtime_env={
                    "CMIS_SOLANA_PROVIDER_ENABLED": "1",
                    "SOLANA_RPC_URL": rpc_url,
                    "CMIS_SOLANA_OBSERVATION_DB": os.path.join(
                        directory, "solana-observations.db"
                    ),
                },
            )

            identity = gateway.dispatch({
                "service": "asset_lookup",
                "chain": "solana",
                "asset": self.mint,
                "params": {},
            })
            tokenomics = gateway.dispatch({
                "service": "tokenomics",
                "chain": "solana",
                "asset": self.mint,
                "params": {},
            })

        self.assertEqual(identity["status"], "ok")
        self.assertEqual(identity["chain"], "solana")
        self.assertEqual(identity["asset"]["mint"], self.mint)
        self.assertTrue(identity["data"]["program"]["identity_verified"])
        self.assertTrue(
            any(
                source.get("source") == "solana_rpc"
                and source.get("role") == "canonical_mint_identity"
                for source in identity["sources"]
            )
        )

        if REQUIRE_TOKEN_2022:
            fixture = SOLANA_TOKEN_2022_LIVE_FIXTURE
            self.assertEqual(
                identity["data"]["program"]["program_kind"],
                fixture.program_kind,
            )
            self.assertEqual(
                identity["data"]["program"]["owner_program_id"],
                fixture.program_id,
            )
            self.assertEqual(identity["data"]["decimals"], fixture.decimals)
            self.assertEqual(
                identity["data"]["extension_names"],
                self.provider.get_mint_account(self.mint)["extension_names"],
            )

        self.assertEqual(tokenomics["status"], "partial")
        self.assertEqual(tokenomics["chain"], "solana")
        self.assertEqual(tokenomics["asset"]["mint"], self.mint)
        self.assertTrue(tokenomics["data"]["supply_verified"])
        self.assertIsNotNone(tokenomics["data"]["total_supply"])
        self.assertFalse(tokenomics["data"]["circulating_supply_verified"])
        self.assertFalse(tokenomics["data"]["maximum_supply_verified"])
        self.assertTrue(gateway.solana_runtime_configuration["enabled"])
        self.assertTrue(gateway.solana_runtime_configuration["rpc_configured"])
        self.assertFalse(
            gateway.solana_runtime_configuration["execution_authorized"]
        )


if __name__ == "__main__":
    unittest.main()
