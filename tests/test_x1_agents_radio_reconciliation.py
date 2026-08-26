import unittest

from liquidity_scout.providers.x1 import (
    X1AgentsRadioProvider,
    parse_agents_radio_catalog,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
)


class X1AgentsRadioReconciliationTests(unittest.TestCase):
    def test_agents_radio_xdex_matches_existing_cmis_observed_identity(self):
        parsed = parse_agents_radio_catalog(
            {
                "generated_at": "2026-08-26T19:30:58.492Z",
                "count": 1,
                "programs": [
                    {
                        "program_id": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                        "name": "XDEX",
                        "name_source": "curated",
                        "category": "DEX",
                        "status": "live",
                        "verified": False,
                    }
                ],
            }
        )

        self.assertEqual(len(parsed["programs"]), 1)

        record = parsed["programs"][0]

        self.assertEqual(
            record["program_id"],
            XDEX_MAINNET_OBSERVED_PROGRAM_ID,
        )

        # The agreement is useful corroborating evidence, but Agents Radio
        # does not become the authority for the existing CMIS identity.
        self.assertEqual(record["name"], "XDEX")
        self.assertEqual(record["name_source"], "curated")
        self.assertIs(record["provider_verified_claim"], False)
        self.assertFalse(record["cmis_identity_promoted"])
        self.assertFalse(record["onchain_account_verified"])
        self.assertFalse(record["onchain_executable_verified"])

    def test_provider_is_explicitly_x1_scoped(self):
        provider = X1AgentsRadioProvider()

        self.assertEqual(provider.chain, "x1")


if __name__ == "__main__":
    unittest.main()
