import unittest

from liquidity_scout.providers.x1.positive_balance_population_evidence import (
    evaluate_x1_positive_balance_population_bracket,
    evaluate_x1_positive_balance_population_observation,
    verify_x1_positive_balance_population_series,
)


MINT = "Mint111"
PROGRAM = "TokenProgram111"


def enumeration(*, slot=100, amounts=(40, 35, 25), owners=("A", "B", "A")):
    accounts = []
    for index, (amount, owner) in enumerate(zip(amounts, owners)):
        accounts.append(
            {
                "address": f"Acct{index}",
                "mint": MINT,
                "token_program_id": PROGRAM,
                "owner": owner,
                "state": "initialized",
                "raw_amount": str(amount),
                "decimals": 0,
            }
        )
    return {
        "chain": "x1",
        "source": "X1 RPC",
        "method": "getProgramAccounts",
        "mint": MINT,
        "token_program_id": PROGRAM,
        "slot": slot,
        "accounts": accounts,
        "account_count_candidate": len(accounts),
        "returned_account_identity_verified": True,
        "token_account_semantics_verified": True,
        "coverage": "unverified",
        "enumeration_complete": False,
        "truncation_absent_verified": False,
        "holder_semantics_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
    }


def supply(*, slot=101, amount="100"):
    return {
        "chain": "x1",
        "source": "X1 RPC",
        "method": "getTokenSupply",
        "mint": MINT,
        "slot": slot,
        "amount": amount,
        "decimals": 0,
        "mint_supply_observed": True,
    }


class X1PositiveBalancePopulationEvidenceTests(unittest.TestCase):
    def test_single_observation_proves_conservation_candidate_not_coverage(self):
        result = evaluate_x1_positive_balance_population_observation(
            enumeration(),
            supply(),
        )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["slot_scope_bounded"])
        self.assertTrue(result["supply_conservation_observed"])
        self.assertTrue(result["positive_balance_population_candidate_complete"])
        self.assertTrue(result["positive_balance_token_account_population_candidate_complete"])
        self.assertTrue(result["positive_balance_authority_address_population_candidate_complete"])
        self.assertFalse(result["positive_balance_population_coverage_verified"])
        self.assertFalse(result["positive_balance_token_account_population_complete_verified"])
        self.assertFalse(result["positive_balance_authority_address_population_complete_verified"])
        self.assertFalse(result["zero_balance_token_account_population_complete_verified"])
        self.assertEqual(result["returned_token_account_count"], 3)
        self.assertEqual(result["positive_balance_token_account_count"], 3)
        self.assertEqual(result["zero_balance_returned_token_account_count"], 0)
        self.assertEqual(
            result["unique_positive_balance_authority_address_count"],
            2,
        )
        self.assertEqual(
            result["authority_address_distribution"]["counted_entity"],
            "token_account_authority_address",
        )
        self.assertEqual(
            result["authority_address_distribution"]["buckets"]["top_1"][
                "percent_of_mint_supply"
            ],
            65.0,
        )
        self.assertFalse(result["wallet_identity_verified"])
        self.assertFalse(result["holder_semantics_verified"])
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_missing_positive_balance_or_wide_slot_span_fails_closed(self):
        missing = evaluate_x1_positive_balance_population_observation(
            enumeration(amounts=(40, 35, 20)),
            supply(),
        )
        self.assertFalse(missing["supply_conservation_observed"])
        self.assertFalse(missing["positive_balance_population_candidate_complete"])

        wide = evaluate_x1_positive_balance_population_observation(
            enumeration(slot=100),
            supply(slot=110),
        )
        self.assertFalse(wide["slot_scope_bounded"])
        self.assertFalse(wide["positive_balance_population_candidate_complete"])

    def test_missing_authority_does_not_destroy_token_account_population_proof(self):
        result = evaluate_x1_positive_balance_population_observation(
            enumeration(owners=("A", None, "A")),
            supply(),
        )

        self.assertTrue(result["supply_conservation_observed"])
        self.assertTrue(result["positive_balance_token_account_population_candidate_complete"])
        self.assertFalse(result["positive_balance_authority_fields_complete"])
        self.assertIsNone(result["unique_positive_balance_authority_address_count"])
        self.assertFalse(
            result["positive_balance_authority_address_population_candidate_complete"]
        )
        self.assertIn(
            "one_or_more_positive_balance_authority_fields_missing",
            result["warnings"],
        )

    def test_stable_supply_bracket_accepts_enumeration_inside_bracket(self):
        result = evaluate_x1_positive_balance_population_bracket(
            enumeration(slot=105),
            supply(slot=100),
            supply(slot=108),
            max_bracket_span=10,
        )

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["supply_bracket_bounded"])
        self.assertTrue(result["mint_supply_stable_across_bracket"])
        self.assertTrue(result["supply_conservation_observed"])
        self.assertTrue(result["positive_balance_population_candidate_complete"])
        self.assertFalse(result["positive_balance_population_coverage_verified"])

    def test_supply_change_or_out_of_bracket_rejects_population_candidate(self):
        changed = evaluate_x1_positive_balance_population_bracket(
            enumeration(slot=105),
            supply(slot=100, amount="100"),
            supply(slot=108, amount="101"),
            max_bracket_span=10,
        )
        self.assertFalse(changed["mint_supply_stable_across_bracket"])
        self.assertFalse(changed["positive_balance_population_candidate_complete"])

        outside = evaluate_x1_positive_balance_population_bracket(
            enumeration(slot=99),
            supply(slot=100),
            supply(slot=108),
            max_bracket_span=10,
        )
        self.assertIn(
            "enumeration_slot_outside_supply_bracket",
            outside["errors"],
        )
        self.assertFalse(outside["positive_balance_population_candidate_complete"])

    def test_repeated_bounded_conservation_verifies_positive_balance_coverage(self):
        observations = [
            evaluate_x1_positive_balance_population_observation(
                enumeration(slot=100 + i * 2),
                supply(slot=101 + i * 2),
            )
            for i in range(3)
        ]

        result = verify_x1_positive_balance_population_series(observations)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["observation_count"], 3)
        self.assertTrue(result["all_supply_conservation_observations_passed"])
        self.assertTrue(result["identity_stable"])
        self.assertTrue(result["positive_balance_population_coverage_verified"])
        self.assertTrue(result["positive_balance_token_account_population_complete_verified"])
        self.assertTrue(result["positive_balance_authority_address_population_complete_verified"])
        self.assertFalse(result["zero_balance_token_account_population_complete_verified"])
        self.assertEqual(result["counted_entity"], "positive_balance_token_account")
        self.assertEqual(
            result["authority_distribution_counted_entity"],
            "token_account_authority_address",
        )
        self.assertFalse(result["holder_semantics_verified"])
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_series_rejects_one_incomplete_observation(self):
        observations = [
            evaluate_x1_positive_balance_population_observation(
                enumeration(slot=100),
                supply(slot=101),
            ),
            evaluate_x1_positive_balance_population_observation(
                enumeration(slot=102, amounts=(40, 35, 20)),
                supply(slot=103),
            ),
            evaluate_x1_positive_balance_population_observation(
                enumeration(slot=104),
                supply(slot=105),
            ),
        ]

        result = verify_x1_positive_balance_population_series(observations)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["positive_balance_population_coverage_verified"])


if __name__ == "__main__":
    unittest.main()
