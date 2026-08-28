"""Phase 3 adapter from the public CMIS shell to the private core.

The public transport imports only this boundary. During migration, a public
fallback keeps the existing repository testable before deployment installs the
private distribution. Production cutover can fail closed by setting
CMIS_PRIVATE_CORE_REQUIRED=1.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

EXPECTED_PRIVATE_CONTRACT = "cmis-private-core/v1"
PUBLIC_TRANSITION_CONTRACT = "cmis-public-transition/v1"


class PrivateCoreUnavailable(RuntimeError):
    """The required private CMIS core is absent or contract-incompatible."""


def private_core_required() -> bool:
    return os.getenv("CMIS_PRIVATE_CORE_REQUIRED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


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
        raise PrivateCoreUnavailable("CMIS private-core facade returned a non-mapping contract.")
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
    """Load the private runtime contract or the temporary public fallback."""
    private_api = _load_private_api()
    if private_api is not None:
        return _validate_private_contract(private_api.runtime_contract())

    if private_core_required():
        raise PrivateCoreUnavailable(
            "CMIS_PRIVATE_CORE_REQUIRED is enabled but cmis-private-core is not installed."
        )

    # Transitional fallback only. This path is removed after Phase 3 split
    # validation and before proprietary implementation is removed from public HEAD.
    from liquidity_scout.cmis.gateway import KNOWN_CHAINS, SUPPORTED_CHAINS
    from liquidity_scout.cmis.runtime_gateway import SUPPORTED_SERVICES, RuntimeCMISGateway

    return {
        "contract": PUBLIC_TRANSITION_CONTRACT,
        "source": "public-transition",
        "gateway_class": RuntimeCMISGateway,
        "supported_services": tuple(SUPPORTED_SERVICES),
        "supported_chains": tuple(SUPPORTED_CHAINS),
        "known_chains": tuple(KNOWN_CHAINS),
    }


def private_core_status() -> dict[str, Any]:
    """Return a non-secret deployment status for diagnostics/tests."""
    api = _load_private_api()
    return {
        "available": api is not None,
        "required": private_core_required(),
        "expected_contract": EXPECTED_PRIVATE_CONTRACT,
    }


__all__ = [
    "EXPECTED_PRIVATE_CONTRACT",
    "PUBLIC_TRANSITION_CONTRACT",
    "PrivateCoreUnavailable",
    "load_runtime_contract",
    "private_core_required",
    "private_core_status",
]
