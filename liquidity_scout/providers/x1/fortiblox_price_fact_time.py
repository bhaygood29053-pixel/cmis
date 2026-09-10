"""Bounded evidence analyzer for FortiBlox price fact-time semantics.

This module does not create or promote ``fortiblox_price_freshness/v1``.
It evaluates repeated provider observations and may only conclude PROVEN,
DISPROVEN, or EVIDENCE_INCOMPLETE. Numerical agreement alone is never proof
that top-level ``updatedAt`` is the exact fact time for each token ``priceUsd``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

CONTRACT_VERSION = "fortiblox_price_fact_time_probe/v1"
PROVEN = "PROVEN"
DISPROVEN = "DISPROVEN"
EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"


def _int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _token_map(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    tokens = snapshot.get("tokens")
    if not isinstance(tokens, Sequence) or isinstance(tokens, (str, bytes, bytearray)):
        raise ValueError("tokens must be a sequence")
    result: dict[str, Any] = {}
    for item in tokens:
        if not isinstance(item, Mapping):
            raise ValueError("token observation must be a mapping")
        mint = item.get("mint")
        if not isinstance(mint, str) or not mint.strip() or mint != mint.strip():
            raise ValueError("token mint must be normalized non-empty text")
        if mint in result:
            raise ValueError("duplicate mint in one FortiBlox snapshot")
        result[mint] = item.get("price_usd")
    return result


def analyze_fortiblox_price_fact_time(
    snapshots: Sequence[Mapping[str, Any]],
    *,
    explicit_provider_field_semantics_verified: bool = False,
) -> dict[str, Any]:
    """Analyze repeated snapshots without upgrading observation into authority."""

    if not isinstance(snapshots, Sequence) or isinstance(snapshots, (str, bytes, bytearray)):
        raise ValueError("snapshots must be a sequence")
    if len(snapshots) < 2:
        raise ValueError("at least two snapshots are required")

    normalized: list[tuple[int, int, dict[str, Any]]] = []
    for index, raw in enumerate(snapshots):
        if not isinstance(raw, Mapping):
            raise ValueError(f"snapshots[{index}] must be a mapping")
        collected = _int(f"snapshots[{index}].collected_at_ms", raw.get("collected_at_ms"))
        updated = _int(f"snapshots[{index}].provider_updated_at_ms", raw.get("provider_updated_at_ms"))
        normalized.append((collected, updated, _token_map(raw)))

    normalized.sort(key=lambda row: row[0])
    if len({row[0] for row in normalized}) != len(normalized):
        raise ValueError("collected_at_ms values must be unique")

    contradictions: list[dict[str, Any]] = []
    coupled_changes = 0
    price_change_pairs = 0
    updated_change_pairs = 0
    common_mints_seen: set[str] = set()

    for before, after in zip(normalized, normalized[1:]):
        b_collected, b_updated, b_tokens = before
        a_collected, a_updated, a_tokens = after
        common = sorted(set(b_tokens) & set(a_tokens))
        common_mints_seen.update(common)
        updated_changed = a_updated != b_updated
        if updated_changed:
            updated_change_pairs += 1
        changed_mints = [mint for mint in common if b_tokens[mint] != a_tokens[mint]]
        if changed_mints:
            price_change_pairs += 1
            if updated_changed:
                coupled_changes += 1
            else:
                contradictions.append(
                    {
                        "before_collected_at_ms": b_collected,
                        "after_collected_at_ms": a_collected,
                        "provider_updated_at_ms": a_updated,
                        "changed_mints": changed_mints,
                        "reason": "price_changed_while_top_level_updatedAt_unchanged",
                    }
                )

    millisecond_shape = all(1_000_000_000_000 <= row[1] < 10_000_000_000_000 for row in normalized)
    provider_clock_near_collection = all(abs(row[0] - row[1]) <= 86_400_000 for row in normalized)

    if contradictions:
        conclusion = DISPROVEN
        reason = "Observed token price change while top-level updatedAt remained unchanged."
    elif explicit_provider_field_semantics_verified and price_change_pairs > 0:
        conclusion = PROVEN
        reason = "Independent provider field-level semantics plus repeated coupled live changes support price fact-time use."
    else:
        conclusion = EVIDENCE_INCOMPLETE
        reason = (
            "Repeated observations do not independently prove that top-level updatedAt is the exact fact time for each priceUsd field."
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "conclusion": conclusion,
        "reason": reason,
        "snapshot_count": len(normalized),
        "common_mint_count": len(common_mints_seen),
        "price_change_pair_count": price_change_pairs,
        "updated_at_change_pair_count": updated_change_pairs,
        "price_changes_coupled_to_updated_at_change_count": coupled_changes,
        "contradictions": contradictions,
        "updated_at_millisecond_shape_observed": millisecond_shape,
        "updated_at_clock_near_collection_observed": provider_clock_near_collection,
        "timestamp_unit_verified": False,
        "clock_semantics_verified": False,
        "price_field_timestamp_semantics_verified": conclusion == PROVEN,
        "current_fact_corroboration_authorized": conclusion == PROVEN,
        "source_independence_verified": False,
        "volume_freshness_verified": False,
        "cmis_verified": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "CONTRACT_VERSION",
    "DISPROVEN",
    "EVIDENCE_INCOMPLETE",
    "PROVEN",
    "analyze_fortiblox_price_fact_time",
]
