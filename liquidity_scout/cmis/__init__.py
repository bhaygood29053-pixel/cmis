"""External access boundary for Cross-Chain Market Intelligence Service.

This package exposes CMIS to external specialist consumers such as X1 Scout
and Solana Scout. It is intentionally above provider modules: external clients
send chain-aware service requests and never receive provider objects or
provider credentials.
"""

from .assets import (
    AssetRegistry,
    DEFAULT_ASSET_DEFINITIONS,
    DEFAULT_ASSET_REGISTRY,
)
from .gateway import (
    KNOWN_CHAINS,
    SUPPORTED_CHAINS,
)
from .verification_gateway import (
    CMISGateway,
    SUPPORTED_SERVICES,
)

__all__ = [
    "AssetRegistry",
    "CMISGateway",
    "DEFAULT_ASSET_DEFINITIONS",
    "DEFAULT_ASSET_REGISTRY",
    "KNOWN_CHAINS",
    "SUPPORTED_CHAINS",
    "SUPPORTED_SERVICES",
]
