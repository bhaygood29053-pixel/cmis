"""CMIS contract wrapper for deterministic asset-wide rankings.

The wrapper reuses the existing ranking core, which aggregates pool rows into
asset-wide metrics and assigns exact ranks only when the requested metric is
complete. It performs no provider/network collection and never converts
incomplete observations into zeroes.
"""

from collections.abc import Iterable, Mapping
from typing import Any, Dict, Optional

from .cmis_contract import ERROR, OK, PARTIAL, UNAVAILABLE, build_service_envelope
from .market_rankings import rank_assets, ranking_value


SUPPORTED_RANK_METRICS = (
    "volume",
    "liquidity",
    "holders",
    "safety",
    "gainers",
    "losers",
    "trending",
)


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _positive_int(value: Any, *, default: int = 10) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _sources(source: Any, observed_at: Any) -> list:
    source_name = _text(source)
    if not source_name:
        return []
    record = {"source": source_name, "role": "rank"}
    if observed_at is not None:
        record["observed_at"] = observed_at
    return [record]


def _ranked_row(asset: Mapping[str, Any], metric: str, meta: Mapping[str, Any]) -> Dict[str, Any]:
    use_txns = meta.get("trending_basis") == "1h transactions"
    pool_count = asset.get("pool_count")
    return {
        "rank": asset.get("rank"),
        "symbol": asset.get("symbol"),
        "name": asset.get("name"),
        "mint": asset.get("mint"),
        "metric": metric,
        "value": ranking_value(asset, metric, use_txns),
        "liquidity_usd": asset.get("liquidity"),
        "liquidity_complete": bool((asset.get("completeness") or {}).get("liquidity")),
        "lp_count": pool_count,
        "#LPs": pool_count,
    }


def _confidence(
    *,
    ranked_count: int,
    incomplete_count: int,
    verified_excluded_count: int,
    total_candidates: int,
) -> Dict[str, Any]:
    complete_universe = total_candidates > 0 and incomplete_count == 0
    verified = ranked_count + verified_excluded_count
    return {
        "complete": complete_universe,
        "verified_checks": verified,
        "total_checks": total_candidates,
        "verification_ratio": (
            round(verified / total_candidates, 6)
            if total_candidates > 0
            else 0.0
        ),
        "checks": {
            "ranking_universe_complete": complete_universe,
        },
    }


def build_rank_response(
    pools: Any,
    *,
    metric: str = "volume",
    limit: Any = 10,
    chain: str = "x1",
    source: Any = None,
    observed_at: Any = None,
) -> Dict[str, Any]:
    """Return an asset-wide ranking through the shared CMIS contract.

    ``ok`` means every candidate asset had a complete requested metric and at
    least one asset was rankable. ``partial`` means an exact ranking exists for
    a verified subset while one or more assets were excluded for incomplete
    requested metrics. ``unavailable`` means no exact ranking could be
    produced. Unsupported metrics or malformed input are ``error``.
    """
    metric_text = _text(metric)
    if metric_text is None:
        return build_service_envelope(
            "rank",
            chain,
            ERROR,
            errors=[{
                "code": "ranking_metric_required",
                "message": "A supported ranking metric is required.",
            }],
            observed_at=observed_at,
        )
    metric_text = metric_text.lower()
    if metric_text not in SUPPORTED_RANK_METRICS:
        return build_service_envelope(
            "rank",
            chain,
            ERROR,
            data={"metric": metric_text},
            errors=[{
                "code": "unsupported_ranking_metric",
                "message": f"Unsupported ranking metric: {metric_text}",
            }],
            observed_at=observed_at,
        )

    parsed_limit = _positive_int(limit)
    if parsed_limit is None:
        return build_service_envelope(
            "rank",
            chain,
            ERROR,
            data={"metric": metric_text},
            errors=[{
                "code": "invalid_ranking_limit",
                "message": "limit must be a positive integer.",
            }],
            observed_at=observed_at,
        )

    if pools is None:
        return build_service_envelope(
            "rank",
            chain,
            UNAVAILABLE,
            data={"metric": metric_text, "limit": parsed_limit, "rankings": []},
            sources=_sources(source, observed_at),
            observed_at=observed_at,
            warnings=[{
                "code": "ranking_catalog_unavailable",
                "message": "No provider pool catalog was supplied for ranking.",
            }],
        )

    if isinstance(pools, (str, bytes, Mapping)) or not isinstance(pools, Iterable):
        return build_service_envelope(
            "rank",
            chain,
            ERROR,
            data={"metric": metric_text, "limit": parsed_limit},
            errors=[{
                "code": "invalid_ranking_catalog",
                "message": "pools must be an iterable collection of provider pool records.",
            }],
            observed_at=observed_at,
        )

    pool_rows = list(pools)
    try:
        ranked, meta = rank_assets(pool_rows, metric=metric_text, limit=parsed_limit)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return build_service_envelope(
            "rank",
            chain,
            ERROR,
            data={"metric": metric_text, "limit": parsed_limit},
            errors=[{
                "code": "rank_validation_error",
                "message": str(exc),
            }],
            observed_at=observed_at,
        )

    ranked_count = int(meta.get("ranked_count") or 0)
    incomplete_count = int(meta.get("incomplete_count") or 0)
    zero_rows = meta.get("unranked_zero") or []
    zero_count = len(zero_rows) if isinstance(zero_rows, list) else 0
    total_candidates = ranked_count + incomplete_count + zero_count
    confidence = _confidence(
        ranked_count=ranked_count,
        incomplete_count=incomplete_count,
        verified_excluded_count=zero_count,
        total_candidates=total_candidates,
    )

    warnings = []
    if incomplete_count:
        warnings.append({
            "code": "ranking_metric_incomplete_for_some_assets",
            "message": (
                f"{incomplete_count} asset(s) were excluded because the requested "
                "ranking metric was incomplete."
            ),
        })
    if zero_count:
        warnings.append({
            "code": "ranking_verified_non_positive_assets_excluded",
            "message": (
                f"{zero_count} asset(s) with verified non-positive values were "
                "excluded by the ranking policy for this metric."
            ),
        })

    rows = [_ranked_row(asset, metric_text, meta) for asset in ranked]
    data = {
        "metric": metric_text,
        "limit": parsed_limit,
        "rankings": rows,
        "ranked_count": ranked_count,
        "returned_count": len(rows),
        "incomplete_count": incomplete_count,
        "excluded_non_positive_count": zero_count,
        "trending_basis": meta.get("trending_basis") if metric_text == "trending" else None,
        "unranked_incomplete": meta.get("unranked_incomplete") or [],
        "unranked_non_positive": zero_rows,
    }

    if ranked_count == 0:
        status = UNAVAILABLE
        if not warnings:
            warnings.append({
                "code": "ranking_no_rankable_assets",
                "message": "No assets had a complete rankable value for the requested metric.",
            })
    elif incomplete_count > 0:
        status = PARTIAL
    else:
        status = OK

    return build_service_envelope(
        "rank",
        chain,
        status,
        asset={},
        data=data,
        risk=None,
        confidence=confidence,
        sources=_sources(source, observed_at),
        observed_at=observed_at,
        warnings=warnings,
        errors=[],
    )


__all__ = ["SUPPORTED_RANK_METRICS", "build_rank_response"]
