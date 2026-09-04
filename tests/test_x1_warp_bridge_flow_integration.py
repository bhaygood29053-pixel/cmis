import copy
import unittest

from liquidity_scout.providers.x1.warp_bridged_supply_evidence import (
    CONTRACT as SUPPLY_CONTRACT,
)
from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SEMANTIC_CONTRACT_ID,
)
from liquidity_scout.providers.x1.warp_message_lifecycle_retention import (
    CONTRACT as LIFECYCLE_CONTRACT,
)
from liquidity_scout.providers.x1.warp_onchain_transfer_history import (
    CONTRACT as TRANSFER_CONTRACT,
)
from liquidity_scout.providers.x1.warp_bridge_flow_integration import (
    CONTRACT,
    WarpBridgeFlowIntegrationError,
    build_warp_bridge_flow_integration,
)
from liquidity_scout.services.cmis_bridge_route_evidence import (
    WARP_QUALIFICATION_CONTRACT,
)


WSOL = "So11111111111111111111111111111111111111112"
WSOL_X = "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8"
ROUTE_ID = "warp-solana-x1-wsol"
AS_OF = 1788436800.0
DAY = 86400.0


def endpoint(chain, mint):
    return {"chain": chain, "asset_id": mint, "asset_id_kind": "mint"}


