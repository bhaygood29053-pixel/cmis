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
RESPONSE_FRESHNESS_CONTRACT_VERSION = "cmis_response_freshness/v1"
RESPONSE_FRESHNESS_STATES = frozenset({
    "VERIFIED",
    "PARTIAL",
    "NOT_VERIFIED",
    "UNKNOWN",
    "STALE",
    "NOT_APPLICABLE",
})


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


def _response_freshness(
    service: str,
    observed_at: Any,
    freshness: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Return the additive public response-freshness contract.

    Observation/collection time alone never proves provider-fact freshness.
    Service-specific evidence is preserved under details and only an explicit
    accepted freshness verdict may promote the response state.
    """
    details = _mapping(freshness)
    explicit_verified = details.get("freshness_verified")
    if not isinstance(explicit_verified, bool):
        explicit_verified = details.get("current_market_freshness_verified")
    if not isinstance(explicit_verified, bool):
        explicit_verified = None

    raw_state = str(details.get("freshness_state") or "").strip().upper()
    classification = str(details.get("classification") or "").strip().upper()

    if explicit_verified is True:
        state = "VERIFIED"
    elif raw_state in RESPONSE_FRESHNESS_STATES:
        state = raw_state
    elif classification == "STALE":
        state = "STALE"
    elif explicit_verified is False or details:
        state = "NOT_VERIFIED"
    else:
        state = "UNKNOWN"

    if state not in RESPONSE_FRESHNESS_STATES:
        state = "UNKNOWN"

    result = {
        "contract_version": RESPONSE_FRESHNESS_CONTRACT_VERSION,
        "scope": f"{service}.response",
        "state": state,
        "freshness_verified": explicit_verified,
        "observed_at": observed_at,
        "details": details,
    }
    if not details:
        result["reason"] = "service_specific_freshness_not_supplied"
    return result



def project_response_freshness(
    response: Mapping[str, Any],
    freshness: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Project explicit service freshness into an existing CMIS envelope.

    This is used by additive service-version projections that enrich a response
    after the original envelope was built. It preserves every existing response
    field and replaces only the universal top-level freshness summary.
    """
    if not isinstance(response, Mapping):
        raise ValueError("response must be a mapping")
    result = dict(response)
    service_name = str(result.get("service") or "cmis_gateway").strip() or "cmis_gateway"
    result["freshness"] = _response_freshness(
        service_name,
        result.get("observed_at"),
        freshness,
    )
    return result

def ensure_response_freshness(
    response: Mapping[str, Any],
    *,
    service: Optional[str] = None,
) -> Dict[str, Any]:
    """Add fail-closed public freshness if a legacy/runtime response omitted it."""
    result = dict(response)
    current = result.get("freshness")
    if isinstance(current, Mapping):
        return result

    service_name = str(service or result.get("service") or "cmis_gateway").strip()
    result["freshness"] = _response_freshness(
        service_name or "cmis_gateway",
        result.get("observed_at"),
        None,
    )
    return result

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
    freshness: Optional[Mapping[str, Any]] = None,
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
        "freshness": _response_freshness(service_name, observed_at, freshness),
        "warnings": _list(warnings),
        "errors": _list(errors),
    }


__all__ = [
    "AMBIGUOUS",
    "ERROR",
    "OK",
    "PARTIAL",
    "RESPONSE_FRESHNESS_CONTRACT_VERSION",
    "RESPONSE_FRESHNESS_STATES",
    "SERVICE_STATUSES",
    "UNAVAILABLE",
    "build_service_envelope",
    "ensure_response_freshness",
    "project_response_freshness",
]
