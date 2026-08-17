import unittest

from liquidity_scout.cmis.evidence import (
    AGREEMENT,
    build_data_quality_assessment,
    compare_same_fact_exact,
)
from liquidity_scout.providers.solana.evidence import (
    ADDRESS_OR_NULL,
    COUNT,
    TOKEN_BASE_UNITS,
    build_solana_largest_accounts_evidence,
    build_solana_mint_state_evidence,
    build_solana_supply_evidence,
)


MINT = "Mint111"


def supply_record(*, amount="42000000", decimals=6, slot=123):
    return {
        "chain": "solana",
        "source": "solana_rpc",
        "method": "getTokenSupply",
        "mint": MINT,
        "context_slot": slot,
        "amount_raw": amount,
        "decimals": decimals,
        "ui_amount_string": "42",
        "supply_verified": True,
        "coverage": "total_token_supply",
    }


def mint_record(*, amount="42000000", decimals=6, slot=124):
    return {
        "chain": "solana",
        "source": "solana_rpc",
        "method": "getAccountInfo(jsonParsed)",
        "mint": MINT,
        "context_slot": slot,
        "owner_program_id": "TokenProgram111",
        "parsed_program": "spl-token",
        "program_identity_verified": True,
        "amount_raw": amount,
        "decimals": decimals,
        "mint_authority": None,
        "freeze_authority": "Freeze111",
        "is_initialized": True,
        "extension_names": [],
        "mint_state_verified": True,
    }


def largest_accounts_record():
    return {
        "chain": "solana",
        "source": "solana_rpc",
        "method": "getTokenLargestAccounts",
        "mint": MINT,
        "context_slot": 125,
        "accounts": [
            {
                "address": "AccountA",
                "amount_raw": "1000",
                "decimals": 6,
                "ui_amount_string": "0.001",
            },
            {
                "address": "AccountB",
                "amount_raw": "500",
                "decimals": 6,
                "ui_amount_string": "0.0005",
            },
        ],
        "account_count_observed": 2,
        "counted_entity": "token_accounts",
        "coverage": "largest_token_accounts_only",
        "total_holder_count_verified": False,
        "warning": "concentration only",
    }


