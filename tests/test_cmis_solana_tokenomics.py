import unittest

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT
from liquidity_scout.cmis.gateway import CMISGateway as BaseCMISGateway
from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.cmis.solana_gateway import SolanaAssetLookupMixin
from liquidity_scout.cmis.solana_tokenomics_gateway import SolanaTokenomicsMixin
from liquidity_scout.providers.solana.helius import HeliusSourceError
from liquidity_scout.providers.solana.rpc import (
    SPL_TOKEN_PROGRAM_ID,
    TOKEN_2022_PROGRAM_ID,
    SolanaRPCError,
)

MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
OTHER_MINT = "So11111111111111111111111111111111111111112"


class FakeSolanaRPCProvider:
    chain = "solana"

    def __init__(self, *, supply_raw="1234500", decimals=6, supply_error=None, mint_record=None):
        self.supply_raw = supply_raw
        self.decimals = decimals
        self.supply_error = supply_error
        self.mint_record = mint_record
        self.mint_calls = []
        self.supply_calls = []

    def get_mint_account(self, mint):
        self.mint_calls.append(mint)
        if self.mint_record is not None:
            return dict(self.mint_record)
        return canonical_mint_record(mint=mint, decimals=self.decimals)

    def get_token_supply(self, mint):
        self.supply_calls.append(mint)
        if self.supply_error is not None:
            raise self.supply_error
        return {
            "chain": "solana",
            "source": "solana_rpc",
            "method": "getTokenSupply",
            "mint": mint,
            "context_slot": 1000,
            "amount_raw": self.supply_raw,
            "decimals": self.decimals,
            "ui_amount_string": None,
            "supply_verified": True,
            "coverage": "total_token_supply",
        }


class FakeHeliusProvider:
    chain = "solana"

    def __init__(self, *, supply=1234500, decimals=6, slot=995, error=None):
        self.supply = supply
        self.decimals = decimals
        self.slot = slot
        self.error = error
        self.calls = []

    def get_asset(self, mint):
        self.calls.append(mint)
        if self.error is not None:
            raise self.error
        return {
            "chain": "solana",
            "source": "helius_das",
            "mint": mint,
            "asset_available": True,
            "identity_verified": True,
            "last_indexed_slot": self.slot,
            "indexed_supply_candidate": self.supply,
            "supply_unit": "TOKEN_BASE_UNITS",
            "supply_semantics_verified": True,
            "decimals": self.decimals,
        }


def canonical_mint_record(
    *,
    mint=MINT,
    decimals=6,
    mint_authority=None,
    freeze_authority=None,
    token_2022=False,
):
    return {
        "chain": "solana",
        "source": "solana_rpc",
        "method": "getAccountInfo(jsonParsed)",
        "mint": mint,
        "context_slot": 999,
        "owner_program_id": TOKEN_2022_PROGRAM_ID if token_2022 else SPL_TOKEN_PROGRAM_ID,
        "parsed_program": "spl-token-2022" if token_2022 else "spl-token",
        "program_kind": "token_2022" if token_2022 else "legacy_spl_token",
        "program_identity_verified": True,
        "amount_raw": "1234500",
        "decimals": decimals,
        "mint_authority": mint_authority,
        "freeze_authority": freeze_authority,
        "is_initialized": True,
        "extension_names": ["transferFeeConfig"] if token_2022 else [],
        "mint_state_verified": True,
    }


class SolanaTokenomicsGateway(
    SolanaTokenomicsMixin,
    SolanaAssetLookupMixin,
    BaseCMISGateway,
):
    pass


def request(gateway, *, asset=MINT, params=None):
    payload = {
        "service": "tokenomics",
        "chain": "solana",
        "asset": asset,
    }
    if params is not None:
        payload["params"] = params
    return gateway.dispatch(payload)


