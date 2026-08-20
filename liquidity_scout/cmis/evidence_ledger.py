"""Persistent sanitized CMIS verification-evidence ledger.

The ledger stores only standard ``verification_evidence`` service envelopes.
It does not collect providers, recompute facts, store arbitrary raw transport
payloads, or participate in the live listener. Historical market snapshots and
verification evidence remain separate persistence concerns.

Evidence identifiers are content-addressed SHA-256 hashes over a canonical,
sanitized projection of the service envelope. Re-storing the same evidence is
idempotent.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import math
import sqlite3
import time
from typing import Any, Optional

from liquidity_scout.cmis.evidence import (
    AGREEMENT,
    CONFLICT,
    INSUFFICIENT_EVIDENCE,
    VERIFICATION_STATUSES,
)


VERSION = "1.0"
SERVICE = "verification_evidence"
_ALLOWED_SERVICE_STATUSES = frozenset({"ok", "partial"})
_QUALITY_LEVELS = frozenset({"HIGH", "MEDIUM", "LOW"})
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
    "observed_at",
    "block_slot",
    "calculation_version",
)
_MESSAGE_FIELDS = ("code", "message")
_QUALITY_BOOLEAN_FIELDS = (
    "identity_verified",
    "semantics_verified",
    "freshness_verified",
    "same_fact_agreement_verified",
    "independent_agreement_verified",
)


def _text(value: Any) -> Optional[str]:
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
    return {
        field: _safe_scalar(value.get(field))
        for field in _ASSET_FIELDS
        if _safe_scalar(value.get(field)) is not None
    }


def _safe_records(value: Any, fields: tuple[str, ...]) -> list[dict[str, Any]]:
    """Project mapping lists to an explicit scalar-field allowlist."""
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        record = {
            field: _safe_scalar(item.get(field))
            for field in fields
            if _safe_scalar(item.get(field)) is not None
        }
        if record:
            result.append(record)
    return result


def _safe_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item)
        for item in value
        if not isinstance(item, (Mapping, list, tuple, set))
    ]


def _safe_observation(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    fields = (
        "chain",
        "fact_type",
        "subject_id",
        "source",
        "source_role",
        "observed_at",
        "block_slot",
        "raw_identifier",
        "raw_value",
        "normalized_value",
        "unit",
        "calculation_version",
        "identity_verified",
        "semantics_verified",
        "freshness_verified",
    )
    record = {field: _safe_scalar(value.get(field)) for field in fields}
    record["warnings"] = _safe_string_list(value.get("warnings"))
    return record


def _safe_quality(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    fields = (
        "quality",
        "independent_source_count",
        "distinct_source_label_count",
        "source_independence_verified",
        *_QUALITY_BOOLEAN_FIELDS,
    )
    record = {field: _safe_scalar(value.get(field)) for field in fields}
    record["reasons"] = _safe_string_list(value.get("reasons"))
    return record


def _validate_quality(
    quality: Mapping[str, Any],
    *,
    verification_status: str,
    promotable: bool,
    primary: Mapping[str, Any],
    verifier: Mapping[str, Any],
) -> None:
    level = _text(quality.get("quality"))
    if level not in _QUALITY_LEVELS:
        raise ValueError("verification evidence data quality level is invalid")

    source_count = quality.get("independent_source_count")
    if isinstance(source_count, bool) or not isinstance(source_count, int) or source_count < 0:
        raise ValueError("verification evidence independent_source_count is invalid")

    label_count = quality.get("distinct_source_label_count")
    if isinstance(label_count, bool) or not isinstance(label_count, int) or label_count < 0:
        raise ValueError("verification evidence distinct_source_label_count is invalid")

    for field in _QUALITY_BOOLEAN_FIELDS:
        if not isinstance(quality.get(field), bool):
            raise ValueError(f"verification evidence {field} must be boolean")

    source_independence_verified = quality.get("source_independence_verified")
    if source_independence_verified is not None and not isinstance(
        source_independence_verified, bool
    ):
        raise ValueError(
            "verification evidence source_independence_verified must be boolean or null"
        )

    unique_sources = {
        _text(record.get("source"))
        for record in (primary, verifier)
        if _text(record.get("source")) is not None
    }
    if source_count != len(unique_sources):
        raise ValueError("verification evidence independent source count is inconsistent")
    if label_count != len(unique_sources):
        raise ValueError("verification evidence distinct source label count is inconsistent")

    same_fact_agreement_verified = quality.get("same_fact_agreement_verified") is True
    if same_fact_agreement_verified != (verification_status == AGREEMENT):
        raise ValueError("verification evidence same-fact agreement quality state is inconsistent")

    independent_agreement_verified = quality.get("independent_agreement_verified") is True
    expected_independent_agreement = bool(
        same_fact_agreement_verified and source_independence_verified is True
    )
    if independent_agreement_verified != expected_independent_agreement:
        raise ValueError("verification evidence independent agreement quality state is inconsistent")

    expected_identity = all(record.get("identity_verified") is True for record in (primary, verifier))
    expected_semantics = all(record.get("semantics_verified") is True for record in (primary, verifier))
    expected_freshness = all(record.get("freshness_verified") is True for record in (primary, verifier))
    if quality.get("identity_verified") is not expected_identity:
        raise ValueError("verification evidence identity quality state is inconsistent")
    if quality.get("semantics_verified") is not expected_semantics:
        raise ValueError("verification evidence semantics quality state is inconsistent")
    if quality.get("freshness_verified") is not expected_freshness:
        raise ValueError("verification evidence freshness quality state is inconsistent")

    if promotable and not (
        level == "HIGH"
        and source_count >= 2
        and label_count >= 2
        and source_independence_verified is True
        and expected_identity
        and expected_semantics
        and expected_freshness
        and same_fact_agreement_verified
        and independent_agreement_verified
    ):
        raise ValueError("CMIS-promotable evidence requires HIGH fully verified quality")


def sanitize_verification_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and project one wrapper response into the ledger schema."""
    if not isinstance(envelope, Mapping):
        raise TypeError("verification evidence envelope must be a mapping")
    if envelope.get("service") != SERVICE:
        raise ValueError("only verification_evidence envelopes may be stored")

    chain = _text(envelope.get("chain"))
    if chain is None:
        raise ValueError("verification evidence chain is required")
    status = _text(envelope.get("status"))
    if status not in _ALLOWED_SERVICE_STATUSES:
        raise ValueError("only completed ok/partial verification evidence may be stored")

    data = envelope.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("verification evidence data is required")
    fact = data.get("fact")
    verification = data.get("verification")
    observations = data.get("observations")
    quality = data.get("data_quality")
    if not isinstance(fact, Mapping):
        raise ValueError("verification evidence fact identity is required")
    if not isinstance(verification, Mapping):
        raise ValueError("verification evidence outcome is required")
    if not isinstance(observations, Mapping):
        raise ValueError("verification evidence observations are required")

    fact_type = _text(fact.get("fact_type"))
    subject_id = _text(fact.get("subject_id"))
    if fact_type is None or subject_id is None:
        raise ValueError("verification evidence fact_type and subject_id are required")

    verification_status = _text(verification.get("status"))
    if verification_status not in VERIFICATION_STATUSES:
        raise ValueError("verification evidence status is invalid")

    promotable = data.get("cmis_promotable")
    if not isinstance(promotable, bool):
        raise ValueError("verification evidence promotion state must be boolean")
    if promotable and verification_status != AGREEMENT:
        raise ValueError("only AGREEMENT evidence may be CMIS-promotable")

    agreement = verification.get("agreement")
    expected_agreement = {
        AGREEMENT: True,
        CONFLICT: False,
        INSUFFICIENT_EVIDENCE: None,
    }[verification_status]
    if agreement is not expected_agreement:
        raise ValueError("verification evidence agreement state is inconsistent")

    if status == "ok" and not (promotable and verification_status == AGREEMENT):
        raise ValueError("verification evidence ok status requires promotable AGREEMENT")
    if status == "partial" and promotable:
        raise ValueError("CMIS-promotable verification evidence must use ok status")

    primary = _safe_observation(observations.get("primary"))
    verifier = _safe_observation(observations.get("verifier"))
    if not primary or not verifier:
        raise ValueError("verification evidence requires primary and verifier observations")
    for record in (primary, verifier):
        if _text(record.get("chain")) != chain:
            raise ValueError("verification evidence observation chain mismatch")
        if _text(record.get("fact_type")) != fact_type:
            raise ValueError("verification evidence observation fact mismatch")
        if _text(record.get("subject_id")) != subject_id:
            raise ValueError("verification evidence observation subject mismatch")

    safe_quality = _safe_quality(quality)
    _validate_quality(
        safe_quality,
        verification_status=verification_status,
        promotable=promotable,
        primary=primary,
        verifier=verifier,
    )

    normalized_value = _safe_scalar(fact.get("normalized_value"))
    unit = _text(fact.get("unit"))
    if promotable:
        if normalized_value is None or unit is None:
            raise ValueError("promotable verification evidence requires normalized fact value and unit")
        if (
            normalized_value != primary.get("normalized_value")
            or normalized_value != verifier.get("normalized_value")
            or unit != _text(primary.get("unit"))
            or unit != _text(verifier.get("unit"))
        ):
            raise ValueError("promoted fact value/unit must match both verified observations")
    elif normalized_value is not None or unit is not None:
        raise ValueError("non-promotable verification evidence must not expose a promoted fact value")

    safe_fact = {
        "fact_type": fact_type,
        "subject_id": subject_id,
        "normalized_value": normalized_value,
        "unit": unit,
    }
    safe_verification = {
        "status": verification_status,
        "code": _text(verification.get("code")),
        "agreement": agreement,
    }

    return {
        "service": SERVICE,
        "chain": chain,
        "status": status,
        "asset": _safe_asset(envelope.get("asset")),
        "data": {
            "fact": safe_fact,
            "verification": safe_verification,
            "data_quality": safe_quality,
            "observations": {"primary": primary, "verifier": verifier},
            "cmis_promotable": promotable,
        },
        "risk": None,
        "confidence": _safe_quality(envelope.get("confidence")),
        "sources": _safe_records(envelope.get("sources"), _SOURCE_FIELDS),
        "observed_at": _safe_scalar(envelope.get("observed_at")),
        "warnings": _safe_records(envelope.get("warnings"), _MESSAGE_FIELDS),
        "errors": [],
    }


