"""Machine-readable CMIS capability contract for external Chain Scouts.

This module is the CMIS-side source of truth for *service eligibility*.  It does
not claim that a provider is healthy, that a requested asset is available, or
that a service will return ``ok`` for every request.  Those remain runtime
facts expressed by the normal CMIS service envelope.

The contract intentionally sits between Chain Scouts and CMIS.  Roberta does
not need to call or understand this endpoint directly.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping


CAPABILITY_SCHEMA_VERSION = 1
CMIS_CONTRACT_VERSION = "1.6.0"
CAPABILITY_STATES = frozenset({"supported", "bounded", "partial", "unavailable"})


def _capability(
    state: str,
    *,
    requirements: Iterable[str] = (),
    limitations: Iterable[str] = (),
) -> dict[str, Any]:
    if state not in CAPABILITY_STATES:
        raise ValueError(f"Unsupported CMIS capability state: {state!r}")
    return {
        "state": state,
        "callable": state != "unavailable",
        "requirements": list(requirements),
        "limitations": list(limitations),
    }


# Every runtime-advertised service must appear for every known chain.  This is
# deliberately explicit: adding a runtime service without classifying its chain
# eligibility should fail contract validation instead of silently reaching a
# Scout with an ambiguous capability boundary.
_CHAIN_SERVICE_CAPABILITIES: dict[str, dict[str, dict[str, Any]]] = {
    "x1": {
        "asset_lookup": _capability("supported"),
        "market_report": _capability("supported"),
        "rank": _capability("supported"),
        "historical_compare": _capability("supported"),
        "tokenomics": _capability("supported"),
        "risk_check": _capability("supported"),
        "pre_trade_check": _capability(
            "bounded",
            limitations=(
                "analysis_only",
                "execution_authorized_false",
                "slippage_unavailable",
                "price_impact_unavailable",
                "route_quality_unavailable",
                "fees_unavailable",
                "transaction_simulation_unavailable",
            ),
        ),
        "trade_verification": _capability(
            "bounded",
            requirements=("provider_trade_event", "x1_rpc_verification"),
            limitations=("recognized_xdex_program_scope",),
        ),
        "verified_asset_activity": _capability(
            "bounded",
            limitations=(
                "selected_pool_scope_may_be_smaller_than_asset_scope",
                "asset_wide_completeness_fails_closed",
            ),
        ),
        "verification_evidence": _capability(
            "bounded",
            requirements=("exact_evidence_id_or_fact_type_subject_id",),
            limitations=("read_only_persisted_evidence_lookup",),
        ),
    },
    "solana": {
        "asset_lookup": _capability(
            "bounded",
            requirements=("exact_mint", "solana_rpc_provider_configured"),
            limitations=("symbol_name_discovery_unavailable",),
        ),
        "market_report": _capability(
            "partial",
            requirements=(
                "exact_mint",
                "solana_rpc_provider_configured",
                "jupiter_price_v3_provider_configured",
                "dexscreener_provider_configured",
                "explicit_cross_source_price_tolerance",
            ),
            limitations=(
                "cross_source_price_agreement_not_canonical_price",
                "asset_wide_liquidity_unverified",
                "asset_wide_volume_unverified",
                "shared_absolute_freshness_unverified",
            ),
        ),
        "rank": _capability(
            "unavailable",
            limitations=("solana_asset_ranking_not_implemented",),
        ),
        "historical_compare": _capability(
            "partial",
            requirements=(
                "exact_mint",
                "jupiter_price_v3_source",
                "price_usd_metric",
                "solana_observation_ledger_configured",
                "deployment_history_distance_policy",
            ),
            limitations=(
                "jupiter_price_v3_history_only",
                "absolute_price_freshness_unverified",
                "dex_pair_history_unavailable",
            ),
        ),
        "tokenomics": _capability(
            "partial",
            requirements=("exact_mint", "solana_rpc_provider_configured"),
            limitations=(
                "circulating_supply_unavailable",
                "maximum_supply_unavailable",
                "lifetime_mint_burn_coverage_unavailable",
            ),
        ),
        "risk_check": _capability(
            "partial",
            requirements=("exact_mint",),
            limitations=(
                "asset_wide_market_inputs_incomplete",
                "bounded_mint_burn_activity_unavailable",
                "historical_risk_inputs_incomplete",
            ),
        ),
        "pre_trade_check": _capability(
            "unavailable",
            limitations=("solana_pre_trade_not_implemented",),
        ),
        "trade_verification": _capability(
            "unavailable",
            limitations=("solana_trade_verification_not_implemented",),
        ),
        "verified_asset_activity": _capability(
            "unavailable",
            limitations=("solana_verified_asset_activity_not_implemented",),
        ),
        "verification_evidence": _capability(
            "unavailable",
            limitations=("solana_persisted_verification_lookup_not_promoted",),
        ),
    },
}


def _normalized(values: Iterable[object]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip().lower()
        if text and text not in result:
            result.append(text)
    return tuple(result)


def validate_capability_contract(
    *,
    runtime_services: Iterable[object],
    known_chains: Iterable[object],
) -> None:
    """Fail loudly when runtime services/chains drift from the manifest."""

    services = set(_normalized(runtime_services))
    chains = set(_normalized(known_chains))
    manifest_chains = set(_CHAIN_SERVICE_CAPABILITIES)
    if chains != manifest_chains:
        raise RuntimeError(
            "CMIS capability contract chain drift: runtime/known chains do not "
            f"match the manifest ({sorted(chains)!r} != {sorted(manifest_chains)!r})."
        )

    for chain, capabilities in _CHAIN_SERVICE_CAPABILITIES.items():
        capability_services = set(capabilities)
        if capability_services != services:
            missing = sorted(services - capability_services)
            extra = sorted(capability_services - services)
            raise RuntimeError(
                "CMIS capability contract service drift for "
                f"{chain}: missing={missing!r}, extra={extra!r}."
            )
        for service, capability in capabilities.items():
            state = capability.get("state")
            callable_flag = capability.get("callable")
            if state not in CAPABILITY_STATES:
                raise RuntimeError(
                    f"CMIS capability {chain}/{service} has invalid state {state!r}."
                )
            if callable_flag is not (state != "unavailable"):
                raise RuntimeError(
                    f"CMIS capability {chain}/{service} has inconsistent callable flag."
                )


def build_capability_manifest(
    *,
    runtime_services: Iterable[object],
    legacy_supported_chains: Iterable[object],
    known_chains: Iterable[object],
    request_path: str = "/v1/cmis",
) -> dict[str, Any]:
    """Return a fresh JSON-safe capability manifest for Chain Scouts.

    ``legacy_supported_chains`` is retained because the original HTTP contract
    exposed the base gateway's fully supported chain list.  Chain-specific
    runtime mixins can now expose narrower capabilities for other known chains,
    so consumers should use ``chains[*].services`` for eligibility decisions.
    """

    runtime_services = _normalized(runtime_services)
    known_chains = _normalized(known_chains)
    legacy_supported_chains = _normalized(legacy_supported_chains)
    validate_capability_contract(
        runtime_services=runtime_services,
        known_chains=known_chains,
    )

    chains: dict[str, Any] = {}
    for chain in known_chains:
        services = deepcopy(_CHAIN_SERVICE_CAPABILITIES[chain])
        chains[chain] = {
            "services": services,
            "callable_services": [
                service
                for service in runtime_services
                if services[service]["callable"] is True
            ],
        }

    return {
        "service": "cmis_gateway",
        "schema_version": CAPABILITY_SCHEMA_VERSION,
        "contract_version": CMIS_CONTRACT_VERSION,
        "request_path": request_path,
        # Backward-compatible flat fields.  New Scouts should consume the
        # chain-specific service table above.
        "supported_services": list(runtime_services),
        "supported_chains": list(legacy_supported_chains),
        "known_chains": list(known_chains),
        "chains": chains,
    }


def service_capability(
    manifest: Mapping[str, Any],
    *,
    chain: str,
    service: str,
) -> Mapping[str, Any] | None:
    """Read one capability record from a manifest without guessing defaults."""

    chains = manifest.get("chains")
    if not isinstance(chains, Mapping):
        return None
    chain_record = chains.get(str(chain or "").strip().lower())
    if not isinstance(chain_record, Mapping):
        return None
    services = chain_record.get("services")
    if not isinstance(services, Mapping):
        return None
    capability = services.get(str(service or "").strip().lower())
    return capability if isinstance(capability, Mapping) else None


__all__ = [
    "CAPABILITY_SCHEMA_VERSION",
    "CAPABILITY_STATES",
    "CMIS_CONTRACT_VERSION",
    "build_capability_manifest",
    "service_capability",
    "validate_capability_contract",
]
