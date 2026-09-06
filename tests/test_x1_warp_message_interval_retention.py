import unittest

from liquidity_scout.providers.x1.warp_message_interval_retention import (
    CONTRACT,
    MAX_INTERVAL_SECONDS,
    WarpMessageIntervalRetentionError,
    evaluate_warp_message_interval_retention,
)
from liquidity_scout.providers.x1.warp_message_lifecycle_retention import (
    CONTRACT as LIFECYCLE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_message_retention_coverage import (
    CONTRACT as COUNTER_CLOSURE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    CONTRACT as MESSAGE_STATE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_onchain_inventory import WARP_PROGRAM_ID


START = 1400
END = 2000
OUT = "11111111111111111111111111111111"


def _counter_closure():
    return {
        "contract": COUNTER_CLOSURE_CONTRACT,
        "counter_account_closure_verified": True,
        "current_message_universe_count_closed": True,
    }


def _message_state(*, event_time=1500):
    empty = {
        "account_type_identity_verified": True,
        "all_pda_identities_verified": True,
        "accounts": [],
    }
    return {
        "contract": MESSAGE_STATE_CONTRACT,
        "solana": {
            "outgoing": {
                "account_type_identity_verified": True,
                "all_pda_identities_verified": True,
                "accounts": [
                    {
                        "pubkey": OUT,
                        "pda_identity_verified": True,
                        "timestamp": event_time,
                        "seq": 7,
                    }
                ],
            },
            "incoming": dict(empty),
        },
        "x1": {
            "outgoing": dict(empty),
            "incoming": dict(empty),
        },
    }


def _tx_row(*, kind, block_time=1500):
    if kind == "creation":
        pre, post = 0, 100
    elif kind == "closure":
        pre, post = 100, 0
    elif kind == "touch":
        pre, post = 100, 100
    elif kind == "zero_zero":
        pre, post = 0, 0
    else:
        raise ValueError(kind)
    return {
        "signature": f"sig-{kind}",
        "slot": block_time,
        "block_time": block_time,
        "transaction": {
            "transaction": {
                "message": {
                    "accountKeys": [WARP_PROGRAM_ID, OUT],
                }
            },
            "meta": {
                "preBalances": [1, pre],
                "postBalances": [1, post],
                "logMessages": [],
            },
        },
    }


def _trace(chain, transactions):
    return {
        "contract": LIFECYCLE_CONTRACT,
        "chain": chain,
        "program_id": WARP_PROGRAM_ID,
        "as_of": END,
        "requested_start": START,
        "lookback_seconds": END - START,
        "signature_count_in_scope": len(transactions),
        "successful_signature_count_in_scope": len(transactions),
        "failed_signature_count_in_scope": 0,
        "transaction_count": len(transactions),
        "transactions": transactions,
        "pagination_exhausted": False,
        "pagination_truncated": False,
        "reached_requested_start": True,
        "missing_block_time_count": 0,
        "first_available_slot": None,
        "first_available_block_time": None,
    }


def _traces(solana_transactions):
    return {
        "solana": _trace("solana", solana_transactions),
        "x1": _trace("x1", []),
    }


class WarpMessageIntervalRetentionTests(unittest.TestCase):
    def test_accepts_complete_short_interval_with_expected_creation(self):
        result = evaluate_warp_message_interval_retention(
            counter_closure=_counter_closure(),
            message_state=_message_state(),
            traces=_traces([_tx_row(kind="creation")]),
            requested_start=START,
            as_of=END,
        )
        self.assertEqual(result["contract"], CONTRACT)
        self.assertEqual(result["requested_start"], START)
        self.assertEqual(result["as_of"], END)
        self.assertTrue(result["program_signature_trace_complete_verified"])
        self.assertTrue(result["no_message_account_closure_observed"])
        self.assertTrue(result["no_message_account_recreation_observed"])
        self.assertTrue(result["no_ambiguous_zero_zero_lifecycle_touch"])
        self.assertTrue(result["expected_outgoing_creations_verified"])
        self.assertTrue(result["interval_retention_complete_verified"])
        self.assertTrue(result["requested_window_coverage_verified"])
        self.assertTrue(result["coverage_complete_verified"])
        self.assertTrue(result["missing_history_zero_authorized"])
        self.assertFalse(result["sixty_day_bridge_flow_retention_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_rejects_closure_inside_requested_interval(self):
        result = evaluate_warp_message_interval_retention(
            counter_closure=_counter_closure(),
            message_state=_message_state(event_time=1300),
            traces=_traces([_tx_row(kind="closure")]),
            requested_start=START,
            as_of=END,
        )
        self.assertFalse(result["no_message_account_closure_observed"])
        self.assertFalse(result["interval_retention_complete_verified"])
        self.assertFalse(result["missing_history_zero_authorized"])

    def test_rejects_recreation_of_preexisting_message(self):
        result = evaluate_warp_message_interval_retention(
            counter_closure=_counter_closure(),
            message_state=_message_state(event_time=1300),
            traces=_traces([_tx_row(kind="creation")]),
            requested_start=START,
            as_of=END,
        )
        self.assertFalse(result["no_message_account_recreation_observed"])
        self.assertFalse(result["interval_retention_complete_verified"])

    def test_rejects_ambiguous_zero_zero_touch(self):
        result = evaluate_warp_message_interval_retention(
            counter_closure=_counter_closure(),
            message_state=_message_state(event_time=1300),
            traces=_traces([_tx_row(kind="zero_zero")]),
            requested_start=START,
            as_of=END,
        )
        self.assertFalse(result["no_ambiguous_zero_zero_lifecycle_touch"])
        self.assertFalse(result["interval_retention_complete_verified"])

    def test_rejects_missing_expected_outgoing_creation(self):
        result = evaluate_warp_message_interval_retention(
            counter_closure=_counter_closure(),
            message_state=_message_state(),
            traces=_traces([]),
            requested_start=START,
            as_of=END,
        )
        self.assertFalse(result["expected_outgoing_creations_verified"])
        self.assertFalse(result["interval_retention_complete_verified"])

    def test_rejects_incomplete_program_trace(self):
        traces = _traces([_tx_row(kind="creation")])
        traces["solana"]["reached_requested_start"] = False
        result = evaluate_warp_message_interval_retention(
            counter_closure=_counter_closure(),
            message_state=_message_state(),
            traces=traces,
            requested_start=START,
            as_of=END,
        )
        self.assertFalse(result["program_signature_trace_complete_verified"])
        self.assertFalse(result["interval_retention_complete_verified"])

    def test_does_not_allow_interval_contract_to_replace_60_day_gate(self):
        with self.assertRaisesRegex(ValueError, "interval exceeds"):
            evaluate_warp_message_interval_retention(
                counter_closure=_counter_closure(),
                message_state=_message_state(),
                traces=_traces([]),
                requested_start=1,
                as_of=MAX_INTERVAL_SECONDS + 2,
            )

    def test_requires_current_counter_closure(self):
        counter = _counter_closure()
        counter["current_message_universe_count_closed"] = False
        with self.assertRaisesRegex(
            WarpMessageIntervalRetentionError,
            "current message universe is not count-closed",
        ):
            evaluate_warp_message_interval_retention(
                counter_closure=counter,
                message_state=_message_state(),
                traces=_traces([_tx_row(kind="creation")]),
                requested_start=START,
                as_of=END,
            )


if __name__ == "__main__":
    unittest.main()
