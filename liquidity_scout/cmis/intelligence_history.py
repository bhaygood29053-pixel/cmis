"""Persisted sanitized CMIS intelligence history for deterministic comparisons.

The ledger stores explicit normalized observations for wallet activity, price,
liquidity, supply, and activity metrics. It never stores arbitrary raw provider
payloads and never infers continuous coverage from sparse observations.

Historical comparison is allowed only when subject, metric, unit, scope, and
verified semantics are compatible. Missing observations remain missing; no
interpolation, backfill, or zero-filling occurs.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import sqlite3
import time
from typing import Any


SCHEMA_VERSION = 1
CATEGORIES = frozenset({"wallet", "price", "liquidity", "supply", "activity"})


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal_text(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not parsed.is_finite():
        return None
    normalized = format(parsed, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"", "-0"} else normalized


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _observation_id(record: Mapping[str, Any]) -> str:
    return "ih_" + hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()


def build_history_observation(
    *,
    chain: Any,
    category: Any,
    subject_id: Any,
    metric: Any,
    value: Any,
    unit: Any,
    observed_at: Any,
    source: Any,
    verification_method: Any,
    evidence_scope: Any,
    block_slot: Any = None,
    receipt_id: Any = None,
    proof_strength: Any = None,
    identity_verified: bool = False,
    semantics_verified: bool = False,
    freshness_verified: bool | None = None,
    scope_complete: bool | None = None,
    limitations: list[Any] | None = None,
) -> dict[str, Any]:
    """Build one normalized history observation with explicit proof metadata."""

    chain_text = _text(chain)
    category_text = (_text(category) or "").lower()
    subject = _text(subject_id)
    metric_text = _text(metric)
    normalized_value = _decimal_text(value)
    unit_text = _text(unit)
    source_text = _text(source)
    method = _text(verification_method)
    scope = _text(evidence_scope)
    if category_text not in CATEGORIES:
        raise ValueError(f"unsupported history category: {category_text!r}")
    if not all((chain_text, subject, metric_text, unit_text, source_text, method, scope)):
        raise ValueError(
            "history observation requires chain, category, subject_id, metric, unit, "
            "source, verification_method, and evidence_scope"
        )
    if normalized_value is None:
        raise ValueError("history observation value must be a finite numeric value")
    if identity_verified is not True:
        raise ValueError("history observation requires verified subject identity")
    if semantics_verified is not True:
        raise ValueError("history observation requires verified metric semantics")
    if freshness_verified not in {True, False, None}:
        raise ValueError("freshness_verified must be true, false, or null")
    if scope_complete not in {True, False, None}:
        raise ValueError("scope_complete must be true, false, or null")

    receipt = _text(receipt_id)
    if receipt is not None and not receipt.startswith("er_"):
        raise ValueError("receipt_id must be a CMIS evidence receipt id")
    proof = (_text(proof_strength) or "").upper() or None
    if proof not in {None, "STRONG", "MODERATE", "WEAK"}:
        raise ValueError("proof_strength must be STRONG, MODERATE, WEAK, or null")

    base = {
        "schema_version": SCHEMA_VERSION,
        "chain": chain_text.lower(),
        "category": category_text,
        "subject_id": subject,
        "metric": metric_text,
        "value": normalized_value,
        "unit": unit_text,
        "observed_at": observed_at,
        "block_slot": block_slot,
        "source": source_text,
        "verification_method": method,
        "evidence_scope": scope,
        "receipt_id": receipt,
        "proof_strength": proof,
        "identity_verified": True,
        "semantics_verified": True,
        "freshness_verified": freshness_verified,
        "scope_complete": scope_complete,
        "limitations": sorted(
            {text for text in (_text(item) for item in (limitations or [])) if text}
        ),
        "continuous_coverage_proven": False,
        "archival_completeness_proven": False,
    }
    return {"observation_id": _observation_id(base), **base}


class IntelligenceHistoryLedger:
    """SQLite-backed sanitized intelligence observation store."""

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
                CREATE TABLE IF NOT EXISTS intelligence_history (
                    observation_id TEXT PRIMARY KEY,
                    chain TEXT NOT NULL,
                    category TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    observed_at_text TEXT,
                    recorded_at REAL NOT NULL,
                    observation_json TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_intelligence_history_lookup
                ON intelligence_history (
                    chain, category, subject_id, metric, unit, recorded_at
                )
                """
            )

    def store(
        self,
        observation: Mapping[str, Any],
        *,
        recorded_at: Any = None,
    ) -> dict[str, Any]:
        safe = self._validate_observation(observation)
        timestamp = time.time() if recorded_at is None else recorded_at
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise ValueError("recorded_at must be numeric")
        timestamp = float(timestamp)
        if not math.isfinite(timestamp):
            raise ValueError("recorded_at must be finite")
        canonical = _canonical_json(safe)
        with self._connect() as db:
            cursor = db.execute(
                """
                INSERT OR IGNORE INTO intelligence_history (
                    observation_id, chain, category, subject_id, metric, unit,
                    observed_at_text, recorded_at, observation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    safe["observation_id"],
                    safe["chain"],
                    safe["category"],
                    safe["subject_id"],
                    safe["metric"],
                    safe["unit"],
                    _text(safe.get("observed_at")),
                    timestamp,
                    canonical,
                ),
            )
            inserted = cursor.rowcount == 1
        return {
            "observation_id": safe["observation_id"],
            "inserted": inserted,
            "recorded_at": timestamp,
        }

    @staticmethod
    def _validate_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(observation, Mapping):
            raise TypeError("history observation must be a mapping")
        record = dict(observation)
        if record.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unsupported history observation schema")
        if _text(record.get("observation_id")) is None:
            raise ValueError("history observation_id is required")
        if record.get("category") not in CATEGORIES:
            raise ValueError("history observation category is invalid")
        if record.get("identity_verified") is not True:
            raise ValueError("history observation identity must be verified")
        if record.get("semantics_verified") is not True:
            raise ValueError("history observation semantics must be verified")
        if record.get("continuous_coverage_proven") is not False:
            raise ValueError("sparse observation cannot claim continuous coverage")
        if record.get("archival_completeness_proven") is not False:
            raise ValueError("sparse observation cannot claim archival completeness")
        for field in (
            "chain",
            "subject_id",
            "metric",
            "unit",
            "source",
            "verification_method",
            "evidence_scope",
        ):
            if _text(record.get(field)) is None:
                raise ValueError(f"history observation {field} is required")
        if _decimal_text(record.get("value")) is None:
            raise ValueError("history observation value is invalid")
        expected_id = _observation_id(
            {key: value for key, value in record.items() if key != "observation_id"}
        )
        if record["observation_id"] != expected_id:
            raise ValueError("history observation content-addressed id mismatch")
        return record

    def find(
        self,
        *,
        chain: Any,
        category: Any,
        subject_id: Any,
        metric: Any,
        unit: Any = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        chain_text = (_text(chain) or "").lower()
        category_text = (_text(category) or "").lower()
        subject = _text(subject_id)
        metric_text = _text(metric)
        unit_text = _text(unit)
        if not all((chain_text, category_text, subject, metric_text)):
            raise ValueError("chain, category, subject_id, and metric are required")
        if category_text not in CATEGORIES:
            raise ValueError("unsupported history category")
        if isinstance(limit, bool) or not isinstance(limit, int) or not (1 <= limit <= 1000):
            raise ValueError("limit must be an integer between 1 and 1000")

        clauses = [
            "chain = ?",
            "category = ?",
            "subject_id = ?",
            "metric = ?",
        ]
        params: list[Any] = [chain_text, category_text, subject, metric_text]
        if unit_text is not None:
            clauses.append("unit = ?")
            params.append(unit_text)
        params.append(limit)
        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT observation_id, recorded_at, observation_json
                FROM intelligence_history
                WHERE {' AND '.join(clauses)}
                ORDER BY recorded_at ASC, observation_id ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [
            {
                "observation_id": row["observation_id"],
                "recorded_at": row["recorded_at"],
                "observation": json.loads(row["observation_json"]),
            }
            for row in rows
        ]

    def compare_first_last(
        self,
        *,
        chain: Any,
        category: Any,
        subject_id: Any,
        metric: Any,
        unit: Any,
    ) -> dict[str, Any]:
        """Compare first/last compatible sparse observations without overclaiming."""

        rows = self.find(
            chain=chain,
            category=category,
            subject_id=subject_id,
            metric=metric,
            unit=unit,
            limit=1000,
        )
        if len(rows) < 2:
            return {
                "status": "INSUFFICIENT_EVIDENCE",
                "sample_count": len(rows),
                "continuous_coverage_proven": False,
                "archival_completeness_proven": False,
                "absolute_change": None,
                "percent_change": None,
            }

        first = rows[0]["observation"]
        last = rows[-1]["observation"]
        if first.get("evidence_scope") != last.get("evidence_scope"):
            return {
                "status": "INCOMPATIBLE_SCOPE",
                "sample_count": len(rows),
                "continuous_coverage_proven": False,
                "archival_completeness_proven": False,
                "absolute_change": None,
                "percent_change": None,
                "first_scope": first.get("evidence_scope"),
                "last_scope": last.get("evidence_scope"),
            }

        first_value = Decimal(str(first["value"]))
        last_value = Decimal(str(last["value"]))
        absolute = last_value - first_value
        percent = None if first_value == 0 else (absolute / first_value) * Decimal(100)
        return {
            "status": "OBSERVED_CHANGE",
            "sample_count": len(rows),
            "first_observation": first,
            "last_observation": last,
            "absolute_change": _decimal_text(absolute),
            "percent_change": _decimal_text(percent),
            "continuous_coverage_proven": False,
            "archival_completeness_proven": False,
            "limitations": [
                "sparse_observation_comparison_only",
                "no_interpolation",
                "no_continuous_coverage_claim",
            ],
        }


__all__ = [
    "CATEGORIES",
    "SCHEMA_VERSION",
    "IntelligenceHistoryLedger",
    "build_history_observation",
]
