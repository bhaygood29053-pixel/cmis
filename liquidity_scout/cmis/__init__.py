"""Public boundary for Cross-Chain Market Intelligence Service.

The public repository owns the stable service/chain identifiers and integration
adapter. Protected CMIS implementation is supplied only by the required
``cmis-private-core`` package. Importing this public package never reconstructs
or eagerly imports protected implementation.
"""

from __future__ import annotations

from liquidity_scout.cmis_private_core import (
    PrivateCoreUnavailable,
    load_runtime_contract,
)

# Stable public identifiers accepted by Chain Scouts. Detailed capability and
# evidence metadata is assembled in deployments where the private runtime is
# installed; the public shell does not embed the protected evidence registry.
SUPPORTED_SERVICES = (
    "asset_lookup",
    "market_report",
    "rank",
    "historical_compare",
    "tokenomics",
    "burn_intelligence",
    "discovery_intelligence",
    "risk_check",
    "pre_trade_check",
    "trade_verification",
    "verified_asset_activity",
    "trade_price_impact_intelligence",
    "large_trade_discovery",
    "instant_x1_scan",
    "verification_evidence",
    "concentration_change_intelligence",
    "concentration_warning_intelligence",
    "bridge_to_xdex_utilization",
    "cross_chain_asset_provenance",
)
SUPPORTED_CHAINS = ("x1",)
KNOWN_CHAINS = ("x1", "solana")


def __getattr__(name: str):
    """Resolve legacy implementation symbols only through the private core."""
    if name == "CMISGateway":
        return load_runtime_contract()["gateway_class"]
    if name in {
        "AssetRegistry",
        "DEFAULT_ASSET_DEFINITIONS",
        "DEFAULT_ASSET_REGISTRY",
    }:
        try:
            from . import assets as private_assets
        except (ImportError, ModuleNotFoundError) as exc:
            raise PrivateCoreUnavailable(
                "cmis-private-core is required but is not installed."
            ) from exc
        return getattr(private_assets, name)
    raise AttributeError(name)


__all__ = [
    "AssetRegistry",
    "CMISGateway",
    "DEFAULT_ASSET_DEFINITIONS",
    "DEFAULT_ASSET_REGISTRY",
    "KNOWN_CHAINS",
    "SUPPORTED_CHAINS",
    "SUPPORTED_SERVICES",
]
