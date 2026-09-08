"""Dedicated XONE/XNT conversion evidence providers.

Exports are resolved lazily so importing this package does not initialize
network-backed providers unless a caller actually requests one of those names.
This preserves the historical package import surface while keeping offline-only
consumers, including the primary allocation-artifact NO_LEAD runner, free from
transitive HTTP client imports.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS: dict[str, tuple[str, str]] = {
    "XONE_XNT_ALLOCATION_SOURCE_PROVENANCE_CONTRACT_VERSION": ("allocation_source_provenance", "CONTRACT_VERSION"),
    "XONE_XNT_ALLOCATION_SOURCE_CLASSES": ("allocation_source_provenance", "SOURCE_CLASSES"),
    "XONE_XNT_ALLOCATION_SOURCE_XONE_CONTRACT": ("allocation_source_provenance", "XONE_CONTRACT"),
    "XoneXntAllocationSourceProvenanceError": ("allocation_source_provenance", "XoneXntAllocationSourceProvenanceError"),
    "extract_allocation_source_provenance": ("allocation_source_provenance", "extract_allocation_source_provenance"),
    "normalize_allocation_source_url": ("allocation_source_provenance", "normalize_source_url"),
    "provenance_path_score": ("allocation_source_provenance", "provenance_path_score"),
    "summarize_allocation_source_provenance": ("allocation_source_provenance", "summarize_allocation_source_provenance"),
    "CANDIDATE_DISCOVERY_CONTRACT_VERSION": ("candidate_discovery", "CONTRACT_VERSION"),
    "CANDIDATE_DISCOVERED": ("candidate_discovery", "DISCOVERED"),
    "XoneXntCandidateDiscoveryError": ("candidate_discovery", "XoneXntCandidateDiscoveryError"),
    "discover_conversion_candidates": ("candidate_discovery", "discover_conversion_candidates"),
    "qualify_conversion_candidate": ("candidate_discovery", "qualify_conversion_candidate"),
    "XONE_XNT_X1_ALLOCATION_RECORD_CONTRACT_VERSION": ("x1_allocation_record_discovery", "CONTRACT_VERSION"),
    "XONE_XNT_X1_ALLOCATION_RECORD_XONE_CONTRACT": ("x1_allocation_record_discovery", "XONE_CONTRACT"),
    "XoneXntX1AllocationRecordDiscoveryError": ("x1_allocation_record_discovery", "XoneXntX1AllocationRecordDiscoveryError"),
    "extract_x1_allocation_records": ("x1_allocation_record_discovery", "extract_x1_allocation_records"),
    "normalize_ethereum_address": ("x1_allocation_record_discovery", "normalize_ethereum_address"),
    "qualify_x1_allocation_candidate": ("x1_allocation_record_discovery", "qualify_x1_allocation_candidate"),
    "summarize_x1_allocation_records": ("x1_allocation_record_discovery", "summarize_x1_allocation_records"),
    "XONE_XNT_X1_BINDING_CHAIN": ("x1_binding_discovery", "CHAIN"),
    "XONE_XNT_X1_BINDING_CONTRACT_VERSION": ("x1_binding_discovery", "CONTRACT_VERSION"),
    "XONE_XNT_X1_BINDING_DEFAULT_HISTORY_LIMIT": ("x1_binding_discovery", "DEFAULT_HISTORY_LIMIT"),
    "XONE_XNT_X1_BINDING_DEFAULT_TRANSACTION_LIMIT": ("x1_binding_discovery", "DEFAULT_TRANSACTION_LIMIT"),
    "XONE_XNT_X1_BINDING_DISCOVERED": ("x1_binding_discovery", "DISCOVERED"),
    "XONE_XNT_X1_KNOWN_INFRASTRUCTURE_PROGRAMS": ("x1_binding_discovery", "KNOWN_INFRASTRUCTURE_PROGRAMS"),
    "XONE_XNT_X1_BINDING_NETWORK": ("x1_binding_discovery", "NETWORK"),
    "XONE_XNT_X1_SYSTEM_PROGRAM_ID": ("x1_binding_discovery", "SYSTEM_PROGRAM_ID"),
    "XoneXntX1BindingDiscoveryError": ("x1_binding_discovery", "XoneXntX1BindingDiscoveryError"),
    "discover_x1_binding_candidates": ("x1_binding_discovery", "discover_x1_binding_candidates"),
    "qualify_x1_binding_candidate": ("x1_binding_discovery", "qualify_x1_binding_candidate"),
    "X1_XNT_MECHANISM_CHAIN": ("x1_xnt_distribution_mechanism", "CHAIN"),
    "X1_XNT_DISTRIBUTION_MECHANISM_CONTRACT_VERSION": ("x1_xnt_distribution_mechanism", "CONTRACT_VERSION"),
    "X1_XNT_MECHANISM_DISCOVERED": ("x1_xnt_distribution_mechanism", "DISCOVERED"),
    "X1_XNT_MECHANISM_NETWORK": ("x1_xnt_distribution_mechanism", "NETWORK"),
    "OFFICIAL_REWARDS_URL": ("x1_xnt_distribution_mechanism", "OFFICIAL_REWARDS_URL"),
    "STAKE_PROGRAM_ID": ("x1_xnt_distribution_mechanism", "STAKE_PROGRAM_ID"),
    "X1XntMechanismDiscoveryError": ("x1_xnt_distribution_mechanism", "X1XntMechanismDiscoveryError"),
    "discover_xnt_distribution_candidates": ("x1_xnt_distribution_mechanism", "discover_xnt_distribution_candidates"),
    "extract_xnt_mechanism_claims": ("x1_xnt_distribution_mechanism", "extract_xnt_mechanism_claims"),
    "normalize_x1_pubkey": ("x1_xnt_distribution_mechanism", "normalize_x1_pubkey"),
    "qualify_xnt_distribution_candidate": ("x1_xnt_distribution_mechanism", "qualify_xnt_distribution_candidate"),
    "MOONPARTY_DEPLOYMENT_VERIFICATION_CONTRACT_VERSION": ("moonparty_deployment_verification", "CONTRACT_VERSION"),
    "MoonPartyDeploymentVerificationError": ("moonparty_deployment_verification", "MoonPartyDeploymentVerificationError"),
    "corroborate_moonparty_deployment": ("moonparty_deployment_verification", "corroborate_moonparty_deployment"),
    "discover_moonparty_deployment_candidates": ("moonparty_deployment_verification", "discover_moonparty_deployment_candidates"),
    "verify_moonparty_deployment_candidate": ("moonparty_deployment_verification", "verify_moonparty_deployment_candidate"),
    "XONE_XNT_MOONPARTY_SOURCE_SEMANTICS_CONTRACT_VERSION": ("moonparty_source_semantics", "CONTRACT_VERSION"),
    "FAIRCRYPTO_X1_APP_COMMIT": ("moonparty_source_semantics", "FAIRCRYPTO_X1_APP_COMMIT"),
    "FAIRCRYPTO_X1_APP_REPO": ("moonparty_source_semantics", "FAIRCRYPTO_X1_APP_REPO"),
    "FAIRCRYPTO_XONE_COMMIT": ("moonparty_source_semantics", "FAIRCRYPTO_XONE_COMMIT"),
    "FAIRCRYPTO_XONE_REPO": ("moonparty_source_semantics", "FAIRCRYPTO_XONE_REPO"),
    "MOONPARTY_ABI_PATH": ("moonparty_source_semantics", "MOONPARTY_ABI_PATH"),
    "MOONPARTY_CONTEXT_PATH": ("moonparty_source_semantics", "MOONPARTY_CONTEXT_PATH"),
    "MOONPARTY_GLOBAL_PATH": ("moonparty_source_semantics", "MOONPARTY_GLOBAL_PATH"),
    "MOONPARTY_STATE_PATH": ("moonparty_source_semantics", "MOONPARTY_STATE_PATH"),
    "MOONPARTY_TYPES_PATH": ("moonparty_source_semantics", "MOONPARTY_TYPES_PATH"),
    "PROJECTS_PATH": ("moonparty_source_semantics", "PROJECTS_PATH"),
    "XONE_SOURCE_PATH": ("moonparty_source_semantics", "XONE_SOURCE_PATH"),
    "XoneXntMoonPartySourceSemanticsError": ("moonparty_source_semantics", "XoneXntMoonPartySourceSemanticsError"),
    "verify_moonparty_source_semantics": ("moonparty_source_semantics", "verify_moonparty_source_semantics"),
    "XONE_XNT_PRIMARY_ALLOCATION_ARTIFACT_RESOLUTION_CONTRACT_VERSION": ("primary_allocation_artifact_resolution", "CONTRACT_VERSION"),
    "XONE_XNT_PRIMARY_ARTIFACT_CANDIDATE": ("primary_allocation_artifact_resolution", "CANDIDATE"),
    "XONE_XNT_PRIMARY_ARTIFACT_NO_LEAD": ("primary_allocation_artifact_resolution", "NO_LEAD"),
    "XONE_XNT_PRIMARY_ARTIFACT_REJECTED": ("primary_allocation_artifact_resolution", "REJECTED"),
    "XONE_XNT_PRIMARY_ARTIFACT_RESOLVED_FOR_HANDOFF": ("primary_allocation_artifact_resolution", "RESOLVED_FOR_HANDOFF"),
    "XoneXntPrimaryAllocationArtifactResolutionError": ("primary_allocation_artifact_resolution", "XoneXntPrimaryAllocationArtifactResolutionError"),
    "no_lead_resolution": ("primary_allocation_artifact_resolution", "no_lead_resolution"),
    "resolve_primary_allocation_artifact": ("primary_allocation_artifact_resolution", "resolve_primary_allocation_artifact"),
    "XONE_SNAPSHOT_ARCHIVED_ASSET_GRAPH_CONTRACT_VERSION": ("snapshot_archived_asset_graph", "CONTRACT_VERSION"),
    "XONE_SNAPSHOT_ARCHIVED_ASSET_GRAPH_MAX_DEPTH": ("snapshot_archived_asset_graph", "MAX_GRAPH_DEPTH"),
    "TRAVERSABLE_ASSET_KINDS": ("snapshot_archived_asset_graph", "TRAVERSABLE_ASSET_KINDS"),
    "XoneSnapshotArchivedAssetGraphError": ("snapshot_archived_asset_graph", "XoneSnapshotArchivedAssetGraphError"),
    "annotate_retrieved_asset_capture": ("snapshot_archived_asset_graph", "annotate_retrieved_asset_capture"),
    "asset_reference_relevance_score": ("snapshot_archived_asset_graph", "asset_reference_relevance_score"),
    "build_asset_graph_edges": ("snapshot_archived_asset_graph", "build_asset_graph_edges"),
    "classify_archived_asset_kind": ("snapshot_archived_asset_graph", "classify_archived_asset_kind"),
    "extract_archived_asset_references": ("snapshot_archived_asset_graph", "extract_archived_asset_references"),
    "extract_asset_provenance_candidates": ("snapshot_archived_asset_graph", "extract_asset_provenance_candidates"),
    "summarize_archived_asset_graph": ("snapshot_archived_asset_graph", "summarize_archived_asset_graph"),
    "XONE_SNAPSHOT_ARCHIVAL_RECOVERY_CONTRACT_VERSION": ("snapshot_archival_recovery", "CONTRACT_VERSION"),
    "XoneSnapshotArchivalRecoveryError": ("snapshot_archival_recovery", "XoneSnapshotArchivalRecoveryError"),
    "archival_url_relevance_score": ("snapshot_archival_recovery", "archival_url_relevance_score"),
    "build_wayback_replay_url": ("snapshot_archival_recovery", "build_wayback_replay_url"),
    "extract_archival_provenance_candidates": ("snapshot_archival_recovery", "extract_archival_provenance_candidates"),
    "original_host_is_authoritative": ("snapshot_archival_recovery", "original_host_is_authoritative"),
    "parse_cdx_json": ("snapshot_archival_recovery", "parse_cdx_json"),
    "rank_archival_captures": ("snapshot_archival_recovery", "rank_archival_captures"),
    "recover_stable_x_urls": ("snapshot_archival_recovery", "recover_stable_x_urls"),
    "select_diverse_archival_captures": ("snapshot_archival_recovery", "select_diverse_archival_captures"),
    "source_role_for_original_url": ("snapshot_archival_recovery", "source_role_for_original_url"),
    "summarize_archival_recovery": ("snapshot_archival_recovery", "summarize_archival_recovery"),
    "XONE_SNAPSHOT_PROVENANCE_CONTRACT_VERSION": ("snapshot_provenance", "CONTRACT_VERSION"),
    "XoneSnapshotProvenanceError": ("snapshot_provenance", "XoneSnapshotProvenanceError"),
    "discover_repository_path_candidates": ("snapshot_provenance", "discover_repository_path_candidates"),
    "extract_provenance_candidates": ("snapshot_provenance", "extract_provenance_candidates"),
    "rank_provenance_candidates": ("snapshot_provenance", "rank_provenance_candidates"),
    "validate_provenance_url": ("snapshot_provenance", "validate_provenance_url"),
    "DEFAULT_MAX_BYTES": ("scraper", "DEFAULT_MAX_BYTES"),
    "DEFAULT_MAX_CLAIMS": ("scraper", "DEFAULT_MAX_CLAIMS"),
    "DEFAULT_MAX_SITEMAP_URLS": ("scraper", "DEFAULT_MAX_SITEMAP_URLS"),
    "DISCOVERED": ("scraper", "DISCOVERED"),
    "SCRAPER_CONTRACT": ("scraper", "SCRAPER_CONTRACT"),
    "XONE_XNT_SOURCE_REGISTRY": ("scraper", "XONE_XNT_SOURCE_REGISTRY"),
    "XoneXntContentError": ("scraper", "XoneXntContentError"),
    "XoneXntConversionScraper": ("scraper", "XoneXntConversionScraper"),
    "XoneXntHTTPError": ("scraper", "XoneXntHTTPError"),
    "XoneXntScraperError": ("scraper", "XoneXntScraperError"),
    "XoneXntSource": ("scraper", "XoneXntSource"),
    "XoneXntSourceBoundaryError": ("scraper", "XoneXntSourceBoundaryError"),
    "extract_xone_xnt_claims": ("scraper", "extract_xone_xnt_claims"),
    "get_source": ("scraper", "get_source"),
    "group_claims_for_review": ("scraper", "group_claims_for_review"),
    "parse_sitemap": ("scraper", "parse_sitemap"),
    "rank_sitemap_entries": ("scraper", "rank_sitemap_entries"),
    "source_catalog": ("scraper", "source_catalog"),
    "source_ids": ("scraper", "source_ids"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
