"""Public-shell adapter to the required private CMIS implementation.

Phase 3 cutover is fail-closed: the public shell exposes contracts and transport,
while cmis-private-core owns the runtime implementation. There is no public
implementation fallback.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

EXPECTED_PRIVATE_CONTRACT = "cmis-private-core/v1"


class PrivateCoreUnavailable(RuntimeError):
    """The required private CMIS core is absent or contract-incompatible."""


def private_core_required() -> bool:
    """Return True: CMIS private core is mandatory after Phase 3 cutover."""
    return True


def _load_private_api():
    try:
        from cmis_core import api
    except ModuleNotFoundError as exc:
        if exc.name == "cmis_core" or str(exc.name or "").startswith("cmis_core."):
            return None
        raise
    return api


def _validate_private_contract(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PrivateCoreUnavailable(
            "CMIS private-core facade returned a non-mapping contract."
        )
    contract = dict(value)
    if contract.get("contract") != EXPECTED_PRIVATE_CONTRACT:
        raise PrivateCoreUnavailable("CMIS private-core contract version is incompatible.")
    required = {
        "gateway_class",
        "supported_services",
        "supported_chains",
        "known_chains",
    }
    missing = sorted(required.difference(contract))
    if missing:
        raise PrivateCoreUnavailable(
            f"CMIS private-core contract is missing required fields: {', '.join(missing)}"
        )
    contract["source"] = "private"
    return contract


def load_runtime_contract() -> dict[str, Any]:
    """Load the required private CMIS runtime contract or fail closed."""
    private_api = _load_private_api()
    if private_api is None:
        raise PrivateCoreUnavailable(
            "cmis-private-core is required but is not installed."
        )
    return _validate_private_contract(private_api.runtime_contract())


def private_core_status() -> dict[str, Any]:
    """Return non-secret deployment status for diagnostics/tests."""
    api = _load_private_api()
    return {
        "available": api is not None,
        "required": True,
        "source": "private" if api is not None else "unavailable",
        "expected_contract": EXPECTED_PRIVATE_CONTRACT,
    }


__all__ = [
    "EXPECTED_PRIVATE_CONTRACT",
    "PrivateCoreUnavailable",
    "load_runtime_contract",
    "private_core_required",
    "private_core_status",
]
