import copy
import json
import pathlib
import unittest

from liquidity_scout.providers.x1.bridge_source_provenance import (
    BridgeSourceProof,
    evaluate_bridge_source_provenance,
)
from liquidity_scout.providers.x1.warp_config_semantics import (
    WARP_CONFIG_SOURCE_URL,
    build_warp_config_route_observation,
)
from liquidity_scout.services.cmis_bridge_flow_intelligence import (
    BridgeFlowContractError,
    CONTRACT_VERSION,
    build_bridge_flow_intelligence,
)
from liquidity_scout.services.cmis_bridge_route_evidence import (
    qualify_warp_bridge_route,
)
from liquidity_scout.services.cmis_cross_chain_provenance import (
    build_cross_chain_asset_provenance,
)


WSOL = "So11111111111111111111111111111111111111112"
WSOL_X = "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8"
ROUTE_ID = "warp-solana-x1-wsol"
FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "warp_bridge_config_20260903.json"
AS_OF = 1788436800.0
DAY = 86400.0


def endpoint(chain, mint):
    return {"chain": chain, "asset_id": mint, "asset_id_kind": "mint"}


def qualification():
    config = json.loads(FIXTURE.read_text(encoding="utf-8"))
    provenance = build_cross_chain_asset_provenance(
        canonical_asset_id="sol",
        origin=endpoint("solana", WSOL),
        current=endpoint("x1", WSOL_X),
        hops=[
            {
                "source": endpoint("solana", WSOL),
                "destination": endpoint("x1", WSOL_X),
                "bridge": "Warp Bridge",
                "representation_type": "bridge_representation",
                "custody_model": "unknown",
                "bridge_route_id": ROUTE_ID,
            }
        ],
    )
    observation = build_warp_config_route_observation(
        config_response=config,
        route_id=ROUTE_ID,
        source=endpoint("solana", WSOL),
        destination=endpoint("x1", WSOL_X),
    )
    source = evaluate_bridge_source_provenance(
        url=WARP_CONFIG_SOURCE_URL,
        proofs=[
            BridgeSourceProof(
                proof_type="official_app_network_observation",
                reference="official X1 bridge app HAR",
                exact_url=WARP_CONFIG_SOURCE_URL,
            )
        ],
    )
    return qualify_warp_bridge_route(
        provenance=provenance,
        hop_index=0,
        source_provenance=source,
        observation=observation,
        evaluated_at=1788436232.329,
    )


def event(
    suffix,
    *,
    age_seconds,
    direction="inflow",
    amount_raw=1_000_000_000,
    lifecycle_state="settled",
    settlement_verified=True,
    pairing_verified=True,
    transfer_id=None,
    decimals=9,
):
    return {
        "event_id": f"event-{suffix}",
        "transfer_id": transfer_id or f"transfer-{suffix}",
        "route_id": ROUTE_ID,
        "direction": direction,
        "amount_raw": amount_raw,
        "decimals": decimals,
        "settled_at": AS_OF - age_seconds,
        "source": endpoint("solana", WSOL),
        "destination": endpoint("x1", WSOL_X),
        "lifecycle_state": lifecycle_state,
        "settlement_verified": settlement_verified,
        "pairing_verified": pairing_verified,
    }


