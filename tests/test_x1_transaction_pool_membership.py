from decimal import Decimal
import unittest

from liquidity_scout.providers.x1.transaction_pool_membership import (
    X1TransactionPoolMembershipError,
    prove_transaction_pool_membership,
)
from liquidity_scout.providers.x1.transaction_semantics import (
    TokenDelta,
    VerificationReport,
    XDEX_MAINNET_OBSERVED_PROGRAM_ID,
)


ASSET_MINT = "AssetMint111"
COUNTER_MINT = "CounterMint111"
ASSET_VAULT = "AssetVault111"
COUNTER_VAULT = "CounterVault111"
POOL = "Pool111"
POOL_OWNER = "PoolOwner111"


def _delta(account, mint, raw, *, owner=POOL_OWNER):
    return TokenDelta(
        account_index=1,
        account=account,
        owner=owner,
        mint=mint,
        decimals=9,
        pre_amount_raw=1000,
        post_amount_raw=1000 + raw,
        delta_raw=raw,
        delta_ui=Decimal(raw) / Decimal(1_000_000_000),
        post_ui=Decimal(1000 + raw) / Decimal(1_000_000_000),
    )


def _report(**overrides):
    values = dict(
        signature="Sig111",
        rpc_url="https://rpc.mainnet.x1.xyz",
        found=True,
        succeeded=True,
        slot=123,
        block_time=1,
        block_time_iso="2026-08-19T00:00:00Z",
        fee_lamports=5000,
        primary_signer="Wallet111",
        dex_protocol="XDEX",
        xdex_amm_invoked=True,
        xendex_amm_invoked=False,
        xendex_staking_invoked=False,
        program_ids=[XDEX_MAINNET_OBSERVED_PROGRAM_ID],
        token_deltas=[
            _delta(ASSET_VAULT, ASSET_MINT, 10),
            _delta(COUNTER_VAULT, COUNTER_MINT, -20),
        ],
        signer_token_deltas=[],
        signer_native_xnt_delta=None,
        signer_native_xnt_delta_before_fee=None,
        inferred_side="BUY",
        inferred_asset_mint=ASSET_MINT,
        inferred_quote_mint=COUNTER_MINT,
        inferred_quote_amount=None,
        pool_leg_match=None,
        verification_basis="SIGNER_OR_ROUTED_BALANCE_DIRECTION",
        inference_reason="fixture",
        expected_side=None,
        expected_mint=None,
        expectation_match=None,
        verification_level="ONCHAIN_ONLY",
    )
    values.update(overrides)
    return VerificationReport(**values)


def _identity(**overrides):
    value = {
        "chain": "x1",
        "pool_address": POOL,
        "asset_mint": ASSET_MINT,
        "asset_vault": ASSET_VAULT,
        "counter_mint": COUNTER_MINT,
        "counter_vault": COUNTER_VAULT,
        "shared_owner": POOL_OWNER,
        "identity_verified": True,
    }
    value.update(overrides)
    return value


def _occurrences(*, accounts=None, program_id=XDEX_MAINNET_OBSERVED_PROGRAM_ID):
    return [
        {
            "program_id": program_id,
            "scope": "outer",
            "group_index": None,
            "instruction_index": 2,
            "accounts": accounts or ["Signer111", POOL, ASSET_VAULT, COUNTER_VAULT],
        }
    ]


def _prove(*, report=None, identity=None, occurrences=None):
    return prove_transaction_pool_membership(
        verification_report=report or _report(),
        pool_identity=identity or _identity(),
        instruction_occurrences=(
            _occurrences() if occurrences is None else occurrences
        ),
    )


