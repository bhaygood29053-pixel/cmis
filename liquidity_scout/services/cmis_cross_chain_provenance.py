"""Deterministic cross-chain asset provenance primitives for CMIS.

This module validates caller-provided provenance structure only. It does not
verify live bridge state, backing, custody, supply, or provider truth.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

PROVENANCE_CONTRACT = "cross_chain_asset_provenance/v1"
ROBINHOOD_X1_EXTENSION_CONTRACT = "cross_chain_asset_provenance_robinhood_x1/v1"
DISALLOWED_ID_KINDS = frozenset({"symbol", "ticker", "name", "label"})
DEFAULT_EXECUTION_AUTHORIZED = False


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _normalized_chain(value: Any, field: str) -> str:
    return _required_text(value, field).casefold()


def _endpoint(value: Any, *, field: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")

    chain = _normalized_chain(value.get("chain"), f"{field}.chain")
    asset_id = _required_text(value.get("asset_id"), f"{field}.asset_id")
    asset_id_kind = _required_text(
        value.get("asset_id_kind"),
        f"{field}.asset_id_kind",
    ).casefold()

    if asset_id_kind in DISALLOWED_ID_KINDS:
        raise ValueError(
            f"{field}.asset_id_kind cannot use symbol/name labels as identity"
        )

    return {
        "chain": chain,
        "asset_id": asset_id,
        "asset_id_kind": asset_id_kind,
    }


def _same_endpoint(left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    return (
        left["chain"] == right["chain"]
        and left["asset_id"] == right["asset_id"]
        and left["asset_id_kind"] == right["asset_id_kind"]
    )


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_hop(value: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"hops[{index}] must be a mapping")

    source = _endpoint(value.get("source"), field=f"hops[{index}].source")
    destination = _endpoint(
        value.get("destination"),
        field=f"hops[{index}].destination",
    )
    if source["chain"] == destination["chain"]:
        raise ValueError(
            f"hops[{index}] must cross chains; same-chain transformations "
            "require a separate contract"
        )

    bridge = _required_text(value.get("bridge"), f"hops[{index}].bridge")
    representation_type = _required_text(
        value.get("representation_type"),
        f"hops[{index}].representation_type",
    ).casefold()

    return {
        "source": source,
        "destination": destination,
        "bridge": bridge,
        "representation_type": representation_type,
        "custody_model": _optional_text(value.get("custody_model")),
        "backing_asset_id": _optional_text(value.get("backing_asset_id")),
        "bridge_route_id": _optional_text(value.get("bridge_route_id")),
    }


def _dependency_records(hops: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()

    for hop in hops:
        bridge = str(hop["bridge"])
        custody_model = hop.get("custody_model")
        key = (bridge.casefold(), custody_model)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "bridge": bridge,
                "custody_model": custody_model,
            }
        )
    return records


def build_cross_chain_asset_provenance(
    *,
    canonical_asset_id: Any,
    origin: Any,
    current: Any,
    hops: Any,
) -> dict[str, Any]:
    """Validate and normalize one ordered cross-chain representation lineage.

    Identity must be rooted in explicit chain-scoped identifiers. Symbol,
    ticker, name, and label identity kinds are rejected. The function proves
    structural continuity only; it does not establish that any bridge route,
    backing model, custody claim, or live state is true.
    """

    canonical = _required_text(canonical_asset_id, "canonical_asset_id")
    origin_endpoint = _endpoint(origin, field="origin")
    current_endpoint = _endpoint(current, field="current")

    if not isinstance(hops, Sequence) or isinstance(hops, (str, bytes)):
        raise ValueError("hops must be a sequence")
    if not hops:
        raise ValueError("at least one cross-chain hop is required")

    normalized_hops = [
        _normalize_hop(hop, index=index)
        for index, hop in enumerate(hops)
    ]

    if not _same_endpoint(normalized_hops[0]["source"], origin_endpoint):
        raise ValueError("first hop source must equal origin")

    seen_hops: set[tuple[str, str, str, str, str]] = set()
    for index, hop in enumerate(normalized_hops):
        if index:
            prior = normalized_hops[index - 1]
            if not _same_endpoint(prior["destination"], hop["source"]):
                raise ValueError(
                    f"hops[{index}] source must equal prior hop destination"
                )

        hop_key = (
            hop["source"]["chain"],
            hop["source"]["asset_id"],
            hop["destination"]["chain"],
            hop["destination"]["asset_id"],
            str(hop["bridge"]).casefold(),
        )
        if hop_key in seen_hops:
            raise ValueError("duplicate provenance hop is not allowed")
        seen_hops.add(hop_key)

    if not _same_endpoint(normalized_hops[-1]["destination"], current_endpoint):
        raise ValueError("final hop destination must equal current")

    return {
        "contract": PROVENANCE_CONTRACT,
        "canonical_asset_id": canonical,
        "origin": origin_endpoint,
        "current": current_endpoint,
        "representation_depth": len(normalized_hops),
        "lineage": normalized_hops,
        "dependencies": _dependency_records(normalized_hops),
        "verification": {
            "structural_continuity_verified": True,
            "exact_chain_scoped_identifiers_required": True,
            "symbol_equivalence_authorized": False,
            "live_bridge_state_verified": False,
            "backing_verified": False,
            "custody_verified": False,
            "source_independence_verified": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": DEFAULT_EXECUTION_AUTHORIZED,
    }


def build_robinhood_x1_provenance_extension(
    *,
    canonical_asset_id: Any,
    origin: Any,
    current: Any,
    hops: Any,
    source_asset_class: Any,
    custody_dependency: Any = None,
    route_evidence_id: Any = None,
) -> dict[str, Any]:
    """Compose a Robinhood-origin to X1 provenance view over accepted v1.

    This is an additive structural extension. It does not alter the accepted
    `cross_chain_asset_provenance/v1` object or promote live bridge, backing,
    custody, tokenized-equity entitlement, or route-state claims.
    """

    base = build_cross_chain_asset_provenance(
        canonical_asset_id=canonical_asset_id,
        origin=origin,
        current=current,
        hops=hops,
    )

    robinhood_chains = {"robinhood", "robinhood chain", "robinhood_chain"}
    if base["origin"]["chain"] not in robinhood_chains:
        raise ValueError("Robinhood→X1 extension requires a Robinhood origin")
    if base["current"]["chain"] != "x1":
        raise ValueError("Robinhood→X1 extension requires current chain x1")

    asset_class = _required_text(source_asset_class, "source_asset_class").casefold()
    custody = _optional_text(custody_dependency)
    route_evidence = _optional_text(route_evidence_id)

    direct_robinhood_x1_hops = [
        hop
        for hop in base["lineage"]
        if hop["source"]["chain"] in robinhood_chains
        and hop["destination"]["chain"] == "x1"
    ]

    return {
        "contract": ROBINHOOD_X1_EXTENSION_CONTRACT,
        "base_provenance_contract": PROVENANCE_CONTRACT,
        "canonical_asset_id": base["canonical_asset_id"],
        "origin": base["origin"],
        "current": base["current"],
        "representation_depth": base["representation_depth"],
        "lineage": base["lineage"],
        "dependencies": base["dependencies"],
        "source_context": {
            "source_asset_class": asset_class,
            "custody_dependency": custody,
            "route_evidence_id": route_evidence,
            "direct_robinhood_to_x1_hop_present": bool(direct_robinhood_x1_hops),
        },
        "verification": {
            **base["verification"],
            "robinhood_origin_structurally_bound": True,
            "x1_destination_structurally_bound": True,
            "source_asset_class_verified": False,
            "tokenized_equity_entitlement_verified": False,
            "live_robinhood_x1_route_verified": False,
            "route_evidence_resolved": False,
            "custody_verified": False,
            "backing_verified": False,
        },
        "boundaries": {
            "source_asset_class_is_descriptive_only": True,
            "custody_dependency_is_descriptive_only": True,
            "route_evidence_id_is_selector_only": route_evidence is not None,
            "bridge_availability_claim_authorized": False,
            "custody_safety_claim_authorized": False,
            "backing_sufficiency_claim_authorized": False,
            "tokenized_equity_ownership_claim_authorized": False,
            "automatic_risk_conclusion_authorized": False,
            "trade_recommendation_authorized": False,
        },
        "read_only": True,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": DEFAULT_EXECUTION_AUTHORIZED,
    }


__all__ = [
    "DEFAULT_EXECUTION_AUTHORIZED",
    "DISALLOWED_ID_KINDS",
    "PROVENANCE_CONTRACT",
    "ROBINHOOD_X1_EXTENSION_CONTRACT",
    "build_cross_chain_asset_provenance",
    "build_robinhood_x1_provenance_extension",
]
