"""Narrow Solana risk-check gateway layer for CMIS.

This adapter composes already-accepted Solana market and tokenomics service
results into the existing deterministic risk core. It never upgrades pair-
scoped market evidence, cross-source price agreement, or missing historical
facts into verified risk inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT
from liquidity_scout.services.cmis_contract import (
    ERROR,
    OK,
    PARTIAL,
    build_service_envelope,
)
from liquidity_scout.services.risk import build_risk_check

SERVICE = "risk_check"
CHAIN = "solana"
_ALLOWED_PARAMS = frozenset({"policy"})


def _risk_market_input(mint: str, market_data: Mapping[str, Any]) -> dict[str, Any]:
    """Translate only risk-core-compatible verified market facts.

    The first Solana market slice has no verified asset-wide liquidity, volume,
    transaction total, or current price. Those values therefore remain absent
    and their completeness flags remain false even when source observations are
    present.
    """

    return {
        "symbol": None,
        "mint": mint,
        "price_usd": None,
        "liquidity_usd": None,
        "volume_24h_usd": None,
        "transactions_24h": None,
        "completeness": {
            "price": False,
            "liquidity": market_data.get("asset_wide_liquidity_verified") is True,
            "volume_24h": market_data.get("asset_wide_volume_24h_verified") is True,
            "transactions_24h": market_data.get("transactions_24h_verified") is True,
            "holders": market_data.get("holders_verified") is True,
        },
    }


def _risk_tokenomics_input(tokenomics_data: Mapping[str, Any]) -> dict[str, Any]:
    mint_status = tokenomics_data.get("mint_authority_status")
    freeze_status = tokenomics_data.get("freeze_authority_status")
    return {
        "supply_verified": tokenomics_data.get("supply_verified") is True,
        "mint_authority_verified": (
            tokenomics_data.get("mint_authority_verified") is True
        ),
        "freeze_authority_verified": (
            tokenomics_data.get("freeze_authority_verified") is True
        ),
        "mint_authority_state": mint_status,
        "freeze_authority_state": freeze_status,
        # The accepted tokenomics gate already fails closed if canonical mint
        # identity and getTokenSupply disagree on decimals.
        "rpc_decimals_consistent": True,
        # No bounded Solana mint/burn activity scanner has been accepted yet.
        "token_activity": {
            "available": False,
            "activity_verified": False,
            "coverage_scope": None,
            "lifetime_coverage_verified": False,
        },
    }


def _copy_sources(*envelopes: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for envelope in envelopes:
        sources = envelope.get("sources")
        if not isinstance(sources, list):
            continue
        for source in sources:
            if isinstance(source, Mapping):
                record = dict(source)
                if record not in result:
                    result.append(record)
    risk_source = {"source": "risk_engine", "role": "risk_check"}
    if risk_source not in result:
        result.append(risk_source)
    return result


def _copy_warning_records(envelope: Mapping[str, Any]) -> list[dict[str, Any]]:
    warnings = envelope.get("warnings")
    if not isinstance(warnings, list):
        return []
    return [dict(item) for item in warnings if isinstance(item, Mapping)]


def _risk_warnings(risk_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    flags = risk_result.get("flags")
    reasons = risk_result.get("reasons")
    flag_list = list(flags) if isinstance(flags, list) else []
    reason_list = list(reasons) if isinstance(reasons, list) else []
    result = []
    for index, flag in enumerate(flag_list):
        record = {"code": str(flag)}
        if index < len(reason_list) and reason_list[index]:
            record["message"] = str(reason_list[index])
        result.append(record)
    return result


class SolanaRiskCheckMixin:
    """Cooperative CMIS mixin for deterministic Solana risk assessment."""

    def _solana_risk_error(self, code: str, message: str):
        return build_service_envelope(
            SERVICE,
            CHAIN,
            ERROR,
            errors=[{"code": code, "message": message}],
        )

    def _solana_risk_check(self, asset: Any, params: Mapping[str, Any]):
        unknown = sorted(set(params) - _ALLOWED_PARAMS)
        if unknown:
            return self._solana_risk_error(
                "solana_risk_params_not_supported",
                (
                    "Unsupported Solana risk parameters: " + ", ".join(unknown) + ". "
                    "Historical risk is not promoted until Solana historical_compare "
                    "has an accepted evidence contract."
                ),
            )

        policy = params.get("policy")
        if policy is not None and not isinstance(policy, Mapping):
            return self._solana_risk_error(
                "invalid_risk_policy",
                "params.policy must be a mapping when supplied.",
            )

        market = self._solana_market_report(asset)
        if not isinstance(market, Mapping):
            return self._solana_risk_error(
                "solana_market_report_contract_invalid",
                "The Solana market-report prerequisite returned a malformed result.",
            )
        if market.get("status") not in {OK, PARTIAL}:
            return self._propagate_upstream(SERVICE, market)

        tokenomics = self._solana_tokenomics(asset)
        if not isinstance(tokenomics, Mapping):
            return self._solana_risk_error(
                "solana_tokenomics_contract_invalid",
                "The Solana tokenomics prerequisite returned a malformed result.",
            )
        if tokenomics.get("status") not in {OK, PARTIAL}:
            return self._propagate_upstream(SERVICE, tokenomics)

        market_data = market.get("data")
        tokenomics_data = tokenomics.get("data")
        market_asset = market.get("asset")
        tokenomics_asset = tokenomics.get("asset")
        if (
            not isinstance(market_data, Mapping)
            or not isinstance(tokenomics_data, Mapping)
            or not isinstance(market_asset, Mapping)
            or not isinstance(tokenomics_asset, Mapping)
        ):
            return self._solana_risk_error(
                "solana_risk_prerequisite_contract_invalid",
                "Solana market/tokenomics prerequisite data is incomplete.",
            )

        market_mint = market_asset.get("mint")
        tokenomics_mint = tokenomics_asset.get("mint")
        if (
            not isinstance(market_mint, str)
            or not market_mint
            or market_mint != tokenomics_mint
        ):
            return self._solana_risk_error(
                "solana_risk_asset_identity_conflict",
                "Solana market and tokenomics prerequisites do not identify the same mint.",
            )

        risk_market = _risk_market_input(market_mint, market_data)
        risk_tokenomics = _risk_tokenomics_input(tokenomics_data)
        try:
            risk_result = build_risk_check(
                risk_market,
                risk_tokenomics,
                None,
                chain=CHAIN,
                policy=policy,
            )
        except ValueError as exc:
            return self._solana_risk_error(
                "risk_check_validation_error",
                f"Deterministic risk policy/input validation failed ({type(exc).__name__}).",
            )
        except Exception as exc:
            return self._solana_risk_error(
                "risk_check_failed_closed",
                f"Deterministic risk evaluation failed ({type(exc).__name__}).",
            )

        if not isinstance(risk_result, Mapping):
            return self._solana_risk_error(
                "risk_check_contract_invalid",
                "The deterministic risk engine returned a malformed result.",
            )

        confidence = risk_result.get("confidence")
        if not isinstance(confidence, Mapping):
            return self._solana_risk_error(
                "risk_check_contract_invalid",
                "The deterministic risk result contains no valid confidence record.",
            )

        verified = confidence.get("verified_checks")
        total = confidence.get("total_checks")
        complete = (
            isinstance(verified, int)
            and not isinstance(verified, bool)
            and isinstance(total, int)
            and not isinstance(total, bool)
            and total > 0
            and verified == total
        )

        warnings = _risk_warnings(risk_result)
        for upstream in (market, tokenomics):
            for warning in _copy_warning_records(upstream):
                if warning not in warnings:
                    warnings.append(warning)

        crosscheck = market_data.get("price_crosscheck")
        crosscheck_status = (
            crosscheck.get("status") if isinstance(crosscheck, Mapping) else None
        )
        if crosscheck_status == CONFLICT:
            warnings.append(
                {
                    "code": "solana_price_conflict_not_scored",
                    "message": (
                        "Cross-source Solana price conflict is preserved as context but "
                        "is not assigned a new risk severity by the current calibrated core."
                    ),
                }
            )
        elif crosscheck_status == AGREEMENT:
            warnings.append(
                {
                    "code": "solana_price_agreement_not_scored",
                    "message": (
                        "Cross-source Solana price agreement is preserved as context but "
                        "does not count as verified current-price risk evidence."
                    ),
                }
            )

        return build_service_envelope(
            SERVICE,
            CHAIN,
            OK if complete else PARTIAL,
            asset={"chain": CHAIN, "mint": market_mint},
            data={
                "input_services": {
                    "market_report_status": market.get("status"),
                    "tokenomics_status": tokenomics.get("status"),
                },
                "market_price_crosscheck_status": crosscheck_status,
                "historical_compare_used": False,
            },
            risk=dict(risk_result),
            confidence=dict(confidence),
            sources=_copy_sources(market, tokenomics),
            observed_at=None,
            warnings=warnings,
            errors=[],
        )

    def dispatch(self, request: Any):
        if isinstance(request, Mapping):
            service = (self._text(request.get("service")) or "").lower()
            chain = (self._text(request.get("chain")) or "").lower()
            if service == SERVICE and chain == CHAIN:
                params = request.get("params", {})
                if not isinstance(params, Mapping):
                    return self._gateway_error(
                        SERVICE,
                        CHAIN,
                        "invalid_params",
                        "params must be a JSON object/mapping.",
                    )
                return self._solana_risk_check(request.get("asset"), params)

        return super().dispatch(request)


__all__ = ["CHAIN", "SERVICE", "SolanaRiskCheckMixin"]
