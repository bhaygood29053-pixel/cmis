from decimal import Decimal
import unittest

from liquidity_scout.providers.x1.ninja_wallet_trade_evidence import (
    CONFIRMED_LEVEL,
    EVIDENCE_SCOPE,
    SOURCE,
    VERIFICATION_METHOD,
    X1NinjaWalletTradeEvidenceError,
    build_verified_ninja_wallet_trade_observation,
)
from liquidity_scout.providers.x1.transaction_semantics import VerificationReport


WALLET = "Wallet1111111111111111111111111111111111111"
MINT = "Mint11111111111111111111111111111111111111"
SIGNATURE = "Signature111111111111111111111111111111111"


def _row(**overrides):
    row = {
        "maker": WALLET,
        "txHash": SIGNATURE,
        "type": "BUY",
        # These provider fields are intentionally untrusted by this adapter.
        "amountToken": "999999999",
        "amountNative": "888888888",
        "amountUsd": "777777777",
        "timestamp": "1900-01-01T00:00:00Z",
        "slot": -999,
    }
    row.update(overrides)
    return row


def _report(**overrides):
    values = {
        "signature": SIGNATURE,
        "rpc_url": "https://rpc.mainnet.x1.xyz",
        "found": True,
        "succeeded": True,
        "slot": 123456,
        "block_time": 1787073600,
        "block_time_iso": "2026-08-18T12:00:00+00:00",
        "fee_lamports": 5000,
        "primary_signer": WALLET,
        "dex_protocol": "XDEX",
        "xdex_amm_invoked": True,
        "xendex_amm_invoked": False,
        "xendex_staking_invoked": False,
        "program_ids": ["recognized-xdex-program"],
        "token_deltas": [],
        "signer_token_deltas": [],
        "signer_native_xnt_delta": Decimal("-1"),
        "signer_native_xnt_delta_before_fee": Decimal("-0.999995"),
        "inferred_side": "BUY",
        "inferred_asset_mint": MINT,
        "inferred_quote_mint": None,
        "inferred_quote_amount": None,
        "pool_leg_match": None,
        "verification_basis": "SIGNER_OR_ROUTED_BALANCE_DIRECTION",
        "inference_reason": "deterministic fixture",
        "expected_side": "BUY",
        "expected_mint": MINT,
        "expectation_match": True,
        "verification_level": CONFIRMED_LEVEL,
    }
    values.update(overrides)
    return VerificationReport(**values)


