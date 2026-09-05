"""XDEX web/API source boundary for CMIS Web Discovery."""

from __future__ import annotations

from .base import CMISWebDiscoveryProvider, WebDiscoverySource


XDEX_WEB_SOURCE = WebDiscoverySource(
    source_id="xdex",
    source_name="XDEX",
    source_role="protocol_native_web_api_discovery",
    base_urls=(
        "https://xdexdocs.gitbook.io/xdex/",
        "https://api.xdex.xyz/",
    ),
    allowed_hosts=(
        "xdexdocs.gitbook.io",
        "api.xdex.xyz",
    ),
)


class XDEXWebDiscoveryProvider(CMISWebDiscoveryProvider):
    source = XDEX_WEB_SOURCE


__all__ = ["XDEX_WEB_SOURCE", "XDEXWebDiscoveryProvider"]
