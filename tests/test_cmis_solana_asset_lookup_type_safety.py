import unittest

from liquidity_scout.cmis.gateway import CMISGateway as BaseCMISGateway
from liquidity_scout.cmis.solana_gateway import SolanaAssetLookupMixin
from liquidity_scout.providers.solana.rpc import SPL_TOKEN_PROGRAM_ID

MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


class FakeSolanaRPCProvider:
    def get_mint_account(self, mint):
        return {
            "chain": "solana",
            "source": "solana_rpc",
            "method": "getAccountInfo(jsonParsed)",
            "mint": mint,
            "context_slot": 123456,
            "owner_program_id": SPL_TOKEN_PROGRAM_ID,
            "parsed_program": "spl-token",
            "program_kind": ["legacy_spl_token"],
            "program_identity_verified": True,
            "amount_raw": "1000000",
            "decimals": 6,
            "mint_authority": None,
            "freeze_authority": None,
            "is_initialized": True,
            "extension_names": [],
            "mint_state_verified": True,
        }


class SolanaLookupGateway(SolanaAssetLookupMixin, BaseCMISGateway):
    pass


class CMISSolanaAssetLookupTypeSafetyTests(unittest.TestCase):
    def test_unhashable_program_kind_fails_closed_instead_of_raising(self):
        response = SolanaLookupGateway(
            solana_rpc_provider=FakeSolanaRPCProvider()
        ).dispatch({
            "service": "asset_lookup",
            "chain": "solana",
            "asset": MINT,
        })

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "solana_mint_program_contract_invalid",
        )


if __name__ == "__main__":
    unittest.main()
