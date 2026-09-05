"""GitHub public-source boundary for CMIS Web Discovery.

This adapter is intentionally unauthenticated and read-only. Repository pages,
public API responses, and raw files are candidate implementation/documentation
evidence only. They are not live-chain truth.
"""

from __future__ import annotations

from .base import CMISWebDiscoveryProvider, WebDiscoverySource


GITHUB_WEB_SOURCE = WebDiscoverySource(
    source_id="github",
    source_name="GitHub",
    source_role="public_source_repository_discovery",
    base_urls=("https://github.com/",),
    allowed_hosts=(
        "github.com",
        "api.github.com",
        "raw.githubusercontent.com",
    ),
)


class GitHubWebDiscoveryProvider(CMISWebDiscoveryProvider):
    source = GITHUB_WEB_SOURCE


__all__ = ["GITHUB_WEB_SOURCE", "GitHubWebDiscoveryProvider"]
