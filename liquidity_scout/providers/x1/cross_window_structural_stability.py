"""CMIS v1.4.6 — cross-window structural stability.

v1.4.5 separated structural AMM layout identity from execution scope. v1.4.6
checks whether the same candidate pair and structural BUY/SELL layouts persist
across nested 1h, 6h, and 24h windows sharing one end time.

This phase is intentionally conservative:
- every requested window must have proven history coverage;
- candidate-pair identity changes are conflicts, not silently merged;
- a direction needs evidence in at least two windows to be called cross-window
  stable;
- every observed directional structural fingerprint must already be stable
  inside its own window;
- missing directional activity is "no evidence", not a contradiction.

No canonical vault mapping or exact pool-leg semantics are promoted here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from liquidity_scout.providers.x1.structural_fingerprint_identity import (
    evaluate_structural_fingerprint_identity,
)

VERSION = "1.4.6"
WINDOWS = (
    ("1h", 3600),
    ("6h", 21600),
    ("24h", 86400),
)


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _pair_key(leading: Mapping[str, Any] | None):
    if not isinstance(leading, Mapping):
        return None
    values = (
        _text(leading.get("asset_account")),
        _text(leading.get("counter_account")),
        _text(leading.get("counter_mint")),
        _text(leading.get("shared_owner")),
    )
    return values if all(values) else None


def _fingerprint_key(fingerprint: Mapping[str, Any] | None):
    if not isinstance(fingerprint, Mapping):
        return None
    return (
        _text(fingerprint.get("program_id")),
        fingerprint.get("pool_position"),
        fingerprint.get("asset_position"),
        fingerprint.get("counter_position"),
    )


def _fingerprint_dict(key):
    if key is None:
        return None
    return {
        "program_id": key[0],
        "pool_position": key[1],
        "asset_position": key[2],
        "counter_position": key[3],
    }


def _range_proven(report: Mapping[str, Any]) -> bool:
    source = report.get("source_attribution")
    source = source if isinstance(source, Mapping) else {}
    baseline = source.get("baseline")
    baseline = baseline if isinstance(baseline, Mapping) else {}
    proof_scan = source.get("proof_scan")
    proof_scan = proof_scan if isinstance(proof_scan, Mapping) else {}

    if baseline.get("range_proven") is not True:
        return False
    # no-candidate reports may legitimately omit the second proof scan.
    if proof_scan and proof_scan.get("range_proven") is not True:
        return False
    return True


def _direction_rows(report: Mapping[str, Any]):
    rows = report.get("directions")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return []
    return [item for item in rows if isinstance(item, Mapping)]


def evaluate_cross_window_structural_stability(
    *,
    pool_address: str,
    asset_mint: str,
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
    min_evidence_windows: int = 2,
    structural_provider: Callable[..., Mapping[str, Any]] = (
        evaluate_structural_fingerprint_identity
    ),
) -> dict[str, Any]:
    """Compare v1.4.5 structural evidence across 1h/6h/24h windows."""

    if (
        isinstance(min_evidence_windows, bool)
        or not isinstance(min_evidence_windows, int)
        or min_evidence_windows < 2
        or min_evidence_windows > len(WINDOWS)
    ):
        raise ValueError("min_evidence_windows must be 2 or 3")

    try:
        end_epoch = float(end_epoch)
    except (TypeError, ValueError):
        raise ValueError("end_epoch must be numeric")
    if end_epoch < 0:
        raise ValueError("end_epoch must be non-negative")

    window_reports = []
    for label, duration in WINDOWS:
        kwargs = {
            "pool_address": pool_address,
            "asset_mint": asset_mint,
            "start_epoch": end_epoch - duration,
            "end_epoch": end_epoch,
            "pair": pair,
            "page_size": page_size,
            "max_signatures": max_signatures,
            "min_occurrences": min_occurrences,
            "min_coverage_ratio": min_coverage_ratio,
            "min_opposite_direction_ratio": (
                min_opposite_direction_ratio
            ),
            "min_direction_occurrences": min_direction_occurrences,
            "min_fingerprint_ratio": min_fingerprint_ratio,
            "min_dominance_margin": min_dominance_margin,
            "min_structural_fingerprint_ratio": (
                min_structural_fingerprint_ratio
            ),
        }
        if rpc_url is not None:
            kwargs["rpc_url"] = rpc_url

        raw = structural_provider(**kwargs)
        report = dict(raw) if isinstance(raw, Mapping) else {}
        window_reports.append(
            {
                "label": label,
                "duration_seconds": duration,
                "start_epoch": end_epoch - duration,
                "end_epoch": end_epoch,
                "range_proven": _range_proven(report),
                "status": report.get("status"),
                "leading_pair": report.get("leading_pair"),
                "summary": report.get("summary"),
                "directions": _direction_rows(report),
                "report": report,
            }
        )

    all_ranges_proven = all(
        item["range_proven"] is True for item in window_reports
    )

    pair_observations = []
    for item in window_reports:
        key = _pair_key(item["leading_pair"])
        if key is not None:
            pair_observations.append((item["label"], key))

    pair_keys = {key for _label, key in pair_observations}
    pair_conflict = len(pair_keys) > 1
    pair_evidence_window_count = len(pair_observations)
    pair_cross_window_stable = bool(
        not pair_conflict
        and pair_evidence_window_count >= min_evidence_windows
    )
    stable_pair_key = (
        next(iter(pair_keys))
        if pair_cross_window_stable and pair_keys
        else None
    )

    direction_results = []
    for direction in ("BUY", "SELL"):
        observations = []
        for item in window_reports:
            for row in item["directions"]:
                if _text(row.get("direction")) != direction:
                    continue
                fp_key = _fingerprint_key(
                    row.get("dominant_structural_fingerprint")
                )
                observations.append(
                    {
                        "window": item["label"],
                        "transaction_count": int(
                            row.get("transaction_count") or 0
                        ),
                        "sufficient_sample": (
                            row.get("sufficient_sample") is True
                        ),
                        "structural_fingerprint_stable": (
                            row.get(
                                "structural_fingerprint_stable"
                            ) is True
                        ),
                        "dominant_structural_fingerprint": (
                            _fingerprint_dict(fp_key)
                        ),
                        "fingerprint_key": fp_key,
                        "scope_variation_observed": (
                            row.get("scope_variation_observed") is True
                        ),
                        "scope_only_variant_observed": (
                            row.get(
                                "scope_only_variant_observed"
                            ) is True
                        ),
                        "non_scope_structural_variant_observed": (
                            row.get(
                                "non_scope_structural_variant_observed"
                            ) is True
                        ),
                    }
                )

        evidence = [
            item for item in observations
            if item["transaction_count"] > 0
            and item["fingerprint_key"] is not None
        ]
        fp_keys = {
            item["fingerprint_key"] for item in evidence
        }
        enough_windows = len(evidence) >= min_evidence_windows
        all_window_stable = bool(
            evidence
            and all(
                item["sufficient_sample"]
                and item["structural_fingerprint_stable"]
                for item in evidence
            )
        )
        fingerprint_conflict = len(fp_keys) > 1
        cross_window_stable = bool(
            enough_windows
            and all_window_stable
            and not fingerprint_conflict
        )
        stable_key = (
            next(iter(fp_keys))
            if cross_window_stable and fp_keys
            else None
        )

        direction_results.append(
            {
                "direction": direction,
                "evidence_window_count": len(evidence),
                "min_evidence_windows": min_evidence_windows,
                "sufficient_cross_window_evidence": enough_windows,
                "all_observed_windows_structurally_stable": (
                    all_window_stable
                ),
                "structural_fingerprint_conflict_observed": (
                    fingerprint_conflict
                ),
                "cross_window_structural_fingerprint_stable": (
                    cross_window_stable
                ),
                "stable_structural_fingerprint": _fingerprint_dict(
                    stable_key
                ),
                "window_observations": [
                    {
                        key: value
                        for key, value in item.items()
                        if key != "fingerprint_key"
                    }
                    for item in observations
                ],
            }
        )

    observed_directions = [
        item for item in direction_results
        if item["evidence_window_count"] > 0
    ]
    directions_with_enough_evidence = [
        item for item in observed_directions
        if item["sufficient_cross_window_evidence"]
    ]
    directional_conflict = any(
        item["structural_fingerprint_conflict_observed"]
        for item in observed_directions
    )
    all_eligible_directions_stable = bool(
        directions_with_enough_evidence
        and all(
            item["cross_window_structural_fingerprint_stable"]
            for item in directions_with_enough_evidence
        )
    )

    cross_window_stability_observed = bool(
        all_ranges_proven
        and pair_cross_window_stable
        and not directional_conflict
        and all_eligible_directions_stable
    )

    status = (
        "cross_window_structural_stability_observed"
        if cross_window_stability_observed
        else "cross_window_conflict_observed"
        if pair_conflict or directional_conflict
        else "insufficient_cross_window_evidence"
    )

    return {
        "service": "cross_window_structural_stability",
        "version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "pair": pair,
        "asset_mint": asset_mint,
        "status": status,
        "windows": [
            {
                key: value
                for key, value in item.items()
                if key != "report"
            }
            for item in window_reports
        ],
        "pair_identity": {
            "evidence_window_count": pair_evidence_window_count,
            "min_evidence_windows": min_evidence_windows,
            "pair_identity_conflict_observed": pair_conflict,
            "cross_window_pair_identity_stable": (
                pair_cross_window_stable
            ),
            "stable_pair_identity": (
                None
                if stable_pair_key is None
                else {
                    "asset_account": stable_pair_key[0],
                    "counter_account": stable_pair_key[1],
                    "counter_mint": stable_pair_key[2],
                    "shared_owner": stable_pair_key[3],
                }
            ),
            "observations": [
                {
                    "window": label,
                    "asset_account": key[0],
                    "counter_account": key[1],
                    "counter_mint": key[2],
                    "shared_owner": key[3],
                }
                for label, key in pair_observations
            ],
        },
        "directions": direction_results,
        "summary": {
            "all_requested_window_ranges_proven": all_ranges_proven,
            "cross_window_pair_identity_stable": (
                pair_cross_window_stable
            ),
            "directional_structural_conflict_observed": (
                directional_conflict
            ),
            "eligible_direction_count": len(
                directions_with_enough_evidence
            ),
            "all_eligible_directions_cross_window_stable": (
                all_eligible_directions_stable
            ),
            "cross_window_structural_stability_observed": (
                cross_window_stability_observed
            ),
            "cross_window_identity_promoted": False,
            "canonical_vault_mapping_proven": False,
            "canonical_vault_mapping_promoted": False,
            "exact_pool_leg_semantics_promoted": False,
            "interpretation": (
                "v1.4.6 compares the same candidate pair and structural "
                "BUY/SELL fingerprints across nested 1h, 6h, and 24h "
                "windows sharing one end time. Missing directional activity "
                "is not a contradiction. Conflicting pair identities or "
                "structural fingerprints block stability. Promotion remains "
                "disabled."
            ),
        },
        "source_reports": {
            item["label"]: item["report"]
            for item in window_reports
        },
    }


__all__ = [
    "VERSION",
    "WINDOWS",
    "evaluate_cross_window_structural_stability",
]
