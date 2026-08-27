"""Structured deterministic market-report construction.

This module turns resolver matches plus the current XDEX catalog into one
asset-level report. It keeps live facts deterministic, aggregates liquidity
and 24-hour activity across distinct LPs, and records completeness when pool
rows disagree or omit values.

Presentation belongs to integrations. In particular, this service does not
format currency strings or manufacture values for missing data.
"""

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from liquidity_scout.market.resolver import pair_name, pool_address

Match = Tuple[Dict[str, Any], str, Optional[Dict[str, Any]], int]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_number(obj: Dict[str, Any], keys: Sequence[str]) -> Optional[float]:
    for key in keys:
        if key not in obj or obj.get(key) is None:
            continue
        return _number(obj.get(key))
    return None


def _pool_identity(pool: Dict[str, Any]) -> str:
    address = pool_address(pool)
    if address:
        return f"address:{address}"
    return f"row:{repr(pool)}"


def _unique_pools(matches: Iterable[Match]) -> List[Dict[str, Any]]:
    pools: List[Dict[str, Any]] = []
    seen = set()

    for match in matches:
        pool = match[0]
        key = _pool_identity(pool)
        if key in seen:
            continue
        seen.add(key)
        pools.append(pool)

    return pools


def _sum_metric(
    pools: Sequence[Dict[str, Any]],
    *keys: str,
) -> Tuple[Optional[float], bool]:
    values: List[float] = []
    complete = True

    for pool in pools:
        value = _first_number(pool, keys)
        if value is None:
            complete = False
            continue
        values.append(value)

    if not values:
        return None, False

    return sum(values), complete


def _provider_holder_summary(
    pools: Sequence[Dict[str, Any]],
) -> Tuple[Optional[int], List[int], bool, bool]:
    """Preserve provider holder-looking values without verifying holder semantics.

    Agreement across XDEX pool rows proves only provider-row consistency. It
    does not prove what entity is counted, total coverage, uniqueness, wallet
    identity, or beneficial ownership.
    """
    values: List[int] = []
    rows_complete = True

    for pool in pools:
        value = _first_number(pool, ("holders",))
        if value is None:
            rows_complete = False
            continue
        values.append(int(value))

    observed = sorted(set(values))
    provider_consistent = len(observed) == 1 and rows_complete
    reported = observed[0] if provider_consistent else None
    return reported, observed, rows_complete, provider_consistent


def build_market_report(term: str, matches: Sequence[Match], catalog: Any) -> Dict[str, Any]:
    """Build one structured asset-wide report from resolver matches.

    Resolver ordering determines the primary/deepest pool used for price,
    price-change, safety, and other pool-specific fields. Liquidity, 24-hour
    volume, and 24-hour transactions are aggregated across distinct matched
    LPs. Missing or malformed pool values are omitted from the numeric sum and
    surfaced through the ``completeness`` flags instead of being treated as
    verified zeroes.
    """
    if not matches:
        raise ValueError("market report requires at least one resolved XDEX match")

    primary_pool, _side, selected_asset, _quality = matches[0]
    if not selected_asset:
        selected_asset = primary_pool.get("baseToken") or {}

    pools = _unique_pools(matches)
    term_text = _text(term)
    symbol = _text(selected_asset.get("symbol")) or term_text
    name = _text(selected_asset.get("name"))
    mint = _text(selected_asset.get("mint") or selected_asset.get("address"))

    liquidity, liquidity_complete = _sum_metric(pools, "liquidity")
    volume24, volume24_complete = _sum_metric(pools, "volume24h")
    txns24, txns24_complete = _sum_metric(
        pools,
        "txns24h",
        "transactions24h",
    )
    holders_reported, holder_observations, holder_rows_complete, holder_provider_consistent = (
        _provider_holder_summary(pools)
    )

    primary_price = _first_number(primary_pool, ("priceUsd",))
    xnt_reference = _number(getattr(catalog, "xnt_price_usd", None))
    is_xnt = symbol.upper() == "XNT" or term_text.upper() == "XNT"

    if is_xnt and xnt_reference is not None:
        price_usd = xnt_reference
        price_source = "x1_ninja_xnt_reference"
    else:
        price_usd = primary_price
        price_source = "primary_pool"

    last_refresh = _number(getattr(catalog, "last_refresh", None))
    if last_refresh is not None and last_refresh <= 0:
        last_refresh = None

    holder_observed_max = max(holder_observations) if holder_observations else None

    return {
        "symbol": symbol,
        "name": name or None,
        "mint": mint or None,
        "price_usd": price_usd,
        "price_source": price_source,
        "liquidity_usd": liquidity,
        "volume_24h_usd": volume24,
        "transactions_24h": int(txns24) if txns24 is not None else None,
        "holders": None,
        "holders_reported": holders_reported,
        "holders_observed": holder_observations,
        "holders_observed_max": holder_observed_max,
        "holder_semantics": {
            "source_field": "holders",
            "counted_entity": "unverified",
            "coverage": "unverified",
            "provider_rows_complete": holder_rows_complete,
            "provider_rows_consistent": holder_provider_consistent,
            "holder_semantics_verified": False,
            "asset_binding_verified": False,
            "uniqueness_semantics_verified": False,
            "beneficial_owner_identity_verified": False,
        },
        "price_change_1h_pct": _first_number(primary_pool, ("priceChange1h",)),
        "price_change_24h_pct": _first_number(primary_pool, ("priceChange24h",)),
        "market_cap_usd_reported": _first_number(primary_pool, ("marketCap",)),
        "market_cap_verified": False,
        "fdv_usd_reported": _first_number(primary_pool, ("fdv",)),
        "fdv_verified": False,
        "safety_grade": _text(primary_pool.get("safetyGrade")) or None,
        "safety_score": _first_number(primary_pool, ("safetyScore",)),
        "created_at": primary_pool.get("createdAt"),
        "lp_count": len(pools),
        "primary_pool": {
            "address": pool_address(primary_pool) or None,
            "pair": pair_name(primary_pool),
            "liquidity_usd": _first_number(primary_pool, ("liquidity",)),
            "price_usd": primary_price,
        },
        "completeness": {
            "liquidity": liquidity_complete,
            "volume_24h": volume24_complete,
            "transactions_24h": txns24_complete,
            "holders": False,
            "price": price_usd is not None,
        },
        "provenance": {
            "source": "X1.Ninja/XDEX",
            "catalog_last_refresh_unix": last_refresh,
        },
    }
