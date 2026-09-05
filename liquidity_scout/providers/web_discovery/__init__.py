"""CMIS Web Discovery provider framework.

The package exposes bounded source-specific collection only. Web observations
are candidate evidence and do not become verified CMIS facts by entering this
framework.
"""

from .base import (
    CMISWebDiscoveryProvider,
    CONTRACT,
    DISCOVERED,
    SourceBoundaryError,
    WebDiscoveryContentError,
    WebDiscoveryError,
    WebDiscoveryHTTPError,
    WebDiscoverySource,
)
from .github import GITHUB_WEB_SOURCE, GitHubWebDiscoveryProvider
from .registry import build_provider, provider_catalog, provider_ids
from .x1_docs import X1_DOCS_SOURCE, X1DocsDiscoveryProvider
from .x1_explorer import X1_EXPLORER_SOURCE, X1ExplorerDiscoveryProvider
from .x1_ninja import X1_NINJA_WEB_SOURCE, X1NinjaWebDiscoveryProvider
from .x1report import X1REPORT_SOURCE, X1ReportDiscoveryProvider
from .xdex import XDEX_WEB_SOURCE, XDEXWebDiscoveryProvider


__all__ = [
    "CMISWebDiscoveryProvider",
    "CONTRACT",
    "DISCOVERED",
    "GITHUB_WEB_SOURCE",
    "GitHubWebDiscoveryProvider",
    "SourceBoundaryError",
    "WebDiscoveryContentError",
    "WebDiscoveryError",
    "WebDiscoveryHTTPError",
    "WebDiscoverySource",
    "X1_DOCS_SOURCE",
    "X1_EXPLORER_SOURCE",
    "X1_NINJA_WEB_SOURCE",
    "X1REPORT_SOURCE",
    "XDEX_WEB_SOURCE",
    "X1DocsDiscoveryProvider",
    "X1ExplorerDiscoveryProvider",
    "X1NinjaWebDiscoveryProvider",
    "X1ReportDiscoveryProvider",
    "XDEXWebDiscoveryProvider",
    "build_provider",
    "provider_catalog",
    "provider_ids",
]
