"""CMIS contract wrapper for deterministic historical comparisons.

The wrapper preserves the existing structured historical comparison and exposes
it through the shared chain-aware CMIS envelope. Historical storage remains an
injected backend and this layer performs no live market collection.
"""

from collections.abc import Mapping
from typing import Any, Dict, Optional

from liquidity_scout.providers.x1.onchain_history_coverage import (
    build_rpc_visible_mint_history_coverage,
)

from .cmis_contract import ERROR, OK, PARTIAL, UNAVAILABLE, build_service_envelope
from .historical_compare import (
    build_all_available_history_profile,
    build_all_available_pair_comparison,
    build_historical_comparison,
)


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _confidence(comparison: Mapping[str, Any]) -> Dict[str, Any]:
    mode = _text(comparison.get("mode")) or "window"
    if mode == "all_available":
        checks = {
            "verified_history_available": comparison.get("available_metric_count", 0) > 0,
            "multi_point_history_available": comparison.get("multi_point_metric_count", 0) > 0,
            "full_asset_lifetime_verified": comparison.get("full_asset_lifetime_verified") is True,
        }
    elif mode == "all_available_pair":
        checks = {
            "primary_verified_history_available": (
                (comparison.get("primary_profile") or {}).get("available_metric_count", 0) > 0
                if isinstance(comparison.get("primary_profile"), Mapping)
                else False
            ),
            "secondary_verified_history_available": (
                (comparison.get("secondary_profile") or {}).get("available_metric_count", 0) > 0
                if isinstance(comparison.get("secondary_profile"), Mapping)
                else False
            ),
            "common_verified_history_comparable": comparison.get("comparable_metric_count", 0) > 0,
            "full_asset_lifetime_verified": comparison.get("full_asset_lifetime_verified") is True,
        }
    else:
        current_verified = comparison.get("current_verified") is True
        historical_verified = comparison.get("historical_verified") is True
        change_verified = (
            current_verified
            and historical_verified
            and comparison.get("change_pct") is not None
        )
        checks = {
            "current_metric_verified": current_verified,
            "historical_metric_verified": historical_verified,
            "change_verified": change_verified,
        }

    verified = sum(1 for value in checks.values() if value)
    total = len(checks)
    return {
        "complete": verified == total,
        "verified_checks": verified,
        "total_checks": total,
        "verification_ratio": round(verified / total, 6) if total else 0.0,
        "checks": checks,
    }


