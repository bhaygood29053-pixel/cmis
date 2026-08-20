"""Sanitized evidence envelope for one X1 historical same-fact comparison."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from liquidity_scout.providers.x1.historical_block_comparison import HistoricalBlockComparison


@dataclass(frozen=True)
class HistoricalComparisonEvidence:
    schema_version: str
    fact_type: str
    subject_id: str
    chain: str
    requested_slot: int
    observed_at: str
    status: str
    official_source: str
    secondary_source: str
    compared_fields: tuple[str, ...]
    conflicts: tuple[str, ...]
    same_fact_identity_verified: bool
    source_independence_verified: bool | None
    data_quality: str
    archival_completeness_verified: bool = False
    retention_verified: bool = False
    finality_semantics_verified: bool = False
    cmis_promotable: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalize_observed_at(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise TypeError("observed_at must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_historical_comparison_evidence(
    comparison: HistoricalBlockComparison,
    *, observed_at: datetime,
) -> HistoricalComparisonEvidence:
    if not isinstance(comparison, HistoricalBlockComparison):
        raise TypeError("comparison must be a HistoricalBlockComparison")
    if comparison.status not in {"AGREEMENT", "CONFLICT", "INSUFFICIENT_EVIDENCE"}:
        raise ValueError("unsupported historical comparison status")
    if comparison.source_independence_verified is not None and not isinstance(
        comparison.source_independence_verified, bool
    ):
        raise TypeError("source_independence_verified must be a boolean or None")

    if comparison.status == "INSUFFICIENT_EVIDENCE":
        quality = "LOW"
    elif (
        comparison.same_fact_identity_verified
        and comparison.source_independence_verified is True
    ):
        quality = "HIGH"
    else:
        quality = "LOW"

    return HistoricalComparisonEvidence(
        schema_version="x1_historical_comparison_evidence.v2",
        fact_type="historical_block_identity_comparison",
        subject_id=f"x1:block:{comparison.requested_slot}",
        chain="x1",
        requested_slot=comparison.requested_slot,
        observed_at=_normalize_observed_at(observed_at),
        status=comparison.status,
        official_source=comparison.official_source,
        secondary_source=comparison.secondary_source,
        compared_fields=comparison.compared_fields,
        conflicts=comparison.conflicts,
        same_fact_identity_verified=comparison.same_fact_identity_verified,
        source_independence_verified=comparison.source_independence_verified,
        data_quality=quality,
    )


__all__ = ["HistoricalComparisonEvidence", "build_historical_comparison_evidence"]
