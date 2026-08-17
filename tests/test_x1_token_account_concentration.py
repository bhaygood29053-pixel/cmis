import copy
import unittest

from liquidity_scout.providers.x1.token_account_concentration import (
    analyze_x1_token_account_concentration,
)


MINT = "mint111"


def largest():
    return {
        "chain": "x1",
        "source": "X1 RPC",
        "method": "getTokenLargestAccounts",
        "mint": MINT,
        "slot": 100,
        "descending_amount_order_verified": True,
        "accounts": [
            {"address": "acct1", "amount": "400", "decimals": 2},
            {"address": "acct2", "amount": "300", "decimals": 2},
            {"address": "acct3", "amount": "200", "decimals": 2},
            {"address": "acct4", "amount": "100", "decimals": 2},
        ],
        "holder_semantics_verified": False,
        "holder_coverage_verified": False,
        "beneficial_owner_identity_verified": False,
        "cmis_promotable": False,
    }


def supply():
    return {
        "chain": "x1",
        "source": "X1 RPC",
        "method": "getTokenSupply",
        "mint": MINT,
        "slot": 101,
        "amount": "2000",
        "decimals": 2,
        "mint_supply_observed": True,
        "circulating_supply_verified": False,
        "holder_semantics_verified": False,
        "cmis_promotable": False,
    }


class X1TokenAccountConcentrationTests(unittest.TestCase):
    def test_calculates_account_share_of_mint_supply_not_holder_concentration(self):
        result = analyze_x1_token_account_concentration(
            largest(),
            supply(),
            observation_scope_verified=True,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["data"]["metric_semantics"],
            "token_account_share_of_total_mint_supply",
        )
        self.assertEqual(
            result["data"]["buckets"]["top_1"]["percent_of_mint_supply"],
            "20",
        )
        self.assertEqual(
            result["data"]["buckets"]["top_5"]["percent_of_mint_supply"],
            "50",
        )
        self.assertEqual(
            result["data"]["observed_set_percent_of_mint_supply"],
            "50",
        )
        self.assertEqual(result["data"]["rpc_slot_span"], 1)
        self.assertTrue(result["token_account_concentration_calculated"])
        self.assertFalse(result["holder_concentration_verified"])
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["holder_coverage_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_unverified_observation_scope_is_partial_without_blocking_raw_calculation(self):
        result = analyze_x1_token_account_concentration(largest(), supply())

        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["observation_scope_verified"])
        self.assertEqual(
            result["data"]["buckets"]["top_1"]["share_of_mint_supply"],
            "0.2",
        )
        self.assertIn("observation_scope_unverified", result["warnings"])
        self.assertFalse(result["cmis_promotable"])

    def test_top_bucket_reports_available_account_count_without_implying_coverage(self):
        result = analyze_x1_token_account_concentration(
            largest(),
            supply(),
            observation_scope_verified=True,
        )

        self.assertEqual(
            result["data"]["buckets"]["top_20"]["available_account_count"],
            4,
        )
        self.assertIn(
            "fewer_than_20_largest_token_accounts_observed",
            result["warnings"],
        )
        self.assertFalse(result["holder_coverage_verified"])

    def test_same_raw_units_make_decimals_mismatch_fail_closed(self):
        item = largest()
        item["accounts"][0]["decimals"] = 6

        result = analyze_x1_token_account_concentration(item, supply())

        self.assertEqual(result["status"], "error")
        self.assertIn("account_0:decimals_mismatch", result["errors"])
        self.assertEqual(result["data"], {})

    def test_mint_mismatch_fails_closed(self):
        item = supply()
        item["mint"] = "other-mint"

        result = analyze_x1_token_account_concentration(largest(), item)

        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["mint"])
        self.assertIn("mint_identity_mismatch", result["errors"])
        self.assertFalse(result["cmis_promotable"])

    def test_unverified_largest_account_order_fails_closed(self):
        item = largest()
        item["descending_amount_order_verified"] = False

        result = analyze_x1_token_account_concentration(item, supply())

        self.assertEqual(result["status"], "error")
        self.assertIn("largest_accounts_order_unverified", result["errors"])

    def test_adapter_rechecks_order_even_if_transport_flag_claims_verified(self):
        item = largest()
        item["accounts"][1]["amount"] = "500"

        result = analyze_x1_token_account_concentration(item, supply())

        self.assertEqual(result["status"], "error")
        self.assertIn("account_1:descending_order_violation", result["errors"])

    def test_observed_account_sum_cannot_exceed_mint_supply(self):
        item = supply()
        item["amount"] = "900"

        result = analyze_x1_token_account_concentration(largest(), item)

        self.assertEqual(result["status"], "error")
        self.assertIn("observed_top_account_sum_exceeds_mint_supply", result["errors"])
        self.assertFalse(result["cmis_promotable"])

    def test_single_account_cannot_exceed_mint_supply(self):
        top = largest()
        top["accounts"] = [
            {"address": "acct1", "amount": "2100", "decimals": 2}
        ]

        result = analyze_x1_token_account_concentration(top, supply())

        self.assertEqual(result["status"], "error")
        self.assertIn("token_account_amount_exceeds_mint_supply", result["errors"])
        self.assertIn("observed_top_account_sum_exceeds_mint_supply", result["errors"])

    def test_zero_mint_supply_is_unavailable_not_division_error(self):
        item = supply()
        item["amount"] = "0"
        top = largest()
        top["accounts"] = []

        result = analyze_x1_token_account_concentration(top, item)

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["data"]["mint_supply_base_units"], "0")
        self.assertIn("zero_mint_supply", result["warnings"])
        self.assertFalse(result["cmis_promotable"])

    def test_invalid_slots_are_reported_but_not_used_as_freshness_inference(self):
        top = largest()
        total = supply()
        top["slot"] = True
        total["slot"] = None

        result = analyze_x1_token_account_concentration(
            top,
            total,
            observation_scope_verified=False,
        )

        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["data"]["rpc_slot_span"])
        self.assertIn(
            "largest_accounts_slot_unavailable_or_invalid",
            result["warnings"],
        )
        self.assertIn(
            "token_supply_slot_unavailable_or_invalid",
            result["warnings"],
        )
        self.assertFalse(result["observation_scope_verified"])

    def test_duplicate_address_fails_closed(self):
        item = largest()
        item["accounts"][1]["address"] = "acct1"

        result = analyze_x1_token_account_concentration(item, supply())

        self.assertEqual(result["status"], "error")
        self.assertIn("account_1:duplicate_address", result["errors"])

    def test_transport_contract_identity_is_rechecked(self):
        item = largest()
        item["source"] = "other"
        total = supply()
        total["method"] = "other"

        result = analyze_x1_token_account_concentration(item, total)

        self.assertEqual(result["status"], "error")
        self.assertIn("largest_accounts_source_mismatch", result["errors"])
        self.assertIn("token_supply_method_mismatch", result["errors"])

    def test_inputs_must_be_mappings(self):
        with self.assertRaisesRegex(TypeError, "largest_accounts must be a mapping"):
            analyze_x1_token_account_concentration([], supply())
        with self.assertRaisesRegex(TypeError, "token_supply must be a mapping"):
            analyze_x1_token_account_concentration(largest(), [])


if __name__ == "__main__":
    unittest.main()
