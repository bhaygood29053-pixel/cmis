"""Fail-closed same-fact comparison for X1 historical block observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from liquidity_scout.providers.x1.secondary_rpc_contract import (
    SecondaryRpcContractObservation,
    classify_secondary_rpc_response,
)


@dataclass(frozen=True)
class HistoricalBlockFact:
    source: str
    requested_slot: int
    blockhash: str
    previous_blockhash: str
    parent_slot: int
    block_height: int | None
    contract_verified: bool
    archival_completeness_verified: bool = False
    retention_verified: bool = False
    finality_semantics_verified: bool = False
    cmis_promotable: bool = False


@dataclass(frozen=True)
class HistoricalBlockComparison:
    requested_slot: int
    status: str
    official_source: str
    secondary_source: str
    compared_fields: tuple[str, ...]
    conflicts: tuple[str, ...]
    same_fact_identity_verified: bool
    source_independence_verified: bool | None
    archival_completeness_verified: bool = False
    retention_verified: bool = False
    finality_semantics_verified: bool = False
    cmis_promotable: bool = False


def _validated_slot(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("requested_slot must be a non-negative integer")
    return value


def extract_historical_block_fact(
    *, source: str, requested_slot: int, payload: Mapping[str, Any]
) -> HistoricalBlockFact:
    """Extract one block identity from a captured ``getBlock`` request/response.

    ``requested_slot`` is the explicit captured request context. The response
    body does not echo that slot, so ``parentSlot + 1`` is deliberately not used
    as a binding rule: skipped slots can make that inference false. We only
    require the returned parent to precede the requested slot.
    """
    requested_slot = _validated_slot(requested_slot)
    observation: SecondaryRpcContractObservation = classify_secondary_rpc_response(
        source=source, method="getBlock", payload=payload
    )
    if not observation.transport_ok or not observation.result_shape_verified:
        raise ValueError("getBlock observation is not structurally verified")

    result = payload["result"]
    parent_slot = result.get("parentSlot")
    blockhash = result.get("blockhash")
    previous_blockhash = result.get("previousBlockhash")
    block_height = result.get("blockHeight")

    if isinstance(parent_slot, bool) or not isinstance(parent_slot, int) or parent_slot < 0:
        raise ValueError("parentSlot is missing or invalid")
    if parent_slot >= requested_slot:
        raise ValueError("parentSlot must precede requested_slot")
    if not isinstance(blockhash, str) or not blockhash.strip():
        raise ValueError("blockhash is missing or invalid")
    if not isinstance(previous_blockhash, str) or not previous_blockhash.strip():
        raise ValueError("previousBlockhash is missing or invalid")
    if block_height is not None and (
        isinstance(block_height, bool) or not isinstance(block_height, int) or block_height < 0
    ):
        raise ValueError("blockHeight is invalid")

    return HistoricalBlockFact(
        source=observation.source,
        requested_slot=requested_slot,
        blockhash=blockhash.strip(),
        previous_blockhash=previous_blockhash.strip(),
        parent_slot=parent_slot,
        block_height=block_height,
        contract_verified=True,
    )


def compare_historical_block_facts(
    official: HistoricalBlockFact,
    secondary: HistoricalBlockFact,
    *,
    source_independence_verified: bool | None = None,
) -> HistoricalBlockComparison:
    """Compare two captured facts without inferring source independence.

    Distinct source labels are necessary but not sufficient for independence.
    ``None`` means independence is unproven, ``False`` means it was explicitly
    rejected/disproven, and ``True`` means an accepted external contract proved
    independence for these observations. Positive proof still requires distinct
    non-empty source identities.
    """
    if not isinstance(official, HistoricalBlockFact) or not isinstance(secondary, HistoricalBlockFact):
        raise TypeError("official and secondary must be HistoricalBlockFact values")
    if source_independence_verified is not None and not isinstance(source_independence_verified, bool):
        raise TypeError("source_independence_verified must be a boolean or None")

    official_source = official.source.strip()
    secondary_source = secondary.source.strip()
    source_identities_present = bool(official_source and secondary_source)
    distinct_sources = bool(
        source_identities_present and official_source != secondary_source
    )

    if source_independence_verified is True:
        independent: bool | None = True if distinct_sources else False
    elif source_independence_verified is False:
        independent = False
    elif source_identities_present and official_source == secondary_source:
        independent = False
    else:
        independent = None

    same_slot = official.requested_slot == secondary.requested_slot
    verified = official.contract_verified and secondary.contract_verified

    if independent is not True or not same_slot or not verified:
        return HistoricalBlockComparison(
            requested_slot=official.requested_slot,
            status="INSUFFICIENT_EVIDENCE",
            official_source=official.source,
            secondary_source=secondary.source,
            compared_fields=(),
            conflicts=(),
            same_fact_identity_verified=False,
            source_independence_verified=independent,
        )

    fields: tuple[str, ...] = ("blockhash", "previous_blockhash", "parent_slot")
    if official.block_height is not None and secondary.block_height is not None:
        fields += ("block_height",)

    conflicts = tuple(field for field in fields if getattr(official, field) != getattr(secondary, field))
    status = "CONFLICT" if conflicts else "AGREEMENT"

    return HistoricalBlockComparison(
        requested_slot=official.requested_slot,
        status=status,
        official_source=official.source,
        secondary_source=secondary.source,
        compared_fields=fields,
        conflicts=conflicts,
        same_fact_identity_verified=True,
        source_independence_verified=True,
    )


__all__ = [
    "HistoricalBlockFact",
    "HistoricalBlockComparison",
    "extract_historical_block_fact",
    "compare_historical_block_facts",
]
