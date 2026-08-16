"""CMIS v1.4.5 — structural AMM fingerprint identity.

v1.4.4 isolated an AGI/rXNT SELL outlier whose program ID and pool/asset/counter
account positions were identical to the dominant SELL layout; only execution
scope differed (outer versus inner).

v1.4.5 separates two concepts:

Structural fingerprint identity:
    program_id
    pool_position
    asset_position
    counter_position

Execution context:
    scope (outer/inner)
    inner group/index metadata retained by v1.4.4

This module does not erase scope. It removes scope only from *structural layout
identity* and reports scope variation separately.

Read-only evidence phase. Canonical vault mapping and exact pool-leg semantics
remain unpromoted.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.fingerprint_variant_attribution import (
    attribute_pool_fingerprint_variants,
)

VERSION = "1.4.5"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _structural_key(fingerprint: Mapping[str, Any]) -> tuple:
    return (
        _text(fingerprint.get("program_id")),
        fingerprint.get("pool_position"),
        fingerprint.get("asset_position"),
        fingerprint.get("counter_position"),
    )


def _structural_to_dict(key: tuple | None) -> dict[str, Any] | None:
    if key is None:
        return None
    return {
        "program_id": key[0],
        "pool_position": key[1],
        "asset_position": key[2],
        "counter_position": key[3],
    }


def _key_sort(key: tuple) -> tuple:
    return tuple("" if value is None else str(value) for value in key)


def _direction_structural_identity(
    direction_report: Mapping[str, Any],
    *,
    min_structural_ratio: float,
    min_direction_occurrences: int,
) -> dict[str, Any]:
    direction = _text(direction_report.get("direction")) or "UNKNOWN"
    transaction_count = int(direction_report.get("transaction_count") or 0)

    distributions = direction_report.get("fingerprint_distribution")
    if not isinstance(distributions, Sequence) or isinstance(
        distributions, (str, bytes)
    ):
        distributions = []

    structural_signatures: dict[tuple, set[str]] = defaultdict(set)
    structural_scopes: dict[tuple, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    full_fingerprint_count = 0

    for item in distributions:
        if not isinstance(item, Mapping):
            continue
        fingerprint = item.get("fingerprint")
        if not isinstance(fingerprint, Mapping):
            continue
        signatures = item.get("signatures")
        if not isinstance(signatures, Sequence) or isinstance(
            signatures, (str, bytes)
        ):
            signatures = []

        key = _structural_key(fingerprint)
        scope = _text(fingerprint.get("scope")) or "unknown"
        signature_set = {
            str(signature)
            for signature in signatures
            if str(signature or "").strip()
        }
        structural_signatures[key].update(signature_set)
        structural_scopes[key][scope].update(signature_set)
        full_fingerprint_count += 1

    dominant_key = None
    dominant_signatures: set[str] = set()
    if structural_signatures:
        dominant_key, dominant_signatures = max(
            structural_signatures.items(),
            key=lambda item: (len(item[1]), _key_sort(item[0])),
        )

    dominant_count = len(dominant_signatures)
    ratio = (
        dominant_count / transaction_count
        if transaction_count > 0
        else 0.0
    )
    sufficient_sample = transaction_count >= min_direction_occurrences
    stable = bool(
        sufficient_sample
        and dominant_key is not None
        and ratio >= min_structural_ratio
    )

    structural_distribution = []
    for key, signatures in sorted(
        structural_signatures.items(),
        key=lambda item: (-len(item[1]), _key_sort(item[0])),
    ):
        scope_distribution = []
        for scope, scope_signatures in sorted(
            structural_scopes[key].items()
        ):
            scope_distribution.append(
                {
                    "scope": scope,
                    "signature_count": len(scope_signatures),
                    "signature_ratio_within_direction": round(
                        len(scope_signatures) / transaction_count
                        if transaction_count
                        else 0.0,
                        6,
                    ),
                    "signatures": sorted(scope_signatures),
                }
            )

        structural_distribution.append(
            {
                "structural_fingerprint": _structural_to_dict(key),
                "signature_count": len(signatures),
                "signature_ratio": round(
                    len(signatures) / transaction_count
                    if transaction_count
                    else 0.0,
                    6,
                ),
                "signatures": sorted(signatures),
                "is_dominant": key == dominant_key,
                "execution_context_distribution": scope_distribution,
                "scope_variation_observed": len(scope_distribution) > 1,
            }
        )

    dominant_scope_distribution = []
    if dominant_key is not None:
        for scope, signatures in sorted(
            structural_scopes[dominant_key].items()
        ):
            dominant_scope_distribution.append(
                {
                    "scope": scope,
                    "signature_count": len(signatures),
                    "signatures": sorted(signatures),
                }
            )

    scope_variation_observed = len(dominant_scope_distribution) > 1
    scope_only_variant_observed = bool(
        scope_variation_observed
        and full_fingerprint_count > len(structural_signatures)
        and ratio == 1.0
    )
    non_scope_structural_variant_observed = bool(
        len(structural_signatures) > 1
    )

    return {
        "direction": direction,
        "transaction_count": transaction_count,
        "min_direction_occurrences": min_direction_occurrences,
        "min_structural_fingerprint_ratio": min_structural_ratio,
        "sufficient_sample": sufficient_sample,
        "dominant_structural_fingerprint": _structural_to_dict(
            dominant_key
        ),
        "dominant_structural_fingerprint_count": dominant_count,
        "dominant_structural_fingerprint_ratio": round(ratio, 6),
        "structural_fingerprint_stable": stable,
        "structural_fingerprint_distribution": structural_distribution,
        "dominant_execution_context_distribution": (
            dominant_scope_distribution
        ),
        "scope_variation_observed": scope_variation_observed,
        "scope_only_variant_observed": scope_only_variant_observed,
        "non_scope_structural_variant_observed": (
            non_scope_structural_variant_observed
        ),
        "structural_identity_promoted": False,
    }


def evaluate_structural_fingerprint_identity(
    *,
    pool_address: str,
    asset_mint: str,
    start_epoch: float,
    end_epoch: float,
    pair: str | None = None,
    rpc_url: str | None = None,
    page_size: int = 1000,
    max_signatures: int = 5000,
    min_occurrences: int = 2,
    min_coverage_ratio: float = 0.50,
    min_opposite_direction_ratio: float = 0.95,
    min_direction_occurrences: int = 2,
    min_fingerprint_ratio: float = 0.95,
    min_dominance_margin: float = 0.10,
    min_structural_fingerprint_ratio: float = 0.95,
    attribution_provider: Callable[..., Mapping[str, Any]] = (
        attribute_pool_fingerprint_variants
    ),
) -> dict[str, Any]:
    """Aggregate v1.4.4 full fingerprints into structural identities."""

    if not 0 <= min_structural_fingerprint_ratio <= 1:
        raise ValueError(
            "min_structural_fingerprint_ratio must be between 0 and 1"
        )
    if (
        isinstance(min_direction_occurrences, bool)
        or not isinstance(min_direction_occurrences, int)
        or min_direction_occurrences < 1
    ):
        raise ValueError(
            "min_direction_occurrences must be an integer >= 1"
        )

    kwargs = {
        "pool_address": pool_address,
        "asset_mint": asset_mint,
        "start_epoch": start_epoch,
        "end_epoch": end_epoch,
        "pair": pair,
        "page_size": page_size,
        "max_signatures": max_signatures,
        "min_occurrences": min_occurrences,
        "min_coverage_ratio": min_coverage_ratio,
        "min_opposite_direction_ratio": min_opposite_direction_ratio,
        "min_direction_occurrences": min_direction_occurrences,
        "min_fingerprint_ratio": min_fingerprint_ratio,
        "min_dominance_margin": min_dominance_margin,
    }
    if rpc_url is not None:
        kwargs["rpc_url"] = rpc_url

    attribution = attribution_provider(**kwargs)
    attribution = (
        dict(attribution) if isinstance(attribution, Mapping) else {}
    )

    leading_pair = attribution.get("leading_pair")
    if not isinstance(leading_pair, Mapping):
        return {
            "service": "structural_fingerprint_identity",
            "version": VERSION,
            "chain": "x1",
            "pool_address": pool_address,
            "pair": pair,
            "asset_mint": asset_mint,
            "status": "no_candidate_pair",
            "leading_pair": None,
            "directions": [],
            "summary": {
                "all_observed_directions_structurally_stable": False,
                "scope_variation_observed": False,
                "scope_only_variant_observed": False,
                "non_scope_structural_variant_observed": False,
                "structural_identity_promoted": False,
                "canonical_vault_mapping_proven": False,
                "canonical_vault_mapping_promoted": False,
                "exact_pool_leg_semantics_promoted": False,
            },
            "source_attribution": attribution,
        }

    raw_directions = attribution.get("directions")
    if not isinstance(raw_directions, Sequence) or isinstance(
        raw_directions, (str, bytes)
    ):
        raw_directions = []

    directions = [
        _direction_structural_identity(
            item,
            min_structural_ratio=min_structural_fingerprint_ratio,
            min_direction_occurrences=min_direction_occurrences,
        )
        for item in raw_directions
        if isinstance(item, Mapping)
    ]

    observed = [
        item for item in directions if item["transaction_count"] > 0
    ]
    all_stable = bool(
        observed
        and all(
            item["structural_fingerprint_stable"]
            for item in observed
        )
    )
    scope_variation = any(
        item["scope_variation_observed"] for item in observed
    )
    scope_only_variant = any(
        item["scope_only_variant_observed"] for item in observed
    )
    non_scope_variant = any(
        item["non_scope_structural_variant_observed"]
        for item in observed
    )

    status = (
        "stable_structural_identity_observed"
        if all_stable
        else "structural_variants_observed"
        if non_scope_variant
        else "insufficient_structural_stability"
    )

    return {
        "service": "structural_fingerprint_identity",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "pair": pair,
        "asset_mint": asset_mint,
        "status": status,
        "leading_pair": dict(leading_pair),
        "thresholds": {
            "min_direction_occurrences": min_direction_occurrences,
            "min_structural_fingerprint_ratio": (
                min_structural_fingerprint_ratio
            ),
        },
        "directions": directions,
        "summary": {
            "all_observed_directions_structurally_stable": all_stable,
            "scope_variation_observed": scope_variation,
            "scope_only_variant_observed": scope_only_variant,
            "non_scope_structural_variant_observed": non_scope_variant,
            "structural_fingerprint_identity_observed": all_stable,
            "structural_identity_promoted": False,
            "canonical_vault_mapping_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "interpretation": (
                "v1.4.5 defines AMM structural layout identity by program ID "
                "plus pool/asset/counter account positions. outer/inner scope "
                "is retained separately as execution context. Scope-only "
                "variation does not create a different structural fingerprint. "
                "No canonical or exact pool-leg promotion occurs here."
            ),
        },
        "source_attribution": attribution,
    }


__all__ = [
    "VERSION",
    "evaluate_structural_fingerprint_identity",
]
