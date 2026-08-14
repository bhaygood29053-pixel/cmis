"""Deterministic asset-wide XDEX pool aggregation."""

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _s(value) -> str:
    return str(value or "").strip()


def _n(value, default=0.0) -> float:
    """Legacy numeric helper kept for compatibility callers."""
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def get_num(obj: Dict[str, Any], *keys: str) -> float:
    """Legacy missing-to-zero lookup kept for compatibility callers."""
    for key in keys:
        if key in obj and obj.get(key) is not None:
            return _n(obj.get(key))
    return 0.0


def get_optional_num(obj: Dict[str, Any], *keys: str) -> Optional[float]:
    """Return the first valid numeric value, preserving missing as ``None``."""
    for key in keys:
        if key not in obj or obj.get(key) is None:
            continue
        try:
            return float(obj.get(key))
        except (TypeError, ValueError):
            continue
    return None


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


def _sum_metric(
    pools: Sequence[Dict[str, Any]],
    *keys: str,
) -> Tuple[Optional[float], bool]:
    values: List[float] = []
    complete = True

    for pool in pools:
        value = get_optional_num(pool, *keys)
        if value is None:
            complete = False
            continue
        values.append(value)

    if not values:
        return None, False

    return sum(values), complete


def _holder_summary(
    pools: Sequence[Dict[str, Any]],
) -> Tuple[Optional[int], List[int], bool]:
    observations: List[int] = []
    complete = True

    for pool in pools:
        value = get_optional_num(pool, "holders")
        if value is None:
            complete = False
            continue
        observations.append(int(value))

    observed = sorted(set(observations))
    if complete and len(observed) == 1:
        return observed[0], observed, True

    return None, observed, False


def _primary_pool(
    pools: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Choose the deepest observed pool without inventing missing liquidity."""
    with_liquidity = [
        (get_optional_num(pool, "liquidity"), pool)
        for pool in pools
    ]
    observed = [
        (value, pool)
        for value, pool in with_liquidity
        if value is not None
    ]

    if observed:
        return max(
            observed,
            key=lambda item: (item[0], pool_id(item[1])),
        )[1]

    return min(pools, key=pool_id)


def aggregate_assets(pools: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aggregate pool rows into one record per mint while preserving uncertainty.

    Asset-wide sums retain any observed lower-bound value but mark themselves
    incomplete when one or more relevant LP rows are missing or malformed.
    Holder counts are accepted only when every relevant LP reports the same
    asset-wide value; disagreement remains unverified instead of collapsing to
    ``max()``. Primary-pool metrics are exact only when the deepest pool can be
    identified from complete liquidity data (or there is only one LP).
    """
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

        liquidity, liquidity_complete = _sum_metric(token_pools, "liquidity")
        volume24, volume24_complete = _sum_metric(token_pools, "volume24h")
        volume1h, volume1h_complete = _sum_metric(token_pools, "volume1h")
        txns1h, txns1h_complete = _sum_metric(
            token_pools,
            "txns1h",
            "transactions1h",
        )
        txns24h, txns24h_complete = _sum_metric(
            token_pools,
            "txns24h",
            "transactions24h",
        )
        holders, holder_observations, holders_complete = _holder_summary(token_pools)

        primary = _primary_pool(token_pools)
        primary_pool_complete = len(token_pools) == 1 or liquidity_complete

        price = get_optional_num(primary, "priceUsd")
        change24 = get_optional_num(primary, "priceChange24h")
        change1h = get_optional_num(primary, "priceChange1h")
        safety_score = get_optional_num(primary, "safetyScore")

        results.append(
            {
                "symbol": asset["symbol"],
                "name": asset["name"],
                "mint": asset["mint"],
                "pool_count": len(token_pools),
                "volume24": volume24,
                "volume1h": volume1h,
                "liquidity": liquidity,
                "txns1h": txns1h,
                "txns24h": txns24h,
                "holders": holders,
                "holder_observations": holder_observations,
                "price": price,
                "change24": change24,
                "change1h": change1h,
                "safety_score": safety_score,
                "safety_grade": _s(primary.get("safetyGrade")),
                "primary_pool_id": pool_id(primary),
                "completeness": {
                    "volume24": volume24_complete,
                    "volume1h": volume1h_complete,
                    "liquidity": liquidity_complete,
                    "txns1h": txns1h_complete,
                    "txns24h": txns24h_complete,
                    "holders": holders_complete,
                    "primary_pool": primary_pool_complete,
                    "price": primary_pool_complete and price is not None,
                    "change24": primary_pool_complete and change24 is not None,
                    "change1h": primary_pool_complete and change1h is not None,
                    "safety": primary_pool_complete and safety_score is not None,
                },
            }
        )

    return results
