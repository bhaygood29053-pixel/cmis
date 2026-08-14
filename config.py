import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    agent_wallet: str = os.getenv("AGENT_WALLET", "").strip()
    api_key: str = os.getenv("X1_NINJA_API_KEY", "").strip()
    x1_rpc_url: str = os.getenv(
        "X1_RPC_URL",
        "https://rpc.mainnet.x1.xyz"
    ).strip()


SETTINGS = Settings()
