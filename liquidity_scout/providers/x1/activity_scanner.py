"""Standalone X1 token mint/burn activity scanning and persistence.

This provider is intentionally separate from the live XDEX listener and from
ordinary X1 RPC tokenomics requests. Callers inject an X1 RPC callable while
this layer selects a bounded signature-history window, retrieves/caches
successful transactions, persists explicit mint/burn events, and delegates
pure deterministic event arithmetic to ``liquidity_scout.tokenomics.activity``.

Scanner coverage is always explicit. Exhausting history visible to the
configured RPC endpoint is not independent proof of complete chain-lifetime
token history.
"""

import sqlite3

from ...tokenomics.activity import extract_token_events, summarize_token_events


CHAIN = "x1"
ACTIVITY_SOURCE = "X1 RPC parsed token instructions"


def _text(value):
    if value is None:
        return ""
    return str(value).strip()


def _max_signatures(value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("max_signatures must be a non-negative integer or None.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "max_signatures must be a non-negative integer or None."
        ) from exc
    if parsed < 0:
        raise ValueError("max_signatures must be a non-negative integer or None.")
    return parsed


def _ensure_scan_metadata_columns(db):
    """Add coverage-scope columns to older standalone activity databases."""
    columns = {
        row[1]
        for row in db.execute("PRAGMA table_info(token_activity_scans)").fetchall()
    }
    additions = {
        "coverage_scope": "TEXT NOT NULL DEFAULT 'unknown'",
        "lifetime_coverage_verified": "INTEGER NOT NULL DEFAULT 0",
        "lifetime_coverage_reason": "TEXT",
    }
    for column, declaration in additions.items():
        if column not in columns:
            db.execute(
                f"ALTER TABLE token_activity_scans ADD COLUMN {column} {declaration}"
            )


def initialize_activity_db(db):
    """Create standalone activity tables on an existing SQLite connection."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_token_activity (
            mint TEXT NOT NULL,
            signature TEXT NOT NULL,
            block_time INTEGER,
            PRIMARY KEY (mint, signature)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS token_activity_events (
            mint TEXT NOT NULL,
            event_key TEXT NOT NULL,
            signature TEXT NOT NULL,
            kind TEXT NOT NULL,
            instruction_type TEXT NOT NULL,
            raw_amount TEXT NOT NULL,
            authority TEXT,
            account TEXT,
            block_time INTEGER,
            PRIMARY KEY (mint, event_key)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS token_activity_scans (
            scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mint TEXT NOT NULL,
            max_signatures INTEGER,
            history_entries_examined INTEGER NOT NULL,
            signatures_scanned INTEGER NOT NULL,
            transactions_retrieved INTEGER NOT NULL,
            rpc_errors INTEGER NOT NULL,
            selection_complete INTEGER NOT NULL,
            history_exhausted INTEGER NOT NULL,
            coverage_verified INTEGER NOT NULL,
            activity_verified INTEGER NOT NULL,
            newest_signature TEXT,
            oldest_signature TEXT,
            coverage_scope TEXT NOT NULL DEFAULT 'unknown',
            lifetime_coverage_verified INTEGER NOT NULL DEFAULT 0,
            lifetime_coverage_reason TEXT
        )
        """
    )
    _ensure_scan_metadata_columns(db)
    db.commit()
    return db


def open_activity_db(path):
    path = _text(path)
    if not path:
        raise ValueError("Activity database path is required.")
    db = sqlite3.connect(path)
    initialize_activity_db(db)
    return db


def _selection_scope(*, selection_complete, history_exhausted, max_signatures):
    if not selection_complete:
        return "incomplete"
    if max_signatures == 0:
        return "none"
    if history_exhausted:
        return "rpc_history_exhausted"
    return "bounded"


