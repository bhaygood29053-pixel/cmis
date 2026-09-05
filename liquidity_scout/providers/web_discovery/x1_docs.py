"""Official X1 documentation source boundary for CMIS Web Discovery."""

from __future__ import annotations

from .base import CMISWebDiscoveryProvider, WebDiscoverySource


X1_DOCS_SOURCE = WebDiscoverySource(
    source_id="x1_docs",
    source_name="X1 Docs",
    source_role="official_documentation_discovery",
    base_urls=(
        "https://docs.x1.xyz/",
        "https://next.x1.xyz/",
    ),
    allowed_hosts=(
        "docs.x1.xyz",
        "next.x1.xyz",
    ),
)


class X1DocsDiscoveryProvider(CMISWebDiscoveryProvider):
    source = X1_DOCS_SOURCE


__all__ = ["X1_DOCS_SOURCE", "X1DocsDiscoveryProvider"]