class TransactionPoolMembershipTests(unittest.TestCase):
    def test_exact_pool_and_both_verified_vaults_in_one_instruction_proves_membership(self):
        result = _prove()

        self.assertTrue(result["transaction_pool_membership_verified"])
        self.assertTrue(result["selected_pool_instruction_verified"])
        self.assertEqual(result["selected_pool_instruction_count"], 1)
        self.assertTrue(result["vault_authority_verified"])
        self.assertTrue(result["asset_vault_mutated"])
        self.assertTrue(result["counter_vault_mutated"])
        self.assertEqual(result["rejection_reasons"], [])
        self.assertFalse(result["cmis_promotable"])
        for field in (
            "provider_row_pool_claim_verified",
            "source_independence_verified",
            "history_completeness_verified",
            "finality_semantics_verified",
            "amount_semantics_verified",
            "price_semantics_verified",
        ):
            self.assertIsNone(result[field], field)

    def test_transaction_wide_amm_presence_does_not_prove_selected_pool(self):
        result = _prove(
            occurrences=_occurrences(
                accounts=["Signer111", "OtherPool", "OtherVaultA", "OtherVaultB"]
            )
        )

        self.assertTrue(result["recognized_amm_invoked"])
        self.assertFalse(result["selected_pool_instruction_verified"])
        self.assertFalse(result["transaction_pool_membership_verified"])
        self.assertIn(
            "selected_pool_vaults_not_coupled_in_recognized_amm_instruction",
            result["rejection_reasons"],
        )

    def test_pool_and_vaults_must_cooccur_in_same_instruction(self):
        result = _prove(
            occurrences=[
                {
                    "program_id": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                    "scope": "outer",
                    "group_index": None,
                    "instruction_index": 1,
                    "accounts": [POOL, ASSET_VAULT],
                },
                {
                    "program_id": XDEX_MAINNET_OBSERVED_PROGRAM_ID,
                    "scope": "outer",
                    "group_index": None,
                    "instruction_index": 2,
                    "accounts": [POOL, COUNTER_VAULT],
                },
            ]
        )

        self.assertFalse(result["selected_pool_instruction_verified"])
        self.assertFalse(result["transaction_pool_membership_verified"])

    def test_unrecognized_program_occurrence_does_not_prove_membership(self):
        result = _prove(occurrences=_occurrences(program_id="UnrecognizedProgram111"))
        self.assertFalse(result["selected_pool_instruction_verified"])
        self.assertFalse(result["transaction_pool_membership_verified"])

    def test_vault_authority_must_match_separately_verified_shared_owner(self):
        wrong_asset = _prove(
            report=_report(
                token_deltas=[
                    _delta(ASSET_VAULT, ASSET_MINT, 10, owner="WrongOwner111"),
                    _delta(COUNTER_VAULT, COUNTER_MINT, -20),
                ]
            )
        )
        self.assertFalse(wrong_asset["vault_authority_verified"])
        self.assertFalse(wrong_asset["transaction_pool_membership_verified"])
        self.assertIn("asset_vault_owner_mismatch", wrong_asset["rejection_reasons"])

        wrong_counter = _prove(
            report=_report(
                token_deltas=[
                    _delta(ASSET_VAULT, ASSET_MINT, 10),
                    _delta(COUNTER_VAULT, COUNTER_MINT, -20, owner="WrongOwner111"),
                ]
            )
        )
        self.assertFalse(wrong_counter["vault_authority_verified"])
        self.assertIn("counter_vault_owner_mismatch", wrong_counter["rejection_reasons"])

    def test_shared_owner_is_required(self):
        with self.assertRaisesRegex(X1TransactionPoolMembershipError, "shared_owner is required"):
            _prove(identity=_identity(shared_owner=None))

    def test_single_vault_is_not_enough(self):
        result = _prove(
            report=_report(token_deltas=[_delta(ASSET_VAULT, ASSET_MINT, 10)])
        )
        self.assertFalse(result["transaction_pool_membership_verified"])
        self.assertIn("counter_vault_delta_missing", result["rejection_reasons"])

    def test_zero_delta_is_not_pool_mutation(self):
        result = _prove(
            report=_report(
                token_deltas=[
                    _delta(ASSET_VAULT, ASSET_MINT, 0),
                    _delta(COUNTER_VAULT, COUNTER_MINT, -20),
                ]
            )
        )
        self.assertFalse(result["transaction_pool_membership_verified"])
        self.assertIn("asset_vault_not_mutated", result["rejection_reasons"])

    def test_wrong_mint_fails_closed(self):
        result = _prove(
            report=_report(
                token_deltas=[
                    _delta(ASSET_VAULT, "WrongMint", 10),
                    _delta(COUNTER_VAULT, COUNTER_MINT, -20),
                ]
            )
        )
        self.assertFalse(result["transaction_pool_membership_verified"])
        self.assertIn("asset_vault_mint_mismatch", result["rejection_reasons"])

    def test_failed_transaction_or_missing_amm_fails_closed(self):
        failed = _prove(report=_report(succeeded=False))
        self.assertIn("transaction_not_successful", failed["rejection_reasons"])

        no_amm = _prove(report=_report(xdex_amm_invoked=False))
        self.assertIn("recognized_amm_not_invoked", no_amm["rejection_reasons"])

    def test_duplicate_delta_account_fails_closed(self):
        result = _prove(
            report=_report(
                token_deltas=[
                    _delta(ASSET_VAULT, ASSET_MINT, 10),
                    _delta(ASSET_VAULT, ASSET_MINT, 11),
                    _delta(COUNTER_VAULT, COUNTER_MINT, -20),
                ]
            )
        )
        self.assertFalse(result["transaction_pool_membership_verified"])
        self.assertIn("duplicate_token_delta_account", result["rejection_reasons"])

    def test_identity_must_be_explicitly_verified_boolean(self):
        with self.assertRaisesRegex(X1TransactionPoolMembershipError, "must be a boolean"):
            _prove(identity=_identity(identity_verified="true"))
        with self.assertRaisesRegex(X1TransactionPoolMembershipError, "must be verified"):
            _prove(identity=_identity(identity_verified=False))

    def test_distinct_vaults_and_mints_required(self):
        with self.assertRaisesRegex(X1TransactionPoolMembershipError, "vault accounts must be distinct"):
            _prove(identity=_identity(counter_vault=ASSET_VAULT))
        with self.assertRaisesRegex(X1TransactionPoolMembershipError, "vault mints must be distinct"):
            _prove(identity=_identity(counter_mint=ASSET_MINT))

    def test_instruction_occurrences_must_be_a_sequence(self):
        with self.assertRaisesRegex(TypeError, "instruction_occurrences must be a sequence"):
            prove_transaction_pool_membership(
                verification_report=_report(),
                pool_identity=_identity(),
                instruction_occurrences="not-a-sequence",
            )


if __name__ == "__main__":
    unittest.main()
