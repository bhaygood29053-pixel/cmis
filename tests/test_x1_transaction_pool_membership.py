from decimal import Decimal
import unittest

from liquidity_scout.providers.x1.transaction_pool_membership import (
    X1TransactionPoolMembershipError,
    prove_transaction_pool_membership,
)
from liquidity_scout.providers.x1.transaction_semantics import TokenDelta, VerificationReport


ASSET_MINT = "AssetMint111"
COUNTER_MINT = "CounterMint111"
ASSET_VAULT = "AssetVault111"
COUNTER_VAULT = "CounterVault111"
POOL = "Pool111"


def _delta(account, mint, raw):
    return TokenDelta(
        account_index=1,
        account=account,
        owner="PoolOwner111",
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
        program_ids=["xdex"],
        token_deltas=[_delta(ASSET_VAULT, ASSET_MINT, 10), _delta(COUNTER_VAULT, COUNTER_MINT, -20)],
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
        "identity_verified": True,
    }
    value.update(overrides)
    return value


class TransactionPoolMembershipTests(unittest.TestCase):
    def test_both_exact_verified_vaults_mutated_proves_membership(self):
        result = prove_transaction_pool_membership(
            verification_report=_report(), pool_identity=_identity()
        )
        self.assertTrue(result["transaction_pool_membership_verified"])
        self.assertTrue(result["asset_vault_mutated"])
        self.assertTrue(result["counter_vault_mutated"])
        self.assertEqual(result["rejection_reasons"], [])
        self.assertFalse(result["cmis_promotable"])
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["provider_row_pool_claim_verified"])

    def test_single_vault_is_not_enough(self):
        result = prove_transaction_pool_membership(
            verification_report=_report(token_deltas=[_delta(ASSET_VAULT, ASSET_MINT, 10)]),
            pool_identity=_identity(),
        )
        self.assertFalse(result["transaction_pool_membership_verified"])
        self.assertIn("counter_vault_delta_missing", result["rejection_reasons"])

    def test_zero_delta_is_not_pool_mutation(self):
        result = prove_transaction_pool_membership(
            verification_report=_report(token_deltas=[_delta(ASSET_VAULT, ASSET_MINT, 0), _delta(COUNTER_VAULT, COUNTER_MINT, -20)]),
            pool_identity=_identity(),
        )
        self.assertFalse(result["transaction_pool_membership_verified"])
        self.assertIn("asset_vault_not_mutated", result["rejection_reasons"])

    def test_wrong_mint_fails_closed(self):
        result = prove_transaction_pool_membership(
            verification_report=_report(token_deltas=[_delta(ASSET_VAULT, "WrongMint", 10), _delta(COUNTER_VAULT, COUNTER_MINT, -20)]),
            pool_identity=_identity(),
        )
        self.assertFalse(result["transaction_pool_membership_verified"])
        self.assertIn("asset_vault_mint_mismatch", result["rejection_reasons"])

    def test_failed_transaction_or_missing_amm_fails_closed(self):
        failed = prove_transaction_pool_membership(
            verification_report=_report(succeeded=False), pool_identity=_identity()
        )
        self.assertIn("transaction_not_successful", failed["rejection_reasons"])
        no_amm = prove_transaction_pool_membership(
            verification_report=_report(xdex_amm_invoked=False), pool_identity=_identity()
        )
        self.assertIn("recognized_amm_not_invoked", no_amm["rejection_reasons"])

    def test_duplicate_delta_account_fails_closed(self):
        result = prove_transaction_pool_membership(
            verification_report=_report(token_deltas=[
                _delta(ASSET_VAULT, ASSET_MINT, 10),
                _delta(ASSET_VAULT, ASSET_MINT, 11),
                _delta(COUNTER_VAULT, COUNTER_MINT, -20),
            ]),
            pool_identity=_identity(),
        )
        self.assertFalse(result["transaction_pool_membership_verified"])
        self.assertIn("duplicate_token_delta_account", result["rejection_reasons"])

    def test_identity_must_be_explicitly_verified_boolean(self):
        with self.assertRaisesRegex(X1TransactionPoolMembershipError, "must be a boolean"):
            prove_transaction_pool_membership(
                verification_report=_report(), pool_identity=_identity(identity_verified="true")
            )
        with self.assertRaisesRegex(X1TransactionPoolMembershipError, "must be verified"):
            prove_transaction_pool_membership(
                verification_report=_report(), pool_identity=_identity(identity_verified=False)
            )

    def test_distinct_vaults_and_mints_required(self):
        with self.assertRaisesRegex(X1TransactionPoolMembershipError, "vault accounts must be distinct"):
            prove_transaction_pool_membership(
                verification_report=_report(), pool_identity=_identity(counter_vault=ASSET_VAULT)
            )
        with self.assertRaisesRegex(X1TransactionPoolMembershipError, "vault mints must be distinct"):
            prove_transaction_pool_membership(
                verification_report=_report(), pool_identity=_identity(counter_mint=ASSET_MINT)
            )


if __name__ == "__main__":
    unittest.main()
