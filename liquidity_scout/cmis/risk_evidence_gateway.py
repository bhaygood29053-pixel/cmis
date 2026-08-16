"""Evidence-aware runtime composition for CMIS risk checks.

The base ``CMISGateway`` owns the stable seven-service contract. This runtime
subclass enriches risk/pre-trade requests with provider-backed evidence that the
pure deterministic risk core already understands:

- bounded X1 mint/burn activity through ``X1ActivityScanner``
- a default verified 24h price comparison through the existing history service

Missing provider data remains explicit uncertainty. This layer never invents
historical baselines, lifetime token activity, risk scores, or execution state.
"""

from __future__ import annotations

from collections.abc import Mapping
import os
from typing import Any

from liquidity_scout.cmis.assets import MARKET_PLUS_NATIVE
from liquidity_scout.cmis.gateway import CMISGateway
from liquidity_scout.providers.x1.activity_scanner import (
    X1ActivityScanner,
    open_activity_db,
)
from liquidity_scout.providers.x1.rpc import X1RPCProvider
from liquidity_scout.services.cmis_contract import AMBIGUOUS, ERROR, UNAVAILABLE
from liquidity_scout.services.cmis_risk import build_risk_check_response
from liquidity_scout.services.cmis_tokenomics import build_tokenomics_response


DEFAULT_RISK_HISTORICAL_QUESTION = "Has price changed in the last 24 hours?"
DEFAULT_RISK_ACTIVITY_MAX_SIGNATURES = 50
DEFAULT_TOKEN_ACTIVITY_DB = os.path.join(
    os.path.expanduser("~"),
    ".liquidity_scout",
    "token_activity.db",
)


