"""Build a sanitized replayable artifact from X1 reserve scope evidence.

The artifact contract deliberately selects only public identity, provider value,
RPC amount/slot, collection timing, and deterministic scope-measurement fields.
It does not copy raw HTTP/RPC payloads, request URLs, headers, credentials, or
other transport internals.

An artifact is evidence for later analysis. It is never CMIS-promotable by
itself, even if an upstream object contains a promotion claim.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


VERSION = "1.0"
ROLES = ("asset", "counter")
BUNDLE_SERVICE = "x1_reserve_live_evidence"
SCOPE_SERVICE = "x1_reserve_scope_measurements"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _safe_sequence(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        result.append(
            {
                "step": _text(item.get("step")),
                "completed_at": item.get("completed_at"),
                "provider_observed_at": item.get("provider_observed_at"),
                "slot": item.get("slot"),
            }
        )
    return result


def _safe_scope_metrics(scope: Mapping[str, Any]) -> dict[str, Any]:
    metrics = scope.get("metrics")
    metrics = metrics if isinstance(metrics, Mapping) else {}
    roles = metrics.get("roles")
    roles = roles if isinstance(roles, Mapping) else {}

    safe_roles: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        item = roles.get(role)
        item = item if isinstance(item, Mapping) else {}
        safe_roles[role] = {
            "balance_slot": item.get("balance_slot"),
            "identity_slot": item.get("identity_slot"),
            "balance_identity_slot_delta": item.get(
                "balance_identity_slot_delta"
            ),
            "balance_identity_same_slot": item.get("balance_identity_same_slot"),
            "rpc_identity_verified": item.get("rpc_identity_verified") is True,
            "rpc_decimals_match": item.get("rpc_decimals_match") is True,
        }

    return {
        "collection_started_at": metrics.get("collection_started_at"),
        "collection_ended_at": metrics.get("collection_ended_at"),
        "collection_duration_seconds": metrics.get("collection_duration_seconds"),
        "collection_sequence_monotonic": metrics.get(
            "collection_sequence_monotonic"
        ),
        "provider_observed_at": metrics.get("provider_observed_at"),
        "provider_observed_within_collection": metrics.get(
            "provider_observed_within_collection"
        ),
        "provider_reported_last_synced_at": metrics.get(
            "provider_reported_last_synced_at"
        ),
        "provider_reported_last_synced_epoch_seconds": metrics.get(
            "provider_reported_last_synced_epoch_seconds"
        ),
        "provider_reported_last_synced_age_at_collection_end_seconds": metrics.get(
            "provider_reported_last_synced_age_at_collection_end_seconds"
        ),
        "provider_last_updated_raw": metrics.get("provider_last_updated_raw"),
        "rpc_min_slot": metrics.get("rpc_min_slot"),
        "rpc_max_slot": metrics.get("rpc_max_slot"),
        "rpc_slot_span": metrics.get("rpc_slot_span"),
        "roles": safe_roles,
    }


def build_x1_reserve_scope_artifact(
    bundle: Mapping[str, Any],
    scope: Mapping[str, Any],
) -> dict[str, Any]:
    """Return one sanitized, replayable reserve-scope evidence artifact."""
    if not isinstance(bundle, Mapping):
        raise TypeError("bundle must be a mapping")
    if not isinstance(scope, Mapping):
        raise TypeError("scope must be a mapping")
    if bundle.get("service") != BUNDLE_SERVICE:
        raise ValueError("unexpected reserve evidence bundle service")
    if scope.get("service") != SCOPE_SERVICE:
        raise ValueError("unexpected reserve scope measurement service")
    if bundle.get("chain") != "x1" or scope.get("chain") != "x1":
        raise ValueError("reserve scope artifact inputs must be for x1")

    pool_address = _text(bundle.get("pool_address"))
    scope_pool = _text(scope.get("pool_address"))
    if pool_address is None:
        raise ValueError("bundle pool_address is required")
    if scope_pool != pool_address:
        raise ValueError("scope pool_address does not match bundle")

    collection = bundle.get("collection")
    collection = collection if isinstance(collection, Mapping) else {}
    provider = bundle.get("provider")
    provider = provider if isinstance(provider, Mapping) else {}
    bundle_roles = bundle.get("roles")
    bundle_roles = bundle_roles if isinstance(bundle_roles, Mapping) else {}

    artifact_roles: dict[str, dict[str, Any]] = {}
    authorities: list[str] = []
    artifact_warnings: list[str] = []

    for role in ROLES:
        role_record = bundle_roles.get(role)
        if not isinstance(role_record, Mapping):
            raise ValueError(f"{role} bundle role is required")
        expected = role_record.get("expected")
        if not isinstance(expected, Mapping):
            raise ValueError(f"{role} expected identity is required")
        balance = role_record.get("rpc_balance")
        balance = balance if isinstance(balance, Mapping) else {}
        identity_observation = role_record.get("rpc_identity_observation")
        identity_observation = (
            identity_observation
            if isinstance(identity_observation, Mapping)
            else {}
        )
        identity_verification = role_record.get("rpc_identity_verification")
        identity_verification = (
            identity_verification
            if isinstance(identity_verification, Mapping)
            else {}
        )

        authority = _text(expected.get("shared_authority"))
        if authority:
            authorities.append(authority)

        artifact_roles[role] = {
            "expected_identity": {
                "vault": _text(expected.get("vault")),
                "mint": _text(expected.get("mint")),
                "decimals": expected.get("decimals"),
                "shared_authority": authority,
                "provider_field_path": _text(expected.get("provider_field_path")),
            },
            "provider_raw_value": role_record.get("provider_raw_value"),
            "rpc_balance": {
                "source": _text(balance.get("source")),
                "method": _text(balance.get("method")),
                "account": _text(balance.get("account")),
                "slot": balance.get("slot"),
                "amount": balance.get("amount"),
                "decimals": balance.get("decimals"),
                "ui_amount_string": balance.get("ui_amount_string"),
            },
            "rpc_identity": {
                "source": _text(identity_observation.get("source")),
                "method": _text(identity_observation.get("method")),
                "encoding": _text(identity_observation.get("encoding")),
                "account": _text(identity_observation.get("account")),
                "slot": identity_observation.get("slot"),
                "mint": _text(identity_observation.get("mint")),
                "authority": _text(identity_observation.get("authority")),
                "identity_verified": (
                    identity_verification.get("identity_verified") is True
                ),
                "rejection_reasons": _strings(
                    identity_verification.get("rejection_reasons")
                ),
            },
            "rpc_decimals_match": role_record.get("rpc_decimals_match") is True,
        }

    shared_authority_consistent = bool(authorities) and len(set(authorities)) == 1
    if not shared_authority_consistent:
        artifact_warnings.append("expected_shared_authority_inconsistent_or_missing")

    scope_flags = scope.get("evidence_flags")
    scope_flags = scope_flags if isinstance(scope_flags, Mapping) else {}

    artifact = {
        "evidence_type": "x1_reserve_scope_evidence",
        "evidence_version": VERSION,
        "chain": "x1",
        "pool_address": pool_address,
        "identity": {
            "shared_authority": authorities[0] if shared_authority_consistent else None,
            "shared_authority_consistent": shared_authority_consistent,
        },
        "collection": {
            "started_at": collection.get("started_at"),
            "ended_at": collection.get("ended_at"),
            "duration_seconds": collection.get("duration_seconds"),
            "sequence": _safe_sequence(collection.get("sequence")),
        },
        "provider": {
            "source": _text(provider.get("source")),
            "observed_at": provider.get("observed_at"),
            "last_synced_at": provider.get("last_synced_at"),
            "last_updated": provider.get("last_updated"),
        },
        "roles": artifact_roles,
        "scope": {
            "status": _text(scope.get("status")),
            "metrics": _safe_scope_metrics(scope),
            "warnings": _strings(scope.get("warnings")),
            "errors": _strings(scope.get("errors")),
        },
        "verification_state": {
            "rpc_identity_verified": bundle.get("rpc_identity_verified") is True,
            "rpc_decimals_match": bundle.get("rpc_decimals_match") is True,
            "scope_rpc_identity_verified": (
                scope_flags.get("rpc_identity_verified") is True
            ),
            "scope_rpc_decimals_match": scope_flags.get("rpc_decimals_match") is True,
            "reserve_field_semantics_verified": (
                bundle.get("reserve_field_semantics_verified") is True
            ),
            "value_agreement_verified": bundle.get("value_agreement_verified") is True,
            "freshness_verified": scope.get("freshness_verified") is True,
            "observation_scope_verified": (
                scope.get("observation_scope_verified") is True
            ),
            "upstream_bundle_cmis_promotable": bundle.get("cmis_promotable") is True,
            "upstream_scope_cmis_promotable": scope.get("cmis_promotable") is True,
        },
        "artifact_sanitized": True,
        "cmis_promotable": False,
        "warnings": list(
            dict.fromkeys(
                artifact_warnings
                + _strings(bundle.get("warnings"))
                + _strings(scope.get("warnings"))
            )
        ),
        "errors": list(
            dict.fromkeys(
                _strings(bundle.get("errors")) + _strings(scope.get("errors"))
            )
        ),
    }
    return artifact


__all__ = [
    "BUNDLE_SERVICE",
    "ROLES",
    "SCOPE_SERVICE",
    "VERSION",
    "build_x1_reserve_scope_artifact",
]
