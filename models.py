from dataclasses import dataclass, asdict
from typing import Optional, List

@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

@dataclass
class MarketSnapshot:
    pool_address: str
    base_symbol: str
    quote_symbol: str
    price: float
    liquidity_usd: float
    volume_24h: float
    candles: List[Candle]

@dataclass
class Signal:
    action: str
    score: int
    confidence: float
    reason: str
    fast_sma: float
    slow_sma: float
    momentum: float
    volume_ratio: float

@dataclass
class Position:
    quantity: float
    entry_price: float
    entry_time: int

@dataclass
class Portfolio:
    quote_balance: float
    position: Optional[Position] = None
    realized_pnl: float = 0.0
    trades: int = 0
    wins: int = 0
    losses: int = 0

    def to_dict(self):
        d = asdict(self)
        return d
