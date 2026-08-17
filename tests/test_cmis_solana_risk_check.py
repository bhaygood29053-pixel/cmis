import unittest

from liquidity_scout.cmis.gateway import CMISGateway as BaseCMISGateway
from liquidity_scout.cmis.runtime_gateway import RuntimeCMISGateway
from liquidity_scout.cmis.solana_gateway import SolanaAssetLookupMixin
from liquidity_scout.cmis.solana_market_gateway import SolanaMarketReportMixin
from liquidity_scout.cmis.solana_risk_gateway import SolanaRiskCheckMixin
from liquidity_scout.cmis.solana_tokenomics_gateway import SolanaTokenomicsMixin
from liquidity_scout.providers.solana.rpc import SPL_TOKEN_PROGRAM_ID

MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
QUOTE = "So11111111111111111111111111111111111111112"
PAIR = "9wFFmGphT3QHkVbMvE8q2w4P5Y6L7N8R9S1T2U3V4W5"


class FakeRPCProvider:
    chain = "solana"

    def __init__(self, *, mint_authority=None, freeze_authority=None, supply_mint=None):
        self.mint_authority = mint_authority
        self.freeze_authority = freeze_authority
        self.supply_mint = supply_mint
        self.mint_calls = []
        self.supply_calls = []

    def get_mint_account(self, mint):
        self.mint_calls.append(mint)
        return {
            "chain": "solana",
            "source": "solana_rpc",
            "method": "getAccountInfo(jsonParsed)",
            "mint": mint,
            "context_slot": 1000,
            "owner_program_id": SPL_TOKEN_PROGRAM_ID,
            "parsed_program": "spl-token",
            "program_kind": "legacy_spl_token",
            "program_identity_verified": True,
            "amount_raw": "1000000",
            "decimals": 6,
            "mint_authority": self.mint_authority,
            "freeze_authority": self.freeze_authority,
            "is_initialized": True,
            "extension_names": [],
            "mint_state_verified": True,
        }

    def get_token_supply(self, mint):
        self.supply_calls.append(mint)
        return {
            "chain": "solana",
            "source": "solana_rpc",
            "method": "getTokenSupply",
            "mint": self.supply_mint or mint,
            "context_slot": 1001,
            "amount_raw": "1000000",
            "decimals": 6,
            "ui_amount_string": "1",
            "supply_verified": True,
            "coverage": "total_token_supply",
        }


class FakeJupiterProvider:
    chain = "solana"

    def __init__(self, price="1"):
        self.price = price
        self.calls = []

    def get_price(self, mint):
        self.calls.append(mint)
        return {
            "chain": "solana",
            "source": "jupiter_price_v3",
            "mint": mint,
            "price_available": True,
            "usd_price": self.price,
            "currency": "USD",
            "block_id": 2000,
            "decimals": 6,
            "token_created_at": None,
            "liquidity_usd_source_value": None,
            "price_change_24h_percent_source_value": None,
            "scope": "jupiter_price_v3",
            "observed_at": None,
            "freshness_verified": False,
        }


class FakeDexProvider:
    chain = "solana"

    def __init__(self, *, price="1.005", role="base"):
        self.price = price
        self.role = role
        self.calls = []

    def get_token_pairs(self, mint):
        self.calls.append(mint)
        is_base = self.role == "base"
        pair = {
            "pair_address": PAIR,
            "dex_id": "testdex",
            "base_token": {
                "address": mint if is_base else QUOTE,
                "name": "Token",
                "symbol": "TOK",
            },
            "quote_token": {
                "address": QUOTE if is_base else mint,
                "name": "Quote",
                "symbol": "Q",
            },
            "requested_mint_role": self.role,
            "price_subject_address": mint if is_base else QUOTE,
            "price_is_for_requested_mint": is_base,
            "price_usd": self.price,
            "price_native": None,
            "liquidity_usd": "1000",
            "liquidity_base": None,
            "liquidity_quote": None,
            "volume": {"h24": "100"},
            "transactions": {"h24": {"buys": 10, "sells": 5}},
            "price_change": {"h24": "1"},
            "fdv": None,
            "market_cap": None,
            "pair_created_at_ms": 1,
        }
        return {
            "chain": "solana",
            "source": "dexscreener_token_pairs_v1",
            "mint": mint,
            "pairs_available": True,
            "pairs": [pair],
            "pair_count_observed": 1,
            "scope": "pair_scoped_dexscreener_observations",
            "freshness_verified": False,
            "solana_wide_coverage_verified": False,
            "aggregate_price_selected": False,
            "aggregate_liquidity_calculated": False,
            "aggregate_volume_calculated": False,
        }


