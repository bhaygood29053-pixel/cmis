"""CMIS contract wrapper for the deterministic market_report core.

The wrapper performs no provider/network collection. It accepts resolver matches
and a current catalog that have already been obtained by the X1 integration,
preserves the existing asset-wide aggregation logic, and translates the result
into the shared chain-aware CMIS service envelope.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Dict, Optional

from liquidity_scout.market.resolver import asset_key

from .cmis_contract import AMBIGUOUS, ERROR, OK, PARTIAL, UNAVAILABLE, build_service_envelope
from .cmis_market_freshness import evaluate_market_observation_freshness
from .market_report import build_market_report


_REQUIRED_COMPLETENESS_KEYS = (
    "price",
    "liquidity",
    "volume_24h",
    "transactions_24h",
)
_OPTIONAL_COMPLETENESS_KEYS = ("holders",)
_COMPLETENESS_KEYS = _REQUIRED_COMPLETENESS_KEYS + _OPTIONAL_COMPLETENESS_KEYS


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _match_asset_keys(matches: Sequence[Any]) -> list:
    keys = set()
    for match in matches:
        if not isinstance(match, (tuple, list)) or len(match) < 4:
            continue
        pool, side, asset, _quality = match[:4]
        selected = asset if isinstance(asset, Mapping) else None
        if selected is None and side == "pool" and isinstance(pool, Mapping):
            selected = pool.get("baseToken")
        key = asset_key(selected) if isinstance(selected, dict) else None
        if key:
            keys.add(key)
    return sorted(keys)


def _confidence(report: Mapping[str, Any]) -> Dict[str, Any]:
    completeness = report.get("completeness")
    completeness = completeness if isinstance(completeness, Mapping) else {}
    checks = {
        f"{key}_complete": completeness.get(key) is True
        for key in _COMPLETENESS_KEYS
    }
    verified = sum(1 for value in checks.values() if value)
    total = len(checks)
    required_checks = {
        f"{key}_complete": completeness.get(key) is True
        for key in _REQUIRED_COMPLETENESS_KEYS
    }
    required_verified = sum(1 for value in required_checks.values() if value)
    required_total = len(required_checks)
    return {
        "complete": verified == total,
        "all_fields_complete": verified == total,
        "core_market_complete": required_verified == required_total,
        "verified_checks": verified,
        "total_checks": total,
        "verification_ratio": round(verified / total, 6),
        "required_verified_checks": required_verified,
        "required_total_checks": required_total,
        "checks": checks,
    }


def _warnings(report: Mapping[str, Any]) -> list:
    completeness = report.get("completeness")
    completeness = completeness if isinstance(completeness, Mapping) else {}
    warnings = []
    for key in _COMPLETENESS_KEYS:
        if completeness.get(key) is not True:
            if key == "holders":
                message = (
                    "Provider holder-looking values are preserved as unverified observations; "
                    "counted-entity, asset-binding, uniqueness, coverage, and beneficial-owner "
                    "semantics are not verified."
                )
            else:
                message = (
                    f"Market report {key.replace('_', ' ')} is missing, malformed, "
                    "conflicting, or only partially covered."
                )
            warnings.append({
                "code": f"{key}_incomplete",
                "message": message,
            })

    if report.get("market_cap_usd_reported") is not None and report.get("market_cap_verified") is not True:
        warnings.append({
            "code": "market_cap_reported_unverified",
            "message": "Reported market cap is preserved as unverified provider data.",
        })
    if report.get("fdv_usd_reported") is not None and report.get("fdv_verified") is not True:
        warnings.append({
            "code": "fdv_reported_unverified",
            "message": "Reported FDV is preserved as unverified provider data.",
        })
    return warnings


def _sources(report: Mapping[str, Any]) -> list:
    provenance = report.get("provenance")
    if not isinstance(provenance, Mapping):
        return []
    source = _text(provenance.get("source"))
    if not source:
        return []
    record = {"source": source, "role": "market_report"}
    observed_at = provenance.get("catalog_last_refresh_unix")
    if observed_at is not None:
        record["observed_at"] = observed_at
    return [record]


def build_market_report_response(
    term: str,
    matches: Optional[Sequence[Any]],
    catalog: Any,
    *,
    chain: str = "x1",
    observed_at: Any = None,
) -> Dict[str, Any]:
    """Return ``market_report`` through the shared CMIS response contract.

    ``matches`` must be resolver matches for one intended asset. Empty matches
    are ``unavailable``. Distinct resolved asset identities are ``ambiguous``.
    Complete core market coverage is ``ok``; incomplete coverage is ``partial``.
    Reported-but-unverified provider fields remain warnings and never become
    verified facts merely because the service completed successfully.
    """
    query = _text(term)
    if not query:
        return build_service_envelope(
            "market_report",
            chain,
            ERROR,
            errors=[{
                "code": "asset_query_required",
                "message": "An asset symbol, name, mint, or pool identifier is required.",
            }],
            observed_at=observed_at,
        )

    if matches is None or (isinstance(matches, Sequence) and not isinstance(matches, (str, bytes)) and len(matches) == 0):
        return build_service_envelope(
            "market_report",
            chain,
            UNAVAILABLE,
            data={"query": query},
            warnings=[{
                "code": "asset_not_resolved",
                "message": "No verified market matches were supplied for the requested asset.",
            }],
            observed_at=observed_at,
        )

    if not isinstance(matches, Sequence) or isinstance(matches, (str, bytes)):
        return build_service_envelope(
            "market_report",
            chain,
            ERROR,
            data={"query": query},
            errors=[{
                "code": "invalid_market_matches",
                "message": "matches must be a resolver-match sequence or None.",
            }],
            observed_at=observed_at,
        )

    identities = _match_asset_keys(matches)
    if len(identities) > 1:
        return build_service_envelope(
            "market_report",
            chain,
            AMBIGUOUS,
            data={"query": query, "candidate_asset_keys": identities},
            warnings=[{
                "code": "asset_ambiguous",
                "message": "Resolver matches contain multiple asset identities; use a unique mint or identifier.",
            }],
            observed_at=observed_at,
        )

    try:
        report = build_market_report(query, matches, catalog)
    except (AttributeError, TypeError, ValueError, IndexError, KeyError) as exc:
        return build_service_envelope(
            "market_report",
            chain,
            ERROR,
            data={"query": query},
            errors=[{
                "code": "market_report_validation_error",
                "message": str(exc),
            }],
            observed_at=observed_at,
        )

    confidence = _confidence(report)
    provenance = report.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    effective_observed_at = (
        observed_at
        if observed_at is not None
        else provenance.get("catalog_last_refresh_unix")
    )

    report = dict(report)
    report["freshness"] = evaluate_market_observation_freshness(
        effective_observed_at
    )

    return build_service_envelope(
        "market_report",
        chain,
        OK if confidence["complete"] else PARTIAL,
        asset={
            "symbol": report.get("symbol"),
            "name": report.get("name"),
            "mint": report.get("mint"),
        },
        data=report,
        risk=None,
        confidence=confidence,
        sources=_sources(report),
        observed_at=effective_observed_at,
        freshness=report.get("freshness"),
        warnings=_warnings(report),
        errors=[],
    )


__all__ = ["build_market_report_response"]
