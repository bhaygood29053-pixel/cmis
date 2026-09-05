"""X1 Explorer source boundary for CMIS Web Discovery."""

from __future__ import annotations

from .base import CMISWebDiscoveryProvider, WebDiscoverySource


X1_EXPLORER_SOURCE = WebDiscoverySource(
    source_id="x1_explorer",
    source_name="X1 Explorer",
    source_role="official_explorer_discovery",
    base_urls=("https://explorer.mainnet.x1.xyz/",),
    allowed_hosts=("explorer.mainnet.x1.xyz",),
)


class X1ExplorerDiscoveryProvider(CMISWebDiscoveryProvider):
    source = X1_EXPLORER_SOURCE


__all__ = ["X1_EXPLORER_SOURCE", "X1ExplorerDiscoveryProvider"]
