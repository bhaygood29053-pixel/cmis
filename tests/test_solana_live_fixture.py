import unittest

from liquidity_scout.providers.solana.live_fixture import (
    SOLANA_TOKEN_2022_LIVE_FIXTURE,
)
from liquidity_scout.providers.solana.rpc import TOKEN_2022_PROGRAM_ID


class SolanaLiveFixtureTests(unittest.TestCase):
    def test_pyusd_fixture_is_exact_read_only_token_2022_contract(self):
        fixture = SOLANA_TOKEN_2022_LIVE_FIXTURE

        self.assertEqual(fixture.name, "PYUSD")
        self.assertEqual(
            fixture.mint,
            "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo",
        )
        self.assertEqual(fixture.program_kind, "token_2022")
        self.assertEqual(fixture.program_id, TOKEN_2022_PROGRAM_ID)
        self.assertEqual(fixture.decimals, 6)
        self.assertEqual(fixture.scope, "read_only_rpc_contract_probe")
        self.assertFalse(fixture.execution_authorized)

    def test_fixture_provenance_is_authoritative_solana_documentation(self):
        fixture = SOLANA_TOKEN_2022_LIVE_FIXTURE

        self.assertGreaterEqual(len(fixture.provenance_urls), 2)
        self.assertTrue(
            all(url.startswith("https://solana.com/") for url in fixture.provenance_urls)
        )
        self.assertTrue(any("pyusd" in url.lower() for url in fixture.provenance_urls))
        self.assertTrue(any("payments" in url.lower() for url in fixture.provenance_urls))


if __name__ == "__main__":
    unittest.main()