class SolanaRPCEvidenceTests(unittest.TestCase):
    def test_supply_adapter_preserves_exact_base_units_and_slot(self):
        result = build_solana_supply_evidence(supply_record())

        self.assertTrue(result["evidence_ready"])
        self.assertFalse(result["cmis_promotable"])
        self.assertEqual(result["rejection_reasons"], [])
        self.assertEqual(len(result["observations"]), 2)

        supply = result["observations"][0]
        decimals = result["observations"][1]

        self.assertEqual(supply["chain"], "solana")
        self.assertEqual(supply["fact_type"], "token_total_supply_base_units")
        self.assertEqual(supply["subject_id"], MINT)
        self.assertEqual(supply["source"], "solana_rpc")
        self.assertEqual(supply["source_role"], "canonical_onchain")
        self.assertEqual(supply["block_slot"], 123)
        self.assertEqual(supply["raw_value"], "42000000")
        self.assertEqual(supply["normalized_value"], "42000000")
        self.assertEqual(supply["unit"], TOKEN_BASE_UNITS)
        self.assertTrue(supply["identity_verified"])
        self.assertTrue(supply["semantics_verified"])
        self.assertFalse(supply["freshness_verified"])
        self.assertIn("freshness_not_verified", supply["warnings"])

        self.assertEqual(decimals["fact_type"], "token_decimals")
        self.assertEqual(decimals["normalized_value"], "6")
        self.assertEqual(decimals["unit"], COUNT)
        self.assertEqual(decimals["block_slot"], 123)

    def test_freshness_is_caller_controlled_not_inferred_from_slot(self):
        default = build_solana_supply_evidence(supply_record(slot=999))
        explicit = build_solana_supply_evidence(
            supply_record(slot=999),
            freshness_verified=True,
        )

        self.assertFalse(default["observations"][0]["freshness_verified"])
        self.assertEqual(default["observations"][0]["warnings"], ["freshness_not_verified"])
        self.assertTrue(explicit["observations"][0]["freshness_verified"])
        self.assertEqual(explicit["observations"][0]["warnings"], [])

    def test_supply_and_mint_account_supply_can_compare_exactly_but_are_not_independent(self):
        supply = build_solana_supply_evidence(supply_record())["observations"][0]
        mint = build_solana_mint_state_evidence(mint_record())["observations"][0]

        comparison = compare_same_fact_exact(supply, mint)
        quality = build_data_quality_assessment(
            observations=[supply, mint],
            verification=comparison,
        )

        self.assertEqual(comparison["status"], AGREEMENT)
        # Both observations come from the same canonical source, and freshness
        # is not proven. Numeric agreement must not be upgraded to HIGH quality.
        self.assertEqual(quality["quality"], "LOW")
        self.assertEqual(quality["independent_source_count"], 1)
        self.assertIn("SINGLE_SOURCE_ONLY", quality["reasons"])
        self.assertIn("FRESHNESS_UNVERIFIED", quality["reasons"])

    def test_mint_state_keeps_null_authority_as_explicit_non_numeric_fact(self):
        result = build_solana_mint_state_evidence(mint_record())

        self.assertTrue(result["evidence_ready"])
        by_type = {item["fact_type"]: item for item in result["observations"]}

        mint_authority = by_type["token_mint_authority"]
        freeze_authority = by_type["token_freeze_authority"]
        program = by_type["token_owner_program_id"]

        self.assertIsNone(mint_authority["raw_value"])
        self.assertIsNone(mint_authority["normalized_value"])
        self.assertEqual(mint_authority["unit"], ADDRESS_OR_NULL)
        self.assertEqual(freeze_authority["raw_value"], "Freeze111")
        self.assertIsNone(freeze_authority["normalized_value"])
        self.assertEqual(program["raw_value"], "TokenProgram111")
        self.assertIsNone(program["normalized_value"])

    def test_token_2022_extensions_remain_separate_provenance_not_numeric_fact(self):
        record = mint_record()
        record["parsed_program"] = "spl-token-2022"
        record["owner_program_id"] = "Token2022Program111"
        record["extension_names"] = ["transferFeeConfig", "metadataPointer"]

        result = build_solana_mint_state_evidence(record)

        self.assertTrue(result["evidence_ready"])
        self.assertEqual(
            result["extensions"],
            ["transferFeeConfig", "metadataPointer"],
        )
        program = next(
            item for item in result["observations"] if item["fact_type"] == "token_program_label"
        )
        self.assertEqual(program["raw_value"], "spl-token-2022")
        self.assertIsNone(program["normalized_value"])

    def test_largest_accounts_create_account_balance_evidence_not_holder_count(self):
        result = build_solana_largest_accounts_evidence(largest_accounts_record())

        self.assertTrue(result["evidence_ready"])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["holder_count_fact_created"])
        self.assertEqual(result["fact_type"], "token_account_balance_base_units")
        self.assertEqual(len(result["observations"]), 2)
        self.assertTrue(
            all(
                item["fact_type"] == "token_account_balance_base_units"
                for item in result["observations"]
            )
        )
        self.assertFalse(
            any("holder" in item["fact_type"] for item in result["observations"])
        )
        self.assertEqual(
            result["observations"][0]["subject_id"],
            f"mint:{MINT}:token_account:AccountA",
        )

    def test_largest_accounts_rejects_attempted_holder_promotion(self):
        record = largest_accounts_record()
        record["total_holder_count_verified"] = True

        result = build_solana_largest_accounts_evidence(record)

        self.assertFalse(result["evidence_ready"])
        self.assertFalse(result["holder_count_fact_created"])
        self.assertIn("holder_count_must_remain_unverified", result["rejection_reasons"])

    def test_wrong_supply_contract_fails_closed(self):
        record = supply_record()
        record["coverage"] = "partial"
        record["supply_verified"] = False

        result = build_solana_supply_evidence(record)

        self.assertFalse(result["evidence_ready"])
        self.assertEqual(result["observations"], [])
        self.assertIn("supply_unverified", result["rejection_reasons"])
        self.assertIn("supply_coverage_unverified", result["rejection_reasons"])

    def test_mint_state_rejects_unverified_program_identity(self):
        record = mint_record()
        record["program_identity_verified"] = False

        result = build_solana_mint_state_evidence(record)

        self.assertFalse(result["evidence_ready"])
        self.assertIn("program_identity_unverified", result["rejection_reasons"])

    def test_duplicate_largest_account_addresses_fail_closed(self):
        record = largest_accounts_record()
        record["accounts"][1]["address"] = "AccountA"

        result = build_solana_largest_accounts_evidence(record)

        self.assertFalse(result["evidence_ready"])
        self.assertEqual(result["observations"], [])
        self.assertIn("duplicate_account_address", result["rejection_reasons"])


if __name__ == "__main__":
    unittest.main()
