import unittest

from liquidity_scout.providers.x1.warp_message_retention_coverage import (
    CONTRACT,
    REQUIRED_FLOW_LOOKBACK_SECONDS,
    WarpMessageRetentionCoverageError,
    evaluate_warp_message_counter_closure,
)
from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    CONTRACT as MESSAGE_STATE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_semantic_layout_discovery import (
    CONTRACT as LAYOUT_CONTRACT,
)


def official_config(sol_out=2, sol_in=3, x1_out=3, x1_in=2):
    return {
        "solana": {
            "config": {
                "programId": "6JbPTuxVuoTgyQeXFb9MH8C8nUY8NBbLP1Lu4B13JfMD",
                "outSeqCounter": str(sol_out),
                "inSeqCounter": str(sol_in),
            }
        },
        "x1": {
            "config": {
                "programId": "6JbPTuxVuoTgyQeXFb9MH8C8nUY8NBbLP1Lu4B13JfMD",
                "outSeqCounter": str(x1_out),
                "inSeqCounter": str(x1_in),
            }
        },
    }


def config_account(chain, out_count, in_count):
    return {
        "contract": LAYOUT_CONTRACT,
        "chain": chain,
        "account_name": "Config",
        "account_type_identity_verified": True,
        "pda_identity_verified": True,
        "decoded_fields": {
            "out_seq_counter_candidate": out_count,
            "in_seq_counter_candidate": in_count,
        },
    }


def classified_configs(sol_out=2, sol_in=3, x1_out=3, x1_in=2):
    return {
        "solana": config_account("solana", sol_out, sol_in),
        "x1": config_account("x1", x1_out, x1_in),
    }


def side(kind, count, start=1_700_000_000):
    key = "seq" if kind == "outgoing" else "source_seq"
    ts = "timestamp" if kind == "outgoing" else "source_timestamp"
    rows = [
        {
            key: index + 1,
            ts: start + index,
        }
        for index in range(count)
    ]
    return {
        "account_type_identity_verified": True,
        "all_pda_identities_verified": True,
        "decoded_account_count": count,
        "accounts": rows,
    }


def message_state(sol_out=2, sol_in=3, x1_out=3, x1_in=2):
    return {
        "contract": MESSAGE_STATE_CONTRACT,
        "solana": {
            "outgoing": side("outgoing", sol_out, 1_700_000_000),
            "incoming": side("incoming", sol_in, 1_700_000_100),
        },
        "x1": {
            "outgoing": side("outgoing", x1_out, 1_700_000_200),
            "incoming": side("incoming", x1_in, 1_700_000_300),
        },
    }


class WarpMessageRetentionCoverageTests(unittest.TestCase):
    def test_exact_three_way_counter_closure_is_verified_but_retention_is_not(self):
        result = evaluate_warp_message_counter_closure(
            config_response=official_config(),
            classified_configs=classified_configs(),
            message_state=message_state(),
        )
        self.assertEqual(result["contract"], CONTRACT)
        self.assertTrue(result["official_onchain_counter_values_match"])
        self.assertTrue(result["counter_account_closure_verified"])
        self.assertTrue(result["current_message_universe_count_closed"])
        self.assertFalse(result["retention_deletion_semantics_verified"])
        self.assertFalse(result["historical_retention_complete_verified"])
        self.assertFalse(result["requested_window_coverage_verified"])
        self.assertFalse(result["coverage_complete_verified"])
        self.assertFalse(result["missing_history_zero_authorized"])
        self.assertEqual(
            result["required_flow_lookback_seconds"],
            REQUIRED_FLOW_LOOKBACK_SECONDS,
        )
        self.assertFalse(result["execution_authorized"])

    def test_official_vs_onchain_counter_disagreement_prevents_closure(self):
        result = evaluate_warp_message_counter_closure(
            config_response=official_config(sol_out=3),
            classified_configs=classified_configs(sol_out=2),
            message_state=message_state(sol_out=2),
        )
        self.assertFalse(result["official_onchain_counter_values_match"])
        self.assertFalse(result["counter_account_closure_verified"])

    def test_counter_vs_account_count_disagreement_prevents_closure(self):
        result = evaluate_warp_message_counter_closure(
            config_response=official_config(sol_out=2),
            classified_configs=classified_configs(sol_out=2),
            message_state=message_state(sol_out=1),
        )
        self.assertTrue(result["official_onchain_counter_values_match"])
        self.assertFalse(result["counter_account_closure_verified"])
        self.assertFalse(
            result["per_chain"]["solana"][
                "outgoing_counter_matches_account_count"
            ]
        )

    def test_duplicate_sequence_fails_closed(self):
        state = message_state()
        state["solana"]["outgoing"]["accounts"][1]["seq"] = 1
        with self.assertRaisesRegex(
            WarpMessageRetentionCoverageError, "duplicate sequence"
        ):
            evaluate_warp_message_counter_closure(
                config_response=official_config(),
                classified_configs=classified_configs(),
                message_state=state,
            )

    def test_unverified_pda_universe_fails_closed(self):
        state = message_state()
        state["x1"]["incoming"]["all_pda_identities_verified"] = False
        with self.assertRaisesRegex(
            WarpMessageRetentionCoverageError, "PDA identities"
        ):
            evaluate_warp_message_counter_closure(
                config_response=official_config(),
                classified_configs=classified_configs(),
                message_state=state,
            )

    def test_wrong_program_id_fails_closed(self):
        config = official_config()
        config["x1"]["config"]["programId"] = "11111111111111111111111111111111"
        with self.assertRaisesRegex(
            WarpMessageRetentionCoverageError, "exact Warp"
        ):
            evaluate_warp_message_counter_closure(
                config_response=config,
                classified_configs=classified_configs(),
                message_state=message_state(),
            )


if __name__ == "__main__":
    unittest.main()
