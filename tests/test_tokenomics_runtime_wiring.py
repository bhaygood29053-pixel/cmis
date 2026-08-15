import unittest
from types import SimpleNamespace
from unittest.mock import patch

import x1_burn_scan as burn_scan
from liquidity_scout.integrations import moltgrid
from liquidity_scout.tokenomics import X1RPCError


class MoltGridTokenomicsWiringTests(unittest.TestCase):
    def setUp(self):
        self.listener = SimpleNamespace(
            SETTINGS=SimpleNamespace(
                x1_rpc_url="https://rpc.example",
            )
        )

    def test_total_supply_delegates_to_shared_core(self):
        record = {
            "total_supply": "123.45",
            "supply_verified": True,
        }

        with patch.object(
            moltgrid,
            "core_get_token_supply",
            return_value=record,
        ) as mock_supply:
            value = moltgrid.get_token_total_supply(
                self.listener,
                "MintA",
            )

        self.assertEqual(value, "123.45")
        mock_supply.assert_called_once_with(
            "MintA",
            rpc_url="https://rpc.example",
        )

    def test_total_supply_rpc_failure_remains_unavailable(self):
        with patch.object(
            moltgrid,
            "core_get_token_supply",
            side_effect=X1RPCError("boom"),
        ):
            value = moltgrid.get_token_total_supply(
                self.listener,
                "MintA",
            )

        self.assertIsNone(value)

    def test_mint_info_preserves_legacy_public_shape(self):
        record = {
            "mint_authority": None,
            "mint_authority_verified": True,
            "freeze_authority": "FreezeA",
            "freeze_authority_verified": True,
            "total_supply": "42.5",
            "raw_supply": "42500000",
            "decimals": 6,
            "supply_verified": True,
        }

        with patch.object(
            moltgrid,
            "core_get_mint_info",
            return_value=record,
        ):
            value = moltgrid.get_token_mint_info(
                self.listener,
                "MintA",
            )

        self.assertEqual(
            value,
            {
                "mint_authority": None,
                "freeze_authority": "FreezeA",
                "supply": "42.5",
                "raw_supply": "42500000",
                "decimals": 6,
            },
        )

    def test_wire_market_core_replaces_legacy_tokenomics_helpers(self):
        listener = SimpleNamespace(
            SETTINGS=SimpleNamespace(
                x1_rpc_url="https://rpc.example",
            ),
            wants_asset_analysis=lambda _question: False,
            format_asset_analysis_answer=lambda *_args: "legacy-analysis",
        )

        wired = moltgrid.wire_market_core(listener)

        self.assertIs(wired, listener)
        self.assertTrue(callable(listener.get_token_total_supply))
        self.assertTrue(callable(listener.get_token_mint_info))

        with patch.object(
            moltgrid,
            "core_get_token_supply",
            return_value={
                "total_supply": "7",
                "supply_verified": True,
            },
        ):
            self.assertEqual(
                listener.get_token_total_supply("MintA"),
                "7",
            )


class BurnScannerTokenomicsWiringTests(unittest.TestCase):
    def test_get_token_info_delegates_and_preserves_raw_supply_shape(self):
        record = {
            "mint_authority": None,
            "mint_authority_verified": True,
            "freeze_authority": None,
            "freeze_authority_verified": True,
            "raw_supply": "2500000",
            "decimals": 6,
            "total_supply": "2.5",
            "supply_verified": True,
        }

        with patch.object(
            burn_scan,
            "core_get_mint_info",
            return_value=record,
        ) as mock_info:
            value = burn_scan.get_token_info("MintA")

        mock_info.assert_called_once_with(
            "MintA",
            rpc_url=burn_scan.RPC,
            retries=5,
            timeout=30,
        )
        self.assertEqual(value["decimals"], 6)
        self.assertEqual(value["supply"], "2500000")
        self.assertIsNone(value["mint_authority"])
        self.assertTrue(value["mint_authority_verified"])

    def test_get_token_info_fails_closed_without_verified_decimals(self):
        record = {
            "mint_authority": None,
            "mint_authority_verified": False,
            "freeze_authority": None,
            "freeze_authority_verified": False,
            "raw_supply": "2500000",
            "decimals": None,
            "total_supply": None,
            "supply_verified": False,
        }

        with patch.object(
            burn_scan,
            "core_get_mint_info",
            return_value=record,
        ):
            with self.assertRaises(RuntimeError):
                burn_scan.get_token_info("MintA")

    def test_missing_authority_remains_distinct_from_verified_null(self):
        record = {
            "mint_authority": None,
            "mint_authority_verified": False,
            "freeze_authority": None,
            "freeze_authority_verified": False,
            "raw_supply": "2500000",
            "decimals": 6,
            "total_supply": "2.5",
            "supply_verified": True,
        }

        with patch.object(
            burn_scan,
            "core_get_mint_info",
            return_value=record,
        ):
            value = burn_scan.get_token_info("MintA")

        self.assertIsNone(value["mint_authority"])
        self.assertFalse(value["mint_authority_verified"])
        self.assertIsNone(value["freeze_authority"])
        self.assertFalse(value["freeze_authority_verified"])


if __name__ == "__main__":
    unittest.main()
