import unittest
from decimal import Decimal

from liquidity_scout.providers.x1.routed_multi_amm_ambiguity import (
    CAUSE_DUPLICATE_REPRESENTATION,
    CAUSE_MULTIPLE_SELECTED_POOL,
    CAUSE_SELECTED_PLUS_ADDITIONAL,
    characterize_routed_multi_amm_ambiguity,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    TokenDelta,
    VerificationReport,
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
)


POOL = "Pool111"
ASSET_MINT = "AssetMint111"
COUNTER_MINT = "CounterMint111"
ASSET_VAULT = "AssetVault111"
COUNTER_VAULT = "CounterVault111"
OWNER = "Owner111"
SIGNATURE = "Sig111"


def identity_resolver(pool_address, *, rpc_url):
    return {
        "chain": "x1",
        "pool_address": pool_address,
        "asset_mint": ASSET_MINT,
        "asset_vault": ASSET_VAULT,
        "counter_mint": COUNTER_MINT,
        "counter_vault": COUNTER_VAULT,
        "shared_owner": OWNER,
        "identity_verified": True,
    }


def tx_fetcher(signature, *, rpc_url):
    return {
        "transaction": {
            "signatures": [signature],
            "message": {"instructions": []},
        },
        "meta": {"innerInstructions": []},
    }


def delta(account, mint, raw, ui):
    return TokenDelta(
        account_index=1,
        account=account,
        owner=OWNER,
        mint=mint,
        decimals=9,
        pre_amount_raw=0,
        post_amount_raw=raw,
        delta_raw=raw,
        delta_ui=Decimal(ui),
        post_ui=Decimal(ui),
    )


def verifier(transaction, *, signature, rpc_url):
    return VerificationReport(
        signature=signature,
        rpc_url=rpc_url,
        found=True,
        succeeded=True,
        slot=123,
        block_time=456,
        block_time_iso=None,
        fee_lamports=1,
        primary_signer="Signer111",
        dex_protocol="XDEX",
        xdex_amm_invoked=True,
        xendex_amm_invoked=False,
        xendex_staking_invoked=False,
        program_ids=["AMM1", "AMM2"],
        token_deltas=[
            delta(ASSET_VAULT, ASSET_MINT, -10, "-10"),
            delta(COUNTER_VAULT, COUNTER_MINT, 5, "5"),
        ],
        signer_token_deltas=[],
        signer_native_xnt_delta=None,
        signer_native_xnt_delta_before_fee=None,
        inferred_side="UNKNOWN",
        inferred_asset_mint=None,
        inferred_quote_mint=None,
        inferred_quote_amount=None,
        pool_leg_match=None,
        verification_basis="TRANSACTION_ONLY",
        inference_reason="fixture",
        expected_side=None,
        expected_mint=None,
        expectation_match=None,
        verification_level="ONCHAIN_CONFIRMED",
    )


def selected(program_id="AMM1", *, scope="outer", index=0):
    return {
        "program_id": program_id,
        "scope": scope,
        "group_index": None if scope == "outer" else 0,
        "instruction_index": index,
        "accounts": [POOL, ASSET_VAULT, COUNTER_VAULT, "Other111"],
    }


def unrelated(program_id="AMM2", *, scope="inner", index=0):
    return {
        "program_id": program_id,
        "scope": scope,
        "group_index": 0 if scope == "inner" else None,
        "instruction_index": index,
        "accounts": ["Else111", "Else222"],
    }


def membership_for(occurrences):
    selected_count = sum(
        1
        for row in occurrences
        if POOL in row["accounts"]
        and ASSET_VAULT in row["accounts"]
        and COUNTER_VAULT in row["accounts"]
    )

    def prove(**kwargs):
        return {
            "transaction_pool_membership_verified": selected_count > 0,
            "recognized_amm_instruction_count": len(occurrences),
            "selected_pool_instruction_count": selected_count,
            "selected_pool_instruction_evidence": [],
        }

    return prove


