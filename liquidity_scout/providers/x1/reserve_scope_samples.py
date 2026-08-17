"""Summarize repeated sanitized X1 reserve-scope evidence artifacts.

This module computes descriptive distributions and metric coverage only. It does
not recommend freshness thresholds, decide an acceptable provider age/slot
span, or promote any reserve fact. Artifacts must refer to one exact pool/vault
identity before their measurements may be summarized together.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any


VERSION = "1.0"
ARTIFACT_TYPE = "x1_reserve_scope_evidence"
ARTIFACT_VERSION = "1.0"
ROLES = ("asset", "counter")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _canonical(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _summary(values: list[Decimal]) -> dict[str, Any]:
    ordered = sorted(values)
    if not ordered:
        return {"available": 0, "min": None, "median": None, "max": None}
    middle = len(ordered) // 2
    if len(ordered) % 2:
        median = ordered[middle]
    else:
        median = (ordered[middle - 1] + ordered[middle]) / Decimal(2)
    return {
        "available": len(ordered),
        "min": _canonical(ordered[0]),
        "median": _canonical(median),
        "max": _canonical(ordered[-1]),
    }


def _identity(artifact: Mapping[str, Any]) -> tuple[Any, ...] | None:
    pool = _text(artifact.get("pool_address"))
    identity = artifact.get("identity")
    identity = identity if isinstance(identity, Mapping) else {}
    authority = _text(identity.get("shared_authority"))
    roles = artifact.get("roles")
    roles = roles if isinstance(roles, Mapping) else {}

    parts: list[Any] = [pool, authority]
    for role in ROLES:
        record = roles.get(role)
        record = record if isinstance(record, Mapping) else {}
        expected = record.get("expected_identity")
        expected = expected if isinstance(expected, Mapping) else {}
        parts.extend(
            [
                _text(expected.get("vault")),
                _text(expected.get("mint")),
                expected.get("decimals"),
                _text(expected.get("provider_field_path")),
            ]
        )
    if any(item is None for item in parts):
        return None
    return tuple(parts)


def _identity_record(identity: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "pool_address": identity[0],
        "shared_authority": identity[1],
        "asset": {
            "vault": identity[2],
            "mint": identity[3],
            "decimals": identity[4],
            "provider_field_path": identity[5],
        },
        "counter": {
            "vault": identity[6],
            "mint": identity[7],
            "decimals": identity[8],
            "provider_field_path": identity[9],
        },
    }


def _unavailable() -> dict[str, Any]:
    return {
        "service": "x1_reserve_scope_sample_summary",
        "version": VERSION,
        "chain": "x1",
        "status": "unavailable",
        "identity": None,
        "sample_count": 0,
        "scope_status_counts": {},
        "metrics": {},
        "coverage": {},
        "evidence_counts": {},
        "threshold_recommendation": None,
        "freshness_verified": False,
        "observation_scope_verified": False,
        "cmis_promotable": False,
        "warnings": ["no_scope_artifacts"],
        "errors": [],
    }


def summarize_x1_reserve_scope_artifacts(
    artifacts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize one identity-consistent set of reserve-scope artifacts."""
    if not isinstance(artifacts, list):
        raise TypeError("artifacts must be a list")
    if not artifacts:
        return _unavailable()

    validation_errors: list[str] = []
    identities: list[tuple[Any, ...]] = []
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, Mapping):
            validation_errors.append(f"artifact_{index}:not_a_mapping")
            continue
        if artifact.get("evidence_type") != ARTIFACT_TYPE:
            validation_errors.append(f"artifact_{index}:unexpected_evidence_type")
        if artifact.get("evidence_version") != ARTIFACT_VERSION:
            validation_errors.append(f"artifact_{index}:unexpected_evidence_version")
        if artifact.get("chain") != "x1":
            validation_errors.append(f"artifact_{index}:wrong_chain")
        if artifact.get("artifact_sanitized") is not True:
            validation_errors.append(f"artifact_{index}:artifact_not_sanitized")
        identity = _identity(artifact)
        if identity is None:
            validation_errors.append(f"artifact_{index}:identity_incomplete")
        else:
            identities.append(identity)

    if validation_errors:
        return {
            "service": "x1_reserve_scope_sample_summary",
            "version": VERSION,
            "chain": "x1",
            "status": "error",
            "identity": None,
            "sample_count": len(artifacts),
            "scope_status_counts": {},
            "metrics": {},
            "coverage": {},
            "evidence_counts": {},
            "threshold_recommendation": None,
            "freshness_verified": False,
            "observation_scope_verified": False,
            "cmis_promotable": False,
            "warnings": [],
            "errors": validation_errors,
        }

    first_identity = identities[0]
    if any(item != first_identity for item in identities[1:]):
        return {
            "service": "x1_reserve_scope_sample_summary",
            "version": VERSION,
            "chain": "x1",
            "status": "ambiguous",
            "identity": None,
            "sample_count": len(artifacts),
            "scope_status_counts": {},
            "metrics": {},
            "coverage": {},
            "evidence_counts": {},
            "threshold_recommendation": None,
            "freshness_verified": False,
            "observation_scope_verified": False,
            "cmis_promotable": False,
            "warnings": [],
            "errors": ["artifact_identity_mismatch"],
        }

    series: dict[str, list[Decimal]] = {
        "collection_duration_seconds": [],
        "provider_sync_age_seconds": [],
        "rpc_slot_span": [],
        "asset_balance_identity_slot_delta": [],
        "counter_balance_identity_slot_delta": [],
    }
    scope_statuses: Counter[str] = Counter()
    rpc_identity_verified_count = 0
    rpc_decimals_match_count = 0
    provider_observed_within_collection_count = 0
    artifact_with_warnings_count = 0
    artifact_with_errors_count = 0
    negative_provider_sync_age = False

    for artifact in artifacts:
        scope = artifact.get("scope")
        scope = scope if isinstance(scope, Mapping) else {}
        status = _text(scope.get("status")) or "unknown"
        scope_statuses[status] += 1
        metrics = scope.get("metrics")
        metrics = metrics if isinstance(metrics, Mapping) else {}
        roles = metrics.get("roles")
        roles = roles if isinstance(roles, Mapping) else {}

        values = {
            "collection_duration_seconds": metrics.get("collection_duration_seconds"),
            "provider_sync_age_seconds": metrics.get(
                "provider_reported_last_synced_age_at_collection_end_seconds"
            ),
            "rpc_slot_span": metrics.get("rpc_slot_span"),
            "asset_balance_identity_slot_delta": (
                roles.get("asset", {}).get("balance_identity_slot_delta")
                if isinstance(roles.get("asset"), Mapping)
                else None
            ),
            "counter_balance_identity_slot_delta": (
                roles.get("counter", {}).get("balance_identity_slot_delta")
                if isinstance(roles.get("counter"), Mapping)
                else None
            ),
        }
        for name, raw_value in values.items():
            parsed = _decimal(raw_value)
            if parsed is not None:
                series[name].append(parsed)
                if name == "provider_sync_age_seconds" and parsed < 0:
                    negative_provider_sync_age = True

        if metrics.get("provider_observed_within_collection") is True:
            provider_observed_within_collection_count += 1

        state = artifact.get("verification_state")
        state = state if isinstance(state, Mapping) else {}
        if state.get("rpc_identity_verified") is True:
            rpc_identity_verified_count += 1
        if state.get("rpc_decimals_match") is True:
            rpc_decimals_match_count += 1

        if artifact.get("warnings"):
            artifact_with_warnings_count += 1
        if artifact.get("errors"):
            artifact_with_errors_count += 1

    sample_count = len(artifacts)
    summaries = {name: _summary(values) for name, values in series.items()}
    coverage = {
        name: {"available": len(values), "total": sample_count}
        for name, values in series.items()
    }

    warnings: list[str] = []
    for name, counts in coverage.items():
        if counts["available"] < counts["total"]:
            warnings.append(f"partial_metric_coverage:{name}")
    if negative_provider_sync_age:
        warnings.append("negative_provider_sync_age_observed")
    if artifact_with_warnings_count:
        warnings.append("source_artifacts_contain_warnings")
    if artifact_with_errors_count:
        warnings.append("source_artifacts_contain_errors")

    complete_coverage = all(
        counts["available"] == sample_count for counts in coverage.values()
    )
    all_scope_ok = scope_statuses == Counter({"ok": sample_count})
    status = (
        "ok"
        if complete_coverage and all_scope_ok and not artifact_with_errors_count
        else "partial"
    )

    return {
        "service": "x1_reserve_scope_sample_summary",
        "version": VERSION,
        "chain": "x1",
        "status": status,
        "identity": _identity_record(first_identity),
        "sample_count": sample_count,
        "scope_status_counts": dict(sorted(scope_statuses.items())),
        "metrics": summaries,
        "coverage": coverage,
        "evidence_counts": {
            "rpc_identity_verified": rpc_identity_verified_count,
            "rpc_decimals_match": rpc_decimals_match_count,
            "provider_observed_within_collection": provider_observed_within_collection_count,
            "artifacts_with_warnings": artifact_with_warnings_count,
            "artifacts_with_errors": artifact_with_errors_count,
        },
        "threshold_recommendation": None,
        "freshness_verified": False,
        "observation_scope_verified": False,
        "cmis_promotable": False,
        "warnings": warnings,
        "errors": [],
    }


__all__ = [
    "ARTIFACT_TYPE",
    "ARTIFACT_VERSION",
    "ROLES",
    "VERSION",
    "summarize_x1_reserve_scope_artifacts",
]
