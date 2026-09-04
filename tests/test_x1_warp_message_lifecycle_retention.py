import unittest

from liquidity_scout.providers.x1.warp_message_lifecycle_retention import (
    CONTRACT,
    WarpMessageLifecycleRetentionError,
    evaluate_warp_message_lifecycle_retention,
)
from liquidity_scout.providers.x1.warp_message_retention_coverage import (
    CONTRACT as COUNTER_CLOSURE_CONTRACT,
    REQUIRED_FLOW_LOOKBACK_SECONDS,
)
from liquidity_scout.providers.x1.warp_onchain_inventory import WARP_PROGRAM_ID
from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    CONTRACT as MESSAGE_STATE_CONTRACT,
)


AS_OF = 1_800_000_000
START = AS_OF - REQUIRED_FLOW_LOOKBACK_SECONDS


def counter_closure():
    return {
        "contract": COUNTER_CLOSURE_CONTRACT,
        "counter_account_closure_verified": True,
        "current_message_universe_count_closed": True,
    }


def side(kind, chain):
    if kind == "outgoing":
        return {
            "account_type_identity_verified": True,
            "all_pda_identities_verified": True,
            "accounts": [
                {
                    "pubkey": f"{chain}-out-1",
                    "seq": 1,
                    "timestamp": START + 100,
                    "pda_identity_verified": True,
                }
            ],
        }
    return {
        "account_type_identity_verified": True,
        "all_pda_identities_verified": True,
        "accounts": [
            {
                "pubkey": f"{chain}-in-1",
                "source_seq": 1,
                "source_timestamp": START + 100,
                "executed_timestamp": START + 120,
                "pda_identity_verified": True,
            }
        ],
    }


def message_state():
    return {
        "contract": MESSAGE_STATE_CONTRACT,
        "solana": {
            "outgoing": side("outgoing", "solana"),
            "incoming": side("incoming", "solana"),
        },
        "x1": {
            "outgoing": side("outgoing", "x1"),
            "incoming": side("incoming", "x1"),
        },
    }


def tx(keys, pre, post, logs=None):
    return {
        "transaction": {
            "message": {
                "accountKeys": keys,
            }
        },
        "meta": {
            "preBalances": pre,
            "postBalances": post,
            "logMessages": logs or [],
        },
    }


def trace(chain, *, reached=True, exhausted=False, truncated=False):
    out = f"{chain}-out-1"
    incoming = f"{chain}-in-1"
    rows = [
        {
            "signature": f"{chain}-out-create",
            "slot": 10,
            "block_time": START + 101,
            "transaction": tx(
                [WARP_PROGRAM_ID, out],
                [10_000, 0],
                [10_000, 500],
                ["Program log: create OutgoingMsg"],
            ),
        },
        {
            "signature": f"{chain}-in-create",
            "slot": 11,
            "block_time": START + 121,
            "transaction": tx(
                [WARP_PROGRAM_ID, incoming],
                [10_000, 0],
                [10_000, 500],
                ["Program log: initialize IncomingMsg"],
            ),
        },
    ]
    return {
        "contract": CONTRACT,
        "chain": chain,
        "program_id": WARP_PROGRAM_ID,
        "as_of": AS_OF,
        "requested_start": START,
        "lookback_seconds": REQUIRED_FLOW_LOOKBACK_SECONDS,
        "signature_count_in_scope": len(rows),
        "successful_signature_count_in_scope": len(rows),
        "failed_signature_count_in_scope": 0,
        "transaction_count": len(rows),
        "transactions": rows,
        "pagination_exhausted": exhausted,
        "pagination_truncated": truncated,
        "reached_requested_start": reached,
        "missing_block_time_count": 0,
        "first_available_slot": 1,
        "first_available_block_time": START - 1000,
    }


def traces():
    return {
        "solana": trace("solana"),
        "x1": trace("x1"),
    }


