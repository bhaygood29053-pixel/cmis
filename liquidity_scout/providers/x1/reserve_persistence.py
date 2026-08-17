"""Persist already-produced X1 reserve cross-check verifier results.

This adapter consumes the output of ``run_x1_reserve_crosscheck``. It never
collects provider/RPC data, reruns semantic gates, recalculates reserve values,
or changes verifier quality/promotion state. Each reserve leg is independently
wrapped and stored through the shared CMIS verification-evidence persistence
helper.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.services.cmis_verification_evidence_persistence import (
    persist_verification_evidence,
)


SERVICE = "x1_reserve_verification_evidence_persistence"
VERSION = "1.0"
ROLES = ("asset", "counter")


def _role_failure(code: str, message: str) -> dict[str, Any]:
    return {
        "stored": False,
        "envelope": None,
        "storage": None,
        "error": {"code": code, "message": message},
    }


def persist_x1_reserve_crosscheck_evidence(
    crosscheck_result: Mapping[str, Any],
    ledger: Any,
    *,
    observed_at: Any = None,
    recorded_at: Any = None,
) -> dict[str, Any]:
    """Persist each storable fact-specific verifier result from one cross-check."""
    if not isinstance(crosscheck_result, Mapping):
        raise TypeError("crosscheck_result must be a mapping")
    if crosscheck_result.get("service") != "x1_reserve_crosscheck":
        raise ValueError("crosscheck_result must come from x1_reserve_crosscheck")
    if crosscheck_result.get("chain") != "x1":
        raise ValueError("crosscheck_result must use chain x1")

    raw_roles = crosscheck_result.get("roles")
    if not isinstance(raw_roles, Mapping):
        raise ValueError("crosscheck_result roles are required")

    role_receipts: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        role_result = raw_roles.get(role)
        if not isinstance(role_result, Mapping):
            role_receipts[role] = _role_failure(
                "reserve_role_result_missing",
                f"The {role} reserve verifier result is missing.",
            )
            continue

        verifier_result = role_result.get("verification")
        if not isinstance(verifier_result, Mapping):
            role_receipts[role] = _role_failure(
                "reserve_role_verifier_result_missing",
                f"The {role} reserve fact-specific verifier result is missing.",
            )
            continue

        role_receipts[role] = persist_verification_evidence(
            verifier_result,
            ledger,
            chain="x1",
            observed_at=observed_at,
            recorded_at=recorded_at,
        )

    stored_roles = [
        role for role in ROLES if role_receipts[role].get("stored") is True
    ]
    return {
        "service": SERVICE,
        "version": VERSION,
        "chain": "x1",
        "pool_address": crosscheck_result.get("pool_address"),
        "roles": role_receipts,
        "stored_roles": stored_roles,
        "stored_count": len(stored_roles),
        "complete": len(stored_roles) == len(ROLES),
        "cmis_promotable": False,
    }


__all__ = [
    "ROLES",
    "SERVICE",
    "VERSION",
    "persist_x1_reserve_crosscheck_evidence",
]
