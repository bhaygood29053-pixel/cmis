"""Narrow Solana market-report gateway layer for CMIS.

The first promoted Solana market slice requires exact mint identity plus both
accepted read-only market sources: Jupiter Price V3 and DEX Screener token-pair
observations. A deployment must also provide an explicit cross-source price
tolerance. Numerical agreement remains non-promotable because shared freshness
and observation scope are not yet verified.

No pair is selected as canonical, no pair prices are averaged, and pair-scoped
liquidity/volume are never promoted to Solana-wide asset aggregates.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from liquidity_scout.cmis.evidence import AGREEMENT, CONFLICT, INSUFFICIENT_EVIDENCE
from liquidity_scout.providers.solana.dexscreener import DexScreenerSourceError
from liquidity_scout.providers.solana.jupiter import JupiterSourceError
from liquidity_scout.providers.solana.market_verification import (
    verify_jupiter_vs_dexscreener_prices,
)
from liquidity_scout.services.cmis_contract import (
    ERROR,
    PARTIAL,
    UNAVAILABLE,
    build_service_envelope,
)

SERVICE = "market_report"
CHAIN = "solana"


def _tolerance(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(
            "solana_price_max_relative_difference must be numeric in [0, 1] or null"
        )
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            "solana_price_max_relative_difference must be numeric in [0, 1] or null"
        ) from exc
    if not parsed.is_finite() or parsed < 0 or parsed > 1:
        raise ValueError(
            "solana_price_max_relative_difference must be between 0 and 1 inclusive"
        )
    text = format(parsed, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _pair_observations(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    pairs = record.get("pairs")
    if not isinstance(pairs, list):
        return []
    observations: list[dict[str, Any]] = []
    for pair in pairs:
        if not isinstance(pair, Mapping):
            continue
        volume = pair.get("volume")
        transactions = pair.get("transactions")
        price_change = pair.get("price_change")
        observations.append(
            {
                "pair_address": pair.get("pair_address"),
                "dex_id": pair.get("dex_id"),
                "requested_mint_role": pair.get("requested_mint_role"),
                "price_subject_address": pair.get("price_subject_address"),
                "price_is_for_requested_mint": pair.get(
                    "price_is_for_requested_mint"
                ),
                "base_token_price_usd": pair.get("price_usd"),
                "liquidity_usd": pair.get("liquidity_usd"),
                "volume_24h": (
                    volume.get("h24") if isinstance(volume, Mapping) else None
                ),
                "transactions_24h": (
                    transactions.get("h24")
                    if isinstance(transactions, Mapping)
                    else None
                ),
                "price_change_24h_percent": (
                    price_change.get("h24")
                    if isinstance(price_change, Mapping)
                    else None
                ),
                "pair_created_at_ms": pair.get("pair_created_at_ms"),
            }
        )
    return observations


class SolanaMarketReportMixin:
    """Cooperative CMIS mixin for exact-mint Solana market evidence."""

    def __init__(
        self,
        *,
        solana_jupiter_provider: Any = None,
        solana_dexscreener_provider: Any = None,
        solana_price_max_relative_difference: object = None,
        **kwargs: Any,
    ):
        self.solana_jupiter_provider = solana_jupiter_provider
        self.solana_dexscreener_provider = solana_dexscreener_provider
        self.solana_price_max_relative_difference = _tolerance(
            solana_price_max_relative_difference
        )
        super().__init__(**kwargs)

    def _solana_market_error(self, code: str, message: str):
        return build_service_envelope(
            SERVICE,
            CHAIN,
            ERROR,
            errors=[{"code": code, "message": message}],
        )

    def _solana_market_unavailable(self, code: str, message: str):
        return build_service_envelope(
            SERVICE,
            CHAIN,
            UNAVAILABLE,
            warnings=[{"code": code, "message": message}],
        )

    def _solana_market_report(self, asset: Any):
        identity = self._solana_asset_lookup(asset)
        if not isinstance(identity, Mapping):
            return self._solana_market_error(
                "solana_asset_lookup_contract_invalid",
                "The Solana asset-identity prerequisite returned a malformed result.",
            )
        if identity.get("status") != "ok":
            return self._propagate_upstream(SERVICE, identity)

        identity_asset = identity.get("asset")
        if not isinstance(identity_asset, Mapping):
            return self._solana_market_error(
                "solana_asset_lookup_contract_invalid",
                "The verified Solana asset-identity prerequisite is incomplete.",
            )
        mint = identity_asset.get("mint")
        if not isinstance(mint, str) or not mint:
            return self._solana_market_error(
                "solana_asset_lookup_contract_invalid",
                "The verified Solana asset identity contains no exact mint.",
            )

        if self.solana_jupiter_provider is None:
            return self._solana_market_unavailable(
                "solana_jupiter_provider_not_configured",
                "Jupiter Price V3 is not configured for the Solana market report.",
            )
        if self.solana_dexscreener_provider is None:
            return self._solana_market_unavailable(
                "solana_dexscreener_provider_not_configured",
                "DEX Screener is not configured for the Solana market report.",
            )
        tolerance = self.solana_price_max_relative_difference
        if tolerance is None:
            return self._solana_market_unavailable(
                "solana_price_crosscheck_policy_not_configured",
                (
                    "No explicit maximum relative price difference is configured; "
                    "market providers were not queried."
                ),
            )

        try:
            jupiter = self.solana_jupiter_provider.get_price(mint)
        except JupiterSourceError as exc:
            return self._solana_market_unavailable(
                "solana_jupiter_price_unavailable",
                f"Jupiter price collection failed ({type(exc).__name__}).",
            )
        except Exception as exc:
            return self._solana_market_unavailable(
                "solana_jupiter_price_failed_closed",
                f"Jupiter price collection failed ({type(exc).__name__}).",
            )

        try:
            dexscreener = self.solana_dexscreener_provider.get_token_pairs(mint)
        except DexScreenerSourceError as exc:
            return self._solana_market_unavailable(
                "solana_dexscreener_pairs_unavailable",
                f"DEX Screener pair collection failed ({type(exc).__name__}).",
            )
        except Exception as exc:
            return self._solana_market_unavailable(
                "solana_dexscreener_pairs_failed_closed",
                f"DEX Screener pair collection failed ({type(exc).__name__}).",
            )

        try:
            crosscheck = verify_jupiter_vs_dexscreener_prices(
                jupiter,
                dexscreener,
                max_relative_difference=tolerance,
            )
        except (TypeError, ValueError) as exc:
            return self._solana_market_error(
                "solana_price_crosscheck_contract_invalid",
                f"Solana price cross-check failed ({type(exc).__name__}).",
            )
        except Exception as exc:
            return self._solana_market_error(
                "solana_price_crosscheck_failed_closed",
                f"Solana price cross-check failed ({type(exc).__name__}).",
            )

        if not isinstance(crosscheck, Mapping):
            return self._solana_market_error(
                "solana_price_crosscheck_contract_invalid",
                "The Solana price cross-check returned a malformed result.",
            )

        crosscheck_status = crosscheck.get("status")
        if crosscheck_status not in {
            AGREEMENT,
            CONFLICT,
            INSUFFICIENT_EVIDENCE,
        }:
            return self._solana_market_error(
                "solana_price_crosscheck_contract_invalid",
                "The Solana price cross-check returned an unknown evidence status.",
            )

        jupiter_mapping = jupiter if isinstance(jupiter, Mapping) else {}
        dex_mapping = dexscreener if isinstance(dexscreener, Mapping) else {}
        jupiter_price = (
            jupiter_mapping.get("usd_price")
            if jupiter_mapping.get("price_available") is True
            else None
        )
        pair_observations = _pair_observations(dex_mapping)

        warnings = [
            {
                "code": "solana_market_freshness_unverified",
                "message": (
                    "The accepted market sources do not yet establish shared "
                    "wall-clock freshness."
                ),
            },
            {
                "code": "solana_market_observation_scope_unverified",
                "message": (
                    "Jupiter and DEX Screener do not yet establish one shared "
                    "asset-wide observation scope."
                ),
            },
            {
                "code": "solana_asset_wide_liquidity_unverified",
                "message": (
                    "DEX Screener liquidity remains pair-scoped; no Solana-wide "
                    "asset liquidity total is claimed."
                ),
            },
            {
                "code": "solana_asset_wide_volume_unverified",
                "message": (
                    "DEX Screener volume remains pair-scoped; no Solana-wide "
                    "asset volume total is claimed."
                ),
            },
        ]
        if crosscheck_status == AGREEMENT:
            warnings.append(
                {
                    "code": "solana_price_agreement_not_promotable",
                    "message": (
                        "Jupiter and all eligible DEX Screener base-pair prices "
                        "agree within tolerance, but freshness/scope remain unverified."
                    ),
                }
            )
        elif crosscheck_status == CONFLICT:
            warnings.append(
                {
                    "code": "solana_price_cross_source_conflict",
                    "message": (
                        "At least one eligible DEX Screener base-pair price is outside "
                        "the configured tolerance from Jupiter."
                    ),
                }
            )
        else:
            warnings.append(
                {
                    "code": "solana_price_crosscheck_insufficient_evidence",
                    "message": (
                        "The configured cross-source price gate lacks enough eligible "
                        "evidence for agreement/conflict classification."
                    ),
                }
            )

        sources = list(identity.get("sources") or [])
        if isinstance(jupiter, Mapping):
            sources.append(
                {
                    "source": "jupiter_price_v3",
                    "role": "market_report.price_source",
                    "block_id": jupiter.get("block_id"),
                }
            )
        if isinstance(dexscreener, Mapping):
            sources.append(
                {
                    "source": "dexscreener_token_pairs_v1",
                    "role": "market_report.pair_observations",
                    "pair_count_observed": dexscreener.get("pair_count_observed"),
                }
            )

        checks = {
            "identity_verified": True,
            "price_semantics_verified": crosscheck.get("semantics_verified") is True,
            "price_cross_source_agreement": crosscheck_status == AGREEMENT,
            "price_freshness_verified": crosscheck.get("freshness_verified") is True,
            "observation_scope_verified": (
                crosscheck.get("observation_scope_verified") is True
            ),
            "asset_wide_liquidity_verified": False,
            "asset_wide_volume_verified": False,
        }
        verified_checks = sum(1 for value in checks.values() if value)

        status = (
            UNAVAILABLE
            if crosscheck_status == INSUFFICIENT_EVIDENCE
            else PARTIAL
        )
        return build_service_envelope(
            SERVICE,
            CHAIN,
            status,
            asset={"chain": CHAIN, "mint": mint},
            data={
                "mint": mint,
                "price_usd_source_value": jupiter_price,
                "price_source": (
                    "jupiter_price_v3" if jupiter_price is not None else None
                ),
                "price_verified": False,
                "price_crosscheck": dict(crosscheck),
                "pair_observations": pair_observations,
                "pair_count_observed": dex_mapping.get("pair_count_observed"),
                "asset_wide_liquidity_usd": None,
                "asset_wide_liquidity_verified": False,
                "asset_wide_volume_24h_usd": None,
                "asset_wide_volume_24h_verified": False,
                "transactions_24h": None,
                "transactions_24h_verified": False,
                "holders": None,
                "holders_verified": False,
            },
            confidence={
                "complete": False,
                "verified_checks": verified_checks,
                "total_checks": len(checks),
                "verification_ratio": round(verified_checks / len(checks), 6),
                "checks": checks,
            },
            sources=sources,
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
                if params:
                    return self._gateway_error(
                        SERVICE,
                        CHAIN,
                        "solana_market_report_params_not_supported",
                        (
                            "Solana market evidence policy is deployment-configured; "
                            "the external request accepts only an exact mint asset."
                        ),
                    )
                return self._solana_market_report(request.get("asset"))

        return super().dispatch(request)


__all__ = ["CHAIN", "SERVICE", "SolanaMarketReportMixin"]