def collect_signature_window(rpc, mint, *, max_signatures=None):
    """Select successful signatures for one explicit address-history window."""
    mint = _text(mint)
    if not mint:
        raise ValueError("Token mint is required.")
    if not callable(rpc):
        raise ValueError("An RPC callable is required.")

    max_signatures = _max_signatures(max_signatures)
    if max_signatures == 0:
        return {
            "signatures": [],
            "history_entries_examined": 0,
            "selection_complete": True,
            "history_exhausted": False,
            "selection_rpc_errors": 0,
            "malformed_history_entries": 0,
            "max_signatures": 0,
            "newest_signature": None,
            "oldest_signature": None,
            "coverage_scope": "none",
        }

    selected = []
    seen = set()
    before = None
    examined = 0
    malformed = 0
    selection_rpc_errors = 0
    history_exhausted = False
    reached_bound = False

    while True:
        limit = 1000
        if max_signatures is not None:
            remaining = max_signatures - examined
            if remaining <= 0:
                reached_bound = True
                break
            limit = min(limit, remaining)

        options = {"limit": limit}
        if before:
            options["before"] = before

        try:
            batch = rpc("getSignaturesForAddress", [mint, options])
        except Exception:
            selection_rpc_errors += 1
            break

        if batch is None or not isinstance(batch, list):
            selection_rpc_errors += 1
            break
        if not batch:
            history_exhausted = True
            break

        examined += len(batch)

        for item in batch:
            if not isinstance(item, dict) or "err" not in item:
                malformed += 1
                continue
            signature = _text(item.get("signature"))
            if not signature:
                malformed += 1
                continue
            if item.get("err") is not None or signature in seen:
                continue
            seen.add(signature)
            selected.append(signature)

        if len(batch) < limit:
            history_exhausted = True
            break

        last = batch[-1]
        before = _text(last.get("signature")) if isinstance(last, dict) else ""
        if not before:
            malformed += 1
            break

        if max_signatures is not None and examined >= max_signatures:
            reached_bound = True
            break

    selection_complete = (
        selection_rpc_errors == 0
        and malformed == 0
        and (history_exhausted or reached_bound)
    )
    coverage_scope = _selection_scope(
        selection_complete=selection_complete,
        history_exhausted=history_exhausted,
        max_signatures=max_signatures,
    )

    return {
        "signatures": selected,
        "history_entries_examined": examined,
        "selection_complete": selection_complete,
        "history_exhausted": history_exhausted,
        "selection_rpc_errors": selection_rpc_errors,
        "malformed_history_entries": malformed,
        "max_signatures": max_signatures,
        "newest_signature": selected[0] if selected else None,
        "oldest_signature": selected[-1] if selected else None,
        "coverage_scope": coverage_scope,
    }


