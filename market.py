import time
import requests
from models import Candle, MarketSnapshot

API_BASE = "https://api.x1.ninja"

def _num(obj, *keys, default=0.0):
    for key in keys:
        if isinstance(obj, dict) and key in obj and obj[key] is not None:
            try:
                return float(obj[key])
            except (TypeError, ValueError):
                pass
    return float(default)

def _symbol(pool, side, fallback):
    value = pool.get(side) or {}
    if isinstance(value, dict):
        return str(value.get("symbol") or fallback)
    return fallback

def _rpc_token_balance(rpc_url: str, token_account: str) -> float:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTokenAccountBalance",
        "params": [token_account, {"commitment": "confirmed"}],
    }
    r = requests.post(rpc_url, json=payload, timeout=15)
    r.raise_for_status()
    body = r.json()
    if body.get("error"):
        raise RuntimeError(f"X1 RPC error: {body['error']}")
    value = body["result"]["value"]
    # uiAmountString preserves the token decimal conversion.
    return float(value["uiAmountString"])

def quote_price_from_vaults(rpc_url: str, base_vault: str, quote_vault: str) -> float:
    """Return quote-token units per one base token (e.g. XNT per AGI)."""
    if not base_vault or not quote_vault:
        raise ValueError("BASE_TOKEN_VAULT and QUOTE_TOKEN_VAULT are required.")
    base_reserve = _rpc_token_balance(rpc_url, base_vault)
    quote_reserve = _rpc_token_balance(rpc_url, quote_vault)
    if base_reserve <= 0:
        raise RuntimeError("Base-token vault reserve is zero.")
    return quote_reserve / base_reserve

class X1NinjaClient:
    def __init__(self, api_key: str, rpc_url: str, base_vault: str, quote_vault: str):
        if not api_key:
            raise ValueError("X1_NINJA_API_KEY is required for live-data mode.")
        self.rpc_url = rpc_url
        self.base_vault = base_vault
        self.quote_vault = quote_vault
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_key}"})

    def _get(self, path, params=None):
        r = self.session.get(f"{API_BASE}{path}", params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def pool(self, address: str) -> dict:
        payload = self._get(f"/v1/pools/{address}")
        return payload.get("pool", payload)

    def candles(self, address: str, timeframe: str, limit: int):
        payload = self._get(
            f"/v1/ohlcv/{address}",
            params={"tf": timeframe, "limit": limit},
        )
        rows = payload.get("candles") or payload.get("ohlcv") or payload.get("data") or []
        out = []
        for row in rows:
            if isinstance(row, dict):
                ts = int(_num(row, "timestamp", "time", "ts", default=time.time()))
                out.append(Candle(
                    timestamp=ts,
                    open=_num(row, "open", "o"),
                    high=_num(row, "high", "h"),
                    low=_num(row, "low", "l"),
                    close=_num(row, "close", "c", "price"),
                    volume=_num(row, "volume", "v", "volumeUsd"),
                ))
            elif isinstance(row, (list, tuple)) and len(row) >= 6:
                out.append(Candle(
                    timestamp=int(row[0]),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                ))
        out.sort(key=lambda c: c.timestamp)
        if not out:
            raise RuntimeError("X1.Ninja returned no OHLCV candles for this pool.")
        return out

    def snapshot(self, address, timeframe, limit, base_fallback="AGI", quote_fallback="XNT"):
        pool = self.pool(address)
        candles = self.candles(address, timeframe, limit)

        # Signal calculations use the OHLCV series. Paper fills use the on-chain
        # reserve ratio, preventing a USD/XNT unit mix-up.
        execution_price = quote_price_from_vaults(
            self.rpc_url, self.base_vault, self.quote_vault
        )

        return MarketSnapshot(
            pool_address=address,
            base_symbol=_symbol(pool, "baseToken", base_fallback),
            quote_symbol=quote_fallback,
            price=execution_price,
            liquidity_usd=_num(pool, "liquidityUsd", "liquidityUSD", "liquidity", "tvlUsd"),
            volume_24h=_num(pool, "volume24h", "volume24hUsd", "volumeUsd24h", "volume"),
            candles=candles,
        )

class DemoMarket:
    """Deterministic local feed so v0.1 can be tested before an API key is added."""
    def __init__(self):
        self.tick = 0

    def snapshot(self, address, timeframe, limit, base_fallback="AGI", quote_fallback="XNT"):
        now = int(time.time())
        candles = []
        start = max(60, limit)
        for i in range(start):
            x = i + self.tick
            trend = 0.00100 + x * 0.0000020
            wave = ((x % 12) - 6) * 0.0000008
            close = max(0.000001, trend + wave)
            open_ = close * (0.997 if x % 2 else 1.002)
            high = max(open_, close) * 1.006
            low = min(open_, close) * 0.994
            volume = 1000 + (x % 7) * 100
            if x % 13 == 0:
                volume *= 2.4
            candles.append(Candle(now - (start-i)*300, open_, high, low, close, volume))
        self.tick += 1
        return MarketSnapshot(
            pool_address=address,
            base_symbol=base_fallback,
            quote_symbol=quote_fallback,
            price=candles[-1].close,
            liquidity_usd=125000.0,
            volume_24h=85000.0,
            candles=candles[-limit:],
        )