class BridgeFlowIntelligenceTests(unittest.TestCase):
    def test_contract_computes_24h_7d_30d_and_prior_windows(self):
        events = [
            event("24-in", age_seconds=3600, amount_raw=2_000_000_000),
            event("24-out", age_seconds=7200, direction="outflow", amount_raw=500_000_000),
            event("prior24", age_seconds=DAY + 3600, amount_raw=1_000_000_000),
            event("7d", age_seconds=3 * DAY, amount_raw=4_000_000_000),
            event("prior7d", age_seconds=10 * DAY, direction="outflow", amount_raw=2_000_000_000),
            event("30d", age_seconds=20 * DAY, amount_raw=3_000_000_000),
            event("prior30d", age_seconds=40 * DAY, direction="outflow", amount_raw=1_000_000_000),
        ]
        result = build_bridge_flow_intelligence(
            route_qualification=qualification(),
            events=events,
            as_of=AS_OF,
            coverage_start=AS_OF - 60 * DAY,
            coverage_end=AS_OF,
        )

        self.assertEqual(result["contract"], CONTRACT_VERSION)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["route_id"], ROUTE_ID)
        self.assertEqual(result["decimals"], 9)
        self.assertEqual(result["windows"]["24h"]["current"]["inflow_raw"], 2_000_000_000)
        self.assertEqual(result["windows"]["24h"]["current"]["outflow_raw"], 500_000_000)
        self.assertEqual(result["windows"]["24h"]["current"]["net_flow_raw"], 1_500_000_000)
        self.assertEqual(result["windows"]["24h"]["current"]["inflow"], "2")
        self.assertEqual(result["windows"]["24h"]["prior"]["inflow_raw"], 1_000_000_000)
        self.assertEqual(
            result["windows"]["24h"]["changes"]["inflow_raw"]["percentage"],
            "100",
        )
        self.assertTrue(result["coverage"]["complete_for_all_current_and_prior_windows"])
        self.assertEqual(result["event_accounting"]["accepted_settled_event_count"], 7)
        self.assertFalse(result["missing_history_zero_filled"])
        self.assertFalse(result["execution_authorized"])

    def test_window_boundaries_are_start_inclusive_end_exclusive(self):
        events = [
            event("current-start", age_seconds=DAY, amount_raw=1),
            event("just-current", age_seconds=DAY - 1, amount_raw=2),
            event("prior-start", age_seconds=2 * DAY, amount_raw=4),
        ]
        result = build_bridge_flow_intelligence(
            route_qualification=qualification(),
            events=events,
            as_of=AS_OF,
            coverage_start=AS_OF - 60 * DAY,
            coverage_end=AS_OF,
        )
        current = result["windows"]["24h"]["current"]
        prior = result["windows"]["24h"]["prior"]
        self.assertEqual(current["inflow_raw"], 3)
        self.assertEqual(prior["inflow_raw"], 4)

    def test_duplicate_event_and_transfer_ids_do_not_double_count(self):
        first = event("one", age_seconds=100, amount_raw=10)
        duplicate_event = copy.deepcopy(first)
        duplicate_transfer = event(
            "two",
            age_seconds=90,
            amount_raw=20,
            transfer_id=first["transfer_id"],
        )
        result = build_bridge_flow_intelligence(
            route_qualification=qualification(),
            events=[first, duplicate_event, duplicate_transfer],
            as_of=AS_OF,
            coverage_start=AS_OF - 60 * DAY,
            coverage_end=AS_OF,
        )
        self.assertEqual(result["windows"]["24h"]["current"]["inflow_raw"], 10)
        self.assertEqual(result["event_accounting"]["accepted_settled_event_count"], 1)
        self.assertEqual(
            result["event_accounting"]["unresolved_counts"]["duplicate_event_id"],
            1,
        )
        self.assertEqual(
            result["event_accounting"]["unresolved_counts"]["duplicate_transfer_id"],
            1,
        )
        self.assertEqual(result["status"], "partial")

    def test_refund_failed_pending_and_unverified_events_are_excluded(self):
        events = [
            event("settled", age_seconds=100, amount_raw=10),
            event("refund", age_seconds=90, lifecycle_state="refunded", amount_raw=99),
            event("failed", age_seconds=80, lifecycle_state="failed", amount_raw=99),
            event("pending", age_seconds=70, lifecycle_state="pending", amount_raw=99),
            event("unverified", age_seconds=60, settlement_verified=False, amount_raw=99),
            event("unpaired", age_seconds=50, pairing_verified=False, amount_raw=99),
        ]
        result = build_bridge_flow_intelligence(
            route_qualification=qualification(),
            events=events,
            as_of=AS_OF,
            coverage_start=AS_OF - 60 * DAY,
            coverage_end=AS_OF,
        )
        self.assertEqual(result["windows"]["24h"]["current"]["inflow_raw"], 10)
        counts = result["event_accounting"]["unresolved_counts"]
        self.assertEqual(counts["excluded_refunded"], 1)
        self.assertEqual(counts["excluded_failed"], 1)
        self.assertEqual(counts["excluded_pending"], 1)
        self.assertEqual(counts["unverified_settlement"], 1)
        self.assertEqual(counts["unverified_pairing"], 1)

    def test_incomplete_history_is_null_not_zero(self):
        result = build_bridge_flow_intelligence(
            route_qualification=qualification(),
            events=[event("recent", age_seconds=3600, amount_raw=10)],
            as_of=AS_OF,
            coverage_start=AS_OF - 2 * DAY,
            coverage_end=AS_OF,
        )
        self.assertEqual(result["windows"]["24h"]["current"]["inflow_raw"], 10)
        self.assertTrue(result["windows"]["24h"]["current"]["coverage_complete"])
        self.assertTrue(result["windows"]["24h"]["prior"]["coverage_complete"])
        self.assertIsNone(result["windows"]["7d"]["current"]["inflow_raw"])
        self.assertFalse(result["windows"]["7d"]["current"]["coverage_complete"])
        self.assertIsNone(result["windows"]["30d"]["prior"]["net_flow_raw"])
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["missing_history_zero_filled"])

    def test_zero_denominator_percentage_states_are_explicit(self):
        result = build_bridge_flow_intelligence(
            route_qualification=qualification(),
            events=[event("current", age_seconds=3600, amount_raw=10)],
            as_of=AS_OF,
            coverage_start=AS_OF - 60 * DAY,
            coverage_end=AS_OF,
        )
        inflow_change = result["windows"]["24h"]["changes"]["inflow_raw"]
        outflow_change = result["windows"]["24h"]["changes"]["outflow_raw"]
        self.assertIsNone(inflow_change["percentage"])
        self.assertEqual(inflow_change["percentage_state"], "undefined_zero_baseline")
        self.assertIsNone(outflow_change["percentage"])
        self.assertEqual(outflow_change["percentage_state"], "unchanged_zero_baseline")

    def test_exact_route_identity_mismatch_is_excluded(self):
        wrong = event("wrong", age_seconds=100)
        wrong["destination"] = endpoint("x1", "WrongMint111111111111111111111111111111")
        result = build_bridge_flow_intelligence(
            route_qualification=qualification(),
            events=[wrong],
            as_of=AS_OF,
            coverage_start=AS_OF - 60 * DAY,
            coverage_end=AS_OF,
        )
        self.assertEqual(result["event_accounting"]["accepted_settled_event_count"], 0)
        self.assertEqual(
            result["event_accounting"]["unresolved_counts"]["destination_identity_mismatch"],
            1,
        )

    def test_decimals_mismatch_is_visible_and_not_mixed(self):
        events = [
            event("one", age_seconds=100, amount_raw=1_000_000_000, decimals=9),
            event("two", age_seconds=90, amount_raw=1_000_000, decimals=6),
        ]
        result = build_bridge_flow_intelligence(
            route_qualification=qualification(),
            events=events,
            as_of=AS_OF,
            coverage_start=AS_OF - 60 * DAY,
            coverage_end=AS_OF,
        )
        self.assertEqual(result["decimals"], 9)
        self.assertEqual(result["windows"]["24h"]["current"]["inflow_raw"], 1_000_000_000)
        self.assertEqual(
            result["event_accounting"]["unresolved_counts"]["decimals_mismatch"],
            1,
        )

    def test_supply_is_unavailable_without_separate_verified_supply_evidence(self):
        result = build_bridge_flow_intelligence(
            route_qualification=qualification(),
            events=[],
            as_of=AS_OF,
            coverage_start=AS_OF - 60 * DAY,
            coverage_end=AS_OF,
        )
        self.assertEqual(result["bridged_supply"]["status"], "unavailable")
        self.assertFalse(result["bridged_supply"]["verified"])
        self.assertIsNone(result["bridged_supply"]["amount_raw"])

    def test_verified_supply_evidence_is_preserved_without_recomputation(self):
        result = build_bridge_flow_intelligence(
            route_qualification=qualification(),
            events=[event("one", age_seconds=100)],
            as_of=AS_OF,
            coverage_start=AS_OF - 60 * DAY,
            coverage_end=AS_OF,
            supply_evidence={
                "verified": True,
                "amount_raw": 123_000_000_000,
                "decimals": 9,
                "basis": "accepted_external_supply_contract/v1",
                "observed_at": AS_OF - 10,
            },
        )
        self.assertEqual(result["bridged_supply"]["status"], "ok")
        self.assertEqual(result["bridged_supply"]["amount"], "123")
        self.assertEqual(
            result["bridged_supply"]["basis"],
            "accepted_external_supply_contract/v1",
        )

    def test_evidence_hash_is_deterministic_across_input_order(self):
        a = event("a", age_seconds=100, amount_raw=10)
        b = event("b", age_seconds=200, direction="outflow", amount_raw=5)
        kwargs = dict(
            route_qualification=qualification(),
            as_of=AS_OF,
            coverage_start=AS_OF - 60 * DAY,
            coverage_end=AS_OF,
        )
        first = build_bridge_flow_intelligence(events=[a, b], **kwargs)
        second = build_bridge_flow_intelligence(events=[b, a], **kwargs)
        self.assertEqual(first["evidence_sha256"], second["evidence_sha256"])

    def test_unqualified_route_is_rejected(self):
        bad = qualification()
        bad["warp_qualified"] = False
        with self.assertRaisesRegex(BridgeFlowContractError, "must be qualified"):
            build_bridge_flow_intelligence(
                route_qualification=bad,
                events=[],
                as_of=AS_OF,
                coverage_start=AS_OF - 60 * DAY,
                coverage_end=AS_OF,
            )


if __name__ == "__main__":
    unittest.main()
