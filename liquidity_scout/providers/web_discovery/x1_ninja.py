"""X1.Ninja web/API source boundary for CMIS Web Discovery."""

from __future__ import annotations

from .base import CMISWebDiscoveryProvider, WebDiscoverySource


X1_NINJA_WEB_SOURCE = WebDiscoverySource(
    source_id="x1_ninja",
    source_name="X1.Ninja",
    source_role="third_party_indexer_web_api_discovery",
    base_urls=(
        "https://x1.ninja/",
        "https://api.x1.ninja/",
    ),
    allowed_hosts=(
        "x1.ninja",
        "api.x1.ninja",
    ),
)


class X1NinjaWebDiscoveryProvider(CMISWebDiscoveryProvider):
    source = X1_NINJA_WEB_SOURCE


__all__ = ["X1_NINJA_WEB_SOURCE", "X1NinjaWebDiscoveryProvider"]
