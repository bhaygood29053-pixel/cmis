from __future__ import annotations

import copy
import hashlib
import json

from liquidity_scout.services.cmis_bridge_to_xdex_public import (
    CONTRACT_VERSION,
    SERVICE,
    build_bridge_to_xdex_utilization_response,
)

ROUTE = "warp-solana-x1-wsol"
SOURCE = "So11111111111111111111111111111111111111112"
DESTINATION = "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8"
AS_OF = 1_788_600_000.0


def _hash(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def canonical():
    core = {
        "service": SERVICE,
        "contract": CONTRACT_VERSION,
        "route_id": ROUTE,
        "source_chain": "solana",
        "source_mint": SOURCE,
        "destination_chain": "x1",
        "destination_mint": DESTINATION,
        "representation_mint": DESTINATION,
        "as_of": AS_OF,
        "pool_universe_contract": "xdex_exact_representation_pool_universe/v1",
        "pool_metric_contract": "xdex_verified_pool_market_metrics/v1",
        "value_basis_contract": "verified_representation_value_basis/v1",
        "value_basis_evidence_id": "warp-wsolx-pyth-sol-usd:test",
        "value_unit": "USD",
        "comparable_value_basis_verified": True,
        "xdex_pool_count": 0,
        "xdex_pool_addresses": [],
        "xdex_pool_universe_scope": "verified_xdex_program_family",
        "recognized_program_registry_globally_exhaustive": False,
        "global_onchain_pool_discovery_proven": False,
        "verified_zero_pool_set": True,
        "current_liquidity_zero_verified": True,
        "volume_24h_window_coverage_verified": True,
        "pool_metrics": [],
        "verified_xdex_liquidity_value": "0",
        "verified_xdex_volume_24h_value": "0",
        "bridged_supply_raw": 10_000_000_000,
        "bridged_supply_decimals": 9,
        "bridged_supply_token_amount": "10",
        "bridged_supply_value": "1000",
        "bridge_flow_24h": {
            "inflow_raw": 2_000_000_000,
            "outflow_raw": 1_000_000_000,
            "net_flow_raw": 1_000_000_000,
            "inflow_value": "200",
            "outflow_value": "100",
            "net_flow_value": "100",
            "gross_flow_value": "300",
            "value_unit": "USD",
        },
        "bridge_to_xdex_liquidity_ratio": "0",
        "bridge_to_xdex_liquidity_ratio_state": "verified",
        "bridge_gross_flow_24h_to_xdex_volume_24h_ratio": None,
        "bridge_net_flow_24h_to_xdex_volume_24h_ratio": None,
        "bridge_flow_to_xdex_volume_ratio_state": "undefined_zero_xdex_volume",
        "market_activity_24h_verified": True,
        "utilization_verified": True,
        "issue_410_acceptance_verified": True,
        "source_independence_verified": False,
        "causal_bridge_to_xdex_claim_authorized": False,
        "adoption_claim_authorized": False,
        "risk_promotion_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "read_only": True,
        "execution_authorized": False,
    }
    return {**core, "evidence_sha256": _hash(core)}


def response(record=None, **kwargs):
    return build_bridge_to_xdex_utilization_response(
        canonical() if record is None else record,
        expected_route_id=kwargs.pop("expected_route_id", ROUTE),
        expected_source_mint=kwargs.pop("expected_source_mint", SOURCE),
        expected_destination_mint=kwargs.pop(
            "expected_destination_mint", DESTINATION
        ),
        evaluated_at=kwargs.pop("evaluated_at", AS_OF + 10),
        max_evidence_age_seconds=kwargs.pop("max_evidence_age_seconds", 300),
        **kwargs,
    )


def _rehash(value):
    value = copy.deepcopy(value)
    value.pop("evidence_sha256", None)
    return {**value, "evidence_sha256": _hash(value)}


def test_promotes_only_validated_canonical_issue410_record():
    result = response()
    assert result["status"] == "ok"
    assert result["risk"] is None
    assert result["execution_authorized"] is False
    data = result["data"]
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["public_service_promoted"] is True
    assert data["scout_reliance_promoted"] is True
    assert data["route"]["source_mint"] == SOURCE
    assert data["route"]["destination_mint"] == DESTINATION
    assert data["scope"]["xdex_pool_universe_scope"] == (
        "verified_xdex_program_family"
    )
    assert data["scope"]["global_onchain_pool_discovery_proven"] is False
    assert data["xdex_market"]["liquidity_value"] == "0"
    assert data["xdex_market"]["volume_24h_value"] == "0"
    assert data["causal_bridge_to_xdex_claim_authorized"] is False
    assert data["adoption_claim_authorized"] is False
    assert data["risk_promotion_authorized"] is False


def test_identity_mismatch_fails_closed():
    result = response(expected_destination_mint="wrong")
    assert result["status"] == "error"
    assert "destination mint identity mismatch" in result["errors"][0]["message"]


def test_scope_cannot_expand_to_all_x1_dexes():
    value = canonical()
    value["xdex_pool_universe_scope"] = "all_x1_dexes"
    result = response(_rehash(value))
    assert result["status"] == "error"
    assert "verified XDEX program-family scope" in result["errors"][0]["message"]


def test_global_exhaustiveness_claim_fails_closed():
    value = canonical()
    value["global_onchain_pool_discovery_proven"] = True
    result = response(_rehash(value))
    assert result["status"] == "error"
    assert "global X1 DEX discovery" in result["errors"][0]["message"]


def test_stale_record_fails_closed():
    result = response(evaluated_at=AS_OF + 301)
    assert result["status"] == "error"
    assert "stale" in result["errors"][0]["message"]


def test_tampered_hash_fails_closed():
    value = canonical()
    value["verified_xdex_volume_24h_value"] = "1"
    result = response(value)
    assert result["status"] == "error"
    assert "evidence hash mismatch" in result["errors"][0]["message"]


def test_missing_volume_coverage_fails_closed():
    value = canonical()
    value["volume_24h_window_coverage_verified"] = False
    result = response(_rehash(value))
    assert result["status"] == "error"
    assert "volume_24h_window_coverage_verified" in result["errors"][0]["message"]
