"""X1.Ninja/XDEX market-data provider transport.

This module owns X1-specific X1.Ninja/XDEX catalog collection beneath CMIS.
It contains transport/cache behavior only; deterministic resolution,
aggregation, ranking, and CMIS response construction remain in shared layers.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from config import SETTINGS

POOLS_URL = "https://api.x1.ninja/v1/pools"
PAGE_SIZE = 100
DEFAULT_REFRESH_SECONDS = 50
MAX_CATALOG_OFFSET = 10_000
MARKET_SOURCE = "X1.Ninja/XDEX"
CHAIN = "x1"


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
    """Fetch the full XDEX pool catalog using the established v0.12 semantics."""
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
    """Cached, read-only X1.Ninja/XDEX pool catalog owned by the X1 provider."""

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
        return self

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


class X1Provider:
    """First explicit X1 provider boundary for CMIS market collection.

    The provider owns source-specific catalog collection only. It does not
    resolve assets, aggregate LPs, rank assets, calculate risk, or build CMIS
    service envelopes.
    """

    chain = CHAIN
    market_source = MARKET_SOURCE

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        refresh_seconds: int = DEFAULT_REFRESH_SECONDS,
        session=requests,
        catalog: Optional[XDEXCatalog] = None,
    ):
        self.catalog = catalog or XDEXCatalog(
            api_key,
            refresh_seconds=refresh_seconds,
            session=session,
        )

    @property
    def pools(self) -> List[Dict[str, Any]]:
        return self.catalog.pools

    @property
    def xnt_price_usd(self):
        return self.catalog.xnt_price_usd

    @property
    def last_refresh(self):
        return self.catalog.last_refresh

    def refresh(self):
        self.catalog.refresh()
        return self

    def refresh_if_needed(self):
        self.catalog.refresh_if_needed()
        return self

    def market_catalog(self) -> Dict[str, Any]:
        """Return the currently collected X1 market facts without calculation."""
        return {
            "chain": self.chain,
            "source": self.market_source,
            "pools": list(self.pools),
            "xnt_price_usd": self.xnt_price_usd,
            "observed_at": self.last_refresh or None,
        }

    def status_text(self) -> str:
        return self.catalog.status_text()


__all__ = [
    "CHAIN",
    "DEFAULT_REFRESH_SECONDS",
    "MARKET_SOURCE",
    "MAX_CATALOG_OFFSET",
    "PAGE_SIZE",
    "POOLS_URL",
    "X1Provider",
    "XDEXCatalog",
    "fetch_all_pools",
]
