import unittest

from liquidity_scout.providers.x1.ninja_history import X1_NINJA_SOURCE
from liquidity_scout.providers.x1.ninja_trade_history_sample_evidence import (
    verify_ninja_trade_history_sample,
)


POOL = "Pool11111111111111111111111111111111111111"


class X1NinjaTradeHistoryEmptySampleTests(unittest.TestCase):
    def test_empty_returned_history_has_no_vacuous_complete_evidence(self):
        observation = {
            "chain": "x1",
            "source": X1_NINJA_SOURCE,
            "pool_address": POOL,
            "raw_response": {
                "lastUpdated": 1787079999,
                "total": 0,
                "trades": [],
            },
            "contract": {
                "response_contract_verified": True,
                "trade_row_shape_verified": True,
                "returned_trade_count": 0,
            },
            "semantics": {
                "trade_rows_verified": True,
                "side_classification_verified": False,
                "token_amount_units_verified": False,
                "usd_value_source_verified": False,
                "lp_event_semantics_verified": False,
                "transaction_signature_verified": False,
                "finality_verified": False,
                "pagination_or_range_verified": False,
            },
            "cmis_promotable": False,
        }

        result = verify_ninja_trade_history_sample(
            observation=observation,
            verification_reports={},
            pool_address=POOL,
            pool_identity_verified=True,
        )

        self.assertEqual(result["sample_size"], 0)
        self.assertFalse(result["distinct_sample_transaction_ids"])
        self.assertFalse(result["sample_rpc_report_binding_complete"])
        self.assertFalse(result["sample_rpc_transaction_success_complete"])
        self.assertFalse(result["sample_transaction_identity_binding_complete"])
        self.assertFalse(result["sample_row_pool_identity_match_complete"])
        self.assertFalse(result["sample_transaction_pool_membership_verified"])
        self.assertFalse(result["sample_maker_primary_signer_match_complete"])
        self.assertFalse(result["sample_rpc_slot_available_complete"])
        self.assertFalse(result["sample_provider_slot_rpc_match_complete"])
        self.assertFalse(result["sample_wallet_side_rpc_match_complete"])
        self.assertEqual(result["returned_order_observation"], "unavailable")
        self.assertFalse(
            result["semantics"]["transaction_pool_membership_verified"]
        )
        self.assertFalse(result["semantics"]["rpc_source_independence_verified"])
        self.assertIn("empty_returned_history_sample", result["warnings"])
        self.assertFalse(result["cmis_promotable"])


if __name__ == "__main__":
    unittest.main()
