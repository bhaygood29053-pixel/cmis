"""Read-only X1.Ninja/XDEX catalog client.

This module extracts catalog transport from the MoltGrid listener so every
Liquidity Scout consumer can use the same deterministic pool catalog.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import SETTINGS

POOLS_URL = "https://api.x1.ninja/v1/pools"
PAGE_SIZE = 100
DEFAULT_REFRESH_SECONDS = 300
MAX_CATALOG_OFFSET = 10_000


def _number(value, default=0.0):
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def fetch_all_pools(
    api_key: Optional[str] = None,
    *,
    session=requests,
    page_size: int = PAGE_SIZE,
    timeout: int = 20,
    sleep_seconds: float = 0.03,
) -> Tuple[List[Dict[str, Any]], Any]:
    """Fetch the full XDEX pool catalog using the listener's v0.12 semantics."""
    api_key = (api_key if api_key is not None else SETTINGS.api_key).strip()
    if not api_key:
        raise RuntimeError("X1_NINJA_API_KEY is missing from .env")

    headers = {"Authorization": f"Bearer {api_key}"}
    pools: List[Dict[str, Any]] = []
    offset = 0
    total = None
    xnt_price_usd = None

    while True:
        response = session.get(
            POOLS_URL,
            params={"limit": page_size, "offset": offset},
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()

        page = body.get("pools", []) if isinstance(body, dict) else []
        if not isinstance(page, list):
            page = []

        if total is None and isinstance(body, dict):
            total = int(body.get("total") or body.get("totalCount") or 0)

        if xnt_price_usd is None and isinstance(body, dict):
            xnt_price_usd = body.get("xntPriceUsd")

        pools.extend(page)

        if not page:
            break

        offset += len(page)

        if total and offset >= total:
            break

        if offset > MAX_CATALOG_OFFSET:
            break

        if sleep_seconds:
            time.sleep(sleep_seconds)

    return pools, xnt_price_usd


class XDEXCatalog:
    """Cached, read-only view of the X1.Ninja/XDEX pool catalog."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        refresh_seconds: int = DEFAULT_REFRESH_SECONDS,
        session=requests,
    ):
        self.api_key = api_key
        self.refresh_seconds = int(refresh_seconds)
        self.session = session
        self.pools: List[Dict[str, Any]] = []
        self.xnt_price_usd = None
        self.last_refresh = 0.0

    def refresh_if_needed(self):
        age = time.time() - self.last_refresh
        if not self.pools or age >= self.refresh_seconds:
            self.refresh()

    def refresh(self):
        pools, xnt_price_usd = fetch_all_pools(
            self.api_key,
            session=self.session,
        )
        self.pools = pools
        self.xnt_price_usd = xnt_price_usd
        self.last_refresh = time.time()
        return self

    def status_text(self) -> str:
        text = f"[catalog] Loaded {len(self.pools)} XDEX pools"
        if self.xnt_price_usd is not None:
            text += f" | XNT ${_number(self.xnt_price_usd):,.6f}"
        return text
