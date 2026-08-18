"""Fail-closed contract classification for a secondary X1 JSON-RPC source.

This module deliberately does not discover endpoints or perform network I/O. It
classifies already-observed JSON-RPC responses so a candidate historical RPC
source can be contract-tested without promoting archival/completeness claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SUPPORTED_METHODS = frozenset({"getHealth", "getSlot", "getBlock"})


@dataclass(frozen=True)
class SecondaryRpcContractObservation:
    source: str
    method: str
    transport_ok: bool
    jsonrpc_envelope_verified: bool
    result_shape_verified: bool
    observed_slot: int | None
    error_code: int | None
    archival_completeness_verified: bool = False
    retention_verified: bool = False
    finality_semantics_verified: bool = False
    cmis_promotable: bool = False


def classify_secondary_rpc_response(
    *, source: str, method: str, payload: Mapping[str, Any]
) -> SecondaryRpcContractObservation:
    """Classify one previously captured JSON-RPC response.

    A structurally valid response proves only that the candidate answered the
    requested method with the expected basic shape. It never proves archival
    completeness, retention depth, finality semantics, or CMIS promotion.
    """
    source = source.strip()
    method = method.strip()
    if not source:
        raise ValueError("source is required")
    if method not in SUPPORTED_METHODS:
        raise ValueError(f"unsupported method: {method}")
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")

    envelope_ok = payload.get("jsonrpc") == "2.0" and "id" in payload
    error = payload.get("error")
    error_code = None
    if (
        isinstance(error, Mapping)
        and isinstance(error.get("code"), int)
        and not isinstance(error.get("code"), bool)
    ):
        error_code = error["code"]

    transport_ok = envelope_ok and error is None and "result" in payload
    result_ok = False
    observed_slot = None
    if transport_ok:
        result = payload["result"]
        if method == "getHealth":
            result_ok = result == "ok"
        elif method == "getSlot":
            result_ok = (
                isinstance(result, int)
                and not isinstance(result, bool)
                and result >= 0
            )
            if result_ok:
                observed_slot = result
        elif method == "getBlock":
            # A block object proves retrievability of that requested block only.
            # Null is a valid JSON-RPC result but does not prove retrievability.
            result_ok = isinstance(result, Mapping)
            if result_ok:
                parent_slot = result.get("parentSlot")
                if (
                    isinstance(parent_slot, int)
                    and not isinstance(parent_slot, bool)
                    and parent_slot >= 0
                ):
                    observed_slot = parent_slot + 1

    return SecondaryRpcContractObservation(
        source=source,
        method=method,
        transport_ok=transport_ok,
        jsonrpc_envelope_verified=envelope_ok,
        result_shape_verified=result_ok,
        observed_slot=observed_slot,
        error_code=error_code,
    )
