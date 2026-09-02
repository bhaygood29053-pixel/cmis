import unittest

from liquidity_scout.cmis.discovery_intelligence_gateway import (
    DiscoveryIntelligenceGatewayMixin,
)
from liquidity_scout.cmis.discovery_ledger import (
    DiscoveryLedgerV1,
    DiscoveryObservationV1,
)
from liquidity_scout.services.cmis_contract import build_service_envelope


MINT = "7SXmUpcBGSAwW5LmtzQVF9jHswZ7xzmdKqWa4nDgL3ER"


def observed(*, kind="market_verified", fact=100, recorded=110, source="x1_rpc", state="verified"):
    return DiscoveryObservationV1.create(
        mint=MINT,
        observation_kind=kind,
        fact_time_unix=fact,
        fact_time_verified=True,
        recorded_at_unix=recorded,
        source_id=source,
        source_role="primary",
        source_scope=f"mint:{MINT}",
        verification_state=state,
    )


class BaseGateway:
    def __init__(self, ledger):
        self.discovery_ledger = ledger

    @staticmethod
    def _text(value):
        text = str(value or "").strip()
        return text or None

    def _asset_lookup(self, asset):
        if asset != MINT:
            return build_service_envelope(
                "asset_lookup", "x1", "unavailable", warnings=[{"code": "not_found"}]
            )
        return build_service_envelope(
            "asset_lookup",
            "x1",
            "ok",
            asset={"mint": MINT, "symbol": "AGI", "name": "AGI"},
            confidence={"identity_verified": True},
        )

    @staticmethod
    def _gateway_error(service, chain, code, message):
        return build_service_envelope(
            service, chain, "error", errors=[{"code": code, "message": message}]
        )

    @staticmethod
    def _chain_unavailable(service, chain):
        return build_service_envelope(service, chain, "unavailable")

    @staticmethod
    def _propagate_upstream(service, upstream):
        return build_service_envelope(
            service,
            upstream.get("chain") or "x1",
            upstream.get("status") or "unavailable",
            warnings=upstream.get("warnings") or [],
        )

    def dispatch(self, request):
        return {"fallback": request}


class Gateway(DiscoveryIntelligenceGatewayMixin, BaseGateway):
    pass


class DiscoveryIntelligenceRuntimeTests(unittest.TestCase):
    def test_dispatch_projects_only_verified_fact_time_observations(self):
        first = observed(fact=100, recorded=500, source="backfill")
        recent = observed(fact=300, recorded=310, source="xdex")
        partial = observed(fact=50, recorded=60, source="partial", state="partial")
        gateway = Gateway(DiscoveryLedgerV1((recent, partial, first)))

        response = gateway.dispatch({
            "service": "discovery_intelligence",
            "chain": "x1",
            "asset": MINT,
            "params": {},
        })

        self.assertEqual(response["status"], "partial")
        self.assertEqual(response["data"]["verified_observation_count"], 2)
        self.assertEqual(response["data"]["first_verified_observation"]["content_id"], first.content_id)
        self.assertEqual(response["data"]["most_recent_verified_observation"]["content_id"], recent.content_id)
        self.assertEqual(response["data"]["coverage"]["elapsed_observed_seconds"], 200)
        self.assertIsNone(response["data"]["token_launch_time"])
        self.assertFalse(response["execution_authorized"])

    def test_optional_kind_filter_is_exact_and_missing_scope_is_unavailable(self):
        gateway = Gateway(DiscoveryLedgerV1((observed(kind="market_verified"),)))
        response = gateway.dispatch({
            "service": "discovery_intelligence",
            "chain": "x1",
            "asset": MINT,
            "params": {"observation_kind": "liquidity_verified"},
        })
        self.assertEqual(response["status"], "unavailable")
        self.assertEqual(response["data"]["verified_observation_count"], 0)
        self.assertIsNone(response["data"]["coverage"]["start_fact_time_unix"])

    def test_caller_cannot_inject_history_or_cross_chain_scope(self):
        gateway = Gateway(DiscoveryLedgerV1())
        response = gateway.dispatch({
            "service": "discovery_intelligence",
            "chain": "x1",
            "asset": MINT,
            "params": {"observations": []},
        })
        self.assertEqual(response["status"], "error")
        self.assertEqual(response["errors"][0]["code"], "unsupported_discovery_params")

        response = gateway.dispatch({
            "service": "discovery_intelligence",
            "chain": "solana",
            "asset": MINT,
            "params": {},
        })
        self.assertEqual(response["status"], "unavailable")
        self.assertFalse(response["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
