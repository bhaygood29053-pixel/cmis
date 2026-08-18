"""Production opt-in XDEX-program activity scope for CMIS v1.5.6.

This mixin leaves the normal provider-backed ``verified_asset_activity`` path
unchanged unless callers explicitly request both ``chain_window=true`` and
``verified_xdex_program_scope=true``.

When enabled, it composes the independently verified XDEX-program pool-set
resolver with the existing chain-window enumerator. A successful result may
promote completeness for the verified XDEX program only. It deliberately does
not promote all-X1 DEX completeness, global AMM-program registry completeness,
or global on-chain pool discovery.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from liquidity_scout.providers.x1.verified_program_pool_set import (
    verify_recognized_program_asset_pool_set,
)
from liquidity_scout.services.cmis_chain_window_dex import (
    enumerate_chain_window_dex_activity,
)
from liquidity_scout.services.cmis_verified_asset_activity import (
    SERVICE as VERIFIED_ASSET_ACTIVITY_SERVICE,
)

VERSION = "1.5.6"
SCOPE_PARAM = "verified_xdex_program_scope"
SCOPE_NAME = "verified_xdex_program"
SCOPE_BASIS = "VERIFIED_PROGRAM_POOL_SET_PLUS_X1_RPC_ADDRESS_HISTORY"


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _iso_epoch(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).timestamp()


class VerifiedXDEXProgramScopeMixin:
    """Opt-in program-scoped chain-window coverage for X1 asset activity."""

    def __init__(
        self,
        *,
        x1_verified_program_pool_set_resolver=None,
        **kwargs,
    ):
        self.x1_verified_program_pool_set_resolver = (
            x1_verified_program_pool_set_resolver
            or verify_recognized_program_asset_pool_set
        )
        super().__init__(**kwargs)

    @staticmethod
    def _compact_pool_set(pool_set: Mapping[str, Any]) -> dict[str, Any]:
        pools = []
        for raw in pool_set.get("pools") or []:
            if not isinstance(raw, Mapping):
                continue
            pools.append({
                "pool_address": _text(raw.get("pool_address")),
                "pair": _text(raw.get("pair")),
                "mint_0": _text(raw.get("mint_0")),
                "mint_1": _text(raw.get("mint_1")),
                "catalog_listed": raw.get("catalog_listed") is True,
                "pool_state_structural_role_verified": (
                    raw.get("pool_state_structural_role_verified") is True
                ),
                "recent_recognized_instruction_coupling_observed": (
                    raw.get("recent_recognized_instruction_coupling_observed")
                    is True
                ),
            })

        summary = pool_set.get("summary")
        summary = dict(summary) if isinstance(summary, Mapping) else {}
        return {
            "service": pool_set.get("service"),
            "version": pool_set.get("version"),
            "status": pool_set.get("status"),
            "program_id": pool_set.get("program_id"),
            "account_space": pool_set.get("account_space"),
            "mint_offsets": list(pool_set.get("mint_offsets") or []),
            "vault_offsets": list(pool_set.get("vault_offsets") or []),
            "pools": pools,
            "summary": summary,
            "errors": list(pool_set.get("errors") or []),
        }

    @staticmethod
    def _scope_failure(response, message, *, pool_set=None):
        if not isinstance(response, dict):
            return response

        data = response.get("data")
        if not isinstance(data, dict):
            data = {}
            response["data"] = data
        if isinstance(pool_set, Mapping):
            data["verified_xdex_program_pool_set"] = (
                VerifiedXDEXProgramScopeMixin._compact_pool_set(pool_set)
            )

        confidence = response.get("confidence")
        if not isinstance(confidence, dict):
            confidence = {}
            response["confidence"] = confidence
        confidence["xdex_program_asset_pool_set_complete"] = False
        confidence["xdex_program_chain_window_complete"] = False
        confidence["xdex_program_asset_window_complete"] = False
        confidence["x1_all_dex_asset_window_complete"] = False
        confidence["recognized_program_registry_globally_exhaustive"] = False
        confidence["global_onchain_pool_discovery_proven"] = False

        warnings = response.get("warnings")
        warnings = list(warnings) if isinstance(warnings, list) else []
        warnings.append({
            "code": "verified_xdex_program_scope_unavailable",
            "message": str(message),
        })
        response["warnings"] = warnings
        if response.get("status") == "ok":
            response["status"] = "partial"
        return response

    @staticmethod
    def _attach_program_scope(response, pool_set, activity):
        if not isinstance(response, dict):
            return response
        if not isinstance(pool_set, Mapping) or not isinstance(activity, Mapping):
            return response

        data = response.get("data")
        if not isinstance(data, dict):
            data = {}
            response["data"] = data
        data["verified_xdex_program_pool_set"] = (
            VerifiedXDEXProgramScopeMixin._compact_pool_set(pool_set)
        )

        pool_summary = pool_set.get("summary")
        pool_summary = pool_summary if isinstance(pool_summary, Mapping) else {}
        activity_summary = activity.get("summary")
        activity_summary = (
            activity_summary if isinstance(activity_summary, Mapping) else {}
        )

        pool_set_complete = pool_summary.get(
            "recognized_program_asset_pool_set_structurally_verified"
        ) is True
        chain_window_complete = activity_summary.get(
            "selected_pool_chain_window_complete"
        ) is True
        xdex_program_complete = bool(pool_set_complete and chain_window_complete)

        confidence = response.get("confidence")
        if not isinstance(confidence, dict):
            confidence = {}
            response["confidence"] = confidence
        confidence["xdex_program_asset_pool_set_complete"] = pool_set_complete
        confidence["xdex_program_chain_window_complete"] = chain_window_complete
        confidence["xdex_program_asset_window_complete"] = xdex_program_complete
        confidence["xdex_program_coverage_scope"] = SCOPE_NAME
        confidence["x1_all_dex_asset_window_complete"] = False
        confidence["recognized_program_registry_globally_exhaustive"] = False
        confidence["global_onchain_pool_discovery_proven"] = False

        activity_window = data.get("activity_window")
        if isinstance(activity_window, Mapping):
            activity_window = dict(activity_window)
            activity_window["xdex_program_coverage_complete"] = (
                xdex_program_complete
            )
            activity_window["xdex_program_coverage_basis"] = SCOPE_BASIS
            activity_window["x1_all_dex_asset_window_complete"] = False
            if xdex_program_complete:
                activity_window["effective_coverage_scope"] = SCOPE_NAME
            data["activity_window"] = activity_window

        warnings = response.get("warnings")
        warnings = list(warnings) if isinstance(warnings, list) else []
        reconciled = []
        replaced_scope_warning = False
        for raw in warnings:
            if not isinstance(raw, Mapping):
                reconciled.append(raw)
                continue
            item = dict(raw)
            if (
                xdex_program_complete
                and item.get("code") == "activity_window_asset_scope_not_proven"
            ):
                item = {
                    "code": "activity_window_all_x1_dex_scope_not_proven",
                    "message": (
                        "Direct X1 RPC evidence proves the requested window across "
                        "every structurally verified pool state in the verified XDEX "
                        "program for this asset. All-X1 DEX completeness remains "
                        "unproven because the AMM-program registry is not independently "
                        "known to be globally exhaustive."
                    ),
                }
                replaced_scope_warning = True
            reconciled.append(item)

        if xdex_program_complete and not replaced_scope_warning:
            reconciled.append({
                "code": "activity_window_all_x1_dex_scope_not_proven",
                "message": (
                    "The requested window is complete for the verified XDEX program "
                    "pool set, but all-X1 DEX completeness remains unproven because "
                    "the AMM-program registry is not independently known to be "
                    "globally exhaustive."
                ),
            })
        elif not xdex_program_complete:
            reconciled.append({
                "code": "verified_xdex_program_window_not_complete",
                "message": (
                    "The verified XDEX program pool set or one of its requested "
                    "address-history ranges was not fully proven, so program-scoped "
                    "window completeness was not promoted."
                ),
            })
        response["warnings"] = reconciled

        return response

    def dispatch(self, request: Any):
        if not isinstance(request, Mapping):
            return super().dispatch(request)

        service = (_text(request.get("service")) or "").lower()
        if service != VERIFIED_ASSET_ACTIVITY_SERVICE:
            return super().dispatch(request)

        params = request.get("params", {})
        if not isinstance(params, Mapping):
            return super().dispatch(request)

        raw_scope = params.get(SCOPE_PARAM)
        if raw_scope is None or raw_scope is False:
            return super().dispatch(request)
        if raw_scope is not True:
            return self._gateway_error(
                VERIFIED_ASSET_ACTIVITY_SERVICE,
                "x1",
                "invalid_activity_bound",
                f"{SCOPE_PARAM} must be a boolean",
            )

        chain = (_text(request.get("chain")) or "").lower()
        if chain != "x1":
            return super().dispatch(request)

        if params.get("chain_window") is not True:
            return self._gateway_error(
                VERIFIED_ASSET_ACTIVITY_SERVICE,
                "x1",
                "verified_xdex_program_scope_requires_chain_window",
                (
                    f"{SCOPE_PARAM}=true requires chain_window=true and one "
                    "supported window: 1h, 6h, or 24h."
                ),
            )

        # Build the normal provider-backed response without running the legacy
        # selected-provider-pool chain scan. The scoped scan below replaces only
        # that chain-window portion; provider market/history behavior is unchanged.
        base_params = dict(params)
        base_params.pop(SCOPE_PARAM, None)
        base_params["chain_window"] = False
        base_request = dict(request)
        base_request["params"] = base_params
        response = super().dispatch(base_request)
        if not isinstance(response, dict) or response.get("status") == "error":
            return response

        asset = response.get("asset")
        asset = asset if isinstance(asset, Mapping) else {}
        asset_mint = _text(asset.get("mint"))
        if not asset_mint:
            return self._scope_failure(
                response,
                "Verified XDEX program scope could not resolve a canonical asset mint.",
            )

        data = response.get("data")
        data = data if isinstance(data, Mapping) else {}
        window = data.get("activity_window")
        window = window if isinstance(window, Mapping) else {}
        start_epoch = _iso_epoch(window.get("start_utc"))
        end_epoch = _iso_epoch(window.get("end_utc"))
        if start_epoch is None or end_epoch is None:
            return self._scope_failure(
                response,
                "Verified XDEX program scope requires a valid requested activity window.",
            )

        catalog, failure = self._collect_x1_catalog(
            VERIFIED_ASSET_ACTIVITY_SERVICE
        )
        if failure is not None:
            return self._scope_failure(
                response,
                "The XDEX catalog could not be collected for program-scope verification.",
            )

        resolver = (
            getattr(self, "x1_verified_program_pool_set_resolver", None)
            or verify_recognized_program_asset_pool_set
        )
        try:
            pool_set = resolver(
                asset_mint=asset_mint,
                catalog_pools=catalog.get("pools") or [],
                rpc_url=self.x1_trade_rpc_url,
            )
        except Exception as exc:
            return self._scope_failure(
                response,
                (
                    "Verified XDEX program pool-set resolution failed closed: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        pool_summary = pool_set.get("summary")
        pool_summary = pool_summary if isinstance(pool_summary, Mapping) else {}
        if pool_summary.get(
            "recognized_program_asset_pool_set_structurally_verified"
        ) is not True:
            return self._scope_failure(
                response,
                "The complete target-mint pool-state set was not structurally verified for the XDEX program.",
                pool_set=pool_set,
            )

        pools = pool_set.get("pools") or []
        enumerator = (
            getattr(self, "x1_chain_window_enumerator", None)
            or enumerate_chain_window_dex_activity
        )
        try:
            activity = enumerator(
                asset_mint=asset_mint,
                pools=pools,
                start_epoch=start_epoch,
                end_epoch=end_epoch,
                rpc_url=self.x1_trade_rpc_url,
                page_size=self._bounded_positive_int(
                    "chain_page_size",
                    params.get("chain_page_size"),
                    default=1000,
                    maximum=1000,
                ),
                max_signatures_per_pool=self._bounded_positive_int(
                    "chain_max_signatures_per_pool",
                    params.get("chain_max_signatures_per_pool"),
                    default=1000,
                    maximum=5000,
                ),
            )
        except Exception as exc:
            return self._scope_failure(
                response,
                (
                    "Verified XDEX program chain-window enumeration failed closed: "
                    f"{type(exc).__name__}: {exc}"
                ),
                pool_set=pool_set,
            )

        # Reuse the existing selected-pool reconciliation first, then add the
        # narrower but stronger verified-program completion semantics.
        response = self._attach_chain_window_activity(response, activity)
        response = self._attach_program_scope(response, pool_set, activity)
        return response


__all__ = [
    "SCOPE_BASIS",
    "SCOPE_NAME",
    "SCOPE_PARAM",
    "VERSION",
    "VerifiedXDEXProgramScopeMixin",
]
