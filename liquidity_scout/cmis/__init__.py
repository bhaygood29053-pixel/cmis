"""External access boundary for Cross-Chain Market Intelligence Service.

This package exposes CMIS to external specialist consumers such as X1 Scout
and Solana Scout. It is intentionally above provider modules: external clients
send chain-aware service requests and never receive provider objects or
provider credentials.
"""

from .gateway import (
    KNOWN_CHAINS,
    SUPPORTED_CHAINS,
    SUPPORTED_SERVICES,
    CMISGateway,
)

__all__ = [
    "CMISGateway",
    "KNOWN_CHAINS",
    "SUPPORTED_CHAINS",
    "SUPPORTED_SERVICES",
]
