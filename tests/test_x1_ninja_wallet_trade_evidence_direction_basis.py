from decimal import Decimal
import unittest

from liquidity_scout.providers.x1.ninja_wallet_trade_evidence import (
    X1NinjaWalletTradeEvidenceError,
    build_verified_ninja_wallet_trade_observation,
)
from liquidity_scout.providers.x1.transaction_semantics import VerificationReport


WALLET = "Wallet1111111111111111111111111111111111111"
MINT = "Mint11111111111111111111111111111111111111"
SIGNATURE = "Signature111111111111111111111111111111111"


class X1NinjaWalletTradeDirectionBasisTests(unittest.TestCase):
    def test_exact_pool_leg_confirmation_cannot_be_promoted_to_wallet_direction(self):
        report = VerificationReport(
            signature=SIGNATURE,
            rpc_url="https://rpc.mainnet.x1.xyz",
            found=True,
            succeeded=True,
            slot=123456,
            block_time=1787073600,
            block_time_iso="2026-08-18T12:00:00+00:00",
            fee_lamports=5000,
            primary_signer=WALLET,
            dex_protocol="XDEX",
            xdex_amm_invoked=True,
            xendex_amm_invoked=False,
            xendex_staking_invoked=False,
            program_ids=["recognized-xdex-program"],
            token_deltas=[],
            signer_token_deltas=[],
            signer_native_xnt_delta=Decimal("0"),
            signer_native_xnt_delta_before_fee=Decimal("0"),
            inferred_side="BUY",
            inferred_asset_mint=MINT,
            inferred_quote_mint="QuoteMint1111111111111111111111111111111111",
            inferred_quote_amount=Decimal("1"),
            pool_leg_match=None,
            verification_basis="EXACT_POOL_LEG_AMOUNTS",
            inference_reason="exact pool leg matched but signer wallet direction is unresolved",
            expected_side="BUY",
            expected_mint=MINT,
            expectation_match=True,
            verification_level="PROVIDER_SIDE_ONCHAIN_CONFIRMED",
        )

        with self.assertRaisesRegex(
            X1NinjaWalletTradeEvidenceError,
            "wallet trade direction requires signer-owned or routed wallet balance evidence",
        ):
            build_verified_ninja_wallet_trade_observation(
                trade_row={"maker": WALLET, "txHash": SIGNATURE, "type": "BUY"},
                verification_report=report,
                wallet=WALLET,
                asset_mint=MINT,
                asset_identity_verified=True,
            )


if __name__ == "__main__":
    unittest.main()
