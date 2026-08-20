"""CMIS-owned persistence for the first bounded Phase 12 intelligence contract.

The public/Scout service must never trust a caller-supplied evidence bundle merely
because it is content-addressed and internally self-consistent.  This ledger is
the internal trust root for the first promoted slice: one already-built,
deterministically revalidated ``top_account_concentration_change`` intelligence
evidence bundle is stored by CMIS and later resolved by its ``ie_...`` id.

No public store endpoint is defined here.  Provider payloads, wallet authority,
transaction preparation, signing, broadcasting, custody, execution, and value
movement are outside this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
import math
import re
import sqlite3
import time
from typing import Any

from liquidity_scout.cmis.intelligence_evidence import build_intelligence_evidence_bundle


VERSION = "1.0"
ACCEPTED_CONCLUSION_TYPE = "top_account_concentration_change"
_ID_RE = re.compile(r"^ie_[0-9a-f]{64}$")


def normalize_intelligence_evidence_id(value: Any) -> str:
    if not isinstance(value, str) or value.strip() != value or not _ID_RE.fullmatch(value):
        raise ValueError("intelligence_evidence_id must be a canonical ie_ content id")
    return value


def validate_concentration_change_intelligence_evidence(value: Any) -> dict[str, Any]:
    """Return one exact canonical concentration-change intelligence bundle.

    This validates deterministic integrity only.  Trust that the record is
    CMIS-owned comes from resolving it through this internal ledger, not from the
    content id itself.
    """
    if not isinstance(value, Mapping):
        raise TypeError("intelligence evidence must be a mapping")
    supplied = deepcopy(dict(value))
    if supplied.get("conclusion_type") != ACCEPTED_CONCLUSION_TYPE:
        raise ValueError(
            "the Phase 12 store accepts only top_account_concentration_change evidence"
        )
    rebuilt = build_intelligence_evidence_bundle(
        conclusion_type=ACCEPTED_CONCLUSION_TYPE,
        conclusion=supplied.get("conclusion"),
        evidence_bundles=supplied.get("evidence_bundles"),
    )
    if supplied != rebuilt:
        raise ValueError("intelligence evidence does not match its deterministic canonical bundle")
    normalize_intelligence_evidence_id(rebuilt.get("intelligence_evidence_id"))
    return rebuilt


class IntelligenceEvidenceLedger:
    """SQLite-backed CMIS-owned store for canonical concentration-change evidence."""

    def __init__(self, db_path: str):
        if not isinstance(db_path, str) or not db_path.strip():
            raise ValueError("db_path is required")
        self.db_path = db_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS intelligence_evidence (
                    intelligence_evidence_id TEXT PRIMARY KEY,
                    chain TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    conclusion_type TEXT NOT NULL,
                    recorded_at REAL NOT NULL,
                    bundle_json TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_intelligence_evidence_subject
                ON intelligence_evidence (chain, asset_id, conclusion_type, recorded_at)
                """
            )

    def store(self, bundle: Mapping[str, Any], *, recorded_at: Any = None) -> dict[str, Any]:
        safe = validate_concentration_change_intelligence_evidence(bundle)
        timestamp = time.time() if recorded_at is None else recorded_at
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise ValueError("recorded_at must be a finite numeric timestamp")
        timestamp = float(timestamp)
        if not math.isfinite(timestamp):
            raise ValueError("recorded_at must be a finite numeric timestamp")

        conclusion = safe["conclusion"]
        chain = str(conclusion.get("chain") or "").strip().lower()
        asset_id = str(conclusion.get("asset_id") or "").strip()
        if not chain or not asset_id:
            raise ValueError("canonical intelligence evidence requires chain and asset_id")
        evidence_id = safe["intelligence_evidence_id"]
        canonical = json.dumps(
            safe,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

        with self._connect() as db:
            cursor = db.execute(
                """
                INSERT OR IGNORE INTO intelligence_evidence (
                    intelligence_evidence_id,
                    chain,
                    asset_id,
                    conclusion_type,
                    recorded_at,
                    bundle_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence_id,
                    chain,
                    asset_id,
                    ACCEPTED_CONCLUSION_TYPE,
                    timestamp,
                    canonical,
                ),
            )
            inserted = cursor.rowcount == 1

        return {
            "intelligence_evidence_id": evidence_id,
            "inserted": inserted,
            "recorded_at": timestamp,
        }

    def get(self, intelligence_evidence_id: Any) -> dict[str, Any] | None:
        evidence_id = normalize_intelligence_evidence_id(intelligence_evidence_id)
        with self._connect() as db:
            row = db.execute(
                """
                SELECT bundle_json
                FROM intelligence_evidence
                WHERE intelligence_evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            decoded = json.loads(row["bundle_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("stored intelligence evidence is not valid canonical JSON") from exc
        safe = validate_concentration_change_intelligence_evidence(decoded)
        if safe["intelligence_evidence_id"] != evidence_id:
            raise ValueError("stored intelligence evidence id does not match lookup key")
        return safe


__all__ = [
    "ACCEPTED_CONCLUSION_TYPE",
    "IntelligenceEvidenceLedger",
    "VERSION",
    "normalize_intelligence_evidence_id",
    "validate_concentration_change_intelligence_evidence",
]
