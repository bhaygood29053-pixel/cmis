"""Opt-in read-only live contract probe for the Solana RPC provider.

This module is skipped in normal CI. It accepts no signing keypair and calls
only getTokenSupply, getAccountInfo(jsonParsed), and getTokenLargestAccounts.
"""

import os
import unittest

from liquidity_scout.providers.solana.rpc import SolanaRPCProvider


RUN_LIVE = os.getenv("RUN_SOLANA_LIVE_TESTS") == "1"


@unittest.skipUnless(RUN_LIVE, "RUN_SOLANA_LIVE_TESTS=1 is required")
class SolanaRPCLiveContractTests(unittest.TestCase):
    def setUp(self):
        mint = os.getenv("SOLANA_LIVE_TEST_MINT", "").strip()
        if not mint:
            self.skipTest("SOLANA_LIVE_TEST_MINT is required for token RPC probes")
        self.mint = mint
        self.provider = SolanaRPCProvider()

    def test_read_only_token_rpc_contracts(self):
        supply = self.provider.get_token_supply(self.mint)
        mint_account = self.provider.get_mint_account(self.mint)
        largest = self.provider.get_token_largest_accounts(self.mint)

        self.assertEqual(supply["chain"], "solana")
        self.assertEqual(supply["source"], "solana_rpc")
        self.assertEqual(supply["mint"], self.mint)
        self.assertTrue(supply["supply_verified"])
        self.assertGreaterEqual(supply["context_slot"], 0)

        self.assertEqual(mint_account["chain"], "solana")
        self.assertEqual(mint_account["source"], "solana_rpc")
        self.assertEqual(mint_account["mint"], self.mint)
        self.assertTrue(mint_account["program_identity_verified"])
        self.assertTrue(mint_account["mint_state_verified"])
        self.assertGreaterEqual(mint_account["context_slot"], 0)

        self.assertEqual(largest["chain"], "solana")
        self.assertEqual(largest["source"], "solana_rpc")
        self.assertEqual(largest["mint"], self.mint)
        self.assertEqual(largest["coverage"], "largest_token_accounts_only")
        self.assertFalse(largest["total_holder_count_verified"])
        self.assertGreaterEqual(largest["context_slot"], 0)
        self.assertLessEqual(largest["account_count_observed"], 20)

        # This is a contract consistency check only. Nearby slots are not
        # interpreted as a shared freshness/observation scope.
        self.assertEqual(supply["decimals"], mint_account["decimals"])
        self.assertEqual(supply["amount_raw"], mint_account["amount_raw"])


if __name__ == "__main__":
    unittest.main()
