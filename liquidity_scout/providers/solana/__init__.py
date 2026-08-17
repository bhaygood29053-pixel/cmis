"""Solana provider namespace beneath CMIS.

The live Solana market/indexer/DEX provider path remains intentionally disabled.
The read-only RPC adapter is available for deterministic contract testing and
future canonical-chain observations without promoting broader Solana services.
"""

from dataclasses import dataclass

from liquidity_scout.providers.solana.rpc import (
    SolanaRPCError,
    SolanaRPCNotFound,
    SolanaRPCProvider,
)

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
    "SolanaRPCError",
    "SolanaRPCNotFound",
    "SolanaRPCProvider",
    "UNCONFIGURED_SOLANA_PROVIDER",
]
