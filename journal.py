import csv
import json
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path(__file__).resolve().parent / "data"
STATE_PATH = DATA_DIR / "state.json"
TRADES_PATH = DATA_DIR / "trades.csv"
DECISIONS_PATH = DATA_DIR / "decisions.jsonl"
HXMP_QUEUE_PATH = DATA_DIR / "hxmp_queue.jsonl"

def _now():
    return datetime.now(timezone.utc).isoformat()

def load_portfolio(starting_balance):
    from models import Portfolio, Position
    DATA_DIR.mkdir(exist_ok=True)
    if not STATE_PATH.exists():
        return Portfolio(quote_balance=starting_balance)
    raw = json.loads(STATE_PATH.read_text())
    pos = raw.get("position")
    position = Position(**pos) if pos else None
    return Portfolio(
        quote_balance=float(raw["quote_balance"]),
        position=position,
        realized_pnl=float(raw.get("realized_pnl", 0)),
        trades=int(raw.get("trades", 0)),
        wins=int(raw.get("wins", 0)),
        losses=int(raw.get("losses", 0)),
    )

def save_portfolio(portfolio):
    DATA_DIR.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(portfolio.to_dict(), indent=2))

def log_decision(snapshot, signal, equity, action_taken):
    row = {
        "time": _now(),
        "pool": snapshot.pool_address,
        "pair": f"{snapshot.base_symbol}/{snapshot.quote_symbol}",
        "price": snapshot.price,
        "liquidity_usd": snapshot.liquidity_usd,
        "volume_24h": snapshot.volume_24h,
        "signal": signal.action,
        "score": signal.score,
        "confidence": signal.confidence,
        "reason": signal.reason,
        "equity": equity,
        "action_taken": action_taken,
    }
    with DECISIONS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row

def log_trade(trade):
    exists = TRADES_PATH.exists()
    fields = ["time", "side", "price", "quantity", "quote_amount", "realized_pnl", "reason"]
    row = {"time": _now(), **trade}
    with TRADES_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})
    return row

def queue_hxmp_event(event_type, payload):
    """Queue only non-secret trading metadata for later human review."""
    record = {
        "time": _now(),
        "event_type": event_type,
        "payload": payload,
        "status": "REVIEW_REQUIRED",
        "note": "v0.1 does not write this to X1 automatically.",
    }
    with HXMP_QUEUE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return record
