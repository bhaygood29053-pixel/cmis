"""Fail-closed retention sampling for isolated X1 historical comparisons."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from liquidity_scout.providers.x1.historical_comparison_evidence import HistoricalComparisonEvidence


_ALLOWED_STATUSES = frozenset({"AGREEMENT", "CONFLICT", "INSUFFICIENT_EVIDENCE"})
_ALLOWED_QUALITIES = frozenset({"HIGH", "LOW"})
_SUPPORTED_EVIDENCE_SCHEMA_VERSIONS = frozenset({
    "x1_historical_comparison_evidence.v1",
    "x1_historical_comparison_evidence.v2",
})
_REQUIRED_BLOCK_IDENTITY_FIELDS = frozenset({"blockhash", "previous_blockhash", "parent_slot"})
_ALLOWED_COMPARED_FIELDS = _REQUIRED_BLOCK_IDENTITY_FIELDS | {"block_height"}


@dataclass(frozen=True)
class HistoricalRetentionSampleSet:
    schema_version: str
    chain: str
    official_source: str
    secondary_source: str
    sample_count: int
    requested_slots: tuple[int, ...]
    earliest_requested_slot: int
    latest_requested_slot: int
    statuses: tuple[str, ...]
    observed_at: tuple[str, ...]
    all_samples_same_fact_verified: bool
    source_independence_verified: bool
    sampled_range_observed: bool
    continuous_coverage_verified: bool = False
    archival_completeness_verified: bool = False
    retention_verified: bool = False
    finality_semantics_verified: bool = False
    cmis_promotable: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _validate_source_identity(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty source identity")
    if value != value.strip():
        raise ValueError(f"{field_name} must be canonical without surrounding whitespace")
    return value


def _validate_sample_integrity(sample: HistoricalComparisonEvidence) -> None:
    if sample.schema_version not in _SUPPORTED_EVIDENCE_SCHEMA_VERSIONS:
        raise ValueError("unsupported historical evidence schema version")
    if sample.chain != "x1":
        raise ValueError("all samples must be X1 evidence")
    if sample.fact_type != "historical_block_identity_comparison":
        raise ValueError("unsupported historical fact type")
    if isinstance(sample.requested_slot, bool) or not isinstance(sample.requested_slot, int) or sample.requested_slot < 0:
        raise ValueError("sample requested_slot must be a non-negative integer")
    if sample.subject_id != f"x1:block:{sample.requested_slot}":
        raise ValueError("sample subject_id does not match requested_slot")

    official_source = _validate_source_identity(sample.official_source, field_name="official_source")
    secondary_source = _validate_source_identity(sample.secondary_source, field_name="secondary_source")
    if official_source == secondary_source:
        raise ValueError("sample requires distinct source identities")

    if sample.status not in _ALLOWED_STATUSES:
        raise ValueError("unsupported historical comparison status")
    if sample.data_quality not in _ALLOWED_QUALITIES:
        raise ValueError("unsupported historical comparison data quality")

    if not isinstance(sample.compared_fields, tuple) or not isinstance(sample.conflicts, tuple):
        raise ValueError("historical comparison fields and conflicts must be tuples")
    if len(set(sample.compared_fields)) != len(sample.compared_fields):
        raise ValueError("historical comparison fields must not contain duplicates")
    if any(field not in _ALLOWED_COMPARED_FIELDS for field in sample.compared_fields):
        raise ValueError("historical comparison contains unsupported compared fields")
    if any(field not in sample.compared_fields for field in sample.conflicts):
        raise ValueError("historical conflicts must be a subset of compared fields")

    unsupported_promotions = (
        sample.archival_completeness_verified,
        sample.retention_verified,
        sample.finality_semantics_verified,
        sample.cmis_promotable,
    )
    if any(unsupported_promotions):
        raise ValueError("historical sample contains unsupported promotion or completeness flags")

    if sample.status in {"AGREEMENT", "CONFLICT"}:
        if not sample.same_fact_identity_verified or not sample.source_independence_verified:
            raise ValueError("observed historical sample requires verified fact identity and source independence")
        if sample.data_quality != "HIGH":
            raise ValueError("observed historical sample must have HIGH data quality")
        if not _REQUIRED_BLOCK_IDENTITY_FIELDS.issubset(sample.compared_fields):
            raise ValueError("observed historical sample is missing required block identity fields")
        if sample.status == "AGREEMENT" and sample.conflicts:
            raise ValueError("AGREEMENT historical sample must not contain conflicts")
        if sample.status == "CONFLICT" and not sample.conflicts:
            raise ValueError("CONFLICT historical sample must identify at least one conflict")
    else:
        if sample.same_fact_identity_verified:
            raise ValueError("insufficient historical evidence cannot claim verified same-fact identity")
        if sample.data_quality != "LOW":
            raise ValueError("insufficient historical evidence must have LOW data quality")
        if sample.compared_fields or sample.conflicts:
            raise ValueError("insufficient historical evidence must not claim compared fields or conflicts")

    if not isinstance(sample.observed_at, str) or not sample.observed_at.endswith("Z"):
        raise ValueError("sample observed_at must be canonical UTC ISO-8601 ending in Z")
    try:
        observed = datetime.fromisoformat(sample.observed_at[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("sample observed_at must be ISO-8601") from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("sample observed_at must be timezone-aware")


def build_historical_retention_sample_set(
    samples: tuple[HistoricalComparisonEvidence, ...],
) -> HistoricalRetentionSampleSet:
    if not isinstance(samples, tuple) or not samples:
        raise ValueError("samples must be a non-empty tuple")
    if not all(isinstance(sample, HistoricalComparisonEvidence) for sample in samples):
        raise TypeError("all samples must be HistoricalComparisonEvidence")

    for sample in samples:
        _validate_sample_integrity(sample)

    official_source = samples[0].official_source
    secondary_source = samples[0].secondary_source

    seen_slots: set[int] = set()
    normalized: list[tuple[int, HistoricalComparisonEvidence]] = []
    for sample in samples:
        if sample.official_source != official_source or sample.secondary_source != secondary_source:
            raise ValueError("all samples must use the same source pair")
        if sample.requested_slot in seen_slots:
            raise ValueError("duplicate requested slots are not allowed")
        seen_slots.add(sample.requested_slot)
        normalized.append((sample.requested_slot, sample))

    normalized.sort(key=lambda item: item[0])
    ordered = tuple(sample for _, sample in normalized)
    slots = tuple(slot for slot, _ in normalized)

    all_same_fact = all(sample.same_fact_identity_verified for sample in ordered)
    independent = all(sample.source_independence_verified for sample in ordered)
    sampled_range_observed = len(ordered) >= 2 and all(
        sample.status in {"AGREEMENT", "CONFLICT"} for sample in ordered
    )

    return HistoricalRetentionSampleSet(
        schema_version="x1_historical_retention_samples.v1",
        chain="x1",
        official_source=official_source,
        secondary_source=secondary_source,
        sample_count=len(ordered),
        requested_slots=slots,
        earliest_requested_slot=slots[0],
        latest_requested_slot=slots[-1],
        statuses=tuple(sample.status for sample in ordered),
        observed_at=tuple(sample.observed_at for sample in ordered),
        all_samples_same_fact_verified=all_same_fact,
        source_independence_verified=independent,
        sampled_range_observed=sampled_range_observed,
    )


__all__ = ["HistoricalRetentionSampleSet", "build_historical_retention_sample_set"]
