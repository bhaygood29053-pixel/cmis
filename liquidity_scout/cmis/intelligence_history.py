"""Sanitized, fail-closed historical storage for CMIS Phase 11.

The ledger stores only normalized intelligence observations.  It never stores raw
provider payloads, interpolates missing samples, converts units, reconciles
incompatible scope, or claims continuous/archival coverage from sparse data.

Historical comparisons are deliberately narrow: chain, category, subject,
metric, unit, evidence scope, source, and verification method must all be
selected explicitly.  Ordering uses canonical observation time, never database
insertion time.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
import json
import math
import re
import sqlite3
import time
from typing import Any


SCHEMA_VERSION = 1
CATEGORIES = frozenset(
    {"concentration", "wallet", "price", "liquidity", "supply", "activity"}
)
_NONNEGATIVE_CATEGORIES = frozenset(
    {"concentration", "price", "liquidity", "supply", "activity"}
)
_RECEIPT_RE = re.compile(r"^er_[0-9a-f]{64}$")
_PROOF_STRENGTHS = frozenset({"STRONG", "MODERATE", "WEAK"})


def _text(name: str, value: Any, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    text = value.strip()
    if not text:
        if required:
            raise ValueError(f"{name} is required")
        return None
    return text


def _strict_bool_or_none(name: str, value: Any) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be true, false, or null")
    return value


def _strict_true(name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    if value is not True:
        raise ValueError(f"{name} must be verified")
    return True


def _nonnegative_int(name: str, value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a non-negative integer")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.isdigit():
        result = int(value)
    else:
        raise ValueError(f"{name} must be a non-negative integer")
    if result < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return result


def _decimal_text(
    name: str,
    value: Any,
    *,
    required: bool = False,
    allow_negative: bool = True,
) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite numeric value")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite numeric value") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be a finite numeric value")
    if not allow_negative and parsed < 0:
        raise ValueError(f"{name} must not be negative")
    normalized = format(parsed, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"", "-0"} else normalized


def _canonical_utc_timestamp(name: str, value: Any) -> tuple[str, float]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        candidate = value.strip()
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    else:
        raise ValueError(f"{name} must be a timezone-aware datetime or ISO-8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    utc = parsed.astimezone(timezone.utc)
    return utc.isoformat().replace("+00:00", "Z"), utc.timestamp()


def _limitations(values: Sequence[Any] | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise ValueError("limitations must be a sequence of strings")
    normalized: set[str] = set()
    for index, value in enumerate(values):
        text = _text(f"limitations[{index}]", value, required=True)
        assert text is not None
        normalized.add(text)
    return sorted(normalized)


def _exact_ratio(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("exact_ratio must be an object with numerator and denominator")
    if set(value) != {"numerator", "denominator"}:
        raise ValueError("exact_ratio must contain only numerator and denominator")
    numerator = _nonnegative_int("exact_ratio.numerator", value.get("numerator"))
    denominator = _nonnegative_int("exact_ratio.denominator", value.get("denominator"))
    assert numerator is not None and denominator is not None
    if denominator == 0:
        raise ValueError("exact_ratio.denominator must be greater than zero")
    if numerator > denominator:
        raise ValueError("exact_ratio.numerator must not exceed denominator")
    fraction = Fraction(numerator, denominator)
    return {"numerator": str(fraction.numerator), "denominator": str(fraction.denominator)}


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
    identity_verified: bool = False,
    semantics_verified: bool = False,
    freshness_verified: bool | None = None,
    scope_complete: bool | None = None,
    evidence_receipt_id: Any = None,
    proof_strength: Any = None,
    proof_percent: Any = None,
    proof_score_method: Any = None,
    exact_ratio: Mapping[str, Any] | None = None,
    limitations: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build one deterministic normalized history observation.

    ``value`` is a presentation/query scalar.  For concentration ratios, callers
    must also supply ``exact_ratio`` so later comparisons use rational evidence
    rather than a rounded decimal string.
    """

    chain_text = _text("chain", chain, required=True)
    category_text = _text("category", category, required=True)
    subject = _text("subject_id", subject_id, required=True)
    metric_text = _text("metric", metric, required=True)
    unit_text = _text("unit", unit, required=True)
    source_text = _text("source", source, required=True)
    method = _text("verification_method", verification_method, required=True)
    scope = _text("evidence_scope", evidence_scope, required=True)
    assert all(
        value is not None
        for value in (
            chain_text,
            category_text,
            subject,
            metric_text,
            unit_text,
            source_text,
            method,
            scope,
        )
    )

    category_lower = category_text.lower()
    if category_lower not in CATEGORIES:
        raise ValueError(f"unsupported history category: {category_lower!r}")

    normalized_value = _decimal_text(
        "value",
        value,
        required=True,
        allow_negative=category_lower not in _NONNEGATIVE_CATEGORIES,
    )
    timestamp, timestamp_epoch = _canonical_utc_timestamp("observed_at", observed_at)
    slot = _nonnegative_int("block_slot", block_slot)
    _strict_true("identity_verified", identity_verified)
    _strict_true("semantics_verified", semantics_verified)
    freshness = _strict_bool_or_none("freshness_verified", freshness_verified)
    scope_is_complete = _strict_bool_or_none("scope_complete", scope_complete)

    receipt_id = _text("evidence_receipt_id", evidence_receipt_id)
    if receipt_id is not None and not _RECEIPT_RE.fullmatch(receipt_id):
        raise ValueError("evidence_receipt_id must be a content-addressed CMIS receipt id")

    strength = _text("proof_strength", proof_strength)
    if strength is not None:
        strength = strength.upper()
        if strength not in _PROOF_STRENGTHS:
            raise ValueError("proof_strength must be STRONG, MODERATE, WEAK, or null")

    percent = _decimal_text("proof_percent", proof_percent)
    if percent is not None:
        parsed_percent = Decimal(percent)
        if parsed_percent < 0 or parsed_percent > 100:
            raise ValueError("proof_percent must be between 0 and 100")

    score_method = _text("proof_score_method", proof_score_method)
    if any(value is not None for value in (strength, percent, score_method)) and not all(
        value is not None for value in (strength, percent, score_method)
    ):
        raise ValueError(
            "proof_strength, proof_percent, and proof_score_method must be supplied together"
        )

    ratio = _exact_ratio(exact_ratio)
    if category_lower == "concentration":
        if ratio is None:
            raise ValueError("concentration history requires exact_ratio evidence")
        if unit_text != "ratio":
            raise ValueError("concentration history unit must be 'ratio'")
        ratio_fraction = Fraction(int(ratio["numerator"]), int(ratio["denominator"]))
        if Decimal(normalized_value) < 0 or Decimal(normalized_value) > 1:
            raise ValueError("concentration value must be between 0 and 1")
        # The scalar is presentation metadata only; it must still be directionally
        # consistent with the exact ratio to prevent obvious forged observations.
        presentation = Decimal(normalized_value)
        exact_as_decimal = Decimal(ratio_fraction.numerator) / Decimal(ratio_fraction.denominator)
        if abs(presentation - exact_as_decimal) > Decimal("0.000000000001"):
            raise ValueError("concentration value does not match exact_ratio evidence")
    elif ratio is not None:
        raise ValueError("exact_ratio is currently supported only for concentration history")

    base = {
        "schema_version": SCHEMA_VERSION,
        "chain": chain_text.lower(),
        "category": category_lower,
        "subject_id": subject,
        "metric": metric_text,
        "value": normalized_value,
        "unit": unit_text,
        "observed_at": timestamp,
        "observed_at_epoch": timestamp_epoch,
        "block_slot": slot,
        "source": source_text,
        "verification_method": method,
        "evidence_scope": scope,
        "identity_verified": True,
        "semantics_verified": True,
        "freshness_verified": freshness,
        "scope_complete": scope_is_complete,
        "evidence_receipt_id": receipt_id,
        "proof_strength": strength,
        "proof_percent": percent,
        "proof_score_method": score_method,
        "exact_ratio": ratio,
        "limitations": _limitations(limitations),
        "continuous_coverage_proven": False,
        "archival_completeness_proven": False,
        "interpolation_performed": False,
        "missing_samples_filled": False,
    }
    return {"observation_id": _observation_id(base), **base}


