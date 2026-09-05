import unittest

from liquidity_scout.providers.x1.warp_usdc_bridgein_v2_anchor import (
    DESTINATION_SLOT,
    DESTINATION_TX_SIGNATURE,
    EXPECTED_AMOUNT_RAW,
    USDC_X_MINT,
    WARP_PROGRAM_ID,
    verify_usdc_bridgein_v2_anchor,
)

INSTRUCTION_DATA_HEX = (
    "671b568b6dbd35f6"
    "a043b68c65000001"
    "c414a808ecd52890982490486eb7a589"
    "1f4f7cb588e2f8c71ac046994cde304e"
    "c6fa7af3bedbad3a3d65f36aabc97431"
    "b1bbe4c2d2f6e0e47ca60203452f5d61"
    "89516e0100000000"
    "82446b6a00000000"
)


class WarpUsdcBridgeInV2AnchorTests(unittest.TestCase):
    def test_exact_destination_mint_amount_is_decoded_from_bridge_instruction(self):
        result = verify_usdc_bridgein_v2_anchor(
            signature=DESTINATION_TX_SIGNATURE,
            slot=DESTINATION_SLOT,
            program_id=WARP_PROGRAM_ID,
            instruction_data_hex=INSTRUCTION_DATA_HEX,
            mint_to_mint=USDC_X_MINT,
            mint_to_amount_raw=EXPECTED_AMOUNT_RAW,
        )
        self.assertTrue(result["source_seq_verified"])
        self.assertTrue(result["amount_raw_match_verified"])
        self.assertTrue(result["source_timestamp_verified"])
        self.assertTrue(result["destination_mint_amount_semantics_verified"])
        self.assertEqual(result["instruction_amount_raw"], 24007049)
        self.assertEqual(result["amount"], "24.007049")
        self.assertFalse(result["route_wide_backing_verified"])
        self.assertFalse(result["current_usdcx_usd_equivalence_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_wrong_mint_amount_fails_closed(self):
        result = verify_usdc_bridgein_v2_anchor(
            signature=DESTINATION_TX_SIGNATURE,
            slot=DESTINATION_SLOT,
            program_id=WARP_PROGRAM_ID,
            instruction_data_hex=INSTRUCTION_DATA_HEX,
            mint_to_mint=USDC_X_MINT,
            mint_to_amount_raw=EXPECTED_AMOUNT_RAW + 1,
        )
        self.assertFalse(result["amount_raw_match_verified"])
        self.assertFalse(result["destination_mint_amount_semantics_verified"])

    def test_wrong_program_rejected(self):
        with self.assertRaisesRegex(ValueError, "program id"):
            verify_usdc_bridgein_v2_anchor(
                signature=DESTINATION_TX_SIGNATURE,
                slot=DESTINATION_SLOT,
                program_id="11111111111111111111111111111111",
                instruction_data_hex=INSTRUCTION_DATA_HEX,
                mint_to_mint=USDC_X_MINT,
                mint_to_amount_raw=EXPECTED_AMOUNT_RAW,
            )


if __name__ == "__main__":
    unittest.main()
