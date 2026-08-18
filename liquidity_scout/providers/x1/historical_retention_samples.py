"""Fail-closed retention sampling for isolated X1 historical comparisons."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from liquidity_scout.providers.x1.historical_comparison_evidence import HistoricalComparisonEvidence


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


def build_historical_retention_sample_set(
    samples: tuple[HistoricalComparisonEvidence, ...],
) -> HistoricalRetentionSampleSet:
    """Retain sparse historical observations without inferring archive coverage.

    Multiple successful samples can establish only that the explicitly requested
    slots were observed. They cannot prove the unsampled interval, chain-lifetime
    history, provider retention policy, or equivalent finality semantics.
    """
    if not isinstance(samples, tuple) or not samples:
        raise ValueError("samples must be a non-empty tuple")
    if not all(isinstance(sample, HistoricalComparisonEvidence) for sample in samples):
        raise TypeError("all samples must be HistoricalComparisonEvidence")

    official_source = samples[0].official_source
    secondary_source = samples[0].secondary_source
    if not official_source or not secondary_source or official_source == secondary_source:
        raise ValueError("samples require distinct non-empty source identities")

    seen_slots: set[int] = set()
    normalized: list[tuple[int, HistoricalComparisonEvidence]] = []
    for sample in samples:
        if sample.chain != "x1":
            raise ValueError("all samples must be X1 evidence")
        if sample.fact_type != "historical_block_identity_comparison":
            raise ValueError("unsupported historical fact type")
        if sample.official_source != official_source or sample.secondary_source != secondary_source:
            raise ValueError("all samples must use the same source pair")
        if sample.requested_slot in seen_slots:
            raise ValueError("duplicate requested slots are not allowed")
        seen_slots.add(sample.requested_slot)
        try:
            observed = datetime.fromisoformat(sample.observed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("sample observed_at must be ISO-8601") from exc
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("sample observed_at must be timezone-aware")
        normalized.append((sample.requested_slot, sample))

    normalized.sort(key=lambda item: item[0])
    ordered = tuple(sample for _, sample in normalized)
    slots = tuple(slot for slot, _ in normalized)

    all_same_fact = all(sample.same_fact_identity_verified for sample in ordered)
    independent = all(sample.source_independence_verified for sample in ordered)
    sampled_range_observed = all(
        sample.status in {"AGREEMENT", "CONFLICT"} and sample.data_quality == "HIGH"
        for sample in ordered
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
