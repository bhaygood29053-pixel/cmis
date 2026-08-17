"""Exact read-only lookup for persisted CMIS verification evidence.

This adapter is gateway-ready but does not alter ``CMISGateway`` itself. It
accepts either one content-addressed evidence ID or one exact fact identity
(``fact_type`` + ``subject_id``), reads from an injected verification-evidence
ledger, and returns only a revalidated sanitized CMIS envelope without
recalculating or strengthening the fact.

Free-form asset names, raw verifier results, provider responses, and arbitrary
queries are intentionally unsupported selectors.
"""

from __future__ import annotations

from collections.abc import Mapping
import copy
import math
from typing import Any, Optional

from liquidity_scout.cmis.evidence_ledger import (
    evidence_id_for,
    sanitize_verification_envelope,
)

from .cmis_contract import ERROR, UNAVAILABLE, build_service_envelope


SERVICE = "verification_evidence"


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _error(chain: str, code: str, message: str) -> dict[str, Any]:
    return build_service_envelope(
        SERVICE,
        chain,
        ERROR,
        errors=[{"code": code, "message": message}],
    )


def _unavailable(chain: str, code: str, message: str) -> dict[str, Any]:
    return build_service_envelope(
        SERVICE,
        chain,
        UNAVAILABLE,
        warnings=[{"code": code, "message": message}],
    )


def lookup_verification_evidence(
    ledger: Any,
    *,
    chain: Any,
    evidence_id: Any = None,
    fact_type: Any = None,
    subject_id: Any = None,
) -> dict[str, Any]:
    """Return one exact persisted verification-evidence envelope.

    Selector modes are mutually exclusive:

    - ``evidence_id``; or
    - ``fact_type`` + ``subject_id`` for the latest exact fact record.

    The returned evidence body is revalidated through the same sanitizer used at
    the persistence boundary. Its content-addressed ID is recomputed before
    release. No fact, verification, quality, source, or promotion field is
    recalculated or strengthened.
    """
    chain_name = (_text(chain) or "unknown").lower()
    if ledger is None:
        return _unavailable(
            chain_name,
            "verification_evidence_ledger_not_configured",
            "No CMIS verification-evidence ledger is configured in this deployment.",
        )

    evidence_key = _text(evidence_id)
    fact_key = _text(fact_type)
    subject_key = _text(subject_id)

    if evidence_key is not None and (fact_key is not None or subject_key is not None):
        return _error(
            chain_name,
            "verification_evidence_selector_conflict",
            "Use either evidence_id or fact_type + subject_id, not both selector modes.",
        )

    if evidence_key is None:
        if fact_key is None and subject_key is None:
            return _error(
                chain_name,
                "verification_evidence_selector_required",
                "Provide evidence_id or the exact pair fact_type + subject_id.",
            )
        if fact_key is None or subject_key is None:
            return _error(
                chain_name,
                "verification_evidence_fact_selector_incomplete",
                "Both fact_type and subject_id are required for exact fact lookup.",
            )

    try:
        if evidence_key is not None:
            record = ledger.get(evidence_key)
        else:
            record = ledger.latest(
                chain=chain_name,
                fact_type=fact_key,
                subject_id=subject_key,
            )
    except Exception:
        return _unavailable(
            chain_name,
            "verification_evidence_ledger_unavailable",
            "CMIS could not read the verification-evidence ledger.",
        )

    if record is None:
        return _unavailable(
            chain_name,
            "verification_evidence_not_found",
            "No persisted CMIS verification evidence matches the exact selector.",
        )
    if not isinstance(record, Mapping):
        return _error(
            chain_name,
            "verification_evidence_record_invalid",
            "The verification-evidence ledger returned an invalid record.",
        )

    stored_id = _text(record.get("evidence_id"))
    stored_at = record.get("recorded_at")
    envelope = record.get("envelope")
    if stored_id is None or not isinstance(envelope, Mapping):
        return _error(
            chain_name,
            "verification_evidence_record_invalid",
            "The verification-evidence ledger record is incomplete.",
        )
    if (
        isinstance(stored_at, bool)
        or not isinstance(stored_at, (int, float))
        or not math.isfinite(float(stored_at))
    ):
        return _error(
            chain_name,
            "verification_evidence_record_timestamp_invalid",
            "The verification-evidence ledger record has an invalid recorded_at timestamp.",
        )

    try:
        safe_envelope = sanitize_verification_envelope(envelope)
    except (TypeError, ValueError):
        return _error(
            chain_name,
            "verification_evidence_record_invalid",
            "The persisted verification-evidence envelope failed CMIS storage validation.",
        )

    if safe_envelope.get("service") != SERVICE:
        return _error(
            chain_name,
            "verification_evidence_record_service_mismatch",
            "The persisted record is not a verification_evidence envelope.",
        )
    stored_chain = _text(safe_envelope.get("chain"))
    if stored_chain is None or stored_chain.lower() != chain_name:
        return _error(
            chain_name,
            "verification_evidence_record_chain_mismatch",
            "The persisted evidence does not belong to the requested chain.",
        )

    computed_id = evidence_id_for(safe_envelope)
    if computed_id != stored_id:
        return _error(
            chain_name,
            "verification_evidence_content_id_mismatch",
            "The persisted evidence ID does not match the sanitized evidence content.",
        )
    if evidence_key is not None and stored_id != evidence_key:
        return _error(
            chain_name,
            "verification_evidence_id_mismatch",
            "The ledger record identity does not match the requested evidence ID.",
        )

    data = safe_envelope.get("data")
    if not isinstance(data, Mapping):
        return _error(
            chain_name,
            "verification_evidence_record_data_invalid",
            "The persisted verification evidence has no valid data object.",
        )

    if evidence_key is None:
        fact = data.get("fact")
        fact = fact if isinstance(fact, Mapping) else {}
        if _text(fact.get("fact_type")) != fact_key or _text(fact.get("subject_id")) != subject_key:
            return _error(
                chain_name,
                "verification_evidence_record_fact_mismatch",
                "The ledger returned evidence for a different fact identity.",
            )

    response = copy.deepcopy(safe_envelope)
    response_data = response.get("data")
    response_data = dict(response_data) if isinstance(response_data, Mapping) else {}
    response_data["evidence_ref"] = {
        "evidence_id": stored_id,
        "recorded_at": float(stored_at),
    }
    response["data"] = response_data
    return response


__all__ = ["SERVICE", "lookup_verification_evidence"]
