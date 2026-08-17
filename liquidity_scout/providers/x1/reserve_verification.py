"""Deterministic X1 pool-reserve verification over already-proven evidence.

This module intentionally does not fetch X1.Ninja or RPC data and does not infer
reserve units, vault identity, token decimals, or timing semantics. Provider-
specific adapters must prove those facts first and construct CMIS evidence
observations before calling this verifier.
"""

from __future__ import annotations

from typing import Any, Mapping

from liquidity_scout.cmis.evidence import (
    CONFLICT,
    INSUFFICIENT_EVIDENCE,
    build_data_quality_assessment,
    compare_same_fact_exact,
)


FACT_TYPE = "pool_reserve"
SEMANTICS_UNVERIFIED = "SEMANTICS_UNVERIFIED"
IDENTITY_UNVERIFIED = "IDENTITY_UNVERIFIED"
SAME_SOURCE = "SAME_SOURCE"
WRONG_FACT_TYPE = "WRONG_FACT_TYPE"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _failed(
    code: str,
    primary: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> dict[str, Any]:
    verification = {
        "status": INSUFFICIENT_EVIDENCE,
        "code": code,
        "agreement": None,
        "primary": dict(primary),
        "verifier": dict(verifier),
    }
    return {
        "verification": verification,
        "data_quality": build_data_quality_assessment(
            observations=[primary, verifier],
            verification=verification,
        ),
        "cmis_promotable": False,
    }


def verify_x1_pool_reserve(
    primary: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify one X1 pool reserve from two independent proven observations.

    Exact comparison is intentionally strict. A future live adapter may need to
    coordinate observations at a common slot or otherwise prove an acceptable
    observation scope before constructing these records. This function never
    introduces a hidden tolerance for moving reserves.
    """
    if not isinstance(primary, Mapping) or not isinstance(verifier, Mapping):
        raise TypeError("X1 reserve verification requires mapping observations.")

    if (
        _text(primary.get("fact_type")) != FACT_TYPE
        or _text(verifier.get("fact_type")) != FACT_TYPE
    ):
        return _failed(WRONG_FACT_TYPE, primary, verifier)

    if (
        primary.get("identity_verified") is not True
        or verifier.get("identity_verified") is not True
    ):
        return _failed(IDENTITY_UNVERIFIED, primary, verifier)

    if (
        primary.get("semantics_verified") is not True
        or verifier.get("semantics_verified") is not True
    ):
        return _failed(SEMANTICS_UNVERIFIED, primary, verifier)

    primary_source = _text(primary.get("source"))
    verifier_source = _text(verifier.get("source"))
    if primary_source is None or verifier_source is None or primary_source == verifier_source:
        return _failed(SAME_SOURCE, primary, verifier)

    verification = compare_same_fact_exact(primary, verifier)
    quality = build_data_quality_assessment(
        observations=[primary, verifier],
        verification=verification,
    )

    return {
        "verification": verification,
        "data_quality": quality,
        "cmis_promotable": (
            verification.get("status") not in {CONFLICT, INSUFFICIENT_EVIDENCE}
            and quality.get("quality") == "HIGH"
        ),
    }


__all__ = [
    "FACT_TYPE",
    "IDENTITY_UNVERIFIED",
    "SAME_SOURCE",
    "SEMANTICS_UNVERIFIED",
    "WRONG_FACT_TYPE",
    "verify_x1_pool_reserve",
]
