"""Deterministic cross-chain asset provenance primitives for CMIS.

This module validates caller-provided provenance structure only. It does not
verify live bridge state, backing, custody, supply, or provider truth.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

PROVENANCE_CONTRACT = "cross_chain_asset_provenance/v1"
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


__all__ = [
    "DEFAULT_EXECUTION_AUTHORIZED",
    "DISALLOWED_ID_KINDS",
    "PROVENANCE_CONTRACT",
    "build_cross_chain_asset_provenance",
]
