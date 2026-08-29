"""Public boundary for Cross-Chain Market Intelligence Service.

The public repository owns capability contracts and transport. Protected CMIS
implementation is supplied only by the required ``cmis-private-core`` package.
This module intentionally avoids importing protected implementation eagerly so
the public shell remains importable and can fail closed when the private core is
not installed.
"""

from __future__ import annotations

from .capabilities import (
    PUBLIC_KNOWN_CHAINS,
    PUBLIC_RUNTIME_SERVICES,
    PUBLIC_SUPPORTED_CHAINS,
)
from liquidity_scout.cmis_private_core import (
    PrivateCoreUnavailable,
    load_runtime_contract,
)

KNOWN_CHAINS = PUBLIC_KNOWN_CHAINS
SUPPORTED_CHAINS = PUBLIC_SUPPORTED_CHAINS
SUPPORTED_SERVICES = PUBLIC_RUNTIME_SERVICES


def __getattr__(name: str):
    """Resolve legacy implementation symbols only through the private core."""
    if name == "CMISGateway":
        return load_runtime_contract()["gateway_class"]
    if name in {
        "AssetRegistry",
        "DEFAULT_ASSET_DEFINITIONS",
        "DEFAULT_ASSET_REGISTRY",
    }:
        # The private distribution supplies ``liquidity_scout.cmis.assets``.
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