def _canonical_json(record: Mapping[str, Any]) -> str:
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def evidence_id_for(record: Mapping[str, Any]) -> str:
    canonical = _canonical_json(record).encode("utf-8")
    return "ve_" + hashlib.sha256(canonical).hexdigest()


class VerificationEvidenceLedger:
    """SQLite-backed content-addressed verification evidence store."""

    def __init__(self, db_path: str):
        path = _text(db_path)
        if path is None:
            raise ValueError("db_path is required")
        self.db_path = path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS verification_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    chain TEXT NOT NULL,
                    fact_type TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    quality TEXT NOT NULL,
                    cmis_promotable INTEGER NOT NULL,
                    recorded_at REAL NOT NULL,
                    envelope_json TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_verification_evidence_fact
                ON verification_evidence (chain, fact_type, subject_id, recorded_at)
                """
            )

    def store(
        self,
        envelope: Mapping[str, Any],
        *,
        recorded_at: Any = None,
    ) -> dict[str, Any]:
        safe = sanitize_verification_envelope(envelope)
        evidence_id = evidence_id_for(safe)
        timestamp = time.time() if recorded_at is None else recorded_at
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise ValueError("recorded_at must be a numeric timestamp")
        timestamp = float(timestamp)
        if not math.isfinite(timestamp):
            raise ValueError("recorded_at must be finite")

        data = safe["data"]
        fact = data["fact"]
        verification = data["verification"]
        quality = data["data_quality"]
        canonical = _canonical_json(safe)

        with self._connect() as db:
            cursor = db.execute(
                """
                INSERT OR IGNORE INTO verification_evidence (
                    evidence_id,
                    chain,
                    fact_type,
                    subject_id,
                    verification_status,
                    quality,
                    cmis_promotable,
                    recorded_at,
                    envelope_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    safe["chain"],
                    fact["fact_type"],
                    fact["subject_id"],
                    verification["status"],
                    quality["quality"],
                    1 if data["cmis_promotable"] else 0,
                    timestamp,
                    canonical,
                ),
            )
            inserted = cursor.rowcount == 1

        return {
            "evidence_id": evidence_id,
            "inserted": inserted,
            "recorded_at": timestamp,
        }

    def get(self, evidence_id: Any) -> Optional[dict[str, Any]]:
        key = _text(evidence_id)
        if key is None:
            return None
        with self._connect() as db:
            row = db.execute(
                """
                SELECT evidence_id, recorded_at, envelope_json
                FROM verification_evidence
                WHERE evidence_id = ?
                """,
                (key,),
            ).fetchone()
        if row is None:
            return None
        return {
            "evidence_id": row["evidence_id"],
            "recorded_at": row["recorded_at"],
            "envelope": json.loads(row["envelope_json"]),
        }

    def find(
        self,
        *,
        chain: Any,
        fact_type: Any = None,
        subject_id: Any = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        chain_text = _text(chain)
        if chain_text is None:
            raise ValueError("chain is required")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0 or limit > 500:
            raise ValueError("limit must be an integer from 1 to 500")

        clauses = ["chain = ?"]
        params: list[Any] = [chain_text]
        fact_text = _text(fact_type)
        subject_text = _text(subject_id)
        if fact_text is not None:
            clauses.append("fact_type = ?")
            params.append(fact_text)
        if subject_text is not None:
            clauses.append("subject_id = ?")
            params.append(subject_text)
        params.append(limit)

        sql = f"""
            SELECT evidence_id, recorded_at, envelope_json
            FROM verification_evidence
            WHERE {' AND '.join(clauses)}
            ORDER BY recorded_at DESC, evidence_id ASC
            LIMIT ?
        """
        with self._connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [
            {
                "evidence_id": row["evidence_id"],
                "recorded_at": row["recorded_at"],
                "envelope": json.loads(row["envelope_json"]),
            }
            for row in rows
        ]

    def latest(
        self,
        *,
        chain: Any,
        fact_type: Any,
        subject_id: Any,
    ) -> Optional[dict[str, Any]]:
        rows = self.find(
            chain=chain,
            fact_type=fact_type,
            subject_id=subject_id,
            limit=1,
        )
        return rows[0] if rows else None


__all__ = [
    "SERVICE",
    "VERSION",
    "VerificationEvidenceLedger",
    "evidence_id_for",
    "sanitize_verification_envelope",
]
