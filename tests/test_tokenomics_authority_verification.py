import unittest
from types import SimpleNamespace
from unittest.mock import patch

from liquidity_scout.integrations import moltgrid
from liquidity_scout.services.market_presentation import format_field_line


class TokenomicsAuthorityVerificationTests(unittest.TestCase):
    def setUp(self):
        self.listener = SimpleNamespace(
            SETTINGS=SimpleNamespace(x1_rpc_url="https://rpc.example")
        )
        self.snapshot = {
            "symbol": "TEST",
            "token_address": "MintA",
        }

    def test_unverified_mint_authority_fails_closed(self):
        record = {
            "mint_authority": None,
            "mint_authority_verified": False,
            "freeze_authority": None,
            "freeze_authority_verified": False,
            "raw_supply": "1000000",
            "decimals": 6,
            "total_supply": "1",
            "supply_verified": True,
        }

        with patch.object(moltgrid, "core_get_mint_info", return_value=record):
            info = moltgrid.get_token_mint_info(self.listener, "MintA")

        self.assertIsNone(info)

        line = format_field_line(
            "max_supply",
            self.snapshot,
            format_usd=lambda value: str(value),
            get_mint_info=lambda _mint: info,
        )
        self.assertIn("Not available from verified X1 RPC data", line)
        self.assertNotIn("revoked", line.lower())

    def test_verified_null_mint_authority_is_revoked(self):
        record = {
            "mint_authority": None,
            "mint_authority_verified": True,
            "freeze_authority": None,
            "freeze_authority_verified": True,
            "raw_supply": "1000000",
            "decimals": 6,
            "total_supply": "1",
            "supply_verified": True,
        }

        with patch.object(moltgrid, "core_get_mint_info", return_value=record):
            info = moltgrid.get_token_mint_info(self.listener, "MintA")

        self.assertEqual(
            info,
            {
                "mint_authority": None,
                "freeze_authority": None,
                "supply": "1",
                "raw_supply": "1000000",
                "decimals": 6,
            },
        )

        line = format_field_line(
            "max_supply",
            self.snapshot,
            format_usd=lambda value: str(value),
            get_mint_info=lambda _mint: info,
        )
        self.assertIn("Mint authority revoked", line)

    def test_verified_active_mint_authority_is_active(self):
        record = {
            "mint_authority": "AuthorityA",
            "mint_authority_verified": True,
            "freeze_authority": None,
            "freeze_authority_verified": False,
            "raw_supply": "1000000",
            "decimals": 6,
            "total_supply": "1",
            "supply_verified": True,
        }

        with patch.object(moltgrid, "core_get_mint_info", return_value=record):
            info = moltgrid.get_token_mint_info(self.listener, "MintA")

        self.assertEqual(
            info,
            {
                "mint_authority": "AuthorityA",
                "freeze_authority": None,
                "supply": "1",
                "raw_supply": "1000000",
                "decimals": 6,
            },
        )

        line = format_field_line(
            "max_supply",
            self.snapshot,
            format_usd=lambda value: str(value),
            get_mint_info=lambda _mint: info,
        )
        self.assertIn("Mint authority active", line)
        self.assertNotIn("revoked", line.lower())


if __name__ == "__main__":
    unittest.main()