def _validated_observation(observation: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(observation, Mapping):
        raise TypeError("history observation must be a mapping")
    record = dict(observation)
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported history observation schema")
    if record.get("continuous_coverage_proven") is not False:
        raise ValueError("sparse observation cannot claim continuous coverage")
    if record.get("archival_completeness_proven") is not False:
        raise ValueError("sparse observation cannot claim archival completeness")
    if record.get("interpolation_performed") is not False:
        raise ValueError("history observation cannot claim interpolation")
    if record.get("missing_samples_filled") is not False:
        raise ValueError("history observation cannot claim filled samples")

    rebuilt = build_history_observation(
        chain=record.get("chain"),
        category=record.get("category"),
        subject_id=record.get("subject_id"),
        metric=record.get("metric"),
        value=record.get("value"),
        unit=record.get("unit"),
        observed_at=record.get("observed_at"),
        source=record.get("source"),
        verification_method=record.get("verification_method"),
        evidence_scope=record.get("evidence_scope"),
        block_slot=record.get("block_slot"),
        identity_verified=record.get("identity_verified"),
        semantics_verified=record.get("semantics_verified"),
        freshness_verified=record.get("freshness_verified"),
        scope_complete=record.get("scope_complete"),
        evidence_receipt_id=record.get("evidence_receipt_id"),
        proof_strength=record.get("proof_strength"),
        proof_percent=record.get("proof_percent"),
        proof_score_method=record.get("proof_score_method"),
        exact_ratio=record.get("exact_ratio"),
        limitations=record.get("limitations"),
    )
    if rebuilt != record:
        raise ValueError("history observation content or content-addressed id is inconsistent")
    return rebuilt


class IntelligenceHistoryLedger:
    """SQLite-backed store for sanitized, content-addressed observations."""

    def __init__(self, db_path: str):
        if not isinstance(db_path, str) or not db_path.strip():
            raise ValueError("db_path is required")
        self.db_path = db_path.strip()
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
                    evidence_scope TEXT NOT NULL,
                    source TEXT NOT NULL,
                    verification_method TEXT NOT NULL,
                    observed_at_text TEXT NOT NULL,
                    observed_at_epoch REAL NOT NULL,
                    block_slot INTEGER,
                    recorded_at_epoch REAL NOT NULL,
                    observation_json TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_intelligence_history_exact_series
                ON intelligence_history (
                    chain, category, subject_id, metric, unit,
                    evidence_scope, source, verification_method,
                    observed_at_epoch, observation_id
                )
                """
            )

    def store(
        self,
        observation: Mapping[str, Any],
        *,
        recorded_at: Any = None,
    ) -> dict[str, Any]:
        safe = _validated_observation(observation)
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
                    evidence_scope, source, verification_method,
                    observed_at_text, observed_at_epoch, block_slot,
                    recorded_at_epoch, observation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    safe["observation_id"],
                    safe["chain"],
                    safe["category"],
                    safe["subject_id"],
                    safe["metric"],
                    safe["unit"],
                    safe["evidence_scope"],
                    safe["source"],
                    safe["verification_method"],
                    safe["observed_at"],
                    safe["observed_at_epoch"],
                    safe["block_slot"],
                    timestamp,
                    canonical,
                ),
            )
            inserted = cursor.rowcount == 1
        return {
            "observation_id": safe["observation_id"],
            "inserted": inserted,
            "recorded_at_epoch": timestamp,
        }

    def find(
        self,
        *,
        chain: str,
        category: str,
        subject_id: str,
        metric: str,
        unit: str | None = None,
        evidence_scope: str | None = None,
        source: str | None = None,
        verification_method: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        chain_text = _text("chain", chain, required=True)
        category_text = _text("category", category, required=True)
        subject = _text("subject_id", subject_id, required=True)
        metric_text = _text("metric", metric, required=True)
        assert all(v is not None for v in (chain_text, category_text, subject, metric_text))
        category_lower = category_text.lower()
        if category_lower not in CATEGORIES:
            raise ValueError("unsupported history category")
        if isinstance(limit, bool) or not isinstance(limit, int) or not (1 <= limit <= 1000):
            raise ValueError("limit must be an integer between 1 and 1000")

        clauses = ["chain = ?", "category = ?", "subject_id = ?", "metric = ?"]
        params: list[Any] = [chain_text.lower(), category_lower, subject, metric_text]
        for column, raw in (
            ("unit", unit),
            ("evidence_scope", evidence_scope),
            ("source", source),
            ("verification_method", verification_method),
        ):
            if raw is not None:
                text = _text(column, raw, required=True)
                clauses.append(f"{column} = ?")
                params.append(text)
        params.append(limit)

        with self._connect() as db:
            rows = db.execute(
                f"""
                SELECT observation_id, recorded_at_epoch, observation_json
                FROM intelligence_history
                WHERE {' AND '.join(clauses)}
                ORDER BY observed_at_epoch ASC, block_slot ASC, observation_id ASC
                LIMIT ?
                """,
                params,
            ).fetchall()

        result: list[dict[str, Any]] = []
        for row in rows:
            observation = json.loads(row["observation_json"])
            safe = _validated_observation(observation)
            if safe["observation_id"] != row["observation_id"]:
                raise ValueError("stored history observation id mismatch")
            result.append(
                {
                    "observation_id": row["observation_id"],
                    "recorded_at_epoch": row["recorded_at_epoch"],
                    "observation": safe,
                }
            )
        return result

    def compare_first_last(
        self,
        *,
        chain: str,
        category: str,
        subject_id: str,
        metric: str,
        unit: str,
        evidence_scope: str,
        source: str,
        verification_method: str,
    ) -> dict[str, Any]:
        """Compare exact compatible sparse samples without overclaiming history."""

        rows = self.find(
            chain=chain,
            category=category,
            subject_id=subject_id,
            metric=metric,
            unit=unit,
            evidence_scope=evidence_scope,
            source=source,
            verification_method=verification_method,
            limit=1000,
        )
        base = {
            "sample_count": len(rows),
            "continuous_coverage_proven": False,
            "archival_completeness_proven": False,
            "interpolation_performed": False,
            "missing_samples_filled": False,
        }
        if len(rows) < 2:
            return {
                **base,
                "status": "INSUFFICIENT_EVIDENCE",
                "absolute_change": None,
                "percent_change": None,
                "exact_ratio_change": None,
            }

        observations = [row["observation"] for row in rows]
        first_time = observations[0]["observed_at"]
        last_time = observations[-1]["observed_at"]
        if first_time == last_time:
            return {
                **base,
                "status": "AMBIGUOUS_BOUNDARY",
                "absolute_change": None,
                "percent_change": None,
                "exact_ratio_change": None,
                "reason": "earliest and latest compatible samples share one observation time",
            }

        first_candidates = [item for item in observations if item["observed_at"] == first_time]
        last_candidates = [item for item in observations if item["observed_at"] == last_time]
        if len(first_candidates) != 1 or len(last_candidates) != 1:
            return {
                **base,
                "status": "AMBIGUOUS_BOUNDARY",
                "absolute_change": None,
                "percent_change": None,
                "exact_ratio_change": None,
                "reason": "multiple compatible samples exist at a comparison boundary time",
            }

        first = first_candidates[0]
        last = last_candidates[0]
        first_ratio = first.get("exact_ratio")
        last_ratio = last.get("exact_ratio")
        if (first_ratio is None) != (last_ratio is None):
            return {
                **base,
                "status": "INCOMPATIBLE_REPRESENTATION",
                "absolute_change": None,
                "percent_change": None,
                "exact_ratio_change": None,
            }

        if first_ratio is not None:
            before = Fraction(int(first_ratio["numerator"]), int(first_ratio["denominator"]))
            after = Fraction(int(last_ratio["numerator"]), int(last_ratio["denominator"]))
            delta = after - before
            percent = None if before == 0 else (delta / before) * 100
            exact_delta = {
                "numerator": str(delta.numerator),
                "denominator": str(delta.denominator),
            }
            absolute_change = _decimal_text(
                "absolute_change",
                Decimal(delta.numerator) / Decimal(delta.denominator),
                required=True,
                allow_negative=True,
            )
            percent_change = (
                None
                if percent is None
                else _decimal_text(
                    "percent_change",
                    Decimal(percent.numerator) / Decimal(percent.denominator),
                    required=True,
                    allow_negative=True,
                )
            )
        else:
            before_decimal = Decimal(first["value"])
            after_decimal = Decimal(last["value"])
            delta_decimal = after_decimal - before_decimal
            absolute_change = _decimal_text(
                "absolute_change", delta_decimal, required=True, allow_negative=True
            )
            percent_change = (
                None
                if before_decimal == 0
                else _decimal_text(
                    "percent_change",
                    (delta_decimal / before_decimal) * Decimal(100),
                    required=True,
                    allow_negative=True,
                )
            )
            exact_delta = None

        return {
            **base,
            "status": "OBSERVED_CHANGE",
            "first_observation": first,
            "last_observation": last,
            "absolute_change": absolute_change,
            "percent_change": percent_change,
            "exact_ratio_change": exact_delta,
            "observed_window": {"start": first_time, "end": last_time},
            "limitations": [
                "sparse_observation_comparison_only",
                "no_interpolation",
                "no_continuous_coverage_claim",
                "no_archival_completeness_claim",
            ],
        }


__all__ = [
    "CATEGORIES",
    "SCHEMA_VERSION",
    "IntelligenceHistoryLedger",
    "build_history_observation",
]
