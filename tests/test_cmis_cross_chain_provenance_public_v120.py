from __future__ import annotations

import copy

from liquidity_scout.services.cmis_cross_chain_provenance import (
    build_cross_chain_asset_provenance,
)
from liquidity_scout.services.cmis_cross_chain_provenance_public import (
    CONTRACT_VERSION,
    SERVICE,
    build_cross_chain_asset_provenance_response,
    content_address_provenance,
)


SOL = "So11111111111111111111111111111111111111112"
WSOLX = "JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8"


def canonical():
    provenance = build_cross_chain_asset_provenance(
        canonical_asset_id="wSOL",
        origin={
            "chain": "solana",
            "asset_id": SOL,
            "asset_id_kind": "mint",
        },
        current={
            "chain": "x1",
            "asset_id": WSOLX,
            "asset_id_kind": "mint",
        },
        hops=[{
            "source": {
                "chain": "solana",
                "asset_id": SOL,
                "asset_id_kind": "mint",
            },
            "destination": {
                "chain": "x1",
                "asset_id": WSOLX,
                "asset_id_kind": "mint",
            },
            "bridge": "Warp",
            "representation_type": "wrapped",
            "custody_model": "bridge_custody_dependency",
            "backing_asset_id": SOL,
            "bridge_route_id": "warp-solana-x1-wsol",
        }],
    )
    return content_address_provenance(provenance)


def response(record=None, *, asset=WSOLX, kind="mint"):
    return build_cross_chain_asset_provenance_response(
        canonical() if record is None else record,
        expected_current_asset_id=asset,
        expected_current_asset_id_kind=kind,
    )


def test_promotes_canonical_structural_provenance_without_risk():
    result = response()
    assert result["service"] == SERVICE
    assert result["status"] == "ok"
    assert result["risk"] is None
    assert result["execution_authorized"] is False
    data = result["data"]
    assert data["contract_version"] == CONTRACT_VERSION
    assert data["public_service_promoted"] is True
    assert data["scout_reliance_promoted"] is True
    assert data["origin"]["chain"] == "solana"
    assert data["current"]["chain"] == "x1"
    assert data["current"]["asset_id"] == WSOLX
    assert data["representation_depth"] == 1
    assert len(data["lineage"]) == 1
    assert data["lineage"][0]["bridge"] == "Warp"
    assert data["verification"]["structural_continuity_verified"] is True
    assert data["verification"]["symbol_equivalence_authorized"] is False
    assert data["verification"]["live_bridge_state_verified"] is False
    assert data["verification"]["backing_verified"] is False
    assert data["verification"]["custody_verified"] is False
    assert data["symbol_or_name_identity_inference_authorized"] is False
    assert data["bridge_dependency_is_risk"] is False
    assert data["custody_dependency_is_risk"] is False
    assert data["risk_promotion_authorized"] is False
    assert data["execution_authorized"] is False


def test_exact_current_identity_mismatch_fails_closed():
    result = response(asset="wrong")
    assert result["status"] == "error"
    assert "current asset identity mismatch" in result["errors"][0]["message"]


def test_content_hash_tampering_fails_closed():
    value = canonical()
    value["representation_depth"] = 2
    result = response(value)
    assert result["status"] == "error"
    assert "evidence hash mismatch" in result["errors"][0]["message"]


def test_symbol_identity_kind_cannot_be_smuggled_into_public_record():
    value = canonical()
    material = copy.deepcopy(value)
    material.pop("evidence_sha256")
    material["current"]["asset_id_kind"] = "symbol"
    tampered = content_address_provenance(material)
    result = response(tampered, kind="symbol")
    assert result["status"] == "error"
    assert "symbol/name labels as identity" in result["errors"][0]["message"]


def test_foundation_promotion_flags_cannot_be_pre_promoted():
    value = canonical()
    material = copy.deepcopy(value)
    material.pop("evidence_sha256")
    material["public_service_promoted"] = True
    tampered = content_address_provenance(material)
    result = response(tampered)
    assert result["status"] == "error"
    assert "deterministic reconstruction" in result["errors"][0]["message"]


def test_lineage_continuity_cannot_be_rewritten():
    provenance = build_cross_chain_asset_provenance(
        canonical_asset_id="test",
        origin={"chain": "ethereum", "asset_id": "0x1", "asset_id_kind": "address"},
        current={"chain": "x1", "asset_id": WSOLX, "asset_id_kind": "mint"},
        hops=[
            {
                "source": {"chain": "ethereum", "asset_id": "0x1", "asset_id_kind": "address"},
                "destination": {"chain": "base", "asset_id": "0x2", "asset_id_kind": "address"},
                "bridge": "Bridge A",
                "representation_type": "wrapped",
            },
            {
                "source": {"chain": "base", "asset_id": "0x2", "asset_id_kind": "address"},
                "destination": {"chain": "x1", "asset_id": WSOLX, "asset_id_kind": "mint"},
                "bridge": "Bridge B",
                "representation_type": "wrapped",
            },
        ],
    )
    result = response(content_address_provenance(provenance))
    assert result["status"] == "ok"
    assert result["data"]["representation_depth"] == 2
    assert [hop["bridge"] for hop in result["data"]["lineage"]] == ["Bridge A", "Bridge B"]