class SolanaRiskGateway(
    SolanaRiskCheckMixin,
    SolanaMarketReportMixin,
    SolanaTokenomicsMixin,
    SolanaAssetLookupMixin,
    BaseCMISGateway,
):
    pass


def gateway(*, rpc=None, jupiter=None, dex=None):
    return SolanaRiskGateway(
        solana_rpc_provider=rpc if rpc is not None else FakeRPCProvider(),
        solana_jupiter_provider=(
            jupiter if jupiter is not None else FakeJupiterProvider()
        ),
        solana_dexscreener_provider=dex if dex is not None else FakeDexProvider(),
        solana_price_max_relative_difference="0.01",
    )


def request(subject, *, params=None):
    payload = {
        "service": "risk_check",
        "chain": "solana",
        "asset": MINT,
    }
    if params is not None:
        payload["params"] = params
    return subject.dispatch(payload)


class CMISSolanaRiskCheckTests(unittest.TestCase):
    def test_runtime_composes_risk_before_solana_prerequisites(self):
        self.assertTrue(issubclass(RuntimeCMISGateway, SolanaRiskCheckMixin))
        mro = RuntimeCMISGateway.__mro__
        self.assertLess(mro.index(SolanaRiskCheckMixin), mro.index(SolanaMarketReportMixin))
        self.assertLess(mro.index(SolanaRiskCheckMixin), mro.index(SolanaTokenomicsMixin))

    def test_default_risk_is_warn_with_only_verified_supply_and_authorities(self):
        response = request(gateway())

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["asset"], {"chain": "solana", "mint": MINT})
        risk = response["risk"]
        self.assertEqual(risk["recommendation"], "WARN")
        self.assertIsNone(risk["score"])
        self.assertFalse(risk["score_verified"])
        confidence = response["confidence"]
        self.assertEqual(confidence["verified_checks"], 3)
        self.assertEqual(confidence["total_checks"], 8)
        self.assertEqual(confidence["level"], "low")
        self.assertTrue(confidence["checks"]["supply_verified"])
        self.assertTrue(confidence["checks"]["mint_authority_verified"])
        self.assertTrue(confidence["checks"]["freeze_authority_verified"])
        self.assertFalse(confidence["checks"]["liquidity_verified"])
        self.assertFalse(confidence["checks"]["volume_24h_verified"])
        self.assertFalse(confidence["checks"]["transactions_24h_verified"])
        self.assertFalse(confidence["checks"]["token_activity_verified"])
        self.assertFalse(confidence["checks"]["historical_price_verified"])
        flags = set(risk["flags"])
        self.assertIn("liquidity_unverified", flags)
        self.assertIn("volume_24h_unverified", flags)
        self.assertIn("transactions_24h_unverified", flags)
        self.assertIn("token_activity_unavailable", flags)
        self.assertIn("historical_price_unavailable", flags)

    def test_pair_scoped_liquidity_does_not_satisfy_risk_liquidity_check(self):
        response = request(gateway())
        component = response["risk"]["components"]["liquidity"]

        self.assertEqual(component["status"], "WARN")
        self.assertFalse(component["available"])
        self.assertIsNone(component["evidence"]["liquidity_usd"])
        self.assertIn("liquidity_unverified", component["flags"])

    def test_active_mint_authority_is_evaluated_by_existing_risk_core(self):
        authority = "11111111111111111111111111111111"
        rpc = FakeRPCProvider(mint_authority=authority)
        response = request(gateway(rpc=rpc))

        tokenomics = response["risk"]["components"]["tokenomics"]
        self.assertEqual(tokenomics["status"], "WARN")
        self.assertIn("mint_authority_active", tokenomics["flags"])
        self.assertEqual(tokenomics["evidence"]["mint_authority_state"], "active")

    def test_price_conflict_is_preserved_but_not_invented_as_block(self):
        dex = FakeDexProvider(price="1.5")
        response = request(gateway(dex=dex))

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["risk"]["recommendation"], "WARN")
        self.assertEqual(response["data"]["market_price_crosscheck_status"], "CONFLICT")
        self.assertIn(
            "solana_price_conflict_not_scored",
            [item["code"] for item in response["warnings"]],
        )

    def test_price_agreement_does_not_count_as_verified_risk_price(self):
        response = request(gateway())

        self.assertEqual(response["data"]["market_price_crosscheck_status"], "AGREEMENT")
        self.assertIn(
            "solana_price_agreement_not_scored",
            [item["code"] for item in response["warnings"]],
        )
        self.assertNotIn("price_verified", response["confidence"]["checks"])

    def test_market_insufficient_evidence_propagates_before_tokenomics(self):
        rpc = FakeRPCProvider()
        dex = FakeDexProvider(role="quote")
        response = request(gateway(rpc=rpc, dex=dex))

        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["data"]["upstream_service"], "market_report")
        self.assertEqual(rpc.mint_calls, [MINT])
        self.assertEqual(rpc.supply_calls, [])

    def test_wrong_supply_mint_propagates_tokenomics_error(self):
        rpc = FakeRPCProvider(supply_mint=QUOTE)
        response = request(gateway(rpc=rpc))

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["data"]["upstream_service"], "tokenomics")
        self.assertEqual(
            response["errors"][0]["code"],
            "solana_token_supply_contract_invalid",
        )

    def test_unsupported_historical_question_rejected_before_provider_calls(self):
        rpc = FakeRPCProvider()
        response = request(
            gateway(rpc=rpc),
            params={"historical_question": "price 24h ago"},
        )

        self.assertEqual(response["status"], "error")
        self.assertEqual(
            response["errors"][0]["code"],
            "solana_risk_params_not_supported",
        )
        self.assertEqual(rpc.mint_calls, [])
        self.assertEqual(rpc.supply_calls, [])

    def test_invalid_policy_shape_rejected_before_provider_calls(self):
        rpc = FakeRPCProvider()
        response = request(gateway(rpc=rpc), params={"policy": "unsafe"})

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "invalid_risk_policy")
        self.assertEqual(rpc.mint_calls, [])
        self.assertEqual(rpc.supply_calls, [])

    def test_policy_cannot_apply_liquidity_threshold_to_unverified_pair_scope(self):
        response = request(
            gateway(),
            params={"policy": {"minimum_liquidity_usd": 5000}},
        )

        liquidity = response["risk"]["components"]["liquidity"]
        self.assertEqual(liquidity["status"], "WARN")
        self.assertIn("liquidity_unverified", liquidity["flags"])
        self.assertNotIn("liquidity_below_policy_minimum", liquidity["flags"])

    def test_valid_policy_can_disable_missing_history_warning_without_faking_history(self):
        response = request(
            gateway(),
            params={"policy": {"warn_on_missing_history": False}},
        )

        history = response["risk"]["components"]["history"]
        self.assertEqual(history["status"], "PASS")
        self.assertFalse(history["available"])
        self.assertFalse(response["confidence"]["checks"]["historical_price_verified"])


if __name__ == "__main__":
    unittest.main()
