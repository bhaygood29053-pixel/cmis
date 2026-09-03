"""Structured Liquidity Scout service capabilities."""

from .cmis_asset_lookup import build_asset_lookup_response
from .cmis_contract import (
    AMBIGUOUS,
    ERROR,
    OK,
    PARTIAL,
    SERVICE_STATUSES,
    UNAVAILABLE,
    build_service_envelope,
)
from .cmis_historical import build_historical_compare_response
from .cmis_market import build_market_report_response
from .cmis_native_tokenomics import build_native_tokenomics_response
from .cmis_pre_trade import build_pre_trade_check_response
from .cmis_rank import SUPPORTED_RANK_METRICS, build_rank_response
from .cmis_risk import build_risk_check_response
from .cmis_tokenomics import build_tokenomics_response
from .historical_compare import (
    DEFAULT_PROFILE_METRICS,
    SUPPORTED_PROFILE_METRICS,
    build_all_available_history_profile,
    build_all_available_pair_comparison,
    build_historical_comparison,
    format_historical_comparison,
)
from .market_comparison import format_market_comparison
from .x1_quote_price_historical_coverage import (
    evaluate_x1_quote_price_historical_coverage,
)
from .market_context import (
    build_verified_market_context,
    liquidity_depth_label,
    price_movement_label,
    volume_activity_label,
)
from .market_presentation import (
    FIELD_ORDER,
    format_field_line,
    full_snapshot_lines,
    requested_asset_fields,
    wants_token_address,
)
from .market_rankings import (
    find_asset_rank,
    format_top,
    rank_assets,
)
from .market_report import build_market_report
from .pre_trade import DEFAULT_PRE_TRADE_POLICY, build_pre_trade_check
from .risk import (
    BLOCK,
    DEFAULT_RISK_POLICY,
    PASS,
    WARN,
    build_risk_check,
)
from .tokenomics import build_tokenomics_report


def __getattr__(name: str):
    """Resolve verification helpers lazily across the public/private boundary."""

    if name == "build_verification_evidence_response":
        from .cmis_verification_evidence import build_verification_evidence_response

        return build_verification_evidence_response
    if name == "lookup_verification_evidence":
        from .cmis_verification_evidence_lookup import lookup_verification_evidence

        return lookup_verification_evidence
    raise AttributeError(name)

__all__ = [
    "AMBIGUOUS",
    "BLOCK",
    "DEFAULT_PRE_TRADE_POLICY",
    "DEFAULT_PROFILE_METRICS",
    "DEFAULT_RISK_POLICY",
    "ERROR",
    "FIELD_ORDER",
    "OK",
    "PARTIAL",
    "PASS",
    "SERVICE_STATUSES",
    "SUPPORTED_PROFILE_METRICS",
    "SUPPORTED_RANK_METRICS",
    "UNAVAILABLE",
    "WARN",
    "build_all_available_history_profile",
    "build_all_available_pair_comparison",
    "build_asset_lookup_response",
    "build_historical_compare_response",
    "build_historical_comparison",
    "build_market_report",
    "build_market_report_response",
    "build_native_tokenomics_response",
    "build_pre_trade_check",
    "build_pre_trade_check_response",
    "build_rank_response",
    "build_risk_check",
    "build_risk_check_response",
    "build_service_envelope",
    "build_tokenomics_report",
    "build_tokenomics_response",
    "build_verification_evidence_response",
    "build_verified_market_context",
    "evaluate_x1_quote_price_historical_coverage",
    "find_asset_rank",
    "format_field_line",
    "format_historical_comparison",
    "format_market_comparison",
    "format_top",
    "full_snapshot_lines",
    "liquidity_depth_label",
    "lookup_verification_evidence",
    "price_movement_label",
    "rank_assets",
    "requested_asset_fields",
    "volume_activity_label",
    "wants_token_address",
]
