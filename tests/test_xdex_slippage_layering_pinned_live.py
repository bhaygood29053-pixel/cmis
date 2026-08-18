import os
import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.transaction_semantics import fetch_transaction
from tests.test_xdex_onchain_slippage_semantics_live import (
    POOL,
    XENCAT,
    XNT,
    _decode_base_input,
    _pool_program_instructions,
    _vault_outflow,
)


RUN_LIVE = os.getenv("RUN_XDEX_ONCHAIN_SLIPPAGE_LIVE") == "1"

# These completed XDEX transactions were discovered by the live read-only scan
# on 2026-08-18. Their encoded minimum-output headroom is extremely close to a
# visible XDEX UI slippage preset plus the independently observed ~0.52% quote
# adjustment. The preset association is a mathematical fit, not a claim about
# what the transaction submitter selected in the UI.
PINNED_PRESET_FITS = (
    {
        "signature": "3Q8TL2Uc5ix6DUsffzTj13koRZBhwRQqCJrYMaMVrKUGw7VNMtP4JeV28QgRaqsxJG19mCoXkXqj4ggARvnvGVTd",
        "slot": 71121980,
        "preset_pct": Decimal("1"),
    },
    {
        "signature": "2zyyzgruHLfPmW6NgSqBAf3sa7B6aiBZgGgQKezaizybkTFrpCiJAUjDiQac1PcD5mg6Y2uSTijeT7HtYdm2f1gy",
        "slot": 70869752,
        "preset_pct": Decimal("5"),
    },
)

MYSTERY_LOW_PCT = Decimal("0.45")
MYSTERY_HIGH_PCT = Decimal("0.60")


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_XDEX_ONCHAIN_SLIPPAGE_LIVE=1 to run pinned XDEX slippage-layer evidence",
)
class XDEXPinnedSlippageLayeringLiveTests(unittest.TestCase):
    def test_visible_slippage_presets_leave_a_separate_half_percent_layer(self):
        residuals = []

        for case in PINNED_PRESET_FITS:
            tx = fetch_transaction(case["signature"])
            self.assertIsInstance(tx, dict)
            self.assertEqual(tx.get("slot"), case["slot"])
            self.assertIsNone((tx.get("meta") or {}).get("err"))

            pool_instructions = _pool_program_instructions(tx)
            self.assertEqual(
                len(pool_instructions),
                1,
                "Pinned evidence transaction no longer decodes as one direct pool instruction",
            )
            instruction, accounts, location = pool_instructions[0]
            decoded = _decode_base_input(instruction, accounts, location)
            self.assertIsNotNone(decoded)
            self.assertEqual(
                {decoded["input_mint"], decoded["output_mint"]},
                {XNT, XENCAT},
            )

            outflow = _vault_outflow(
                tx,
                decoded["output_vault"],
                decoded["output_mint"],
            )
            self.assertIsNotNone(outflow)
            actual_output_raw, output_decimals = outflow
            minimum_output_raw = decoded["amount_out_min_raw"]
            self.assertGreater(actual_output_raw, minimum_output_raw)

            headroom_pct = (
                (Decimal(actual_output_raw) - Decimal(minimum_output_raw))
                / Decimal(actual_output_raw)
                * Decimal(100)
            )

            # Counterfactual: if the only threshold reduction were the visible
            # UI preset, min-out would equal actual_output * (1 - preset).
            # The remaining reduction is measured independently in percentage
            # points of actual on-chain pool output.
            preset_pct = case["preset_pct"]
            preset_only_min = (
                Decimal(actual_output_raw)
                * (Decimal(1) - preset_pct / Decimal(100))
            )
            separate_layer_pct = (
                (preset_only_min - Decimal(minimum_output_raw))
                / Decimal(actual_output_raw)
                * Decimal(100)
            )
            residuals.append(separate_layer_pct)

            scale = Decimal(10) ** output_decimals
            print(
                {
                    "signature": case["signature"],
                    "slot": case["slot"],
                    "pool": POOL,
                    "direction": f"{decoded['input_mint']}->{decoded['output_mint']}",
                    "actual_pool_output_ui": str(Decimal(actual_output_raw) / scale),
                    "minimum_output_ui": str(Decimal(minimum_output_raw) / scale),
                    "total_min_out_headroom_pct": str(headroom_pct),
                    "tested_visible_slippage_preset_pct": str(preset_pct),
                    "separate_layer_after_preset_pct": str(separate_layer_pct),
                }
            )

            self.assertGreaterEqual(separate_layer_pct, MYSTERY_LOW_PCT)
            self.assertLessEqual(separate_layer_pct, MYSTERY_HIGH_PCT)

        mean_residual = sum(residuals) / Decimal(len(residuals))
        print(f"Pinned preset-fit residuals: {[str(x) for x in residuals]}")
        print(f"Mean separate layer: {mean_residual}%")
        print(
            "Evidence classification: STRONGLY CORROBORATED that the ~0.52% "
            "adjustment is separate from the transaction's slippage/minimum-output layer; "
            "the exact economic label of that separate adjustment remains unverified."
        )


if __name__ == "__main__":
    unittest.main()
