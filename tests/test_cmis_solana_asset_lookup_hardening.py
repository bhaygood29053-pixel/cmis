import unittest

from liquidity_scout.cmis.gateway import CMISGateway as BaseCMISGateway
from liquidity_scout.cmis.solana_gateway import SolanaAssetLookupMixin
from liquidity_scout.providers.solana.rpc import SPL_TOKEN_PROGRAM_ID, TOKEN_2022_PROGRAM_ID

MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


class FakeSolanaRPCProvider:
    def __init__(self, record):
        self.record = dict(record)
        self.calls = []

    def get_mint_account(self, mint):
        self.calls.append(mint)
        return dict(self.record)


def mint_record(**overrides):
    record = {
        "chain": "solana",
        "source": "solana_rpc",
        "method": "getAccountInfo(jsonParsed)",
        "mint": MINT,
        "context_slot": 123456,
        "owner_program_id": SPL_TOKEN_PROGRAM_ID,
        "parsed_program": "spl-token",
        "program_kind": "legacy_spl_token",
        "program_identity_verified": True,
        "amount_raw": "1000000",
        "decimals": 6,
        "mint_authority": None,
        "freeze_authority": None,
        "is_initialized": True,
        "extension_names": [],
        "mint_state_verified": True,
    }
    record.update(overrides)
    return record


class SolanaLookupGateway(SolanaAssetLookupMixin, BaseCMISGateway):
    pass


def lookup(record):
    provider = FakeSolanaRPCProvider(record)
    response = SolanaLookupGateway(solana_rpc_provider=provider).dispatch({
        "service": "asset_lookup",
        "chain": "solana",
        "asset": MINT,
    })
    return provider, response


class CMISSolanaAssetLookupHardeningTests(unittest.TestCase):
    def test_legacy_kind_requires_legacy_owner(self):
        provider, response = lookup(mint_record(owner_program_id=TOKEN_2022_PROGRAM_ID))
        self.assertEqual(provider.calls, [MINT])
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "solana_mint_program_contract_invalid")

    def test_program_kind_requires_matching_parsed_label(self):
        _, response = lookup(mint_record(parsed_program="spl-token-2022"))
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "solana_mint_program_contract_invalid")

    def test_unsupported_program_kind_fails_closed(self):
        _, response = lookup(mint_record(program_kind="unknown-token-program"))
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "solana_mint_program_contract_invalid")

    def test_authorities_must_be_nonempty_string_or_null(self):
        for field, value in (
            ("mint_authority", 123),
            ("mint_authority", ""),
            ("freeze_authority", False),
            ("freeze_authority", "   "),
        ):
            with self.subTest(field=field, value=value):
                _, response = lookup(mint_record(**{field: value}))
                self.assertEqual(response["status"], "error")
                self.assertEqual(response["errors"][0]["code"], "solana_mint_authority_contract_invalid")

    def test_duplicate_or_unnormalized_extensions_fail_closed(self):
        for extensions in (
            ["transferFeeConfig", "transferFeeConfig"],
            [" transferFeeConfig"],
            ["transferFeeConfig "],
            [""],
        ):
            with self.subTest(extensions=extensions):
                _, response = lookup(mint_record(extension_names=extensions))
                self.assertEqual(response["status"], "error")
                self.assertEqual(response["errors"][0]["code"], "solana_mint_extensions_invalid")

    def test_token_2022_contract_and_authorities_are_preserved(self):
        mint_authority = "11111111111111111111111111111111"
        freeze_authority = "So11111111111111111111111111111111111111112"
        _, response = lookup(mint_record(
            owner_program_id=TOKEN_2022_PROGRAM_ID,
            parsed_program="spl-token-2022",
            program_kind="token_2022",
            mint_authority=mint_authority,
            freeze_authority=freeze_authority,
            extension_names=["transferFeeConfig", "metadataPointer"],
        ))
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"]["program"]["owner_program_id"], TOKEN_2022_PROGRAM_ID)
        self.assertEqual(response["data"]["program"]["parsed_program"], "spl-token-2022")
        self.assertEqual(response["data"]["program"]["program_kind"], "token_2022")
        self.assertEqual(response["data"]["authorities"], {
            "mint_authority": mint_authority,
            "freeze_authority": freeze_authority,
        })
        self.assertEqual(response["data"]["extension_names"], ["transferFeeConfig", "metadataPointer"])


if __name__ == "__main__":
    unittest.main()
