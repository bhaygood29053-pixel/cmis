import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _f(name, default):
    return float(os.getenv(name, str(default)))

def _i(name, default):
    return int(os.getenv(name, str(default)))

@dataclass(frozen=True)
class Settings:
    agent_wallet: str = os.getenv("AGENT_WALLET", "").strip()
    pool_address: str = os.getenv(
        "POOL_ADDRESS", "4sn8oCQWPikDxBkyRdd1S6bJ24oYjGF16aR7ZqCSXy4v"
    ).strip()
    api_key: str = os.getenv("X1_NINJA_API_KEY", "").strip()
    rpc_url: str = os.getenv("X1_RPC_URL", "https://rpc.mainnet.x1.xyz").strip()
    base_token_vault: str = os.getenv(
        "BASE_TOKEN_VAULT", "ELG1JmpJETYxZCwFBesCrpJDukfrMmND3gKtVnsKtMgi"
    ).strip()
    quote_token_vault: str = os.getenv(
        "QUOTE_TOKEN_VAULT", "FSxoLLMasBzDnqPDU7VzKXDmfp34cKJxXQsoXQEvwECf"
    ).strip()
    timeframe: str = os.getenv("TIMEFRAME", "5m").strip()
    candle_limit: int = _i("CANDLE_LIMIT", 60)
    poll_seconds: int = _i("POLL_SECONDS", 60)

    quote_symbol: str = os.getenv("QUOTE_SYMBOL", "XNT").strip()
    base_symbol: str = os.getenv("BASE_SYMBOL", "AGI").strip()
    starting_quote_balance: float = _f("STARTING_QUOTE_BALANCE", 10000)
    trade_allocation_pct: float = _f("TRADE_ALLOCATION_PCT", 0.10)

    fast_sma: int = _i("FAST_SMA", 5)
    slow_sma: int = _i("SLOW_SMA", 20)
    momentum_lookback: int = _i("MOMENTUM_LOOKBACK", 6)
    buy_score: int = _i("BUY_SCORE", 3)
    sell_score: int = _i("SELL_SCORE", -2)
    volume_spike_ratio: float = _f("VOLUME_SPIKE_RATIO", 1.50)

    min_liquidity_usd: float = _f("MIN_LIQUIDITY_USD", 50000)
    stop_loss_pct: float = _f("STOP_LOSS_PCT", 0.05)
    take_profit_pct: float = _f("TAKE_PROFIT_PCT", 0.10)
    max_position_pct: float = _f("MAX_POSITION_PCT", 0.25)

    hxmp_queue_enabled: bool = os.getenv("HXMP_QUEUE_ENABLED", "true").lower() == "true"

SETTINGS = Settings()