def _positive_int(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return parsed


class EvidenceAwareCMISGateway(CMISGateway):
    """CMIS runtime gateway that proactively supplies verified risk evidence."""

    def __init__(
        self,
        *,
        x1_rpc_provider: X1RPCProvider | None = None,
        x1_activity_scanner: X1ActivityScanner | None = None,
        activity_db_path: str | None = None,
        risk_activity_max_signatures: int | None = None,
        risk_historical_question: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.x1_rpc_provider = x1_rpc_provider or X1RPCProvider()
        self.x1_activity_scanner = x1_activity_scanner or X1ActivityScanner(
            self.x1_rpc_provider.request
        )

        configured_db = (
            activity_db_path
            if activity_db_path is not None
            else os.getenv("CMIS_TOKEN_ACTIVITY_DB", DEFAULT_TOKEN_ACTIVITY_DB)
        )
        self.activity_db_path = str(configured_db or "").strip()
        if not self.activity_db_path:
            raise ValueError("CMIS token-activity database path must not be empty.")

        configured_bound = (
            risk_activity_max_signatures
            if risk_activity_max_signatures is not None
            else os.getenv(
                "CMIS_RISK_ACTIVITY_MAX_SIGNATURES",
                str(DEFAULT_RISK_ACTIVITY_MAX_SIGNATURES),
            )
        )
        self.risk_activity_max_signatures = _positive_int(
            "risk_activity_max_signatures",
            configured_bound,
        )

        configured_question = (
            risk_historical_question
            if risk_historical_question is not None
            else os.getenv(
                "CMIS_RISK_HISTORICAL_QUESTION",
                DEFAULT_RISK_HISTORICAL_QUESTION,
            )
        )
        self.risk_historical_question = str(configured_question or "").strip()
        if not self.risk_historical_question:
            raise ValueError("CMIS risk historical question must not be empty.")

    def _risk_activity_bound(self, params: Mapping[str, Any]):
        raw = params.get(
            "activity_max_signatures",
            self.risk_activity_max_signatures,
        )
        try:
            return _positive_int("activity_max_signatures", raw), None
        except ValueError as exc:
            return None, self._gateway_error(
                "risk_check",
                "x1",
                "invalid_activity_max_signatures",
                str(exc),
            )

    def _collect_token_activity(
        self,
        *,
        mint: Any,
        decimals: Any,
        max_signatures: int,
    ):
        mint_text = self._text(mint)
        if not mint_text:
            return None, {
                "code": "token_activity_scan_skipped_mint_unverified",
                "message": "A verified mint is required before bounded token-activity scanning.",
            }
        if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0:
            return None, {
                "code": "token_activity_scan_skipped_decimals_unverified",
                "message": (
                    "Verified token decimals are required before bounded token-activity "
                    "scanning can be attached to risk evidence."
                ),
            }

        db = None
        try:
            if self.activity_db_path != ":memory:":
                parent = os.path.dirname(os.path.abspath(self.activity_db_path))
                if parent:
                    os.makedirs(parent, exist_ok=True)
            db = open_activity_db(self.activity_db_path)
            report = self.x1_activity_scanner.scan(
                mint=mint_text,
                decimals=decimals,
                db=db,
                max_signatures=max_signatures,
            )
        except Exception as exc:
            return None, {
                "code": "token_activity_collection_failed",
                "message": f"Bounded X1 token-activity collection failed: {exc}",
            }
        finally:
            if db is not None:
                db.close()

        if not isinstance(report, Mapping):
            return None, {
                "code": "token_activity_collection_malformed",
                "message": "The X1 activity scanner returned no usable structured report.",
            }

        result = dict(report)
        if not result.get("source"):
            result["source"] = getattr(
                self.x1_activity_scanner,
                "source",
                "X1 RPC parsed token instructions",
            )
        return result, None

    def _risk_check(self, asset: Any, params: Mapping[str, Any]):
        definition = self._canonical_definition(asset)
        market = self._market_report(asset)
        if market.get("status") in {ERROR, UNAVAILABLE, AMBIGUOUS}:
            return self._propagate_upstream("risk_check", market)

        market_data = market.get("data")
        market_identity = self._provider_asset_from_data(market_data)
        native_mode = (
            isinstance(definition, Mapping)
            and self.asset_registry.service_mode(definition, "risk_check")
            == MARKET_PLUS_NATIVE
        )

        collection_warning = None
        if native_mode:
            # Native network assets do not use token-program mint/burn scanning.
            tokenomics = self._native_asset_tokenomics(definition)
        else:
            mint = market_identity.get("mint")
            symbol = market_identity.get("symbol")
            name = market_identity.get("name")
            tokenomics = build_tokenomics_response(
                mint,
                symbol=symbol,
                name=name,
                chain="x1",
            )

            bound, bound_error = self._risk_activity_bound(params)
            if bound_error is not None:
                return bound_error

            base_data = tokenomics.get("data")
            if tokenomics.get("status") != ERROR and isinstance(base_data, Mapping):
                activity_report, collection_warning = self._collect_token_activity(
                    mint=mint,
                    decimals=base_data.get("decimals"),
                    max_signatures=bound,
                )
                if activity_report is not None:
                    # Re-run the tokenomics verification service so scanner mint,
                    # decimals, coverage, and net issuance are independently
                    # cross-checked against current RPC facts before risk use.
                    tokenomics = build_tokenomics_response(
                        mint,
                        symbol=symbol,
                        name=name,
                        chain="x1",
                        activity_report=activity_report,
                    )

        tokenomics_data = (
            tokenomics.get("data")
            if tokenomics.get("status") != ERROR
            and isinstance(tokenomics.get("data"), Mapping)
            else None
        )

        historical_question = (
            self._text(params.get("historical_question"))
            or self.risk_historical_question
        )
        historical = self._historical_from_market(historical_question, market)
        historical_data = None
        if (
            historical.get("status") in {"ok", "partial"}
            and isinstance(historical.get("data"), Mapping)
        ):
            historical_data = historical.get("data")

        policy = params.get("policy")
        if policy is not None and not isinstance(policy, Mapping):
            return self._gateway_error(
                "risk_check",
                "x1",
                "invalid_risk_policy",
                "params.policy must be a mapping when supplied.",
            )

        response = build_risk_check_response(
            market_data,
            tokenomics_data,
            historical_data,
            chain="x1",
            policy=policy,
            observed_at=market.get("observed_at"),
        )
        if collection_warning is not None:
            response.setdefault("warnings", []).append(collection_warning)

        if isinstance(definition, Mapping):
            response = self._canonicalize(
                response,
                definition,
                provider_asset=market_identity,
                role="market",
            )
        return response


__all__ = [
    "DEFAULT_RISK_ACTIVITY_MAX_SIGNATURES",
    "DEFAULT_RISK_HISTORICAL_QUESTION",
    "DEFAULT_TOKEN_ACTIVITY_DB",
    "EvidenceAwareCMISGateway",
]
