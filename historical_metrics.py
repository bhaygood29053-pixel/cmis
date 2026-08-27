import json
import math
import os
import re
import sqlite3
import time
from datetime import datetime

DB_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "liquidity_scout_history.db",
)

PERIODS = {
    "24h": 86400,
    "7d": 7 * 86400,
    "30d": 30 * 86400,
}

METRIC_COLUMNS = {
    "price": "price",
    "liquidity": "liquidity",
    "volume": "volume24",
    "transactions": "transactions24",
    "holders": "holders",
    "supply": "total_supply",
    "pool_count": "pool_count",
}


def parse_historical_comparison(question):
    """
    Parse questions such as:
      Has AGI liquidity fallen more than 30% this week?
      Did X1X volume increase 20% in 24 hours?
      Are AGI holders down 5% this month?
    """
    q = str(question or "").lower().strip()

    metric = None

    if re.search(r"\b(liquidity|liq)\b", q):
        metric = "liquidity"
    elif re.search(r"\bvolume\b", q):
        metric = "volume"
    elif re.search(r"\bholders?\b", q):
        metric = "holders"
    elif re.search(r"\bburn(?:ed|s|ing)?\b", q):
        metric = "burns"
    elif "supply" in q:
        metric = "supply"
    elif re.search(r"\bprice\b", q):
        metric = "price"

    if not metric:
        return None

    comparison_terms = (
        "fallen", "falling", "fell",
        "dropped", "drop", "declined", "decreased",
        "down", "lower",
        "increased", "increase", "risen", "rose",
        "up", "higher", "gained",
        "changed", "change",
        "compared", "compare", "versus", " vs ",
        "trend", "trending",
        "more than", "less than",
        "at least", "at most",
        "over the last", "in the last",
        "this week", "last week",
        "this month", "last month",
        "ago", "since",
    )

    has_comparison = (
        any(term in q for term in comparison_terms)
        or "%" in q
    )

    if not has_comparison:
        return None

    # -------------------------
    # Period
    # -------------------------

    period = None

    if (
        re.search(r"\b24\s*h\b", q)
        or "24 hours" in q
        or "24-hour" in q
        or "one day" in q
        or "1 day" in q
        or "yesterday" in q
    ):
        period = "24h"

    elif (
        re.search(r"\b7\s*d\b", q)
        or "7 days" in q
        or "seven days" in q
        or "this week" in q
        or "last week" in q
        or "one week" in q
        or "1 week" in q
    ):
        period = "7d"

    elif (
        re.search(r"\b30\s*d\b", q)
        or "30 days" in q
        or "thirty days" in q
        or "this month" in q
        or "last month" in q
        or "one month" in q
        or "1 month" in q
    ):
        period = "30d"

    # -------------------------
    # Direction
    # -------------------------

    direction = None

    down_terms = (
        "fallen", "falling", "fell",
        "dropped", "drop",
        "declined", "decreased",
        "down", "lower",
    )

    up_terms = (
        "increased", "increase",
        "risen", "rose",
        "up", "higher", "gained",
    )

    if any(term in q for term in down_terms):
        direction = "down"
    elif any(term in q for term in up_terms):
        direction = "up"

    # -------------------------
    # Percentage threshold
    # -------------------------

    threshold = None
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", q)

    if match:
        threshold = float(match.group(1))

    comparator = None

    if "at least" in q:
        comparator = "at_least"
    elif "at most" in q:
        comparator = "at_most"
    elif "less than" in q or "under" in q:
        comparator = "less_than"
    elif (
        "more than" in q
        or "over " in q
        or "greater than" in q
    ):
        comparator = "more_than"

    return {
        "metric": metric,
        "period": period,
        "period_seconds": PERIODS.get(period),
        "direction": direction,
        "threshold": threshold,
        "comparator": comparator,
    }


