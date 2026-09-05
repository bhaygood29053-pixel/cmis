"""Deterministic XDEX network-gap registry beneath CMIS Web Discovery.

This registry answers whether currently known XDEX frontend/provider surfaces
require browser capture. It classifies URL/method identity only and never
fetches, replays, prepares, signs, or executes a request.

Known useful uncovered XDEX surfaces are direct machine-readable GET endpoints,
so the current decision is browser_capture_required_now=false.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .base import DISCOVERED


GAP_REGISTRY_CONTRACT = "xdex_network_gap_registry/v1"

COVERED_READ_ONLY = "covered_read_only"
READ_ONLY_GAP_CANDIDATE = "read_only_gap_candidate"
EXECUTION_ADJACENT_EXCLUDED = "execution_adjacent_excluded"
UI_ONLY_CANDIDATE = "ui_only_candidate"
UNKNOWN = "unknown"

_NEXT_STRUCTURED_CONTRACT = "xdex_extended_readonly_structured_discovery/v1"

_KNOWN_MACHINE_SURFACES: dict[tuple[str, str], dict[str, Any]] = {
    ("api.xdex.xyz", "/api/xendex/pool/list"): {
        "classification": COVERED_READ_ONLY,
        "transport_method": "GET",
        "surface_id": "pool_list",
        "direct_machine_access": True,
        "structured_discovery_covered": True,
        "semantic_state": "existing_cmis_provider_contract",
        "evidence_basis": [
            "liquidity_scout.providers.x1.xdex.POOL_LIST_URL",
            "xdex_structured_discovery/v1",
        ],
    },
    ("api.xdex.xyz", "/api/token-price/price"): {
        "classification": COVERED_READ_ONLY,
        "transport_method": "GET",
        "surface_id": "token_price",
        "direct_machine_access": True,
        "structured_discovery_covered": True,
        "semantic_state": "existing_cmis_provider_contract",
        "evidence_basis": [
            "liquidity_scout.providers.x1.xdex.TOKEN_PRICE_URL",
            "xdex_structured_discovery/v1",
        ],
    },
    ("api.xdex.xyz", "/api/xendex/chart/history"): {
        "classification": COVERED_READ_ONLY,
        "transport_method": "GET",
        "surface_id": "price_history",
        "direct_machine_access": True,
        "structured_discovery_covered": True,
        "semantic_state": "scoped_history_semantics",
        "evidence_basis": [
            "liquidity_scout.providers.x1.xdex.PRICE_HISTORY_URL",
            "docs/X1_EVIDENCE_CAPABILITY_BOUNDARY.md#xdex-history-semantics",
            "xdex_structured_discovery/v1",
        ],
    },
    ("api.xdex.xyz", "/api/xendex/swap/quote"): {
        "classification": COVERED_READ_ONLY,
        "transport_method": "GET",
        "surface_id": "swap_quote_research_route",
        "direct_machine_access": True,
        "structured_discovery_covered": True,
        "semantic_state": "scoped_quote_semantics",
        "evidence_basis": [
            "liquidity_scout.providers.x1.xdex.SWAP_QUOTE_URL",
            "docs/X1_EVIDENCE_CAPABILITY_BOUNDARY.md#xdex-quote-semantics",
            "xdex_structured_discovery/v1",
        ],
    },
    ("api.xdex.xyz", "/api/xdex/swap/quote"): {
        "classification": READ_ONLY_GAP_CANDIDATE,
        "transport_method": "GET",
        "surface_id": "swap_quote_frontend_alias",
        "direct_machine_access": True,
        "structured_discovery_covered": False,
        "semantic_state": "live_alias_equivalence_evidence_exists",
        "evidence_basis": [
            "tests/test_xdex_frontend_quote_route_live.py",
            "tests/test_xdex_frontend_quote_bundle_live.py",
        ],
        "recommended_next_contract": _NEXT_STRUCTURED_CONTRACT,
    },
    ("oracle.xdex.xyz", "/api/v1/token/price"): {
        "classification": READ_ONLY_GAP_CANDIDATE,
        "transport_method": "GET",
        "surface_id": "oracle_token_price",
        "direct_machine_access": True,
        "structured_discovery_covered": False,
        "semantic_state": "bounded_existing_evidence_not_web_discovery_covered",
        "evidence_basis": [
            ".github/workflows/xdex-oracle-price-evidence.yml",
            "docs/X1_EVIDENCE_CAPABILITY_BOUNDARY.md#xdex-oracle-role",
        ],
        "recommended_next_contract": _NEXT_STRUCTURED_CONTRACT,
    },
    ("oracle.xdex.xyz", "/api/v1/token/sell-quote"): {
        "classification": READ_ONLY_GAP_CANDIDATE,
        "transport_method": "GET",
        "surface_id": "oracle_sell_quote",
        "direct_machine_access": True,
        "structured_discovery_covered": False,
        "semantic_state": "verified_scoped_no_fee_cp_reference",
        "evidence_basis": [
            "tests/test_xdex_output_slippage_semantics_live.py",
            "docs/XDEX_OUTPUT_SLIPPAGE_RESEARCH.md",
            "docs/X1_EVIDENCE_CAPABILITY_BOUNDARY.md#xdex-oracle-role",
        ],
        "recommended_next_contract": _NEXT_STRUCTURED_CONTRACT,
    },
}

_EXECUTION_PATHS = frozenset(
    {
        ("api.xdex.xyz", "/api/xendex/swap/prepare"),
        ("api.xdex.xyz", "/api/xdex/swap/prepare"),
    }
)

_UI_HOSTS = frozenset({"app.xdex.xyz", "xdex.xyz"})


def _truth_state() -> dict[str, Any]:
    return {
        "discovery_state": DISCOVERED,
        "surface_identity_verified": False,
        "provider_response_verified": False,
        "semantic_verification_complete": False,
        "web_claim_verified": False,
        "cmis_verified": False,
        "source_independence_verified": False,
    }


def _base_result(
    *,
    url: str,
    method: str,
    host: str | None,
    path: str,
    classification: str,
    reason: str | None,
) -> dict[str, Any]:
    return {
        "contract": GAP_REGISTRY_CONTRACT,
        "url": url,
        "transport_method": method,
        "host": host,
        "path": path,
        "classification": classification,
        "reason": reason,
        "surface_id": None,
        "direct_machine_access": False,
        "structured_discovery_covered": False,
        "semantic_state": "unknown",
        "evidence_basis": [],
        "recommended_next_contract": None,
        "browser_capture_justified": False,
        "truth_state": _truth_state(),
        "read_only": classification
        in {COVERED_READ_ONLY, READ_ONLY_GAP_CANDIDATE, UI_ONLY_CANDIDATE},
        "request_replay_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


def classify_xdex_network_surface(
    url: str,
    *,
    method: str = "GET",
) -> dict[str, Any]:
    """Classify one XDEX URL/method identity without making a request."""

    text = str(url or "").strip()
    normalized_method = str(method or "").strip().upper()
    parsed = urlparse(text)

    if normalized_method not in {"GET", "POST", "HEAD"}:
        return _base_result(
            url=text,
            method=normalized_method,
            host=(parsed.hostname or "").casefold() or None,
            path=parsed.path or "/",
            classification=UNKNOWN,
            reason="unsupported_transport_method",
        )

    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        return _base_result(
            url=text,
            method=normalized_method,
            host=(parsed.hostname or "").casefold() or None,
            path=parsed.path or "/",
            classification=UNKNOWN,
            reason="invalid_or_non_https_url",
        )

    host = parsed.hostname.casefold()
    path = parsed.path or "/"

    if (host, path) in _EXECUTION_PATHS:
        result = _base_result(
            url=text,
            method=normalized_method,
            host=host,
            path=path,
            classification=EXECUTION_ADJACENT_EXCLUDED,
            reason="swap_prepare_is_execution_adjacent_and_outside_read_only_discovery",
        )
        result.update(
            {
                "surface_id": "swap_prepare",
                "direct_machine_access": True,
                "semantic_state": "explicitly_excluded",
                "evidence_basis": [
                    "tests/test_xdex_frontend_quote_bundle_live.py",
                    "docs/XDEX_OUTPUT_SLIPPAGE_RESEARCH.md#minimum-received--prepare-boundary",
                ],
                "read_only": False,
            }
        )
        return result

    known = _KNOWN_MACHINE_SURFACES.get((host, path))
    if known is not None:
        expected_method = str(known["transport_method"])
        if normalized_method != expected_method:
            result = _base_result(
                url=text,
                method=normalized_method,
                host=host,
                path=path,
                classification=UNKNOWN,
                reason="known_surface_wrong_transport_method",
            )
            result["surface_id"] = known["surface_id"]
            return result

        result = _base_result(
            url=text,
            method=normalized_method,
            host=host,
            path=path,
            classification=str(known["classification"]),
            reason=None,
        )
        result.update({key: value for key, value in known.items()})
        result["browser_capture_justified"] = False
        return result

    if host in _UI_HOSTS:
        result = _base_result(
            url=text,
            method=normalized_method,
            host=host,
            path=path,
            classification=UI_ONLY_CANDIDATE,
            reason="ui_route_presence_is_not_machine_readable_evidence",
        )
        result.update(
            {
                "surface_id": "xdex_ui_route",
                "direct_machine_access": False,
                "semantic_state": "ui_route_only",
                "evidence_basis": [
                    "tests/test_xdex_frontend_quote_bundle_live.py",
                ],
                "browser_capture_justified": False,
            }
        )
        return result

    return _base_result(
        url=text,
        method=normalized_method,
        host=host,
        path=path,
        classification=UNKNOWN,
        reason="unknown_xdex_surface",
    )


def xdex_network_gap_report() -> dict[str, Any]:
    """Return the deterministic current XDEX Web Discovery gap decision."""

    known_records = []
    for (host, path), record in _KNOWN_MACHINE_SURFACES.items():
        known_records.append(
            classify_xdex_network_surface(
                f"https://{host}{path}",
                method=str(record["transport_method"]),
            )
        )

    for host, path in sorted(_EXECUTION_PATHS):
        known_records.append(
            classify_xdex_network_surface(
                f"https://{host}{path}",
                method="POST",
            )
        )

    counts = {
        COVERED_READ_ONLY: 0,
        READ_ONLY_GAP_CANDIDATE: 0,
        EXECUTION_ADJACENT_EXCLUDED: 0,
        UI_ONLY_CANDIDATE: 0,
        UNKNOWN: 0,
    }
    for row in known_records:
        counts[row["classification"]] += 1

    read_only_gaps = [
        row
        for row in known_records
        if row["classification"] == READ_ONLY_GAP_CANDIDATE
    ]
    direct_gaps_only = bool(read_only_gaps) and all(
        row["direct_machine_access"] is True for row in read_only_gaps
    )

    return {
        "contract": GAP_REGISTRY_CONTRACT,
        "known_surface_count": len(known_records),
        "classification_counts": counts,
        "known_surfaces": known_records,
        "read_only_gap_count": len(read_only_gaps),
        "read_only_gap_surface_ids": [row["surface_id"] for row in read_only_gaps],
        "all_known_read_only_gaps_direct_machine_access": direct_gaps_only,
        "browser_capture_required_now": False,
        "browser_capture_decision_basis": (
            "Known uncovered useful XDEX surfaces are direct machine-readable "
            "GET endpoints. Extend structured discovery before considering a browser."
        ),
        "recommended_next_contract": _NEXT_STRUCTURED_CONTRACT,
        "execution_adjacent_paths_excluded": sorted(
            f"https://{host}{path}" for host, path in _EXECUTION_PATHS
        ),
        "read_only": True,
        "request_replay_authorized": False,
        "background_monitoring_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "COVERED_READ_ONLY",
    "EXECUTION_ADJACENT_EXCLUDED",
    "GAP_REGISTRY_CONTRACT",
    "READ_ONLY_GAP_CANDIDATE",
    "UI_ONLY_CANDIDATE",
    "UNKNOWN",
    "classify_xdex_network_surface",
    "xdex_network_gap_report",
]
