"""Provider-neutral chain/component registry beneath CMIS.

This module is deliberately small. It does not collect market data and it does
not replace the existing X1 provider implementations. It only resolves an
explicit ``chain + component`` request to a configured provider object or a
fail-closed availability result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from liquidity_scout.providers.solana import UNCONFIGURED_SOLANA_PROVIDER
from liquidity_scout.providers.x1.market import X1Provider
from liquidity_scout.providers.x1.supply import X1SupplyProvider

ProviderResolutionStatus = Literal["selected", "unavailable", "unknown_chain"]

KNOWN_CHAINS = ("x1", "solana")
KNOWN_COMPONENTS = (
    "rpc",
    "market",
    "supply",
    "indexer",
    "dex",
    "security",
    "history",
    "streaming",
)


def _normalized(value: object, *, field: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        raise ValueError(f"{field} must not be empty")
    return text


@dataclass(frozen=True, slots=True)
class ProviderResolution:
    """Deterministic provider selection result with no live-health inference."""

    status: ProviderResolutionStatus
    chain: str
    component: str
    provider: object | None
    reason: str


class ChainProviderRegistry:
    """Resolve configured chain-provider components without cross-chain fallback."""

    def __init__(self, *, known_chains: tuple[str, ...] = KNOWN_CHAINS) -> None:
        normalized = tuple(_normalized(chain, field="chain") for chain in known_chains)
        if len(set(normalized)) != len(normalized):
            raise ValueError("known_chains must not contain duplicates")
        self._known_chains = frozenset(normalized)
        self._providers: dict[tuple[str, str], object] = {}
        self._unavailable_reasons: dict[str, str] = {}

    def mark_chain_unavailable(self, chain: str, *, reason: str) -> None:
        normalized_chain = _normalized(chain, field="chain")
        if normalized_chain not in self._known_chains:
            raise ValueError(f"cannot mark unknown chain unavailable: {normalized_chain}")
        normalized_reason = str(reason or "").strip()
        if not normalized_reason:
            raise ValueError("reason must not be empty")
        self._unavailable_reasons[normalized_chain] = normalized_reason

    def register(self, *, chain: str, component: str, provider: object) -> None:
        normalized_chain = _normalized(chain, field="chain")
        normalized_component = _normalized(component, field="component")
        if normalized_chain not in self._known_chains:
            raise ValueError(f"cannot register provider for unknown chain: {normalized_chain}")
        if normalized_component not in KNOWN_COMPONENTS:
            raise ValueError(f"unsupported provider component: {normalized_component}")
        if provider is None:
            raise TypeError("provider must not be None")

        provider_chain = getattr(provider, "chain", None)
        if provider_chain is not None:
            provider_chain = _normalized(provider_chain, field="provider.chain")
            if provider_chain != normalized_chain:
                raise ValueError(
                    f"provider chain mismatch: expected {normalized_chain}, got {provider_chain}"
                )

        key = (normalized_chain, normalized_component)
        if key in self._providers:
            raise ValueError(
                f"provider already registered for {normalized_chain}/{normalized_component}"
            )
        self._providers[key] = provider

    def resolve(self, *, chain: str, component: str) -> ProviderResolution:
        normalized_chain = _normalized(chain, field="chain")
        normalized_component = _normalized(component, field="component")
        if normalized_component not in KNOWN_COMPONENTS:
            raise ValueError(f"unsupported provider component: {normalized_component}")

        if normalized_chain not in self._known_chains:
            return ProviderResolution(
                status="unknown_chain",
                chain=normalized_chain,
                component=normalized_component,
                provider=None,
                reason="chain is not registered in the CMIS provider registry",
            )

        provider = self._providers.get((normalized_chain, normalized_component))
        if provider is not None:
            return ProviderResolution(
                status="selected",
                chain=normalized_chain,
                component=normalized_component,
                provider=provider,
                reason="configured provider component selected",
            )

        reason = self._unavailable_reasons.get(
            normalized_chain,
            "known chain provider component is not configured",
        )
        return ProviderResolution(
            status="unavailable",
            chain=normalized_chain,
            component=normalized_component,
            provider=None,
            reason=reason,
        )


def build_default_chain_provider_registry(
    *,
    x1_market_provider: object | None = None,
    x1_supply_provider: object | None = None,
    solana_rpc_provider: object | None = None,
) -> ChainProviderRegistry:
    """Return the current provider registry with Solana opt-in by component.

    X1 uses its existing provider classes. Solana is a known chain and remains
    unavailable by default. A verified/read-only Solana RPC adapter may be
    injected explicitly without enabling market/indexer/DEX/security components.
    """

    registry = ChainProviderRegistry()
    registry.register(
        chain="x1",
        component="market",
        provider=x1_market_provider or X1Provider(),
    )
    registry.register(
        chain="x1",
        component="supply",
        provider=x1_supply_provider or X1SupplyProvider(),
    )
    registry.mark_chain_unavailable(
        "solana",
        reason=UNCONFIGURED_SOLANA_PROVIDER.reason,
    )
    if solana_rpc_provider is not None:
        registry.register(
            chain="solana",
            component="rpc",
            provider=solana_rpc_provider,
        )
    return registry


__all__ = [
    "ChainProviderRegistry",
    "KNOWN_CHAINS",
    "KNOWN_COMPONENTS",
    "ProviderResolution",
    "ProviderResolutionStatus",
    "build_default_chain_provider_registry",
]
