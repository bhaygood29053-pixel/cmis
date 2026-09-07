"""Deterministic FortiBlox cross-source reconciliation for X1.

This contract compares one normalized FortiBlox token observation against
bounded XDEX, X1.Ninja, and/or accepted CMIS reference observations.

Agreement is numerical corroboration only. It is not source-independence proof,
CMIS verification, freshness promotion, risk truth, or execution authority.
Disagreement is preserved explicitly and never averaged away.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


CONTRACT_VERSION = "fortiblox_cross_source_reconciliation/v1"

AGREE = "AGREE"
DISAGREE = "DISAGREE"
EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
SCOPE_MISMATCH = "SCOPE_MISMATCH"
NOT_COMPARABLE = "NOT_COMPARABLE"

ALLOWED_REFERENCE_SOURCES = frozenset({"xdex", "x1_ninja", "cmis"})
DEFAULT_PRICE_RELATIVE_TOLERANCE = Decimal("0.005")
DEFAULT_PRICE_ABSOLUTE_TOLERANCE_USD = Decimal("0.000000000001")
DEFAULT_VOLUME_RELATIVE_TOLERANCE = Decimal("0.01")
DEFAULT_VOLUME_ABSOLUTE_TOLERANCE_USD = Decimal("0.01")
ROLLING_24H_SECONDS = 86400


class FortiBloxCrossSourceReconciliationError(ValueError):
    pass


def _mapping(value: Any, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FortiBloxCrossSourceReconciliationError(f"{name} must be a mapping")
    return value


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _decimal(value: Any, *, name: str, nonnegative: bool = False) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise FortiBloxCrossSourceReconciliationError(f"{name} must be numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise FortiBloxCrossSourceReconciliationError(
            f"{name} must be numeric"
        ) from exc
    if not parsed.is_finite():
        raise FortiBloxCrossSourceReconciliationError(f"{name} must be finite")
    if nonnegative and parsed < 0:
        raise FortiBloxCrossSourceReconciliationError(
            f"{name} must be non-negative"
        )
    return parsed


def _positive_tolerance(value: Any, *, name: str) -> Decimal:
    parsed = _decimal(value, name=name, nonnegative=True)
    if parsed is None:
        raise FortiBloxCrossSourceReconciliationError(f"{name} is required")
    if parsed > 1:
        raise FortiBloxCrossSourceReconciliationError(
            f"{name} must be <= 1"
        )
    return parsed


def _comparison(
    left: Decimal,
    right: Decimal,
    *,
    relative_tolerance: Decimal,
    absolute_tolerance: Decimal,
) -> dict[str, Any]:
    error = abs(left - right)
    denominator = max(abs(left), abs(right))
    relative_error = Decimal(0) if denominator == 0 else error / denominator
    allowed = max(absolute_tolerance, denominator * relative_tolerance)
    return {
        "fortiblox_value": format(left, "f"),
        "reference_value": format(right, "f"),
        "absolute_error": format(error, "f"),
        "relative_error": format(relative_error, "f"),
        "allowed_error": format(allowed, "f"),
        "within_tolerance": error <= allowed,
    }


def _find_fortiblox_token(
    normalized_tokens: Mapping[str, Any],
    mint: str,
) -> tuple[Mapping[str, Any], int | None]:
    if normalized_tokens.get("scope") != "fortiswap_token_universe_observation":
        raise FortiBloxCrossSourceReconciliationError(
            "FortiBlox input must be normalized fortiswap_token_universe_observation"
        )
    if normalized_tokens.get("execution_authorized") is not False:
        raise FortiBloxCrossSourceReconciliationError(
            "FortiBlox input must preserve execution_authorized=false"
        )

    rows = normalized_tokens.get("tokens")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        raise FortiBloxCrossSourceReconciliationError(
            "FortiBlox tokens must be a sequence"
        )

    matches = [
        row for row in rows
        if isinstance(row, Mapping) and _text(row.get("mint")) == mint
    ]
    if len(matches) != 1:
        raise FortiBloxCrossSourceReconciliationError(
            "FortiBlox input must contain exactly one matching mint"
        )

    updated = normalized_tokens.get("provider_updated_at_ms")
    if isinstance(updated, bool):
        updated = None
    elif updated is not None:
        try:
            updated = int(updated)
        except (TypeError, ValueError):
            updated = None
        if updated is not None and updated < 0:
            updated = None

    return matches[0], updated


def _reference_record(value: Any, *, mint: str) -> dict[str, Any]:
    row = _mapping(value, name="reference observation")
    source_id = _text(row.get("source_id"))
    if source_id not in ALLOWED_REFERENCE_SOURCES:
        raise FortiBloxCrossSourceReconciliationError(
            "reference source_id must be xdex, x1_ninja, or cmis"
        )
    reference_mint = _text(row.get("mint"))
    if reference_mint != mint:
        raise FortiBloxCrossSourceReconciliationError(
            f"reference mint mismatch for {source_id}"
        )
    if row.get("execution_authorized") is not False:
        raise FortiBloxCrossSourceReconciliationError(
            f"{source_id} reference must preserve execution_authorized=false"
        )

    return {
        "source_id": source_id,
        "mint": reference_mint,
        "price_usd": _decimal(
            row.get("price_usd"),
            name=f"{source_id}.price_usd",
            nonnegative=True,
        ),
        "price_comparable": row.get("price_comparable") is not False,
        "price_semantics_verified": row.get("price_semantics_verified") is True,
        "price_freshness_verified": row.get("price_freshness_verified") is True,
        "price_observed_at_ms": row.get("price_observed_at_ms"),
        "volume_24h_usd": _decimal(
            row.get("volume_24h_usd"),
            name=f"{source_id}.volume_24h_usd",
            nonnegative=True,
        ),
        "volume_comparable": row.get("volume_comparable") is not False,
        "volume_semantics_verified": row.get("volume_semantics_verified") is True,
        "volume_freshness_verified": row.get("volume_freshness_verified") is True,
        "volume_window_seconds": row.get("volume_window_seconds"),
        "volume_scope_id": _text(row.get("volume_scope_id")),
        "cmis_verified": row.get("cmis_verified") is True,
        "source_independence_verified": row.get("source_independence_verified") is True,
        "raw_authority_state": _text(row.get("authority_state")),
    }


def _price_reconciliation(
    fortiblox_price: Decimal | None,
    reference: Mapping[str, Any],
    *,
    relative_tolerance: Decimal,
    absolute_tolerance: Decimal,
    fortiblox_price_semantics_verified: bool,
    fortiblox_price_freshness_verified: bool,
) -> dict[str, Any]:
    source = reference["source_id"]
    reference_price = reference["price_usd"]

    if reference["price_comparable"] is not True:
        return {
            "field": "price_usd",
            "source_id": source,
            "state": NOT_COMPARABLE,
            "reason": "reference_marks_price_not_comparable",
            "current_fact_corroboration": False,
        }
    if fortiblox_price is None or reference_price is None:
        return {
            "field": "price_usd",
            "source_id": source,
            "state": EVIDENCE_INCOMPLETE,
            "reason": "price_value_missing",
            "current_fact_corroboration": False,
        }
    if not fortiblox_price_semantics_verified:
        return {
            "field": "price_usd",
            "source_id": source,
            "state": EVIDENCE_INCOMPLETE,
            "reason": "fortiblox_price_semantics_not_verified",
            "current_fact_corroboration": False,
        }
    if reference["price_semantics_verified"] is not True:
        return {
            "field": "price_usd",
            "source_id": source,
            "state": EVIDENCE_INCOMPLETE,
            "reason": "reference_price_semantics_not_verified",
            "current_fact_corroboration": False,
        }

    comparison = _comparison(
        fortiblox_price,
        reference_price,
        relative_tolerance=relative_tolerance,
        absolute_tolerance=absolute_tolerance,
    )
    state = AGREE if comparison["within_tolerance"] else DISAGREE
    freshness_aligned = bool(
        fortiblox_price_freshness_verified
        and reference["price_freshness_verified"] is True
    )
    return {
        "field": "price_usd",
        "source_id": source,
        "state": state,
        "reason": (
            "numeric_price_agreement_within_policy"
            if state == AGREE
            else "material_price_disagreement"
        ),
        **comparison,
        "fortiblox_price_freshness_verified": fortiblox_price_freshness_verified,
        "reference_price_freshness_verified": reference["price_freshness_verified"],
        "current_fact_corroboration": state == AGREE and freshness_aligned,
    }


def _volume_reconciliation(
    fortiblox_volume: Decimal | None,
    reference: Mapping[str, Any],
    *,
    relative_tolerance: Decimal,
    absolute_tolerance: Decimal,
    fortiblox_volume_semantics_verified: bool,
    fortiblox_volume_freshness_verified: bool,
    fortiblox_volume_window_seconds: int | None,
    fortiblox_volume_scope_id: str | None,
) -> dict[str, Any]:
    source = reference["source_id"]
    reference_volume = reference["volume_24h_usd"]

    if reference["volume_comparable"] is not True:
        return {
            "field": "volume_24h_usd",
            "source_id": source,
            "state": NOT_COMPARABLE,
            "reason": "reference_marks_volume_not_comparable",
            "current_fact_corroboration": False,
        }
    if fortiblox_volume is None or reference_volume is None:
        return {
            "field": "volume_24h_usd",
            "source_id": source,
            "state": EVIDENCE_INCOMPLETE,
            "reason": "volume_value_missing",
            "current_fact_corroboration": False,
        }
    if not fortiblox_volume_semantics_verified:
        return {
            "field": "volume_24h_usd",
            "source_id": source,
            "state": EVIDENCE_INCOMPLETE,
            "reason": "fortiblox_volume_semantics_not_verified",
            "current_fact_corroboration": False,
        }
    if reference["volume_semantics_verified"] is not True:
        return {
            "field": "volume_24h_usd",
            "source_id": source,
            "state": EVIDENCE_INCOMPLETE,
            "reason": "reference_volume_semantics_not_verified",
            "current_fact_corroboration": False,
        }

    if (
        fortiblox_volume_window_seconds != ROLLING_24H_SECONDS
        or reference["volume_window_seconds"] != ROLLING_24H_SECONDS
    ):
        return {
            "field": "volume_24h_usd",
            "source_id": source,
            "state": SCOPE_MISMATCH,
            "reason": "exact_rolling_24h_window_not_aligned",
            "current_fact_corroboration": False,
        }
    if (
        fortiblox_volume_scope_id is None
        or reference["volume_scope_id"] is None
        or fortiblox_volume_scope_id != reference["volume_scope_id"]
    ):
        return {
            "field": "volume_24h_usd",
            "source_id": source,
            "state": SCOPE_MISMATCH,
            "reason": "volume_scope_id_not_aligned",
            "current_fact_corroboration": False,
        }

    comparison = _comparison(
        fortiblox_volume,
        reference_volume,
        relative_tolerance=relative_tolerance,
        absolute_tolerance=absolute_tolerance,
    )
    state = AGREE if comparison["within_tolerance"] else DISAGREE
    freshness_aligned = bool(
        fortiblox_volume_freshness_verified
        and reference["volume_freshness_verified"] is True
    )
    return {
        "field": "volume_24h_usd",
        "source_id": source,
        "state": state,
        "reason": (
            "numeric_volume_agreement_within_exact_scope"
            if state == AGREE
            else "material_volume_disagreement"
        ),
        **comparison,
        "fortiblox_volume_freshness_verified": fortiblox_volume_freshness_verified,
        "reference_volume_freshness_verified": reference["volume_freshness_verified"],
        "current_fact_corroboration": state == AGREE and freshness_aligned,
    }


def accepted_fortiblox_token_field_evidence() -> dict[str, Any]:
    """Return the currently accepted FortiBlox token-field semantic boundary.

    The normalized provider contract accepts the provider-labeled priceUsd field
    as a USD price observation. It does not yet prove exact per-field fact time
    for price or exact rolling-window/scope semantics for volume24hUsd.
    """

    return {
        "contract_version": "fortiblox_token_field_evidence/v1",
        "price_semantics_verified": True,
        "price_freshness_verified": False,
        "volume_semantics_verified": False,
        "volume_freshness_verified": False,
        "volume_window_seconds": None,
        "volume_scope_id": None,
        "source_independence_verified": False,
        "cmis_verified": False,
        "execution_authorized": False,
    }


def reconcile_fortiblox_cross_source(
    *,
    mint: str,
    fortiblox_tokens_observation: Mapping[str, Any],
    references: Sequence[Mapping[str, Any]],
    fortiblox_field_evidence: Mapping[str, Any] | None = None,
    price_relative_tolerance: Any = DEFAULT_PRICE_RELATIVE_TOLERANCE,
    price_absolute_tolerance_usd: Any = DEFAULT_PRICE_ABSOLUTE_TOLERANCE_USD,
    volume_relative_tolerance: Any = DEFAULT_VOLUME_RELATIVE_TOLERANCE,
    volume_absolute_tolerance_usd: Any = DEFAULT_VOLUME_ABSOLUTE_TOLERANCE_USD,
) -> dict[str, Any]:
    """Reconcile one FortiBlox token against XDEX/X1.Ninja/CMIS evidence."""

    normalized_mint = _text(mint)
    if not normalized_mint:
        raise FortiBloxCrossSourceReconciliationError("mint is required")
    if not isinstance(references, Sequence) or isinstance(
        references, (str, bytes, bytearray)
    ):
        raise FortiBloxCrossSourceReconciliationError(
            "references must be a sequence"
        )
    if not references:
        raise FortiBloxCrossSourceReconciliationError(
            "at least one reference observation is required"
        )

    price_rel = _positive_tolerance(
        price_relative_tolerance,
        name="price_relative_tolerance",
    )
    price_abs = _positive_tolerance(
        price_absolute_tolerance_usd,
        name="price_absolute_tolerance_usd",
    )
    volume_rel = _positive_tolerance(
        volume_relative_tolerance,
        name="volume_relative_tolerance",
    )
    volume_abs = _positive_tolerance(
        volume_absolute_tolerance_usd,
        name="volume_absolute_tolerance_usd",
    )

    token, provider_updated_at_ms = _find_fortiblox_token(
        _mapping(
            fortiblox_tokens_observation,
            name="fortiblox_tokens_observation",
        ),
        normalized_mint,
    )
    field_evidence = (
        dict(fortiblox_field_evidence)
        if isinstance(fortiblox_field_evidence, Mapping)
        else {}
    )

    fortiblox_price = _decimal(
        token.get("price_usd"),
        name="fortiblox.price_usd",
        nonnegative=True,
    )
    fortiblox_volume = _decimal(
        token.get("volume_24h_usd"),
        name="fortiblox.volume_24h_usd",
        nonnegative=True,
    )
    fortiblox_sources = sorted(
        {
            str(item).strip().casefold()
            for item in list(token.get("sources") or [])
            if str(item).strip()
        }
    )

    parsed_references = [
        _reference_record(item, mint=normalized_mint)
        for item in references
    ]
    source_ids = [row["source_id"] for row in parsed_references]
    if len(set(source_ids)) != len(source_ids):
        raise FortiBloxCrossSourceReconciliationError(
            "reference source_id values must be unique"
        )

    fortiblox_price_semantics_verified = (
        field_evidence.get("price_semantics_verified") is True
    )
    fortiblox_price_freshness_verified = (
        field_evidence.get("price_freshness_verified") is True
    )
    fortiblox_volume_semantics_verified = (
        field_evidence.get("volume_semantics_verified") is True
    )
    fortiblox_volume_freshness_verified = (
        field_evidence.get("volume_freshness_verified") is True
    )

    window = field_evidence.get("volume_window_seconds")
    if isinstance(window, bool):
        window = None
    elif window is not None:
        try:
            window = int(window)
        except (TypeError, ValueError):
            window = None

    fortiblox_volume_scope_id = _text(
        field_evidence.get("volume_scope_id")
    )

    rows: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    agreements: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []

    for reference in parsed_references:
        price = _price_reconciliation(
            fortiblox_price,
            reference,
            relative_tolerance=price_rel,
            absolute_tolerance=price_abs,
            fortiblox_price_semantics_verified=fortiblox_price_semantics_verified,
            fortiblox_price_freshness_verified=fortiblox_price_freshness_verified,
        )
        volume = _volume_reconciliation(
            fortiblox_volume,
            reference,
            relative_tolerance=volume_rel,
            absolute_tolerance=volume_abs,
            fortiblox_volume_semantics_verified=fortiblox_volume_semantics_verified,
            fortiblox_volume_freshness_verified=fortiblox_volume_freshness_verified,
            fortiblox_volume_window_seconds=window,
            fortiblox_volume_scope_id=fortiblox_volume_scope_id,
        )

        overlap = reference["source_id"] in fortiblox_sources
        authority_preserved = bool(
            reference["source_id"] == "cmis"
            and reference["cmis_verified"] is True
        )
        row = {
            "source_id": reference["source_id"],
            "upstream_overlap_with_fortiblox": overlap,
            "source_independence_verified": False,
            "reference_source_independence_claim": (
                reference["source_independence_verified"] is True
            ),
            "reference_cmis_verified": reference["cmis_verified"] is True,
            "cmis_authority_preserved": authority_preserved,
            "price": price,
            "volume_24h_usd": volume,
            "execution_authorized": False,
        }
        rows.append(row)

        for field in (price, volume):
            if field["state"] == DISAGREE:
                disagreements.append(
                    {
                        "source_id": reference["source_id"],
                        "field": field["field"],
                        "reason": field["reason"],
                    }
                )
            elif field["state"] == AGREE:
                agreements.append(
                    {
                        "source_id": reference["source_id"],
                        "field": field["field"],
                        "current_fact_corroboration": (
                            field.get("current_fact_corroboration") is True
                        ),
                    }
                )
            else:
                incomplete.append(
                    {
                        "source_id": reference["source_id"],
                        "field": field["field"],
                        "state": field["state"],
                        "reason": field["reason"],
                    }
                )

    current_corroboration_count = sum(
        1 for row in agreements if row["current_fact_corroboration"]
    )
    overall_state = (
        "DISAGREEMENT"
        if disagreements
        else (
            "CORROBORATED"
            if agreements
            else "EVIDENCE_INCOMPLETE"
        )
    )

    cmis_reference = next(
        (row for row in parsed_references if row["source_id"] == "cmis"),
        None,
    )
    cmis_authoritative = bool(
        cmis_reference is not None and cmis_reference["cmis_verified"] is True
    )

    return {
        "contract_version": CONTRACT_VERSION,
        "chain": "x1",
        "mint": normalized_mint,
        "fortiblox_source": "app.fortiblox.com",
        "fortiblox_provider_updated_at_ms": provider_updated_at_ms,
        "fortiblox_provider_update_time_is_cross_source_fact_time": False,
        "fortiblox_upstream_sources": fortiblox_sources,
        "policy": {
            "price_relative_tolerance": format(price_rel, "f"),
            "price_absolute_tolerance_usd": format(price_abs, "f"),
            "volume_relative_tolerance": format(volume_rel, "f"),
            "volume_absolute_tolerance_usd": format(volume_abs, "f"),
            "volume_requires_exact_rolling_24h_window": True,
            "volume_requires_exact_scope_id": True,
        },
        "reconciliations": rows,
        "agreement_count": len(agreements),
        "current_fact_corroboration_count": current_corroboration_count,
        "disagreements": disagreements,
        "incomplete_or_scope_mismatched": incomplete,
        "overall_state": overall_state,
        "same_fact_agreement_is_source_independence": False,
        "source_independence_verified": False,
        "cmis_reference_authoritative": cmis_authoritative,
        "fortiblox_cmis_verified": False,
        "cmis_verification_promoted_from_agreement": False,
        "risk_conclusion_authorized": False,
        "recommendation_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "execution_authorized": False,
    }


__all__ = [
    "AGREE",
    "ALLOWED_REFERENCE_SOURCES",
    "CONTRACT_VERSION",
    "DEFAULT_PRICE_ABSOLUTE_TOLERANCE_USD",
    "DEFAULT_PRICE_RELATIVE_TOLERANCE",
    "DEFAULT_VOLUME_ABSOLUTE_TOLERANCE_USD",
    "DEFAULT_VOLUME_RELATIVE_TOLERANCE",
    "DISAGREE",
    "EVIDENCE_INCOMPLETE",
    "FortiBloxCrossSourceReconciliationError",
    "NOT_COMPARABLE",
    "ROLLING_24H_SECONDS",
    "SCOPE_MISMATCH",
    "accepted_fortiblox_token_field_evidence",
    "reconcile_fortiblox_cross_source",
]