def open_db():
    db = sqlite3.connect(DB_FILE)

    db.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mint TEXT NOT NULL,
            symbol TEXT NOT NULL,
            ts INTEGER NOT NULL,
            price REAL,
            liquidity REAL,
            volume24 REAL,
            holders REAL,
            total_supply REAL,
            pool_count INTEGER,
            transactions24 REAL
        )
    """)

    columns = {
        row[1]
        for row in db.execute("PRAGMA table_info(snapshots)").fetchall()
    }
    if "transactions24" not in columns:
        db.execute("ALTER TABLE snapshots ADD COLUMN transactions24 REAL")

    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshots_mint_ts
        ON snapshots (mint, ts)
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS verified_price_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mint TEXT NOT NULL,
            symbol TEXT NOT NULL,
            ts INTEGER NOT NULL,
            price_usd REAL NOT NULL,
            source TEXT NOT NULL,
            provider_pair TEXT NOT NULL,
            quote_mint TEXT NOT NULL,
            quote_unit TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            imported_at INTEGER NOT NULL,
            UNIQUE (mint, ts, source, provider_pair)
        )
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_verified_price_mint_ts
        ON verified_price_observations (mint, ts)
    """)

    db.commit()
    return db


def record_snapshot(
    mint,
    symbol,
    price=None,
    liquidity=None,
    volume24=None,
    holders=None,
    total_supply=None,
    pool_count=None,
    transactions24=None,
    timestamp=None,
):
    if not mint:
        return

    db = open_db()

    db.execute(
        """
        INSERT INTO snapshots (
            mint,
            symbol,
            ts,
            price,
            liquidity,
            volume24,
            holders,
            total_supply,
            pool_count,
            transactions24
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mint,
            symbol,
            int(time.time()) if timestamp is None else int(timestamp),
            price,
            liquidity,
            volume24,
            holders,
            total_supply,
            pool_count,
            transactions24,
        ),
    )

    db.commit()
    db.close()


def record_verified_price_observation(
    *,
    mint,
    symbol,
    timestamp,
    price_usd,
    source,
    provider_pair,
    quote_mint,
    quote_unit="configured_usd_stable",
    evidence=None,
    imported_at=None,
):
    """Persist one externally backfilled USD price with explicit provenance.

    This table is intentionally separate from current CMIS snapshots. Imported
    provider history must never lose its source/evidence boundary merely because
    historical consumers read it through the shared price metric.
    """

    mint = str(mint or "").strip()
    symbol = str(symbol or "").strip() or "Unknown"
    source = str(source or "").strip()
    provider_pair = str(provider_pair or "").strip()
    quote_mint = str(quote_mint or "").strip()
    quote_unit = str(quote_unit or "").strip()
    if not all((mint, source, provider_pair, quote_mint, quote_unit)):
        raise ValueError(
            "mint, source, provider_pair, quote_mint, and quote_unit are required"
        )

    if isinstance(timestamp, bool):
        raise ValueError("timestamp must be a non-negative integer")
    try:
        ts = int(timestamp)
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamp must be a non-negative integer") from exc
    if ts < 0:
        raise ValueError("timestamp must be a non-negative integer")

    if isinstance(price_usd, bool):
        raise ValueError("price_usd must be a positive finite number")
    try:
        price = float(price_usd)
    except (TypeError, ValueError) as exc:
        raise ValueError("price_usd must be a positive finite number") from exc
    if not math.isfinite(price) or price <= 0:
        raise ValueError("price_usd must be a positive finite number")

    imported = int(time.time()) if imported_at is None else int(imported_at)
    if imported < 0:
        raise ValueError("imported_at must be non-negative")

    payload = evidence if isinstance(evidence, dict) else {}
    evidence_json = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    db = open_db()
    cursor = db.execute(
        """
        INSERT OR IGNORE INTO verified_price_observations (
            mint,
            symbol,
            ts,
            price_usd,
            source,
            provider_pair,
            quote_mint,
            quote_unit,
            evidence_json,
            imported_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mint,
            symbol,
            ts,
            price,
            source,
            provider_pair,
            quote_mint,
            quote_unit,
            evidence_json,
            imported,
        ),
    )
    inserted = cursor.rowcount > 0
    db.commit()
    db.close()
    return inserted