class X1NinjaWalletTradeEvidenceTests(unittest.TestCase):
    def test_confirmed_buy_builds_one_bounded_wallet_fact(self):
        observation = build_verified_ninja_wallet_trade_observation(
            trade_row=_row(),
            verification_report=_report(),
            wallet=WALLET,
            asset_mint=MINT,
            asset_identity_verified=True,
        )

        self.assertEqual(observation["chain"], "x1")
        self.assertEqual(observation["wallet"], WALLET)
        self.assertEqual(observation["activity_type"], "BUY")
        self.assertEqual(observation["transaction_signature"], SIGNATURE)
        self.assertEqual(observation["asset_id"], MINT)
        self.assertEqual(observation["block_slot"], 123456)
        self.assertEqual(observation["observed_at"], "2026-08-18T12:00:00Z")
        self.assertEqual(observation["source"], SOURCE)
        self.assertEqual(observation["verification_method"], VERIFICATION_METHOD)
        self.assertEqual(observation["evidence_scope"], EVIDENCE_SCOPE)

        verification = observation["verification"]
        self.assertTrue(verification["wallet_identity_verified"])
        self.assertTrue(verification["asset_identity_verified"])
        self.assertTrue(verification["transaction_identity_verified"])
        self.assertTrue(verification["trade_direction_verified"])
        self.assertFalse(verification["amount_verified"])
        self.assertFalse(verification["quote_value_verified"])

        self.assertIsNone(observation["asset_amount"])
        self.assertIsNone(observation["asset_unit"])
        self.assertIsNone(observation["quote_value"])
        self.assertIsNone(observation["quote_unit"])
        self.assertFalse(observation["classification_authorized"])
        self.assertFalse(observation["complete_wallet_history_proven"])
        self.assertIn("single_transaction_fact_only", observation["limitations"])
        self.assertIn("complete_wallet_history_not_proven", observation["limitations"])

        # Provider amount/timestamp/slot fields must not leak into the wallet fact.
        serialized = str(observation)
        self.assertNotIn("999999999", serialized)
        self.assertNotIn("888888888", serialized)
        self.assertNotIn("777777777", serialized)
        self.assertNotIn("1900-01-01", serialized)
        self.assertNotEqual(observation["block_slot"], -999)

    def test_confirmed_sell_builds_sell_fact(self):
        observation = build_verified_ninja_wallet_trade_observation(
            trade_row=_row(type="sell"),
            verification_report=_report(
                inferred_side="SELL",
                expected_side="SELL",
                signer_native_xnt_delta=Decimal("1"),
                signer_native_xnt_delta_before_fee=Decimal("1.000005"),
            ),
            wallet=WALLET,
            asset_mint=MINT,
            asset_identity_verified=True,
        )
        self.assertEqual(observation["activity_type"], "SELL")
        self.assertTrue(observation["verification"]["trade_direction_verified"])

    def test_requires_mapping_row_and_verification_report_type(self):
        with self.assertRaisesRegex(TypeError, "trade_row must be a mapping"):
            build_verified_ninja_wallet_trade_observation(
                trade_row=[],
                verification_report=_report(),
                wallet=WALLET,
                asset_mint=MINT,
                asset_identity_verified=True,
            )
        with self.assertRaisesRegex(TypeError, "VerificationReport"):
            build_verified_ninja_wallet_trade_observation(
                trade_row=_row(),
                verification_report={},
                wallet=WALLET,
                asset_mint=MINT,
                asset_identity_verified=True,
            )

    def test_asset_identity_flag_is_strict_and_required(self):
        for value in (False, "true", 1, None):
            with self.subTest(value=value):
                with self.assertRaises(X1NinjaWalletTradeEvidenceError):
                    build_verified_ninja_wallet_trade_observation(
                        trade_row=_row(),
                        verification_report=_report(),
                        wallet=WALLET,
                        asset_mint=MINT,
                        asset_identity_verified=value,
                    )

    def test_maker_must_match_requested_wallet(self):
        with self.assertRaisesRegex(X1NinjaWalletTradeEvidenceError, "maker"):
            build_verified_ninja_wallet_trade_observation(
                trade_row=_row(maker="OtherWallet"),
                verification_report=_report(),
                wallet=WALLET,
                asset_mint=MINT,
                asset_identity_verified=True,
            )

    def test_txhash_must_match_verified_rpc_signature(self):
        with self.assertRaisesRegex(X1NinjaWalletTradeEvidenceError, "txHash"):
            build_verified_ninja_wallet_trade_observation(
                trade_row=_row(txHash="OtherSignature"),
                verification_report=_report(),
                wallet=WALLET,
                asset_mint=MINT,
                asset_identity_verified=True,
            )

    def test_primary_signer_must_match_wallet(self):
        with self.assertRaisesRegex(X1NinjaWalletTradeEvidenceError, "primary signer"):
            build_verified_ninja_wallet_trade_observation(
                trade_row=_row(),
                verification_report=_report(primary_signer="OtherWallet"),
                wallet=WALLET,
                asset_mint=MINT,
                asset_identity_verified=True,
            )

    def test_transaction_must_be_found_successful_and_recognized_dex(self):
        cases = (
            ({"found": False}, "found and successful"),
            ({"succeeded": False}, "found and successful"),
            (
                {"xdex_amm_invoked": False, "xendex_amm_invoked": False},
                "recognized XDEX/XenDEX",
            ),
        )
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(X1NinjaWalletTradeEvidenceError, message):
                    build_verified_ninja_wallet_trade_observation(
                        trade_row=_row(),
                        verification_report=_report(**overrides),
                        wallet=WALLET,
                        asset_mint=MINT,
                        asset_identity_verified=True,
                    )

    def test_weaker_or_unresolved_provider_side_evidence_is_rejected(self):
        for level in (
            "PROVIDER_SIDE_ONCHAIN_SUPPORTED",
            "PROVIDER_SIDE_ONCHAIN_UNRESOLVED",
            "DEX_ONCHAIN_CONFIRMED",
        ):
            with self.subTest(level=level):
                with self.assertRaisesRegex(
                    X1NinjaWalletTradeEvidenceError,
                    "not deterministically on-chain confirmed",
                ):
                    build_verified_ninja_wallet_trade_observation(
                        trade_row=_row(),
                        verification_report=_report(verification_level=level),
                        wallet=WALLET,
                        asset_mint=MINT,
                        asset_identity_verified=True,
                    )

    def test_expectation_side_and_inferred_side_must_all_agree(self):
        cases = (
            ({"expectation_match": False}, "expectation"),
            ({"expectation_match": None}, "expectation"),
            ({"expected_side": "SELL"}, "expected side"),
            ({"inferred_side": "SELL"}, "on-chain side"),
        )
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(X1NinjaWalletTradeEvidenceError, message):
                    build_verified_ninja_wallet_trade_observation(
                        trade_row=_row(),
                        verification_report=_report(**overrides),
                        wallet=WALLET,
                        asset_mint=MINT,
                        asset_identity_verified=True,
                    )

    def test_expected_and_inferred_mint_must_match_exact_asset_mint(self):
        for overrides, message in (
            ({"expected_mint": "OtherMint"}, "expected mint"),
            ({"inferred_asset_mint": "OtherMint"}, "on-chain asset mint"),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(X1NinjaWalletTradeEvidenceError, message):
                    build_verified_ninja_wallet_trade_observation(
                        trade_row=_row(),
                        verification_report=_report(**overrides),
                        wallet=WALLET,
                        asset_mint=MINT,
                        asset_identity_verified=True,
                    )

    def test_only_buy_sell_rows_are_eligible(self):
        for trade_type in ("LP_ADD", "TRANSFER", "", None):
            with self.subTest(trade_type=trade_type):
                with self.assertRaises(X1NinjaWalletTradeEvidenceError):
                    build_verified_ninja_wallet_trade_observation(
                        trade_row=_row(type=trade_type),
                        verification_report=_report(),
                        wallet=WALLET,
                        asset_mint=MINT,
                        asset_identity_verified=True,
                    )

    def test_rpc_block_time_and_slot_are_required(self):
        for overrides in (
            {"block_time_iso": None},
            {"slot": None},
            {"slot": True},
            {"slot": -1},
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaises(X1NinjaWalletTradeEvidenceError):
                    build_verified_ninja_wallet_trade_observation(
                        trade_row=_row(),
                        verification_report=_report(**overrides),
                        wallet=WALLET,
                        asset_mint=MINT,
                        asset_identity_verified=True,
                    )


if __name__ == "__main__":
    unittest.main()
