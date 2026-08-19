"""Deterministic machine-readable CMIS evidence receipts.

Receipts summarize only evidence already present in a completed CMIS service
response.  They never fetch providers, infer missing semantics, promote a
provider assertion, or reinterpret risk.  Missing proof remains explicit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import hashlib
import json
import math
from typing import Any


SCHEMA_VERSION = 1
_VERIFICATION_STATUSES = frozenset({
    "AGREEMENT",
    "CONFLICT",
    "INSUFFICIENT_EVIDENCE",
})
_ASSET_FIELDS = (
    "canonical_id",
    "symbol",
    "name",
    "mint",
    "address",
    "role",
)
_SOURCE_FIELDS = (
    "source",
    "role",
    "source_role",
    "observed_at",
    "block_slot",
    "slot",
    "context_slot",
    "block_height",
    "calculation_version",
)
_EVIDENCE_FLAG_SUFFIXES = (
    "_verified",
    "_complete",
    "_proven",
    "_eligible",
    "_promotable",
)
_SCOPE_PATHS = (
    ("data", "activity_window", "effective_coverage_scope"),
    ("data", "effective_coverage_scope"),
    ("data", "verification_scope"),
    ("data", "coverage_scope"),
    ("data", "scope"),
    ("data", "coverage"),
    ("confidence", "effective_coverage_scope"),
    ("confidence", "coverage_scope"),
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return None


def _safe_asset(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for field in _ASSET_FIELDS:
        scalar = _safe_scalar(value.get(field))
        if scalar is not None:
            result[field] = scalar
    return result


def _safe_source(value: Any, *, evidence_class: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    record: dict[str, Any] = {"evidence_class": evidence_class}
    for field in _SOURCE_FIELDS:
        scalar = _safe_scalar(value.get(field))
        if scalar is not None:
            record[field] = scalar
    # Existing evidence observations use `source_role`, while service sources
    # generally use `role`. Preserve both exactly instead of normalizing one
    # into the other and accidentally changing provider semantics.
    return record if len(record) > 1 else {}


def _messages(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    result: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, Mapping):
            record: dict[str, str] = {}
            for field in ("code", "message"):
                text = _text(item.get(field))
                if text is not None:
                    record[field] = text
            if record:
                result.append(record)
        else:
            text = _text(item)
            if text is not None:
                result.append({"message": text})
    return result


def _path_get(root: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = root
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _walk_evidence_flags(value: Any, *, prefix: str = "") -> dict[str, bool]:
    result: dict[str, bool] = {}
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(child, bool) and key.endswith(_EVIDENCE_FLAG_SUFFIXES):
                result[path] = child
            if isinstance(child, (Mapping, list, tuple)):
                result.update(_walk_evidence_flags(child, prefix=path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            path = f"{prefix}[{index}]"
            if isinstance(child, (Mapping, list, tuple)):
                result.update(_walk_evidence_flags(child, prefix=path))
    return result


def _walk_chain_positions(value: Any, *, prefix: str = "") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            if key in {
                "block_slot",
                "slot",
                "context_slot",
                "block_height",
                "blockHeight",
            }:
                scalar = _safe_scalar(child)
                if scalar is not None:
                    result.append({"path": path, "value": scalar})
            if isinstance(child, (Mapping, list, tuple)):
                result.extend(_walk_chain_positions(child, prefix=path))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            if isinstance(child, (Mapping, list, tuple)):
                result.extend(
                    _walk_chain_positions(child, prefix=f"{prefix}[{index}]")
                )
    return result[:64]


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _receipt_id(record: Mapping[str, Any]) -> str:
    return "er_" + hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()


def build_evidence_receipt(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Build one deterministic receipt from an existing CMIS envelope.

    The function is intentionally conservative.  A missing verification flag
    becomes an unresolved field; it is never converted to ``False``.  Explicit
    ``False`` remains explicit evidence that a proof gate was not satisfied.
    """

    if not isinstance(envelope, Mapping):
        raise TypeError("CMIS evidence receipt requires a mapping envelope")

    chain = _text(envelope.get("chain"))
    service = _text(envelope.get("service"))
    status = _text(envelope.get("status"))
    if chain is None or service is None or status is None:
        raise ValueError("CMIS evidence receipt requires chain, service, and status")

    data = envelope.get("data") if isinstance(envelope.get("data"), Mapping) else {}
    confidence = (
        envelope.get("confidence")
        if isinstance(envelope.get("confidence"), Mapping)
        else {}
    )

    sources: list[dict[str, Any]] = []
    raw_sources = envelope.get("sources")
    if isinstance(raw_sources, Sequence) and not isinstance(raw_sources, (str, bytes)):
        for item in raw_sources:
            record = _safe_source(item, evidence_class="source_record")
            if record:
                sources.append(record)

    observations = data.get("observations") if isinstance(data, Mapping) else None
    if isinstance(observations, Mapping):
        primary = _safe_source(
            observations.get("primary"), evidence_class="reported_observation"
        )
        verifier = _safe_source(
            observations.get("verifier"), evidence_class="verifier_observation"
        )
        if primary:
            sources.append(primary)
        if verifier:
            sources.append(verifier)

    verification = data.get("verification") if isinstance(data, Mapping) else None
    verification_status = None
    verification_code = None
    if isinstance(verification, Mapping):
        candidate = _text(verification.get("status"))
        verification_status = candidate if candidate in _VERIFICATION_STATUSES else None
        verification_code = _text(verification.get("code"))

    scope_claims: list[dict[str, str]] = []
    for path in _SCOPE_PATHS:
        value = _text(_path_get(envelope, path))
        if value is not None:
            scope_claims.append({"path": ".".join(path), "value": value})

    evidence_flags = {
        **_walk_evidence_flags(data, prefix="data"),
        **_walk_evidence_flags(confidence, prefix="confidence"),
    }

    source_independence_flags = {
        path: flag
        for path, flag in evidence_flags.items()
        if path.endswith("source_independence_verified")
    }
    if source_independence_flags:
        source_independence_verified: bool | None = all(
            source_independence_flags.values()
        )
    else:
        source_independence_verified = None

    promotable = data.get("cmis_promotable") if isinstance(data, Mapping) else None
    if (
        verification_status == "AGREEMENT"
        and promotable is True
        and source_independence_verified is True
    ):
        independently_verified: bool | None = True
    elif verification_status == "CONFLICT" or source_independence_verified is False:
        independently_verified = False
    else:
        independently_verified = None

    freshness_flags = {
        path: flag
        for path, flag in evidence_flags.items()
        if path.endswith("freshness_verified")
    }
    if freshness_flags:
        freshness_verified: bool | None = all(freshness_flags.values())
    else:
        freshness_verified = None

    observed_times = sorted({
        text
        for text in (
            [_text(envelope.get("observed_at"))]
            + [_text(item.get("observed_at")) for item in sources]
        )
        if text is not None
    })

    warnings = _messages(envelope.get("warnings"))
    errors = _messages(envelope.get("errors"))

    disagreements: list[dict[str, str]] = []
    if verification_status == "CONFLICT":
        record = {"kind": "verification_conflict"}
        if verification_code is not None:
            record["code"] = verification_code
        disagreements.append(record)
    for message in warnings:
        haystack = " ".join(message.values()).lower()
        if any(token in haystack for token in ("conflict", "disagree", "mismatch")):
            disagreements.append({"kind": "warning", **message})

    unresolved_fields = sorted(
        path for path, flag in evidence_flags.items() if flag is False
    )
    if verification_status is None:
        unresolved_fields.append("verification.status")
    elif verification_status == "INSUFFICIENT_EVIDENCE":
        unresolved_fields.append("verification.same_fact_evidence")
    if source_independence_verified is None:
        unresolved_fields.append("verification.source_independence")
    if not scope_claims:
        unresolved_fields.append("evidence_scope")
    if freshness_verified is None:
        unresolved_fields.append("freshness.verified")
    if not sources:
        unresolved_fields.append("sources")
    unresolved_fields = sorted(set(unresolved_fields))

    limitations: list[dict[str, str]] = []
    for item in warnings + errors:
        limitations.append(deepcopy(item))
    for field in unresolved_fields:
        limitations.append({"code": "UNRESOLVED_EVIDENCE_FIELD", "message": field})

    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "chain": chain.lower(),
        "service": service,
        "service_status": status.lower(),
        "asset": _safe_asset(envelope.get("asset")),
        "observation": {
            "envelope_observed_at": _safe_scalar(envelope.get("observed_at")),
            "observed_times": observed_times,
            "chain_positions": _walk_chain_positions(
                {"data": data, "sources": sources},
            ),
        },
        "verification": {
            "status": verification_status or "UNVERIFIED",
            "code": verification_code,
            "source_independence_verified": source_independence_verified,
            "independently_verified": independently_verified,
            "provider_assertion_promoted": False,
        },
        "evidence_scope": {
            "claims": scope_claims,
            "explicit_scope_available": bool(scope_claims),
        },
        "freshness": {
            "verified": freshness_verified,
            "flags": freshness_flags,
        },
        "sources": sources,
        "evidence_flags": dict(sorted(evidence_flags.items())),
        "disagreements": disagreements,
        "limitations": limitations,
        "unresolved_fields": unresolved_fields,
        "risk_included_in_proof": False,
    }
    return {"receipt_id": _receipt_id(base), **base}


__all__ = ["SCHEMA_VERSION", "build_evidence_receipt"]
