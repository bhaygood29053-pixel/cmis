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

    db = open_db()

    row = db.execute(
        f"""
        SELECT ts, {column}
        FROM snapshots
        WHERE mint = ?
          AND {column} IS NOT NULL
        ORDER BY ABS(ts - ?) ASC
        LIMIT 1
        """,
        (mint, target),
    ).fetchone()

    db.close()

    if not row:
        return None

    ts, value = row

    # Historical point must be reasonably close to target.
    # 6-hour tolerance keeps 24h/7d/30d comparisons honest.
    if abs(int(ts) - target) > 6 * 3600:
        return None

    return {
        "timestamp": int(ts),
        "value": float(value),
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
    """Return every locally stored verified observation for one metric."""

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

    return [
        {"timestamp": int(ts), "value": float(value)}
        for ts, value in rows
        if value is not None
    ]


def historical_value_at(mint, metric, target_timestamp, *, tolerance_seconds=21600):
    """Return the closest stored observation to an explicit target time."""

    column = METRIC_COLUMNS.get(metric)
    if not column or target_timestamp is None:
        return None

    target = int(target_timestamp)
    tolerance = max(0, int(tolerance_seconds))

    db = open_db()
    row = db.execute(
        f"""
        SELECT ts, {column}
        FROM snapshots
        WHERE mint = ?
          AND {column} IS NOT NULL
        ORDER BY ABS(ts - ?) ASC, ts ASC
        LIMIT 1
        """,
        (mint, target),
    ).fetchone()
    db.close()

    if not row:
        return None

    ts, value = row
    if abs(int(ts) - target) > tolerance:
        return None

    return {
        "timestamp": int(ts),
        "value": float(value),
        "target_timestamp": target,
        "distance_seconds": abs(int(ts) - target),
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