def _processed_signatures(db, mint, signatures):
    if not signatures:
        return set()
    found = set()
    for start in range(0, len(signatures), 500):
        chunk = signatures[start:start + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = db.execute(
            f"""
            SELECT signature
            FROM processed_token_activity
            WHERE mint = ? AND signature IN ({placeholders})
            """,
            [mint, *chunk],
        ).fetchall()
        found.update(row[0] for row in rows)
    return found


def _persist_transaction(db, mint, signature, tx, events):
    block_time = tx.get("blockTime") if isinstance(tx, dict) else None
    for event in events:
        location = _text(event.get("location"))
        if not location:
            continue
        event_key = f"{signature}:{location}"
        db.execute(
            """
            INSERT OR IGNORE INTO token_activity_events (
                mint, event_key, signature, kind, instruction_type,
                raw_amount, authority, account, block_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mint,
                event_key,
                signature,
                _text(event.get("kind")),
                _text(event.get("instruction_type")),
                _text(event.get("raw_amount")),
                _text(event.get("authority")),
                _text(event.get("account")),
                event.get("block_time"),
            ),
        )

    db.execute(
        """
        INSERT OR REPLACE INTO processed_token_activity (
            mint, signature, block_time
        ) VALUES (?, ?, ?)
        """,
        (mint, signature, block_time),
    )


def _load_window_events(db, mint, signatures):
    if not signatures:
        return []
    rows = []
    for start in range(0, len(signatures), 500):
        chunk = signatures[start:start + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows.extend(
            db.execute(
                f"""
                SELECT signature, kind, instruction_type, raw_amount,
                       authority, account, event_key, block_time
                FROM token_activity_events
                WHERE mint = ? AND signature IN ({placeholders})
                ORDER BY event_key
                """,
                [mint, *chunk],
            ).fetchall()
        )

    return [
        {
            "signature": row[0],
            "kind": row[1],
            "instruction_type": row[2],
            "raw_amount": row[3],
            "authority": row[4] or "",
            "account": row[5] or "",
            "event_key": row[6],
            "block_time": row[7],
        }
        for row in rows
    ]


def _lifetime_coverage_reason(report, coverage):
    if not report.get("coverage_verified"):
        return "selected_window_coverage_unverified"
    scope = coverage.get("coverage_scope")
    if scope == "bounded":
        return "bounded_signature_window"
    if scope == "rpc_history_exhausted":
        return "rpc_history_exhaustion_not_independent_lifetime_proof"
    if scope == "none":
        return "no_signature_history_examined"
    return "lifetime_history_not_independently_verified"


def _record_scan(db, mint, coverage, report):
    cursor = db.execute(
        """
        INSERT INTO token_activity_scans (
            mint, max_signatures, history_entries_examined,
            signatures_scanned, transactions_retrieved, rpc_errors,
            selection_complete, history_exhausted, coverage_verified,
            activity_verified, newest_signature, oldest_signature,
            coverage_scope, lifetime_coverage_verified,
            lifetime_coverage_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mint,
            coverage.get("max_signatures"),
            coverage["history_entries_examined"],
            coverage["signatures_scanned"],
            coverage["transactions_retrieved"],
            coverage["rpc_errors"],
            int(coverage["selection_complete"]),
            int(coverage["history_exhausted"]),
            int(report["coverage_verified"]),
            int(report["activity_verified"]),
            coverage.get("newest_signature"),
            coverage.get("oldest_signature"),
            coverage.get("coverage_scope"),
            int(report["lifetime_coverage_verified"]),
            report.get("lifetime_coverage_reason"),
        ),
    )
    db.commit()
    return cursor.lastrowid


def scan_token_activity(rpc, *, mint, decimals, db, max_signatures=None):
    """Scan one X1 token-activity window and return a verified report."""
    mint = _text(mint)
    if not mint:
        raise ValueError("Token mint is required.")
    if not callable(rpc):
        raise ValueError("An RPC callable is required.")
    initialize_activity_db(db)

    selection = collect_signature_window(
        rpc,
        mint,
        max_signatures=max_signatures,
    )
    signatures = selection["signatures"]
    cached = _processed_signatures(db, mint, signatures)

    retrieved = len(cached)
    transaction_errors = 0
    newly_retrieved = 0

    for signature in signatures:
        if signature in cached:
            continue
        try:
            tx = rpc(
                "getTransaction",
                [
                    signature,
                    {
                        "encoding": "jsonParsed",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            )
        except Exception:
            transaction_errors += 1
            continue

        meta = tx.get("meta") if isinstance(tx, dict) else None
        if (
            not isinstance(tx, dict)
            or not isinstance(meta, dict)
            or "err" not in meta
            or meta.get("err") is not None
        ):
            transaction_errors += 1
            continue

        events = extract_token_events(tx, mint)
        _persist_transaction(db, mint, signature, tx, events)
        retrieved += 1
        newly_retrieved += 1

    db.commit()

    rpc_errors = selection["selection_rpc_errors"] + transaction_errors
    coverage = {
        "signatures_scanned": len(signatures),
        "transactions_retrieved": retrieved,
        "rpc_errors": rpc_errors,
        "selection_complete": selection["selection_complete"],
        "history_exhausted": selection["history_exhausted"],
        "max_signatures": selection["max_signatures"],
        "history_entries_examined": selection["history_entries_examined"],
        "malformed_history_entries": selection["malformed_history_entries"],
        "selection_rpc_errors": selection["selection_rpc_errors"],
        "transaction_errors": transaction_errors,
        "cached_transactions": len(cached),
        "new_transactions_retrieved": newly_retrieved,
        "newest_signature": selection["newest_signature"],
        "oldest_signature": selection["oldest_signature"],
        "coverage_scope": selection["coverage_scope"],
    }

    events = _load_window_events(db, mint, signatures)
    report = summarize_token_events(
        events,
        mint=mint,
        decimals=decimals,
        coverage=coverage,
    )
    report["coverage_scope"] = coverage["coverage_scope"]
    report["lifetime_coverage_verified"] = False
    report["lifetime_coverage_reason"] = _lifetime_coverage_reason(report, coverage)
    report["coverage"]["coverage_scope"] = coverage["coverage_scope"]
    report["coverage"]["lifetime_coverage_verified"] = False
    report["coverage"]["lifetime_coverage_reason"] = report[
        "lifetime_coverage_reason"
    ]
    report["events"] = events
    report["scan_id"] = _record_scan(db, mint, coverage, report)
    report["storage"] = "standalone SQLite token activity DB"
    return report


class X1ActivityScanner:
    """Explicit provider facade for standalone X1 mint/burn activity scans."""

    chain = CHAIN
    source = ACTIVITY_SOURCE

    def __init__(self, rpc):
        if not callable(rpc):
            raise ValueError("An RPC callable is required.")
        self.rpc = rpc

    def collect_signature_window(self, mint, *, max_signatures=None):
        return collect_signature_window(
            self.rpc,
            mint,
            max_signatures=max_signatures,
        )

    def scan(self, *, mint, decimals, db, max_signatures=None):
        return scan_token_activity(
            self.rpc,
            mint=mint,
            decimals=decimals,
            db=db,
            max_signatures=max_signatures,
        )


__all__ = [
    "ACTIVITY_SOURCE",
    "CHAIN",
    "X1ActivityScanner",
    "collect_signature_window",
    "initialize_activity_db",
    "open_activity_db",
    "scan_token_activity",
]