def _market_source(snapshot: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(snapshot, Mapping):
        return None
    report = snapshot.get("_market_report")
    if not isinstance(report, Mapping):
        return None
    provenance = report.get("provenance")
    if not isinstance(provenance, Mapping):
        return None
    source = _text(provenance.get("source"))
    if not source:
        return None
    record = {"source": source, "role": "historical_compare.current"}
    observed_at = provenance.get("catalog_last_refresh_unix")
    if observed_at is not None:
        record["observed_at"] = observed_at
    return record


def _sources(
    comparison: Mapping[str, Any],
    snapshot: Any,
    compare_snapshot: Any = None,
) -> list:
    result = []
    current_source = _market_source(snapshot)
    if current_source is not None:
        result.append(current_source)

    compare_source = _market_source(compare_snapshot)
    if compare_source is not None:
        compare_source["role"] = "historical_compare.compare_current"
        if compare_source not in result:
            result.append(compare_source)

    source = _text(comparison.get("source"))
    if source:
        mode = _text(comparison.get("mode")) or "window"
        role = (
            "historical_compare.baseline"
            if mode == "window"
            else f"historical_compare.{mode}"
        )
        record = {"source": source, "role": role}
        historical_observed_at = comparison.get("historical_observed_at")
        if historical_observed_at is not None:
            record["observed_at"] = historical_observed_at
        first = comparison.get("first_verified_observed_at")
        last = comparison.get("last_verified_observed_at")
        if first is not None:
            record["first_observed_at"] = first
        if last is not None:
            record["last_observed_at"] = last
        if record not in result:
            result.append(record)

    provider_price_history = comparison.get("provider_price_history")
    if isinstance(provider_price_history, Mapping):
        for raw_source in provider_price_history.get("sources") or []:
            provider_source = _text(raw_source)
            if not provider_source:
                continue
            record = {
                "source": provider_source,
                "role": "historical_compare.provider_price_backfill",
            }
            first = provider_price_history.get("first_observed_at")
            last = provider_price_history.get("last_observed_at")
            if first is not None:
                record["first_observed_at"] = first
            if last is not None:
                record["last_observed_at"] = last
            if record not in result:
                result.append(record)

    coverage = comparison.get("coverage")
    if isinstance(coverage, Mapping):
        onchain = coverage.get("onchain")
        if isinstance(onchain, Mapping):
            onchain_source = _text(onchain.get("source"))
            if onchain_source:
                record = {
                    "source": onchain_source,
                    "role": "historical_compare.onchain_coverage",
                    "coverage_scope": onchain.get("coverage_scope"),
                }
                if onchain.get("first_available_block") is not None:
                    record["first_available_block"] = onchain.get(
                        "first_available_block"
                    )
                if record not in result:
                    result.append(record)
    return result


def _warnings(comparison: Mapping[str, Any], confidence: Mapping[str, Any]) -> list:
    warnings = []
    reason = _text(comparison.get("reason"))
    if reason:
        warnings.append({"code": reason})

    mode = _text(comparison.get("mode")) or "window"
    checks = confidence.get("checks")
    checks = checks if isinstance(checks, Mapping) else {}

    if mode in {"all_available", "all_available_pair"}:
        limitations = comparison.get("limitations")
        if isinstance(limitations, list):
            for item in limitations:
                code = _text(item)
                if code:
                    warnings.append({"code": code})
        if comparison.get("full_asset_lifetime_verified") is not True:
            if comparison.get("full_supported_pair_lifetime_verified") is True:
                warnings.append({
                    "code": "historical_quote_usd_equivalence_unverified",
                    "message": (
                        "The exact supported market-pair price lifetime is verified, "
                        "but complete USD-denominated lifetime history remains "
                        "unverified until historical quote-to-USD equivalence is proven."
                    ),
                })
            else:
                warnings.append({
                    "code": "asset_lifetime_coverage_unverified",
                    "message": (
                        "All-available history is bounded to verified CMIS observations; "
                        "it is not proof of the asset's complete lifetime."
                    ),
                })

        coverage = comparison.get("coverage")
        if isinstance(coverage, Mapping):
            onchain = coverage.get("onchain")
            if isinstance(onchain, Mapping):
                onchain_reason = _text(onchain.get("reason"))
                if (
                    onchain.get("status") not in {"full", "not_requested"}
                    and onchain_reason
                    and not any(
                        item.get("code") == onchain_reason
                        for item in warnings
                    )
                ):
                    warnings.append({"code": onchain_reason})
                onchain_limitations = onchain.get("limitations")
                if isinstance(onchain_limitations, list):
                    for item in onchain_limitations:
                        code = _text(item)
                        if code and not any(
                            warning.get("code") == code
                            for warning in warnings
                        ):
                            warnings.append({"code": code})
        return warnings

    messages = {
        "current_metric_verified": "Current comparison value is not verified.",
        "historical_metric_verified": "Historical baseline value is not verified.",
        "change_verified": "Historical percentage change is not verified.",
    }
    for key, message in messages.items():
        if checks.get(key) is not True and not any(item.get("code") == key for item in warnings):
            warnings.append({"code": key, "message": message})
    return warnings



def _attach_x1_price_lifetime_coverage(
    comparison: Mapping[str, Any],
    price_lifetime_coverage: Any,
) -> Dict[str, Any]:
    """Attach an accepted quote-vs-USD price lifetime proof to one asset.

    The proof must bind to the exact comparison asset mint. Pair-lifetime
    promotion never upgrades legacy USD/full-asset lifetime flags unless the
    supplied proof separately verifies historical quote-to-USD equivalence.
    """

    result = dict(comparison)
    if not isinstance(price_lifetime_coverage, Mapping):
        return result

    candidate = dict(price_lifetime_coverage)
    asset = result.get("asset")
    asset_mint = _text(asset.get("mint")) if isinstance(asset, Mapping) else None
    base_mint = _text(candidate.get("base_mint"))
    quote_mint = _text(candidate.get("quote_mint"))

    asset_identity_bound = bool(
        asset_mint
        and base_mint
        and quote_mint
        and base_mint != quote_mint
        and asset_mint == base_mint
    )

    pair_lifetime_verified = bool(
        asset_identity_bound
        and candidate.get("full_supported_pair_lifetime_verified") is True
        and candidate.get("continuous_pair_price_coverage_verified") is True
        and candidate.get("provider_range_complete_verified") is True
    )
    historical_quote_usd_equivalence_verified = bool(
        pair_lifetime_verified
        and candidate.get("historical_quote_usd_equivalence_verified") is True
    )
    full_usd_lifetime_verified = bool(
        pair_lifetime_verified
        and historical_quote_usd_equivalence_verified
        and candidate.get("full_usd_lifetime_verified") is True
    )

    attached = dict(candidate)
    attached["asset_identity_bound"] = asset_identity_bound
    attached["full_supported_pair_lifetime_verified"] = pair_lifetime_verified
    attached["continuous_pair_price_coverage_verified"] = pair_lifetime_verified
    attached["provider_range_complete_verified"] = pair_lifetime_verified
    attached["historical_quote_usd_equivalence_verified"] = (
        historical_quote_usd_equivalence_verified
    )
    attached["full_usd_lifetime_verified"] = full_usd_lifetime_verified

    result["price_lifetime_coverage"] = attached
    result["asset_lifetime_start_verified"] = bool(
        result.get("asset_lifetime_start_verified") is True
        or pair_lifetime_verified
    )
    result["full_supported_pair_lifetime_verified"] = pair_lifetime_verified
    result["continuous_pair_price_coverage_verified"] = pair_lifetime_verified
    result["provider_range_complete_verified"] = pair_lifetime_verified
    result["historical_quote_usd_equivalence_verified"] = (
        historical_quote_usd_equivalence_verified
    )
    result["full_usd_lifetime_verified"] = full_usd_lifetime_verified

    if full_usd_lifetime_verified:
        result["full_asset_lifetime_verified"] = True
        result["continuous_coverage_verified"] = True

    return result


def _attach_x1_all_available_coverage(
    comparison: Mapping[str, Any],
    *,
    rpc_provider: Any,
    page_size: int,
    max_signatures: int,
) -> Dict[str, Any]:
    result = dict(comparison)
    asset = result.get("asset")
    mint = _text(asset.get("mint")) if isinstance(asset, Mapping) else None

    market_coverage = {
        "status": _text(result.get("status")) or "unavailable",
        "coverage_scope": result.get("coverage_scope"),
        "first_verified_observed_at": result.get("first_verified_observed_at"),
        "last_verified_observed_at": result.get("last_verified_observed_at"),
        "coverage_seconds": result.get("coverage_seconds"),
        "full_asset_lifetime_verified": (
            result.get("full_asset_lifetime_verified") is True
        ),
        "continuous_coverage_verified": (
            result.get("continuous_coverage_verified") is True
        ),
        "full_supported_pair_lifetime_verified": (
            result.get("full_supported_pair_lifetime_verified") is True
        ),
        "continuous_pair_price_coverage_verified": (
            result.get("continuous_pair_price_coverage_verified") is True
        ),
        "provider_range_complete_verified": (
            result.get("provider_range_complete_verified") is True
        ),
        "historical_quote_usd_equivalence_verified": (
            result.get("historical_quote_usd_equivalence_verified") is True
        ),
        "full_usd_lifetime_verified": (
            result.get("full_usd_lifetime_verified") is True
        ),
        "price_lifetime_coverage": (
            dict(result.get("price_lifetime_coverage"))
            if isinstance(result.get("price_lifetime_coverage"), Mapping)
            else None
        ),
        "provider_history_imported": (
            result.get("provider_history_imported") is True
        ),
        "provider_price_history": (
            dict(result.get("provider_price_history"))
            if isinstance(result.get("provider_price_history"), Mapping)
            else None
        ),
    }

    if rpc_provider is None:
        onchain_coverage = {
            "chain": "x1",
            "status": "not_requested",
            "reason": "onchain_coverage_not_requested",
            "coverage_scope": "x1_rpc_visible_mint_address_history",
            "subject_kind": "mint_address",
            "mint": mint,
            "source": None,
            "rpc_visible_mint_history_complete": False,
            "asset_wide_activity_verified": False,
            "asset_lifetime_start_verified": False,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
            "archival_completeness_verified": False,
            "limitations": [],
        }
    elif mint:
        onchain_coverage = build_rpc_visible_mint_history_coverage(
            mint,
            rpc_provider=rpc_provider,
            page_size=page_size,
            max_signatures=max_signatures,
        )
    else:
        onchain_coverage = {
            "chain": "x1",
            "status": "unavailable",
            "reason": "historical_asset_mint_unavailable",
            "coverage_scope": "x1_rpc_visible_mint_address_history",
            "subject_kind": "mint_address",
            "mint": None,
            "source": None,
            "rpc_visible_mint_history_complete": False,
            "asset_wide_activity_verified": False,
            "asset_lifetime_start_verified": False,
            "full_asset_lifetime_verified": False,
            "continuous_coverage_verified": False,
            "archival_completeness_verified": False,
            "limitations": [
                "mint_address_required_for_onchain_coverage",
                "mint_address_history_is_not_asset_wide_transfer_history",
            ],
        }

    result["coverage"] = {
        "market": market_coverage,
        "onchain": onchain_coverage,
    }
    return result


def _service_status(comparison: Mapping[str, Any]) -> str:
    status = _text(comparison.get("status"))
    if status == "ok":
        return OK
    if status == "partial":
        return PARTIAL
    if status == "unavailable":
        return UNAVAILABLE
    return ERROR


def build_historical_compare_response(
    question: str | None,
    snapshot: Any,
    *,
    history_backend: Any,
    get_total_supply=None,
    chain: str = "x1",
    observed_at: Any = None,
    mode: str = "window",
    compare_snapshot: Any = None,
    metrics: Any = None,
    gap_threshold_seconds: int = 129600,
    anchor_tolerance_seconds: int = 21600,
    onchain_coverage_provider: Any = None,
    price_lifetime_coverage: Any = None,
    onchain_page_size: int = 1000,
    onchain_max_signatures: int = 5000,
) -> Dict[str, Any]:
    """Return deterministic window or all-available history through CMIS."""

    normalized_mode = (_text(mode) or "window").lower()
    if normalized_mode not in {"window", "all_available", "all_available_pair"}:
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            errors=[{
                "code": "historical_mode_invalid",
                "message": (
                    "mode must be one of: window, all_available, all_available_pair"
                ),
            }],
            observed_at=observed_at,
        )

    query = _text(question)
    if normalized_mode == "window" and not query:
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            errors=[{
                "code": "historical_query_required",
                "message": "A historical comparison request is required.",
            }],
            observed_at=observed_at,
        )

    if not isinstance(snapshot, Mapping):
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            data={"query": query, "mode": normalized_mode},
            errors=[{
                "code": "invalid_market_snapshot",
                "message": "snapshot must be a mapping.",
            }],
            observed_at=observed_at,
        )

    if normalized_mode == "all_available_pair" and not isinstance(compare_snapshot, Mapping):
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            data={"query": query, "mode": normalized_mode},
            errors=[{
                "code": "compare_market_snapshot_required",
                "message": "all_available_pair requires a second verified market snapshot.",
            }],
            observed_at=observed_at,
        )

    try:
        if normalized_mode == "all_available":
            comparison = build_all_available_history_profile(
                dict(snapshot),
                history_backend=history_backend,
                get_total_supply=get_total_supply,
                metrics=metrics,
                gap_threshold_seconds=gap_threshold_seconds,
            )
        elif normalized_mode == "all_available_pair":
            comparison = build_all_available_pair_comparison(
                dict(snapshot),
                dict(compare_snapshot),
                history_backend=history_backend,
                get_total_supply=get_total_supply,
                metrics=metrics,
                gap_threshold_seconds=gap_threshold_seconds,
                anchor_tolerance_seconds=anchor_tolerance_seconds,
            )
        else:
            comparison = build_historical_comparison(
                query,
                dict(snapshot),
                history_backend=history_backend,
                get_total_supply=get_total_supply,
            )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            data={"query": query, "mode": normalized_mode},
            errors=[{
                "code": "historical_compare_validation_error",
                "message": str(exc),
            }],
            observed_at=observed_at,
        )

    if comparison is not None and normalized_mode == "all_available" and chain == "x1":
        try:
            comparison = _attach_x1_price_lifetime_coverage(
                comparison,
                price_lifetime_coverage,
            )
            comparison = _attach_x1_all_available_coverage(
                comparison,
                rpc_provider=onchain_coverage_provider,
                page_size=onchain_page_size,
                max_signatures=onchain_max_signatures,
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            comparison = dict(comparison)
            comparison["coverage"] = {
                "market": {
                    "status": _text(comparison.get("status")) or "unavailable",
                    "coverage_scope": comparison.get("coverage_scope"),
                    "first_verified_observed_at": comparison.get("first_verified_observed_at"),
                    "last_verified_observed_at": comparison.get("last_verified_observed_at"),
                    "full_asset_lifetime_verified": False,
                    "continuous_coverage_verified": False,
                },
                "onchain": {
                    "chain": "x1",
                    "status": "unavailable",
                    "reason": "x1_onchain_coverage_validation_error",
                    "details": str(exc),
                    "coverage_scope": "x1_rpc_visible_mint_address_history",
                    "source": "X1 RPC",
                    "rpc_visible_mint_history_complete": False,
                    "asset_wide_activity_verified": False,
                    "full_asset_lifetime_verified": False,
                    "archival_completeness_verified": False,
                },
            }

    if comparison is None:
        return build_service_envelope(
            "historical_compare",
            chain,
            ERROR,
            data={"query": query, "mode": normalized_mode},
            errors=[{
                "code": "historical_request_unrecognized",
                "message": "The historical backend did not recognize the comparison request.",
            }],
            observed_at=observed_at,
        )

    confidence = _confidence(comparison)
    status = _service_status(comparison)
    effective_observed_at = (
        observed_at
        if observed_at is not None
        else comparison.get("current_observed_at")
    )

    return build_service_envelope(
        "historical_compare",
        chain,
        status,
        asset=comparison.get("asset"),
        data=comparison,
        risk=None,
        confidence=confidence,
        sources=_sources(comparison, snapshot, compare_snapshot),
        observed_at=effective_observed_at,
        warnings=_warnings(comparison, confidence),
        errors=(
            [{"code": "historical_compare_invalid_status"}]
            if status == ERROR
            else []
        ),
    )


__all__ = ["build_historical_compare_response"]
