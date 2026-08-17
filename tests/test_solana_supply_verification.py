import unittest

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT, INSUFFICIENT_EVIDENCE
from liquidity_scout.providers.solana.supply_verification import (
    verify_rpc_vs_helius_supply,
)


MINT = "Mint111"


def rpc(*, amount="42000000", decimals=6, slot=1000):
    return {
        "chain": "solana",
        "source": "solana_rpc",
        "method": "getTokenSupply",
        "mint": MINT,
        "context_slot": slot,
        "amount_raw": amount,
        "decimals": decimals,
        "supply_verified": True,
        "coverage": "total_token_supply",
    }


def helius(*, supply=42000000, decimals=6, slot=995):
    return {
        "chain": "solana",
        "source": "helius_das",
        "mint": MINT,
        "asset_available": True,
        "identity_verified": True,
        "last_indexed_slot": slot,
        "indexed_supply_candidate": supply,
        "supply_unit": "TOKEN_BASE_UNITS",
        "supply_semantics_verified": True,
        "decimals": decimals,
    }


class SolanaSupplyVerificationTests(unittest.TestCase):
    def test_slot_lag_is_required_and_has_no_hidden_default(self):
        for value in (None, -1, 1.5, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    verify_rpc_vs_helius_supply(
                        rpc(),
                        helius(),
                        max_index_slot_lag=value,  # type: ignore[arg-type]
                    )

    def test_matching_independent_supply_within_slot_window_is_agreement_not_promotion(self):
        result = verify_rpc_vs_helius_supply(
            rpc(slot=1000),
            helius(slot=995),
            max_index_slot_lag=10,
        )

        self.assertEqual(result["status"], AGREEMENT)
        self.assertTrue(result["identity_verified"])
        self.assertTrue(result["semantics_verified"])
        self.assertTrue(result["relative_recency_verified"])
        self.assertFalse(result["freshness_verified"])
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["slot_gap"], 5)
        self.assertTrue(result["supply_match"])
        self.assertTrue(result["decimals_match"])
        self.assertEqual(result["independent_source_count"], 2)
        self.assertEqual(result["decision_reason"], "independent_supply_agreement")
        self.assertIn("absolute_freshness_not_verified", result["warnings"])

    def test_supply_mismatch_within_slot_window_is_conflict(self):
        result = verify_rpc_vs_helius_supply(
            rpc(amount="42000000", slot=1000),
            helius(supply=41000000, slot=999),
            max_index_slot_lag=5,
        )

        self.assertEqual(result["status"], CONFLICT)
        self.assertTrue(result["relative_recency_verified"])
        self.assertFalse(result["supply_match"])
        self.assertEqual(result["decision_reason"], "supply_conflict_within_slot_window")

    def test_supply_mismatch_outside_slot_window_is_insufficient_not_conflict(self):
        result = verify_rpc_vs_helius_supply(
            rpc(amount="42000000", slot=2000),
            helius(supply=41000000, slot=1000),
            max_index_slot_lag=50,
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertFalse(result["relative_recency_verified"])
        self.assertEqual(result["slot_gap"], 1000)
        self.assertEqual(result["decision_reason"], "index_slot_lag_exceeds_limit")
        self.assertIn("index_slot_lag_exceeds_limit", result["rejection_reasons"])
        self.assertIn("helius_index_slot_outside_configured_window", result["warnings"])

    def test_matching_supply_outside_slot_window_stays_insufficient(self):
        result = verify_rpc_vs_helius_supply(
            rpc(slot=2000),
            helius(slot=1000),
            max_index_slot_lag=50,
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertTrue(result["supply_match"])
        self.assertFalse(result["relative_recency_verified"])

    def test_decimals_mismatch_is_conflict_even_when_slot_window_is_wide(self):
        result = verify_rpc_vs_helius_supply(
            rpc(decimals=6, slot=2000),
            helius(decimals=9, slot=1000),
            max_index_slot_lag=5000,
        )

        self.assertEqual(result["status"], CONFLICT)
        self.assertFalse(result["decimals_match"])
        self.assertEqual(result["decision_reason"], "decimals_conflict")

    def test_decimals_mismatch_remains_conflict_even_when_index_slot_is_old(self):
        result = verify_rpc_vs_helius_supply(
            rpc(decimals=6, slot=2000),
            helius(decimals=9, slot=1000),
            max_index_slot_lag=5,
        )

        self.assertEqual(result["status"], CONFLICT)
        self.assertFalse(result["relative_recency_verified"])
        self.assertEqual(result["decision_reason"], "decimals_conflict")

    def test_helius_supply_semantics_must_be_explicitly_verified(self):
        record = helius()
        record["supply_semantics_verified"] = False

        result = verify_rpc_vs_helius_supply(
            rpc(),
            record,
            max_index_slot_lag=10,
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn("helius_supply_semantics_unverified", result["rejection_reasons"])

    def test_helius_supply_unit_must_match_base_units(self):
        record = helius()
        record["supply_unit"] = "UI_TOKENS"

        result = verify_rpc_vs_helius_supply(
            rpc(),
            record,
            max_index_slot_lag=10,
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn("helius_supply_unit_mismatch", result["rejection_reasons"])

    def test_mint_mismatch_fails_closed(self):
        record = helius()
        record["mint"] = "OtherMint"

        result = verify_rpc_vs_helius_supply(
            rpc(),
            record,
            max_index_slot_lag=10,
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn("mint_mismatch", result["rejection_reasons"])

    def test_invalid_source_or_wire_contract_fails_closed(self):
        canonical = rpc()
        canonical["amount_raw"] = 42000000
        indexed = helius()
        indexed["source"] = "other"

        result = verify_rpc_vs_helius_supply(
            canonical,
            indexed,
            max_index_slot_lag=10,
        )

        self.assertEqual(result["status"], INSUFFICIENT_EVIDENCE)
        self.assertIn("rpc_amount_invalid", result["rejection_reasons"])
        self.assertIn("helius_source_mismatch", result["rejection_reasons"])


if __name__ == "__main__":
    unittest.main()
