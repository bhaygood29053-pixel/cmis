"""Persist already-produced CMIS verification results without re-verification.

This helper sits between fact-specific deterministic verifiers and the accepted
content-addressed verification-evidence ledger. It does not fetch providers,
compare observations, infer source independence, choose verification status, or
strengthen data quality/promotion state.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

from liquidity_scout.cmis.evidence_ledger import sanitize_verification_envelope
from liquidity_scout.services.cmis_verification_evidence import (
    build_verification_evidence_response,
)


_ERROR_STATUS = "error"


def _failure(
    *,
    envelope: Mapping[str, Any] | None,
    code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "stored": False,
        "envelope": dict(envelope) if isinstance(envelope, Mapping) else None,
        "storage": None,
        "error": {"code": code, "message": message},
    }


def persist_verification_evidence(
    verifier_result: Mapping[str, Any],
    ledger: Any,
    *,
    chain: str = "x1",
    asset: Mapping[str, Any] | None = None,
    observed_at: Any = None,
    recorded_at: Any = None,
) -> dict[str, Any]:
    """Sanitize one accepted verifier result and persist the resulting envelope.

    A verifier result that cannot satisfy the accepted ``verification_evidence``
    wrapper is never sent to the ledger. The returned envelope is the same strict
    canonical sanitized shape that the ledger persists. Ledger failures are
    returned explicitly without exposing exception/provider text.
    """
    envelope = build_verification_evidence_response(
        verifier_result,
        chain=chain,
        asset=asset,
        observed_at=observed_at,
    )
    if envelope.get("status") == _ERROR_STATUS:
        return _failure(
            envelope=envelope,
            code="verification_evidence_not_storable",
            message=(
                "The fact-specific verifier result did not satisfy the accepted "
                "verification_evidence envelope contract."
            ),
        )

    try:
        safe_envelope = sanitize_verification_envelope(envelope)
    except Exception:
        return _failure(
            envelope=envelope,
            code="verification_evidence_not_storable",
            message=(
                "The verification_evidence envelope did not satisfy the accepted "
                "storage sanitizer contract."
            ),
        )

    store = getattr(ledger, "store", None)
    if not callable(store):
        return _failure(
            envelope=safe_envelope,
            code="verification_evidence_ledger_not_configured",
            message="A verification-evidence ledger with store() is required.",
        )

    try:
        receipt = store(safe_envelope, recorded_at=recorded_at)
    except Exception:
        return _failure(
            envelope=safe_envelope,
            code="verification_evidence_persistence_failed",
            message="The verification-evidence ledger rejected or failed to store the envelope.",
        )

    if not isinstance(receipt, Mapping):
        return _failure(
            envelope=safe_envelope,
            code="verification_evidence_persistence_receipt_invalid",
            message="The verification-evidence ledger returned an invalid storage receipt.",
        )

    evidence_id = receipt.get("evidence_id")
    inserted = receipt.get("inserted")
    receipt_recorded_at = receipt.get("recorded_at")
    if (
        not isinstance(evidence_id, str)
        or not evidence_id.strip()
        or not isinstance(inserted, bool)
        or isinstance(receipt_recorded_at, bool)
        or not isinstance(receipt_recorded_at, (int, float))
        or not math.isfinite(float(receipt_recorded_at))
    ):
        return _failure(
            envelope=safe_envelope,
            code="verification_evidence_persistence_receipt_invalid",
            message="The verification-evidence ledger returned an invalid storage receipt.",
        )

    return {
        "stored": True,
        "envelope": safe_envelope,
        "storage": {
            "evidence_id": evidence_id,
            "inserted": inserted,
            "recorded_at": float(receipt_recorded_at),
        },
        "error": None,
    }


__all__ = ["persist_verification_evidence"]
