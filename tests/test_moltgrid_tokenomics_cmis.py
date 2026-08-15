import unittest
from types import SimpleNamespace
from unittest.mock import patch

from liquidity_scout.integrations import moltgrid
from liquidity_scout.integrations.moltgrid_asset_cmis import (
    build_cmis_asset_request,
    cmis_asset_service,
    format_cmis_asset_answer,
)
from liquidity_scout.integrations.moltgrid_tokenomics_cmis import (
    build_cmis_tokenomics_request,
    wants_cmis_tokenomics,
)


class FakeGateway:
    def __init__(self, response=None):
        self.requests = []
        self.response = response or self.partial_response()

    @staticmethod
    def partial_response():
        return {
            "service": "tokenomics",
            "chain": "x1",
            "status": "partial",
            "asset": {
                "symbol": "XNT",
                "name": "Wrapped XNT",
                "mint": "MintXNT",
            },
            "data": {
                "mint": "MintXNT",
                "symbol": "XNT",
                "name": "Wrapped XNT",
                "current_total_supply": "1000000.5",
                "raw_supply": "1000000500000",
                "decimals": 6,
                "supply_verified": True,
                "rpc_decimals_consistent": True,
                "mint_authority": None,
                "mint_authority_verified": True,
                "mint_authority_state": "revoked",
                "freeze_authority": None,
                "freeze_authority_verified": True,
                "freeze_authority_state": "none",
                "future_minting_possible": False,
                "circulating_supply": None,
                "circulating_supply_verified": False,
                "maximum_supply": None,
                "maximum_supply_verified": False,
                "token_activity": {
                    "available": False,
                    "activity_verified": False,
                    "mint_events_observed": None,
                    "burn_events_observed": None,
                    "net_issuance_verified": False,
                    "net_issuance_tokens": None,
                    "coverage_scope": None,
                    "lifetime_coverage_verified": False,
                },
            },
            "risk": None,
            "confidence": {
                "complete": False,
                "verified_checks": 3,
                "total_checks": 4,
            },
            "sources": [
                {
                    "source": "X1 RPC getTokenSupply",
                    "role": "tokenomics.current_supply",
                },
                {
                    "source": "X1 RPC getAccountInfo(jsonParsed)",
                    "role": "tokenomics.mint_account",
                },
            ],
            "observed_at": None,
            "warnings": [
                {"code": "token_activity_not_supplied"},
                {
                    "code": "circulating_supply_unverified",
                    "message": "Circulating supply is not independently verified by this service.",
                },
                {
                    "code": "maximum_supply_unverified",
                    "message": "Maximum supply is not independently verified by this service.",
                },
            ],
            "errors": [],
        }

    def dispatch(self, request):
        self.requests.append(request)
        return self.response


