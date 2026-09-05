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
from .x1_explorer_browser_capture import (
    BROWSER_CAPTURE_CONTRACT as X1_EXPLORER_BROWSER_CAPTURE_CONTRACT,
    DEFAULT_DWELL_SECONDS as X1_EXPLORER_BROWSER_DEFAULT_DWELL_SECONDS,
    DEFAULT_MAX_NETWORK_EVENTS as X1_EXPLORER_BROWSER_DEFAULT_MAX_NETWORK_EVENTS,
    DEFAULT_NAVIGATION_TIMEOUT_MS as X1_EXPLORER_BROWSER_DEFAULT_NAVIGATION_TIMEOUT_MS,
    capture_x1_explorer_page_network,
)
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
from .x1_ninja_semantic_coverage import (
    BLOCKED as X1_NINJA_SEMANTIC_BLOCKED,
    PARTIAL as X1_NINJA_SEMANTIC_PARTIAL,
    SEMANTIC_COVERAGE_CONTRACT as X1_NINJA_SEMANTIC_COVERAGE_CONTRACT,
    UNAVAILABLE as X1_NINJA_SEMANTIC_UNAVAILABLE,
    VERIFIED as X1_NINJA_SEMANTIC_VERIFIED,
    x1_ninja_semantic_coverage_reconciliation,
)
from .x1_ninja_network_gaps import (
    ACCESS_LIMITED_ROUTE as X1_NINJA_ACCESS_LIMITED_ROUTE,
    CAPABILITY_WITHOUT_MACHINE_CONTRACT as X1_NINJA_CAPABILITY_WITHOUT_MACHINE_CONTRACT,
    COVERED_READ_ONLY_ROUTE as X1_NINJA_COVERED_READ_ONLY_ROUTE,
    GAP_INVENTORY_CONTRACT as X1_NINJA_NETWORK_API_GAP_INVENTORY_CONTRACT,
    SEMANTIC_GAP_NOT_ROUTE_GAP as X1_NINJA_SEMANTIC_GAP_NOT_ROUTE_GAP,
    UNKNOWN as X1_NINJA_NETWORK_GAP_UNKNOWN,
    x1_ninja_network_api_gap_inventory,
)
from .x1_ninja_structured import (
    OHLCV_PREFIX as X1_NINJA_OHLCV_PREFIX,
    POOL_CATALOG_PATH as X1_NINJA_POOL_CATALOG_PATH,
    POOL_DETAIL_PREFIX as X1_NINJA_POOL_DETAIL_PREFIX,
    STRUCTURED_CONTRACT as X1_NINJA_STRUCTURED_CONTRACT,
    TRADE_HISTORY_PREFIX as X1_NINJA_TRADE_HISTORY_PREFIX,
    TRADE_STREAM_PATH as X1_NINJA_TRADE_STREAM_PATH,
    parse_x1_ninja_url,
)
from .x1report import X1REPORT_SOURCE, X1ReportDiscoveryProvider
from .xdex import XDEX_WEB_SOURCE, XDEXWebDiscoveryProvider
from .xdex_coverage_reconciliation import (
    COVERAGE_RECONCILIATION_CONTRACT as XDEX_COVERAGE_RECONCILIATION_CONTRACT,
    KNOWN_DIRECT_READONLY_SURFACES as XDEX_KNOWN_DIRECT_READONLY_SURFACES,
    KNOWN_DOCUMENTATION_SURFACE as XDEX_KNOWN_DOCUMENTATION_SURFACE,
    KNOWN_EXECUTION_EXCLUSIONS as XDEX_KNOWN_EXECUTION_EXCLUSIONS,
    KNOWN_UI_ONLY_SURFACES as XDEX_KNOWN_UI_ONLY_SURFACES,
    xdex_coverage_reconciliation,
)
from .xdex_extended_structured import (
    EXTENDED_STRUCTURED_CONTRACT as XDEX_EXTENDED_READONLY_STRUCTURED_CONTRACT,
    FRONTEND_QUOTE_ALIAS_PATH as XDEX_FRONTEND_QUOTE_ALIAS_PATH,
    ORACLE_SELL_QUOTE_PATH as XDEX_ORACLE_SELL_QUOTE_PATH,
    ORACLE_TOKEN_PRICE_PATH as XDEX_ORACLE_TOKEN_PRICE_PATH,
    parse_xdex_extended_readonly_url,
)
from .xdex_network_gaps import (
    COVERED_READ_ONLY as XDEX_COVERED_READ_ONLY,
    EXECUTION_ADJACENT_EXCLUDED as XDEX_EXECUTION_ADJACENT_EXCLUDED,
    GAP_REGISTRY_CONTRACT as XDEX_NETWORK_GAP_REGISTRY_CONTRACT,
    READ_ONLY_GAP_CANDIDATE as XDEX_READ_ONLY_GAP_CANDIDATE,
    UI_ONLY_CANDIDATE as XDEX_UI_ONLY_CANDIDATE,
    UNKNOWN as XDEX_NETWORK_GAP_UNKNOWN,
    classify_xdex_network_surface,
    xdex_network_gap_report,
)
from .xdex_structured import (
    STRUCTURED_CONTRACT as XDEX_STRUCTURED_CONTRACT,
    X1PAYS_CORROBORATION_COMMIT,
    X1PAYS_CORROBORATION_REF,
    X1PAYS_CORROBORATION_REPOSITORY,
    XDEXStructuredDiscoveryError,
    parse_xdex_url,
)


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
    "X1_EXPLORER_BROWSER_CAPTURE_CONTRACT",
    "X1_EXPLORER_BROWSER_DEFAULT_DWELL_SECONDS",
    "X1_EXPLORER_BROWSER_DEFAULT_MAX_NETWORK_EVENTS",
    "X1_EXPLORER_BROWSER_DEFAULT_NAVIGATION_TIMEOUT_MS",
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
    "X1_NINJA_STRUCTURED_CONTRACT",
    "X1_NINJA_NETWORK_API_GAP_INVENTORY_CONTRACT",
    "X1_NINJA_SEMANTIC_COVERAGE_CONTRACT",
    "X1_NINJA_SEMANTIC_VERIFIED",
    "X1_NINJA_SEMANTIC_PARTIAL",
    "X1_NINJA_SEMANTIC_BLOCKED",
    "X1_NINJA_SEMANTIC_UNAVAILABLE",
    "X1_NINJA_COVERED_READ_ONLY_ROUTE",
    "X1_NINJA_ACCESS_LIMITED_ROUTE",
    "X1_NINJA_SEMANTIC_GAP_NOT_ROUTE_GAP",
    "X1_NINJA_CAPABILITY_WITHOUT_MACHINE_CONTRACT",
    "X1_NINJA_NETWORK_GAP_UNKNOWN",
    "X1_NINJA_POOL_CATALOG_PATH",
    "X1_NINJA_POOL_DETAIL_PREFIX",
    "X1_NINJA_TRADE_HISTORY_PREFIX",
    "X1_NINJA_OHLCV_PREFIX",
    "X1_NINJA_TRADE_STREAM_PATH",
    "X1REPORT_SOURCE",
    "XDEX_WEB_SOURCE",
    "XDEX_STRUCTURED_CONTRACT",
    "XDEX_NETWORK_GAP_REGISTRY_CONTRACT",
    "XDEX_EXTENDED_READONLY_STRUCTURED_CONTRACT",
    "XDEX_COVERAGE_RECONCILIATION_CONTRACT",
    "XDEX_KNOWN_DIRECT_READONLY_SURFACES",
    "XDEX_KNOWN_DOCUMENTATION_SURFACE",
    "XDEX_KNOWN_EXECUTION_EXCLUSIONS",
    "XDEX_KNOWN_UI_ONLY_SURFACES",
    "XDEX_FRONTEND_QUOTE_ALIAS_PATH",
    "XDEX_ORACLE_TOKEN_PRICE_PATH",
    "XDEX_ORACLE_SELL_QUOTE_PATH",
    "XDEX_COVERED_READ_ONLY",
    "XDEX_EXECUTION_ADJACENT_EXCLUDED",
    "XDEX_READ_ONLY_GAP_CANDIDATE",
    "XDEX_UI_ONLY_CANDIDATE",
    "XDEX_NETWORK_GAP_UNKNOWN",
    "X1PAYS_CORROBORATION_COMMIT",
    "X1PAYS_CORROBORATION_REF",
    "X1PAYS_CORROBORATION_REPOSITORY",
    "XDEXStructuredDiscoveryError",
    "X1DocsDiscoveryProvider",
    "X1ExplorerDiscoveryProvider",
    "extract_x1_explorer_related_from_web_discovery",
    "extract_related_x1_explorer_entities",
    "parse_x1_explorer_url",
    "list_x1_explorer_network_observations",
    "capture_x1_explorer_page_network",
    "X1NinjaWebDiscoveryProvider",
    "parse_x1_ninja_url",
    "x1_ninja_network_api_gap_inventory",
    "x1_ninja_semantic_coverage_reconciliation",
    "X1ReportDiscoveryProvider",
    "XDEXWebDiscoveryProvider",
    "parse_xdex_url",
    "classify_xdex_network_surface",
    "xdex_network_gap_report",
    "parse_xdex_extended_readonly_url",
    "xdex_coverage_reconciliation",
    "build_provider",
    "provider_catalog",
    "provider_ids",
]
