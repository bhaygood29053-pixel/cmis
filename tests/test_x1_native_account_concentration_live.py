"""Opt-in live finalized native-XNT account concentration evidence."""

import json
import os
import unittest

from liquidity_scout.providers.x1.native_account_concentration import (
    collect_native_xnt_account_concentration,
)


RUN_LIVE = os.getenv("RUN_X1_NATIVE_ACCOUNT_CONCENTRATION_LIVE") == "1"


@unittest.skipUnless(
    RUN_LIVE,
    "set RUN_X1_NATIVE_ACCOUNT_CONCENTRATION_LIVE=1 to run read-only evidence",
)
class X1NativeAccountConcentrationLiveTests(unittest.TestCase):
    def test_live_finalized_native_xnt_distribution(self):
        result = collect_native_xnt_account_concentration(max_slot_span=64)

        summary = {
            "status": result["status"],
            "counted_entity": result["counted_entity"],
            "holder_count_state": result["holder_count_state"],
            "native_account_concentration_verified": result[
                "native_account_concentration_verified"
            ],
            "largest_accounts_slot": result["largest_accounts_slot"],
            "network_supply_slot": result["network_supply_slot"],
            "slot_span": result["slot_span"],
            "slot_scope_verified": result["slot_scope_verified"],
            "returned_largest_account_count": result[
                "returned_largest_account_count"
            ],
            "buckets": result["buckets"],
            "beneficial_owner_identity_verified": result[
                "beneficial_owner_identity_verified"
            ],
            "person_or_wallet_group_count_verified": result[
                "person_or_wallet_group_count_verified"
            ],
            "cmis_promotable": result["cmis_promotable"],
        }
        print(
            "[XNT native account concentration] "
            + json.dumps(summary, sort_keys=True)
        )

        self.assertEqual(result["status"], "verified")
        self.assertTrue(result["native_account_concentration_verified"])
        self.assertTrue(result["cmis_promotable"])
        self.assertTrue(result["slot_scope_verified"])
        self.assertGreaterEqual(result["returned_largest_account_count"], 20)
        top_20 = result["buckets"]["top_20"]["percent_of_circulating_xnt"]
        self.assertIsInstance(top_20, (int, float))
        self.assertGreaterEqual(top_20, 0)
        self.assertLessEqual(top_20, 100)
        self.assertEqual(result["holder_count_state"], "not_applicable")
        self.assertFalse(result["beneficial_owner_identity_verified"])
        self.assertFalse(result["person_or_wallet_group_count_verified"])
        self.assertFalse(result["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
