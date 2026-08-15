"""CMIS contract wrapper for deterministic asset resolution.

The wrapper reuses the existing catalog resolver and exposes one unique asset
identity through the shared chain-aware CMIS envelope. It performs no provider
or network collection and never guesses between duplicate human-facing
identifiers or between the two assets in a pool-address lookup.
"""

from collections.abc import Iterable, Mapping
from typing import Any, Dict, Optional

from liquidity_scout.market.resolver import (
    AmbiguousAssetError,
    asset_key,
    find_matches_for_term,
    pool_address,
    resolve_asset,
)

from .cmis_contract import AMBIGUOUS, ERROR, OK, UNAVAILABLE, build_service_envelope


def _text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _token_identity(token: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(token, Mapping):
        return None
    symbol = _text(token.get("symbol"))
    name = _text(token.get("name"))
    mint = _text(token.get("mint") or token.get("address"))
    key = asset_key(dict(token))
    if not key:
        return None
    return {
        "symbol": symbol,
        "name": name,
        "mint": mint,
        "identity_key": key,
    }


def _candidate_assets(matches: Iterable[Any]) -> list:
    by_key = {}
    for match in matches:
        if not isinstance(match, (tuple, list)) or len(match) < 4:
            continue
        pool, side, asset, _quality = match[:4]
        tokens = []
        if side == "pool" and isinstance(pool, Mapping):
            tokens.extend([pool.get("baseToken"), pool.get("quoteToken")])
        else:
            tokens.append(asset)

        for token in tokens:
            identity = _token_identity(token)
            if identity is not None:
                by_key[identity["identity_key"]] = identity
    return [by_key[key] for key in sorted(by_key)]


def _resolved_by(term: str, token: Mapping[str, Any]) -> str:
    query = term.lower()
    mint = _text(token.get("mint") or token.get("address"))
    symbol = _text(token.get("symbol"))
    name = _text(token.get("name"))
    if mint and query == mint.lower():
        return "mint"
    if symbol and query == symbol.lower():
        return "symbol"
    if name and query == name.lower():
        return "name"
    return "exact_identifier"


def _unique_pool_count(matches: Iterable[Any]) -> int:
    identities = set()
    fallback = 0
    for match in matches:
        if not isinstance(match, (tuple, list)) or len(match) < 1:
            continue
        pool = match[0]
        if not isinstance(pool, Mapping):
            continue
        address = pool_address(dict(pool))
        if address:
            identities.add(address)
        else:
            fallback += 1
    return len(identities) + fallback


def _confidence(unique_mint_resolved: bool) -> Dict[str, Any]:
    return {
        "complete": bool(unique_mint_resolved),
        "verified_checks": 1 if unique_mint_resolved else 0,
        "total_checks": 1,
        "verification_ratio": 1.0 if unique_mint_resolved else 0.0,
        "checks": {"unique_mint_resolved": bool(unique_mint_resolved)},
    }


def _sources(source: Any, observed_at: Any) -> list:
    source_name = _text(source)
    if not source_name:
        return []
    record = {"source": source_name, "role": "asset_lookup"}
    if observed_at is not None:
        record["observed_at"] = observed_at
    return [record]


def build_asset_lookup_response(
    query: Any,
    pools: Any,
    *,
    chain: str = "x1",
    source: Any = None,
    observed_at: Any = None,
) -> Dict[str, Any]:
    """Resolve one unique catalog asset through the shared CMIS contract.

    ``ok`` requires an exact resolver match with one unique mint/address.
    Duplicate exact identifiers and pool-address lookups containing two assets
    are ``ambiguous``. Missing matches or identities that lack a mint are
    ``unavailable``. Malformed input is returned as ``error``.
    """
    query_text = _text(query)
    if not query_text:
        return build_service_envelope(
            "asset_lookup",
            chain,
            ERROR,
            errors=[{
                "code": "asset_query_required",
                "message": "An asset symbol, name, mint, or unique identifier is required.",
            }],
            observed_at=observed_at,
        )

    if pools is None:
        return build_service_envelope(
            "asset_lookup",
            chain,
            UNAVAILABLE,
            data={"query": query_text},
            sources=_sources(source, observed_at),
            observed_at=observed_at,
            warnings=[{
                "code": "asset_catalog_unavailable",
                "message": "No provider asset catalog was supplied for resolution.",
            }],
        )

    if isinstance(pools, (str, bytes, Mapping)) or not isinstance(pools, Iterable):
        return build_service_envelope(
            "asset_lookup",
            chain,
            ERROR,
            data={"query": query_text},
            observed_at=observed_at,
            errors=[{
                "code": "invalid_asset_catalog",
                "message": "pools must be an iterable collection of provider pool records.",
            }],
        )

    pool_rows = list(pools)
    try:
        term, matches = resolve_asset(query_text, pool_rows)
    except AmbiguousAssetError as exc:
        exact_matches = [
            match
            for match in find_matches_for_term(exc.term, pool_rows)
            if isinstance(match, (tuple, list)) and len(match) >= 4 and match[3] >= 90
        ]
        candidates = _candidate_assets(exact_matches)
        return build_service_envelope(
            "asset_lookup",
            chain,
            AMBIGUOUS,
            data={
                "query": query_text,
                "resolved_term": exc.term or None,
                "candidate_asset_keys": list(exc.asset_keys),
                "candidate_assets": candidates,
            },
            confidence=_confidence(False),
            sources=_sources(source, observed_at),
            observed_at=observed_at,
            warnings=[{
                "code": "asset_ambiguous",
                "message": str(exc),
            }],
        )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        return build_service_envelope(
            "asset_lookup",
            chain,
            ERROR,
            data={"query": query_text},
            observed_at=observed_at,
            errors=[{
                "code": "asset_lookup_validation_error",
                "message": str(exc),
            }],
        )

    if not term or not matches:
        return build_service_envelope(
            "asset_lookup",
            chain,
            UNAVAILABLE,
            data={"query": query_text},
            confidence=_confidence(False),
            sources=_sources(source, observed_at),
            observed_at=observed_at,
            warnings=[{
                "code": "asset_not_resolved",
                "message": "No exact provider-catalog asset match was found.",
            }],
        )

    candidates = _candidate_assets(matches)
    if len(candidates) > 1:
        return build_service_envelope(
            "asset_lookup",
            chain,
            AMBIGUOUS,
            data={
                "query": query_text,
                "resolved_term": term,
                "candidate_asset_keys": [item["identity_key"] for item in candidates],
                "candidate_assets": candidates,
            },
            confidence=_confidence(False),
            sources=_sources(source, observed_at),
            observed_at=observed_at,
            warnings=[{
                "code": "asset_ambiguous",
                "message": "The resolved identifier maps to multiple asset identities.",
            }],
        )

    if not candidates:
        return build_service_envelope(
            "asset_lookup",
            chain,
            UNAVAILABLE,
            data={"query": query_text, "resolved_term": term},
            confidence=_confidence(False),
            sources=_sources(source, observed_at),
            observed_at=observed_at,
            warnings=[{
                "code": "asset_identity_unavailable",
                "message": "The resolver matched catalog data but no asset identity was available.",
            }],
        )

    identity = candidates[0]
    if not identity.get("mint"):
        return build_service_envelope(
            "asset_lookup",
            chain,
            UNAVAILABLE,
            asset={
                "symbol": identity.get("symbol"),
                "name": identity.get("name"),
                "mint": None,
            },
            data={
                "query": query_text,
                "resolved_term": term,
                "identity_key": identity.get("identity_key"),
            },
            confidence=_confidence(False),
            sources=_sources(source, observed_at),
            observed_at=observed_at,
            warnings=[{
                "code": "asset_mint_unavailable",
                "message": "A catalog asset matched, but its mint/address is unavailable.",
            }],
        )

    primary = matches[0]
    selected_token = primary[2] if len(primary) >= 3 else None
    resolved_by = (
        _resolved_by(term, selected_token)
        if isinstance(selected_token, Mapping)
        else "exact_identifier"
    )
    match_quality = max(
        int(match[3])
        for match in matches
        if isinstance(match, (tuple, list)) and len(match) >= 4
    )

    return build_service_envelope(
        "asset_lookup",
        chain,
        OK,
        asset={
            "symbol": identity.get("symbol"),
            "name": identity.get("name"),
            "mint": identity.get("mint"),
        },
        data={
            "query": query_text,
            "resolved_term": term,
            "resolved_by": resolved_by,
            "match_quality": match_quality,
            "lp_count": _unique_pool_count(matches),
            "identity_key": identity.get("identity_key"),
        },
        confidence=_confidence(True),
        sources=_sources(source, observed_at),
        observed_at=observed_at,
        warnings=[],
        errors=[],
    )


__all__ = ["build_asset_lookup_response"]
