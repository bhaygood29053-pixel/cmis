"""Quote-denominated lifetime coverage policy for X1 price history.

This policy deliberately separates two claims:

1. full_supported_pair_lifetime_verified
   The exact provider market pair has a verified lifetime start, complete
   cadence coverage through a fresh current end, and exact pair identity.

2. full_usd_lifetime_verified
   The same price series is additionally proven to be USD-denominated for the
   whole lifetime. This requires a separate historical quote/USD equivalence
   proof and is never inferred from a stable-token name or configuration.

For XNT/USDC.X this lets CMIS truthfully prove the complete XNT price history in
USDC.X quote units without pretending that every historical USDC.X was exactly
one US dollar.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SCHEMA = "x1_quote_price_historical_coverage.v1"
POLICY_ID = "cmis.x1.quote_price_historical_coverage.v1"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def evaluate_x1_quote_price_historical_coverage(
    *,
    supported_lifetime_range: Any,
    exact_pair_quote_identity_verified: bool,
    canonical_fact_timestamps_verified: bool,
    historical_quote_usd_equivalence_verified: bool = False,
) -> dict[str, Any]:
    """Promote exact pair-lifetime price coverage without inventing USD truth."""

    lifetime = _mapping(supported_lifetime_range)
    base_mint = _text(lifetime.get("base_mint"))
    quote_mint = _text(lifetime.get("quote_mint"))

    pair_lifetime_range_verified = bool(
        lifetime.get("supported_lifetime_range_complete_verified") is True
        and lifetime.get("provider_range_complete_verified") is True
        and lifetime.get("archive_exhaustion_verified") is True
        and lifetime.get("price_bar_continuity_verified") is True
        and lifetime.get("global_provider_archive_complete_verified") is False
    )

    identity_verified = bool(
        exact_pair_quote_identity_verified is True
        and base_mint
        and quote_mint
        and base_mint != quote_mint
    )
    timestamps_verified = canonical_fact_timestamps_verified is True

    full_supported_pair_lifetime_verified = bool(
        pair_lifetime_range_verified
        and identity_verified
        and timestamps_verified
    )

    quote_usd_verified = historical_quote_usd_equivalence_verified is True
    full_usd_lifetime_verified = bool(
        full_supported_pair_lifetime_verified
        and quote_usd_verified
    )

    missing_pair_gates = []
    if not pair_lifetime_range_verified:
        missing_pair_gates.append("supported_pair_lifetime_range")
    if not identity_verified:
        missing_pair_gates.append("exact_pair_quote_identity")
    if not timestamps_verified:
        missing_pair_gates.append("canonical_fact_timestamps")

    missing_usd_gates = list(missing_pair_gates)
    if not quote_usd_verified:
        missing_usd_gates.append("historical_quote_usd_equivalence")

    return {
        "schema": SCHEMA,
        "policy_id": POLICY_ID,
        "metric": "price",
        "base_mint": base_mint,
        "quote_mint": quote_mint,
        "quote_unit": quote_mint,
        "supported_lifetime_scope": "first_verified_supported_market_interval_to_fresh_current_end",
        "pair_lifetime_status": (
            "verified" if full_supported_pair_lifetime_verified else "partial"
        ),
        "usd_lifetime_status": (
            "verified" if full_usd_lifetime_verified else "partial"
        ),
        "full_supported_pair_lifetime_verified": (
            full_supported_pair_lifetime_verified
        ),
        "continuous_pair_price_coverage_verified": (
            full_supported_pair_lifetime_verified
        ),
        "provider_range_complete_verified": (
            pair_lifetime_range_verified
        ),
        "archive_exhaustion_verified": (
            lifetime.get("archive_exhaustion_verified") is True
        ),
        "historical_quote_usd_equivalence_verified": quote_usd_verified,
        "full_usd_lifetime_verified": full_usd_lifetime_verified,
        "continuous_usd_price_coverage_verified": full_usd_lifetime_verified,
        "full_asset_lifetime_verified": full_usd_lifetime_verified,
        "continuous_coverage_verified": full_usd_lifetime_verified,
        "missing_pair_gates": missing_pair_gates,
        "missing_usd_gates": missing_usd_gates,
        "limitations": [
            "pair_lifetime_truth_is_quote_denominated",
            "quote_token_name_or_configuration_does_not_prove_historical_usd_equivalence",
            "global_provider_archive_completeness_not_claimed",
        ],
    }


__all__ = [
    "POLICY_ID",
    "SCHEMA",
    "evaluate_x1_quote_price_historical_coverage",
]