def qualification():
    return {
        "contract": WARP_QUALIFICATION_CONTRACT,
        "provider": "warp_bridge",
        "warp_qualified": True,
        "route_evidence": {
            "qualified": True,
            "route_id": ROUTE_ID,
            "source": endpoint("solana", WSOL),
            "destination": endpoint("x1", WSOL_X),
            "semantic_contract_id": WARP_CONFIG_SEMANTIC_CONTRACT_ID,
            "evidence_id": "route-evidence",
            "source_url": "https://app.bridge.x1.xyz/api/bridge/config",
        },
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


def event(suffix, *, age_seconds, direction="inflow", amount_raw=1_000_000_000):
    return {
        "event_id": f"event-{suffix}",
        "transfer_id": f"transfer-{suffix}",
        "route_id": ROUTE_ID,
        "direction": direction,
        "amount_raw": amount_raw,
        "decimals": 9,
        "settled_at": AS_OF - age_seconds,
        "source": endpoint("solana", WSOL),
        "destination": endpoint("x1", WSOL_X),
        "lifecycle_state": "settled",
        "settlement_verified": True,
        "pairing_verified": True,
    }


def normalized():
    events = [
        event("now", age_seconds=3600, amount_raw=2_000_000_000),
        event("prior24", age_seconds=DAY + 3600, amount_raw=1_000_000_000),
        event("7d", age_seconds=3 * DAY, direction="outflow", amount_raw=500_000_000),
        event("prior7d", age_seconds=10 * DAY, amount_raw=3_000_000_000),
        event("30d", age_seconds=20 * DAY, amount_raw=4_000_000_000),
        event("prior30d", age_seconds=40 * DAY, direction="outflow", amount_raw=2_000_000_000),
    ]
    return {
        "contract": TRANSFER_CONTRACT,
        "route_id": ROUTE_ID,
        "candidate_route_outgoing_count": len(events),
        "accepted_settled_event_count": len(events),
        "unresolved_counts": {},
        "events": events,
        "pairing_semantics_verified": True,
        "settled_event_semantics_verified": True,
        "flow_event_normalization_authorized": True,
        "execution_authorized": False,
    }


def lifecycle():
    return {
        "contract": LIFECYCLE_CONTRACT,
        "as_of": AS_OF,
        "requested_start": AS_OF - 60 * DAY,
        "lookback_seconds": 60 * DAY,
        "program_signature_trace_complete_verified": True,
        "requested_history_boundary_verified": True,
        "no_message_account_closure_observed": True,
        "no_message_account_recreation_observed": True,
        "no_ambiguous_zero_zero_lifecycle_touch": True,
        "expected_outgoing_creations_verified": True,
        "retention_deletion_semantics_verified": True,
        "historical_retention_complete_verified": True,
        "requested_window_coverage_verified": True,
        "coverage_complete_verified": True,
        "missing_history_zero_authorized": True,
        "missing_history_zero_scope": "exact_message_universe_requested_lookback_only",
        "execution_authorized": False,
    }


def supply():
    return {
        "contract": SUPPLY_CONTRACT,
        "route_id": ROUTE_ID,
        "current_backing_closure_verified": True,
        "bridged_supply_verified": True,
        "supply_evidence": {
            "verified": True,
            "semantic_contract_accepted": True,
            "amount_raw": 328_561_024,
            "decimals": 9,
            "basis": (
                "exact_native_source_warp_vault_balance_equals_"
                "exact_wrapped_destination_mint_supply_with_warp_mint_authority"
            ),
            "observed_at": AS_OF,
        },
        "provider_tvl_label_promoted": False,
        "execution_authorized": False,
    }


class WarpBridgeFlowIntegrationTests(unittest.TestCase):
    def test_accepts_complete_retention_events_and_supply(self):
        result = build_warp_bridge_flow_integration(
            route_qualification=qualification(),
            normalized_events=normalized(),
            lifecycle_retention=lifecycle(),
            bridged_supply=supply(),
        )
        self.assertEqual(result["contract"], CONTRACT)
        self.assertTrue(result["integration_verified"])
        self.assertTrue(result["canonical_event_pairing_verified"])
        self.assertTrue(result["historical_retention_complete_verified"])
        self.assertTrue(result["missing_history_zero_authorized"])
        self.assertTrue(result["bridged_supply_verified"])
        self.assertTrue(result["all_current_and_prior_windows_complete"])
        self.assertTrue(result["all_current_and_prior_window_values_non_null"])
        self.assertEqual(
            result["flow"]["windows"]["24h"]["current"]["inflow_raw"],
            2_000_000_000,
        )
        self.assertEqual(
            result["flow"]["windows"]["24h"]["prior"]["inflow_raw"],
            1_000_000_000,
        )
        self.assertFalse(result["source_independence_verified"])
        self.assertFalse(result["provider_tvl_label_promoted"])
        self.assertFalse(result["public_service_promoted"])
        self.assertFalse(result["scout_reliance_promoted"])
        self.assertFalse(result["execution_authorized"])

    def test_rejects_unaccepted_lifecycle_coverage(self):
        bad = lifecycle()
        bad["historical_retention_complete_verified"] = False
        with self.assertRaisesRegex(
            WarpBridgeFlowIntegrationError,
            "historical_retention_complete_verified",
        ):
            build_warp_bridge_flow_integration(
                route_qualification=qualification(),
                normalized_events=normalized(),
                lifecycle_retention=bad,
                bridged_supply=supply(),
            )

    def test_rejects_unverified_supply(self):
        bad = supply()
        bad["bridged_supply_verified"] = False
        with self.assertRaisesRegex(
            WarpBridgeFlowIntegrationError,
            "bridged_supply_verified",
        ):
            build_warp_bridge_flow_integration(
                route_qualification=qualification(),
                normalized_events=normalized(),
                lifecycle_retention=lifecycle(),
                bridged_supply=bad,
            )

    def test_unresolved_pairing_prevents_final_integration_verification(self):
        bad = copy.deepcopy(normalized())
        bad["unresolved_counts"] = {"missing_incoming_match": 1}
        result = build_warp_bridge_flow_integration(
            route_qualification=qualification(),
            normalized_events=bad,
            lifecycle_retention=lifecycle(),
            bridged_supply=supply(),
        )
        self.assertFalse(result["canonical_event_pairing_verified"])
        self.assertFalse(result["integration_verified"])
        self.assertEqual(
            result["normalized_unresolved_counts"],
            {"missing_incoming_match": 1},
        )

    def test_zero_window_is_numeric_only_under_accepted_coverage(self):
        value = normalized()
        value["events"] = []
        value["candidate_route_outgoing_count"] = 0
        value["accepted_settled_event_count"] = 0
        result = build_warp_bridge_flow_integration(
            route_qualification=qualification(),
            normalized_events=value,
            lifecycle_retention=lifecycle(),
            bridged_supply=supply(),
        )
        self.assertTrue(result["integration_verified"])
        self.assertEqual(result["flow"]["windows"]["24h"]["current"]["inflow_raw"], 0)
        self.assertEqual(result["flow"]["windows"]["30d"]["prior"]["outflow_raw"], 0)
        self.assertTrue(result["missing_history_zero_authorized"])
        self.assertFalse(result["flow"]["missing_history_zero_filled"])


if __name__ == "__main__":
    unittest.main()
