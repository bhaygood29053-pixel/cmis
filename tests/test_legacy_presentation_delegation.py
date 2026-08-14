import unittest
from unittest.mock import patch

import moltgrid_signal_v12_ollama as legacy
from liquidity_scout.services import (
    FIELD_ORDER as SERVICE_FIELD_ORDER,
    wants_token_address as service_wants_token_address,
)


class LegacyPresentationDelegationTests(unittest.TestCase):
    def test_field_order_and_token_address_policy_come_from_services(self):
        self.assertIs(legacy.FIELD_ORDER, SERVICE_FIELD_ORDER)
        self.assertIs(legacy.wants_token_address, service_wants_token_address)

    def test_requested_asset_fields_delegates_with_route_predicates(self):
        with patch.object(
            legacy.history,
            "parse_historical_comparison",
            return_value={"kind": "comparison"},
        ), patch.object(
            legacy,
            "wants_volume_rank",
            return_value=True,
        ), patch.object(
            legacy,
            "wants_historical_liquidity",
            return_value=False,
        ), patch.object(
            legacy,
            "core_requested_asset_fields",
            return_value=["price"],
        ) as core:
            result = legacy.requested_asset_fields("question")

        self.assertEqual(result, ["price"])
        core.assert_called_once_with(
            "question",
            historical_comparison=True,
            volume_rank=True,
            historical_liquidity=False,
        )

    def test_format_field_line_delegates_with_rpc_callbacks(self):
        snap = {"symbol": "AGI"}
        with patch.object(
            legacy,
            "core_format_field_line",
            return_value="formatted",
        ) as core:
            result = legacy.format_field_line("price", snap)

        self.assertEqual(result, "formatted")
        core.assert_called_once_with(
            "price",
            snap,
            format_usd=legacy.format_usd,
            get_total_supply=legacy.get_token_total_supply,
            get_mint_info=legacy.get_token_mint_info,
        )

    def test_full_snapshot_lines_delegates_with_rpc_callbacks(self):
        snap = {"symbol": "AGI"}
        with patch.object(
            legacy,
            "core_full_snapshot_lines",
            return_value=["line"],
        ) as core:
            result = legacy.full_snapshot_lines(snap)

        self.assertEqual(result, ["line"])
        core.assert_called_once_with(
            snap,
            format_usd=legacy.format_usd,
            get_total_supply=legacy.get_token_total_supply,
            get_mint_info=legacy.get_token_mint_info,
        )


if __name__ == "__main__":
    unittest.main()
