"""Shared CMIS service-response contract helpers.

This module introduces the chain-aware response envelope without renaming or
rewriting the existing Liquidity Scout implementation. It contains no network,
RPC, DEX, database, or LLM logic.
"""

from typing import Any, Dict, Iterable, Mapping, Optional


OK = "ok"
PARTIAL = "partial"
UNAVAILABLE = "unavailable"
AMBIGUOUS = "ambiguous"
ERROR = "error"
SERVICE_STATUSES = frozenset({OK, PARTIAL, UNAVAILABLE, AMBIGUOUS, ERROR})


def _required_text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _mapping(value: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Optional[Iterable[Any]]) -> list:
    if value is None:
        return []
    if isinstance(value, (str, bytes, Mapping)):
        raise ValueError("list fields must be iterable collections, not text or mappings")
    return list(value)


def build_service_envelope(
    service: str,
    chain: str,
    status: str,
    *,
    asset: Optional[Mapping[str, Any]] = None,
    data: Optional[Mapping[str, Any]] = None,
    risk: Optional[Mapping[str, Any]] = None,
    confidence: Optional[Mapping[str, Any]] = None,
    sources: Optional[Iterable[Any]] = None,
    observed_at: Any = None,
    warnings: Optional[Iterable[Any]] = None,
    errors: Optional[Iterable[Any]] = None,
) -> Dict[str, Any]:
    """Build one deterministic chain-aware CMIS response envelope.

    The helper validates only envelope structure. Service-specific meaning and
    verification remain the responsibility of the deterministic service or
    wrapper producing the supplied fields.
    """
    service_name = _required_text("service", service)
    chain_name = _required_text("chain", chain).lower()
    status_name = _required_text("status", status).lower()
    if status_name not in SERVICE_STATUSES:
        raise ValueError(
            "status must be one of: " + ", ".join(sorted(SERVICE_STATUSES))
        )

    if risk is not None and not isinstance(risk, Mapping):
        raise ValueError("risk must be a mapping or None")

    return {
        "service": service_name,
        "chain": chain_name,
        "status": status_name,
        "asset": _mapping(asset),
        "data": _mapping(data),
        "risk": dict(risk) if isinstance(risk, Mapping) else None,
        "confidence": _mapping(confidence),
        "sources": _list(sources),
        "observed_at": observed_at,
        "warnings": _list(warnings),
        "errors": _list(errors),
    }


__all__ = [
    "AMBIGUOUS",
    "ERROR",
    "OK",
    "PARTIAL",
    "SERVICE_STATUSES",
    "UNAVAILABLE",
    "build_service_envelope",
]
