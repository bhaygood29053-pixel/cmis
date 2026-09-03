import unittest

from liquidity_scout.providers.x1.native_account_concentration import (
    X1NativeAccountConcentrationError,
    build_native_xnt_account_concentration,
    parse_native_largest_accounts_result,
)


def largest(slot=100):
    return {
        "chain": "x1",
        "asset": "XNT",
        "slot": slot,
        "accounts": [
            {"address": f"A{i}", "base_units": str(amount)}
            for i, amount in enumerate(
                [200, 150, 100, 90, 80, 70, 60, 50, 40, 30,
                 20, 19, 18, 17, 16, 15, 14, 13, 12, 11]
            )
        ],
        "returned_account_count": 20,
        "commitment": "finalized",
        "filter": "circulating",
        "counted_entity": "native_xnt_account_address",
        "source": "X1 RPC getLargestAccounts(finalized,circulating)",
    }


def supply(slot=102):
    return {
        "chain": "x1",
        "asset": "XNT",
        "total_raw": "2000",
        "circulating_raw": "1000",
        "non_circulating_raw": "1000",
        "context_slot": str(slot),
        "commitment": "finalized",
        "source": "X1 RPC getSupply(finalized)",
    }


class X1NativeAccountConcentrationTests(unittest.TestCase):
    def test_parser_accepts_finalized_largest_accounts_shape(self):
        result = parse_native_largest_accounts_result(
            {
                "context": {"slot": 123},
                "value": [
                    {"address": "B", "lamports": 5},
                    {"address": "A", "lamports": 10},
                ],
            }
        )
        self.assertEqual(result["slot"], 123)
        self.assertEqual(result["filter"], "circulating")
        self.assertEqual(result["accounts"][0]["address"], "A")
        self.assertEqual(result["accounts"][0]["base_units"], "10")

    def test_builds_verified_native_account_concentration_not_holder_count(self):
        result = build_native_xnt_account_concentration(largest(), supply())

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["native_account_concentration_verified"])
        self.assertEqual(result["holder_count_state"], "not_applicable")
        self.assertEqual(
            result["counted_entity"],
            "native_xnt_account_address",
        )
        self.assertEqual(
            result["buckets"]["top_1"]["percent_of_circulating_xnt"],
            20.0,
        )
        self.assertEqual(
            result["buckets"]["top_5"]["percent_of_circulating_xnt"],
            62.0,
        )
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["person_or_wallet_group_count_verified"])
        self.assertTrue(result["cmis_promotable"])
        self.assertFalse(result["execution_authorized"])

    def test_wide_slot_span_fails_closed(self):
        result = build_native_xnt_account_concentration(
            largest(slot=100),
            supply(slot=200),
            max_slot_span=32,
        )
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["slot_scope_verified"])
        self.assertFalse(result["native_account_concentration_verified"])
        self.assertFalse(result["cmis_promotable"])

    def test_parser_rejects_duplicate_or_malformed_rows(self):
        with self.assertRaises(X1NativeAccountConcentrationError):
            parse_native_largest_accounts_result(
                {
                    "context": {"slot": 123},
                    "value": [
                        {"address": "A", "lamports": 5},
                        {"address": "A", "lamports": 4},
                    ],
                }
            )
        with self.assertRaises(X1NativeAccountConcentrationError):
            parse_native_largest_accounts_result(
                {
                    "context": {"slot": 123},
                    "value": [{"address": "A", "lamports": -1}],
                }
            )


if __name__ == "__main__":
    unittest.main()
