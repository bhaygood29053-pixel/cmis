"""Fail-closed field-level semantics for observed XDEX read-only quotes.

This module performs no network I/O and does not reconstruct swap economics. It
records only semantics backed by explicit independent evidence supplied by the
caller. Unknown output/fee/slippage/fill semantics remain unverified.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


SCHEMA = "xdex_quote_field_semantics.v1"


@dataclass(frozen=True)
class XDEXQuoteSemanticResult:
    schema: str
    route_identity_verified: bool
    amm_config_identity_verified: bool
    trade_fee_config_verified: bool
    trade_fee_bps: int | None
    price_impact_semantics_verified: bool
    output_amount_semantics_verified: bool
    output_decomposition_verified: bool
    slippage_semantics_verified: bool
    fill_quality_verified: bool
    execution_quality_verified: bool
    cmis_promotable: bool


def _finite_decimal(value: Any, *, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must not be boolean")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError(f"{field} must be finite numeric") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field} must be finite numeric")
    return parsed


def classify_xdex_quote_semantics(
    quote: Mapping[str, Any],
    *,
    requested_input_mint: str,
    requested_output_mint: str,
    independently_verified_amm_config: str | None = None,
    independently_verified_trade_fee_bps: int | None = None,
    corroborated_price_impact_pct: Any | None = None,
) -> XDEXQuoteSemanticResult:
    """Classify only independently evidenced quote-field semantics.

    Route identity is verified only when the response preserves the exact requested
    mint pair. AMM-config identity requires an independently verified config address.
    Trade-fee configuration requires an explicit independently verified basis-point
    value. Price-impact semantics require an independent numeric corroboration equal
    to the provider field. No combination of these facts verifies outputAmount,
    unexplained output adjustments, slippage, fill quality, or execution quality.
    """

    if not isinstance(quote, Mapping):
        raise ValueError("quote must be a mapping")
    input_mint = str(requested_input_mint or "").strip()
    output_mint = str(requested_output_mint or "").strip()
    if not input_mint or not output_mint or input_mint == output_mint:
        raise ValueError("requested mint identities must be distinct and non-empty")

    observed_input = str(quote.get("inputMint") or "").strip()
    observed_output = str(quote.get("outputMint") or "").strip()
    route_verified = observed_input == input_mint and observed_output == output_mint

    observed_config = str(quote.get("amm_config_address") or "").strip()
    expected_config = str(independently_verified_amm_config or "").strip()
    config_verified = bool(route_verified and expected_config and observed_config == expected_config)

    fee_verified = False
    fee_bps: int | None = None
    if independently_verified_trade_fee_bps is not None:
        fee = independently_verified_trade_fee_bps
        if isinstance(fee, bool) or not isinstance(fee, int) or not 0 <= fee <= 10_000:
            raise ValueError("independently_verified_trade_fee_bps must be an integer from 0 to 10000")
        if not config_verified:
            raise ValueError("trade-fee configuration cannot be verified without AMM-config identity")
        fee_verified = True
        fee_bps = fee

    impact_verified = False
    if corroborated_price_impact_pct is not None:
        if "priceImpactPct" not in quote:
            raise ValueError("quote omitted priceImpactPct")
        observed_impact = _finite_decimal(quote["priceImpactPct"], field="priceImpactPct")
        corroborated_impact = _finite_decimal(corroborated_price_impact_pct, field="corroborated_price_impact_pct")
        impact_verified = route_verified and config_verified and observed_impact == corroborated_impact

    return XDEXQuoteSemanticResult(
        schema=SCHEMA,
        route_identity_verified=route_verified,
        amm_config_identity_verified=config_verified,
        trade_fee_config_verified=fee_verified,
        trade_fee_bps=fee_bps,
        price_impact_semantics_verified=impact_verified,
        output_amount_semantics_verified=False,
        output_decomposition_verified=False,
        slippage_semantics_verified=False,
        fill_quality_verified=False,
        execution_quality_verified=False,
        cmis_promotable=False,
    )


__all__ = ["SCHEMA", "XDEXQuoteSemanticResult", "classify_xdex_quote_semantics"]