class MoltGridCMISTokenomicsTests(unittest.TestCase):
    def test_tokenomics_intent_is_narrow_and_does_not_capture_market_or_identity(self):
        positives = (
            "What are XNT tokenomics?",
            "What is XNT total supply?",
            "What is XNT circulating supply?",
            "What is XNT maximum supply?",
            "Is XNT mint authority revoked?",
            "Does XNT have a freeze authority?",
            "How many decimals does XNT have?",
            "Can XNT mint more tokens?",
        )
        for question in positives:
            with self.subTest(question=question):
                self.assertTrue(wants_cmis_tokenomics(question))
                self.assertEqual(cmis_asset_service(question), "tokenomics")

        exclusions = {
            "What is XNT market cap?": "market_report",
            "What is XNT FDV?": "market_report",
            "What is XNT current supply valuation?": "market_report",
            "Is XNT safe?": "market_report",
            "What is XNT mint address?": "asset_lookup",
        }
        for question, service in exclusions.items():
            with self.subTest(question=question):
                self.assertFalse(wants_cmis_tokenomics(question))
                self.assertEqual(cmis_asset_service(question), service)

    def test_request_contract_is_public_cmis_tokenomics_shape(self):
        expected = {
            "service": "tokenomics",
            "chain": "x1",
            "asset": "XNT",
            "params": {},
        }
        self.assertEqual(build_cmis_tokenomics_request("XNT"), expected)
        self.assertEqual(build_cmis_asset_request("What is XNT total supply?", "XNT"), expected)

    def test_partial_tokenomics_preserves_verified_rpc_facts_and_uncertainty(self):
        gateway = FakeGateway()
        listener = SimpleNamespace()

        answer = format_cmis_asset_answer(
            listener,
            "What are XNT tokenomics?",
            "XNT",
            gateway=gateway,
        )

        self.assertEqual(gateway.requests, [{
            "service": "tokenomics",
            "chain": "x1",
            "asset": "XNT",
            "params": {},
        }])
        self.assertIn("CMIS tokenomics — XNT", answer)
        self.assertIn("Service status: PARTIAL", answer)
        self.assertIn("Current total supply: 1,000,000.5 XNT", answer)
        self.assertIn("Decimals: 6", answer)
        self.assertIn("RPC decimals consistent: YES", answer)
        self.assertIn("Mint authority: REVOKED", answer)
        self.assertIn("Freeze authority: NONE", answer)
        self.assertIn("Future minting possible: NO", answer)
        self.assertIn("Circulating supply: unavailable from independently verified data", answer)
        self.assertIn("Maximum supply: unavailable from independently verified data", answer)
        self.assertIn("standalone scanner result was not supplied", answer)
        self.assertNotIn("Mint events observed: 0", answer)
        self.assertNotIn("Burn events observed: 0", answer)
        self.assertIn("Confidence checks: 3/4 verified", answer)
        self.assertIn("Source: X1 RPC getTokenSupply (tokenomics.current_supply)", answer)
        self.assertIn("Source: X1 RPC getAccountInfo(jsonParsed) (tokenomics.mint_account)", answer)
        self.assertIn("token_activity_not_supplied", answer)
        self.assertIn("circulating_supply_unverified", answer)
        self.assertIn("maximum_supply_unverified", answer)

    def test_verified_bounded_activity_is_visible_without_claiming_lifetime_history(self):
        response = FakeGateway.partial_response()
        response["status"] = "ok"
        response["confidence"] = {
            "complete": True,
            "verified_checks": 4,
            "total_checks": 4,
        }
        response["data"]["token_activity"] = {
            "available": True,
            "activity_verified": True,
            "coverage_scope": "bounded",
            "mint_events_observed": 2,
            "burn_events_observed": 1,
            "minted_tokens_observed": "3",
            "burned_tokens_observed": "1",
            "net_issuance_verified": True,
            "net_issuance_tokens": "2",
            "lifetime_coverage_verified": False,
        }
        gateway = FakeGateway(response)

        answer = format_cmis_asset_answer(
            SimpleNamespace(),
            "What are XNT tokenomics?",
            "XNT",
            gateway=gateway,
        )

        self.assertIn("Bounded mint/burn activity: VERIFIED", answer)
        self.assertIn("Coverage scope: bounded", answer)
        self.assertIn("Mint events observed: 2", answer)
        self.assertIn("Burn events observed: 1", answer)
        self.assertIn("Net issuance in verified scan window: 2 XNT", answer)
        self.assertIn("Chain-lifetime activity coverage: UNVERIFIED", answer)

    def test_canonical_pool_answer_routes_total_supply_to_cmis_tokenomics(self):
        gateway = FakeGateway()
        listener = SimpleNamespace(
            SETTINGS=SimpleNamespace(x1_rpc_url="https://rpc.example"),
            history=SimpleNamespace(parse_historical_comparison=lambda _q: None),
            wants_asset_rank=lambda _q: False,
            wants_historical_liquidity=lambda _q: False,
            wants_volume_rank=lambda _q: False,
            wants_asset_analysis=lambda _q: False,
            format_asset_analysis_answer=lambda *_args: "legacy-analysis",
            format_pool_answer=lambda *_args: "legacy-pool",
            format_usd=lambda value: f"${float(value):,.2f}",
            format_age=lambda value: str(value),
        )

        with patch.object(moltgrid, "_gateway_instance", return_value=gateway):
            moltgrid.wire_market_core(listener)
            answer = listener.format_pool_answer(
                "What is XNT total supply?",
                "XNT",
                ["match"],
                object(),
            )

        self.assertIn("CMIS tokenomics — XNT", answer)
        self.assertEqual(gateway.requests[0]["service"], "tokenomics")
        self.assertEqual(gateway.requests[0]["chain"], "x1")
        self.assertEqual(gateway.requests[0]["asset"], "XNT")


if __name__ == "__main__":
    unittest.main()
