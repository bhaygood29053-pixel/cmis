"""Deterministic XDEX Web Discovery coverage reconciliation.

This module reconciles the repository-known XDEX surface inventory against the
accepted v5 and v7 structured-discovery contracts.

It proves only coverage of the known CMIS repository inventory. It does not
claim universal completeness of every XDEX endpoint deployed on the internet.
"""

from __future__ import annotations

from typing import Any

from .base import DISCOVERED
from .xdex_extended_structured import parse_xdex_extended_readonly_url
from .xdex_network_gaps import (
    EXECUTION_ADJACENT_EXCLUDED,
    UI_ONLY_CANDIDATE,
    classify_xdex_network_surface,
)
from .xdex_structured import parse_xdex_url


COVERAGE_RECONCILIATION_CONTRACT = "xdex_coverage_reconciliation/v1"

V5_CONTRACT = "xdex_structured_discovery/v1"
V7_CONTRACT = "xdex_extended_readonly_structured_discovery/v1"

KNOWN_DIRECT_READONLY_SURFACES = (
    {
        "surface_id": "pool_list",
        "url": "https://api.xdex.xyz/api/xendex/pool/list?network=mainnet",
        "coverage_contract": V5_CONTRACT,
    },
    {
        "surface_id": "token_price",
        "url": (
            "https://api.xdex.xyz/api/token-price/price"
            "?network=X1%20Mainnet"
            "&token_address=So11111111111111111111111111111111111111112"
        ),
        "coverage_contract": V5_CONTRACT,
    },
    {
        "surface_id": "price_history",
        "url": (
            "https://api.xdex.xyz/api/xendex/chart/history"
            "?network=X1%20Mainnet"
            "&from_token=So11111111111111111111111111111111111111112"
            "&to_token=B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
            "&time_from=1788400000"
            "&time_to=1788403600"
        ),
        "coverage_contract": V5_CONTRACT,
    },
    {
        "surface_id": "swap_quote_research_route",
        "url": (
            "https://api.xdex.xyz/api/xendex/swap/quote"
            "?network=X1%20Mainnet"
            "&token_in=B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
            "&token_out=So11111111111111111111111111111111111111112"
            "&token_in_amount=10"
            "&is_exact_amount_in=true"
        ),
        "coverage_contract": V5_CONTRACT,
    },
    {
        "surface_id": "swap_quote_frontend_alias",
        "url": (
            "https://api.xdex.xyz/api/xdex/swap/quote"
            "?network=X1%20Mainnet"
            "&token_in=B69chRzqzDCmdB5WYB8NRu5Yv5ZA95ABiZcdzCgGm9Tq"
            "&token_out=So11111111111111111111111111111111111111112"
            "&token_in_amount=10"
            "&is_exact_amount_in=true"
        ),
        "coverage_contract": V7_CONTRACT,
        "former_v6_gap_candidate": True,
    },
    {
        "surface_id": "oracle_token_price",
        "url": (
            "https://oracle.xdex.xyz/api/v1/token/price"
            "?token_address=DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
        ),
        "coverage_contract": V7_CONTRACT,
        "former_v6_gap_candidate": True,
    },
    {
        "surface_id": "oracle_sell_quote",
        "url": (
            "https://oracle.xdex.xyz/api/v1/token/sell-quote"
            "?token_address=DQ6sApYPMJ8LwpvyUjthL7amykNBJ3fx5jZi2koN7vHb"
            "&amount_in=1000"
        ),
        "coverage_contract": V7_CONTRACT,
        "former_v6_gap_candidate": True,
    },
)

KNOWN_EXECUTION_EXCLUSIONS = (
    "https://api.xdex.xyz/api/xendex/swap/prepare",
    "https://api.xdex.xyz/api/xdex/swap/prepare",
)

KNOWN_UI_ONLY_SURFACES = (
    "https://app.xdex.xyz/swap",
)

KNOWN_DOCUMENTATION_SURFACE = (
    "https://xdexdocs.gitbook.io/xdex/developers/interface-definition-idl"
)


def _truth_state() -> dict[str, Any]:
    return {
        "discovery_state": DISCOVERED,
        "provider_response_verified": False,
        "semantic_verification_complete": False,
        "source_independence_verified": False,
        "web_claim_verified": False,
        "cmis_verified": False,
    }


def _structured_result(
    *,
    url: str,
    coverage_contract: str,
) -> dict[str, Any]:
    if coverage_contract == V5_CONTRACT:
        return parse_xdex_url(url)
    if coverage_contract == V7_CONTRACT:
        return parse_xdex_extended_readonly_url(url)
    raise ValueError(f"unsupported coverage contract {coverage_contract!r}")