class RoutedMultiAmmAmbiguityTests(unittest.TestCase):
    def run_case(self, occurrences, *, membership_prover=None):
        if membership_prover is None:
            membership_prover = membership_for(occurrences)
        return characterize_routed_multi_amm_ambiguity(
            signature=SIGNATURE,
            pool_address=POOL,
            rpc_url="rpc",
            identity_resolver=identity_resolver,
            transaction_fetcher=tx_fetcher,
            transaction_verifier=verifier,
            membership_prover=membership_prover,
            occurrence_collector=lambda tx: list(occurrences),
        )

    def test_selected_pool_plus_unrelated_recognized_instruction_stays_blocked(self):
        occurrences = [selected(), unrelated()]
        result = self.run_case(occurrences)

        self.assertEqual(
            result["ambiguity_cause"],
            CAUSE_SELECTED_PLUS_ADDITIONAL,
        )
        self.assertEqual(
            result["recognized_amm_instruction_count_normalized"],
            2,
        )
        self.assertEqual(
            result["selected_pool_instruction_count_normalized"],
            1,
        )
        self.assertEqual(
            result["additional_recognized_instruction_count_normalized"],
            1,
        )
        self.assertTrue(result["genuine_instruction_multiplicity_observed"])
        self.assertTrue(result["exact_vault_deltas_verified"])
        self.assertFalse(
            result["duplicate_occurrence_representation_verified"]
        )
        self.assertFalse(result["classification_change_authorized"])
        self.assertTrue(result["existing_fail_closed_block_should_remain"])

    def test_multiple_selected_pool_instructions_are_not_normalized_away(self):
        occurrences = [
            selected(scope="outer", index=0),
            selected(scope="inner", index=1),
        ]
        result = self.run_case(occurrences)

        self.assertEqual(
            result["ambiguity_cause"],
            CAUSE_MULTIPLE_SELECTED_POOL,
        )
        self.assertEqual(
            result["selected_pool_instruction_count_normalized"],
            2,
        )
        self.assertFalse(
            result["duplicate_occurrence_representation_verified"]
        )
        self.assertTrue(result["existing_fail_closed_block_should_remain"])

    def test_exact_same_instruction_location_duplicate_is_diagnostic_artifact(self):
        row = selected(scope="inner", index=2)
        occurrences = [dict(row), dict(row)]
        result = self.run_case(occurrences)

        self.assertEqual(
            result["ambiguity_cause"],
            CAUSE_DUPLICATE_REPRESENTATION,
        )
        self.assertEqual(
            result["recognized_amm_instruction_count_raw"],
            2,
        )
        self.assertEqual(
            result["recognized_amm_instruction_count_normalized"],
            1,
        )
        self.assertTrue(
            result["duplicate_occurrence_representation_verified"]
        )
        self.assertFalse(result["classification_change_authorized"])
        self.assertTrue(result["existing_fail_closed_block_should_remain"])

    def test_default_collector_detects_duplicated_rpc_inner_group(self):
        instruction = {
            "programId": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
            "accounts": [POOL, ASSET_VAULT, COUNTER_VAULT],
        }

        def duplicated_group_tx(signature, *, rpc_url):
            return {
                "transaction": {
                    "signatures": [signature],
                    "message": {
                        "accountKeys": [
                            POOL,
                            ASSET_VAULT,
                            COUNTER_VAULT,
                            XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                        ],
                        "instructions": [],
                    },
                },
                "meta": {
                    "innerInstructions": [
                        {
                            "index": 4,
                            "instructions": [dict(instruction)],
                        },
                        {
                            "index": 4,
                            "instructions": [dict(instruction)],
                        },
                    ],
                },
            }

        def duplicate_membership(**kwargs):
            return {
                "transaction_pool_membership_verified": True,
                "recognized_amm_instruction_count": 2,
                "selected_pool_instruction_count": 2,
                "selected_pool_instruction_evidence": [],
            }

        result = characterize_routed_multi_amm_ambiguity(
            signature=SIGNATURE,
            pool_address=POOL,
            rpc_url="rpc",
            identity_resolver=identity_resolver,
            transaction_fetcher=duplicated_group_tx,
            transaction_verifier=verifier,
            membership_prover=duplicate_membership,
        )

        self.assertEqual(
            result["ambiguity_cause"],
            CAUSE_DUPLICATE_REPRESENTATION,
        )
        self.assertEqual(
            result["recognized_amm_instruction_count_raw"],
            2,
        )
        self.assertEqual(
            result["recognized_amm_instruction_count_normalized"],
            1,
        )
        self.assertTrue(
            result["duplicate_occurrence_representation_verified"]
        )
        self.assertEqual(
            sorted(
                row["source_group_position"]
                for row in result[
                    "recognized_amm_instruction_occurrences"
                ]
            ),
            [0, 1],
        )
        self.assertEqual(
            {
                row["parent_outer_instruction_index"]
                for row in result[
                    "recognized_amm_instruction_occurrences"
                ]
            },
            {4},
        )

    def test_membership_occurrence_count_mismatch_fails_closed(self):
        occurrences = [selected(), unrelated()]

        def bad_membership(**kwargs):
            return {
                "transaction_pool_membership_verified": True,
                "recognized_amm_instruction_count": 1,
                "selected_pool_instruction_count": 1,
            }

        with self.assertRaisesRegex(
            ValueError,
            "recognized-instruction count mismatch",
        ):
            self.run_case(
                occurrences,
                membership_prover=bad_membership,
            )


if __name__ == "__main__":
    unittest.main()
