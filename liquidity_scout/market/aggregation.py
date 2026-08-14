"""Deterministic asset-wide XDEX pool aggregation."""

from typing import Any, Dict, Iterable, List


def _s(value) -> str:
    return str(value or "").strip()


def _n(value, default=0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def get_num(obj: Dict[str, Any], *keys: str) -> float:
    for key in keys:
        if key in obj and obj.get(key) is not None:
            return _n(obj.get(key))
    return 0.0


def pool_id(pool: Dict[str, Any]) -> str:
    return (
        _s(pool.get("address"))
        or _s(pool.get("poolAddress"))
        or _s(pool.get("id"))
        or repr(pool)
    )


def token_identity(token: Dict[str, Any]):
    symbol = _s(token.get("symbol")).upper()
    name = _s(token.get("name"))
    mint = _s(token.get("mint") or token.get("address"))
    return symbol, name, mint


def aggregate_assets(pools: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate pool rows into one record per mint using v0.12 semantics."""
    assets = {}

    for pool in pools:
        pid = pool_id(pool)

        for side in ("baseToken", "quoteToken"):
            token = pool.get(side) or {}
            symbol, name, mint = token_identity(token)

            if not symbol or not mint:
                continue

            asset = assets.setdefault(
                mint,
                {
                    "symbol": symbol,
                    "name": name,
                    "mint": mint,
                    "pools": {},
                },
            )
            asset["pools"][pid] = pool

    results = []

    for asset in assets.values():
        token_pools = list(asset["pools"].values())
        if not token_pools:
            continue

        primary = max(token_pools, key=lambda pool: get_num(pool, "liquidity"))

        results.append(
            {
                "symbol": asset["symbol"],
                "name": asset["name"],
                "mint": asset["mint"],
                "pool_count": len(token_pools),
                "volume24": sum(get_num(pool, "volume24h") for pool in token_pools),
                "volume1h": sum(get_num(pool, "volume1h") for pool in token_pools),
                "liquidity": sum(get_num(pool, "liquidity") for pool in token_pools),
                "txns1h": sum(
                    get_num(pool, "txns1h", "transactions1h")
                    for pool in token_pools
                ),
                "txns24h": sum(
                    get_num(pool, "txns24h", "transactions24h")
                    for pool in token_pools
                ),
                "holders": max(
                    (get_num(pool, "holders") for pool in token_pools),
                    default=0.0,
                ),
                "price": get_num(primary, "priceUsd"),
                "change24": get_num(primary, "priceChange24h"),
                "change1h": get_num(primary, "priceChange1h"),
                "safety_score": get_num(primary, "safetyScore"),
                "safety_grade": _s(primary.get("safetyGrade")),
                "primary_pool_id": pool_id(primary),
            }
        )

    return results