class WarpMessageLifecycleRetentionTests(unittest.TestCase):
    def test_clean_60_day_trace_promotes_bounded_retention(self):
        result = evaluate_warp_message_lifecycle_retention(
            counter_closure=counter_closure(),
            message_state=message_state(),
            traces=traces(),
            as_of=AS_OF,
        )
        self.assertTrue(result["program_signature_trace_complete_verified"])
        self.assertTrue(result["no_message_account_closure_observed"])
        self.assertTrue(result["no_message_account_recreation_observed"])
        self.assertTrue(result["expected_outgoing_creations_verified"])
        self.assertTrue(result["retention_deletion_semantics_verified"])
        self.assertTrue(result["historical_retention_complete_verified"])
        self.assertTrue(result["requested_window_coverage_verified"])
        self.assertTrue(result["coverage_complete_verified"])
        self.assertTrue(result["missing_history_zero_authorized"])
        self.assertEqual(
            result["missing_history_zero_scope"],
            "exact_message_universe_requested_lookback_only",
        )
        self.assertFalse(result["bridged_supply_verified"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_closure_transition_blocks_retention(self):
        evidence = traces()
        evidence["x1"]["transactions"].append(
            {
                "signature": "x1-close",
                "slot": 12,
                "block_time": START + 200,
                "transaction": tx(
                    [WARP_PROGRAM_ID, "x1-out-1"],
                    [10_000, 500],
                    [10_000, 0],
                    ["Program log: close OutgoingMsg"],
                ),
            }
        )
        evidence["x1"]["transaction_count"] += 1
        evidence["x1"]["successful_signature_count_in_scope"] += 1
        result = evaluate_warp_message_lifecycle_retention(
            counter_closure=counter_closure(),
            message_state=message_state(),
            traces=evidence,
            as_of=AS_OF,
        )
        self.assertFalse(result["no_message_account_closure_observed"])
        self.assertFalse(result["retention_deletion_semantics_verified"])
        self.assertFalse(result["requested_window_coverage_verified"])

    def test_repeated_creation_blocks_retention(self):
        evidence = traces()
        evidence["solana"]["transactions"].append(
            {
                "signature": "solana-recreate",
                "slot": 13,
                "block_time": START + 300,
                "transaction": tx(
                    [WARP_PROGRAM_ID, "solana-out-1"],
                    [10_000, 0],
                    [10_000, 500],
                ),
            }
        )
        evidence["solana"]["transaction_count"] += 1
        evidence["solana"]["successful_signature_count_in_scope"] += 1
        result = evaluate_warp_message_lifecycle_retention(
            counter_closure=counter_closure(),
            message_state=message_state(),
            traces=evidence,
            as_of=AS_OF,
        )
        self.assertFalse(result["no_message_account_recreation_observed"])
        self.assertEqual(
            result["per_chain"]["solana"]["repeated_creation_pda_count"],
            1,
        )
        self.assertFalse(result["coverage_complete_verified"])

    def test_missing_expected_outgoing_creation_blocks_trace(self):
        evidence = traces()
        evidence["x1"]["transactions"] = [
            row
            for row in evidence["x1"]["transactions"]
            if row["signature"] != "x1-out-create"
        ]
        evidence["x1"]["transaction_count"] = 1
        evidence["x1"]["successful_signature_count_in_scope"] = 1
        result = evaluate_warp_message_lifecycle_retention(
            counter_closure=counter_closure(),
            message_state=message_state(),
            traces=evidence,
            as_of=AS_OF,
        )
        self.assertFalse(result["expected_outgoing_creations_verified"])
        self.assertEqual(
            result["per_chain"]["x1"][
                "missing_expected_outgoing_creation_count"
            ],
            1,
        )
        self.assertFalse(result["historical_retention_complete_verified"])

    def test_pagination_truncation_fails_closed(self):
        evidence = traces()
        evidence["solana"]["pagination_truncated"] = True
        result = evaluate_warp_message_lifecycle_retention(
            counter_closure=counter_closure(),
            message_state=message_state(),
            traces=evidence,
            as_of=AS_OF,
        )
        self.assertFalse(result["program_signature_trace_complete_verified"])
        self.assertFalse(result["requested_window_coverage_verified"])

    def test_younger_program_lifetime_can_use_archive_plus_program_creation(self):
        evidence = traces()
        for chain in ("solana", "x1"):
            evidence[chain]["reached_requested_start"] = False
            evidence[chain]["pagination_exhausted"] = True
            evidence[chain]["transactions"].insert(
                0,
                {
                    "signature": f"{chain}-program-create",
                    "slot": 2,
                    "block_time": START + 10,
                    "transaction": tx(
                        [WARP_PROGRAM_ID],
                        [0],
                        [10_000],
                        ["Program log: program create"],
                    ),
                },
            )
            evidence[chain]["transaction_count"] += 1
            evidence[chain]["successful_signature_count_in_scope"] += 1
        result = evaluate_warp_message_lifecycle_retention(
            counter_closure=counter_closure(),
            message_state=message_state(),
            traces=evidence,
            as_of=AS_OF,
        )
        self.assertTrue(
            result["per_chain"]["solana"]["program_lifetime_fallback_verified"]
        )
        self.assertTrue(
            result["per_chain"]["x1"]["program_lifetime_fallback_verified"]
        )
        self.assertTrue(result["requested_window_coverage_verified"])

    def test_unverified_counter_closure_is_rejected(self):
        prerequisite = counter_closure()
        prerequisite["counter_account_closure_verified"] = False
        with self.assertRaisesRegex(
            WarpMessageLifecycleRetentionError,
            "counter/account closure",
        ):
            evaluate_warp_message_lifecycle_retention(
                counter_closure=prerequisite,
                message_state=message_state(),
                traces=traces(),
                as_of=AS_OF,
            )


if __name__ == "__main__":
    unittest.main()