def verified_price_observations(mint, *, start_ts=None, end_ts=None):
    """Return verified provider-price rows with provenance intact."""

    clauses = ["mint = ?"]
    params = [mint]
    if start_ts is not None:
        clauses.append("ts >= ?")
        params.append(int(start_ts))
    if end_ts is not None:
        clauses.append("ts <= ?")
        params.append(int(end_ts))

    db = open_db()
    rows = db.execute(
        f"""
        SELECT
            ts,
            price_usd,
            source,
            provider_pair,
            quote_mint,
            quote_unit,
            evidence_json,
            imported_at
        FROM verified_price_observations
        WHERE {" AND ".join(clauses)}
        ORDER BY ts ASC, id ASC
        """,
        tuple(params),
    ).fetchall()
    db.close()

    result = []
    for (
        ts,
        price_usd,
        source,
        provider_pair,
        quote_mint,
        quote_unit,
        evidence_json,
        imported_at,
    ) in rows:
        try:
            evidence = json.loads(evidence_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            evidence = {}
        result.append({
            "timestamp": int(ts),
            "value": float(price_usd),
            "source": source,
            "provider_pair": provider_pair,
            "quote_mint": quote_mint,
            "quote_unit": quote_unit,
            "evidence": evidence if isinstance(evidence, dict) else {},
            "imported_at": int(imported_at),
        })
    return result


def verified_price_import_summary(mint):
    """Return bounded provenance/coverage metadata for imported price rows."""

    rows = verified_price_observations(mint)
    if not rows:
        return {
            "available": False,
            "observation_count": 0,
            "first_observed_at": None,
            "last_observed_at": None,
            "last_imported_at": None,
            "sources": [],
            "provider_pairs": [],
            "quote_mints": [],
        }

    return {
        "available": True,
        "observation_count": len(rows),
        "first_observed_at": rows[0]["timestamp"],
        "last_observed_at": rows[-1]["timestamp"],
        "last_imported_at": max(row["imported_at"] for row in rows),
        "sources": sorted({row["source"] for row in rows}),
        "provider_pairs": sorted({row["provider_pair"] for row in rows}),
        "quote_mints": sorted({row["quote_mint"] for row in rows}),
    }


def earliest_snapshot_time(mint):
    db = open_db()

    row = db.execute(
        """
        SELECT MIN(ts)
        FROM snapshots
        WHERE mint = ?
        """,
        (mint,),
    ).fetchone()

    db.close()

    if not row or row[0] is None:
        return None

    return int(row[0])


def historical_value(mint, metric, period_seconds):
    column = METRIC_COLUMNS.get(metric)

    if not column or not period_seconds:
        return None

    target = int(time.time()) - period_seconds
    point = historical_value_at(
        mint,
        metric,
        target,
        tolerance_seconds=6 * 3600,
    )
    if not isinstance(point, dict):
        return None
    return {
        "timestamp": point["timestamp"],
        "value": point["value"],
    }


def latest_snapshot_time(mint):
    db = open_db()

    row = db.execute(
        """
        SELECT MAX(ts)
        FROM snapshots
        WHERE mint = ?
        """,
        (mint,),
    ).fetchone()

    db.close()

    if not row or row[0] is None:
        return None

    return int(row[0])


def record_snapshot_if_due(
    *,
    mint,
    symbol,
    price=None,
    liquidity=None,
    volume24=None,
    holders=None,
    total_supply=None,
    pool_count=None,
    transactions24=None,
    timestamp=None,
    min_interval_seconds=300,
):
    """Persist a verified observation without creating high-frequency duplicates."""

    if not mint:
        return False

    observed_at = int(time.time()) if timestamp is None else int(timestamp)
    latest = latest_snapshot_time(mint)
    if (
        latest is not None
        and min_interval_seconds is not None
        and int(min_interval_seconds) > 0
        and observed_at - latest < int(min_interval_seconds)
    ):
        return False

    record_snapshot(
        mint=mint,
        symbol=symbol,
        price=price,
        liquidity=liquidity,
        volume24=volume24,
        holders=holders,
        total_supply=total_supply,
        pool_count=pool_count,
        transactions24=transactions24,
        timestamp=observed_at,
    )
    return True


def historical_series(mint, metric, *, start_ts=None, end_ts=None):
    """Return every locally stored verified observation for one metric.

    For price this merges current CMIS snapshot prices with explicitly verified
    provider-price backfill rows. Provider provenance remains stored in the
    dedicated table and is available through verified_price_observations.
    """

    column = METRIC_COLUMNS.get(metric)
    if not column:
        return []

    clauses = ["mint = ?", f"{column} IS NOT NULL"]
    params = [mint]

    if start_ts is not None:
        clauses.append("ts >= ?")
        params.append(int(start_ts))
    if end_ts is not None:
        clauses.append("ts <= ?")
        params.append(int(end_ts))

    db = open_db()
    rows = db.execute(
        f"""
        SELECT ts, {column}
        FROM snapshots
        WHERE {" AND ".join(clauses)}
        ORDER BY ts ASC, id ASC
        """,
        tuple(params),
    ).fetchall()
    db.close()

    merged = {}
    if metric == "price":
        for item in verified_price_observations(
            mint,
            start_ts=start_ts,
            end_ts=end_ts,
        ):
            merged[int(item["timestamp"])] = float(item["value"])

    for ts, value in rows:
        if value is not None:
            merged[int(ts)] = float(value)

    return [
        {"timestamp": ts, "value": merged[ts]}
        for ts in sorted(merged)
    ]


def historical_value_at(mint, metric, target_timestamp, *, tolerance_seconds=21600):
    """Return the closest verified observation to an explicit target time."""

    if metric not in METRIC_COLUMNS or target_timestamp is None:
        return None

    target = int(target_timestamp)
    tolerance = max(0, int(tolerance_seconds))
    rows = historical_series(mint, metric)
    if not rows:
        return None

    row = min(
        rows,
        key=lambda item: (
            abs(int(item["timestamp"]) - target),
            int(item["timestamp"]),
        ),
    )
    distance = abs(int(row["timestamp"]) - target)
    if distance > tolerance:
        return None

    return {
        "timestamp": int(row["timestamp"]),
        "value": float(row["value"]),
        "target_timestamp": target,
        "distance_seconds": distance,
    }


def percent_change(old_value, new_value):
    old_value = float(old_value)
    new_value = float(new_value)

    if old_value == 0:
        return None

    return ((new_value - old_value) / old_value) * 100.0


def threshold_result(change_pct, direction, threshold):
    if change_pct is None or threshold is None:
        return None

    threshold = abs(float(threshold))

    if direction == "down":
        return change_pct <= -threshold

    if direction == "up":
        return change_pct >= threshold

    return abs(change_pct) >= threshold


def format_number(metric, value):
    if metric in ("liquidity", "volume"):
        return f"${value:,.2f}"

    if metric == "price":
        if abs(value) < 0.01:
            return f"${value:.10f}".rstrip("0").rstrip(".")
        return f"${value:,.6f}".rstrip("0").rstrip(".")

    if metric in ("holders", "supply"):
        return f"{value:,.0f}"

    return f"{value:,.4f}"


def history_not_ready_message(symbol, metric, period, mint):
    earliest = earliest_snapshot_time(mint)

    metric_name = {
        "price": "price",
        "liquidity": "liquidity",
        "volume": "volume",
        "holders": "holder",
        "supply": "supply",
        "burns": "burn",
    }.get(metric, metric)

    if earliest:
        started = datetime.fromtimestamp(
            earliest
        ).strftime("%Y-%m-%d %H:%M")

        return (
            f"Liquidity Scout reply: {symbol} • "
            f"Historical {metric_name} comparison cannot yet be verified "
            f"for {period or 'the requested period'}. "
            f"Historical snapshots began {started}."
        )

    return (
        f"Liquidity Scout reply: {symbol} • "
        f"Historical {metric_name} comparison cannot yet be verified "
        f"for {period or 'the requested period'}. "
        "No historical snapshots have been collected yet."
    )
