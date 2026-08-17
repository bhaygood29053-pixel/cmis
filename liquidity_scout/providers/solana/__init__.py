"""Solana provider namespace beneath CMIS.

The live Solana provider is intentionally not configured yet. This placeholder
makes that state explicit without exposing fake market data or falling back to
X1 provider implementations.
"""

from dataclasses import dataclass

CHAIN = "solana"


@dataclass(frozen=True, slots=True)
class SolanaProviderPlaceholder:
    """Known-chain marker used until verified Solana provider components exist."""

    chain: str = CHAIN
    configured: bool = False
    reason: str = (
        "Solana provider components are not configured. Contract tests and "
        "read-only live verification are required before promotion."
    )


UNCONFIGURED_SOLANA_PROVIDER = SolanaProviderPlaceholder()

__all__ = [
    "CHAIN",
    "SolanaProviderPlaceholder",
    "UNCONFIGURED_SOLANA_PROVIDER",
]
