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
from .x1_explorer_network import (
    ALLOWED_TARGET_HOSTS as X1_EXPLORER_NETWORK_ALLOWED_TARGET_HOSTS,
    NETWORK_OBSERVATION_CONTRACT as X1_EXPLORER_NETWORK_OBSERVATION_CONTRACT,
    OFFICIAL_EXPLORER_HOST as X1_EXPLORER_NETWORK_OFFICIAL_HOST,
    READ_ONLY_RPC_METHODS as X1_EXPLORER_READ_ONLY_RPC_METHODS,
    list_x1_explorer_network_observations,
)
from .x1_explorer_structured import (
    ADDRESS_SUBVIEWS,
    STRUCTURED_CONTRACT as X1_EXPLORER_STRUCTURED_CONTRACT,
    X1_EXPLORER_IMPLEMENTATION_COMMIT,
    X1_EXPLORER_IMPLEMENTATION_REF,
    X1_EXPLORER_IMPLEMENTATION_REPOSITORY,
    X1ExplorerStructuredDiscoveryError,
    extract_related_from_web_discovery as extract_x1_explorer_related_from_web_discovery,
    extract_related_x1_explorer_entities,
    parse_x1_explorer_url,
)
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
    "X1_EXPLORER_STRUCTURED_CONTRACT",
    "X1_EXPLORER_NETWORK_ALLOWED_TARGET_HOSTS",
    "X1_EXPLORER_NETWORK_OBSERVATION_CONTRACT",
    "X1_EXPLORER_NETWORK_OFFICIAL_HOST",
    "X1_EXPLORER_READ_ONLY_RPC_METHODS",
    "X1_EXPLORER_IMPLEMENTATION_COMMIT",
    "X1_EXPLORER_IMPLEMENTATION_REF",
    "X1_EXPLORER_IMPLEMENTATION_REPOSITORY",
    "X1ExplorerStructuredDiscoveryError",
    "ADDRESS_SUBVIEWS",
    "X1_NINJA_WEB_SOURCE",
    "X1REPORT_SOURCE",
    "XDEX_WEB_SOURCE",
    "X1DocsDiscoveryProvider",
    "X1ExplorerDiscoveryProvider",
    "extract_x1_explorer_related_from_web_discovery",
    "extract_related_x1_explorer_entities",
    "parse_x1_explorer_url",
    "list_x1_explorer_network_observations",
    "X1NinjaWebDiscoveryProvider",
    "X1ReportDiscoveryProvider",
    "XDEXWebDiscoveryProvider",
    "build_provider",
    "provider_catalog",
    "provider_ids",
]
