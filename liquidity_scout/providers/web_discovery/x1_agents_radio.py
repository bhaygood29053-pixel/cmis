"""X1 Agents Radio source boundary for CMIS Web Discovery.

This provider exposes only bounded, read-only discovery against the public
machine-readable X1 Agents Radio surfaces. Provider-reported program names,
categories, instructions, activity, deployment status, upgrade labels, and
health state remain candidate metadata until separately verified by an accepted
CMIS/RPC/provider contract.

The legacy x1radio.vercel.app host currently redirects to x1agentsradio.xyz, so
both hosts are within the same source boundary. Host continuity does not prove
source independence.
"""

from __future__ import annotations

from urllib.parse import urlparse

from .base import (
    CMISWebDiscoveryProvider,
    SourceBoundaryError,
    WebDiscoverySource,
)


PUBLIC_DISCOVERY_PATHS = (
    "/api/bootstrap",
    "/api/catalog",
    "/api/deployments",
    "/api/health",
)

LEGACY_HOST = "x1radio.vercel.app"
CURRENT_HOST = "x1agentsradio.xyz"


X1_AGENTS_RADIO_SOURCE = WebDiscoverySource(
    source_id="x1_agents_radio",
    source_name="X1 Agents Radio",
    source_role="third_party_x1_agent_registry_web_api_discovery",
    base_urls=tuple(
        f"https://{host}{path}"
        for host in (LEGACY_HOST, CURRENT_HOST)
        for path in PUBLIC_DISCOVERY_PATHS
    ),
    allowed_hosts=(LEGACY_HOST, CURRENT_HOST),
)


def validate_x1_agents_radio_public_url(url: str) -> str:
    """Accept only the documented unauthenticated discovery GET surfaces."""

    normalized = X1_AGENTS_RADIO_SOURCE.validate_url(url)
    parsed = urlparse(normalized)
    path = parsed.path.rstrip("/") or "/"

    if path not in PUBLIC_DISCOVERY_PATHS:
        raise SourceBoundaryError(
            "X1 Agents Radio discovery is restricted to the documented "
            f"public GET surfaces; path={path!r}"
        )
    if parsed.query:
        raise SourceBoundaryError(
            "X1 Agents Radio public discovery endpoints do not accept "
            "query-bearing URLs in this CMIS adapter"
        )
    return normalized


class X1AgentsRadioDiscoveryProvider(CMISWebDiscoveryProvider):
    source = X1_AGENTS_RADIO_SOURCE

    def discover_url(self, url=None, *, query=None):
        target = validate_x1_agents_radio_public_url(
            url or self.source.default_url
        )
        return super().discover_url(target, query=query)


__all__ = [
    "CURRENT_HOST",
    "LEGACY_HOST",
    "PUBLIC_DISCOVERY_PATHS",
    "X1_AGENTS_RADIO_SOURCE",
    "X1AgentsRadioDiscoveryProvider",
    "validate_x1_agents_radio_public_url",
]
