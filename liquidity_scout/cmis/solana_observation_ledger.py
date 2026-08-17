"""Provenance-preserving historical observation ledger for Solana CMIS.

This ledger is deliberately separate from the legacy XDEX snapshot schema.
Solana history preserves exact source, scope, subject, pair, collection time,
and trust flags so comparisons cannot silently mix Jupiter, DEX-pair, or RPC
facts. No arbitrary provider payloads, URLs, headers, or credentials are stored.
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

VERSION = "1.0"
CHAIN = "solana"
PRICE_USD = "price_usd"
LIQUIDITY_USD = "liquidity_usd"
VOLUME_24H_USD = "volume_24h_usd"
TOTAL_SUPPLY_RAW = "total_supply_raw"
METRICS = frozenset({PRICE_USD, LIQUIDITY_USD, VOLUME_24H_USD, TOTAL_SUPPLY_RAW})
JUPITER_SOURCE = "jupiter_price_v3"
DEX_SOURCE = "dexscreener_token_pairs_v1"
RPC_SOURCE = "solana_rpc"
SOURCES = frozenset({JUPITER_SOURCE, DEX_SOURCE, RPC_SOURCE})
JUPITER_SCOPE = "jupiter_price_v3"
DEX_PAIR_SCOPE = "dex_pair"
RPC_SUPPLY_SCOPE = "canonical_total_supply"
SCOPES = frozenset({JUPITER_SCOPE, DEX_PAIR_SCOPE, RPC_SUPPLY_SCOPE})
_SOURCE_ROLES = {
    (JUPITER_SOURCE, PRICE_USD): "market.price_source",
    (DEX_SOURCE, PRICE_USD): "market.pair_price",
    (DEX_SOURCE, LIQUIDITY_USD): "market.pair_liquidity",
    (DEX_SOURCE, VOLUME_24H_USD): "market.pair_volume_24h",
    (RPC_SOURCE, TOTAL_SUPPLY_RAW): "tokenomics.total_supply",
}
_UNITS = {
    PRICE_USD: "USD_PER_TOKEN",
    LIQUIDITY_USD: "USD",
    VOLUME_24H_USD: "USD",
    TOTAL_SUPPLY_RAW: "TOKEN_BASE_UNITS",
}
_ALLOWED_INPUT_FIELDS = frozenset({
    "chain", "mint", "metric", "source", "scope", "subject_id",
    "pair_address", "requested_mint_role", "base_mint", "quote_mint", "value",
    "provider_observed_at", "provider_block_id", "provider_block_slot",
    "identity_verified", "semantics_verified", "freshness_verified",
})
_BASE58_ALPHABET = frozenset(
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
)


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _pubkey(value: Any, *, field: str, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    text = _text(value)
    if text is None or not 32 <= len(text) <= 44 or any(c not in _BASE58_ALPHABET for c in text):
        raise ValueError(f"{field} must be an exact Solana base58 public key")
    return text


def _timestamp(value: Any, *, field: str, required: bool = False) -> float | None:
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite numeric timestamp")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError(f"{field} must be a non-negative finite numeric timestamp")
    return parsed


def _nonnegative_int(value: Any, *, field: str, required: bool = False) -> int | None:
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _decimal_text(value: Any, *, metric: str) -> str:
    if isinstance(value, bool) or value is None:
        raise ValueError("observation value must be a non-negative numeric scalar")
    if metric == TOTAL_SUPPLY_RAW:
        if isinstance(value, int):
            if value < 0:
                raise ValueError("total_supply_raw must be non-negative")
            return str(value)
        text = _text(value)
        if text is None or not text.isdigit():
            raise ValueError("total_supply_raw must be an integer base-unit string")
        return text.lstrip("0") or "0"
    if not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("observation value must be numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("observation value must be numeric") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("observation value must be non-negative and finite")
    if metric == PRICE_USD and parsed <= 0:
        raise ValueError("price_usd must be greater than zero")
    text = format(parsed, "f")
    normalized = text.rstrip("0").rstrip(".") if "." in text else text
    return normalized or "0"


def _boolean(value: Any, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be boolean")
    return value


def _validate_contract(source: str, scope: str, metric: str) -> None:
    allowed = {
        (JUPITER_SOURCE, JUPITER_SCOPE, PRICE_USD),
        (DEX_SOURCE, DEX_PAIR_SCOPE, PRICE_USD),
        (DEX_SOURCE, DEX_PAIR_SCOPE, LIQUIDITY_USD),
        (DEX_SOURCE, DEX_PAIR_SCOPE, VOLUME_24H_USD),
        (RPC_SOURCE, RPC_SUPPLY_SCOPE, TOTAL_SUPPLY_RAW),
    }
    if (source, scope, metric) not in allowed:
        raise ValueError("source, scope, and metric are not an accepted Solana observation contract")


def sanitize_solana_observation(
    observation: Mapping[str, Any], *, collected_at: Any = None
) -> dict[str, Any]:
    if not isinstance(observation, Mapping):
        raise TypeError("Solana observation must be a mapping")
    if set(observation) - _ALLOWED_INPUT_FIELDS:
        raise ValueError("Solana observation contains unsupported fields")
    if observation.get("chain") != CHAIN:
        raise ValueError("Solana observation chain must be solana")

    mint = _pubkey(observation.get("mint"), field="mint")
    subject = _pubkey(observation.get("subject_id"), field="subject_id")
    metric = _text(observation.get("metric"))
    source = _text(observation.get("source"))
    scope = _text(observation.get("scope"))
    if metric not in METRICS:
        raise ValueError("Solana observation metric is unsupported")
    if source not in SOURCES:
        raise ValueError("Solana observation source is unsupported")
    if scope not in SCOPES:
        raise ValueError("Solana observation scope is unsupported")
    _validate_contract(source, scope, metric)

    pair = _pubkey(observation.get("pair_address"), field="pair_address", required=False)
    base = _pubkey(observation.get("base_mint"), field="base_mint", required=False)
    quote = _pubkey(observation.get("quote_mint"), field="quote_mint", required=False)
    role = _text(observation.get("requested_mint_role"))
    provider_observed_at = _timestamp(
        observation.get("provider_observed_at"), field="provider_observed_at"
    )
    block_id = _nonnegative_int(observation.get("provider_block_id"), field="provider_block_id")
    block_slot = _nonnegative_int(observation.get("provider_block_slot"), field="provider_block_slot")
    identity_verified = _boolean(observation.get("identity_verified"), field="identity_verified")
    semantics_verified = _boolean(observation.get("semantics_verified"), field="semantics_verified")
    freshness_verified = _boolean(observation.get("freshness_verified"), field="freshness_verified")

    if source == JUPITER_SOURCE:
        if subject != mint:
            raise ValueError("Jupiter price subject must equal the exact requested mint")
        if any(v is not None for v in (pair, base, quote, role)):
            raise ValueError("Jupiter observations must not carry DEX-pair dimensions")
        if block_id is None:
            raise ValueError("Jupiter price observation requires provider_block_id")
        if block_slot is not None:
            raise ValueError("Jupiter price observation must not claim a Solana RPC slot")
    elif source == DEX_SOURCE:
        if pair is None or base is None or quote is None:
            raise ValueError("DEX-pair observations require pair, base mint, and quote mint")
        if base == quote:
            raise ValueError("DEX-pair base and quote mints must differ")
        if role not in {"base", "quote"}:
            raise ValueError("DEX-pair requested_mint_role must be base or quote")
        if mint != (base if role == "base" else quote):
            raise ValueError("DEX-pair requested mint role does not match pair token identity")
        if block_id is not None or block_slot is not None:
            raise ValueError("DEX Screener observations must not invent block identity")
        if metric == PRICE_USD and subject != base:
            raise ValueError("DEX Screener price subject must be the pair base token")
        if metric != PRICE_USD and subject != pair:
            raise ValueError("DEX pair liquidity/volume subject must be the pair address")
    else:
        if subject != mint:
            raise ValueError("canonical supply subject must equal the exact mint")
        if any(v is not None for v in (pair, base, quote, role)):
            raise ValueError("canonical supply observations must not carry DEX-pair dimensions")
        if block_slot is None:
            raise ValueError("canonical total-supply observation requires provider_block_slot")
        if block_id is not None:
            raise ValueError("canonical RPC supply observation must not claim Jupiter block_id")

    collected = _timestamp(
        time.time() if collected_at is None else collected_at,
        field="collected_at",
        required=True,
    )
    assert mint and subject and metric and source and scope and collected is not None
    return {
        "version": VERSION,
        "chain": CHAIN,
        "mint": mint,
        "metric": metric,
        "source": source,
        "source_role": _SOURCE_ROLES[(source, metric)],
        "scope": scope,
        "subject_id": subject,
        "pair_address": pair,
        "requested_mint_role": role,
        "base_mint": base,
        "quote_mint": quote,
        "value": _decimal_text(observation.get("value"), metric=metric),
        "unit": _UNITS[metric],
        "provider_observed_at": provider_observed_at,
        "provider_block_id": block_id,
        "provider_block_slot": block_slot,
        "collected_at": collected,
        "timestamp_basis": "collection_time",
        "identity_verified": identity_verified,
        "semantics_verified": semantics_verified,
        "freshness_verified": freshness_verified,
    }


def _canonical_json(record: Mapping[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def observation_id_for(record: Mapping[str, Any]) -> str:
    return "so_" + hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()


class SolanaObservationLedger:
    """SQLite ledger that keeps historical source/scope dimensions exact."""

    def __init__(self, db_path: str):
        path = _text(db_path)
        if path is None:
            raise ValueError("db_path is required")
        self.db_path = path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS solana_observations (
                    observation_id TEXT PRIMARY KEY,
                    chain TEXT NOT NULL,
                    mint TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_role TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    subject_id TEXT NOT NULL,
                    pair_address TEXT,
                    collected_at REAL NOT NULL,
                    provider_observed_at REAL,
                    provider_block_id INTEGER,
                    provider_block_slot INTEGER,
                    value_text TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    identity_verified INTEGER NOT NULL,
                    semantics_verified INTEGER NOT NULL,
                    freshness_verified INTEGER NOT NULL,
                    observation_json TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_solana_observations_dimensions
                ON solana_observations (
                    mint, metric, source, scope, subject_id, pair_address, collected_at
                )
            """)

    def store(self, observation: Mapping[str, Any], *, collected_at: Any = None) -> dict[str, Any]:
        safe = sanitize_solana_observation(observation, collected_at=collected_at)
        oid = observation_id_for(safe)
        canonical = _canonical_json(safe)
        with self._connect() as db:
            cursor = db.execute("""
                INSERT OR IGNORE INTO solana_observations (
                    observation_id, chain, mint, metric, source, source_role, scope,
                    subject_id, pair_address, collected_at, provider_observed_at,
                    provider_block_id, provider_block_slot, value_text, unit,
                    identity_verified, semantics_verified, freshness_verified,
                    observation_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                oid, safe["chain"], safe["mint"], safe["metric"], safe["source"],
                safe["source_role"], safe["scope"], safe["subject_id"], safe["pair_address"],
                safe["collected_at"], safe["provider_observed_at"], safe["provider_block_id"],
                safe["provider_block_slot"], safe["value"], safe["unit"],
                int(safe["identity_verified"]), int(safe["semantics_verified"]),
                int(safe["freshness_verified"]), canonical,
            ))
            inserted = cursor.rowcount == 1
        return {
            "observation_id": oid,
            "inserted": inserted,
            "collected_at": safe["collected_at"],
            "timestamp_basis": "collection_time",
        }

    def get(self, observation_id: Any) -> dict[str, Any] | None:
        key = _text(observation_id)
        if key is None:
            return None
        with self._connect() as db:
            row = db.execute(
                "SELECT observation_id, observation_json FROM solana_observations WHERE observation_id = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return {"observation_id": row["observation_id"], "observation": json.loads(row["observation_json"])}

    def find(
        self, *, mint: Any, metric: Any = None, source: Any = None,
        scope: Any = None, subject_id: Any = None, pair_address: Any = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        mint_text = _pubkey(mint, field="mint")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("limit must be an integer from 1 to 500")
        clauses = ["mint = ?"]
        args: list[Any] = [mint_text]
        for column, value, allowed in (
            ("metric", metric, METRICS), ("source", source, SOURCES), ("scope", scope, SCOPES)
        ):
            if value is not None:
                text = _text(value)
                if text not in allowed:
                    raise ValueError(f"{column} is unsupported")
                clauses.append(f"{column} = ?")
                args.append(text)
        if subject_id is not None:
            clauses.append("subject_id = ?")
            args.append(_pubkey(subject_id, field="subject_id"))
        if pair_address is not None:
            clauses.append("pair_address = ?")
            args.append(_pubkey(pair_address, field="pair_address"))
        args.append(limit)
        with self._connect() as db:
            rows = db.execute(f"""
                SELECT observation_id, observation_json FROM solana_observations
                WHERE {' AND '.join(clauses)}
                ORDER BY collected_at DESC, observation_id DESC LIMIT ?
            """, tuple(args)).fetchall()
        return [
            {"observation_id": row["observation_id"], "observation": json.loads(row["observation_json"])}
            for row in rows
        ]

    def nearest(
        self, *, mint: Any, metric: Any, source: Any, scope: Any, subject_id: Any,
        target_time: Any, max_distance_seconds: Any, pair_address: Any = None,
    ) -> dict[str, Any] | None:
        """Return nearest identity/semantics-verified observation with exact dimensions.

        Selection deliberately uses CMIS collection time. Current accepted Solana
        market providers do not establish a shared verified provider observation
        timestamp, so collection time is never relabelled as provider time.
        """
        mint_text = _pubkey(mint, field="mint")
        subject_text = _pubkey(subject_id, field="subject_id")
        metric_text, source_text, scope_text = _text(metric), _text(source), _text(scope)
        if metric_text not in METRICS:
            raise ValueError("metric is unsupported")
        if source_text not in SOURCES:
            raise ValueError("source is unsupported")
        if scope_text not in SCOPES:
            raise ValueError("scope is unsupported")
        _validate_contract(source_text, scope_text, metric_text)
        pair_text = _pubkey(pair_address, field="pair_address", required=False)
        if source_text == DEX_SOURCE and pair_text is None:
            raise ValueError("DEX historical lookup requires exact pair_address")
        if source_text != DEX_SOURCE and pair_text is not None:
            raise ValueError("non-DEX historical lookup must not include pair_address")
        if source_text in {JUPITER_SOURCE, RPC_SOURCE} and subject_text != mint_text:
            raise ValueError("canonical source historical lookup subject must equal mint")
        if source_text == DEX_SOURCE and metric_text in {LIQUIDITY_USD, VOLUME_24H_USD} and subject_text != pair_text:
            raise ValueError("DEX liquidity/volume historical subject must equal pair_address")
        target = _timestamp(target_time, field="target_time", required=True)
        distance = _timestamp(max_distance_seconds, field="max_distance_seconds", required=True)
        assert target is not None and distance is not None

        clauses = [
            "mint = ?", "metric = ?", "source = ?", "scope = ?", "subject_id = ?",
            "identity_verified = 1", "semantics_verified = 1",
        ]
        args: list[Any] = [mint_text, metric_text, source_text, scope_text, subject_text]
        if pair_text is None:
            clauses.append("pair_address IS NULL")
        else:
            clauses.append("pair_address = ?")
            args.append(pair_text)
        args.append(target)
        with self._connect() as db:
            row = db.execute(f"""
                SELECT observation_id, collected_at, observation_json
                FROM solana_observations
                WHERE {' AND '.join(clauses)}
                ORDER BY ABS(collected_at - ?) ASC, collected_at ASC LIMIT 1
            """, tuple(args)).fetchone()
        if row is None:
            return None
        actual_distance = abs(float(row["collected_at"]) - target)
        if actual_distance > distance:
            return None
        return {
            "observation_id": row["observation_id"],
            "observation": json.loads(row["observation_json"]),
            "distance_seconds": actual_distance,
            "timestamp_basis": "collection_time",
        }


__all__ = [
    "CHAIN", "DEX_PAIR_SCOPE", "DEX_SOURCE", "JUPITER_SCOPE", "JUPITER_SOURCE",
    "LIQUIDITY_USD", "METRICS", "PRICE_USD", "RPC_SOURCE", "RPC_SUPPLY_SCOPE",
    "SCOPES", "SOURCES", "SolanaObservationLedger", "TOTAL_SUPPLY_RAW", "VERSION",
    "VOLUME_24H_USD", "observation_id_for", "sanitize_solana_observation",
]