class CMISSolanaTokenomicsTests(unittest.TestCase):
    def test_runtime_composes_tokenomics_before_asset_lookup(self):
        self.assertTrue(issubclass(RuntimeCMISGateway, SolanaTokenomicsMixin))
        mro = RuntimeCMISGateway.__mro__
        self.assertLess(mro.index(SolanaTokenomicsMixin), mro.index(SolanaAssetLookupMixin))

    def test_canonical_rpc_supply_and_authorities_are_partial_verified_tokenomics(self):
        rpc = FakeSolanaRPCProvider()
        gateway = SolanaTokenomicsGateway(solana_rpc_provider=rpc)

        response = request(gateway)

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["asset"], {"chain": "solana", "mint": MINT})
        self.assertTrue(response["data"]["supply_verified"])
        self.assertEqual(response["data"]["total_supply_raw"], "1234500")
        self.assertEqual(response["data"]["total_supply"], "1.2345")
        self.assertEqual(response["data"]["decimals"], 6)
        self.assertIsNone(response["data"]["circulating_supply"])
        self.assertFalse(response["data"]["circulating_supply_verified"])
        self.assertIsNone(response["data"]["maximum_supply"])
        self.assertFalse(response["data"]["maximum_supply_verified"])
        self.assertEqual(response["data"]["mint_authority_status"], "revoked")
        self.assertEqual(response["data"]["freeze_authority_status"], "none")
        self.assertEqual(response["confidence"]["verified_checks"], 4)
        self.assertEqual(response["confidence"]["total_checks"], 6)
        self.assertEqual(response["data"]["supply_crosscheck"]["status"], "unavailable")
        self.assertEqual(rpc.mint_calls, [MINT])
        self.assertEqual(rpc.supply_calls, [MINT])

    def test_explicit_zero_supply_remains_verified_zero(self):
        rpc = FakeSolanaRPCProvider(supply_raw="0")
        response = request(SolanaTokenomicsGateway(solana_rpc_provider=rpc))

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["data"]["total_supply_raw"], "0")
        self.assertEqual(response["data"]["total_supply"], "0")
        self.assertTrue(response["data"]["supply_verified"])

    def test_token_2022_program_and_extensions_are_preserved(self):
        mint_authority = "11111111111111111111111111111111"
        record = canonical_mint_record(
            token_2022=True,
            mint_authority=mint_authority,
        )
        rpc = FakeSolanaRPCProvider(mint_record=record)
        response = request(SolanaTokenomicsGateway(solana_rpc_provider=rpc))

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["data"]["program"]["program_kind"], "token_2022")
        self.assertEqual(response["data"]["extension_names"], ["transferFeeConfig"])
        self.assertEqual(response["data"]["mint_authority"], mint_authority)
        self.assertEqual(response["data"]["mint_authority_status"], "active")

    def test_symbol_input_fails_closed_before_supply_lookup(self):
        rpc = FakeSolanaRPCProvider()
        response = request(SolanaTokenomicsGateway(solana_rpc_provider=rpc), asset="USDC")

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["data"]["upstream_service"], "asset_lookup")
        self.assertEqual(rpc.mint_calls, [])
        self.assertEqual(rpc.supply_calls, [])

    def test_nonempty_params_fail_before_provider_calls(self):
        rpc = FakeSolanaRPCProvider()
        response = request(
            SolanaTokenomicsGateway(solana_rpc_provider=rpc),
            params={"max_index_slot_lag": 10},
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "solana_tokenomics_params_not_supported")
        self.assertEqual(rpc.mint_calls, [])
        self.assertEqual(rpc.supply_calls, [])

    def test_canonical_mint_and_supply_decimals_conflict_fails_closed(self):
        record = canonical_mint_record(decimals=6)
        rpc = FakeSolanaRPCProvider(decimals=9, mint_record=record)
        response = request(SolanaTokenomicsGateway(solana_rpc_provider=rpc))

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "solana_tokenomics_decimals_conflict")

    def test_wrong_supply_mint_contract_fails_closed(self):
        class WrongMintRPC(FakeSolanaRPCProvider):
            def get_token_supply(self, mint):
                record = super().get_token_supply(mint)
                record["mint"] = OTHER_MINT
                return record

        response = request(SolanaTokenomicsGateway(solana_rpc_provider=WrongMintRPC()))
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "solana_token_supply_contract_invalid")

    def test_supply_provider_exception_text_is_not_reflected(self):
        secret = "https://rpc.invalid/?api-key=SECRET"
        rpc = FakeSolanaRPCProvider(supply_error=SolanaRPCError(f"failed at {secret}"))
        response = request(SolanaTokenomicsGateway(solana_rpc_provider=rpc))

        self.assertEqual(response["status"], "unavailable")
        self.assertNotIn(secret, str(response))

    def test_helius_is_not_queried_without_explicit_slot_lag_policy(self):
        rpc = FakeSolanaRPCProvider()
        helius = FakeHeliusProvider()
        gateway = SolanaTokenomicsGateway(
            solana_rpc_provider=rpc,
            solana_helius_provider=helius,
        )
        response = request(gateway)

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["data"]["supply_crosscheck"]["status"], "unavailable")
        self.assertEqual(response["data"]["supply_crosscheck"]["reason"], "max_index_slot_lag_not_configured")
        self.assertEqual(helius.calls, [])

    def test_helius_agreement_is_preserved_without_promoting_absolute_freshness(self):
        rpc = FakeSolanaRPCProvider()
        helius = FakeHeliusProvider(supply=1234500, decimals=6, slot=995)
        gateway = SolanaTokenomicsGateway(
            solana_rpc_provider=rpc,
            solana_helius_provider=helius,
            solana_supply_max_index_slot_lag=10,
        )
        response = request(gateway)

        crosscheck = response["data"]["supply_crosscheck"]
        self.assertEqual(response["status"], "partial")
        self.assertEqual(crosscheck["status"], AGREEMENT)
        self.assertTrue(crosscheck["supply_match"])
        self.assertFalse(crosscheck["freshness_verified"])
        self.assertFalse(crosscheck["cmis_promotable"])
        self.assertEqual(helius.calls, [MINT])

    def test_helius_conflict_is_visible_but_does_not_replace_canonical_supply(self):
        rpc = FakeSolanaRPCProvider()
        helius = FakeHeliusProvider(supply=999, decimals=6, slot=995)
        gateway = SolanaTokenomicsGateway(
            solana_rpc_provider=rpc,
            solana_helius_provider=helius,
            solana_supply_max_index_slot_lag=10,
        )
        response = request(gateway)

        self.assertEqual(response["data"]["total_supply_raw"], "1234500")
        self.assertEqual(response["data"]["supply_crosscheck"]["status"], CONFLICT)
        self.assertIn("solana_supply_crosscheck_conflict", [item["code"] for item in response["warnings"]])

    def test_helius_exception_text_is_not_reflected(self):
        secret = "https://helius.invalid/?api-key=SECRET"
        rpc = FakeSolanaRPCProvider()
        helius = FakeHeliusProvider(error=HeliusSourceError(f"failed at {secret}"))
        gateway = SolanaTokenomicsGateway(
            solana_rpc_provider=rpc,
            solana_helius_provider=helius,
            solana_supply_max_index_slot_lag=10,
        )
        response = request(gateway)

        self.assertEqual(response["status"], "partial")
        self.assertNotIn(secret, str(response))
        self.assertEqual(response["data"]["supply_crosscheck"]["status"], "unavailable")

    def test_invalid_slot_lag_configuration_is_rejected(self):
        for value in (-1, True, "10"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    SolanaTokenomicsGateway(
                        solana_rpc_provider=FakeSolanaRPCProvider(),
                        solana_supply_max_index_slot_lag=value,
                    )


if __name__ == "__main__":
    unittest.main()