def xdex_coverage_reconciliation() -> dict[str, Any]:
    """Reconcile the known XDEX direct-machine inventory against v5/v7."""

    direct_rows: list[dict[str, Any]] = []
    direct_gap_rows: list[dict[str, Any]] = []

    for spec in KNOWN_DIRECT_READONLY_SURFACES:
        structured = _structured_result(
            url=str(spec["url"]),
            coverage_contract=str(spec["coverage_contract"]),
        )
        covered = bool(structured.get("supported"))
        row = {
            "surface_id": spec["surface_id"],
            "url": spec["url"],
            "coverage_contract": spec["coverage_contract"],
            "former_v6_gap_candidate": bool(
                spec.get("former_v6_gap_candidate", False)
            ),
            "covered_by_structured_contract": covered,
            "structured_endpoint_type": structured.get("endpoint_type"),
            "structured_route_verified": bool(
                structured.get("truth_state", {}).get(
                    "xdex_route_verified",
                    structured.get("truth_state", {}).get(
                        "xdex_extended_route_verified",
                        False,
                    ),
                )
            ),
            "provider_response_verified": False,
            "semantic_verification_complete": False,
        }
        direct_rows.append(row)
        if not covered:
            direct_gap_rows.append(row)

    execution_rows = []
    for url in KNOWN_EXECUTION_EXCLUSIONS:
        classification = classify_xdex_network_surface(url, method="POST")
        execution_rows.append(
            {
                "url": url,
                "classification": classification["classification"],
                "excluded": (
                    classification["classification"]
                    == EXECUTION_ADJACENT_EXCLUDED
                ),
                "read_only": classification["read_only"],
                "execution_authorized": classification["execution_authorized"],
            }
        )

    ui_rows = []
    for url in KNOWN_UI_ONLY_SURFACES:
        classification = classify_xdex_network_surface(url)
        ui_rows.append(
            {
                "url": url,
                "classification": classification["classification"],
                "ui_only": (
                    classification["classification"] == UI_ONLY_CANDIDATE
                ),
                "direct_machine_access": classification["direct_machine_access"],
                "browser_capture_justified": classification[
                    "browser_capture_justified"
                ],
            }
        )

    docs = parse_xdex_url(KNOWN_DOCUMENTATION_SURFACE)

    former_gap_rows = [
        row for row in direct_rows if row["former_v6_gap_candidate"]
    ]
    former_gaps_closed = bool(former_gap_rows) and all(
        row["covered_by_structured_contract"] for row in former_gap_rows
    )

    known_direct_complete = (
        not direct_gap_rows
        and all(row["covered_by_structured_contract"] for row in direct_rows)
    )
    execution_exclusions_intact = all(
        row["excluded"]
        and row["read_only"] is False
        and row["execution_authorized"] is False
        for row in execution_rows
    )
    ui_boundary_intact = all(
        row["ui_only"]
        and row["direct_machine_access"] is False
        and row["browser_capture_justified"] is False
        for row in ui_rows
    )

    return {
        "contract": COVERAGE_RECONCILIATION_CONTRACT,
        "scope": "known_repository_owned_xdex_surface_inventory",
        "universal_xdex_endpoint_completeness_verified": False,
        "known_direct_readonly_surface_count": len(direct_rows),
        "known_direct_readonly_surfaces": direct_rows,
        "known_direct_readonly_gap_count": len(direct_gap_rows),
        "known_direct_readonly_gaps": direct_gap_rows,
        "former_v6_gap_candidate_count": len(former_gap_rows),
        "former_v6_gap_candidates_covered_by_v7": former_gaps_closed,
        "known_execution_exclusion_count": len(execution_rows),
        "known_execution_exclusions": execution_rows,
        "execution_exclusions_intact": execution_exclusions_intact,
        "known_ui_only_surface_count": len(ui_rows),
        "known_ui_only_surfaces": ui_rows,
        "ui_only_boundary_intact": ui_boundary_intact,
        "documentation_surface_covered": bool(docs.get("supported")),
        "xdex_direct_machine_coverage_complete_for_known_inventory": (
            known_direct_complete
        ),
        "browser_capture_required_now": False,
        "browser_capture_decision_basis": (
            "No known useful direct read-only XDEX surface remains uncovered "
            "after v5 and v7; known UI-only routes have no unique machine-data "
            "requirement that justifies browser capture."
        ),
        "recommended_next_source": "x1_ninja",
        "recommended_next_action": (
            "Begin source-specific X1.Ninja structured discovery and preserve "
            "XDEX v5-v8 as internal DISCOVERED-only coverage."
        ),
        "truth_state": _truth_state(),
        "read_only": True,
        "request_replay_authorized": False,
        "background_monitoring_authorized": False,
        "public_service_promoted": False,
        "scout_reliance_promoted": False,
        "cmis_promotable": False,
        "execution_authorized": False,
    }


__all__ = [
    "COVERAGE_RECONCILIATION_CONTRACT",
    "KNOWN_DIRECT_READONLY_SURFACES",
    "KNOWN_DOCUMENTATION_SURFACE",
    "KNOWN_EXECUTION_EXCLUSIONS",
    "KNOWN_UI_ONLY_SURFACES",
    "xdex_coverage_reconciliation",
]
