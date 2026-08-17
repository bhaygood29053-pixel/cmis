import unittest

from liquidity_scout.cmis.gateway import CMISGateway as BaseCMISGateway
from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.cmis.solana_gateway import SolanaAssetLookupMixin
from liquidity_scout.providers.solana.rpc import SolanaRPCError, SolanaRPCNotFound


MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
OTHER_MINT = "So11111111111111111111111111111111111111112"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022_PROGRAM = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"


class FakeSolanaRPCProvider:
    chain = "solana"

    def __init__(self, *, record=None, error=None):
        self.record = record
        self.error = error
        self.calls = []

    def get_mint_account(self, mint):
        self.calls.append(mint)
        if self.error is not None:
            raise self.error
        if self.record is not None:
            return dict(self.record)
        return mint_record(mint)


def mint_record(
    mint=MINT,
    *,
    slot=123456,
    decimals=6,
    owner_program_id=TOKEN_PROGRAM,
    parsed_program="spl-token",
    program_kind="legacy_spl_token",
    extensions=None,
):
    return {
        "chain": "solana",
        "source": "solana_rpc",
        "method": "getAccountInfo(jsonParsed)",
        "mint": mint,
        "context_slot": slot,
        "owner_program_id": owner_program_id,
        "parsed_program": parsed_program,
        "program_kind": program_kind,
        "program_identity_verified": True,
        "amount_raw": "1000000",
        "decimals": decimals,
        "mint_authority": None,
        "freeze_authority": None,
        "is_initialized": True,
        "extension_names": list(extensions or []),
        "mint_state_verified": True,
    }


class SolanaLookupGateway(SolanaAssetLookupMixin, BaseCMISGateway):
    pass


class CMISSolanaAssetLookupTests(unittest.TestCase):
    def test_runtime_composes_solana_lookup_before_existing_gateway_layers(self):
        self.assertTrue(issubclass(RuntimeCMISGateway, SolanaAssetLookupMixin))

    def test_exact_mint_lookup_returns_canonical_identity_without_metadata_guessing(self):
        provider = FakeSolanaRPCProvider()
        gateway = SolanaLookupGateway(solana_rpc_provider=provider)

        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "solana",
            "asset": MINT,
            "params": {},
        })

        self.assertEqual(response["service"], "asset_lookup")
        self.assertEqual(response["chain"], "solana")
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["asset"], {"chain": "solana", "mint": MINT})
        self.assertEqual(response["data"]["identity_key"], f"solana:mint:{MINT}")
        self.assertEqual(response["data"]["resolution"]["input_type"], "mint")
        self.assertTrue(response["data"]["resolution"]["exact"])
        self.assertFalse(response["data"]["resolution"]["ambiguous"])
        self.assertEqual(response["data"]["program"]["program_kind"], "legacy_spl_token")
        self.assertEqual(response["data"]["decimals"], 6)
        self.assertEqual(response["data"]["metadata"]["symbol"], None)
        self.assertFalse(response["data"]["metadata"]["verified"])
        self.assertEqual(response["sources"][0]["block_slot"], 123456)
        self.assertIsNone(response["observed_at"])
        self.assertEqual(provider.calls, [MINT])

    def test_token_2022_identity_is_preserved_without_legacy_assumption(self):
        provider = FakeSolanaRPCProvider(
            record=mint_record(
                owner_program_id=TOKEN_2022_PROGRAM,
                parsed_program="spl-token-2022",
                program_kind="token_2022",
                extensions=["transferFeeConfig"],
            )
        )
        gateway = SolanaLookupGateway(solana_rpc_provider=provider)

        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "solana",
            "asset": MINT,
        })

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["data"]["program"]["program_kind"], "token_2022")
        self.assertEqual(response["data"]["extension_names"], ["transferFeeConfig"])

    def test_symbol_or_name_input_fails_closed_without_rpc_call(self):
        provider = FakeSolanaRPCProvider()
        gateway = SolanaLookupGateway(solana_rpc_provider=provider)

        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "solana",
            "asset": "JUP",
        })

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "solana_asset_lookup_requires_exact_mint",
        )
        self.assertEqual(provider.calls, [])

    def test_unconfigured_provider_remains_explicitly_unavailable(self):
        gateway = SolanaLookupGateway(solana_rpc_provider=None)

        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "solana",
            "asset": MINT,
        })

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(
            response["warnings"][0]["code"],
            "solana_rpc_provider_not_configured",
        )

    def test_not_found_is_unavailable_not_a_fabricated_asset(self):
        provider = FakeSolanaRPCProvider(error=SolanaRPCNotFound("missing"))
        gateway = SolanaLookupGateway(solana_rpc_provider=provider)

        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "solana",
            "asset": MINT,
        })

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["asset"], {})
        self.assertEqual(response["warnings"][0]["code"], "solana_mint_not_found")

    def test_wrong_mint_record_fails_identity_contract(self):
        provider = FakeSolanaRPCProvider(record=mint_record(OTHER_MINT))
        gateway = SolanaLookupGateway(solana_rpc_provider=provider)

        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "solana",
            "asset": MINT,
        })

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "solana_mint_identity_contract_invalid",
        )
        self.assertEqual(response["asset"], {})

    def test_provider_exception_text_is_not_reflected_to_caller(self):
        secret = "https://keyed-rpc.invalid/?api-key=SECRET"
        for error in (
            SolanaRPCError(f"provider failed at {secret}"),
            RuntimeError(f"unexpected provider failure at {secret}"),
        ):
            with self.subTest(error=type(error).__name__):
                provider = FakeSolanaRPCProvider(error=error)
                gateway = SolanaLookupGateway(solana_rpc_provider=provider)
                response = gateway.dispatch({
                    "service": "asset_lookup",
                    "chain": "solana",
                    "asset": MINT,
                })
                self.assertEqual(response["status"], "unavailable")
                self.assertNotIn(secret, str(response))

    def test_nonempty_params_are_rejected_before_rpc(self):
        provider = FakeSolanaRPCProvider()
        gateway = SolanaLookupGateway(solana_rpc_provider=provider)

        response = gateway.dispatch({
            "service": "asset_lookup",
            "chain": "solana",
            "asset": MINT,
            "params": {"symbol": "USDC"},
        })

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "solana_asset_lookup_params_not_supported",
        )
        self.assertEqual(provider.calls, [])

    def test_other_solana_services_stay_unavailable_and_never_fall_back_to_x1(self):
        provider = FakeSolanaRPCProvider()
        gateway = SolanaLookupGateway(solana_rpc_provider=provider)

        response = gateway.dispatch({
            "service": "market_report",
            "chain": "solana",
            "asset": MINT,
        })

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["chain"], "solana")
        self.assertEqual(
            response["warnings"][0]["code"],
            "chain_provider_not_implemented",
        )
        self.assertEqual(provider.calls, [])


if __name__ == "__main__":
    unittest.main()
