"""Read-only CMIS composition for comparing verified direct XDEX candidates.

The composition deliberately reuses the accepted direct-route discovery,
exact-route collector, route resolver, and deterministic candidate comparator.
A candidate quote may participate only after the exact route + amount snapshot
passes the hardened CMIS resolver. Any candidate failure therefore makes the
comparison incomplete rather than disappearing from route selection.

This module does not prepare transactions, simulate execution, sign, broadcast,
move value, claim expected fill quality, or claim global route optimality.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from liquidity_scout.cmis.xdex_route_resolver import (
    SCHEMA_VERSION as ROUTE_EVIDENCE_SCHEMA_VERSION,
    SOURCE as ROUTE_EVIDENCE_SOURCE,
    resolve_xdex_route_evidence,
)
from liquidity_scout.providers.x1.xdex_direct_candidate_quote_comparison import (
    compare_direct_candidate_quotes,
)
from liquidity_scout.providers.x1.xdex_direct_route_discovery import discover_direct_route
from liquidity_scout.providers.x1.xdex_exact_route import collect_exact_route_snapshot
from liquidity_scout.services.pre_trade_route_evidence import normalize_token_in_amount


SERVICE = "cmis_xdex_verified_direct_candidate_comparison"
VERSION = "1.0"


class XDEXDirectCandidateComparisonError(RuntimeError):
    """Raised when a candidate cannot enter the trusted quote comparison."""


def _candidate_route(candidate: Mapping[str, Any], token_in: str, token_out: str) -> dict[str, str]:
    pool = candidate.get("pool")
    config = candidate.get("amm_config")
    if not isinstance(pool, str) or not pool.strip() or pool != pool.strip():
        raise XDEXDirectCandidateComparisonError("candidate pool identity is invalid")
    if not isinstance(config, str) or not config.strip() or config != config.strip():
        raise XDEXDirectCandidateComparisonError("candidate AMM config identity is invalid")
    return {
        "token_in_mint": token_in,
        "token_out_mint": token_out,
        "pool": pool,
        "amm_config": config,
    }


def compare_verified_direct_xdex_candidates(
    token_in_mint: str,
    token_out_mint: str,
    token_in_amount: Any,
    *,
    discovery_provider: Callable[[str, str], Mapping[str, Any]] = discover_direct_route,
    collector: Callable[..., Mapping[str, Any]] = collect_exact_route_snapshot,
    resolver: Callable[..., Mapping[str, Any]] = resolve_xdex_route_evidence,
    comparator: Callable[..., dict[str, Any]] = compare_direct_candidate_quotes,
) -> dict[str, Any]:
    """Compare every completely verified direct XDEX candidate read-only.

    The same exact route snapshot is supplied to the hardened route resolver and
    then used to expose quote output for comparison. Passing resolver validation
    proves the accepted route/amount/program/source/zero-slippage trust boundary;
    it does not turn the quote into an execution-quality or expected-fill claim.
    """
    try:
        normalized_amount = normalize_token_in_amount(token_in_amount)
    except ValueError as exc:
        raise XDEXDirectCandidateComparisonError(
            "token_in_amount must be a positive finite decimal"
        ) from exc
    if normalized_amount is None:
        raise XDEXDirectCandidateComparisonError("token_in_amount is required")

    discovery = discovery_provider(token_in_mint, token_out_mint)
    if not isinstance(discovery, Mapping):
        raise XDEXDirectCandidateComparisonError("direct-route discovery did not return a mapping")

    def quote_provider(
        candidate: Mapping[str, str],
        token_in: str,
        token_out: str,
        amount: str,
    ) -> Mapping[str, Any]:
        route = _candidate_route(candidate, token_in, token_out)
        snapshot = collector(route, amount)
        if not isinstance(snapshot, Mapping):
            raise XDEXDirectCandidateComparisonError("exact-route collector did not return a mapping")

        evidence = resolver(
            route,
            amount,
            collector=lambda _route, _amount: snapshot,
        )
        if not isinstance(evidence, Mapping):
            raise XDEXDirectCandidateComparisonError("route resolver did not return a mapping")
        if evidence.get("source") != ROUTE_EVIDENCE_SOURCE:
            raise XDEXDirectCandidateComparisonError("route evidence source is not accepted")
        if evidence.get("schema_version") != ROUTE_EVIDENCE_SCHEMA_VERSION:
            raise XDEXDirectCandidateComparisonError("route evidence schema is not accepted")
        if evidence.get("route") != route:
            raise XDEXDirectCandidateComparisonError("route evidence identity does not match candidate")
        if evidence.get("token_in_amount") != normalized_amount:
            raise XDEXDirectCandidateComparisonError("route evidence amount does not match request")
        if snapshot.get("quote_slippage_percent") != 0:
            raise XDEXDirectCandidateComparisonError("candidate quote is not the accepted zero-slippage quote")

        return {
            "token_in_mint": token_in,
            "token_out_mint": token_out,
            "pool": route["pool"],
            "amm_config": route["amm_config"],
            "route_identity_verified": True,
            "zero_slippage_output_verified": True,
            "zero_slippage_output": snapshot.get("quote_output_amount"),
            "output_decimals": snapshot.get("output_decimals"),
        }

    result = comparator(
        token_in_mint,
        token_out_mint,
        normalized_amount,
        discovery=discovery,
        quote_provider=quote_provider,
    )
    if not isinstance(result, dict):
        raise XDEXDirectCandidateComparisonError("candidate comparator did not return a dictionary")

    return {
        **result,
        "service": SERVICE,
        "version": VERSION,
        "discovery_status": discovery.get("status"),
        "candidate_quotes_passed_hardened_route_resolver": result.get("quoted_candidate_count")
        == result.get("candidate_count"),
        "runtime_integrated": False,
        "read_only": True,
        "execution_authorized": False,
    }


__all__ = [
    "SERVICE",
    "VERSION",
    "XDEXDirectCandidateComparisonError",
    "compare_verified_direct_xdex_candidates",
]
